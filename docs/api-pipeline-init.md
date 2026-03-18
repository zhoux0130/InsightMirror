# 股票数据初始化 API 文档

## 概述

提供 HTTP API 触发 CN（A 股）和 US（美股）的全量数据初始化，替代手动执行 CLI 脚本。初始化在后台异步执行，可通过 Pipeline 状态接口查询进度。

---

## 端点

### `POST /api/pipeline/init`

触发股票数据全量初始化。需要 JWT 认证。

> **Compute 服务直连**：`POST /compute/v1/pipeline/init`（内部服务间调用，无需认证）

### 请求头

| Header          | 值                        | 必填 |
|-----------------|---------------------------|------|
| `Content-Type`  | `application/json`        | 是   |
| `Authorization` | `Bearer <jwt_token>`      | 是   |

### 请求体

| 字段         | 类型       | 默认值     | 必填 | 说明                                                    |
|-------------|-----------|-----------|------|--------------------------------------------------------|
| `market`    | `string`  | `"CN"`    | 否   | 市场类型：`"CN"`（A 股）或 `"US"`（美股）                   |
| `symbols`   | `string[]` | `null`   | 条件 | 股票代码列表。US 市场**必填**；CN 市场可选（`null` = 全量 A 股）|
| `start_date`| `string`  | 按市场而定  | 否   | 起始日期 `YYYY-MM-DD`。CN 默认 `2016-01-01`，US 默认 `2020-01-01` |
| `end_date`  | `string`  | 今天       | 否   | 截止日期 `YYYY-MM-DD`                                    |
| `skip_hnsw` | `boolean` | `false`   | 否   | 是否跳过 HNSW 向量索引重建                                 |

### 响应

**200 OK** — 任务已接受

```json
{
  "success": true,
  "data": {
    "status": "accepted",
    "market": "US",
    "symbols": ["AAPL", "MSFT", "TSLA"],
    "start_date": "2020-01-01",
    "end_date": null,
    "skip_hnsw": false,
    "message": "US stock initialization started in background"
  }
}
```

**400 Bad Request** — 参数错误

```json
{
  "detail": "symbols is required for US market initialization"
}
```

**401 Unauthorized** — 未提供或无效的 JWT token

---

## 请求示例

### 1. 初始化美股（指定股票）

```bash
curl -X POST http://localhost:3000/api/pipeline/init \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -d '{
    "market": "US",
    "symbols": ["AAPL", "MSFT", "TSLA"],
    "start_date": "2020-01-01"
  }'
```

### 2. 初始化全量 A 股

```bash
curl -X POST http://localhost:3000/api/pipeline/init \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -d '{
    "market": "CN"
  }'
```

### 3. 初始化指定 A 股（跳过 HNSW）

```bash
curl -X POST http://localhost:3000/api/pipeline/init \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -d '{
    "market": "CN",
    "symbols": ["000001.SZ", "600519.SH"],
    "start_date": "2020-01-01",
    "skip_hnsw": true
  }'
```

### 4. 直接调用 Compute 服务（内部）

```bash
curl -X POST http://localhost:8000/compute/v1/pipeline/init \
  -H "Content-Type: application/json" \
  -d '{
    "market": "US",
    "symbols": ["AAPL"],
    "start_date": "2024-01-01",
    "skip_hnsw": true
  }'
```

---

## 查询初始化状态

### `GET /api/pipeline/status`

复用现有的 Pipeline 状态查询接口。初始化任务以 `step_name = "init"` 记录在 `pipeline_run_log` 表中。

```bash
curl http://localhost:3000/api/pipeline/status?run_date=2026-03-18
```

**响应示例**（初始化进行中）：

```json
{
  "success": true,
  "data": {
    "steps": [
      {
        "step_name": "init",
        "market": "US",
        "status": "running",
        "started_at": "2026-03-18T10:30:00",
        "finished_at": null,
        "records_processed": null,
        "error_message": null
      }
    ]
  }
}
```

**响应示例**（初始化完成）：

```json
{
  "success": true,
  "data": {
    "steps": [
      {
        "step_name": "init",
        "market": "US",
        "status": "success",
        "started_at": "2026-03-18T10:30:00",
        "finished_at": "2026-03-18T10:45:32",
        "records_processed": null,
        "error_message": null
      }
    ]
  }
}
```

**响应示例**（初始化失败）：

```json
{
  "success": true,
  "data": {
    "steps": [
      {
        "step_name": "init",
        "market": "US",
        "status": "failed",
        "started_at": "2026-03-18T10:30:00",
        "finished_at": "2026-03-18T10:31:05",
        "records_processed": null,
        "error_message": "Yahoo Finance API rate limit exceeded"
      }
    ]
  }
}
```

---

## 初始化流程

### CN 市场（A 股）

调用 `scripts.full_init.full_init()`，执行以下步骤：

| 步骤 | 说明 |
|------|------|
| 1. `ensure_pgvector_schema` | 确保 pgvector 扩展和表结构 |
| 2. `seed_feature_version_config` | 写入 v1 特征版本配置（182 维） |
| 3. `init_security_master` | 从 AKShare 拉取股票元数据 |
| 4. `fetch_full_history` | 下载历史行情数据 |
| 5. `load_daily_bars` | 加载日线数据到 `daily_bar` 表 |
| 6. `build_full_segments` | 构建 60 天滚动窗口分段 + 计算特征向量 |
| 7. `backfill_full_labels` | 回补未来收益标签（收益率、最大回撤、夏普比率等）|
| 8. `build_hnsw_index` | 重建 HNSW 向量索引（可通过 `skip_hnsw` 跳过）|

### US 市场（美股）

调用 `scripts.init_us_stocks.init_us_stocks()`，执行以下步骤：

| 步骤 | 说明 |
|------|------|
| 1. `init_us_security_master` | 从 Yahoo Finance 拉取股票元数据 |
| 2. `fetch_us_daily_bars` | 下载历史 OHLCV 数据 |
| 3. `build_full_segments` | 构建分段 + 计算 182 维特征向量 |
| 4. `backfill_full_labels` | 回补未来收益标签 |
| 5. `build_hnsw_index` | 重建 HNSW 向量索引（可通过 `skip_hnsw` 跳过）|

---

## 注意事项

- **耗时操作**：全量初始化可能需要数分钟到数小时（取决于股票数量和日期范围）
- **幂等性**：底层使用 `ON CONFLICT ... DO UPDATE`，重复调用不会产生脏数据
- **US 市场限流**：Yahoo Finance API 有速率限制，每个 symbol 间隔 0.5 秒
- **认证**：通过 Server 代理调用需要 JWT token（与 `/api/pipeline/trigger` 一致）
- **并发**：同一市场的多次初始化会在 `pipeline_run_log` 中覆盖同日状态记录
