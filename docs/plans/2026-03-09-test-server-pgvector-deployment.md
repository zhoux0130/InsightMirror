# Test Server Pgvector Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy the InsightMirror test environment on a server with PostgreSQL + pgvector, then verify that the application stack can read and write vector data correctly.

**Architecture:** Use the existing `docker-compose.yml` as the single source of truth. The database is not a separate vector database service; it is PostgreSQL with the `pgvector` extension enabled through the `pgvector/pgvector:pg16` image. Start PostgreSQL first, initialize the `vector` extension and schema, then start `compute`, `server`, and `web`.

**Tech Stack:** Docker Compose, PostgreSQL 16, pgvector, Prisma, Fastify, React/Vite, Python 3.11, AKShare.

## Assumptions

- The server can run Docker and Docker Compose.
- The code is deployed to a directory such as `/opt/InsightMirror`.
- Test traffic is acceptable on a single-node deployment.
- The PostgreSQL instance is local to this stack, not a managed cloud database.
- If a managed PostgreSQL service is used instead, it must support `CREATE EXTENSION vector`.

## Ports

- `80`: web
- `3000`: server inside compose network
- `8000`: compute inside compose network
- `5432`: postgres inside compose network

## Files To Prepare

- `docker-compose.yml`
- `.env`
- Optional: `scripts/deploy.sh`

## Task 1: Prepare The Server

**Files:**
- Verify: `/opt/InsightMirror/docker-compose.yml`
- Create: `/opt/InsightMirror/.env`

**Step 1: Install Docker and Compose**

Run:

```bash
docker --version
docker compose version
```

Expected:
- Both commands succeed.

**Step 2: Create application directory**

Run:

```bash
mkdir -p /opt/InsightMirror
cd /opt/InsightMirror
```

Expected:
- Target directory exists and is writable.

**Step 3: Upload or pull the repository**

Run one of:

```bash
git clone <your-repo-url> /opt/InsightMirror
```

or

```bash
cd /opt/InsightMirror
git pull
```

Expected:
- Repository files are present, including `docker-compose.yml`.

**Step 4: Create `.env`**

Template:

```bash
NODE_ENV=production
PORT=3000
EPORT=80

POSTGRES_USER=insightmirror
POSTGRES_PASSWORD=replace-with-strong-password
POSTGRES_DB=insightmirror

DATABASE_URL=postgresql://insightmirror:replace-with-strong-password@postgres:5432/insightmirror

WEB_SECRET=replace-with-32-char-secret-aaaaaaaa
APP_SECRET=replace-with-32-char-secret-bbbbbbbb
JWT_SECRET=replace-with-32-char-secret-cccccccc
JWT_EXPIRES_IN=7d

COMPUTE_SERVICE_URL=http://compute:8000
COMPUTE_PORT=8000
DATA_SOURCE=akshare
RAW_DATA_DIR=data/raw
HISTORY_START_DATE=2016-01-01
HISTORY_END_DATE=2026-03-06
HISTORY_ADJUST=
```

Expected:
- `.env` exists in the project root.

## Task 2: Start PostgreSQL With pgvector

**Files:**
- Verify: `/opt/InsightMirror/docker-compose.yml`

**Step 1: Start only PostgreSQL**

Run:

```bash
cd /opt/InsightMirror
docker compose up -d postgres
```

Expected:
- `postgres` container starts and becomes healthy.

**Step 2: Verify container health**

Run:

```bash
docker compose ps
```

Expected:
- `postgres` shows `healthy`.

**Step 3: Verify the database is reachable**

Run:

```bash
docker compose exec postgres psql -U insightmirror -d insightmirror -c "select 1;"
```

Expected:
- Returns `1`.

## Task 3: Initialize pgvector And Application Schema

**Files:**
- Verify: `packages/compute/scripts/init_db.py`
- Verify: `packages/server/prisma/schema.prisma`

**Step 1: Create the `vector` extension and vector table**

Run:

```bash
cd /opt/InsightMirror
docker compose run --rm compute python -m scripts.init_db --skip-index
```

Expected:
- Output contains `pgvector schema initialized.`

**Step 2: Verify extension installation**

Run:

```bash
docker compose exec postgres psql -U insightmirror -d insightmirror -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

Expected:
- One row: `vector`

**Step 3: Push Prisma schema**

Run:

```bash
cd /opt/InsightMirror
docker compose run --rm server pnpm --filter server db:push
```

Expected:
- Prisma finishes without errors.

**Step 4: Verify vector table**

Run:

```bash
docker compose exec postgres psql -U insightmirror -d insightmirror -c "\d segment_feature"
```

Expected:
- `feature_vector` column exists with type `vector(182)`.

## Task 4: Start Application Services

**Files:**
- Verify: `docker-compose.yml`

**Step 1: Start compute, server, and web**

Run:

```bash
cd /opt/InsightMirror
docker compose up -d compute server web
```

Expected:
- All services start successfully.

**Step 2: Check health**

Run:

```bash
docker compose ps
```

Expected:
- `postgres`, `compute`, `server`, and `web` are all up.

**Step 3: Verify API health**

Run:

```bash
curl -I http://127.0.0.1/api/health
```

Expected:
- HTTP `200` or a valid app response depending on your reverse proxy setup.

## Task 5: Smoke Test Vector Capability

**Files:**
- Verify: `packages/compute/scripts/full_init.py`

**Step 1: Run a single-stock initialization**

Run:

```bash
cd /opt/InsightMirror
docker compose run --rm compute python -m scripts.full_init --symbols 300750.SZ --skip-hnsw
```

Expected:
- `security_master`, `history`, `daily_bar`, `segments`, and `labels` all report successful row counts.

**Step 2: Verify vector rows exist**

Run:

```bash
docker compose exec postgres psql -U insightmirror -d insightmirror -c "SELECT COUNT(*) FROM segment_feature;"
```

Expected:
- Count is greater than `0`.

**Step 3: Verify stock options API**

Run:

```bash
curl -s http://127.0.0.1/api/stocks/options
```

Expected:
- Response includes `300750.SZ`.

## Task 6: Optional HNSW Index Build

**Files:**
- Verify: `packages/compute/scripts/init_db.py`

**Step 1: Build HNSW only after enough data exists**

Run:

```bash
cd /opt/InsightMirror
docker compose run --rm compute python -m scripts.init_db --build-hnsw-only
```

Expected:
- Output contains `HNSW index created.`

**Step 2: Verify the index**

Run:

```bash
docker compose exec postgres psql -U insightmirror -d insightmirror -c "\di idx_segment_feature_hnsw"
```

Expected:
- HNSW index exists.

**Note:**
- Skip this on an empty or very small test dataset.
- Build it after several stocks or after the test seed is loaded.

## Acceptance Checklist

- Docker and Compose installed
- `.env` created with real secrets
- `postgres` started from `pgvector/pgvector:pg16`
- `vector` extension exists
- `segment_feature.feature_vector` uses `vector(182)`
- Prisma schema pushed successfully
- `compute`, `server`, `web` all running
- One stock can be initialized end to end
- `segment_feature` row count is greater than `0`
- `/api/stocks/options` returns initialized symbols

## Troubleshooting

### Problem: `CREATE EXTENSION vector` fails

Likely cause:
- You are not using the `pgvector/pgvector` image or your managed PostgreSQL does not support `pgvector`.

Fix:
- Switch to `pgvector/pgvector:pg16`
- Or use a managed PostgreSQL service that explicitly supports `vector`

### Problem: Prisma works but vector search fails

Likely cause:
- Prisma tables exist, but `segment_feature` or the `vector` extension was never initialized.

Fix:

```bash
docker compose run --rm compute python -m scripts.init_db --skip-index
```

### Problem: stock dropdown is empty

Likely cause:
- Stocks were not fully initialized through `segment_index` and `segment_feature`.

Fix:

```bash
docker compose run --rm compute python -m scripts.full_init --symbols 300750.SZ --skip-hnsw
```

### Problem: HNSW build is slow

Likely cause:
- Building index before data size justifies it.

Fix:
- Skip HNSW in early test environments
- Build it after the test dataset is stable
