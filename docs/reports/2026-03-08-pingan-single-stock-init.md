# 平安银行单票初始化结果

日期: 2026-03-08
标的: `000001.SZ`
模式: 单票历史初始化
数据源: `AKShare`，历史行情在 Eastmoney 失败时自动回退到 Sina
价格口径: 未复权
HNSW 索引: 跳过
数据库: `postgresql://localhost:5433/insightmirror`

## 结果摘要
- `security_master`: 1 行
- `daily_bar`: 2469 行
- `daily_bar` 日期范围: `2016-01-04` 到 `2026-03-06`
- `segment_index`: 2410 行
- `segment_feature`: 2410 行
- `segment_future_label`:
  - `filled`: 2390
  - `na`: 20

## 最新 5 条日线
| trade_date | close | pct_change |
|---|---:|---:|
| 2026-03-06 | 10.8200 | 0.0925 |
| 2026-03-05 | 10.8100 | 0.9337 |
| 2026-03-04 | 10.7100 | -1.5625 |
| 2026-03-03 | 10.8800 | 0.2765 |
| 2026-03-02 | 10.8500 | -0.4587 |
