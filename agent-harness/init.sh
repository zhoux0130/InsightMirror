#!/bin/bash

# =============================================================================
# init.sh - InsightMirror Environment Initialization
# =============================================================================
# Run at the start of each agent session to ensure the dev environment is ready.
# =============================================================================

HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$HARNESS_ROOT")"
RUNTIME_DIR="$HARNESS_ROOT/.runtime"

WEB_DIR="$PROJECT_ROOT/packages/web/"
SERVER_DIR="$PROJECT_ROOT/packages/server/"
COMPUTE_DIR="$PROJECT_ROOT/packages/compute/"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}$1${NC}"; }
ok()    { echo -e "${GREEN}✓ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠ $1${NC}"; }
fail()  { echo -e "${RED}✗ $1${NC}"; }

port_in_use() {
  lsof -iTCP:"$1" -sTCP:LISTEN -t &>/dev/null
}

echo -e "${YELLOW}Initializing InsightMirror Agent Harness...${NC}"
echo ""

# =============================================================================
# 1. Check repo directories
# =============================================================================
info "--- Checking project directories ---"

if [ ! -d "$WEB_DIR" ]; then
  fail "web/ not found: $WEB_DIR"
  exit 1
fi
ok "web/ ready"

if [ ! -d "$SERVER_DIR" ]; then
  fail "server/ not found: $SERVER_DIR"
  exit 1
fi
ok "server/ ready"

if [ ! -d "$COMPUTE_DIR" ]; then
  fail "compute/ not found: $COMPUTE_DIR"
  exit 1
fi
ok "compute/ ready"

echo ""
info "--- Local harness bootstrap ---"
"$PROJECT_ROOT/scripts/setup-local-agent-harness.sh" || warn "Local agent harness bootstrap skipped"

# =============================================================================
# 2. Prepare runtime directory (screenshots, logs, session data)
# =============================================================================
info "--- Preparing runtime directory ---"

# Clean previous session data, keep the dir
rm -rf "$RUNTIME_DIR"
mkdir -p "$RUNTIME_DIR/screenshots"
mkdir -p "$RUNTIME_DIR/logs"

# Export env vars for agent and scripts to use
export AGENT_RUNTIME_DIR="$RUNTIME_DIR"
export AGENT_SCREENSHOTS_DIR="$RUNTIME_DIR/screenshots"
export AGENT_LOGS_DIR="$RUNTIME_DIR/logs"

ok "Runtime dir: $RUNTIME_DIR"
ok "  screenshots/ — browser test screenshots"
ok "  logs/        — build & lint logs"

# Session metadata
cat > "$RUNTIME_DIR/session-info.json" <<EOF
{
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "node_version": "$(node -v 2>/dev/null || echo N/A)",
  "directories": {
    "screenshots": "$RUNTIME_DIR/screenshots",
    "logs": "$RUNTIME_DIR/logs"
  }
}
EOF

# Test report template
cat > "$RUNTIME_DIR/test-report.md" <<'REPORT_EOF'
# Test Report

## Session Info
- Start time: PLACEHOLDER_TIME
- Task: (to be filled)

## Test Steps

| # | Step | Type | Result | Screenshot/Log | Notes |
|---|------|------|--------|----------------|-------|
| 1 | -    | -    | -      | -              | -     |

## Build Verification
- [ ] `pnpm --filter web build` passes
- [ ] `pnpm --filter server lint` passes
- [ ] `pnpm --filter server build` passes
- [ ] `cd packages/compute &amp;&amp; python -m pytest tests/` passes

## Browser Tests
- [ ] Page loads correctly
- [ ] Interactions work
- [ ] Screenshots saved

## Conclusion
- Status: PENDING
- Notes: (to be filled)
REPORT_EOF

sed -i '' "s/PLACEHOLDER_TIME/$(date '+%Y-%m-%d %H:%M:%S')/" "$RUNTIME_DIR/test-report.md" 2>/dev/null || \
sed -i "s/PLACEHOLDER_TIME/$(date '+%Y-%m-%d %H:%M:%S')/" "$RUNTIME_DIR/test-report.md" 2>/dev/null

ok "test-report.md template generated"

# =============================================================================
# 1. web setup
# =============================================================================
echo ""
info "--- web (frontend) ---"

# Check Node.js
if ! command -v node &>/dev/null; then
  fail "Node.js not installed"
  exit 1
fi
ok "Node.js $(node -v | sed 's/^v//')"

# Check pnpm
if ! command -v pnpm &>/dev/null; then
  warn "pnpm not found, installing..."
  npm install -g pnpm
fi
ok "pnpm $(pnpm -v)"

cd "$WEB_DIR"
if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  pnpm install --frozen-lockfile 2>/dev/null || pnpm install
  ok "Dependencies installed"
else
  ok "Dependencies up to date"
fi



if port_in_use 5173; then
  ok "Dev server already running (port 5173)"
else
  echo "Starting dev server..."
  cd "$WEB_DIR"
  nohup pnpm --filter web dev > "$RUNTIME_DIR/logs/web-dev.log" 2>&1 &
  DEV_PID=$!
  echo -n "Waiting for dev server"
  for i in $(seq 1 30); do
    if port_in_use 5173; then
      echo ""
      ok "Dev server started (PID: $DEV_PID, port 5173)"
      break
    fi
    echo -n "."
    sleep 1
  done
  if ! port_in_use 5173; then
    echo ""
    warn "Dev server start timeout — check log: $RUNTIME_DIR/logs/web-dev.log"
  fi
fi

cd "$HARNESS_ROOT"

# =============================================================================
# 2. server setup
# =============================================================================
echo ""
info "--- server (backend) ---"

# Check Node.js
if ! command -v node &>/dev/null; then
  fail "Node.js not installed"
  exit 1
fi
ok "Node.js $(node -v | sed 's/^v//')"

# Check pnpm
if ! command -v pnpm &>/dev/null; then
  warn "pnpm not found, installing..."
  npm install -g pnpm
fi
ok "pnpm $(pnpm -v)"

cd "$SERVER_DIR"
if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  pnpm install --frozen-lockfile 2>/dev/null || pnpm install
  ok "Dependencies installed"
else
  ok "Dependencies up to date"
fi



if port_in_use 3000; then
  ok "Dev server already running (port 3000)"
else
  echo "Starting dev server..."
  cd "$SERVER_DIR"
  nohup pnpm --filter server dev > "$RUNTIME_DIR/logs/server-dev.log" 2>&1 &
  DEV_PID=$!
  echo -n "Waiting for dev server"
  for i in $(seq 1 30); do
    if port_in_use 3000; then
      echo ""
      ok "Dev server started (PID: $DEV_PID, port 3000)"
      break
    fi
    echo -n "."
    sleep 1
  done
  if ! port_in_use 3000; then
    echo ""
    warn "Dev server start timeout — check log: $RUNTIME_DIR/logs/server-dev.log"
  fi
fi

cd "$HARNESS_ROOT"

# =============================================================================
# 3. compute setup
# =============================================================================
echo ""
info "--- compute (other) ---"




if port_in_use 8000; then
  ok "Dev server already running (port 8000)"
else
  echo "Starting dev server..."
  cd "$COMPUTE_DIR"
  nohup cd packages/compute && python -m uvicorn app.main:app --reload --port 8000 > "$RUNTIME_DIR/logs/compute-dev.log" 2>&1 &
  DEV_PID=$!
  echo -n "Waiting for dev server"
  for i in $(seq 1 30); do
    if port_in_use 8000; then
      echo ""
      ok "Dev server started (PID: $DEV_PID, port 8000)"
      break
    fi
    echo -n "."
    sleep 1
  done
  if ! port_in_use 8000; then
    echo ""
    warn "Dev server start timeout — check log: $RUNTIME_DIR/logs/compute-dev.log"
  fi
fi

cd "$HARNESS_ROOT"


# =============================================================================
# Summary
# =============================================================================
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Initialization complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "  web: ${GREEN}http://localhost:5173${NC}"
echo -e "  server: ${GREEN}http://localhost:3000${NC}"
echo -e "  compute: ${GREEN}http://localhost:8000${NC}"
echo -e "  Runtime: ${CYAN}$RUNTIME_DIR${NC} (gitignored)"
echo ""
echo "Ready to go."
