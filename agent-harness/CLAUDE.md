# InsightMirror - Project Instructions

## Project Context

InsightMirror — Mobile H5 应用，monorepo 架构（pnpm workspace），包含三个模块：
- **web** (packages/web)：React 18 + Vite + TypeScript，移动端 H5 界面
- **server** (packages/server)：Fastify 5 + Prisma + PostgreSQL (pgvector)，后端 API
- **compute** (packages/compute)：Python FastAPI，数据计算服务（akshare/tushare）
Docker Compose 编排，PostgreSQL + pgvector 数据库。


- **web**: React 18 + Vite 6 + TypeScript + React Router 6 + Axios
- **server**: Fastify 5 + Prisma + PostgreSQL (pgvector) + JWT + Swagger
- **compute**: Python FastAPI + akshare/tushare + PostgreSQL

---

## MANDATORY: Agent Workflow

Every new agent session MUST follow this workflow:

### Step 1: Initialize Environment

```bash
./init.sh
```

This will:
- Check web repository exists
- Install web dependencies
- Start web dev server (port 5173)
- Check server repository exists
- Install server dependencies
- Start server dev server (port 3000)
- Check compute repository exists
- Start compute dev server (port 8000)

**DO NOT skip this step.** Ensure the server is running before proceeding.

### Step 1.5: 启动本地服务（铁律）

> **⛔ 铁律：执行任何 task 之前，必须确保本地服务都已启动。违反此规则禁止继续执行 task。**

**本地服务启动清单：**

1. **启动 web**（如未运行）：
   ```bash
   cd packages/web/ && pnpm --filter web dev
   ```
   - 端口: 5173
   - 验证: `curl -s http://localhost:5173/ | head -c 100` 能返回内容

2. **启动 server**（如未运行）：
   ```bash
   cd packages/server/ && pnpm --filter server dev
   ```
   - 端口: 3000
   - 验证: `curl -s http://localhost:3000/ | head -c 100` 能返回内容

3. **启动 compute**（如未运行）：
   ```bash
   cd packages/compute/ && cd packages/compute && python -m uvicorn app.main:app --reload --port 8000
   ```
   - 端口: 8000
   - 验证: `curl -s http://localhost:8000/ | head -c 100` 能返回内容


**验证联通性：**
- 在浏览器中访问前端页面，确认能正常加载
- 如果出现 504/502/连接拒绝，说明后端未启动，必须先启动
- 使用 `mcp__playwright__browser_navigate` 访问前端确认页面可达

**禁止事项：**
- ❌ 禁止依赖远程/测试环境进行开发测试
- ❌ 禁止在后端未启动时进行浏览器测试
- ❌ 禁止跳过服务联通性验证


### Step 2: Select Next Task

Read `task.json` and select ONE task to work on.

Selection criteria (in order of priority):
1. Choose a task where `passes: false`
2. Consider dependencies - fundamental features should be done first
3. Pick the highest-priority incomplete task

### Step 3: Implement the Task

- Read the task description and steps carefully
- Implement the functionality to satisfy all steps
- Follow existing code patterns and conventions

### Step 4: Test Thoroughly

After implementation, verify ALL steps in the task.

**强制测试要求（Testing Requirements - MANDATORY）：**

> **⛔ 铁律：如果任务步骤中包含浏览器测试，但 MCP Playwright 不可用或浏览器测试无法执行，则该任务视为「阻塞」，禁止标记 passes: true，禁止提交 commit。必须输出阻塞信息并停止。**

1. **大幅度页面修改**（新建页面、重写组件、修改核心交互）：
   - **必须在浏览器中测试！** 使用 MCP Playwright 工具
   - 使用 `mcp__playwright__browser_navigate` 打开页面
   - 使用 `mcp__playwright__browser_snapshot` 获取页面无障碍快照（比截图更适合判断页面状态）
   - 使用 `mcp__playwright__browser_click` / `mcp__playwright__browser_fill_form` 进行表单和交互操作
   - 使用 `mcp__playwright__browser_take_screenshot` 截图确认 UI 正确显示
   - 使用 `mcp__playwright__browser_wait_for` 等待异步内容加载
   - 验证页面能正确加载和渲染
   - 验证表单提交、按钮点击等交互功能

2. **小幅度代码修改**（修复 bug、调整样式、添加辅助函数）：
   - 可以使用单元测试或 lint/build 验证
   - 如有疑虑，仍建议浏览器测试

3. **所有修改必须通过：**
   - web: `pnpm --filter web build` 构建成功
   - server: `pnpm --filter server lint` 无错误
   - server: `pnpm --filter server build` 构建成功
   - compute: `cd packages/compute &amp;&amp; python -m pytest tests/` 构建成功
   - 浏览器/单元测试验证功能正常

**测试环境账号（Browser Testing Credentials）：**

```


支持用户名密码注册登录，agent 可自行注册测试账号；微信 OAuth 登录待审批
```

**浏览器测试规范（Browser Testing Best Practices）：**

1. **登录流程**：使用 `mcp__playwright__browser_navigate` 打开 `http://localhost:5173`，使用测试账号登录
2. **直达目标页面**：登录成功后，使用 `mcp__playwright__browser_navigate` 直接导航到任务涉及的页面 URL，不要在无关页面停留
3. **聚焦测试范围**：只验证当前 task 涉及的功能，不要测试无关模块
4. **每个关键步骤截图**：使用 `mcp__playwright__browser_take_screenshot` 对页面加载、交互操作、结果验证各截一张
5. **异常时截图留证**：如果遇到错误，先截图再排查
6. **使用快照辅助判断**：操作前后使用 `mcp__playwright__browser_snapshot` 获取页面结构，确认元素存在和状态变化

**浏览器测试标准流程：**
```
1. mcp__playwright__browser_navigate → 打开登录页
2. mcp__playwright__browser_fill_form → 填写账号密码
3. mcp__playwright__browser_click → 点击登录
4. mcp__playwright__browser_wait_for → 等待登录成功
5. mcp__playwright__browser_navigate → 导航到目标页面
6. mcp__playwright__browser_snapshot → 获取页面快照，确认渲染正确
7. mcp__playwright__browser_take_screenshot → 截图留证
8. 执行交互操作（click / fill_form 等）
9. mcp__playwright__browser_snapshot → 确认操作结果
10. mcp__playwright__browser_take_screenshot → 截图留证
```

**测试清单：**
- [ ] 代码没有编译错误
- [ ] web build 成功
- [ ] server lint 通过
- [ ] server build 成功
- [ ] compute build 成功
- [ ] 功能在浏览器中正常工作（对于 UI 相关修改）
- [ ] 关键步骤已截图保存

**测试留痕（Test Artifact Traceability - MANDATORY）：**

所有运行时产物保存在 `.runtime/`（gitignored，由 init.sh 创建）：

1. **截图留痕** → `.runtime/screenshots/`
   - 命名规则: `task{id}_step{n}_{描述}.png`，如 `task3_step1_login.png`
   - 浏览器测试的每个关键步骤都要截图
   - 错误状态也要截图（用于排查）
   - 此目录已被 gitignore，截图为临时过程数据

2. **日志留痕** → `.runtime/logs/`
   - `web-build.log` — `pnpm --filter web build` 的完整输出
   - `server-lint.log` — `pnpm --filter server lint` 的完整输出
   - `server-build.log` — `pnpm --filter server build` 的完整输出
   - `compute-build.log` — `cd packages/compute &amp;&amp; python -m pytest tests/` 的完整输出

3. **测试报告** → `.runtime/test-report.md`
   - init.sh 已生成模板，agent 需在测试完成后更新
   - 填写每个测试步骤的结果（PASS/FAIL）
   - 关联截图和日志文件路径
   - 标注最终测试结论（PASSED / FAILED / BLOCKED）

4. **构建验证命令（日志重定向）：**
   ```bash
   # web build
   cd packages/web/ && pnpm --filter web build 2>&1 | tee "$AGENT_LOGS_DIR/web-build.log"
   # server lint
   cd packages/server/ && pnpm --filter server lint 2>&1 | tee "$AGENT_LOGS_DIR/server-lint.log"
   # server build
   cd packages/server/ && pnpm --filter server build 2>&1 | tee "$AGENT_LOGS_DIR/server-build.log"
   # compute build
   cd packages/compute/ && cd packages/compute &amp;&amp; python -m pytest tests/ 2>&1 | tee "$AGENT_LOGS_DIR/compute-build.log"
   ```


### Step 5: Update Progress

Write your work to `progress.txt`:

```
## [Date] - Task: [task description]

### What was done:
- [specific changes made]

### Testing:
- [how it was tested]

### Notes:
- [any relevant notes for future agents]
```

### Step 6: Commit Changes (including task.json update)

**IMPORTANT: All changes must be committed together, including the task.json update!**

Workflow:
1. Update `task.json` — flip the task's `passes` from `false` to `true`
2. Update `progress.txt` — record your work
3. Commit all changes at once:

```bash
git add [modified files] task.json progress.txt
git commit -m "task#{id}: [task description] - completed"
```

**Rules:**
- Only mark `passes: true` after ALL steps are verified
- **Including browser tests! If the task requires browser testing but it was not performed, do NOT mark passes: true**
- Never delete or modify task descriptions
- Never remove tasks from the list



---

## ⚠️ 阻塞处理（Blocking Issues）

**如果任务无法完成测试或需要人工介入，必须遵循以下规则：**

### 需要停止任务并请求人工帮助的情况：

1. **缺少环境配置**：
   - 数据库、缓存、外部服务凭证未配置
   - 前端代理地址未指向可用的后端

2. **外部依赖不可用**：
   - 第三方 API 服务宕机
   - 需要人工授权的 OAuth 流程
   - 需要付费升级的服务

3. **测试工具不可用**：
   - **MCP Playwright 未安装或不可用，但任务要求浏览器测试** ← 这是阻塞，不能跳过
   - dev server 无法启动
   - 后端服务不可达

4. **测试无法进行**：
   - 登录/注册功能需要真实用户账号
   - 功能依赖外部系统尚未部署
   - 需要特定硬件环境

### 阻塞时的正确操作：

**DO NOT（禁止）：**
- ❌ 提交 git commit
- ❌ 将 task.json 的 passes 设为 true
- ❌ 假装任务已完成

**DO（必须）：**
- ✅ 在 progress.txt 中记录当前进度和阻塞原因
- ✅ 输出清晰的阻塞信息，说明需要人工做什么
- ✅ 停止任务，等待人工介入

### 阻塞信息格式：

```
🚫 任务阻塞 - 需要人工介入

**当前任务**: [任务名称]

**已完成的工作**:
- [已完成的代码/配置]

**阻塞原因**:
- [具体说明为什么无法继续]

**需要人工帮助**:
1. [具体的步骤 1]
2. [具体的步骤 2]
...

**解除阻塞后**:
- 运行 [命令] 继续任务
```


---

## Project Structure

```
/insightmirror/
├── agent-harness/              # This directory - Agent automation
│   ├── CLAUDE.md               # This file - workflow instructions
│   ├── task.json               # Task definitions (source of truth)
│   ├── progress.txt            # Session progress log
│   ├── init.sh                 # Init script
│   └── .runtime/                # Runtime artifacts (gitignored)
│       ├── screenshots/        # Browser test screenshots
│       ├── logs/               # Build & lint logs
│       └── test-report.md      # Test results
├── web/
├── server/
├── compute/
```

## Commands

```bash
# web (in packages/web/)
pnpm install         # Install dependencies
pnpm --filter web dev  # Start dev server
pnpm --filter web build  # Build

# server (in packages/server/)
pnpm install         # Install dependencies
pnpm --filter server dev  # Start dev server
pnpm --filter server build  # Build
pnpm --filter server lint   # Lint
pnpm --filter server test   # Test

# compute (in packages/compute/)
cd packages/compute && python -m uvicorn app.main:app --reload --port 8000  # Start dev server
cd packages/compute && python -m pytest tests/  # Build

```

## Coding Conventions

**Frontend (web):**
- React 18 + TypeScript
- Vite 构建
- React Router 6 路由
- Axios HTTP 请求
- 移动端 H5 适配

**Backend (server):**
- Fastify 5 框架
- Prisma ORM + PostgreSQL (pgvector)
- JWT 认证（cookie-based）
- Swagger API 文档
- cross-env 环境变量管理

**Compute (Python):**
- FastAPI 框架
- akshare / tushare 数据源
- 定时任务调度（scheduler）
- pytest 测试


---

## Key Rules

1. **One task per session** - 专注完成一个任务
2. **Test before marking complete** - 所有步骤必须通过验证
3. **Browser testing for UI changes** - 新建或大幅修改页面必须使用 MCP Playwright 在浏览器中测试，不能跳过
4. **Document in progress.txt** - 帮助后续 agent 理解你的工作
5. **One commit per task** - 所有更改（代码、progress.txt、task.json）必须在同一个 commit 中提交
6. **Never remove tasks** - 只能将 `passes: false` 改为 `true`
7. **Stop if blocked** - 需要人工介入时，不要提交，输出阻塞信息并停止
9. **Artifacts** - 测试截图、日志、trace 等产物保存到 `$AGENT_RUNTIME_DIR` 目录（由 init.sh 创建），gitignored
10. **Test traceability** - 每个 task 完成后必须更新 `test-report.md`，确保截图、日志、TC 结果可追溯
11. **MCP Playwright 是必备工具** - 如果 MCP Playwright 不可用，涉及 UI 的任务视为阻塞，禁止标记完成


---

## API Overview

API base path: `/api`

| Module | Path Prefix | Description |
|--------|-------------|-------------|
| Health | /api/health | 健康检查 |
| Auth | /api/auth | 微信 OAuth 登录、JWT 认证 |
| Compute | /compute | Python 计算服务（数据抓取、指标计算） |