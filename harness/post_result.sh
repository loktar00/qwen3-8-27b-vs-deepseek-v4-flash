#!/bin/bash
# post_result.sh -- score one A/B run, rebuild the results site, print one RESULT line.
# See ab/score_task.py (writes _runs/<task>/<label>/score.json) and ab/build_site.py (renders
# the static site from _runs + SCORING.md).
#
# usage:
#   bash post_result.sh <task> <label>   score one run, rebuild the site, print one RESULT line
#   bash post_result.sh --all            score every run (score_task.py --all), rebuild once,
#                                         print a RESULT line for every run that now has a score.json
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCORE_PY="$SCRIPT_DIR/score_task.py"
BUILD_PY="$SCRIPT_DIR/build_site.py"

ROOT=/d/dev/ab-tasks           # posix path, for globbing/tests on this side
RUNS_WIN="D:/dev/ab-tasks"     # windows-style path, matches build_site.py's own defaults
SITE_WIN="D:/dev/ab-tasks/_site"
SITE_INDEX_WIN='D:\dev\ab-tasks\_site\index.html'

usage() {
  cat <<'EOF'
usage:
  bash post_result.sh <task> <label>
  bash post_result.sh --all
EOF
}

# Prints one RESULT line for <task>/<label>, reading its score.json. Defensive: any missing or
# unreadable field renders as "?" rather than failing.
fmt_result() {
  local task="$1" label="$2"
  local score_json="$ROOT/_runs/$task/$label/score.json"
  python - "$task" "$label" "$score_json" "$SITE_INDEX_WIN" <<'PYEOF'
import json
import sys

task, label, path, site_index = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]


def g(d, *keys):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur or cur[k] is None:
            return "?"
        cur = cur[k]
    return cur


try:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        data = {}
except Exception:
    data = {}

overall = data.get("overall_pass")
overall_s = "PASS" if overall is True else ("FAIL" if overall is False else "?")

p1 = g(data, "P1", "status")
p2 = g(data, "P2", "status")
p3 = g(data, "P3", "status")

wall = data.get("wallclock_seconds")
wall_s = wall if isinstance(wall, (int, float)) else "?"

tokens = g(data, "events", "completion_tokens_sum")

tcc = g(data, "events", "tool_call_counts")
if isinstance(tcc, dict) and tcc:
    tool_calls = sum(v for v in tcc.values() if isinstance(v, (int, float)))
else:
    tool_calls = "?"

print(
    f"RESULT {task}/{label}: {overall_s} P1={p1} P2={p2} P3={p3} | "
    f"wall={wall_s} tokens={tokens} tool_calls={tool_calls} | "
    f"site: {site_index}"
)
PYEOF
}

rebuild_site() {
  echo "[post_result] rebuilding site -> $SITE_WIN"
  python "$BUILD_PY" --runs "$RUNS_WIN" --out "$SITE_WIN"
}

if [ $# -eq 1 ] && [ "$1" = "--all" ]; then
  echo "[post_result] scoring all runs (score_task.py --all)..."
  python "$SCORE_PY" --all
  score_rc=$?

  rebuild_site

  echo "[post_result] results:"
  shopt -s nullglob
  for d in "$ROOT"/_runs/*/*/; do
    [ -f "$d/score.json" ] || continue
    task="$(basename "$(dirname "$d")")"
    label="$(basename "$d")"
    fmt_result "$task" "$label"
  done
  shopt -u nullglob
  exit $score_rc
fi

if [ $# -ne 2 ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  usage
  [ $# -eq 1 ] && { [ "$1" = "-h" ] || [ "$1" = "--help" ]; } && exit 0
  exit 1
fi

TASK="$1"; LABEL="$2"

echo "[post_result] scoring $TASK/$LABEL..."
score_summary="$(python "$SCORE_PY" "$TASK" "$LABEL")"
score_rc=$?
echo "[post_result] score_task.py: $score_summary"

rebuild_site

fmt_result "$TASK" "$LABEL"
exit $score_rc
