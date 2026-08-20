#!/bin/bash
# Lane B harness-calibration gate: runs the 5-item gate from ab/calibration.md against one
# model, non-interactively, via OpenCode, in a throwaway scratch copy of D:/dev/ab-tasks/_calib/.
# Run this per model, per harness, BEFORE any head-to-head comparison. 5/5 required; a failure
# here is a HARNESS/CONFIG event to fix, never scored as a model loss (see calibration.md).
#
# usage: bash opencode_probe.sh <model-ref> [run-label]
#   model-ref = OpenCode provider/model ref, e.g. pod-qwen/qwen3.8-27b-bf16
#               or pod-qwen-medium/qwen3.8-27b-bf16:medium
#   run-label = optional short label for the scratch dir (default: derived from model-ref)
#
# NOTE: cannot be exercised end-to-end until the pod model servers are up (this is the "stub for
# later" the config/driver prep also had to leave). The plumbing below (worktree-free scratch dir,
# stdin message delivery, session-id capture, export-based answer extraction) is exercised and
# working against a bogus model in the dry run reported alongside this file; the PASS/FAIL
# judgment logic itself has not been checked against a real model response -- see the NOTE in
# opencode_calib_check.py.
set -u
ROOT=/d/dev/ab-tasks
OC="/c/Program Files/nodejs/opencode"
CFG="D:/dev/style-pilot/labs/qwen38-day0/ab/opencode.jsonc"
CHECK="D:/dev/style-pilot/labs/qwen38-day0/ab/opencode_calib_check.py"

MODELREF=${1:?usage: opencode_probe.sh ^<model-ref^> [run-label]}
LABEL=${2:-$(echo "$MODELREF" | tr '/:' '--')}

MODEL="${MODELREF%%:*}"
VARIANT=""
[ "$MODEL" != "$MODELREF" ] && VARIANT="${MODELREF#*:}"
VARIANT_FLAG=()
[ -n "$VARIANT" ] && VARIANT_FLAG=(--variant "$VARIANT")

WORK="$ROOT/_calib_runs/${LABEL}-oc"
rm -rf "$WORK"; mkdir -p "$WORK"
cp "$ROOT/_calib/"* "$WORK/"

export OPENCODE_CONFIG=$(cygpath -w "$CFG")
export OPENCODE_DISABLE_CLAUDE_CODE=1

COMMON=(--pure --format json --dangerously-skip-permissions --dir "$WORK" --model "$MODEL" "${VARIANT_FLAG[@]}")
log(){ echo "[$(date +%T)] $*" | tee -a "$WORK/probe.log"; }
log "calibrating $MODELREF (label=$LABEL) in $WORK"

SID=""
PREV_COUNT=0
NPASS=0

# run one turn (message via stdin -- positional args hang on this box, see run_opencode_task.sh),
# capture the session id on turn 1, then export + isolate this turn's new assistant text/tool count.
run_item(){
  local n=$1; local prompt=$2
  local sflag=(); [ -n "$SID" ] && sflag=(-s "$SID")
  log "item $n prompt: $prompt"
  "$OC" "${COMMON[@]}" "${sflag[@]}" --title "calib-$LABEL" run <<< "$prompt" \
    > "$WORK/turn-$n.json" 2> "$WORK/turn-$n.err"
  local rc=$?
  [ -z "$SID" ] && SID=$(grep -o '"sessionID":"[^"]*"' "$WORK/turn-$n.json" | head -1 | cut -d'"' -f4)
  if [ -z "$SID" ]; then
    log "item $n: FAIL -- no session id, harness/config error (rc=$rc, see turn-$n.err)"
    ANSWER=""; TOOLCOUNT=0
    return 1
  fi
  "$OC" export "$SID" > "$WORK/export-$n.json" 2>> "$WORK/probe.log"
  local out; out=$(python "$CHECK" "$WORK/export-$n.json" "$PREV_COUNT")
  TOOLCOUNT=$(echo "$out" | sed -n 's/^TOOLCOUNT=//p')
  PREV_COUNT=$(echo "$out" | sed -n 's/^TOTALMESSAGES=//p')
  ANSWER=$(echo "$out" | tail -n +3)
  echo "$ANSWER" > "$WORK/answer-$n.txt"
  return 0
}

verdict(){  # $1=item name, $2=0/1 pass condition, $3=detail
  if [ "$2" = "1" ]; then
    log "item PASS: $1 -- $3"; NPASS=$((NPASS+1))
  else
    log "item FAIL: $1 -- $3"
  fi
}

# 1. READ
run_item 1 "What is on line 2 of notes.txt?"
ans_lc=$(echo "$ANSWER" | tr '[:upper:]' '[:lower:]')
[[ "$ans_lc" == *"beta gamma"* ]] && ok=1 || ok=0
verdict "1-READ" "$ok" "answer mentions 'beta gamma': $ok (tool calls: ${TOOLCOUNT:-0}); raw answer in $WORK/answer-1.txt"

# 2. EDIT
run_item 2 "calc.py's add() is wrong; fix it and show the diff."
CALC_OUT=$(cd "$WORK" && python calc.py 2>&1)
[ "$CALC_OUT" = "5" ] && ok=1 || ok=0
verdict "2-EDIT" "$ok" "python calc.py now prints '$CALC_OUT' (want 5); tool calls: ${TOOLCOUNT:-0}"

# 3. RUN+READ OUTPUT
run_item 3 'Run `python calc.py` (prints add(2,3)) and tell me the output.'
[[ "$ANSWER" == *"5"* ]] && ok=1 || ok=0
verdict "3-RUN+READ" "$ok" "answer mentions '5': $ok; raw answer in $WORK/answer-3.txt"

# 4. CHAIN
run_item 4 "Count the valid rows in data.csv, write the count to count.txt, then read it back."
COUNT_CONTENT=$(cat "$WORK/count.txt" 2>/dev/null | tr -d '[:space:]')
[ "$COUNT_CONTENT" = "4" ] && ok=1 || ok=0
verdict "4-CHAIN" "$ok" "count.txt contains '$COUNT_CONTENT' (want 4); tool calls: ${TOOLCOUNT:-0} (expect >=3)"

# 5. RECOVER
run_item 5 'Run `node sum.js 1 2`. If it fails, fix sum.js so it prints the sum of its two numeric arguments, re-run, and tell me the output.'
NODE_OUT=$(cd "$WORK" && node sum.js 1 2 2>&1)
[ "$NODE_OUT" = "3" ] && node_ok=1 || node_ok=0
[[ "$ANSWER" == *"3"* ]] && ans_ok=1 || ans_ok=0
ok=$([ "$node_ok" = "1" ] && [ "$ans_ok" = "1" ] && echo 1 || echo 0)
verdict "5-RECOVER" "$ok" "fixed sum.js now prints '$NODE_OUT' (want 3), answer mentions 3: $ans_ok"

log "RESULT: $NPASS/5 -- $([ "$NPASS" = 5 ] && echo PASS || echo FAIL) (see $WORK/probe.log, turn-*.json, answer-*.txt)"
[ "$NPASS" = 5 ]
