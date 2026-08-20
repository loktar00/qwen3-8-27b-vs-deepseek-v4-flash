#!/usr/bin/env bash
# sync_results.sh — re-copy the latest scored/allowed results into this repo and push.
#
# Safe to call frequently and from multiple concurrent callers (e.g. post_result.sh
# after every scored job): uses an atomic mkdir-based lock, so a second concurrent
# invocation skips instead of racing (a lock older than STALE_SECS is treated as
# abandoned and taken over). Only commits+pushes when `git status --porcelain` is
# actually non-empty after syncing.
#
# This environment has no `rsync`/`flock` (plain Git-for-Windows Git Bash), so
# mirroring uses Windows' built-in `robocopy` instead — see robomirror() below for
# the exit-code handling that makes that safe to call without tripping `set -e`.
#
# Source of truth lives outside this repo, in the private working tree at
# D:\dev\ab-tasks (and D:\dev\style-pilot\labs\qwen38-day0\ab for methodology).
# This script never touches D:\devNewman (company-confidential) and never copies
# deeweb run data beyond what's already committed here.
#
# IMPORTANT: this script intentionally never touches tasks/ (and specifically
# never re-copies tasks/deeweb/*). Those files were hand-scrubbed of local
# paths/setup notes before publish — do not add a tasks/ sync step that would
# overwrite that scrubbed copy from the raw _briefs/ source.
#
# Output contract: every other message goes to stderr; stdout carries exactly one
# final line: "synced: <short-sha>" | "synced: skipped (<reason>)" | "synced: failed (<reason>)".

set -uo pipefail

# Git-for-Windows/MSYS rewrites bare "/X" args (like robocopy's /MIR, /XD) as POSIX
# paths before exec'ing native Win32 tools. This disables that heuristic for every
# command this script runs, which is required for every robocopy call below.
export MSYS_NO_PATHCONV=1

SRC="D:/dev/ab-tasks"
AB="D:/dev/style-pilot/labs/qwen38-day0/ab"
DST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCKDIR="$DST/.sync.lock"
STALE_SECS=600

log() { echo "[sync_results] $*" >&2; }

fail() {
  echo "synced: failed ($1)"
  exit 1
}

# --- concurrency guard: atomic mkdir lock, stale-takeover after STALE_SECS ---
acquire_lock() {
  if mkdir "$LOCKDIR" 2>/dev/null; then
    echo $$ > "$LOCKDIR/pid"
    return 0
  fi
  if [ -f "$LOCKDIR/pid" ]; then
    local mtime age
    mtime="$(stat -c %Y "$LOCKDIR/pid" 2>/dev/null || echo 0)"
    age=$(( $(date +%s) - mtime ))
    if [ "$age" -gt "$STALE_SECS" ]; then
      log "stale lock (age ${age}s) -- taking over"
      rm -rf "$LOCKDIR"
      if mkdir "$LOCKDIR" 2>/dev/null; then
        echo $$ > "$LOCKDIR/pid"
        return 0
      fi
    fi
  fi
  return 1
}

if ! acquire_lock; then
  echo "synced: skipped (lock held by another sync)"
  exit 0
fi
trap 'rm -rf "$LOCKDIR"' EXIT

# --- robocopy wrapper: robocopy's own "success" exit codes are 0-7 (bitflags for
# what it did), only >=8 means real failure. Wrap so callers can treat this like
# any other command returning 0/1 under set -o pipefail without robocopy's normal
# nonzero-on-success codes tripping anything. /MIR mirrors (deletes dst extras),
# so only use robomirror on dirs with no hand-authored files worth protecting. ---
robomirror() {
  local src="$1" dst="$2"; shift 2
  local rc=0
  mkdir -p "$dst"
  robocopy "$src" "$dst" /MIR /NFL /NDL /NJH /NJS /NP "$@" >/dev/null 2>&1
  rc=$?
  [ "$rc" -ge 8 ] && return 1
  return 0
}

# Same as robomirror but non-mirroring (no deletion of dst extras) -- for dirs
# where we keep a hand-written file (e.g. a README.md) alongside synced content.
robocopy_update() {
  local src="$1" dst="$2"; shift 2
  local rc=0
  mkdir -p "$dst"
  robocopy "$src" "$dst" /E /NFL /NDL /NJH /NJS /NP "$@" >/dev/null 2>&1
  rc=$?
  [ "$rc" -ge 8 ] && return 1
  return 0
}

log "syncing from $SRC ..."

# --- docs/ (built site) ---
robomirror "$SRC/_site" "$DST/docs" || fail "docs copy"

# --- methodology/ (individual files, not a directory mirror) ---
mkdir -p "$DST/methodology"
cp -f "$AB/METHODOLOGY.md" "$AB/SCORING.md" "$AB/calibration.md" "$AB/method.html" "$DST/methodology/" \
  || fail "methodology copy"

# --- raptor-support/ (reference + checks only; keep our own README.md) ---
robomirror "$SRC/_raptor-support/reference" "$DST/raptor-support/reference" || fail "raptor-support/reference copy"
robomirror "$SRC/_raptor-support/checks" "$DST/raptor-support/checks" /XD __pycache__ /XF "*.pyc" \
  || fail "raptor-support/checks copy"
cp -f "$SRC/_raptor-support/GLB-FORMAT.md" "$SRC/_raptor-support/brief-draft.md" "$DST/raptor-support/" \
  || fail "raptor-support docs copy"

# --- runs/ (all tasks except deeweb*, and except the _matrix/calibration pseudo-tasks) ---
mkdir -p "$DST/runs/_matrix"
cp -f "$SRC/_runs/_matrix/status.tsv" "$DST/runs/_matrix/" || fail "matrix status.tsv copy"
for d in "$SRC/_runs"/*/; do
  t="$(basename "$d")"
  case "$t" in
    _matrix) continue ;;
    calibration) continue ;;
    deeweb*) log "skipping excluded task dir: $t"; continue ;;
  esac
  robomirror "$d" "$DST/runs/$t" /XD "worktree*" node_modules __pycache__ /XF "*.pyc" \
    || fail "runs/$t copy"
done

# --- calibration/ ---
robomirror "$SRC/_runs/calibration" "$DST/calibration" /XD __pycache__ /XF "*.pyc" || fail "calibration copy"

# --- answer-keys/ (keep our own README.md, refresh the rest, no deletion) ---
robocopy_update "$SRC/_hidden" "$DST/answer-keys" /XF README.md || fail "answer-keys copy"

log "sync complete, checking git status..."
cd "$DST" || fail "cd to repo"

# Release the lock before staging so .sync.lock/ is never present for `git add -A`
# to pick up (the EXIT trap still covers early-failure paths above this point).
rm -rf "$LOCKDIR"
trap - EXIT

git add -A || fail "git add"
CHANGES="$(git status --porcelain)"

if [ -z "$CHANGES" ]; then
  echo "synced: skipped (no changes)"
  exit 0
fi

git commit -q -m "results sync $(date -u +%FT%TZ)" || fail "git commit"
git push -q || fail "git push"

SHA="$(git rev-parse --short HEAD)"
echo "synced: $SHA"
