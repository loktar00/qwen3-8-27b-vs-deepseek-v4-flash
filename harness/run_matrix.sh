#!/bin/bash
# run_matrix.sh -- fires the full lane-A (OMP) job matrix (task x model x rep) for the DSV4 vs
# Qwen3.8 A/B, with a per-model concurrency cap, resumable skip, and a live status.tsv. See
# ab/run_omp_task.sh (the per-job driver) and ab/SCORING.md SS3-4 (lanes, n=2 reps per model per
# bug-fix task; Qwen shipped default is the primary row, `medium` the secondary row).
#
# usage:
#   bash run_matrix.sh [--tasks a,b,c] [--models dsv4,qwen,qwen-med] [--reps 2]
#                       [--concurrency-per-model 2] [--dry-run]
#
# Each job runs:  bash run_omp_task.sh <task> <model-ref> <label>
#   label is "<model>-r<rep>", e.g. qwen-r1, qwen-med-r2, dsv4-r1
#   stdout/stderr -> D:/dev/ab-tasks/_runs/_matrix/<task>-<label>.log
#   status table  -> D:/dev/ab-tasks/_runs/_matrix/status.tsv (rewritten every 30s)
#   live summary printed every 60s
#
# Resumable: a job is skipped (marked done) if its run dir already has a driver.log containing
# "DONE" -- re-running run_matrix.sh after a partial matrix only launches what's missing.
#
# Concurrency: capped PER MODEL (default 2 concurrent jobs per model -- the OMP pods run with
# max-num-seqs=8, so 2 keeps a server busy without flooding it). All models run their queues in
# parallel, so with 3 models and the default cap that's up to 6 jobs running at once.
set -u

# ---- model refs (edit here, or override via env, if an OMP ref changes) ----------------------
# qwen-med's ref may move to the calibrator's proxy path (pod-qwen-medium/qwen3.8-27b-bf16) if the
# direct ":medium" suffix turns out not to be selectable server-side -- change it in ONE place here.
MODEL_REF_DSV4="${MODEL_REF_DSV4:-pod-dsv4/deepseek-v4-flash-0731}"
MODEL_REF_QWEN="${MODEL_REF_QWEN:-pod-qwen/qwen3.8-27b-bf16}"
MODEL_REF_QWEN_MED="${MODEL_REF_QWEN_MED:-pod-qwen/qwen3.8-27b-bf16:medium}"

ROOT=/d/dev/ab-tasks
RUNS="$ROOT/_runs"
MATRIX_DIR="$RUNS/_matrix"
STATE_DIR="$MATRIX_DIR/.state"
STATUS_TSV="$MATRIX_DIR/status.tsv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRIVER="$SCRIPT_DIR/run_omp_task.sh"

ALL_TASKS=(radix anyio hatetris chessground chessground-322 chessjs)
ALL_MODELS=(dsv4 qwen qwen-med)

TASKS_OPT=""
MODELS_OPT=""
REPS=2
CONCURRENCY=2
DRY_RUN=0

usage() {
  cat <<'EOF'
usage: bash run_matrix.sh [--tasks a,b,c] [--models dsv4,qwen,qwen-med] [--reps 2]
                           [--concurrency-per-model 2] [--dry-run]

  --tasks                  comma-separated subset of: radix,anyio,hatetris,chessground,chessground-322,chessjs
                            (default: all six)
  --models                 comma-separated subset of: dsv4,qwen,qwen-med (default: all three)
  --reps                   repetitions per task x model (default: 2, per SCORING.md n=2)
  --concurrency-per-model  max concurrent jobs per model, all models run in parallel (default: 2)
  --dry-run                print the job list and exact commands, run nothing
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --tasks) TASKS_OPT="$2"; shift 2 ;;
    --models) MODELS_OPT="$2"; shift 2 ;;
    --reps) REPS="$2"; shift 2 ;;
    --concurrency-per-model) CONCURRENCY="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [ -z "$TASKS_OPT" ]; then
  TASK_LIST=("${ALL_TASKS[@]}")
else
  IFS=',' read -r -a TASK_LIST <<< "$TASKS_OPT"
fi
if [ -z "$MODELS_OPT" ]; then
  MODEL_LIST=("${ALL_MODELS[@]}")
else
  IFS=',' read -r -a MODEL_LIST <<< "$MODELS_OPT"
fi

for t in "${TASK_LIST[@]}"; do
  found=0
  for at in "${ALL_TASKS[@]}"; do [ "$t" = "$at" ] && found=1 && break; done
  if [ "$found" -ne 1 ]; then
    echo "unknown task: $t (known: ${ALL_TASKS[*]})" >&2; exit 1
  fi
  if [ ! -f "$ROOT/_briefs/$t/brief.md" ] || [ ! -f "$ROOT/_briefs/$t/turns.json" ]; then
    echo "task '$t' is missing brief.md/turns.json under $ROOT/_briefs/$t" >&2; exit 1
  fi
done

model_ref_for() {
  case "$1" in
    dsv4) echo "$MODEL_REF_DSV4" ;;
    qwen) echo "$MODEL_REF_QWEN" ;;
    qwen-med) echo "$MODEL_REF_QWEN_MED" ;;
    *) echo "unknown model key: $1 (known: ${ALL_MODELS[*]})" >&2; return 1 ;;
  esac
}
for m in "${MODEL_LIST[@]}"; do model_ref_for "$m" > /dev/null || exit 1; done

case "$REPS" in ''|*[!0-9]*) echo "--reps must be a positive integer, got: $REPS" >&2; exit 1 ;; esac
case "$CONCURRENCY" in ''|*[!0-9]*) echo "--concurrency-per-model must be a positive integer, got: $CONCURRENCY" >&2; exit 1 ;; esac

# ---- build the job list: task x model x rep -----------------------------------------------
JOB_TASK=(); JOB_MODEL=(); JOB_REF=(); JOB_LABEL=(); JOB_RUNDIR=(); JOB_LOG=(); JOB_STATE=()
for task in "${TASK_LIST[@]}"; do
  for model in "${MODEL_LIST[@]}"; do
    ref="$(model_ref_for "$model")"
    for ((r = 1; r <= REPS; r++)); do
      label="${model}-r${r}"
      JOB_TASK+=("$task")
      JOB_MODEL+=("$model")
      JOB_REF+=("$ref")
      JOB_LABEL+=("$label")
      JOB_RUNDIR+=("$RUNS/$task/$label")
      JOB_LOG+=("$MATRIX_DIR/$task-$label.log")
      JOB_STATE+=("$STATE_DIR/$task-$label.state")
    done
  done
done
NJOBS=${#JOB_TASK[@]}

is_done() {
  # $1 = run dir
  [ -f "$1/driver.log" ] && grep -q "DONE" "$1/driver.log" 2>/dev/null
}

if [ "$NJOBS" -eq 0 ]; then
  echo "no jobs matched --tasks/--models" >&2
  exit 1
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo "job list ($NJOBS jobs = ${#TASK_LIST[@]} tasks x ${#MODEL_LIST[@]} models x $REPS reps):"
  for ((i = 0; i < NJOBS; i++)); do
    task="${JOB_TASK[$i]}"; ref="${JOB_REF[$i]}"; label="${JOB_LABEL[$i]}"; rundir="${JOB_RUNDIR[$i]}"
    note=""
    is_done "$rundir" && note="  [skip: already DONE, resumable]"
    printf '[%d/%d] %s / %s%s\n' "$((i + 1))" "$NJOBS" "$task" "$label" "$note"
    printf '    bash "%s" %s "%s" %s > "%s" 2>&1\n' "$DRIVER" "$task" "$ref" "$label" "${JOB_LOG[$i]}"
  done
  exit 0
fi

# ---- real run -------------------------------------------------------------------------------
mkdir -p "$MATRIX_DIR" "$STATE_DIR"
set -m   # each backgrounded job becomes its own process group -> `kill -- -$pid` reaches its
         # children (the omp binary run_omp_task.sh launches), not just the wrapper shell.

now() { date +%Y-%m-%dT%H:%M:%S; }

get_field() { grep -m1 "^$2=" "$1" 2>/dev/null | cut -d= -f2-; }

write_state() {
  # $1=statefile $2=state $3=start $4=end $5=pid $6=task $7=label
  # task/label are embedded so a reader (matrix_status.py) never has to reverse-parse them out of
  # the "<task>-<label>.state" filename, which is ambiguous when both contain hyphens
  # (e.g. task "chessground-322" + label "qwen-med-r1").
  { printf 'state=%s\n' "$2"; printf 'start=%s\n' "$3"; printf 'end=%s\n' "$4"; printf 'pid=%s\n' "$5"
    printf 'task=%s\n' "${6:-}"; printf 'label=%s\n' "${7:-}"; } \
    > "$1.tmp" && mv -f "$1.tmp" "$1"
}

generate_status() {
  local tmp="$STATUS_TSV.tmp"
  # Two run_matrix.sh instances can run concurrently over disjoint --tasks/--models subsets (e.g.
  # one covering dsv4, another covering qwen+qwen-med); each only knows its OWN job list, so a
  # naive overwrite would clobber the other's rows every 30s. Merge: keep our own rows fresh, and
  # carry forward any existing row whose (task,label) isn't one of ours.
  local -A own_key=()
  for ((i = 0; i < NJOBS; i++)); do
    own_key["${JOB_TASK[$i]}"$'\t'"${JOB_LABEL[$i]}"]=1
  done
  local -a foreign_rows=()
  if [ -f "$STATUS_TSV" ]; then
    local -a existing_lines=()
    mapfile -t existing_lines < "$STATUS_TSV"
    local li line ot rest1 ol
    for ((li = 1; li < ${#existing_lines[@]}; li++)); do
      line="${existing_lines[$li]}"
      [ -z "$line" ] && continue
      ot="${line%%$'\t'*}"
      rest1="${line#*$'\t'}"
      ol="${rest1%%$'\t'*}"
      [ -n "${own_key[$ot$'\t'$ol]:-}" ] && continue
      foreign_rows+=("$line")
    done
  fi
  {
    printf 'task\tlabel\tstate\tstart\tend\tlast_driver_log_line\n'
    for ((i = 0; i < NJOBS; i++)); do
      local task="${JOB_TASK[$i]}" label="${JOB_LABEL[$i]}" sf="${JOB_STATE[$i]}" rundir="${JOB_RUNDIR[$i]}"
      local state="queued" start="" end="" lastline=""
      if [ -f "$sf" ]; then
        state="$(get_field "$sf" state)"
        start="$(get_field "$sf" start)"
        end="$(get_field "$sf" end)"
      fi
      [ -f "$rundir/driver.log" ] && lastline="$(tail -1 "$rundir/driver.log" 2>/dev/null | tr -d '\t\r')"
      printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$task" "$label" "$state" "$start" "$end" "$lastline"
    done
    if [ "${#foreign_rows[@]}" -gt 0 ]; then
      printf '%s\n' "${foreign_rows[@]}"
    fi
    true   # guarantee this group's exit status is 0 even when foreign_rows is empty (an empty
           # `if` here would otherwise make the group -- and the `&&` before `mv` -- fail)
  } > "$tmp" && mv -f "$tmp" "$STATUS_TSV"
}

status_loop() {
  while true; do
    generate_status
    sleep 30
  done
}

summary_loop() {
  while true; do
    sleep 60
    [ -f "$STATUS_TSV" ] || continue
    local ts; ts="$(date +%H:%M:%S)"
    awk -F'\t' -v ts="$ts" 'NR>1{c[$3]++; n++} END{
      printf "[matrix %s] total=%d queued=%d running=%d done=%d failed=%d\n", ts, n, c["queued"]+0, c["running"]+0, c["done"]+0, c["failed"]+0
    }' "$STATUS_TSV"
  done
}

# initial state pass: mark already-DONE jobs done up front (resumable skip), everything else queued
for ((i = 0; i < NJOBS; i++)); do
  rundir="${JOB_RUNDIR[$i]}"; sf="${JOB_STATE[$i]}"; log="${JOB_LOG[$i]}"
  if is_done "$rundir"; then
    write_state "$sf" done "" "" "" "${JOB_TASK[$i]}" "${JOB_LABEL[$i]}"
    printf '[matrix] SKIP %s/%s: already DONE, resumable\n' "${JOB_TASK[$i]}" "${JOB_LABEL[$i]}" >> "$log"
  else
    write_state "$sf" queued "" "" "" "${JOB_TASK[$i]}" "${JOB_LABEL[$i]}"
  fi
done
generate_status
echo "[matrix] $NJOBS jobs queued ($(awk -F'\t' 'NR>1 && $3=="done"{n++} END{print n+0}' "$STATUS_TSV") already done, resumable). status: $STATUS_TSV"

run_model_queue() {
  # $1=model_key $2=cap, rest = job indices for this model, in matrix order
  local model_key="$1" cap="$2"; shift 2
  local idxs=("$@")
  set -m
  local -A running_pid=()   # idx -> pid (must init empty: `local -A x` alone trips `set -u` on some bash builds)
  local qi=0 total=${#idxs[@]}
  while [ "$qi" -lt "$total" ] || [ "${#running_pid[@]}" -gt 0 ]; do
    while [ "${#running_pid[@]}" -lt "$cap" ] && [ "$qi" -lt "$total" ]; do
      local idx="${idxs[$qi]}"; qi=$((qi + 1))
      local task="${JOB_TASK[$idx]}" ref="${JOB_REF[$idx]}" label="${JOB_LABEL[$idx]}"
      local rundir="${JOB_RUNDIR[$idx]}" logfile="${JOB_LOG[$idx]}" sf="${JOB_STATE[$idx]}"
      if [ "$(get_field "$sf" state)" = "done" ]; then
        continue   # already marked done in the initial pass, resumable skip
      fi
      local started; started="$(now)"
      ( bash "$DRIVER" "$task" "$ref" "$label" > "$logfile" 2>&1
        rc=$?
        if [ "$rc" -eq 0 ] && grep -q "DONE" "$rundir/driver.log" 2>/dev/null; then
          write_state "$sf" done "$started" "$(now)" "" "$task" "$label"
        else
          write_state "$sf" failed "$started" "$(now)" "" "$task" "$label"
        fi
      ) &
      local jpid=$!
      running_pid[$idx]=$jpid
      write_state "$sf" running "$started" "" "$jpid" "$task" "$label"
    done
    if [ "${#running_pid[@]}" -gt 0 ]; then
      local donepid
      wait -n -p donepid "${running_pid[@]}" 2>/dev/null
      for k in "${!running_pid[@]}"; do
        [ "${running_pid[$k]}" = "$donepid" ] && unset 'running_pid[$k]'
      done
    fi
  done
}

declare -A MODEL_IDXS
for ((i = 0; i < NJOBS; i++)); do
  m="${JOB_MODEL[$i]}"
  MODEL_IDXS[$m]="${MODEL_IDXS[$m]:-} $i"
done

MANAGER_PIDS=()
for m in "${MODEL_LIST[@]}"; do
  idxs=(${MODEL_IDXS[$m]:-})
  [ "${#idxs[@]}" -eq 0 ] && continue
  run_model_queue "$m" "$CONCURRENCY" "${idxs[@]}" &
  MANAGER_PIDS+=("$!")
done

status_loop & STATUS_PID=$!
summary_loop & SUMMARY_PID=$!

cleanup() {
  echo ""
  echo "[matrix] caught signal, stopping children..."
  kill "$STATUS_PID" "$SUMMARY_PID" 2>/dev/null
  for p in "${MANAGER_PIDS[@]:-}"; do kill -- -"$p" 2>/dev/null; kill "$p" 2>/dev/null; done
  for sf in "$STATE_DIR"/*.state; do
    [ -f "$sf" ] || continue
    if [ "$(get_field "$sf" state)" = "running" ]; then
      pid="$(get_field "$sf" pid)"
      [ -n "$pid" ] && kill -- -"$pid" 2>/dev/null
    fi
  done
  wait 2>/dev/null
  generate_status
  echo "[matrix] stopped. status: $STATUS_TSV"
  exit 130
}
trap cleanup INT TERM

for p in "${MANAGER_PIDS[@]}"; do wait "$p"; done

kill "$STATUS_PID" "$SUMMARY_PID" 2>/dev/null
wait "$STATUS_PID" "$SUMMARY_PID" 2>/dev/null
generate_status
echo "[matrix] all jobs finished. status: $STATUS_TSV"
awk -F'\t' 'NR>1{c[$3]++} END{printf "[matrix] final: done=%d failed=%d queued=%d running=%d\n", c["done"]+0, c["failed"]+0, c["queued"]+0, c["running"]+0}' "$STATUS_TSV"
