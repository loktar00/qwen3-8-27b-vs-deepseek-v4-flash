#!/usr/bin/env bash
# sync_results.sh — re-copy the latest scored results into this repo and push.
#
# Idempotent: safe to re-run any time. Run after batches of scored jobs finish
# to refresh docs/ (the built scoreboard), runs/, calibration/, and answer-keys/.
#
# Source of truth lives outside this repo, in the private working tree at
# D:\dev\ab-tasks. This script never touches D:\devNewman (company-confidential)
# and never copies deeweb run data beyond what's already committed here.

set -euo pipefail

SRC="D:/dev/ab-tasks"
DST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Syncing results from $SRC into $DST ..."

# --- docs/ (built site) ---
rm -rf "$DST/docs"
mkdir -p "$DST/docs"
cp -r "$SRC/_site/." "$DST/docs/"

# --- runs/ (all tasks except deeweb*) ---
mkdir -p "$DST/runs/_matrix"
cp "$SRC/_runs/_matrix/status.tsv" "$DST/runs/_matrix/"
for d in "$SRC/_runs"/*/; do
  t="$(basename "$d")"
  case "$t" in
    _matrix) continue ;;
    calibration) continue ;;
    deeweb*) echo "  skipping excluded task dir: $t"; continue ;;
  esac
  mkdir -p "$DST/runs/$t"
  rsync -a --delete \
    --exclude 'worktree*/' \
    --exclude 'node_modules/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    "$d" "$DST/runs/$t/"
done

# --- calibration/ ---
rm -rf "$DST/calibration"
mkdir -p "$DST/calibration"
rsync -a --exclude '__pycache__/' --exclude '*.pyc' "$SRC/_runs/calibration/." "$DST/calibration/"

# --- answer-keys/ (keep our own README.md, refresh the rest) ---
rsync -a --exclude 'README.md' "$SRC/_hidden/." "$DST/answer-keys/"

echo "Sync complete. Reviewing git status..."
cd "$DST"
git add -A

if git diff --cached --quiet; then
  echo "No changes to commit."
  exit 0
fi

git commit -m "results sync $(date -u +%FT%TZ)"
git push

CHANGED=$(git diff --stat HEAD~1 HEAD | tail -1)
echo "Pushed. $CHANGED"
