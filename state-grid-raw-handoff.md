# State Grid Raw Crawler Handoff

## Scope

当前实现只覆盖 **国网招投标 raw 采集**：

| 范围 | 状态 |
|---|---|
| 组织树抓取 | 已实现 |
| 公告列表抓取 | 已实现，当前主目标为“采购公告” |
| 详情抓取 | 已实现基础链路 |
| 文件元数据 / 原文抓取 | 已实现基础链路 |
| DB raw 入库 | 已实现 |
| OSS 落盘 | 已实现 |
| 本地镜像落盘 | 已实现 |
| sourceRunId / suspect 标记 | 已补 schema 与部分落库逻辑 |
| 结构化解析 | 未实现 |
| 业务表出数 | 未实现 |

## Real Endpoints

基础前缀：

| 项 | 值 |
|---|---|
| Base URL | `https://ecp.sgcc.com.cn/ecp2.0/ecpwcmcore//index` |

接口清单：

| 能力 | 方法 | 路径 | 请求说明 |
|---|---|---|---|
| 组织树 | POST | `/orgTreeNew` | body: `{"orgId": null}` |
| 公告列表 | POST | `/noteList` | body JSON，当前使用采购公告菜单 |
| 招标详情 | POST | `/getNoticeBid` | body 直接是字符串 noticeId |
| 变更详情 | POST | `/getChangeBid` | body 直接是字符串 noticeId |
| 结果详情 | POST | `/getNoticeWin` | body 直接是字符串 noticeId |
| 招标附件下载 | GET | `/downLoadBid` | query: `noticeId`, `noticeDetId` |
| 结果文件索引 | POST | `/getWinFile` | body 直接是字符串 noticeId |
| PDF 原文 | GET | `/showPDF` | query: `filePath` |

## Current Menu IDs

| 类型 | firstPageMenuId |
|---|---|
| 招标公告 | `2018032700291334` |
| 采购公告 | `2018032900295987` |
| 结果公告 | `2018060501171111` |

当前代码默认跑：

| 类型 | firstPageMenuId |
|---|---|
| 采购公告 | `2018032900295987` |

## Real Response Structure

### noteList

**关键点：公告内容列表在 `resultValue.noteList`。**

| 路径 | 含义 |
|---|---|
| `resultValue.count` | 总条数 |
| `resultValue.noteList` | 公告内容列表 |
| `resultValue.orglist.items` | 组织列表 |
| `resultValue.purTypes.items` | 采购类型字典 |

### orgTreeNew

**不要复用 noteList 解析逻辑。** 组织节点在 `resultValue` 相关结构里，字段常见为：

| 字段 | 说明 |
|---|---|
| `ID` / `CODE` | 组织 ID |
| `NAME` | 组织名 |
| `PID` | 父节点 |

## Current File Layout

| 模块 | 路径 | 作用 |
|---|---|---|
| 配置 | `packages/compute/app/config.py` | DB / 国网 / OSS 配置 |
| HTTP 基础层 | `packages/compute/app/crawlers/state_grid/base.py` | httpx + retry |
| HTTP 客户端 | `packages/compute/app/crawlers/state_grid/client.py` | 国网接口封装 |
| OSS / 本地镜像 | `packages/compute/app/crawlers/state_grid/blob_store.py` | 双写 raw |
| Repository | `packages/compute/app/crawlers/state_grid/repository.py` | text() SQL |
| Orchestrator | `packages/compute/app/crawlers/state_grid/orchestrator.py` | 全量 / 增量 / detail / file 编排 |
| CLI | `packages/compute/scripts/fetch_state_grid_raw.py` | 命令入口 |
| Scheduler | `packages/compute/app/scheduler.py` | 定时任务 |
| Prisma schema | `packages/server/prisma/schema.prisma` | DB 结构 |

## Storage Design

### DB Tables

| Prisma Model | DB Table |
|---|---|
| `StateGridCrawlerWatermark` | `state_grid_crawler_watermarks` |
| `StateGridCrawlTask` | `state_grid_crawl_tasks` |
| `StateGridNoticeRaw` | `state_grid_notice_raws` |
| `StateGridNoticeDetail` | `state_grid_notice_details` |
| `StateGridNoticeFile` | `state_grid_notice_files` |

### Primary Keys

| 表 | 主键 |
|---|---|
| 全部 state-grid raw 表 | `String @id @default(uuid())` |

### Unique Keys

| 表 | 唯一键 |
|---|---|
| watermark | `(source, scopeType, scopeKey)` |
| task | `(source, taskType, bizKey)` |
| notice raw | `(source, noticeId)` |
| detail | `(source, noticeId, detailApi)` |
| file | `(source, noticeId, sourceApi, sourceFileId)` |

## sourceRunId / suspect Design

### Purpose

| 字段 | 用途 |
|---|---|
| `sourceRunId` | 标记同一次抓取运行 |
| `isSuspect` | 标记该条 raw 可疑 |
| `suspectReason` | 记录可疑原因 |

### Current Schema

已补字段：

| 表 | 字段 |
|---|---|
| `state_grid_crawl_tasks` | `source_run_id` |
| `state_grid_notice_raws` | `source_run_id`, `is_suspect`, `suspect_reason` |
| `state_grid_notice_details` | `source_run_id`, `is_suspect`, `suspect_reason` |
| `state_grid_notice_files` | `source_run_id` |

### Current Code Status

| 项 | 状态 |
|---|---|
| orchestrator 生成 `source_run_id` | 已完成 |
| task payload 带 `sourceRunId` | 已完成 |
| task SQL 持久化 `source_run_id` | 已完成 |
| notice raw/detail/file SQL 持久化 `source_run_id` | 未完成 |
| suspect 标记写库 | 未完成 |

## OSS and Local Mirror

### OSS Prefix

| 项 | 值 |
|---|---|
| Bucket | `upivot-static` |
| Prefix | `state-grid/raw` |

### Key Rules

| 类型 | 模板 |
|---|---|
| 列表 JSON | `state-grid/raw/list/{api}/{yyyy}/{mm}/{dd}/{taskId}-{page}.json` |
| 详情 JSON | `state-grid/raw/detail/{noticeId}/{api}-{timestamp}.json` |
| HTML | `state-grid/raw/file/{noticeId}/render/{api}-{timestamp}.html` |
| 原始文件 | `state-grid/raw/file/{noticeId}/{sha256-prefix}/{sha256}/{originalName}` |

### Local Mirror

| 根目录 |
|---|
| `packages/compute/data/raw/state_grid/mirror/` |

OSS 与本地镜像保持同样相对路径。

## Current Flow

### Full Pipeline

| 步骤 | 行为 |
|---|---|
| 1 | `sync_org_tree()` |
| 2 | `fetch_notices_full()` |
| 3 | `fetch_details_for_raws()` |
| 4 | `fetch_files_for_raws()` |

### Incremental Pipeline

| 步骤 | 行为 |
|---|---|
| 1 | `sync_org_tree()` |
| 2 | `fetch_notices_full(..., limit_pages=1)` |
| 3 | `fetch_details_for_raws()` |
| 4 | `fetch_files_for_raws()` |

## Important Current Gaps

| 优先级 | 问题 | 说明 |
|---|---|---|
| P0 | `sync_org_tree()` 还复用 `_extract_items()` | 应改成专用 `_extract_orgs()` |
| P0 | `sourceRunId` 未完整写入 raw/detail/file | repository 还要补 SQL |
| P0 | suspect 标记未真正落库 | 还未在 repository/orchestrator 使用 |
| P0 | detail / file 的真实结构还未完全吃透 | 需要继续基于本地镜像调试 |
| P1 | 分页目前假设 page size 为 20 | 应从请求参数或返回结构统一控制 |
| P1 | 文件候选提取较通用 | 要按真实 detail / getWinFile 结构重写 |

## Recommended suspect Rules

| 场景 | isSuspect | suspectReason |
|---|---|---|
| `count > 0` 但 `noteList` 为空 | true | `note_list_empty_with_positive_count` |
| 返回结构缺少 `resultValue` | true | `missing_result_value` |
| 公告项缺少 `noticeId` | true | `missing_notice_id` |
| detail 200 但核心内容为空 | true | `empty_detail_payload` |
| 文件接口 200 但无有效文件内容 | true | `empty_file_payload` |

## Recommended Next Steps

| 优先级 | 任务 |
|---|---|
| P0 | 补 repository：`upsert_notice_raw/detail/file` 增加 `source_run_id` / suspect 参数 |
| P0 | 拆出 `_extract_orgs()`，不要再复用 `_extract_items()` |
| P0 | 对列表异常场景写入 `is_suspect=true` |
| P0 | 跑一轮采购公告全量小样本，确认 DB 真正入库 |
| P1 | 加按 `sourceRunId` 查询与重放能力 |
| P1 | 扩展到招标公告、结果公告三类菜单 |
| P1 | 针对 `getWinFile` 的 `files[].FILE_PATH` 重写文件补抓逻辑 |

## Commands

| 用途 | 命令 |
|---|---|
| 全量 | `cd packages/compute && .venv/bin/python -m scripts.fetch_state_grid_raw --mode full --limit-pages 1` |
| 增量 | `cd packages/compute && .venv/bin/python -m scripts.fetch_state_grid_raw --mode incremental` |
| 单公告 | `cd packages/compute && .venv/bin/python -m scripts.fetch_state_grid_raw --notice-id <ID>` |
| 单公告带文件 | `cd packages/compute && .venv/bin/python -m scripts.fetch_state_grid_raw --notice-id <ID> --with-files` |
| 死信重放 | `cd packages/compute && .venv/bin/python -m scripts.fetch_state_grid_raw --replay-dead --task-type file` |

## Notes for Future AI

| 事项 | 约束 |
|---|---|
| 不要把 `orgTreeNew` 当公告列表 | 必须单独解析 |
| `noteList` 只按 `resultValue.noteList` 取项目列表 | 不要回退到通用解析污染逻辑 |
| 错误 raw 不删除 | 用 `sourceRunId + isSuspect` 隔离 |
| 保留 OSS + 本地双写 | 方便后续调试结构 |
| repository 继续用 `text()` SQL | 当前代码风格已固定 |
