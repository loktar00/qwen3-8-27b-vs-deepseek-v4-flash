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
# Output contract: every other message goes to stderr; stdout carries exactly one
# final line: "synced: <short-sha>" | "synced: skipped (<reason>)" | "synced: failed (<reason>)".

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
STALE_SECS=600
MAX_FILE_BYTES=$((95 * 1024 * 1024))   # 95 MiB; GitHub's hard limit is 100MB

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
# invalidated and redone (e.g. _invalid-effort-20260820, _restarted-raptor-cap-20260820)
# -- publishing those alongside real results would present retracted/broken runs as if
# they were live data, so they're skipped like _matrix/deeweb* are. NOT every
# underscore-prefixed dir is quarantine, though -- _laneC is real Lane C (scripted
# no-harness chat) results and must sync normally. Anything else starting with "_"
# that isn't recognized is synced (default to not silently dropping real data) but
# logged loudly, so an actually-new quarantine convention gets noticed, not swallowed.
mkdir -p "$DST/runs/_matrix"
cp -f "$SRC/_runs/_matrix/status.tsv" "$DST/runs/_matrix/" || fail "matrix status.tsv copy"
for d in "$SRC/_runs"/*/; do
  t="$(basename "$d")"
  case "$t" in
    _matrix) continue ;;
    calibration) continue ;;
    deeweb*) log "skipping excluded task dir: $t"; continue ;;
    _invalid-*|_restarted-*) log "skipping orchestrator quarantine dir: $t"; continue ;;
    _*) log "WARNING: unrecognized underscore-prefixed _runs dir '$t' -- syncing it as real data. If this is actually orchestrator scratch/quarantine, add its pattern to the skip list above." ;;
  esac
  robomirror "$d" "$DST/runs/$t" /XD "worktree*" node_modules __pycache__ /XF "*.pyc" "*.bash.log" \
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

PUSH_OUT="$(git push -q 2>&1)"
PUSH_RC=$?
if [ "$PUSH_RC" -ne 0 ]; then
  FIRST_LINE="$(printf '%s\n' "$PUSH_OUT" | grep -m1 -E '^(remote: )?error:')"
  [ -z "$FIRST_LINE" ] && FIRST_LINE="$(printf '%s\n' "$PUSH_OUT" | grep -m1 .)"
  fail "git push: ${FIRST_LINE:-no output}"
fi

SHA="$(git rev-parse --short HEAD)"
echo "synced: $SHA"
