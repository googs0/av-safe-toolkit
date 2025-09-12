#!/usr/bin/env bash
set -euo pipefail

if ! command -v git-filter-repo >/dev/null 2>&1; then
  echo "Please install git-filter-repo: https://github.com/newren/git-filter-repo" >&2
  exit 1
fi

PATTERN="${1:-}"
BRANCH="${2:-main}"
if [[ -z "$PATTERN" ]]; then
  echo "Usage: tools/purge_secret.sh <grep-pattern-or-file-path> [branch]" >&2
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

backup="../$(basename "$repo_root")-backup-$(date +%s)"
echo ">>> Backing up current repo to $backup"
cp -a . "$backup"

echo ">>> Rewriting history to remove: $PATTERN"
set +e
git filter-repo --path-glob "$PATTERN" --invert-paths
if [[ $? -ne 0 ]]; then
  set -e
  git filter-repo --replace-text <(echo "regex:$PATTERN==>REMOVED")
fi

echo ">>> Force-pushing rewritten history to origin/$BRANCH"
git push --force origin "$BRANCH"

cat <<'EON'
>>> NEXT STEPS:
1) Rotate the exposed key/token at its provider (GitHub/AWS/GCP/etc).
2) Ask collaborators to reclone or run:
     git fetch --all && git reset --hard origin/<branch>
3) Invalidate any derived tokens/keys if applicable.
EON
