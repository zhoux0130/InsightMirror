# State Grid Raw Crawler 状态流转详细设计

## 1. 目标

本文只描述 **国网招投标 raw 采集链路的状态流转**，用于后续 AI 或人工接手维护。范围仅限：

| 范围 | 是否包含 |
|---|---|
| 列表抓取 | 是 |
| 详情抓取 | 是 |
| 文件下载 | 是 |
| DB raw 入库 | 是 |
| OSS / 本地镜像落盘 | 是 |
| sourceRunId / suspect | 是 |
| 结构化解析 | 否 |
| 业务出数 | 否 |

## 2. 核心对象

| 对象 | 表 | 用途 |
|---|---|---|
| Watermark | `state_grid_crawler_watermarks` | 增量游标 / scope 状态 |
| Task | `state_grid_crawl_tasks` | 任务状态、重试、死信 |
| NoticeRaw | `state_grid_notice_raws` | 列表层公告原始项 |
| NoticeDetail | `state_grid_notice_details` | 详情层 raw JSON / HTML |
| NoticeFile | `state_grid_notice_files` | 文件元信息、下载状态 |

## 3. 主流程状态机

### 3.1 NoticeRaw.status

| 状态 | 含义 | 进入条件 | 下一步 |
|---|---|---|---|
| `discovered` | 刚发现公告 | 预留状态，当前较少直接使用 | `detail_pending` |
| `detail_pending` | 等待抓详情 | 列表 upsert 成功 | `detail_done` / `failed` |
| `detail_done` | 详情已抓成功 | 至少一个详情接口成功 | `file_pending` / `file_done` / `partial` |
| `file_pending` | 等待文件抓取 | 预留状态，可用于后续显式推进 | `file_done` / `partial` |
| `file_done` | 文件阶段完成 | 所有需要抓的文件已成功，或明确无文件 | 终态 |
| `partial` | 只完成了一部分 | 文件部分失败，或后续需要补抓 | `detail_done` / `file_done` |
| `failed` | 当前阶段失败 | 详情阶段完全失败 | 重放 / 人工修复 |

### 3.2 NoticeDetail.fetchStatus

| 状态 | 含义 | 进入条件 |
|---|---|---|
| `pending` | 未抓取 / 预留 | 默认值 |
| `succeeded` | 详情抓取成功 | 接口返回成功并落库 |
| `failed` | 详情抓取失败 | 接口报错、结构异常、空内容等 |

### 3.3 NoticeFile.status

| 状态 | 含义 | 进入条件 |
|---|---|---|
| `pending` | 未下载 | 默认值 |
| `uploading` | 已进入下载 / 上传过程 | 创建文件记录后 |
| `succeeded` | 文件下载并落 OSS 成功 | 文件二进制拿到并上传成功 |
| `failed` | 文件失败 | 下载失败、上传失败、内容异常 |

### 3.4 CrawlTask.status

| 状态 | 含义 | 进入条件 |
|---|---|---|
| `pending` | 预留待执行 | 默认值 |
| `running` | 当前正在执行 | 任务开始 |
| `succeeded` | 成功结束 | 当前任务完成 |
| `failed` | 本次失败但仍可重试 | `attempt_count < max_attempts` |
| `dead` | 超过最大重试次数 | `attempt_count >= max_attempts` |

## 4. 当前主干流程

### 4.1 列表阶段

当前主干已改成 **不依赖 orgTree**，直接跑采购公告主列表：

| 项 | 当前行为 |
|---|---|
| 菜单 | `firstPageMenuId=2018032900295987` |
| org 参数 | 先固定 `orgId=""` |
| 分页来源 | `index` + `size` |
| 列表提取 | 只认 `resultValue.noteList` |
| 总数判断 | `resultValue.count` |

流程：

| 步骤 | 动作 | 结果 |
|---|---|---|
| 1 | 创建 `list` task | `state_grid_crawl_tasks.status=running` |
| 2 | 调 `noteList` | 获取一页采购公告 |
| 3 | 落 OSS / 本地镜像 | 存列表 raw 快照 |
| 4 | 遍历 `resultValue.noteList` | 每条公告执行 upsert |
| 5 | 写 `NoticeRaw` | `status=detail_pending` |
| 6 | 更新 `Watermark` | 记录页游标 |
| 7 | 标记 task 成功 | `status=succeeded` |

### 4.2 详情阶段

| 项 | 当前行为 |
|---|---|
| 候选集合 | `NoticeRaw.status in ('discovered','detail_pending','partial')` |
| 详情接口 | `getNoticeBid` / `getChangeBid` / `getNoticeWin` |
| 路由规则 | 先按 `noticeType` 粗分，否则回退多接口尝试 |

流程：

| 步骤 | 动作 | 结果 |
|---|---|---|
| 1 | 取待抓详情公告 | 从 `state_grid_notice_raws` 查 |
| 2 | 创建 `detail` task | `running` |
| 3 | 调详情接口 | 获取 JSON / HTML |
| 4 | 落 OSS / 本地镜像 | 存 detail raw / html raw |
| 5 | 写 `NoticeDetail` | `fetchStatus=succeeded/failed` |
| 6 | 更新 `NoticeRaw.status` | `detail_done` 或 `failed` |
| 7 | 标记 task 状态 | `succeeded/failed/dead` |

### 4.3 文件阶段

| 项 | 当前行为 |
|---|---|
| 候选集合 | `NoticeRaw.status in ('detail_done','file_pending')` |
| 默认下载策略 | 对采购/招标公告可默认尝试 `downLoadBid` |
| 结果公告策略 | 先 `getWinFile`，再 `showPDF` |

流程：

| 步骤 | 动作 | 结果 |
|---|---|---|
| 1 | 取待抓文件公告 | 从 `state_grid_notice_raws` 查 |
| 2 | 提取 file candidates | 来自详情 / 默认候选 |
| 3 | 创建 `file` task | `running` |
| 4 | 下载原文 | `downLoadBid` / `getWinFile` / `showPDF` |
| 5 | 落 OSS / 本地镜像 | 保存原始文件 |
| 6 | 写 / 更新 `NoticeFile` | `uploading -> succeeded/failed` |
| 7 | 更新 `NoticeRaw.status` | `file_done` / `partial` / 保持 `detail_done` |
| 8 | 标记 task 状态 | `succeeded/failed/dead` |

## 5. 关键状态推进规则

### 5.1 列表 -> 详情

| 条件 | 结果 |
|---|---|
| 列表 item 成功解析出 `noticeId` | `NoticeRaw.status = detail_pending` |
| 列表返回有 count 但无项目项 | `is_suspect=true`，原因 `note_list_empty_with_positive_count` |
| item 缺 `noticeId` | 不入 raw，建议后续补 suspect 批次记录 |

### 5.2 详情 -> 文件

| 条件 | 结果 |
|---|---|
| 至少一个详情接口成功 | `NoticeRaw.status = detail_done` |
| 所有详情接口失败 | `NoticeRaw.status = failed` |
| 详情返回空结构 | `NoticeDetail.is_suspect = true` |

### 5.3 文件阶段

**这里刚修过，规则如下：**

| 条件 | 结果 |
|---|---|
| 没提取到文件候选 | 保持 `detail_done`，不再直接标 `file_done` |
| 有候选且全部成功 | `file_done` |
| 有候选但部分失败 | `partial` |
| 文件内容为空 | `NoticeFile.is_suspect = true` |

## 6. sourceRunId 设计

### 6.1 含义

`sourceRunId` 用于标记一次完整采集运行，便于：

| 用途 |
|---|
| 按一次运行排查所有 task / raw / detail / file |
| 隔离脏批次 |
| 做定向重放 |
| 复盘某次结构变化 |

### 6.2 当前流转

| 对象 | 当前情况 |
|---|---|
| orchestrator | 初始化时生成 `uuid4()` |
| task payload | 已写入 `sourceRunId` |
| `state_grid_crawl_tasks` | 已持久化 |
| `state_grid_notice_raws` | 已持久化 |
| `state_grid_notice_details` | 已持久化 |
| `state_grid_notice_files` | 已持久化 |

## 7. suspect 标记设计

### 7.1 字段

| 表 | 字段 |
|---|---|
| `state_grid_notice_raws` | `is_suspect`, `suspect_reason` |
| `state_grid_notice_details` | `is_suspect`, `suspect_reason` |
| `state_grid_notice_files` | `is_suspect`, `suspect_reason` |

### 7.2 当前规则

| 场景 | 表 | 标记 |
|---|---|---|
| 列表返回 `count > 0` 但 `noteList` 空 | `NoticeRaw` | `note_list_empty_with_positive_count` |
| 详情空结构且无 HTML | `NoticeDetail` | `empty_detail_payload` |
| 文件内容为空 | `NoticeFile` | `empty_file_payload` |

## 8. orgId 固化规则

你特别要求的点：**`orgId` 只在 `noteList` 有，详情接口会丢失，所以初始化阶段必须固化。**

### 8.1 当前规则

| 表 | orgId 来源 |
|---|---|
| `state_grid_notice_raws.org_id` | `raw_list_json.orgId` |
| `state_grid_notice_details.org_id` | 从 `NoticeRaw.org_id` 继承 |
| `state_grid_notice_files.org_id` | 从 `NoticeRaw.org_id` 继承 |

### 8.2 结果

后续做清洗、关联、建宽表时：

| 需求 | 是否还要回看 list raw JSON |
|---|---|
| 拿 `orgId` | 不需要 |
| 拿 notice 基础信息 | 通常不需要 |

## 9. 当前 DB / OSS / 本地分工

| 数据 | DB | OSS | 本地镜像 |
|---|---|---|---|
| 列表 raw JSON | `NoticeRaw.rawListJson` | 是 | 是 |
| 详情 raw JSON | `NoticeDetail.rawDetailJson` | 是 | 是 |
| 详情 HTML | `NoticeDetail.rawHtml` | 是 | 是 |
| 文件元信息 | `NoticeFile` | 否 | 否 |
| zip/pdf/html 原文 | 否 | 是 | 是 |
| task / watermark | 是 | 否 | 否 |

## 10. 当前已知正确行为

| 项 | 状态 |
|---|---|
| `noteList` 必须带 `firstPageMenuId=2018032900295987` | 已确认 |
| `noteList` 必须带有效 `JSESSIONID` | 已确认 |
| `resultValue.noteList` 才是项目列表 | 已确认 |
| `downLoadBid?noticeId=` 能下载 zip | 已确认 |
| 1 条公告文件下载与入库 | 已确认 |
| `file_done` 误标记逻辑 | 已修复 |
| 历史误标 `file_done` 数据 | 已回滚 |

## 11. 当前仍需继续补强的点

| 优先级 | 问题 | 建议 |
|---|---|---|
| P0 | `sync_org_tree()` 不是主干 | 目前可不阻塞主流程，后续独立修 |
| P0 | 文件候选提取仍较粗糙 | 对不同公告类型细分规则 |
| P0 | 详情接口路由仍较粗 | 可根据 `doctype/noticeType` 更精准选择 API |
| P1 | 当前增量逻辑较保守 | 后续再引入真正 watermark 分页恢复 |
| P1 | suspect 规则还不够丰富 | 可继续增加结构漂移检测 |
| P1 | scheduler 只是基础版 | 后续可拆成 list/detail/file 三类 job |

## 12. 初始化建议

| 阶段 | 做法 |
|---|---|
| 1 | 先只跑采购公告 1 页 |
| 2 | 确认 raw/detail/file 入库正确 |
| 3 | 分批跑 5 页 / 50 页 |
| 4 | 再做完整全量 |
| 5 | 之后再扩到招标公告 / 结果公告 |

## 13. 命令

| 用途 | 命令 |
|---|---|
| 采购公告 1 页全链路 | `cd packages/compute && .venv/bin/python -m scripts.fetch_state_grid_raw --mode full --limit-pages 1` |
| 单公告详情+文件 | `cd packages/compute && .venv/bin/python -m scripts.fetch_state_grid_raw --notice-id <NOTICE_ID> --with-files` |
| 死信重放 | `cd packages/compute && .venv/bin/python -m scripts.fetch_state_grid_raw --replay-dead --task-type file` |

## 14. 维护原则

| 原则 | 说明 |
|---|---|
| 不删错 raw | 用 `sourceRunId + suspect` 隔离 |
| 不依赖重新解析列表 JSON 拿 orgId | 初始化阶段就固化 |
| 文件状态不提前结束 | 只有明确成功才 `file_done` |
| 主流程先可跑，再补 orgTree / 精细规则 | 避免非主干阻塞 |
