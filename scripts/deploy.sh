#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="root@kei.upivot.io"
REMOTE_DIR="/root/repos/insight-mirror"

echo "==> Deploying InsightMirror to ${REMOTE_HOST}:${REMOTE_DIR}"

ssh "${REMOTE_HOST}" bash -s <<EOF
  set -euo pipefail
  cd "${REMOTE_DIR}"

  echo "--- git pull"
  git pull

  echo "--- docker compose build"
  docker compose build

  echo "--- docker compose up -d"
  docker compose up -d

  echo "--- docker compose ps"
  docker compose ps
EOF

echo "==> Deploy complete"
