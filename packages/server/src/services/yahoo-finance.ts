/**
 * Yahoo Finance API 客户端
 *
 * 使用 Yahoo Finance v8 公开 API 获取美股行情数据。
 * 无需 API Key，直接 HTTP 请求。
 */

const BASE_URL = 'https://query1.finance.yahoo.com';

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
};

// ---------- 类型定义 ----------

export interface YahooQuote {
  symbol: string;
  shortName: string;
  longName?: string;
  exchange: string;
  currency: string;
  regularMarketPrice: number;
  regularMarketChange: number;
  regularMarketChangePercent: number;
  regularMarketVolume: number;
  regularMarketTime: number;
}

export interface YahooDailyBar {
  date: string;       // YYYY-MM-DD
  open: number;
  high: number;
  low: number;
  close: number;
  adjClose: number;
  volume: number;
}

export interface YahooSearchResult {
  symbol: string;
  shortname: string;
  longname?: string;
  exchange: string;
  quoteType: string;
}

// ---------- 错误处理 ----------

export class YahooFinanceError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number = 500,
  ) {
    super(message);
    this.name = 'YahooFinanceError';
  }
}

// ---------- API 方法 ----------

/**
 * 获取实时行情报价
 */
export async function getQuote(symbol: string): Promise<YahooQuote> {
  const url = `${BASE_URL}/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=1d`;
  const response = await fetchWithRetry(url);
  const json = await response.json() as any;

  const result = json?.chart?.result?.[0];
  if (!result) {
    throw new YahooFinanceError(`未找到 ${symbol} 的行情数据`, 404);
  }

  const meta = result.meta;
  return {
    symbol: meta.symbol,
    shortName: meta.shortName ?? meta.symbol,
    longName: meta.longName,
    exchange: meta.exchangeName,
    currency: meta.currency,
    regularMarketPrice: meta.regularMarketPrice,
    regularMarketChange: meta.regularMarketPrice - meta.chartPreviousClose,
    regularMarketChangePercent:
      ((meta.regularMarketPrice - meta.chartPreviousClose) / meta.chartPreviousClose) * 100,
    regularMarketVolume: meta.regularMarketVolume ?? 0,
    regularMarketTime: meta.regularMarketTime,
  };
}

/**
 * 获取历史日K数据
 *
 * @param symbol - 美股代码，如 AAPL、TSLA
 * @param startDate - 起始日期 YYYY-MM-DD
 * @param endDate - 结束日期 YYYY-MM-DD（默认今天）
 */
export async function getDailyBars(
  symbol: string,
  startDate: string,
  endDate?: string,
): Promise<YahooDailyBar[]> {
  const period1 = Math.floor(new Date(`${startDate}T00:00:00Z`).getTime() / 1000);
  const period2 = endDate
    ? Math.floor(new Date(`${endDate}T23:59:59Z`).getTime() / 1000)
    : Math.floor(Date.now() / 1000);

  const url =
    `${BASE_URL}/v8/finance/chart/${encodeURIComponent(symbol)}` +
    `?period1=${period1}&period2=${period2}&interval=1d&events=history`;

  const response = await fetchWithRetry(url);
  const json = await response.json() as any;

  const result = json?.chart?.result?.[0];
  if (!result) {
    throw new YahooFinanceError(`未找到 ${symbol} 的历史数据`, 404);
  }

  const timestamps: number[] = result.timestamp ?? [];
  const quotes = result.indicators?.quote?.[0] ?? {};
  const adjClose = result.indicators?.adjclose?.[0]?.adjclose ?? [];

  const bars: YahooDailyBar[] = [];
  for (let i = 0; i < timestamps.length; i++) {
    const open = quotes.open?.[i];
    const high = quotes.high?.[i];
    const low = quotes.low?.[i];
    const close = quotes.close?.[i];
    const volume = quotes.volume?.[i];

    // 跳过无效数据点（节假日/停牌等）
    if (open == null || high == null || low == null || close == null) {
      continue;
    }

    bars.push({
      date: timestampToDate(timestamps[i]),
      open: round4(open),
      high: round4(high),
      low: round4(low),
      close: round4(close),
      adjClose: round4(adjClose[i] ?? close),
      volume: volume ?? 0,
    });
  }

  return bars;
}

/**
 * 搜索美股股票
 */
export async function searchStocks(query: string, limit = 10): Promise<YahooSearchResult[]> {
  const url =
    `${BASE_URL}/v1/finance/search?q=${encodeURIComponent(query)}` +
    `&quotesCount=${limit}&newsCount=0&enableFuzzyQuery=false&quotesQueryId=tss_match_phrase_query`;

  const response = await fetchWithRetry(url);
  const json = await response.json() as any;

  const quotes: any[] = json?.quotes ?? [];
  return quotes
    .filter((q: any) => q.quoteType === 'EQUITY')
    .map((q: any) => ({
      symbol: q.symbol,
      shortname: q.shortname ?? q.symbol,
      longname: q.longname,
      exchange: q.exchange,
      quoteType: q.quoteType,
    }));
}

/**
 * 将 Yahoo 日K数据转换为 DailyBar 入库格式
 */
export function toDailyBarRecords(
  symbol: string,
  bars: YahooDailyBar[],
): Array<{
  symbol: string;
  tradeDate: Date;
  market: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: bigint;
  amount: null;
  turnover: null;
  pctChange: number | null;
}> {
  return bars.map((bar, index) => {
    const prevClose = index > 0 ? bars[index - 1].close : null;
    const pctChange = prevClose ? round4((bar.close - prevClose) / prevClose) : null;

    return {
      symbol,
      tradeDate: new Date(`${bar.date}T00:00:00.000Z`),
      market: 'US',
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      volume: BigInt(bar.volume),
      amount: null,
      turnover: null,
      pctChange,
    };
  });
}

// ---------- 内部工具 ----------

async function fetchWithRetry(url: string, retries = 2): Promise<Response> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, { headers: HEADERS });

      if (response.status === 429) {
        // Rate limited — 等待后重试
        const waitMs = 1000 * (attempt + 1);
        await new Promise((resolve) => setTimeout(resolve, waitMs));
        continue;
      }

      if (!response.ok) {
        throw new YahooFinanceError(
          `Yahoo Finance API 错误: ${response.status} ${response.statusText}`,
          response.status >= 500 ? 502 : response.status,
        );
      }

      return response;
    } catch (error: any) {
      lastError = error;
      if (error instanceof YahooFinanceError) {
        throw error;
      }
      if (attempt < retries) {
        await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
      }
    }
  }

  throw new YahooFinanceError(
    `Yahoo Finance API 请求失败: ${lastError?.message ?? 'Unknown'}`,
    502,
  );
}

function timestampToDate(ts: number): string {
  return new Date(ts * 1000).toISOString().slice(0, 10);
}

function round4(value: number): number {
  return Math.round(value * 10000) / 10000;
}
