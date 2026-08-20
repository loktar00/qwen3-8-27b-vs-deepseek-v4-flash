#!/bin/bash
# Lane B driver: run one task for one model in OpenCode, non-interactive, scripted turns.
# Mirrors run_omp_task.sh (Lane A / OMP) exactly in semantics; only the CLI shape differs.
# usage: bash run_opencode_task.sh <task> <model-ref> <label>
#   task      = radix | anyio | chessground | hatetris | chessjs   (dir under D:/dev/ab-tasks, brief in _briefs/<task>/)
#   model-ref = OpenCode provider/model ref, e.g. pod-dsv4/deepseek-v4-flash-0731  or  pod-qwen/qwen3.8-27b-bf16
#               or  pod-qwen-medium/qwen3.8-27b-bf16:medium   (":variant" suffix is stripped and passed as --variant)
#   label     = short run label used for the worktree + output dir, e.g. dsv4 | qwen | qwen-med
# What it does: creates a git worktree <task>-<label>-oc at the task's HEAD, installs deps (per
# _briefs/<task>/turns.json), runs the opening brief with `opencode run` (message piped via stdin --
# see WINDOWS GOTCHA below), then each scripted turn continuing the same session id, captures json
# events, exports the session as JSON, and saves the final `git diff` + test run. Same flags for every
# model.
#
# WINDOWS GOTCHA (verified empirically on this box, opencode 1.14.29): passing the message as a
# positional CLI arg -- `opencode run "$TEXT"` -- HANGS even for a short single-line string with no
# special characters (confirmed: `timeout 20 opencode run ... "Run npm test..."` never returns).
# Piping the same text via stdin (`opencode run ... < file` or `<<<"$TEXT"`) works cleanly every time.
# So every prompt here, brief and turns alike, goes in via stdin -- never as a positional arg.
#
# ISOLATION GOTCHA (verified): OpenCode auto-grants external_directory permission on
# ~/.claude/skills/* and pulls in ~/.claude/CLAUDE.md via a "Claude Code compatibility" layer that is
# ON BY DEFAULT, even with a from-scratch project-local config (`opencode debug agent build` showed
# 30 .claude-rooted permission grants with the env unset, 0 with OPENCODE_DISABLE_CLAUDE_CODE=1 set).
# Left unset, Jason's personal global CLAUDE.md instructions could leak into the model-under-test's
# context, which is not vanilla and has no OMP-lane equivalent leak. So it's always exported below.
set -u
ROOT=/d/dev/ab-tasks
OC="/c/Program Files/nodejs/opencode"
CFG="D:/dev/style-pilot/labs/qwen38-day0/ab/opencode.jsonc"
TASK=$1; MODELREF=$2; LABEL=$3

# split "provider/model:variant" -> MODEL (provider/model) + VARIANT (may be empty)
MODEL="${MODELREF%%:*}"
VARIANT=""
[ "$MODEL" != "$MODELREF" ] && VARIANT="${MODELREF#*:}"
VARIANT_FLAG=()
[ -n "$VARIANT" ] && VARIANT_FLAG=(--variant "$VARIANT")

BRIEF="$ROOT/_briefs/$TASK/brief.md"; TURNS="$ROOT/_briefs/$TASK/turns.json"
WT="$ROOT/$TASK-${LABEL}-oc"; OUT="$ROOT/_runs/$TASK/${LABEL}-oc"
mkdir -p "$OUT"
TURNSW=$(cygpath -w "$TURNS")   # Windows Python cannot open Git-Bash /d/... paths
INSTALL=$(python -c "import json;print(json.load(open(r'$TURNSW'))['install'])")
TEST=$(python -c "import json;print(json.load(open(r'$TURNSW'))['test_cmd'])")
SRC=$(python -c "import json;print(json.load(open(r'$TURNSW')).get('dir','$TASK'))")   # clone/worktree dir to branch from
log(){ echo "[$(date +%T)] $*" | tee -a "$OUT/driver.log"; }

# vanilla, reproducible env for every model: project-local config only, no Claude Code compat leak,
# no external plugins (belt-and-suspenders with the config's mcp:{}/plugin:[]/instructions:[]).
export OPENCODE_CONFIG=$(cygpath -w "$CFG")
export OPENCODE_DISABLE_CLAUDE_CODE=1

# 1. worktree at the task's HEAD (fresh tree, no model-visible hidden files)
if [ ! -d "$WT" ]; then
  (cd "$ROOT/$SRC" && git worktree add -q "$WT" HEAD) && log "worktree $WT created from $SRC" || { log "worktree FAILED"; exit 1; }
  (cd "$WT" && rm -f AGENTS.md CLAUDE.md .cursorrules) && log "removed project-level AGENTS.md/CLAUDE.md/.cursorrules from worktree (lane-consistency policy)"
  (cd "$WT" && eval "$INSTALL") > "$OUT/install.log" 2>&1; log "install rc=$?"
fi
(cd "$WT" && git rev-parse --short HEAD > "$OUT/base-sha.txt")

# 2. opening brief (message via stdin -- see WINDOWS GOTCHA above)
COMMON=(--pure --format json --dangerously-skip-permissions --dir "$WT" --model "$MODEL" "${VARIANT_FLAG[@]}")
log "opening: $MODELREF on $TASK"
"$OC" "${COMMON[@]}" --title "$TASK-$LABEL" run < "$BRIEF" > "$OUT/turn-0.json" 2> "$OUT/turn-0.err"; log "turn 0 rc=$?"
SID=$(grep -o '"sessionID":"[^"]*"' "$OUT/turn-0.json" 2>/dev/null | head -1 | cut -d'"' -f4)
if [ -n "$SID" ]; then log "session id: $SID"; else log "WARNING: no session id captured from turn 0 -- follow-up turns will start fresh sessions"; fi

# 3. scripted follow-ups (identical text for every model). Explicit -s "$SID" rather than -c/--continue:
#    --continue resolves the single most-recently-created session across the WHOLE machine/user, not
#    scoped to --dir, so it isn't safe if runs for other labels/models happen concurrently on this box.
N=$(python -c "import json;print(len(json.load(open(r'$TURNSW'))['turns']))")
for i in $(seq 0 $((N-1))); do
  T=$(python -c "import json;print(json.load(open(r'$TURNSW'))['turns'][$i])")
  log "turn $((i+1)): $T"
  SFLAG=(); [ -n "$SID" ] && SFLAG=(-s "$SID")
  "$OC" "${COMMON[@]}" "${SFLAG[@]}" run <<< "$T" > "$OUT/turn-$((i+1)).json" 2> "$OUT/turn-$((i+1)).err"; log "turn $((i+1)) rc=$?"
done

# 4. artifacts: diff, final test run, session export
(cd "$WT" && git add -A && git diff --cached -- . ':!package-lock.json' ':!pnpm-lock.yaml' ':!.venv' ':!AGENTS.md' ':!CLAUDE.md' ':!.cursorrules' > "$OUT/final.diff" && git diff --cached --stat -- . ':!package-lock.json' ':!pnpm-lock.yaml' ':!.venv' ':!AGENTS.md' ':!CLAUDE.md' ':!.cursorrules' | tail -3 | tee -a "$OUT/driver.log"; git reset -q)
(cd "$WT" && eval "$TEST") > "$OUT/final-tests.log" 2>&1; log "final tests rc=$?"
if [ -n "$SID" ]; then
  "$OC" export "$SID" > "$OUT/export.json" 2> "$OUT/export.log" && log "session exported -> $OUT/export.json" || log "session export FAILED (see export.log)"
else
  log "no session id -- skipping export"
fi
log "DONE $TASK/$LABEL -> $OUT"
