# Stock Detail Demo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a demo-ready A-share stock detail page backed by a single business API that aggregates price, structure, entry zone, emotion, risk/reward, and flow continuity for already initialized symbols.

**Architecture:** Keep `compute` as the generic feature/vector engine and implement demo-specific orchestration in `server`. The server will read bars from PostgreSQL, call `compute` only for feature-vector generation, search similar segments through pgvector, compute short-horizon stats online, and return a UI-ready DTO to the web client.

**Tech Stack:** Fastify, TypeScript, Prisma, `pg`, React, Vite, PostgreSQL/pgvector.

### Task 1: Add server test infrastructure and pure indicator tests

**Files:**
- Create: `packages/server/jest.config.cjs`
- Create: `packages/server/src/apps/api/services/stock-detail-calculations.test.ts`
- Create: `packages/server/src/apps/api/services/stock-detail-calculations.ts`

**Step 1: Write the failing test**

Add tests for:
- ATR-based entry zone and invalidation level
- stage classification and phase mapping
- emotion score bucketing
- flow continuity classification
- rating mapping from component scores

**Step 2: Run test to verify it fails**

Run: `pnpm --filter server test -- stock-detail-calculations`
Expected: FAIL because the module or exported functions do not exist yet.

**Step 3: Write minimal implementation**

Implement pure functions that accept normalized bar arrays and return typed outputs for the detail page cards.

**Step 4: Run test to verify it passes**

Run: `pnpm --filter server test -- stock-detail-calculations`
Expected: PASS.

### Task 2: Add server stock-detail service and routes

**Files:**
- Create: `packages/server/src/apps/api/controllers/stocks.ts`
- Create: `packages/server/src/apps/api/services/stock-detail-service.ts`
- Modify: `packages/server/src/apps/api/routes.ts`
- Modify: `packages/server/src/services/pgvector.ts`

**Step 1: Write the failing test**

Add tests for service-level helpers such as:
- similar result deduplication by window gap
- 3D/5D forward statistics calculation from matched windows
- stock options filtering for initialized symbols

**Step 2: Run test to verify it fails**

Run: `pnpm --filter server test -- stock-detail`
Expected: FAIL because the service helpers and DTO assembly do not exist.

**Step 3: Write minimal implementation**

Implement:
- `GET /api/stocks/options`
- `GET /api/stocks/:symbol/detail`
- database reads for `security_master`, `daily_bar`, and similar segments
- compute feature proxy to `/compute/v1/feature`
- online 3D/5D statistics from matched windows

**Step 4: Run test to verify it passes**

Run: `pnpm --filter server test -- stock-detail`
Expected: PASS.

### Task 3: Add web API client and page rendering

**Files:**
- Create: `packages/web/src/services/stocks.ts`
- Modify: `packages/web/src/pages/Home.tsx`
- Modify: `packages/web/src/index.css`

**Step 1: Define typed DTO usage**

Add typed client methods for the new server endpoints and keep UI state minimal: selected symbol, selected date, loading, error, detail payload, and local favorite state.

**Step 2: Build the page**

Implement:
- stock selector and query form
- summary card
- rating / entry / emotion / phase / risk-reward / flow sections
- loading / empty / error states
- mobile-first styling matching the supplied demo direction

**Step 3: Run build verification**

Run: `pnpm --filter web build`
Expected: PASS.

### Task 4: Verify end-to-end behavior

**Files:**
- Modify as needed based on verification findings

**Step 1: Run targeted verification**

Run:
- `pnpm --filter server test -- --runInBand`
- `pnpm --filter server build`
- `pnpm --filter web build`

Expected: all pass.

**Step 2: Smoke check the API against the local database**

Run the server against the existing local Postgres data and confirm:
- `GET /api/stocks/options` returns initialized symbols
- `GET /api/stocks/300750.SZ/detail` returns all required cards

**Step 3: Commit**

Stage the changed files and commit with a focused message once verification is green.
