# 宁德时代单票初始化结果

日期: 2026-03-08
标的: `300750.SZ`
模式: 单票历史初始化
数据源: `AKShare`
价格口径: 未复权
HNSW 索引: 跳过
数据库: `postgresql://localhost:5433/insightmirror`

## 结果摘要
- `security_master`: 1 行
- `daily_bar`: 1876 行
- `daily_bar` 日期范围: `2018-06-11` 到 `2026-03-06`
- `segment_index`: 1817 行
- `segment_feature`: 1817 行
- `segment_future_label`:
  - `filled`: 1797
  - `na`: 20

## 最新 5 条日线
| trade_date | close | pct_change |
|---|---:|---:|
| 2026-03-06 | 354.7700 | 1.2900 |
| 2026-03-05 | 350.2500 | 3.3500 |
| 2026-03-04 | 338.9000 | -1.5000 |
| 2026-03-03 | 344.0700 | 1.1300 |
| 2026-03-02 | 340.2200 | -0.5200 |

## 明天可直接执行的检查 SQL
```sql
SELECT COUNT(*) FROM security_master WHERE symbol = '300750.SZ';

SELECT COUNT(*), MIN(trade_date), MAX(trade_date)
FROM daily_bar
WHERE symbol = '300750.SZ';

SELECT COUNT(*) FROM segment_index WHERE symbol = '300750.SZ';

SELECT COUNT(*)
FROM segment_feature sf
JOIN segment_index si ON si.id = sf.segment_id
WHERE si.symbol = '300750.SZ';

SELECT label_status, COUNT(*)
FROM segment_future_label sfl
JOIN segment_index si ON si.id = sfl.segment_id
WHERE si.symbol = '300750.SZ'
GROUP BY label_status
ORDER BY label_status;
```
