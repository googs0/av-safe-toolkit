#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------------------------
# AV-SAFE: purge_secret.sh
# History rewrite to remove secret files and/or redact matching patterns.
#
# Usage:
#   tools/purge_secret.sh \
#     [--branch main] \
#     [--paths "secrets/*.json,*.pem"] \
#     [--pattern "AKIA[0-9A-Z]{16}"] \
#     [--replace-file path/to/replace.txt] \
#     [--yes] [--dry-run]
#
# Notes:
#  - Run LOCALLY, not in CI.
#  - Rotate secrets at the provider after running this.
#  - Collaborators must reclone or hard reset after force-push.
#  - Requires: git-filter-repo  (https://github.com/newren/git-filter-repo)
# ------------------------------------------------------------------------------

err() { printf "ERROR: %s\n" "$*" >&2; exit 1; }
note() { printf ">>> %s\n" "$*"; }

# ---- deps --------------------------------------------------------------------
command -v git >/dev/null || err "git is required"
command -v git-filter-repo >/dev/null || err "Install git-filter-repo first"

# ---- defaults ----------------------------------------------------------------
BRANCH_DEFAULT="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||' || true)"
BRANCH="${BRANCH_DEFAULT:-main}"
PATHS=""
PATTERN=""
REPLACE_FILE=""
YES="false"
DRY="false"

# ---- args --------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch)       BRANCH="${2:-}"; shift 2 ;;
    --paths)        PATHS="${2:-}"; shift 2 ;;
    --pattern)      PATTERN="${2:-}"; shift 2 ;;
    --replace-file) REPLACE_FILE="${2:-}"; shift 2 ;;
    --yes)          YES="true"; shift ;;
    --dry-run)      DRY="true"; shift ;;
    -h|--help)
      cat <<'USAGE'
Usage:
  tools/purge_secret.sh [options]

Options:
  --branch <name>           Branch to force-push (default: detected origin/HEAD or 'main')
  --paths  "<glob,glob>"    Comma-separated path globs to *remove* from history
  --pattern "<regex>"       Regex to redact (content rewrite) across history
  --replace-file <path>     git-filter-repo --replace-text file (one rule per line)
  --yes                     Skip interactive confirmation
  --dry-run                 Show plan; do not rewrite or push

Examples:
  # Remove .pem files and redact AWS keys:
  tools/purge_secret.sh --paths "*.pem" --pattern "AKIA[0-9A-Z]{16}"

  # Use a replace map file (supports many rules):
  tools/purge_secret.sh --replace-file tools/replace_rules.txt
USAGE
      exit 0;;
    *)
      err "Unknown option: $1"
      ;;
  esac
done

# Must specify at least one action
if [[ -z "$PATHS" && -z "$PATTERN" && -z "$REPLACE_FILE" ]]; then
  err "Provide at least one of: --paths, --pattern, --replace-file"
fi

# ---- safety checks -----------------------------------------------------------
# Working tree must be clean
if ! git diff-index --quiet HEAD --; then
  err "Working tree not clean. Commit or stash changes first."
fi

# Ensure branch exists locally
if ! git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  note "Local branch '$BRANCH' not found; creating from origin/$BRANCH"
  git fetch origin "$BRANCH" || true
  git checkout -B "$BRANCH" "origin/$BRANCH" 2>/dev/null || git checkout -B "$BRANCH"
fi

# ---- backup ------------------------------------------------------------------
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="../$(basename "$(pwd)")-mirror-backup-$TS.git"
note "Creating MIRROR backup at: $BACKUP_DIR"
if [[ "$DRY" == "false" ]]; then
  git clone --mirror . "$BACKUP_DIR"
else
  note "[dry-run] would: git clone --mirror . $BACKUP_DIR"
fi

# ---- confirmation ------------------------------------------------------------
note "Plan:"
[[ -n "$PATHS" ]]        && note " - Remove paths: $PATHS"
[[ -n "$PATTERN" ]]      && note " - Redact regex: $PATTERN"
[[ -n "$REPLACE_FILE" ]] && note " - Replace-text file: $REPLACE_FILE"
note " - Rewrite all branches & tags; force-push to 'origin/$BRANCH'"

if [[ "$YES" != "true" ]]; then
  read -r -p "Proceed with history rewrite? (yes/NO) " ans
  [[ "$ans" == "yes" ]] || err "Aborted."
fi

# ---- build filter-repo args --------------------------------------------------
ARGS=( )
# Rewrite all refs (heads & tags)
ARGS+=( --refs "refs/heads/*" --tag-rename : )

# Remove paths (comma-separated -> multiple --path-glob)
if [[ -n "$PATHS" ]]; then
  IFS=',' read -r -a _paths <<< "$PATHS"
  for p in "${_paths[@]}"; do
    ARGS+=( --path-glob "$p" --invert-paths )
  done
fi

# Replace text (regex redaction)
TMP_REPLACE=""
if [[ -n "$PATTERN" ]]; then
  TMP_REPLACE="$(mktemp)"
  printf 'regex:%s==>REMOVED\n' "$PATTERN" > "$TMP_REPLACE"
  ARGS+=( --replace-text "$TMP_REPLACE" )
fi

if [[ -n "$REPLACE_FILE" ]]; then
  [[ -f "$REPLACE_FILE" ]] || err "--replace-file not found: $REPLACE_FILE"
  ARGS+=( --replace-text "$REPLACE_FILE" )
fi

# ---- rewrite -----------------------------------------------------------------
if [[ "$DRY" == "true" ]]; then
  note "[dry-run] would run: git filter-repo ${ARGS[*]}"
else
  note "Running git filter-repo ..."
  git filter-repo "${ARGS[@]}"
fi

# ---- GC & push ---------------------------------------------------------------
if [[ "$DRY" == "false" ]]; then
  note "Expiring reflogs & GC ..."
  git reflog expire --expire-unreachable=now --all || true
  git gc --prune=now --aggressive || true

  note "Force-pushing rewritten history to origin/$BRANCH"
  git push --force --tags origin "$BRANCH"
else
  note "[dry-run] would force-push to origin/$BRANCH and tags"
fi

# ---- cleanup -----------------------------------------------------------------
[[ -n "$TMP_REPLACE" && -f "$TMP_REPLACE" ]] && rm -f "$TMP_REPLACE"

cat <<EON

DONE.

Next steps:
 1) **Rotate** the exposed token/key at the provider (GitHub/AWS/GCP/etc).
 2) Ask collaborators to reclone OR run:
      git fetch --all
      git reset --hard origin/$BRANCH
 3) Invalidate any derived credentials (PATs, deploy keys) if applicable.

Backup mirror saved at:
  $BACKUP_DIR
EON
