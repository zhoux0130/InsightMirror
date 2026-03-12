#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
DEFAULT_HARNESS_DIR="$(cd "$REPO_ROOT/.." && pwd)/agent-harness-kit"
HARNESS_DIR="${AGENT_HARNESS_KIT_DIR:-$DEFAULT_HARNESS_DIR}"

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm not found, skipping local agent harness bootstrap"
  exit 0
fi

if [ ! -f "$HARNESS_DIR/package.json" ]; then
  echo "Local agent-harness-kit not found at $HARNESS_DIR, skipping"
  exit 0
fi

if ! grep -q '"name": "agent-harness-kit"' "$HARNESS_DIR/package.json"; then
  echo "Package at $HARNESS_DIR is not agent-harness-kit, skipping"
  exit 0
fi

if [ ! -f "$HARNESS_DIR/dist/cli.js" ]; then
  echo "Building local agent-harness-kit from $HARNESS_DIR"
  pnpm --dir "$HARNESS_DIR" install --frozen-lockfile >/dev/null 2>&1 || pnpm --dir "$HARNESS_DIR" install >/dev/null
  pnpm --dir "$HARNESS_DIR" build >/dev/null
fi

pnpm --dir "$REPO_ROOT" link "$HARNESS_DIR" >/dev/null
echo "Linked local agent-harness-kit from $HARNESS_DIR"
