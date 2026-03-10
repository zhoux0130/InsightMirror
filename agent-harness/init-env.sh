#!/bin/bash
set -e

if [ -z "$1" ]; then
  echo "Usage: ./init-env.sh <branch-name> [frontend|backend|other]"
  echo "Examples:"
  echo "  ./init-env.sh feature/task-1           # All repos"
  echo "  ./init-env.sh feature/task-1 frontend   # Only frontend"
  echo "  ./init-env.sh feature/task-1 backend   # Only backend"
  echo "  ./init-env.sh feature/task-1 other   # Only other"
  exit 1
fi

BRANCH_NAME="$1"
SCOPE="$2"
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

case "$SCOPE" in
  frontend) REPOS=("web") ;;
  backend) REPOS=("server") ;;
  other) REPOS=("compute") ;;
  "") REPOS=("web" "server" "compute" );;
  *)
    echo "❌ Invalid argument: $SCOPE"
    exit 1
    ;;
esac

for repo in "${REPOS[@]}"; do
  REPO_DIR="$BASE_DIR/$repo"

  if [ ! -d "$REPO_DIR" ]; then
    echo "❌ Repo not found: $REPO_DIR"
    exit 1
  fi

  echo "========== $repo =========="
  cd "$REPO_DIR"

  if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
    echo "📌 Branch $BRANCH_NAME exists, switching and merging latest master"
    git checkout "$BRANCH_NAME"
    git fetch origin master
    git merge origin/master -m "merge latest master into $BRANCH_NAME"
  else
    echo "🆕 Creating branch $BRANCH_NAME (from latest master)"
    git checkout master
    git pull origin master
    git checkout -b "$BRANCH_NAME"
  fi

  echo "✅ $repo -> branch $BRANCH_NAME"
  echo ""
done

echo "🎉 Done! All repos on branch: $BRANCH_NAME"
