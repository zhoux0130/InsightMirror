import type { PrismaClient, Prisma } from '@prisma/client';
import type { Application } from '@/types';
import { createStockDetailService } from './stock-detail-service';

// ── Types ────────────────────────────────────────────────────────

export interface CreateBasketInput {
  name: string;
  description?: string;
  capital?: number;
}

export interface UpdateBasketInput {
  name?: string;
  description?: string;
  capital?: number;
  status?: 'active' | 'archived';
}

export interface BuyInput {
  symbol: string;
  buyDate: string;
  buyPrice?: number;
  shares?: number;
  triggerType?: 'manual' | 'rule';
  ruleId?: string;
  note?: string;
}

export interface SellInput {
  sellDate: string;
  sellPrice?: number;
  note?: string;
}

export interface ConditionGroup {
  operator: 'AND' | 'OR';
  conditions: Condition[];
}

export interface Condition {
  type: 'fact' | 'computed';
  indicator: string;
  op: '>' | '<' | '>=' | '<=' | '==' | '!=';
  value: number;
}

export interface CreateRuleInput {
  name?: string;
  conditionGroup: ConditionGroup;
  enabled?: boolean;
}

export interface UpdateRuleInput {
  name?: string;
  conditionGroup?: ConditionGroup;
  enabled?: boolean;
}

export interface PositionPnL {
  id: string;
  symbol: string;
  buyDate: string;
  buyPrice: number;
  shares: number;
  sellDate: string | null;
  sellPrice: number | null;
  currentPrice: number | null;
  cost: number;
  marketValue: number;
  pnl: number;
  pnlPercent: number;
  holdingDays: number;
  status: 'open' | 'closed';
}

export interface BasketPnL {
  basketId: string;
  basketName: string;
  capital: number;
  totalCost: number;
  totalMarketValue: number;
  totalPnl: number;
  totalPnlPercent: number;
  winRate: number;
  avgPnlPercent: number;
  maxDrawdown: number;
  openCount: number;
  closedCount: number;
  positions: PositionPnL[];
}

export interface ScanResult {
  symbol: string;
  ruleId: string;
  ruleName: string | null;
  triggered: boolean;
  details: Record<string, { value: number; passed: boolean }>;
}

export class BasketServiceError extends Error {
  statusCode: number;
  constructor(message: string, statusCode = 400) {
    super(message);
    this.statusCode = statusCode;
  }
}

// ── Service ──────────────────────────────────────────────────────

export function createBasketService(app: Application) {
  return new BasketService(app.$prisma, app);
}

export class BasketService {
  constructor(
    private readonly prisma: PrismaClient,
    private readonly app: Application,
  ) {}

  // ── Basket CRUD ──────────────────────────────────────────────

  async createBasket(userId: string, input: CreateBasketInput) {
    return this.prisma.basket.create({
      data: {
        userId,
        name: input.name,
        description: input.description,
        capital: input.capital ?? 100000,
      },
      include: { stocks: true, rules: true, positions: true },
    });
  }

  async listBaskets(userId: string) {
    const baskets = await this.prisma.basket.findMany({
      where: { userId },
      include: {
        stocks: true,
        positions: true,
      },
      orderBy: { createdAt: 'desc' },
    });

    return baskets.map((b) => ({
      id: b.id,
      name: b.name,
      description: b.description,
      capital: toNumber(b.capital),
      status: b.status,
      stockCount: b.stocks.length,
      openPositionCount: b.positions.filter((p) => !p.sellDate).length,
      closedPositionCount: b.positions.filter((p) => p.sellDate).length,
      createdAt: b.createdAt.toISOString(),
      updatedAt: b.updatedAt.toISOString(),
    }));
  }

  async getBasket(userId: string, basketId: string) {
    const basket = await this.prisma.basket.findFirst({
      where: { id: basketId, userId },
      include: { stocks: true, rules: true, positions: { include: { rule: true } } },
    });
    if (!basket) {
      throw new BasketServiceError('篮子不存在', 404);
    }
    return {
      ...basket,
      capital: toNumber(basket.capital),
      positions: basket.positions.map(formatPosition),
    };
  }

  async updateBasket(userId: string, basketId: string, input: UpdateBasketInput) {
    await this.ensureOwnership(userId, basketId);
    return this.prisma.basket.update({
      where: { id: basketId },
      data: {
        ...(input.name !== undefined && { name: input.name }),
        ...(input.description !== undefined && { description: input.description }),
        ...(input.capital !== undefined && { capital: input.capital }),
        ...(input.status !== undefined && { status: input.status }),
      },
      include: { stocks: true, rules: true, positions: true },
    });
  }

  async deleteBasket(userId: string, basketId: string) {
    await this.ensureOwnership(userId, basketId);
    await this.prisma.basket.delete({ where: { id: basketId } });
  }

  // ── Watchlist (BasketStock) ──────────────────────────────────

  async addStock(userId: string, basketId: string, symbol: string) {
    await this.ensureOwnership(userId, basketId);

    const exists = await this.prisma.basketStock.findUnique({
      where: { basketId_symbol: { basketId, symbol } },
    });
    if (exists) {
      throw new BasketServiceError('该股票已在关注列表中');
    }

    return this.prisma.basketStock.create({
      data: { basketId, symbol },
    });
  }

  async removeStock(userId: string, basketId: string, symbol: string) {
    await this.ensureOwnership(userId, basketId);
    const stock = await this.prisma.basketStock.findUnique({
      where: { basketId_symbol: { basketId, symbol } },
    });
    if (!stock) {
      throw new BasketServiceError('该股票不在关注列表中', 404);
    }
    await this.prisma.basketStock.delete({
      where: { id: stock.id },
    });
  }

  // ── Rules ────────────────────────────────────────────────────

  async createRule(userId: string, basketId: string, input: CreateRuleInput) {
    await this.ensureOwnership(userId, basketId);
    return this.prisma.basketRule.create({
      data: {
        basketId,
        name: input.name,
        conditionGroup: input.conditionGroup as unknown as Prisma.JsonObject,
        enabled: input.enabled ?? true,
      },
    });
  }

  async updateRule(userId: string, basketId: string, ruleId: string, input: UpdateRuleInput) {
    await this.ensureOwnership(userId, basketId);
    const rule = await this.prisma.basketRule.findFirst({
      where: { id: ruleId, basketId },
    });
    if (!rule) {
      throw new BasketServiceError('规则不存在', 404);
    }
    return this.prisma.basketRule.update({
      where: { id: ruleId },
      data: {
        ...(input.name !== undefined && { name: input.name }),
        ...(input.conditionGroup !== undefined && {
          conditionGroup: input.conditionGroup as unknown as Prisma.JsonObject,
        }),
        ...(input.enabled !== undefined && { enabled: input.enabled }),
      },
    });
  }

  async deleteRule(userId: string, basketId: string, ruleId: string) {
    await this.ensureOwnership(userId, basketId);
    const rule = await this.prisma.basketRule.findFirst({
      where: { id: ruleId, basketId },
    });
    if (!rule) {
      throw new BasketServiceError('规则不存在', 404);
    }
    await this.prisma.basketRule.delete({ where: { id: ruleId } });
  }

  // ── Positions (Buy / Sell) ───────────────────────────────────

  async buy(userId: string, basketId: string, input: BuyInput) {
    const basket = await this.getBasket(userId, basketId);

    // Verify stock is in watchlist
    const inWatchlist = basket.stocks.some((s) => s.symbol === input.symbol);
    if (!inWatchlist) {
      throw new BasketServiceError('请先将该股票添加到关注列表');
    }

    let buyPrice = input.buyPrice;
    if (!buyPrice) {
      // Default: fetch close price from DailyBar
      const bar = await this.prisma.dailyBar.findUnique({
        where: {
          symbol_tradeDate: {
            symbol: input.symbol,
            tradeDate: new Date(input.buyDate),
          },
        },
      });
      if (!bar) {
        throw new BasketServiceError(`未找到 ${input.symbol} 在 ${input.buyDate} 的行情数据`);
      }
      buyPrice = toNumber(bar.close);
    }

    let shares = input.shares;
    if (!shares) {
      // Equal-weight allocation: capital / stockCount / buyPrice
      const stockCount = basket.stocks.length;
      const allocationPerStock = toNumber(basket.capital) / Math.max(stockCount, 1);
      shares = Math.floor(allocationPerStock / buyPrice / 100) * 100; // Round to lots of 100
      if (shares <= 0) shares = 100;
    }

    return this.prisma.position.create({
      data: {
        basketId,
        symbol: input.symbol,
        buyDate: new Date(input.buyDate),
        buyPrice,
        shares,
        triggerType: input.triggerType ?? 'manual',
        ruleId: input.ruleId,
        note: input.note,
      },
    });
  }

  async sell(userId: string, basketId: string, positionId: string, input: SellInput) {
    await this.ensureOwnership(userId, basketId);

    const position = await this.prisma.position.findFirst({
      where: { id: positionId, basketId },
    });
    if (!position) {
      throw new BasketServiceError('持仓不存在', 404);
    }
    if (position.sellDate) {
      throw new BasketServiceError('该持仓已平仓');
    }

    let sellPrice = input.sellPrice;
    if (!sellPrice) {
      const bar = await this.prisma.dailyBar.findUnique({
        where: {
          symbol_tradeDate: {
            symbol: position.symbol,
            tradeDate: new Date(input.sellDate),
          },
        },
      });
      if (!bar) {
        throw new BasketServiceError(`未找到 ${position.symbol} 在 ${input.sellDate} 的行情数据`);
      }
      sellPrice = toNumber(bar.close);
    }

    return this.prisma.position.update({
      where: { id: positionId },
      data: {
        sellDate: new Date(input.sellDate),
        sellPrice,
        note: input.note ?? position.note,
      },
    });
  }

  async listPositions(userId: string, basketId: string, status?: 'open' | 'closed' | 'all') {
    await this.ensureOwnership(userId, basketId);

    const where: Prisma.PositionWhereInput = { basketId };
    if (status === 'open') {
      where.sellDate = null;
    } else if (status === 'closed') {
      where.sellDate = { not: null };
    }

    const positions = await this.prisma.position.findMany({
      where,
      include: { rule: true },
      orderBy: { buyDate: 'desc' },
    });

    return positions.map(formatPosition);
  }

  // ── PnL Calculation ──────────────────────────────────────────

  async getBasketPnl(userId: string, basketId: string): Promise<BasketPnL> {
    const basket = await this.getBasket(userId, basketId);
    const positions = basket.positions;

    // Get latest prices for open positions
    const openSymbols = [...new Set(
      positions.filter((p) => !p.sellDate).map((p) => p.symbol)
    )];

    const latestPrices = new Map<string, number>();
    for (const symbol of openSymbols) {
      const bar = await this.prisma.dailyBar.findFirst({
        where: { symbol },
        orderBy: { tradeDate: 'desc' },
      });
      if (bar) {
        latestPrices.set(symbol, toNumber(bar.close));
      }
    }

    const positionPnls: PositionPnL[] = positions.map((p) => {
      const buyPrice = toNumber(p.buyPrice);
      const cost = buyPrice * p.shares;
      const isClosed = !!p.sellDate;
      const exitPrice = isClosed ? toNumber(p.sellPrice) : (latestPrices.get(p.symbol) ?? buyPrice);
      const marketValue = exitPrice * p.shares;
      const pnl = marketValue - cost;
      const pnlPercent = cost > 0 ? pnl / cost : 0;

      const buyDateObj = new Date(p.buyDate);
      const endDateObj = isClosed ? new Date(p.sellDate!) : new Date();
      const holdingDays = Math.ceil((endDateObj.getTime() - buyDateObj.getTime()) / (24 * 60 * 60 * 1000));

      return {
        id: p.id,
        symbol: p.symbol,
        buyDate: formatDate(buyDateObj),
        buyPrice,
        shares: p.shares,
        sellDate: p.sellDate ? formatDate(new Date(p.sellDate)) : null,
        sellPrice: p.sellPrice != null ? toNumber(p.sellPrice) : null,
        currentPrice: !isClosed ? (latestPrices.get(p.symbol) ?? null) : null,
        cost,
        marketValue,
        pnl,
        pnlPercent,
        holdingDays,
        status: isClosed ? 'closed' : 'open',
      };
    });

    const totalCost = positionPnls.reduce((s, p) => s + p.cost, 0);
    const totalMarketValue = positionPnls.reduce((s, p) => s + p.marketValue, 0);
    const totalPnl = totalMarketValue - totalCost;
    const totalPnlPercent = totalCost > 0 ? totalPnl / totalCost : 0;

    const closedPositions = positionPnls.filter((p) => p.status === 'closed');
    const winCount = closedPositions.filter((p) => p.pnl > 0).length;
    const winRate = closedPositions.length > 0 ? winCount / closedPositions.length : 0;
    const avgPnlPercent = closedPositions.length > 0
      ? closedPositions.reduce((s, p) => s + p.pnlPercent, 0) / closedPositions.length
      : 0;

    // Simple max drawdown from closed positions
    let maxDrawdown = 0;
    let runningPnl = 0;
    let peakPnl = 0;
    for (const p of closedPositions.sort((a, b) => a.sellDate!.localeCompare(b.sellDate!))) {
      runningPnl += p.pnl;
      peakPnl = Math.max(peakPnl, runningPnl);
      const drawdown = peakPnl > 0 ? (peakPnl - runningPnl) / peakPnl : 0;
      maxDrawdown = Math.max(maxDrawdown, drawdown);
    }

    return {
      basketId: basket.id,
      basketName: basket.name,
      capital: toNumber(basket.capital),
      totalCost,
      totalMarketValue,
      totalPnl,
      totalPnlPercent,
      winRate,
      avgPnlPercent,
      maxDrawdown,
      openCount: positionPnls.filter((p) => p.status === 'open').length,
      closedCount: closedPositions.length,
      positions: positionPnls,
    };
  }

  async compareBaskets(userId: string) {
    const baskets = await this.prisma.basket.findMany({
      where: { userId },
      include: { stocks: true, positions: true },
    });

    const results = await Promise.all(
      baskets.map(async (b) => {
        try {
          const pnl = await this.getBasketPnl(userId, b.id);
          return {
            basketId: pnl.basketId,
            basketName: pnl.basketName,
            capital: pnl.capital,
            totalPnl: pnl.totalPnl,
            totalPnlPercent: pnl.totalPnlPercent,
            winRate: pnl.winRate,
            avgPnlPercent: pnl.avgPnlPercent,
            maxDrawdown: pnl.maxDrawdown,
            openCount: pnl.openCount,
            closedCount: pnl.closedCount,
            stockCount: b.stocks.length,
          };
        } catch {
          return {
            basketId: b.id,
            basketName: b.name,
            capital: toNumber(b.capital),
            totalPnl: 0,
            totalPnlPercent: 0,
            winRate: 0,
            avgPnlPercent: 0,
            maxDrawdown: 0,
            openCount: 0,
            closedCount: 0,
            stockCount: b.stocks.length,
          };
        }
      })
    );

    return results;
  }

  // ── Rule Scan ────────────────────────────────────────────────

  async scanRules(userId: string, basketId: string): Promise<ScanResult[]> {
    const basket = await this.getBasket(userId, basketId);
    const enabledRules = basket.rules.filter((r) => r.enabled);
    if (enabledRules.length === 0) return [];

    const stockDetailService = createStockDetailService(this.app);
    const results: ScanResult[] = [];

    for (const stock of basket.stocks) {
      // Get indicator values once per stock (expensive: DB + vector search)
      let indicators: Record<string, number> = {};
      let fetchFailed = false;
      try {
        indicators = await this.getIndicators(stock.symbol, stockDetailService);
      } catch {
        fetchFailed = true;
      }

      for (const rule of enabledRules) {
        const conditionGroup = rule.conditionGroup as unknown as ConditionGroup;
        const details: Record<string, { value: number; passed: boolean }> = {};
        let triggered = false;

        if (!fetchFailed) {
          const conditionResults = conditionGroup.conditions.map((cond) => {
            const actualValue = indicators[cond.indicator] ?? 0;
            const passed = evaluateCondition(actualValue, cond.op, cond.value);
            details[cond.indicator] = { value: actualValue, passed };
            return passed;
          });

          triggered = conditionGroup.operator === 'AND'
            ? conditionResults.every(Boolean)
            : conditionResults.some(Boolean);
        }

        results.push({
          symbol: stock.symbol,
          ruleId: rule.id,
          ruleName: rule.name,
          triggered,
          details,
        });
      }
    }

    return results;
  }

  // ── Private Helpers ──────────────────────────────────────────

  private async ensureOwnership(userId: string, basketId: string) {
    const basket = await this.prisma.basket.findFirst({
      where: { id: basketId, userId },
    });
    if (!basket) {
      throw new BasketServiceError('篮子不存在', 404);
    }
    return basket;
  }

  private async getIndicators(
    symbol: string,
    stockDetailService: ReturnType<typeof createStockDetailService>,
  ): Promise<Record<string, number>> {
    const indicators: Record<string, number> = {};

    // Fetch recent bars for fact-type indicators
    const bars = await this.prisma.dailyBar.findMany({
      where: { symbol },
      orderBy: { tradeDate: 'desc' },
      take: 60,
    });

    if (bars.length === 0) return indicators;

    const latest = bars[0];
    const close = toNumber(latest.close);

    // price_vs_ma20: close / MA20 - 1
    if (bars.length >= 20) {
      const ma20 = bars.slice(0, 20).reduce((s, b) => s + toNumber(b.close), 0) / 20;
      indicators['price_vs_ma20'] = ma20 > 0 ? (close / ma20 - 1) * 100 : 0;
    }

    // price_vs_ma60: close / MA60 - 1
    if (bars.length >= 60) {
      const ma60 = bars.slice(0, 60).reduce((s, b) => s + toNumber(b.close), 0) / 60;
      indicators['price_vs_ma60'] = ma60 > 0 ? (close / ma60 - 1) * 100 : 0;
    }

    // volume_ratio_5d: latest volume / avg volume of last 5 days
    if (bars.length >= 6) {
      const avgVol5 = bars.slice(1, 6).reduce((s, b) => s + Number(b.volume), 0) / 5;
      indicators['volume_ratio_5d'] = avgVol5 > 0 ? Number(latest.volume) / avgVol5 : 0;
    }

    // pct_change
    indicators['pct_change'] = latest.pctChange != null ? toNumber(latest.pctChange) : 0;

    // Use StockDetailService for computed indicators
    try {
      const detail = await stockDetailService.getDetail({ symbol });
      indicators['emotion_temp'] = detail.emotion.temp;
      indicators['rating_score'] = detail.rating.score;
      indicators['up_probability'] = detail.riskReward.upProbability * 100;
      indicators['avg_max_drawdown'] = detail.riskReward.avgMaxDrawdown * 100;
    } catch {
      // computed indicators unavailable
    }

    return indicators;
  }
}

// ── Utilities ──────────────────────────────────────────────────

function toNumber(value: unknown): number {
  if (value == null) return 0;
  return Number(value);
}

function formatDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function formatPosition(p: any) {
  return {
    ...p,
    buyPrice: toNumber(p.buyPrice),
    sellPrice: p.sellPrice != null ? toNumber(p.sellPrice) : null,
    buyDate: p.buyDate instanceof Date ? formatDate(p.buyDate) : p.buyDate,
    sellDate: p.sellDate instanceof Date ? formatDate(p.sellDate) : p.sellDate,
  };
}

function evaluateCondition(actual: number, op: string, expected: number): boolean {
  switch (op) {
    case '>': return actual > expected;
    case '<': return actual < expected;
    case '>=': return actual >= expected;
    case '<=': return actual <= expected;
    case '==': return Math.abs(actual - expected) < 0.0001;
    case '!=': return Math.abs(actual - expected) >= 0.0001;
    default: return false;
  }
}
