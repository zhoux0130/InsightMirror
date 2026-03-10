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

**Testing Requirements (MANDATORY):**

> **⛔ Rule: If task steps include browser testing but MCP Playwright is unavailable or browser testing cannot be executed, the task is BLOCKED. Do NOT mark passes: true, do NOT commit. Output blocking info and stop.**

1. **Major page changes** (new pages, component rewrites, core interaction changes):
   - **MUST test in browser!** Use MCP Playwright tools
   - Verify page loads and renders correctly
   - Verify form submissions, button clicks, and other interactions
   - Take screenshots to confirm correct UI display

2. **Minor code changes** (bug fixes, style adjustments, helper functions):
   - Can verify with unit tests or lint/build
   - If in doubt, still recommend browser testing

3. **All changes must pass:**
   - web: `pnpm --filter web build` — build successful
   - server: `pnpm --filter server lint` — no errors
   - server: `pnpm --filter server build` — build successful
   - compute: `cd packages/compute &amp;&amp; python -m pytest tests/` — build successful
   - Browser/unit tests verify functionality works

**Browser Testing Credentials:**

```


微信 OAuth 登录，本地开发可能需要 mock 或测试账号
```

**Browser Testing Best Practices:**

1. **Login flow**: Open `http://localhost:5173`, login with test credentials
2. **Navigate directly**: After login, go directly to the target page URL
3. **Focus scope**: Only test functionality related to the current task
4. **Screenshot key steps**: Page load, interactions, result verification
5. **Screenshot on errors**: If errors occur, screenshot first, then debug

**Test Checklist:**
- [ ] No compilation errors
- [ ] web build succeeds
- [ ] server lint passes
- [ ] server build succeeds
- [ ] compute build succeeds
- [ ] Functionality works in browser (for UI changes)

**Test Artifact Traceability (MANDATORY):**

Each test must leave complete evidence in `$AGENT_SESSION_DIR` (created by init.sh):

1. **Screenshots** → `../artifacts/screenshots/`
   - Naming: `task{id}_step{n}_{description}.png`
   - Screenshot every key browser testing step
   - Screenshot error states too (for debugging)

2. **Logs** → `$AGENT_LOGS_DIR/`
   - `0-build.log` — `pnpm --filter web build` full output
   - `1-lint.log` — `pnpm --filter server lint` full output
   - `1-build.log` — `pnpm --filter server build` full output
   - `2-build.log` — `cd packages/compute &amp;&amp; python -m pytest tests/` full output

3. **Test report** → `$AGENT_SESSION_DIR/test-report.md`
   - init.sh generates a template; agent must update after testing
   - Fill in each test step result (PASS/FAIL)
   - Link screenshots and log file paths
   - Mark final conclusion (PASSED / FAILED / BLOCKED)

4. **Build verification commands (with log redirect):**
   ```bash
   # web build
   cd packages/web/ && pnpm --filter web build 2>&1 | tee "$AGENT_LOGS_DIR/0-build.log"
   # server lint
   cd packages/server/ && pnpm --filter server lint 2>&1 | tee "$AGENT_LOGS_DIR/1-lint.log"
   # server build
   cd packages/server/ && pnpm --filter server build 2>&1 | tee "$AGENT_LOGS_DIR/1-build.log"
   # compute build
   cd packages/compute/ && cd packages/compute &amp;&amp; python -m pytest tests/ 2>&1 | tee "$AGENT_LOGS_DIR/2-build.log"
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



### Step 1.5: Start Local Services (Mandatory)

> **⛔ Rule: Before executing any task, you MUST ensure all local services are running. Violating this rule means the task CANNOT proceed.**

**Local service checklist:**

1. **Start web** (if not running):
   ```bash
   cd packages/web/ && pnpm --filter web dev
   ```
   - Port: 5173

2. **Start server** (if not running):
   ```bash
   cd packages/server/ && pnpm --filter server dev
   ```
   - Port: 3000

3. **Start compute** (if not running):
   ```bash
   cd packages/compute/ && cd packages/compute && python -m uvicorn app.main:app --reload --port 8000
   ```
   - Port: 8000


**Prohibited:**
- ❌ Do NOT rely on remote/staging environments for development testing
- ❌ Do NOT proceed with browser testing if services are not running


---

## ⚠️ Blocking Issues

**If a task cannot complete testing or requires manual intervention, follow these rules:**

### Situations requiring manual help:

1. **Missing environment config**:
   - Database, cache, or external service credentials not configured
   - Dev proxy not pointing to a reachable backend

2. **External dependencies unavailable**:
   - Third-party API services down
   - OAuth flows requiring manual authorization
   - Services requiring paid upgrades

3. **Testing tools unavailable**:
   - **MCP Playwright not installed or unavailable, but task requires browser testing** ← This is a blocker, cannot skip
   - Dev server cannot start
   - Backend not reachable

4. **Tests cannot proceed**:
   - Login requires real user accounts
   - Functionality depends on undeployed external systems
   - Requires specific hardware environment

### Correct actions when blocked:

**DO NOT:**
- ❌ Commit to git
- ❌ Set task.json passes to true
- ❌ Pretend the task is complete

**DO:**
- ✅ Record progress and blocking reason in progress.txt
- ✅ Output clear blocking info explaining what manual action is needed
- ✅ Stop the task and wait for manual intervention

### Blocking info format:

```
🚫 Task Blocked - Manual Intervention Required

**Current task**: [task name]

**Completed work**:
- [code/config already done]

**Blocking reason**:
- [specific explanation of why it cannot continue]

**Manual help needed**:
1. [specific step 1]
2. [specific step 2]
...

**After unblocking**:
- Run [command] to continue the task
```


---

## Project Structure

```
/insightmirror/
├── agent-harness/              # This directory - Agent automation
│   ├── CLAUDE.md               # This file - workflow instructions
│   ├── task.json               # Task definitions (source of truth)
│   ├── progress.txt            # Session progress log
│   └── init.sh                 # Init script
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

1. **One task per session** - Focus on completing one task well
2. **Test before marking complete** - All steps must pass
3. **Browser testing for UI changes** - New pages or major modifications MUST be browser tested
4. **Document in progress.txt** - Help future agents understand your work
5. **One commit per task** - All changes (code, progress.txt, task.json) must be committed together
6. **Never remove tasks** - Only flip `passes: false` to `true`
7. **Stop if blocked** - When manual intervention is needed, do not commit; output blocking info and stop
9. **Artifacts** - Save test screenshots, logs, and traces to `$AGENT_SESSION_DIR` (created by init.sh), each session gets its own directory
10. **Test traceability** - After each task, update `test-report.md` to ensure screenshots, logs, and test results are traceable


---

## API Overview

API base path: `/api`

| Module | Path Prefix | Description |
|--------|-------------|-------------|
| Health | /api/health | 健康检查 |
| Auth | /api/auth | 微信 OAuth 登录、JWT 认证 |
| Compute | /compute | Python 计算服务（数据抓取、指标计算） |