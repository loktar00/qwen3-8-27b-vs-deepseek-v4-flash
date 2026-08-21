#!/usr/bin/env bash
# sync_results.sh — re-copy the latest scored/allowed results into this repo and push.
#
# usage:
#   sync_results.sh              copy+commit; push, unless the last push was < 5 min
#                                 ago (debounce), in which case just commit locally
#   sync_results.sh --force      copy+commit+push regardless of the debounce window
#   sync_results.sh --push-now   push any already-committed, not-yet-pushed commits;
#                                 does no copying/committing of its own
#
# Safe to call frequently and from multiple concurrent callers (e.g. post_result.sh
# after every scored job): uses an atomic mkdir-based lock, so a second concurrent
# invocation skips instead of racing (a lock older than STALE_SECS is treated as
# abandoned and taken over). Only commits when `git status --porcelain` is actually
# non-empty after syncing.
#
# Push debounce: pushing on every single scored job (which can be every 1-2 minutes
# under this harness) hammers GitHub Pages' build queue -- one push already caused a
# transient build failure from rapid-fire successive pushes. So a normal invocation
# always does the copy+commit (nothing is ever lost), but skips the push if the last
# successful push was under DEBOUNCE_SECS ago; the commit sits local until either a
# later sync's debounce window has elapsed, or something runs --push-now / --force.
# Last-push time lives in PUSH_STATE, a local dotfile, not committed to the repo.
#
# This environment has no `rsync`/`flock` (plain Git-for-Windows Git Bash), so
# mirroring uses Windows' built-in `robocopy` instead — see robomirror() below for
# the exit-code handling that makes that safe to call without tripping `set -e`.
#
# robocopy is a native Win32 tool: it needs real "D:\..." paths, not the POSIX
# "/d/..." form bash's own `pwd`/`dirname` produce. Both wrappers below convert
# both src and dst through `cygpath -w` right before the robocopy call. Getting
# this wrong is silent, not loud: robocopy given a POSIX-style destination exits
# 1 ("success") having copied zero files — it does not error. So each wrapper
# also does a post-copy sanity check (src has files => dst ends up non-empty)
# and treats a false "success" that copied nothing as a real failure.
#
# Size guard: GitHub rejects any pushed file over 100MB. Both wrappers pass
# robocopy /MAX so it never even copies a file over MAX_FILE_BYTES in the first
# place (cheap, avoids the I/O), and after ALL copying is done there's also a
# full-tree scan (big_file_guard) that deletes and logs anything over the limit
# that slipped through some other way (e.g. a plain `cp` copy, or a file that
# grew between the size check and the push). Belt and suspenders on purpose —
# a rejected push here blocks every future sync until someone notices.
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
# IMPORTANT: every edit to this file must be made via write-new+mv (write the
# new content to sync_results.sh.new, chmod +x, then `mv -f` over this file),
# never edited in place. post_result.sh shells out to this script after every
# scored job, so it can be mid-invocation at any time; an in-place edit risks a
# concurrent caller reading a half-written file.
#
# IMPORTANT: no destructive git operations against this repo, ever -- no reset
# --hard, no force-push, no branch deletion. Comparisons against the remote are
# fetch + diff/log only.
#
# Output contract: every other message goes to stderr; stdout carries exactly one
# final line, one of:
#   "synced: <short-sha>"                          -- committed (if applicable) and pushed
#   "synced: committed, push deferred (debounce)"   -- committed locally, push skipped
#   "synced: skipped (<reason>)"                    -- nothing to do
#   "synced: failed (<reason>)"                     -- see reason

set -uo pipefail

# Git-for-Windows/MSYS rewrites bare "/X" args (like robocopy's /MIR, /XD) as POSIX
# paths before exec'ing native Win32 tools. This disables that heuristic for every
# command this script runs; the wrappers below compensate by converting the actual
# path arguments themselves via cygpath -w, since MSYS won't do it for us anymore.
export MSYS_NO_PATHCONV=1

SRC="D:/dev/ab-tasks"
AB="D:/dev/style-pilot/labs/qwen38-day0/ab"
DST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCKDIR="$DST/.sync.lock"
PUSH_STATE="$DST/.sync-push-state"
STALE_SECS=600
DEBOUNCE_SECS=300
MAX_FILE_BYTES=$((95 * 1024 * 1024))   # 95 MiB; GitHub's hard limit is 100MB

FORCE=0
PUSH_NOW=0
case "${1:-}" in
  --force) FORCE=1 ;;
  --push-now) PUSH_NOW=1 ;;
  "") ;;
  *) echo "synced: failed (unknown argument: $1)"; exit 1 ;;
esac

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

# Pushes whatever is currently committed (caller decides whether that's warranted),
# records the successful-push time for the debounce window, and prints the final
# "synced: ..." line. Never returns on failure -- calls fail(), same as elsewhere.
do_push() {
  local push_out push_rc first_line sha
  push_out="$(git push -q 2>&1)"
  push_rc=$?
  if [ "$push_rc" -ne 0 ]; then
    first_line="$(printf '%s\n' "$push_out" | grep -m1 -E '^(remote: )?error:')"
    [ -z "$first_line" ] && first_line="$(printf '%s\n' "$push_out" | grep -m1 .)"
    fail "git push: ${first_line:-no output}"
  fi
  date +%s > "$PUSH_STATE"
  sha="$(git rev-parse --short HEAD)"
  echo "synced: $sha"
}

# --push-now: no copying, no committing -- just flush whatever's already committed
# locally but not yet on origin/main. Still takes the lock (shares git state with a
# normal sync) and still respects the "no destructive git ops" rule: fetch, compare,
# push -- never reset/force.
if [ "$PUSH_NOW" -eq 1 ]; then
  cd "$DST" || fail "cd to repo"
  git fetch -q origin || fail "git fetch"
  LOCAL_SHA="$(git rev-parse HEAD)"
  REMOTE_SHA="$(git rev-parse origin/main 2>/dev/null || echo "")"
  if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
    echo "synced: skipped (nothing to push)"
    exit 0
  fi
  do_push
  exit 0
fi

# Sanity check: if src has any files, dst must end up with at least one too.
# Catches robocopy "succeeding" (exit <8) while having silently copied nothing
# (e.g. because it was handed a POSIX-style destination it can't write to).
# NOTE: a src dir consisting ENTIRELY of oversized files (all skipped by /MAX)
# would also trip this; that's fine -- it means investigate, not paper over.
verify_copied() {
  local src="$1" dst="$2"
  local src_n dst_n
  src_n="$(find "$src" -type f 2>/dev/null | wc -l)"
  dst_n="$(find "$dst" -type f 2>/dev/null | wc -l)"
  if [ "$src_n" -gt 0 ] && [ "$dst_n" -eq 0 ]; then
    log "VERIFY FAILED: $src has $src_n file(s) but $dst has 0 after copy"
    return 1
  fi
  return 0
}

# --- robocopy wrapper: robocopy's own "success" exit codes are 0-7 (bitflags for
# what it did), only >=8 means real failure. Wrap so callers can treat this like
# any other command returning 0/1 under set -o pipefail without robocopy's normal
# nonzero-on-success codes tripping anything. /MIR mirrors (deletes dst extras),
# so only use robomirror on dirs with no hand-authored files worth protecting.
# /MAX:MAX_FILE_BYTES on every call: never even attempt to copy an oversized file. ---
robomirror() {
  local src="$1" dst="$2"; shift 2
  local rc=0 src_win dst_win
  mkdir -p "$dst"
  src_win="$(cygpath -w "$src" 2>/dev/null || echo "$src")"
  dst_win="$(cygpath -w "$dst" 2>/dev/null || echo "$dst")"
  robocopy "$src_win" "$dst_win" /MIR /MAX:"$MAX_FILE_BYTES" /NFL /NDL /NJH /NJS /NP "$@" >/dev/null 2>&1
  rc=$?
  [ "$rc" -ge 8 ] && return 1
  verify_copied "$src" "$dst" || return 1
  return 0
}

# Same as robomirror but non-mirroring (no deletion of dst extras) -- for dirs
# where we keep a hand-written file (e.g. a README.md) alongside synced content.
robocopy_update() {
  local src="$1" dst="$2"; shift 2
  local rc=0 src_win dst_win
  mkdir -p "$dst"
  src_win="$(cygpath -w "$src" 2>/dev/null || echo "$src")"
  dst_win="$(cygpath -w "$dst" 2>/dev/null || echo "$dst")"
  robocopy "$src_win" "$dst_win" /E /MAX:"$MAX_FILE_BYTES" /NFL /NDL /NJH /NJS /NP "$@" >/dev/null 2>&1
  rc=$?
  [ "$rc" -ge 8 ] && return 1
  verify_copied "$src" "$dst" || return 1
  return 0
}

# Publishes a quarantine dir (_invalid-*/_restarted-*) into archived-runs/<t>/,
# with a curated, smaller file set (score.json, final.diff, driver.log, turn-*.json,
# session transcripts) rather than the full raw log set live runs/ entries carry --
# these are kept for the record, not as live results (see archived-runs/README.md).
# Uses /MIR + an explicit include list (robocopy treats bare trailing args as a
# file-name filter) instead of /E, so stale files disappear if the source changes,
# but only within the included patterns -- nothing outside that set is touched.
archive_quarantine_dir() {
  local src="$1" t="$2"
  local dst="$DST/archived-runs/$t"
  local rc=0 src_win dst_win
  mkdir -p "$dst"
  src_win="$(cygpath -w "$src" 2>/dev/null || echo "$src")"
  dst_win="$(cygpath -w "$dst" 2>/dev/null || echo "$dst")"
  robocopy "$src_win" "$dst_win" score.json final.diff driver.log "turn-*.json" "*.jsonl" \
    /S /MIR /MAX:"$MAX_FILE_BYTES" /XF "*.bash.log" /NFL /NDL /NJH /NJS /NP >/dev/null 2>&1
  rc=$?
  if [ "$rc" -ge 8 ]; then
    log "archive copy failed for $t (robocopy rc=$rc)"
    return 1
  fi
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
# _invalid-*/_restarted-* are orchestrator quarantine dirs created when a run gets
# invalidated and redone (e.g. _invalid-effort-20260820, _restarted-raptor-cap-20260820).
# Policy: these ARE published, for transparency, but under archived-runs/<t>/ with a
# curated file set and a README explaining they're not results -- never under runs/,
# which would present a retracted/broken run as if it were live data.
# _laneC is Lane-C *scratch* (the runner's working directory) -- the actual Lane-C
# results are already published under runs/chessjs/<label>-c/, so _laneC itself is
# just skipped, not archived (it's not invalidated data, just not the publish copy).
# Anything else starting with "_" that isn't recognized is synced into runs/ as if
# it were a normal task (default to not silently dropping real data) but logged
# loudly, so an actually-new convention gets noticed instead of mis-handled by default.
mkdir -p "$DST/runs/_matrix"
cp -f "$SRC/_runs/_matrix/status.tsv" "$DST/runs/_matrix/" || fail "matrix status.tsv copy"
for d in "$SRC/_runs"/*/; do
  t="$(basename "$d")"
  case "$t" in
    _matrix) continue ;;
    calibration) continue ;;
    deeweb*) log "skipping excluded task dir: $t"; continue ;;
    _laneC) continue ;;
    _invalid-*|_restarted-*)
      log "archiving quarantine dir: $t -> archived-runs/$t"
      archive_quarantine_dir "$d" "$t" || fail "archive $t"
      continue
      ;;
    _*) log "WARNING: unrecognized underscore-prefixed _runs dir '$t' -- syncing it into runs/ as real data. If this is actually orchestrator scratch/quarantine, add its pattern to the skip/archive list above." ;;
  esac
  robomirror "$d" "$DST/runs/$t" /XD "worktree*" node_modules __pycache__ scratch .git /XF "*.pyc" "*.bash.log" \
    || fail "runs/$t copy"
done

# --- calibration/ ---
robomirror "$SRC/_runs/calibration" "$DST/calibration" /XD __pycache__ /XF "*.pyc" "*.bash.log" \
  || fail "calibration copy"

# --- answer-keys/ (keep our own README.md, refresh the rest, no deletion) ---
robocopy_update "$SRC/_hidden" "$DST/answer-keys" /XF README.md || fail "answer-keys copy"

# --- final safety net: nothing over MAX_FILE_BYTES may enter the repo, regardless
# of which mechanism copied it (robocopy /MAX above, or a plain `cp`). Scans the
# whole working tree except .git, deletes and logs any offender before staging. ---
big_file_guard() {
  local f size any=0
  while IFS= read -r -d '' f; do
    size="$(stat -c %s "$f" 2>/dev/null || echo 0)"
    if [ "$size" -gt "$MAX_FILE_BYTES" ]; then
      log "removing oversized file (${size} bytes > ${MAX_FILE_BYTES}): $f"
      rm -f "$f"
      any=1
    fi
  done < <(find "$DST" -type d -name .git -prune -o -type f -print0)
  return $any
}
big_file_guard || log "one or more oversized files were dropped from this sync (see lines above)"

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

# --- push debounce: always commit locally (nothing is ever lost); only push if
# forced, or if the last successful push was >= DEBOUNCE_SECS ago. A deferred
# commit sits local until a later sync's window has elapsed, or --push-now/--force
# flushes it explicitly. ---
if [ "$FORCE" -ne 1 ]; then
  NOW=$(date +%s)
  LAST_PUSH=0
  [ -f "$PUSH_STATE" ] && LAST_PUSH="$(cat "$PUSH_STATE" 2>/dev/null || echo 0)"
  ELAPSED=$(( NOW - LAST_PUSH ))
  if [ "$ELAPSED" -lt "$DEBOUNCE_SECS" ]; then
    log "last push was ${ELAPSED}s ago (< ${DEBOUNCE_SECS}s debounce window) -- deferring push"
    echo "synced: committed, push deferred (debounce)"
    exit 0
  fi
fi

do_push
