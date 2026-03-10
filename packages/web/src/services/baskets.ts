import api from './api';

type ApiEnvelope<T> = { success: boolean; data: T; error?: string };

// ── Types ────────────────────────────────────────────────────────

export interface BasketSummary {
  id: string;
  name: string;
  description: string | null;
  capital: number;
  status: string;
  stockCount: number;
  openPositionCount: number;
  closedPositionCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface BasketStock {
  id: string;
  basketId: string;
  symbol: string;
  addedAt: string;
}

export interface BasketRule {
  id: string;
  basketId: string;
  name: string | null;
  conditionGroup: ConditionGroup;
  enabled: boolean;
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

export interface Position {
  id: string;
  basketId: string;
  symbol: string;
  buyDate: string;
  buyPrice: number;
  shares: number;
  sellDate: string | null;
  sellPrice: number | null;
  triggerType: string;
  ruleId: string | null;
  note: string | null;
}

export interface BasketDetail {
  id: string;
  name: string;
  description: string | null;
  capital: number;
  status: string;
  stocks: BasketStock[];
  rules: BasketRule[];
  positions: Position[];
  createdAt: string;
  updatedAt: string;
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

export interface BasketCompareItem {
  basketId: string;
  basketName: string;
  capital: number;
  totalPnl: number;
  totalPnlPercent: number;
  winRate: number;
  avgPnlPercent: number;
  maxDrawdown: number;
  openCount: number;
  closedCount: number;
  stockCount: number;
}

export interface ScanResult {
  symbol: string;
  ruleId: string;
  ruleName: string | null;
  triggered: boolean;
  details: Record<string, { value: number; passed: boolean }>;
}

// ── API Functions ────────────────────────────────────────────────

export async function listBaskets(): Promise<BasketSummary[]> {
  const res = await api.get<ApiEnvelope<BasketSummary[]>, ApiEnvelope<BasketSummary[]>>('/baskets');
  return res.data;
}

export async function getBasket(id: string): Promise<BasketDetail> {
  const res = await api.get<ApiEnvelope<BasketDetail>, ApiEnvelope<BasketDetail>>(`/baskets/${id}`);
  return res.data;
}

export async function createBasket(input: {
  name: string;
  description?: string;
  capital?: number;
}): Promise<BasketDetail> {
  const res = await api.post<ApiEnvelope<BasketDetail>, ApiEnvelope<BasketDetail>>('/baskets', input);
  return res.data;
}

export async function updateBasket(
  id: string,
  input: { name?: string; description?: string; capital?: number; status?: string }
): Promise<BasketDetail> {
  const res = await api.put<ApiEnvelope<BasketDetail>, ApiEnvelope<BasketDetail>>(`/baskets/${id}`, input);
  return res.data;
}

export async function deleteBasket(id: string): Promise<void> {
  await api.delete(`/baskets/${id}`);
}

// Stocks
export async function addStock(basketId: string, symbol: string): Promise<BasketStock> {
  const res = await api.post<ApiEnvelope<BasketStock>, ApiEnvelope<BasketStock>>(
    `/baskets/${basketId}/stocks`, { symbol }
  );
  return res.data;
}

export async function removeStock(basketId: string, symbol: string): Promise<void> {
  await api.delete(`/baskets/${basketId}/stocks/${symbol}`);
}

// Rules
export async function createRule(
  basketId: string,
  input: { name?: string; conditionGroup: ConditionGroup; enabled?: boolean }
): Promise<BasketRule> {
  const res = await api.post<ApiEnvelope<BasketRule>, ApiEnvelope<BasketRule>>(
    `/baskets/${basketId}/rules`, input
  );
  return res.data;
}

export async function updateRule(
  basketId: string,
  ruleId: string,
  input: { name?: string; conditionGroup?: ConditionGroup; enabled?: boolean }
): Promise<BasketRule> {
  const res = await api.put<ApiEnvelope<BasketRule>, ApiEnvelope<BasketRule>>(
    `/baskets/${basketId}/rules/${ruleId}`, input
  );
  return res.data;
}

export async function deleteRule(basketId: string, ruleId: string): Promise<void> {
  await api.delete(`/baskets/${basketId}/rules/${ruleId}`);
}

// Positions
export async function buyPosition(
  basketId: string,
  input: { symbol: string; buyDate: string; buyPrice?: number; shares?: number; note?: string }
): Promise<Position> {
  const res = await api.post<ApiEnvelope<Position>, ApiEnvelope<Position>>(
    `/baskets/${basketId}/positions`, input
  );
  return res.data;
}

export async function sellPosition(
  basketId: string,
  positionId: string,
  input: { sellDate: string; sellPrice?: number; note?: string }
): Promise<Position> {
  const res = await api.put<ApiEnvelope<Position>, ApiEnvelope<Position>>(
    `/baskets/${basketId}/positions/${positionId}/sell`, input
  );
  return res.data;
}

export async function listPositions(
  basketId: string,
  status?: 'open' | 'closed' | 'all'
): Promise<Position[]> {
  const suffix = status ? `?status=${status}` : '';
  const res = await api.get<ApiEnvelope<Position[]>, ApiEnvelope<Position[]>>(
    `/baskets/${basketId}/positions${suffix}`
  );
  return res.data;
}

// PnL
export async function getBasketPnl(basketId: string): Promise<BasketPnL> {
  const res = await api.get<ApiEnvelope<BasketPnL>, ApiEnvelope<BasketPnL>>(`/baskets/${basketId}/pnl`);
  return res.data;
}

export async function compareBaskets(): Promise<BasketCompareItem[]> {
  const res = await api.get<ApiEnvelope<BasketCompareItem[]>, ApiEnvelope<BasketCompareItem[]>>(
    '/baskets/compare'
  );
  return res.data;
}

// Scan
export async function scanRules(basketId: string): Promise<ScanResult[]> {
  const res = await api.post<ApiEnvelope<ScanResult[]>, ApiEnvelope<ScanResult[]>>(
    `/baskets/${basketId}/scan`
  );
  return res.data;
}
