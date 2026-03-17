# InsightMirror - Agent Workflow

## Project Context

InsightMirror — Mobile H5 应用，monorepo（pnpm workspace）：
- **web** (packages/web)：React 18 + Vite + TypeScript
- **server** (packages/server)：Fastify 5 + Prisma + PostgreSQL (pgvector)
- **compute** (packages/compute)：Python FastAPI + akshare/yahoo

## Tech Stack

- **web**: React 18 + Vite 6 + TypeScript + React Router 6 + Axios
- **server**: Fastify 5 + Prisma + PostgreSQL (pgvector) + JWT + Swagger
- **compute**: Python FastAPI + akshare/tushare + PostgreSQL

---

## Agent Workflow

每个 task 遵循 4 步循环：**实现 → 测试 → 标记完成 → 提交**

### Step 1: 选择任务

读取 `task.json`，选择一个 `passes: false` 的任务。优先选 id 最小的未完成任务。

### Step 2: 实现

- 仔细阅读 task 的 description 和 steps
- 按照已有代码风格实现
- 只改必要的代码，不过度工程化

### Step 3: 测试

> 只测试当前 task 涉及的模块，不需要全量构建。

**按模块测试：**

| 模块 | 测试命令 | 何时需要 |
|------|---------|---------|
| compute | `cd packages/compute && .venv/bin/python -m pytest tests/ -v` | task 涉及 compute 代码 |
| server | `pnpm --filter server build` | task 涉及 server 代码 |
| web | `pnpm --filter web build` | task 涉及 web 代码 |

**浏览器测试（仅 UI 类 task）：**

涉及前端页面修改时，使用 MCP Playwright 验证：
1. `mcp__playwright__browser_navigate` → 打开页面
2. `mcp__playwright__browser_snapshot` → 确认渲染
3. 交互操作 → 确认功能
4. `mcp__playwright__browser_take_screenshot` → 截图留证

如果 task 要求浏览器测试但 MCP Playwright 不可用，该 task 视为阻塞，禁止标记完成。

**测试账号：** 支持用户名密码注册登录，agent 可自行注册测试账号。

### Step 4: 标记完成 & 提交

测试通过后，一次性完成以下操作：

1. 修改 `task.json` 中对应 task 的 `passes` 为 `true`
2. 将所有改动（代码 + task.json）提交为一个 commit

```bash
git add [修改的文件] agent-harness/task.json
git commit -m "task#<id>: <task title>"
```

**规则：**
- 测试未通过 → 禁止标记 `passes: true`，禁止 commit
- 一个 task 一个 commit
- 不要删除或修改 task 的 description/steps

---

## 阻塞处理

无法完成时，输出阻塞信息并停止，**不提交、不标记完成**：

```
BLOCKED: <task title>
原因: <具体原因>
需要: <人工操作>
```

---

## 启动本地服务

执行 task 前确认相关服务已启动（只启动 task 需要的服务）：

```bash
# web (port 5173)
cd packages/web/ && pnpm --filter web dev

# server (port 3000)
cd packages/server/ && pnpm --filter server dev

# compute (port 8000)
cd packages/compute && .venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

---

## Commands Quick Reference

```bash
# web
pnpm --filter web dev          # dev server
pnpm --filter web build        # build

# server
pnpm --filter server dev       # dev server
pnpm --filter server build     # build
pnpm --filter server lint      # lint

# compute
cd packages/compute && .venv/bin/python -m uvicorn app.main:app --reload --port 8000
cd packages/compute && .venv/bin/python -m pytest tests/ -v
```

## API Overview

| Module | Path Prefix | Description |
|--------|-------------|-------------|
| Health | /api/health | 健康检查 |
| Auth | /api/auth | 认证（用户名密码 / 微信 OAuth） |
| Stocks | /api/stocks | 股票列表 & 详情 |
| Compute | /compute/v1 | 数据 pipeline 管理 |
