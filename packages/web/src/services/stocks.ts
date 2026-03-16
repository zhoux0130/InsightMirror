import api from './api';

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
  similarityBreakdown: {
    symbol: string;
    endDate: string;
    overallSimilarity: number;
    overallScore: number;
    windowSize: number;
    dimensions: Array<{
      key: 'price_shape' | 'return_rhythm' | 'volume_profile' | 'stat_signature';
      label: string;
      description: string;
      similarity: number;
      score: number;
    }>;
  } | null;
  similarSamples: Array<{
    segmentId: number;
    symbol: string;
    endDate: string;
    similarity: number;
    return5d: number;
    maxDrawdown5d: number;
  }>;
}

type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  error?: string;
};

export async function listStockOptions(market?: 'CN' | 'US'): Promise<StockOption[]> {
  const url = market ? `/stocks/options?market=${market}` : '/stocks/options';
  const response = await api.get<ApiEnvelope<StockOption[]>, ApiEnvelope<StockOption[]>>(url);
  return response.data;
}

export async function getStockDetail(
  symbol: string,
  params?: { endDate?: string; topK?: number }
): Promise<StockDetailResponse> {
  const search = new URLSearchParams();
  if (params?.endDate) {
    search.set('endDate', params.endDate);
  }
  if (params?.topK) {
    search.set('topK', String(params.topK));
  }

  const suffix = search.toString() ? `?${search.toString()}` : '';
  const response = await api.get<ApiEnvelope<StockDetailResponse>, ApiEnvelope<StockDetailResponse>>(
    `/stocks/${symbol}/detail${suffix}`
  );
  return response.data;
}
