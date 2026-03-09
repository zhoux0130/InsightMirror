import {
  buildEntryInsight,
  buildEmotionInsight,
  buildFlowInsight,
  buildPhaseInsight,
  buildRatingInsight,
  type DailyBarInput,
} from './stock-detail-calculations';

function makeBars(length: number, overrides?: Partial<DailyBarInput>): DailyBarInput[] {
  return Array.from({ length }, (_, index) => {
    const close = 100 + index * 1.2;
    const open = close - 0.6;
    const high = close + 1.4;
    const low = close - 1.1;
    const amount = 1_000_000 + index * 50_000;
    const volume = 100_000 + index * 2_000;

    return {
      tradeDate: `2026-01-${String(index + 1).padStart(2, '0')}`,
      open,
      high,
      low,
      close,
      volume,
      amount,
      pctChange: index === 0 ? 0 : (1.2 / (close - 1.2)) * 100,
      ...overrides,
    };
  });
}

describe('stock-detail calculations', () => {
  test('builds an entry zone around support and classifies current price position', () => {
    const bars = makeBars(60);

    const result = buildEntryInsight(bars);

    expect(result.mode).toBe('range');
    expect(result.lower).not.toBeNull();
    expect(result.upper).not.toBeNull();
    expect(result.invalidationLevel).not.toBeNull();
    expect(result.lower!).toBeLessThan(result.upper!);
    expect(result.invalidationLevel!).toBeLessThan(result.lower!);
    expect(['区间下沿', '区间中部', '区间上沿', '偏离区间']).toContain(result.position);
  });

  test('returns wait mode when price is below ma20 and structure is not ready for participation', () => {
    const bars = makeBars(60).map((bar, index, all) => {
      if (index < all.length - 8) {
        return bar;
      }

      const cut = (index - (all.length - 8) + 1) * 4.2;
      return {
        ...bar,
        close: bar.close - cut,
        open: bar.open - cut,
        high: bar.high - cut,
        low: bar.low - cut,
      };
    });

    const result = buildEntryInsight(bars);

    expect(result.mode).toBe('wait');
    expect(result.lower).toBeNull();
    expect(result.upper).toBeNull();
    expect(result.invalidationLevel).toBeNull();
    expect(result.position).toBe('暂不参与');
    expect(result.watchLevel).not.toBeNull();
    expect(result.note).toContain('重回');
  });

  test('classifies a healthy uptrend as a main rising phase', () => {
    const bars = makeBars(60);

    const result = buildPhaseInsight(bars);

    expect(result.current).toBe('主升初段');
    expect(result.trendBroken).toBe(false);
    expect(result.stageLabel).toBe('主升初段');
  });

  test('raises emotion temperature when momentum and amount are stretched', () => {
    const bars = makeBars(250).map((bar, index, all) => {
      if (index < all.length - 20) {
        return bar;
      }

      return {
        ...bar,
        close: bar.close + 30 + index,
        high: bar.high + 32 + index,
        low: bar.low + 28 + index,
        amount: bar.amount * 2.8,
      };
    });

    const result = buildEmotionInsight(bars);

    expect(result.temp).toBeGreaterThanOrEqual(70);
    expect(['健康偏强', '偏热', '过热']).toContain(result.status);
  });

  test('grades flow continuity from amount trend and obv trend', () => {
    const bars = makeBars(60).map((bar, index, all) => ({
      ...bar,
      close: bar.close + (index % 3 === 0 ? 0.8 : 1.2),
      amount: index >= all.length - 3 ? bar.amount * 1.5 : bar.amount,
    }));

    const result = buildFlowInsight(bars);

    expect(['良好', '一般', '偏弱']).toContain(result.label);
    expect(result.signals.length).toBeGreaterThan(0);
  });

  test('maps component scores into a user-facing rating label', () => {
    const result = buildRatingInsight({
      stageLabel: '主升初段',
      mainlineConsistency: '中',
      upProbability: 0.64,
      avgMaxDrawdown: 0.062,
      emotionTemp: 72,
      flowLabel: '良好',
    });

    expect(result.label).toBe('可参与');
    expect(result.score).toBeGreaterThanOrEqual(75);
    expect(result.reasons.length).toBeGreaterThan(0);
  });
});
