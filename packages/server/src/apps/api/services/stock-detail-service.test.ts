import {
  buildForwardMetric,
  buildSimilarityBreakdown,
  dedupeMatches,
  selectSameSymbolMatches,
  summarizeForwardMetrics,
  type SimilarMatch,
} from './stock-detail-service';
import type { DailyBarInput } from './stock-detail-calculations';

function makeBars(length: number): DailyBarInput[] {
  return Array.from({ length }, (_, index) => {
    const close = 100 + index * 1.1 + Math.sin(index / 4) * 2;
    const volume = 100_000 + index * 1800 + (index % 5) * 3000;
    return {
      tradeDate: `2026-01-${String((index % 28) + 1).padStart(2, '0')}`,
      open: close - 0.8,
      high: close + 1.5,
      low: close - 1.2,
      close,
      volume,
      amount: close * volume,
      pctChange: index === 0 ? 0 : 1.2,
    };
  });
}

describe('stock detail service helpers', () => {
  test('dedupes overlapping windows from the same symbol', () => {
    const matches: SimilarMatch[] = [
      { segmentId: 1, symbol: '300750.SZ', startDate: '2025-11-01', endDate: '2025-12-30', similarity: 0.93 },
      { segmentId: 2, symbol: '300750.SZ', startDate: '2025-11-10', endDate: '2026-01-10', similarity: 0.9 },
      { segmentId: 3, symbol: '300750.SZ', startDate: '2026-01-15', endDate: '2026-03-01', similarity: 0.88 },
      { segmentId: 4, symbol: '000001.SZ', startDate: '2025-12-01', endDate: '2026-02-20', similarity: 0.87 },
    ];

    const result = dedupeMatches(matches, 30);

    expect(result.map((item) => item.segmentId)).toEqual([1, 3, 4]);
  });

  test('selects only same-symbol matches for stock detail', () => {
    const matches: SimilarMatch[] = [
      { segmentId: 1, symbol: '300750.SZ', startDate: '2025-11-01', endDate: '2025-12-30', similarity: 0.93 },
      { segmentId: 2, symbol: '000001.SZ', startDate: '2025-11-10', endDate: '2026-01-10', similarity: 0.95 },
      { segmentId: 3, symbol: '300750.SZ', startDate: '2026-01-15', endDate: '2026-03-01', similarity: 0.88 },
    ];

    const result = selectSameSymbolMatches(matches, '300750.SZ', 30, 10);

    expect(result.map((item: SimilarMatch) => item.segmentId)).toEqual([1, 3]);
    expect(result.every((item: SimilarMatch) => item.symbol === '300750.SZ')).toBe(true);
  });

  test('builds 3d and 5d forward metrics from future bars', () => {
    const result = buildForwardMetric(
      100,
      [
        { close: 103, high: 104, low: 99.5 },
        { close: 105, high: 106, low: 102 },
        { close: 107, high: 108, low: 103 },
        { close: 106, high: 109, low: 101 },
        { close: 109, high: 110, low: 105 },
      ],
      95
    );

    expect(result).not.toBeNull();
    expect(result!.return3d).toBeCloseTo(0.07, 4);
    expect(result!.return5d).toBeCloseTo(0.09, 4);
    expect(result!.maxDrawdown5d).toBeCloseTo(-0.005, 4);
    expect(result!.continuation3d).toBe(true);
  });

  test('summarizes forward metrics into risk reward stats', () => {
    const result = summarizeForwardMetrics([
      { similarity: 0.91, return3d: 0.03, return5d: 0.08, maxDrawdown5d: -0.02, continuation3d: true },
      { similarity: 0.87, return3d: -0.01, return5d: -0.02, maxDrawdown5d: -0.05, continuation3d: false },
      { similarity: 0.84, return3d: 0.02, return5d: 0.06, maxDrawdown5d: -0.03, continuation3d: true },
    ]);

    expect(result.similarCount).toBe(3);
    expect(result.upProbability).toBeCloseTo(2 / 3, 4);
    expect(result.avgMaxDrawdown).toBeCloseTo(0.0333, 3);
    expect(result.continuationProb3d).toBeCloseTo(2 / 3, 4);
  });

  test('builds four similarity subscores for identical windows', () => {
    const bars = makeBars(60);

    const result = buildSimilarityBreakdown(bars, bars, '300750.SZ', '2026-03-06');

    expect(result.overallScore).toBeCloseTo(100, 3);
    expect(result.dimensions).toHaveLength(4);
    expect(result.dimensions.every((item) => item.score >= 99)).toBe(true);
  });

  test('penalizes the volume dimension when price path is unchanged but amount profile diverges', () => {
    const queryBars = makeBars(60);
    const reversedVolume = [...queryBars].reverse().map((bar) => bar.volume);
    const compareBars = queryBars.map((bar, index) => ({
      ...bar,
      volume: reversedVolume[index],
      amount: reversedVolume[index] * bar.close,
    }));

    const result = buildSimilarityBreakdown(queryBars, compareBars, '300750.SZ', '2023-11-23');
    const priceShape = result.dimensions.find((item) => item.key === 'price_shape');
    const volumeProfile = result.dimensions.find((item) => item.key === 'volume_profile');

    expect(priceShape?.score).toBeGreaterThan(95);
    expect(volumeProfile?.score).toBeLessThan(40);
  });
});
