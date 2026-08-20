#!/bin/bash
# Lane A/B driver: run one task for one model in OMP (oh-my-pi), non-interactive, scripted turns.
# usage: bash run_omp_task.sh <task> <model-ref> <label>
#   task      = radix | anyio | chessground | hatetris | chessjs   (dir under D:/dev/ab-tasks, brief in _briefs/<task>/)
#   model-ref = OMP model ref, e.g. pod-dsv4/deepseek-v4-flash-0731  or  pod-qwen/qwen3.8-27b-bf16  or  pod-qwen/qwen3.8-27b-bf16:medium
#   label     = short run label used for the worktree + output dir, e.g. dsv4 | qwen | qwen-med
# What it does: creates a git worktree <task>-<label> at the task's HEAD, installs deps (per _briefs/<task>/turns.json),
# runs the opening brief with `omp -p`, then each scripted turn with `omp -c -p` (continue), captures json events,
# exports the session to HTML, and saves the final `git diff` + test run. Same flags for every model.
set -u
ROOT=/d/dev/ab-tasks; OMP="/c/Users/lokta/AppData/Local/omp/omp"
TASK=$1; MODEL=$2; LABEL=$3
BRIEF="$ROOT/_briefs/$TASK/brief.md"; TURNS="$ROOT/_briefs/$TASK/turns.json"
WT="$ROOT/$TASK-$LABEL"; OUT="$ROOT/_runs/$TASK/$LABEL"; SESS="$OUT/sessions"
mkdir -p "$OUT" "$SESS"
TURNSW=$(cygpath -w "$TURNS")   # Windows Python cannot open Git-Bash /d/... paths
INSTALL=$(python -c "import json;print(json.load(open(r'$TURNSW'))['install'])")
TEST=$(python -c "import json;print(json.load(open(r'$TURNSW'))['test_cmd'])")
SRC=$(python -c "import json;print(json.load(open(r'$TURNSW')).get('dir','$TASK'))")   # clone/worktree dir to branch from
log(){ echo "[$(date +%T)] $*" | tee -a "$OUT/driver.log"; }

# 1. worktree at the task's HEAD (fresh tree, no model-visible hidden files)
if [ ! -d "$WT" ]; then
  (cd "$ROOT/$SRC" && git worktree add -q "$WT" HEAD) && log "worktree $WT created from $SRC" || { log "worktree FAILED"; exit 1; }
  (cd "$WT" && rm -f AGENTS.md CLAUDE.md .cursorrules) && log "removed project-level AGENTS.md/CLAUDE.md/.cursorrules from worktree (lane-consistency policy)"
  (cd "$WT" && eval "$INSTALL") > "$OUT/install.log" 2>&1; log "install rc=$?"
fi
(cd "$WT" && git rev-parse --short HEAD > "$OUT/base-sha.txt")

# 2. opening brief
COMMON=(--no-extensions --no-skills --no-rules --approval-mode yolo --mode json --no-title
        --session-dir "$SESS" --cwd "$WT" --model "$MODEL" --max-time 90m --config "$ROOT/_briefs/ab-overlay.yml")
log "opening: $MODEL on $TASK"
"$OMP" "${COMMON[@]}" -p "@$BRIEF" > "$OUT/turn-0.json" 2> "$OUT/turn-0.err"; log "turn 0 rc=$?"

# 3. scripted follow-ups (identical text for every model)
N=$(python -c "import json;print(len(json.load(open(r'$TURNSW'))['turns']))")
for i in $(seq 0 $((N-1))); do
  T=$(python -c "import json;print(json.load(open(r'$TURNSW'))['turns'][$i])")
  log "turn $((i+1)): $T"
  "$OMP" "${COMMON[@]}" -c -p "$T" > "$OUT/turn-$((i+1)).json" 2> "$OUT/turn-$((i+1)).err"; log "turn $((i+1)) rc=$?"
done

# 4. artifacts: diff, final test run, HTML export
(cd "$WT" && git add -A && git diff --cached -- . ':!package-lock.json' ':!pnpm-lock.yaml' ':!.venv' ':!AGENTS.md' ':!CLAUDE.md' ':!.cursorrules' > "$OUT/final.diff" && git diff --cached --stat -- . ':!package-lock.json' ':!pnpm-lock.yaml' ':!.venv' ':!AGENTS.md' ':!CLAUDE.md' ':!.cursorrules' | tail -3 | tee -a "$OUT/driver.log"; git reset -q)
(cd "$WT" && eval "$TEST") > "$OUT/final-tests.log" 2>&1; log "final tests rc=$?"
S=$(ls -t "$SESS"/**/*.jsonl "$SESS"/*.jsonl 2>/dev/null | head -1)
[ -n "$S" ] && "$OMP" --export "$S" > "$OUT/export.log" 2>&1 && log "session exported (see export.log for path)"
log "DONE $TASK/$LABEL -> $OUT"
