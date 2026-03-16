import type { PrismaClient } from '@prisma/client';
import { compute } from '@/config';
import type { Application } from '@/types';
import type { PgVectorService, SimilarResult } from '@/services/pgvector';
import {
  buildEmotionInsight,
  buildEntryInsight,
  buildFlowInsight,
  buildPhaseInsight,
  buildRatingInsight,
  type DailyBarInput,
} from './stock-detail-calculations';

type DetailQuery = {
  symbol: string;
  endDate?: string;
  topK?: number;
};

type Market = 'CN' | 'US';

type StockOptionRow = {
  symbol: string;
  name: string;
  market: string;
  last_trade_date: Date;
};

type ForwardBar = {
  close: number;
  high: number;
  low: number;
};

export interface SimilarMatch extends Omit<SimilarResult, 'distance'> {
  distance?: number;
  baseClose?: number;
}

export interface ForwardMetric {
  similarity: number;
  return3d: number;
  return5d: number;
  maxDrawdown5d: number;
  continuation3d: boolean;
}

export interface SimilarityDimensionBreakdown {
  key: 'price_shape' | 'return_rhythm' | 'volume_profile' | 'stat_signature';
  label: string;
  description: string;
  similarity: number;
  score: number;
}

export interface SimilarityBreakdown {
  symbol: string;
  endDate: string;
  overallSimilarity: number;
  overallScore: number;
  windowSize: number;
  dimensions: SimilarityDimensionBreakdown[];
}

export interface StockOption {
  symbol: string;
  name: string;
  market: string;
  lastTradeDate: string;
}

export interface StockDetailResponse {
  security: {
    symbol: string;
    name: string;
    tradeDate: string;
  };
  quote: {
    close: number;
    changePct: number;
  };
  rating: {
    label: '可参与' | '观察' | '规避';
    score: number;
    stageTrend: string;
    mainlineConsistency: '高' | '中' | '低' | '--';
    reasons: string[];
  };
  entry: {
    mode: 'range' | 'wait';
    lower: number | null;
    upper: number | null;
    position: string;
    invalidationLevel: number | null;
    watchLevel: number | null;
    note: string;
  };
  emotion: {
    temp: number;
    status: string;
    warning: string | null;
  };
  phase: {
    current: string;
    nodes: string[];
    activeNode: string;
    trendBroken: boolean;
    trendNote: string;
  };
  riskReward: {
    upProbability: number;
    avgMaxDrawdown: number;
    similarCount: number;
    sampleYears: number;
    topK: number;
  };
  flow: {
    continuity: '良好' | '一般' | '偏弱';
    signals: string[];
    continuationProb3d: number;
    quote: string;
  };
  similarityBreakdown: SimilarityBreakdown | null;
  similarSamples: Array<{
    segmentId: number;
    symbol: string;
    endDate: string;
    similarity: number;
    return5d: number;
    maxDrawdown5d: number;
  }>;
}

export class StockDetailError extends Error {
  statusCode: number;

  constructor(message: string, statusCode = 400) {
    super(message);
    this.statusCode = statusCode;
  }
}

export function dedupeMatches(matches: SimilarMatch[], minGapDays: number): SimilarMatch[] {
  const accepted: SimilarMatch[] = [];
  const bySymbol = new Map<string, string[]>();

  for (const match of [...matches].sort((left, right) => right.similarity - left.similarity)) {
    const dates = bySymbol.get(match.symbol) ?? [];
    const tooClose = dates.some((date) => {
      const gap = Math.abs(dateDiffInDays(date, match.endDate));
      return gap < minGapDays;
    });
    if (tooClose) {
      continue;
    }
    accepted.push(match);
    bySymbol.set(match.symbol, [...dates, match.endDate]);
  }

  return accepted;
}

export function selectSameSymbolMatches(
  matches: SimilarMatch[],
  symbol: string,
  minGapDays: number,
  limit: number
): SimilarMatch[] {
  return dedupeMatches(
    matches.filter((match) => match.symbol === symbol),
    minGapDays
  ).slice(0, limit);
}

export function buildForwardMetric(
  baseClose: number,
  futureBars: ForwardBar[],
  invalidationLevel: number
): Omit<ForwardMetric, 'similarity'> | null {
  if (futureBars.length < 5 || baseClose <= 0) {
    return null;
  }

  const first3 = futureBars.slice(0, 3);
  const first5 = futureBars.slice(0, 5);

  return {
    return3d: round(first3[first3.length - 1].close / baseClose - 1, 4),
    return5d: round(first5[first5.length - 1].close / baseClose - 1, 4),
    maxDrawdown5d: round(Math.min(...first5.map((bar) => bar.low / baseClose - 1)), 4),
    continuation3d:
      Math.max(...first3.map((bar) => bar.high)) > baseClose
      && Math.min(...first3.map((bar) => bar.low)) > invalidationLevel,
  };
}

export function summarizeForwardMetrics(metrics: ForwardMetric[]) {
  if (metrics.length === 0) {
    return {
      similarCount: 0,
      upProbability: 0,
      avgMaxDrawdown: 0,
      continuationProb3d: 0,
    };
  }

  const upCount = metrics.filter((metric) => metric.return5d > 0).length;
  const continuationCount = metrics.filter((metric) => metric.continuation3d).length;
  const avgMaxDrawdown = metrics.reduce((sum, metric) => sum + Math.abs(metric.maxDrawdown5d), 0)
    / metrics.length;

  return {
    similarCount: metrics.length,
    upProbability: round(upCount / metrics.length, 4),
    avgMaxDrawdown: round(avgMaxDrawdown, 4),
    continuationProb3d: round(continuationCount / metrics.length, 4),
  };
}

export function buildSimilarityBreakdown(
  queryBars: DailyBarInput[],
  compareBars: DailyBarInput[],
  symbol: string,
  endDate: string,
  overallSimilarityOverride?: number
): SimilarityBreakdown {
  const query = ensureWindow(queryBars);
  const compare = ensureWindow(compareBars);

  const queryComponents = buildSimilarityComponents(query);
  const compareComponents = buildSimilarityComponents(compare);

  const dimensions: SimilarityDimensionBreakdown[] = [
    {
      key: 'price_shape',
      label: '价格形状',
      description: '60日收盘路径的形状相似度',
      similarity: round(clamp(cosineSimilarity(queryComponents.priceShape, compareComponents.priceShape), 0, 1), 4),
      score: round(clamp(cosineSimilarity(queryComponents.priceShape, compareComponents.priceShape), 0, 1) * 100, 1),
    },
    {
      key: 'return_rhythm',
      label: '收益节奏',
      description: '日收益波动的快慢和节奏',
      similarity: round(clamp(cosineSimilarity(queryComponents.returnRhythm, compareComponents.returnRhythm), 0, 1), 4),
      score: round(clamp(cosineSimilarity(queryComponents.returnRhythm, compareComponents.returnRhythm), 0, 1) * 100, 1),
    },
    {
      key: 'volume_profile',
      label: '量能轮廓',
      description: '成交量放缩的轮廓相似度',
      similarity: round(clamp(cosineSimilarity(queryComponents.volumeProfile, compareComponents.volumeProfile), 0, 1), 4),
      score: round(clamp(cosineSimilarity(queryComponents.volumeProfile, compareComponents.volumeProfile), 0, 1) * 100, 1),
    },
    {
      key: 'stat_signature',
      label: '统计签名',
      description: '偏度、峰度、最大回撤的相似度',
      similarity: round(clamp(cosineSimilarity(queryComponents.statSignature, compareComponents.statSignature), 0, 1), 4),
      score: round(clamp(cosineSimilarity(queryComponents.statSignature, compareComponents.statSignature), 0, 1) * 100, 1),
    },
  ];

  const overallSimilarity = overallSimilarityOverride
    ?? clamp(cosineSimilarity(queryComponents.fullVector, compareComponents.fullVector), 0, 1);

  return {
    symbol,
    endDate,
    overallSimilarity: round(overallSimilarity, 4),
    overallScore: round(overallSimilarity * 100, 1),
    windowSize: 60,
    dimensions,
  };
}

export function createStockDetailService(app: Application) {
  return new StockDetailService(app.$prisma, app.$pgvector);
}

export class StockDetailService {
  constructor(
    private readonly prisma: PrismaClient,
    private readonly pgvector: PgVectorService
  ) {}

  async listOptions(market?: Market): Promise<StockOption[]> {
    const rows = market
      ? await this.prisma.$queryRaw<StockOptionRow[]>`
          SELECT sm.symbol, sm.name, sm.market, MAX(db.trade_date) AS last_trade_date
          FROM security_master sm
          JOIN daily_bar db ON db.symbol = sm.symbol
          WHERE sm.market = ${market}
            AND EXISTS (
              SELECT 1 FROM segment_index si
              WHERE si.symbol = sm.symbol
                AND si.window_size = 60
                AND si.feature_version = 'v1'
            )
          GROUP BY sm.symbol, sm.name, sm.market
          ORDER BY sm.symbol ASC
        `
      : await this.prisma.$queryRaw<StockOptionRow[]>`
          SELECT sm.symbol, sm.name, sm.market, MAX(db.trade_date) AS last_trade_date
          FROM security_master sm
          JOIN daily_bar db ON db.symbol = sm.symbol
          WHERE EXISTS (
            SELECT 1 FROM segment_index si
            WHERE si.symbol = sm.symbol
              AND si.window_size = 60
              AND si.feature_version = 'v1'
          )
          GROUP BY sm.symbol, sm.name, sm.market
          ORDER BY sm.symbol ASC
        `;

    return rows.map((row) => ({
      symbol: row.symbol,
      name: row.name,
      market: row.market,
      lastTradeDate: formatDate(row.last_trade_date),
    }));
  }

  async getDetail(params: DetailQuery): Promise<StockDetailResponse> {
    const topK = clampInt(params.topK ?? 100, 20, 150);
    const security = await this.prisma.securityMaster.findUnique({
      where: { symbol: params.symbol },
    });

    if (!security) {
      throw new StockDetailError('股票不存在或尚未初始化', 404);
    }

    const latestBar = await this.prisma.dailyBar.findFirst({
      where: {
        symbol: params.symbol,
        ...(params.endDate ? { tradeDate: { lte: new Date(params.endDate) } } : {}),
      },
      orderBy: { tradeDate: 'desc' },
    });

    if (!latestBar) {
      throw new StockDetailError('股票尚无可用行情数据', 404);
    }

    const bars = (await this.prisma.dailyBar.findMany({
      where: {
        symbol: params.symbol,
        tradeDate: { lte: latestBar.tradeDate },
      },
      orderBy: { tradeDate: 'desc' },
      take: 260,
    }))
      .reverse()
      .map((bar) => ({
        tradeDate: formatDate(bar.tradeDate),
        open: toNumber(bar.open),
        high: toNumber(bar.high),
        low: toNumber(bar.low),
        close: toNumber(bar.close),
        volume: Number(bar.volume),
        amount: toNumber(bar.amount),
        pctChange: bar.pctChange == null ? null : toNumber(bar.pctChange),
      }));

    if (bars.length < 60) {
      throw new StockDetailError('该股票历史长度不足 60 个交易日，无法生成结构分析', 400);
    }

    const windowBars = bars.slice(-60);
    const phase = buildPhaseInsight(windowBars);
    const entry = buildEntryInsight(windowBars);
    const emotion = buildEmotionInsight(bars);
    const flow = buildFlowInsight(windowBars);
    const mainlineConsistency = buildMainlineConsistencyProxy(phase, flow, emotion.temp);

    const vector = await computeFeatureVector(windowBars);
    const endDate = formatDate(latestBar.tradeDate);
    const queryClose = windowBars[windowBars.length - 1].close;
    const invalidationBasis = entry.invalidationLevel ?? entry.watchLevel ?? queryClose;
    const invalidationRatio = invalidationBasis / Math.max(queryClose, 1);

    const candidates = await this.pgvector.searchSimilar({
      vector,
      topK: Math.max(topK * 5, 200),
      windowSize: 60,
      featureVersion: 'v1',
      excludeDateRange: { endDate, gapDays: 30 },
      dateFrom: addYears(endDate, -3),
      dateTo: endDate,
    });

    const matches = selectSameSymbolMatches(candidates as SimilarMatch[], params.symbol, 30, topK);
    const topMatch = matches[0];
    let similarityBreakdown: SimilarityBreakdown | null = null;

    if (topMatch) {
      const topMatchBars = (await this.prisma.dailyBar.findMany({
        where: {
          symbol: topMatch.symbol,
          tradeDate: { lte: new Date(topMatch.endDate) },
        },
        orderBy: { tradeDate: 'desc' },
        take: 60,
      }))
        .reverse()
        .map((bar) => ({
          tradeDate: formatDate(bar.tradeDate),
          open: toNumber(bar.open),
          high: toNumber(bar.high),
          low: toNumber(bar.low),
          close: toNumber(bar.close),
          volume: Number(bar.volume),
          amount: toNumber(bar.amount),
          pctChange: bar.pctChange == null ? null : toNumber(bar.pctChange),
        }));

      if (topMatchBars.length === 60) {
        similarityBreakdown = buildSimilarityBreakdown(
          windowBars,
          topMatchBars,
          topMatch.symbol,
          topMatch.endDate,
          topMatch.similarity
        );
      }
    }

    const matchMetrics = (await Promise.all(matches.map(async (match) => {
      const futureBars = await this.prisma.dailyBar.findMany({
        where: {
          symbol: match.symbol,
          tradeDate: { gt: new Date(match.endDate) },
        },
        orderBy: { tradeDate: 'asc' },
        take: 5,
      });

      const forwardMetric = buildForwardMetric(
        match.baseClose ?? 0,
        futureBars.map((bar) => ({
          close: toNumber(bar.close),
          high: toNumber(bar.high),
          low: toNumber(bar.low),
        })),
        (match.baseClose ?? 0) * invalidationRatio
      );

      return forwardMetric == null
        ? null
        : {
            match,
            metric: {
              similarity: match.similarity,
              ...forwardMetric,
            },
          };
    }))).filter((row): row is { match: SimilarMatch; metric: ForwardMetric } => row != null);

    const metrics = matchMetrics.map((row) => row.metric);

    const summary = summarizeForwardMetrics(metrics);
    const rating = buildRatingInsight({
      stageLabel: phase.stageLabel,
      mainlineConsistency,
      upProbability: summary.upProbability,
      avgMaxDrawdown: summary.avgMaxDrawdown,
      emotionTemp: emotion.temp,
      flowLabel: flow.label,
    });

    return {
      security: {
        symbol: params.symbol,
        name: security.name,
        tradeDate: endDate,
      },
      quote: {
        close: toNumber(latestBar.close),
        changePct: latestBar.pctChange == null ? 0 : toNumber(latestBar.pctChange),
      },
      rating: {
        label: rating.label,
        score: rating.score,
        stageTrend: phase.stageLabel,
        mainlineConsistency,
        reasons: rating.reasons,
      },
      entry,
      emotion,
      phase: {
        current: phase.current,
        nodes: phase.nodes,
        activeNode: phase.activeNode,
        trendBroken: phase.trendBroken,
        trendNote: phase.trendBroken ? '趋势转弱' : '趋势未破',
      },
      riskReward: {
        upProbability: summary.upProbability,
        avgMaxDrawdown: summary.avgMaxDrawdown,
        similarCount: summary.similarCount,
        sampleYears: 3,
        topK,
      },
      flow: {
        continuity: flow.label,
        signals: flow.signals,
        continuationProb3d: summary.continuationProb3d,
        quote: '趋势的延续来自量价配合。',
      },
      similarityBreakdown,
      similarSamples: matchMetrics.slice(0, 8).map(({ match, metric }) => ({
        segmentId: match.segmentId,
        symbol: match.symbol,
        endDate: match.endDate,
        similarity: round(match.similarity, 4),
        return5d: metric.return5d,
        maxDrawdown5d: Math.abs(metric.maxDrawdown5d),
      })),
    };
  }
}

function buildMainlineConsistencyProxy(
  phase: ReturnType<typeof buildPhaseInsight>,
  flow: ReturnType<typeof buildFlowInsight>,
  emotionTemp: number
): '高' | '中' | '低' | '--' {
  let score = 0;

  if (phase.stageLabel === '主升初段' || phase.stageLabel === '加速') {
    score += 2;
  } else if (phase.trendBroken) {
    score -= 2;
  }

  if (flow.label === '良好') {
    score += 1;
  } else if (flow.label === '偏弱') {
    score -= 1;
  }

  if (emotionTemp >= 45 && emotionTemp <= 78) {
    score += 1;
  } else if (emotionTemp >= 85) {
    score -= 1;
  }

  if (score >= 3) {
    return '高';
  }
  if (score >= 1) {
    return '中';
  }
  return '低';
}

async function computeFeatureVector(bars: DailyBarInput[]): Promise<number[]> {
  const response = await fetch(new URL('/compute/v1/feature', compute.url), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      close: bars.map((bar) => bar.close),
      volume: bars.map((bar) => bar.volume),
      high: bars.map((bar) => bar.high),
      low: bars.map((bar) => bar.low),
      feature_version: 'v1',
    }),
  });

  if (!response.ok) {
    throw new StockDetailError(`Compute 服务不可用 (${response.status})`, 502);
  }

  const data = await response.json() as { vector?: number[] };
  if (!data.vector || data.vector.length === 0) {
    throw new StockDetailError('Compute 未返回可用向量', 502);
  }

  return data.vector;
}

function toNumber(value: unknown): number {
  if (value == null) {
    return 0;
  }
  return Number(value);
}

function ensureWindow(bars: DailyBarInput[]): DailyBarInput[] {
  if (bars.length < 60) {
    throw new StockDetailError('相似度拆解至少需要 60 个交易日数据', 400);
  }
  return bars.slice(-60);
}

function buildSimilarityComponents(bars: DailyBarInput[]) {
  const close = bars.map((bar) => bar.close);
  const volume = bars.map((bar) => bar.volume);

  const priceShape = zscore(close);
  const returnRhythm = logReturns(close).map((value) => value * 0.5);
  const volumeProfile = zscore(volume).map((value) => value * 0.7);
  const statSignature = [
    skewness(returnRhythm.map((value) => value / 0.5)),
    kurtosis(returnRhythm.map((value) => value / 0.5)),
    maxDrawdown(close),
  ].map((value) => value * 1.5);

  const fullVector = normalize([
    ...priceShape,
    ...returnRhythm,
    ...volumeProfile,
    ...statSignature,
  ]);

  return {
    priceShape,
    returnRhythm,
    volumeProfile,
    statSignature,
    fullVector,
  };
}

function zscore(values: number[]): number[] {
  const mean = average(values);
  const std = Math.sqrt(average(values.map((value) => (value - mean) ** 2)));
  if (std < 1e-10) {
    return values.map(() => 0);
  }
  return values.map((value) => (value - mean) / std);
}

function logReturns(values: number[]): number[] {
  const returns: number[] = [];
  for (let index = 1; index < values.length; index += 1) {
    returns.push(Math.log(values[index] / values[index - 1]));
  }
  return returns;
}

function normalize(values: number[]): number[] {
  const norm = Math.sqrt(values.reduce((sum, value) => sum + value ** 2, 0));
  if (norm < 1e-10) {
    return values.map(() => 0);
  }
  return values.map((value) => value / norm);
}

function cosineSimilarity(left: number[], right: number[]): number {
  if (left.length !== right.length || left.length === 0) {
    return 0;
  }
  const leftNorm = Math.sqrt(left.reduce((sum, value) => sum + value ** 2, 0));
  const rightNorm = Math.sqrt(right.reduce((sum, value) => sum + value ** 2, 0));
  if (leftNorm < 1e-10 || rightNorm < 1e-10) {
    return 0;
  }
  const dot = left.reduce((sum, value, index) => sum + value * right[index], 0);
  return dot / (leftNorm * rightNorm);
}

function average(values: number[]): number {
  if (values.length === 0) {
    return 0;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function skewness(values: number[]): number {
  const mean = average(values);
  const centered = values.map((value) => value - mean);
  const variance = average(centered.map((value) => value ** 2));
  if (variance < 1e-12) {
    return 0;
  }
  return average(centered.map((value) => value ** 3)) / (variance ** 1.5);
}

function kurtosis(values: number[]): number {
  const mean = average(values);
  const centered = values.map((value) => value - mean);
  const variance = average(centered.map((value) => value ** 2));
  if (variance < 1e-12) {
    return 0;
  }
  return average(centered.map((value) => value ** 4)) / (variance ** 2) - 3;
}

function maxDrawdown(values: number[]): number {
  let peak = values[0];
  let drawdown = 0;
  values.forEach((value) => {
    peak = Math.max(peak, value);
    drawdown = Math.min(drawdown, value / peak - 1);
  });
  return drawdown;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function formatDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function addYears(dateText: string, years: number): string {
  const date = new Date(`${dateText}T00:00:00.000Z`);
  date.setUTCFullYear(date.getUTCFullYear() + years);
  return date.toISOString().slice(0, 10);
}

function dateDiffInDays(left: string, right: string): number {
  const leftDate = new Date(`${left}T00:00:00.000Z`);
  const rightDate = new Date(`${right}T00:00:00.000Z`);
  return Math.round((rightDate.getTime() - leftDate.getTime()) / (24 * 60 * 60 * 1000));
}

function clampInt(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, Math.round(value)));
}

function round(value: number, digits = 2): number {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}
