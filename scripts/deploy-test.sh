#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="kei"
REMOTE_DIR="/root/repos/insight-mirror-test"
REPO_URL="git@github.com:zhoux0130/InsightMirror.git"
BRANCH="${1:-feat/260313}"
EPORT="${EPORT:-9001}"
TEST_URL="https://t1.upivot.io"

echo "==> Deploying InsightMirror (test) to ${REMOTE_HOST}:${REMOTE_DIR}"
echo "    Branch: ${BRANCH}  Port: ${EPORT} -> ${TEST_URL}"

ssh "${REMOTE_HOST}" bash -s <<EOF
  set -euo pipefail

  # First-time setup: clone if dir doesn't exist
  if [ ! -d "${REMOTE_DIR}" ]; then
    echo "--- cloning repo"
    git clone "${REPO_URL}" "${REMOTE_DIR}"
  fi

  cd "${REMOTE_DIR}"

  echo "--- git fetch & checkout ${BRANCH}"
  git fetch --all
  git checkout "${BRANCH}"
  git pull origin "${BRANCH}"

  echo "--- docker compose build"
  EPORT=${EPORT} docker compose -f docker-compose.yml -f docker-compose.test.yml build

  echo "--- docker compose up -d (EPORT=${EPORT})"
  EPORT=${EPORT} docker compose -f docker-compose.yml -f docker-compose.test.yml up -d

  echo "--- docker compose ps"
  EPORT=${EPORT} docker compose -f docker-compose.yml -f docker-compose.test.yml ps
EOF

echo "==> Deploy complete: ${TEST_URL}"
