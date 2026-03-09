# A-Share Historical Initialization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a zero-paid-API initialization pipeline for full A-share 10-year daily history, then generate segment metadata, pgvector features, and future labels for the existing similarity-search system.

**Architecture:** Use `AKShare` as the primary free data source for the first version, persist raw snapshots locally for replayability, bulk-load normalized OHLCV data into PostgreSQL, then batch-build `segment_index`, `segment_feature`, and `segment_future_label` in separate offline stages. Do not reuse the current EOD-oriented fetch loop for historical initialization; implement a dedicated full-history pipeline and keep the EOD pipeline as a later follow-up.

**Tech Stack:** Python 3.11, AKShare, pandas, NumPy, SQLAlchemy, psycopg2, PostgreSQL, Prisma, pgvector, pytest.

## 1. Scope And Decisions

### Fixed decisions
- Market: A-share only.
- History range: `2016-01-01` to `2026-03-06` for the first full initialization.
- Price basis for v1: unadjusted daily bars.
- Window size: 60 trading days.
- Feature version: `v1` only.
- Future label horizon: 20 trading days.
- Data source for v1: `AKShare`.

### Why this version is the right first cut
- It satisfies the business target in the prior design docs: full A-share history, offline initialization, then online read-only search.
- It avoids paid APIs and keeps the data-source layer replaceable.
- It avoids the look-ahead risk of directly relying on full-history adjusted prices in v1.
- It matches the current repo split: `packages/compute` for ingest + feature work, `packages/server` for schema and API serving.

### Explicit non-goals for this phase
- No fundamentals, valuation ratios, or shareholder data.
- No automatic EOD scheduler refactor yet.
- No multi-source reconciliation yet.
- No feature formula change beyond the existing `v1` calculator.

## 2. Gap Between Current Repo And Target Design

### Current blockers in the repo
- `packages/compute/app/core/pipeline/orchestrator.py` fetches symbols from existing `daily_bar`, so first-time initialization cannot bootstrap itself.
- `packages/compute/app/data/tushare.py` assumes a Tushare token and is not suitable for a zero-paid-API plan.
- `packages/compute/scripts/full_init.py` seeds only pgvector metadata; it does not ingest bars or build history.
- `packages/server/prisma/schema.prisma` lacks a stock master table, so there is no durable source of active and delisted symbols.

### Required architectural correction
The repo needs a dedicated historical initialization path:
1. Fetch stock universe into a master table.
2. Fetch and persist 10-year raw daily history.
3. Bulk-normalize and import into `daily_bar`.
4. Batch-build all segments and vectors.
5. Batch-backfill future labels.
6. Build HNSW index only after bulk insert completes.

## 3. Recommended Initialization Pipeline

### Stage 0: Bootstrap metadata
Create a persistent stock universe table named `security_master` in Prisma.

Required fields:
- `symbol`: canonical code such as `000001.SZ`
- `name`
- `exchange`: `SSE` or `SZSE`
- `listDate`
- `delistDate` nullable
- `listStatus`: `listed`, `delisted`, `suspended`
- `source`
- `updatedAt`

Rationale:
- Historical initialization cannot depend on `daily_bar` to discover symbols.
- EOD ingest later should also read from this table.
- Delisted symbols must remain queryable for historical segment coverage.

### Stage 1: Raw snapshot ingest
Fetch the A-share symbol list from AKShare and write it to two places:
- PostgreSQL `security_master`
- Local raw snapshot storage under `packages/compute/data/raw/akshare/`

Recommended layout:
- `packages/compute/data/raw/akshare/universe/YYYY-MM-DD/stocks.parquet`
- `packages/compute/data/raw/akshare/daily/<symbol>.parquet`

Rules:
- One file per symbol for daily history.
- Re-runs overwrite the same symbol snapshot atomically.
- Persist raw source columns in the snapshot, normalize only during load.

### Stage 2: Daily bar normalization and bulk load
Normalize each symbol history to the existing `daily_bar` schema:
- `symbol`
- `trade_date`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `amount`
- `turnover`
- `pct_change`

Normalization rules:
- Canonical symbol format must match current DB usage, for example `000001.SZ` or `600000.SH`.
- Drop rows before each symbol's `listDate`.
- Enforce unique `(symbol, trade_date)`.
- Sort ascending by `trade_date` before writing.
- Preserve nullability for unavailable `amount`, `turnover`, and `pct_change`.

Load strategy:
- Convert normalized batches to CSV or in-memory tuples.
- Use PostgreSQL `COPY` into a staging table.
- Upsert from staging into `daily_bar`.
- Commit per batch, not per row.

### Stage 3: Full segment and feature build
For each symbol:
- Read all bars ordered by `trade_date`.
- Generate every 60-day window.
- Produce one `segment_index` row per window.
- Produce one `segment_feature` row per segment using the existing `v1` calculator.
- Create a `segment_future_label` placeholder row with `pending` status.

Implementation rules:
- Build vectors in batches per symbol or symbol chunk.
- Insert `segment_index` in batches.
- Insert `segment_feature` in batches.
- Insert pending labels in batches.
- Keep this stage restartable by using natural uniqueness keys and upserts.

Important correction to current strategy:
- Disable HNSW creation during the bulk feature load.
- Create the index only after all vectors are written.

### Stage 4: Future label backfill
Backfill labels only after the full daily history and segment metadata exist.

Definition:
- Base date: segment `end_date`
- Horizon: next 20 trading days
- Metrics: `return_rate`, `max_drawdown`, `max_profit`, `sharpe_ratio`, `win_flag`

Rules:
- Use trading-day offsets from `daily_bar`, not calendar-day math.
- If there are fewer than 20 future trading bars, mark status as `na`.
- Never use future data when building the feature vector itself.

### Stage 5: HNSW index build and verification
After `segment_feature` is complete:
- Create pgvector extension if needed.
- Create `segment_feature` table if needed.
- Build the HNSW index.
- Run smoke queries to verify cosine-search results are returned.

## 4. Data Source Choice And Trade-offs

### Recommended option: AKShare only for v1
Pros:
- Zero paid API cost.
- Python-native and fits the existing `packages/compute` service.
- Good enough for prototype and internal MVP.

Cons:
- External website dependencies can change.
- Some endpoints may become unstable without warning.
- Data quality checks must be owned by us.

### Rejected options for this phase
- Tushare as primary source: current zero-budget constraint does not fit.
- Mixed-source merge: too much complexity for the first initialization pass.
- Direct adjusted-price strategy: higher risk of look-ahead mistakes in v1.

## 5. File-Level Plan

### Create
- `packages/compute/app/data/akshare.py`
- `packages/compute/app/data/factory.py`
- `packages/compute/scripts/init_security_master.py`
- `packages/compute/scripts/fetch_full_history.py`
- `packages/compute/scripts/load_daily_bars.py`
- `packages/compute/scripts/build_full_segments.py`
- `packages/compute/scripts/backfill_full_labels.py`
- `packages/compute/tests/data/test_akshare_source.py`
- `packages/compute/tests/scripts/test_daily_bar_normalization.py`
- `packages/compute/tests/scripts/test_label_backfill.py`

### Modify
- `packages/server/prisma/schema.prisma`
- `packages/compute/app/data/base.py`
- `packages/compute/app/config.py`
- `packages/compute/scripts/full_init.py`
- `packages/compute/scripts/init_db.py`
- `packages/compute/app/core/pipeline/orchestrator.py`
- `packages/compute/pyproject.toml`

## 6. Implementation Tasks

### Task 1: Add stock master persistence

**Files:**
- Modify: `packages/server/prisma/schema.prisma`
- Test: `packages/compute/tests/scripts/test_daily_bar_normalization.py`

**Step 1: Write the failing test**
- Add a test that expects normalized stock metadata to map to a durable canonical symbol and list status.

**Step 2: Run test to verify it fails**
- Run: `cd packages/compute && pytest tests/scripts/test_daily_bar_normalization.py -v`
- Expected: FAIL because stock master normalization helpers do not exist yet.

**Step 3: Write minimal implementation**
- Add `SecurityMaster` model to Prisma.
- Include unique key on `symbol`.
- Include indexes on `listStatus` and `exchange`.

**Step 4: Verify schema compiles**
- Run: `cd packages/server && pnpm prisma validate`
- Expected: schema valid.

**Step 5: Commit**
- Commit message: `feat: add security master model`

### Task 2: Generalize the data-source abstraction

**Files:**
- Modify: `packages/compute/app/data/base.py`
- Create: `packages/compute/app/data/akshare.py`
- Create: `packages/compute/app/data/factory.py`
- Modify: `packages/compute/app/config.py`
- Test: `packages/compute/tests/data/test_akshare_source.py`

**Step 1: Write the failing test**
- Add tests for symbol canonicalization, stock-list fetch shape, and daily-bar mapping shape.

**Step 2: Run test to verify it fails**
- Run: `cd packages/compute && pytest tests/data/test_akshare_source.py -v`
- Expected: FAIL because AKShare source and factory are missing.

**Step 3: Write minimal implementation**
- Extend `DataSource` to support stock list and range history fetch for initialization.
- Add `AKShareDataSource`.
- Add `DATA_SOURCE` config with default `akshare`.
- Add factory selection instead of importing Tushare directly in orchestration code.

**Step 4: Run tests**
- Run: `cd packages/compute && pytest tests/data/test_akshare_source.py -v`
- Expected: PASS.

**Step 5: Commit**
- Commit message: `feat: add akshare data source`

### Task 3: Build the security master initializer

**Files:**
- Create: `packages/compute/scripts/init_security_master.py`
- Modify: `packages/compute/app/data/factory.py`
- Test: `packages/compute/tests/scripts/test_daily_bar_normalization.py`

**Step 1: Write the failing test**
- Add a test that a stock-list payload is transformed into upsert-ready rows for `security_master`.

**Step 2: Run test to verify it fails**
- Run: `cd packages/compute && pytest tests/scripts/test_daily_bar_normalization.py -v`
- Expected: FAIL because the initializer transformation does not exist.

**Step 3: Write minimal implementation**
- Implement stock-universe fetch.
- Persist raw universe snapshot under `packages/compute/data/raw/akshare/universe/`.
- Upsert rows into `security_master`.

**Step 4: Run tests**
- Run: `cd packages/compute && pytest tests/scripts/test_daily_bar_normalization.py -v`
- Expected: PASS.

**Step 5: Commit**
- Commit message: `feat: initialize security master`

### Task 4: Fetch and cache full 10-year history

**Files:**
- Create: `packages/compute/scripts/fetch_full_history.py`
- Modify: `packages/compute/app/data/akshare.py`
- Test: `packages/compute/tests/data/test_akshare_source.py`

**Step 1: Write the failing test**
- Add tests for date-range mapping, raw-file path generation, and empty-response handling.

**Step 2: Run test to verify it fails**
- Run: `cd packages/compute && pytest tests/data/test_akshare_source.py -v`
- Expected: FAIL because range-fetch history support is incomplete.

**Step 3: Write minimal implementation**
- Fetch 10-year history per symbol.
- Save one raw parquet file per symbol.
- Skip symbols already fetched unless `--force` is provided.
- Emit progress logs and a failed-symbol report.

**Step 4: Run tests**
- Run: `cd packages/compute && pytest tests/data/test_akshare_source.py -v`
- Expected: PASS.

**Step 5: Commit**
- Commit message: `feat: cache full a-share history`

### Task 5: Normalize and bulk-load daily bars

**Files:**
- Create: `packages/compute/scripts/load_daily_bars.py`
- Modify: `packages/compute/app/config.py`
- Test: `packages/compute/tests/scripts/test_daily_bar_normalization.py`

**Step 1: Write the failing test**
- Add tests for canonical symbol format, ascending date order, duplicate removal, and null-safe numeric conversion.

**Step 2: Run test to verify it fails**
- Run: `cd packages/compute && pytest tests/scripts/test_daily_bar_normalization.py -v`
- Expected: FAIL because the normalizer and loader do not exist.

**Step 3: Write minimal implementation**
- Read cached raw files.
- Normalize to `daily_bar` rows.
- Load into a staging table.
- Upsert into `daily_bar` using bulk SQL.

**Step 4: Run tests**
- Run: `cd packages/compute && pytest tests/scripts/test_daily_bar_normalization.py -v`
- Expected: PASS.

**Step 5: Commit**
- Commit message: `feat: bulk load normalized daily bars`

### Task 6: Build full segment and vector initialization

**Files:**
- Create: `packages/compute/scripts/build_full_segments.py`
- Modify: `packages/compute/scripts/init_db.py`
- Modify: `packages/compute/scripts/full_init.py`
- Modify: `packages/compute/app/core/pipeline/orchestrator.py`
- Test: `packages/compute/tests/scripts/test_daily_bar_normalization.py`

**Step 1: Write the failing test**
- Add tests that a 60-bar series produces one correct segment, one vector, and one pending label placeholder.

**Step 2: Run test to verify it fails**
- Run: `cd packages/compute && pytest tests/scripts/test_daily_bar_normalization.py -v`
- Expected: FAIL because the full-history builder does not exist.

**Step 3: Write minimal implementation**
- Read symbol histories from `daily_bar`.
- Batch-generate 60-day windows.
- Insert `segment_index`, `segment_feature`, and pending `segment_future_label` rows.
- Ensure HNSW index creation is optional and disabled during the bulk load phase.

**Step 4: Run tests**
- Run: `cd packages/compute && pytest tests/scripts/test_daily_bar_normalization.py -v`
- Expected: PASS.

**Step 5: Commit**
- Commit message: `feat: build full historical segments`

### Task 7: Backfill future labels with trading-day offsets

**Files:**
- Create: `packages/compute/scripts/backfill_full_labels.py`
- Modify: `packages/compute/app/core/pipeline/orchestrator.py`
- Test: `packages/compute/tests/scripts/test_label_backfill.py`

**Step 1: Write the failing test**
- Add tests for 20-trading-day return calculation, `na` status on insufficient future data, and no calendar-day shortcuts.

**Step 2: Run test to verify it fails**
- Run: `cd packages/compute && pytest tests/scripts/test_label_backfill.py -v`
- Expected: FAIL because the historical backfill job does not exist.

**Step 3: Write minimal implementation**
- Query pending labels in chunks.
- Resolve future bars from `daily_bar` ordered by trade date.
- Compute the label metrics.
- Mark insufficient-history segments as `na`.

**Step 4: Run tests**
- Run: `cd packages/compute && pytest tests/scripts/test_label_backfill.py -v`
- Expected: PASS.

**Step 5: Commit**
- Commit message: `feat: backfill historical future labels`

### Task 8: Add operator runbook and full verification path

**Files:**
- Modify: `packages/compute/scripts/full_init.py`
- Create: `docs/plans/2026-03-07-a-share-history-init-runbook.md`

**Step 1: Write the failing verification checklist**
- Document the end-to-end commands and the expected row-count invariants.

**Step 2: Add orchestration entrypoints**
- Make `full_init.py` call the new stages in order.
- Allow stage-by-stage execution flags for replay and recovery.

**Step 3: Run verification**
- Run schema validation, targeted unit tests, and one small-symbol dry run.
- Expected invariants:
  - `security_master` row count > 4000
  - `daily_bar` row count is non-zero and increasing with history load
  - `segment_feature` row count equals `segment_index` row count for `v1`
  - `segment_future_label` status distribution contains `filled` and maybe `na`, but not all `pending`

**Step 4: Commit**
- Commit message: `docs: add historical init runbook`

## 7. Operational Run Order

Use this run order for the first full initialization:
1. `pnpm --filter server prisma db push`
2. `python packages/compute/scripts/init_security_master.py`
3. `python packages/compute/scripts/fetch_full_history.py --start 2016-01-01 --end 2026-03-06`
4. `python packages/compute/scripts/load_daily_bars.py`
5. `python packages/compute/scripts/full_init.py --skip-hnsw`
6. `python packages/compute/scripts/backfill_full_labels.py`
7. `python packages/compute/scripts/init_db.py --build-hnsw-only`

## 8. Idempotency, Recovery, And Validation Rules

### Idempotency rules
- `security_master` upserts on `symbol`.
- `daily_bar` upserts on `(symbol, trade_date)`.
- `segment_index` upserts on `(symbol, end_date, window_size, feature_version)`.
- `segment_feature` upserts on `segment_id`.
- `segment_future_label` upserts on `segment_id`.

### Recovery rules
- Any failed symbol fetch is written to a retry file.
- Any failed load batch is logged with batch boundaries.
- Raw snapshots remain the source of replay for the load stage.
- Segment build and label backfill must support `--symbols-file` or `--start-symbol` style partial replay.

### Validation rules
- Daily bars must be strictly ascending per symbol.
- No duplicate `(symbol, trade_date)` keys.
- No segment without exactly 60 bars.
- No feature row without matching `segment_index`.
- Label backfill must use trading-day count, not natural-day count.

## 9. Recommended Follow-up After This Plan
- Refactor `run_eod.py` and `PipelineOrchestrator` to use the new data-source factory.
- Add a small benchmark dataset for local performance checks.
- Introduce adjusted-price support as `v2` only after the non-adjusted pipeline is stable.

Plan complete and saved to `docs/plans/2026-03-07-a-share-history-initialization.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
