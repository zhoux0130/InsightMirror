export interface DailyBarInput {
  tradeDate: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
  pctChange?: number | null;
}

export interface EntryInsight {
  mode: 'range' | 'wait';
  lower: number | null;
  upper: number | null;
  position: '区间下沿' | '区间中部' | '区间上沿' | '偏离区间' | '暂不参与';
  invalidationLevel: number | null;
  watchLevel: number | null;
  note: string;
}

export interface PhaseInsight {
  current: string;
  nodes: string[];
  activeNode: string;
  trendBroken: boolean;
  stageLabel: string;
}

export interface EmotionInsight {
  temp: number;
  status: string;
  warning: string | null;
}

export interface FlowInsight {
  label: '良好' | '一般' | '偏弱';
  score: number;
  signals: string[];
}

export interface RatingInput {
  stageLabel: string;
  mainlineConsistency: '高' | '中' | '低' | '--';
  upProbability: number;
  avgMaxDrawdown: number;
  emotionTemp: number;
  flowLabel: '良好' | '一般' | '偏弱';
}

export interface RatingInsight {
  label: '可参与' | '观察' | '规避';
  score: number;
  reasons: string[];
}

export function buildEntryInsight(bars: DailyBarInput[]): EntryInsight {
  const ordered = ensureBars(bars);
  const current = ordered[ordered.length - 1];
  const atr = computeAtr(ordered, 14);
  const ma20 = sma(ordered.slice(-20).map((bar) => bar.close));
  const recentLow = Math.min(...ordered.slice(-10).map((bar) => bar.low));
  const support = Math.max(recentLow, ma20 * 0.995);

  let lower = support - atr * 0.15;
  let upper = support + atr * 0.65;
  const minWidth = atr * 0.8;

  if (upper - lower < minWidth) {
    upper = lower + minWidth;
  }

  const invalidationLevel = support - atr * 0.55;
  const range = upper - lower || 1;
  const pos = (current.close - lower) / range;

  if (current.close < ma20) {
    return {
      mode: 'wait',
      lower: null,
      upper: null,
      position: '暂不参与',
      invalidationLevel: null,
      watchLevel: round(support),
      note: `当前价格跌破 MA20，先观察重回 ${round(support)} 附近后的确认机会`,
    };
  }

  let position: EntryInsight['position'] = '偏离区间';
  if (pos >= 0 && pos <= 0.33) {
    position = '区间下沿';
  } else if (pos > 0.33 && pos <= 0.66) {
    position = '区间中部';
  } else if (pos > 0.66 && pos <= 1.1) {
    position = '区间上沿';
  }

  return {
    mode: 'range',
    lower: round(lower),
    upper: round(upper),
    position,
    invalidationLevel: round(Math.min(invalidationLevel, lower - 0.01)),
    watchLevel: round(support),
    note: '跌破此位，结构逻辑失效',
  };
}

export function buildPhaseInsight(bars: DailyBarInput[]): PhaseInsight {
  const ordered = ensureBars(bars);
  const current = ordered[ordered.length - 1];
  const ma20 = sma(ordered.slice(-20).map((bar) => bar.close));
  const ma60 = sma(ordered.slice(-60).map((bar) => bar.close));
  const previousMa20 = sma(ordered.slice(-25, -5).map((bar) => bar.close));
  const ret20 = ordered.length > 20
    ? current.close / ordered[ordered.length - 21].close - 1
    : 0;
  const distanceToMa20 = current.close / ma20 - 1;
  const amountRatio = average(ordered.slice(-5).map((bar) => bar.amount))
    / Math.max(average(ordered.slice(-20).map((bar) => bar.amount)), 1);

  let stageLabel = '整理蓄势';
  let trendBroken = false;

  if (current.close < ma20 && ma20 < ma60) {
    stageLabel = '趋势转弱';
    trendBroken = true;
  } else if (current.close > ma20 && ma20 > ma60 && ret20 > 0.08) {
    if (distanceToMa20 > 0.11 && amountRatio < 1.05) {
      stageLabel = '尾段';
    } else if (distanceToMa20 > 0.09 && amountRatio > 1.15) {
      stageLabel = '加速';
    } else {
      stageLabel = '主升初段';
    }
  } else if (current.close > ma60 && ma20 >= previousMa20) {
    stageLabel = '启动';
  }

  return {
    current: stageLabel,
    nodes: ['启动', '主升', '加速', '尾段'],
    activeNode: phaseNode(stageLabel),
    trendBroken,
    stageLabel,
  };
}

export function buildEmotionInsight(bars: DailyBarInput[]): EmotionInsight {
  const ordered = ensureBars(bars);
  const current = ordered[ordered.length - 1];
  const ret5 = ordered.length > 5 ? current.close / ordered[ordered.length - 6].close - 1 : 0;
  const ret10 = ordered.length > 10 ? current.close / ordered[ordered.length - 11].close - 1 : 0;
  const ret20 = ordered.length > 20 ? current.close / ordered[ordered.length - 21].close - 1 : 0;
  const ma20 = sma(ordered.slice(-20).map((bar) => bar.close));
  const deviation = ma20 > 0 ? current.close / ma20 - 1 : 0;

  const amountSeries = ordered.slice(-120).map((bar) => bar.amount);
  const atrSeries = ordered.slice(-60).map((_, index, all) =>
    computeAtr(ordered.slice(-(all.length - index + 14)), 14)
  ).filter((value) => Number.isFinite(value));
  const currentAtr = computeAtr(ordered, 14);

  const momentumScore = clamp((ret5 * 0.2 + ret10 * 0.35 + ret20 * 0.45) / 0.1, 0, 1);
  const amountScore = percentileRank(amountSeries, current.amount);
  const deviationScore = clamp(deviation / 0.08, 0, 1);
  const atrScore = atrSeries.length > 0 ? percentileRank(atrSeries, currentAtr) : 0.5;

  const temp = Math.round(
    (momentumScore * 0.46 + amountScore * 0.24 + deviationScore * 0.2 + atrScore * 0.1) * 100
  );

  let status = '中性';
  let warning: string | null = null;
  if (temp >= 85) {
    status = '过热';
    warning = '历史高温阶段，3日内回撤概率提升';
  } else if (temp >= 70) {
    status = '偏热';
    warning = '情绪偏热，注意不要在脉冲位置追高';
  } else if (temp >= 55) {
    status = '健康偏强';
  } else if (temp < 35) {
    status = '偏冷';
  }

  return {
    temp,
    status,
    warning,
  };
}

export function buildFlowInsight(bars: DailyBarInput[]): FlowInsight {
  const ordered = ensureBars(bars);
  const recentAmounts = ordered.slice(-3).map((bar) => bar.amount);
  const amountSlope = linearSlope(recentAmounts);
  const obvSeries = buildObvSeries(ordered);
  const obvTrend = obvSeries[obvSeries.length - 1] - obvSeries[Math.max(0, obvSeries.length - 6)];
  const pullbackVolumeRatio = average(ordered.slice(-3).map((bar) => bar.volume))
    / Math.max(average(ordered.slice(-10, -3).map((bar) => bar.volume)), 1);

  let score = 45;
  const signals: string[] = [];

  if (amountSlope > 0) {
    score += 20;
    signals.push('近3日成交额改善');
  }

  if (obvTrend > 0) {
    score += 20;
    signals.push('量价承接保持正向');
  }

  if (pullbackVolumeRatio <= 1.05) {
    score += 15;
    signals.push('回踩缩量，抛压可控');
  }

  let label: FlowInsight['label'] = '偏弱';
  if (score >= 75) {
    label = '良好';
  } else if (score >= 58) {
    label = '一般';
  }

  return {
    label,
    score,
    signals: signals.length > 0 ? signals : ['量价配合一般'],
  };
}

export function buildRatingInsight(input: RatingInput): RatingInsight {
  const stageScoreMap: Record<string, number> = {
    启动: 74,
    主升初段: 86,
    加速: 68,
    尾段: 42,
    趋势转弱: 24,
    整理蓄势: 58,
  };
  const mainlineScoreMap = { 高: 84, 中: 68, 低: 48, '--': 60 };
  const flowScoreMap = { 良好: 80, 一般: 62, 偏弱: 42 };

  const riskScore = clamp(
    input.upProbability * 100 + (0.1 - Math.abs(input.avgMaxDrawdown)) * 200,
    20,
    92
  );
  const emotionScore = input.emotionTemp >= 85 ? 38 : input.emotionTemp >= 75 ? 56 : 74;
  const total = Math.round(
    stageScoreMap[input.stageLabel] * 0.32
      + mainlineScoreMap[input.mainlineConsistency] * 0.14
      + riskScore * 0.26
      + flowScoreMap[input.flowLabel] * 0.16
      + emotionScore * 0.12
  );

  let label: RatingInsight['label'] = '规避';
  if (total >= 75) {
    label = '可参与';
  } else if (total >= 60) {
    label = '观察';
  }

  const reasons = [
    input.stageLabel === '主升初段' ? '结构处于主升窗口' : `当前结构为${input.stageLabel}`,
    input.upProbability >= 0.6 ? '相似样本胜率占优' : '相似样本胜率一般',
    input.flowLabel === '良好' ? '量价延续性较好' : '量价延续性一般',
  ];

  if (input.emotionTemp >= 80) {
    reasons.push('情绪偏热，参与节奏要保守');
  }

  return {
    label,
    score: total,
    reasons,
  };
}

function ensureBars(bars: DailyBarInput[]): DailyBarInput[] {
  if (bars.length < 20) {
    throw new Error('At least 20 bars are required');
  }
  return [...bars].sort((left, right) => left.tradeDate.localeCompare(right.tradeDate));
}

function computeAtr(bars: DailyBarInput[], period: number): number {
  if (bars.length < 2) {
    return 0;
  }
  const subset = bars.slice(-Math.max(period + 1, 2));
  const trs = subset.slice(1).map((bar, index) => {
    const prevClose = subset[index].close;
    return Math.max(
      bar.high - bar.low,
      Math.abs(bar.high - prevClose),
      Math.abs(bar.low - prevClose)
    );
  });
  return average(trs);
}

function phaseNode(stageLabel: string): string {
  if (stageLabel === '主升初段') {
    return '主升';
  }
  if (stageLabel === '趋势转弱') {
    return '尾段';
  }
  return ['启动', '加速', '尾段'].includes(stageLabel) ? stageLabel : '主升';
}

function buildObvSeries(bars: DailyBarInput[]): number[] {
  const series: number[] = [];
  let total = 0;
  bars.forEach((bar, index) => {
    if (index === 0) {
      series.push(total);
      return;
    }
    const prevClose = bars[index - 1].close;
    if (bar.close > prevClose) {
      total += bar.volume;
    } else if (bar.close < prevClose) {
      total -= bar.volume;
    }
    series.push(total);
  });
  return series;
}

function percentileRank(values: number[], current: number): number {
  if (values.length === 0) {
    return 0.5;
  }
  const count = values.filter((value) => value <= current).length;
  return clamp(count / values.length, 0, 1);
}

function linearSlope(values: number[]): number {
  if (values.length < 2) {
    return 0;
  }
  const meanX = (values.length - 1) / 2;
  const meanY = average(values);
  let numerator = 0;
  let denominator = 0;
  values.forEach((value, index) => {
    numerator += (index - meanX) * (value - meanY);
    denominator += (index - meanX) ** 2;
  });
  return denominator === 0 ? 0 : numerator / denominator;
}

function sma(values: number[]): number {
  return average(values);
}

function average(values: number[]): number {
  if (values.length === 0) {
    return 0;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}
