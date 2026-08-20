#!/usr/bin/env python3
"""make_fixture.py -- builds a small, fully-fake data root at D:/dev/ab-tasks/_runs-fixture
to develop and demo build_site.py against, without touching the real D:/dev/ab-tasks/_runs
(which is being written by a different agent and does not have score.json yet).

The fixture is a complete, self-contained root: it has its own _briefs/, _runs/, and
_runs/calibration/ -- it does not read or copy anything from the real ab-tasks tree.
Every issue, ticket, diff and log body below is invented for this fixture; none of it
is real project content.

Run once: python make_fixture.py
Then:     python build_site.py --runs D:/dev/ab-tasks/_runs-fixture --out D:/dev/ab-tasks/_site-sample
"""
import json
from pathlib import Path

ROOT = Path("D:/dev/ab-tasks/_runs-fixture")


def w(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def wj(path: Path, obj):
    w(path, json.dumps(obj, indent=2))


# --------------------------------------------------------------------------
# _briefs/<task>/brief.md + turns.json  (fictional stand-ins, same shape as real ones)
# --------------------------------------------------------------------------

BRIEFS = {
    "radix": {
        "brief": """# Task: fix a reported bug in `radix`

## Bug report (verbatim from the project's issue tracker)
**installHook.js:1 Error: Maximum update depth exceeded - React 19 + Radix**

When using Radix components with React 19, an infinite loop occurs in `composeRefs`:
the composed ref callback triggers itself on every render, hitting React's nested-update
limit. Reproducible by typing quickly inside a Plate editor with Radix popovers attached.

### Suggested solution
Memoize the composed ref callback, or guard against recursive `setRef` calls, and handle
the cleanup-function return value React 19 ref callbacks may now return.

## Standing instructions (identical for every run)
You are working in the repository at the current working directory. Work like a careful
open-source contributor:
1. Reproduce the bug first (write a minimal failing test or script) before changing code.
2. Find the root cause; fix the cause, not the symptom. Keep the change minimal and in the
   project's style.
3. Add or update a regression test that fails before your fix and passes after.
4. Run the project's test suite and make it green. Do not modify or delete unrelated tests.
5. When done, summarize: root cause, the files you changed, how you verified it.
Do not ask me for permission between steps; proceed until the task is complete, then report.

Test command for this repo: `pnpm vitest run packages/react/slot`
""",
        "turns": {
            "repo": "D:\\dev\\ab-tasks\\radix",
            "test_cmd": "pnpm vitest run packages/react/slot",
            "turns": [
                "Run the full slot package test suite and paste the summary.",
                "Your change should not alter behavior when no forwardedRef is passed. Confirm with a test.",
                "Is the same pattern present anywhere else in packages/react? Check and report, fix only if it is the same bug.",
            ],
            "install": "pnpm install --frozen-lockfile",
        },
    },
    "anyio": {
        "brief": """# Task: fix a reported bug in `anyio`

## Bug report (verbatim from the project's issue tracker)
**CapacityLimiter can over-grant tokens (`borrowed_tokens > total_tokens`)**

Raising `total_tokens` while tasks are already waiting on the limiter can cause more
tokens to be granted than are actually available, because the wake logic re-checks the
old capacity snapshot instead of the live value.

## Standing instructions (identical for every run)
Reproduce first, fix the root cause, add a regression test that fails before / passes
after, run the suite green, then summarize root cause + files changed + verification.

Test command for this repo: `.venv/Scripts/python -m pytest tests/test_synchronization.py -q`
""",
        "turns": {
            "repo": "D:\\dev\\ab-tasks\\anyio",
            "test_cmd": ".venv/Scripts/python -m pytest tests/test_synchronization.py -q",
            "turns": [
                "Run tests/test_synchronization.py and paste the summary.",
                "Does your fix also hold when total_tokens is raised while tasks are waiting? Add a test for that path.",
                "Explain in two sentences why the original ordering allowed the over-grant.",
            ],
            "install": "python -m venv .venv && ./.venv/Scripts/python -m pip install -q -e .",
        },
    },
    "hatetris": {
        "brief": """# Task: fix a reported bug in `hatetris`

## Bug report (verbatim from the project's issue tracker)
**Incomplete replays cause a softlock**

If you play a replay that doesn't end the game, the game stays stuck in replay mode
even after inputs run out, forcing a page refresh. It should let the user continue
playing from that state instead.

## Standing instructions (identical for every run)
Reproduce first, fix the root cause, add a regression test, run the suite green
(100% coverage enforced), then summarize.

Test command for this repo: `npm run unit`
""",
        "turns": {
            "repo": "D:\\dev\\ab-tasks\\hatetris",
            "test_cmd": "npm run unit",
            "turns": [
                "Run `npm run unit` and paste the summary (the suite enforces 100% coverage; keep it green).",
                "After a replay ends early, the user should be able to continue playing from that state without reloading. Confirm that is what your fix does, with a test.",
                "Keep the change confined to the game/replay state handling; do not alter the replay encoding.",
            ],
            "install": "npm ci --no-audit --no-fund",
        },
    },
    "chessground": {
        "brief": """# Task: fix a reported bug in `chessground`

## Bug report (verbatim from the project's issue tracker)
**Disconnect ResizeObserver on destroy and on redraw**

`bindBoard` constructs a `ResizeObserver` and observes the wrap element, but the
observer is never stored or disconnected: destroying the board leaks it, and calling
`redraw` a second time creates a duplicate observer on the same element.

## Standing instructions (identical for every run)
Reproduce first (a frozen leak test lives outside your worktree), fix the root cause,
add/confirm a regression test, run the suite green, then summarize.

Test command for this repo: `npm test`
""",
        "turns": {
            "dir": "chessground-ref",
            "repo": "D:\\dev\\ab-tasks\\chessground-ref",
            "test_cmd": "npm test",
            "install": "pnpm install",
            "turns": [
                "Add a unit test (vitest with jsdom) that proves the observer is disconnected on destroy and not duplicated on redraw, then run npm test.",
                "Compile with `npx tsc --sourceMap --declaration` and confirm demo.html still loads and resizes.",
                "Are there other listeners or observers created in bindBoard/bindDocument that share the same lifecycle problem? Check and report; fix only if it is the same bug.",
            ],
        },
    },
    "chessjs": {
        "brief": """# Task: fix a reported bug in `chessjs`

## Bug report (verbatim from the project's issue tracker)
**BigInt error when generating moves for pawns on edge ranks**

```
chess.put({ type: 'p', color: 'w' }, 'h8')
chess.moves({ square: 'h8', verbose: true })
```
throws `TypeError: Cannot mix BigInt and other types` inside `_movePiece`.

## Standing instructions (identical for every run)
Reproduce first with our pre-written repro (frozen, outside your worktree), fix the
root cause, add a regression test, run the suite green, then summarize.

Test command for this repo: `npm test`
""",
        "turns": {
            "repo": "D:\\dev\\ab-tasks\\chessjs",
            "test_cmd": "npm test",
            "turns": [
                "Run npm test and paste the summary.",
                "Does the same class of bug exist for black pawns on rank 1? Check and handle it in the same fix if so.",
                "Confirm promotion moves for pawns on the 7th rank are unaffected, with a test.",
            ],
            "install": "npm ci",
        },
        "lane_c": {
            "opening": "# Task: fix a reported bug in `chessjs`\n\n**BigInt error when generating moves for pawns on edge ranks.** "
                       "See above for the repro. You have no tools in this chat -- ask for any file by exact path and I will "
                       "paste it; give me full files or unified diffs to apply and I will run tests and paste the output.",
            "turns": [
                "Run npm test and paste the summary.",
                "Does the same class of bug exist for black pawns on rank 1? Check and handle it in the same fix if so.",
                "Confirm promotion moves for pawns on the 7th rank are unaffected, with a test.",
            ],
            "test_cmd": "npm test",
        },
    },
    "deeweb": {
        "brief": """# Task: CAL-7207 -- Fix pinned chat ordering and add drag-and-drop reordering

(Brief = the ticket, verbatim. Repo: called-deeweb at develop@fixture. Same text every model received.)

## Story
Pinned chats don't hold their order: pin/unpin never renumber the stored order, so
unpinning leaves gaps and pinning assigns order by array length, causing collisions.
There is also no way to rearrange pinned chats -- an explicit Edit mode should expose
checkboxes, a drag handle, and Save/Cancel.

## Acceptance Criteria
1. Pinned chats always render in the backend-stored order, stable across refetches
2. Pinning a new chat adds it to the end, never above older pins
3. Unpinning keeps the remaining pins in their existing order
4. Drag handles are not visible until Edit is on
5. In edit mode: check/uncheck to pin/unpin, drag to reorder
6. Save persists the new pin set and order in one request; survives reload
7. Cancel leaves the pinned chats exactly as they were
8. Outside edit mode, rows still open the chat on click
9. The drag handle is reachable and operable by keyboard

## Standing instructions
Same as every task: reproduce, fix root cause, add tests, run the suite green, summarize.
Private ticket -- published as aggregate scores only.
""",
        "turns": None,
    },
    "raptor": {
        "brief": """# Task Brief: Port Raptor: Call of the Shadows (Sector 1) to HTML5

Port the shareware sector-1 content to a browser build: HTML5 canvas, vanilla JS, Web
Audio, real extracted GLB assets, no external frameworks. Fixed milestone ladder M1-M5,
graded by a Playwright script against a required `window.__raptor` state object and a
320x200 `#raptor-canvas`. Same wall-clock cap and scripted milestone turns for every model.
Full grader interface contract: see `_raptor-support/brief-draft.md`.
""",
        "turns": None,
    },
}

for tid, spec in BRIEFS.items():
    w(ROOT / "_briefs" / tid / "brief.md", spec["brief"])
    if spec.get("turns"):
        wj(ROOT / "_briefs" / tid / "turns.json", spec["turns"])
    if spec.get("lane_c"):
        wj(ROOT / "_briefs" / tid / "lane_c_task.json", spec["lane_c"])


# --------------------------------------------------------------------------
# _runs/<task>/<label>/  (score.json + artifacts)
# --------------------------------------------------------------------------

FAKE_DIFF = """diff --git a/src/composeRefs.tsx b/src/composeRefs.tsx
index 1a2b3c4..5d6e7f8 100644
--- a/src/composeRefs.tsx
+++ b/src/composeRefs.tsx
@@ -8,10 +8,14 @@ function setRef<T>(ref: PossibleRef<T>, value: T) {
 export function composeRefs<T>(...refs: PossibleRef<T>[]) {
-  return (node: T) => refs.forEach((ref) => setRef(ref, node));
+  return (node: T) => {
+    const cleanups = refs.map((ref) => setRef(ref, node));
+    return () => cleanups.forEach((cleanup) => cleanup?.());
+  };
 }

 export function useComposedRefs<T>(...refs: PossibleRef<T>[]) {
-  return React.useCallback(composeRefs(...refs), refs);
+  return React.useCallback(composeRefs(...refs), refs); // eslint-disable-line react-hooks/exhaustive-deps
 }
diff --git a/src/composeRefs.test.tsx b/src/composeRefs.test.tsx
new file mode 100644
index 0000000..9f8e7d6
--- /dev/null
+++ b/src/composeRefs.test.tsx
@@ -0,0 +1,18 @@
+import { describe, it, expect, vi } from 'vitest';
+import { composeRefs } from './composeRefs';
+
+describe('composeRefs', () => {
+  it('does not re-invoke refs on repeated renders with the same node', () => {
+    const calls = vi.fn();
+    const ref = (n: unknown) => calls();
+    const composed = composeRefs(ref);
+    const node = {};
+    composed(node);
+    composed(node);
+    expect(calls).toHaveBeenCalledTimes(1);
+  });
+});
"""

FAKE_TESTS_LOG_PASS = """> pnpm vitest run packages/react/slot

 RUN  v1.6.0

 \u2713 src/composeRefs.test.tsx (3 tests) 12ms
 \u2713 src/Slot.test.tsx (9 tests) 41ms

 Test Files  2 passed (2)
      Tests  12 passed (12)
   Start at  14:02:11
   Duration  1.84s
"""

FAKE_TESTS_LOG_FAIL = """> pnpm vitest run packages/react/slot

 RUN  v1.6.0

 \u2713 src/composeRefs.test.tsx (3 tests) 12ms
 \u2715 src/Slot.test.tsx (9 tests) 44ms
   \u2715 forwards additional refs passed via cloneElement

 Test Files  1 failed | 1 passed (2)
      Tests  1 failed | 11 passed (12)
   Start at  14:03:52
   Duration  1.91s
"""

FAKE_DRIVER_LOG = """[14:00:02] worktree D:/dev/ab-tasks/radix-{label} created from radix
[14:00:41] install rc=0
[14:00:41] opening: {model} on radix
[14:07:18] turn 0 rc=0
[14:07:18] turn 1: Run the full slot package test suite and paste the summary.
[14:09:03] turn 1 rc=0
[14:09:03] turn 2: Your change should not alter behavior when no forwardedRef is passed. Confirm with a test.
[14:11:47] turn 2 rc=0
[14:11:47] turn 3: Is the same pattern present anywhere else in packages/react? Check and report, fix only if it is the same bug.
[14:14:20] turn 3 rc=0
 2 files changed, 22 insertions(+), 2 deletions(-)
[14:14:52] final tests rc=0
[14:14:53] session exported (see export.log for path)
[14:14:53] DONE radix/{label} -> D:/dev/ab-tasks/_runs/radix/{label}
"""

FAKE_INSTALL_LOG = "Lockfile is up to date, resolution step is skipped\nPackages: +842\nDone in 6.1s\n"


def diff_stats(added, removed, files):
    return {"added": added, "removed": removed, "files": files}


def write_run(task, label, model, lane, rep, class_kind, primary, secondary, tertiary=None,
              p4=None, checklist_extra=None, diff_text=None, tests_log=None, session=None):
    d = ROOT / "_runs" / task / label
    score = {"task": task, "label": label, "model": model, "lane": lane, "rep": rep}
    score.update(primary)
    score["secondary"] = secondary
    if tertiary:
        score["tertiary"] = tertiary
    if p4:
        score["p4"] = p4
    if checklist_extra:
        score["checklist_extra"] = checklist_extra
    wj(d / "score.json", score)
    w(d / "final.diff", diff_text if diff_text is not None else FAKE_DIFF)
    w(d / "final-tests.log", tests_log if tests_log is not None else FAKE_TESTS_LOG_PASS)
    w(d / "driver.log", FAKE_DRIVER_LOG.format(label=label, model=model))
    w(d / "install.log", FAKE_INSTALL_LOG)
    if session == "html":
        w(d / "sessions" / f"{label}-export.html",
          f"<!doctype html><meta charset='utf-8'><body style='font-family:monospace;padding:2rem'>"
          f"<h3>OMP session export (fixture) -- {label}</h3>"
          f"<p>&gt; opening brief delivered</p><p>&lt; assistant reproduces bug, edits composeRefs.tsx, runs tests</p>"
          f"<p>&gt; turn 1: run the suite</p><p>&lt; assistant pastes green summary</p></body>")
    elif session == "omp-jsonl":
        lines = [
            {"event": "user_message", "text": "opening brief delivered"},
            {"event": "tool_call", "name": "read_file", "args": {"path": "src/composeRefs.tsx"}},
            {"event": "tool_result", "name": "read_file", "ok": True},
            {"event": "assistant_message", "text": "Reproducing the loop with a failing test first..."},
            {"event": "tool_call", "name": "edit_file", "args": {"path": "src/composeRefs.tsx"}},
            {"event": "tool_call", "name": "bash", "args": {"cmd": "pnpm vitest run packages/react/slot"}},
            {"event": "assistant_message", "text": "Suite is green. Root cause: setRef re-invoked ref callbacks on every render because composeRefs recreated the closure without memoizing the cleanup."},
        ]
        w(d / "sessions" / f"{label}.jsonl", "\n".join(json.dumps(x) for x in lines))
    elif session == "lane_c":
        lines = [
            {"t": 1000.0, "role": "user", "content": "opening brief delivered", "turn": "opening"},
            {"t": 1041.2, "role": "assistant", "content": "Here is a failing repro test and the fix as a unified diff...", "reasoning_chars": 812, "usage": {"completion_tokens": 640}, "secs": 41.2},
            {"t": 1041.2, "role": "user", "content": "Applied your changes. I ran `npm test` -- exit code 0. Output (tail):\\n```\\n12 passed\\n```", "turn": 1},
            {"t": 1078.9, "role": "assistant", "content": "Confirmed: black pawns on rank 1 hit the same path; added a symmetric test.", "reasoning_chars": 340, "usage": {"completion_tokens": 210}, "secs": 37.7},
        ]
        w(d / "transcript.jsonl", "\n".join(json.dumps(x) for x in lines))
    return d


def p123(p1, p2, p3, p1r="", p2r="", p3r=""):
    return {
        "P1": {"pass": p1, "reason": p1r},
        "P2": {"pass": p2, "reason": p2r},
        "P3": {"pass": p3, "reason": p3r},
        "pass": p1 and p2 and p3,
    }


def sec(wall_s, prompt, completion, reasoning, tools, test_runs, reproduced_first, added, removed, files,
        precision="subset", events=None, reverts=None, redirects=None, coderabbit=None):
    d = {
        "wall_s": wall_s,
        "tokens": {"prompt": prompt, "completion": completion, "reasoning": reasoning},
        "tool_calls": {"by_name": tools, "total": sum(tools.values())},
        "test_runs": test_runs,
        "reproduced_first": reproduced_first,
        "diff": diff_stats(added, removed, files),
        "precision": precision,
    }
    if events:
        d["harness_events"] = events
    if reverts is not None:
        d["reverts"] = reverts
    if redirects is not None:
        d["redirects"] = redirects
    if coderabbit is not None:
        d["coderabbit"] = coderabbit
    return d


# ---- radix: 2A, lanes A/B/C -------------------------------------------------
write_run("radix", "dsv4-a-r1", "dsv4", "A", 1, "2A",
          p123(True, True, True, "upstream test file copied in, passes.", "full slot suite green.", "our own regression test fails on base, passes on fix."),
          sec(438, 9800, 2100, 4400, {"read": 6, "edit": 2, "bash": 5}, 3, True, 22, 2, ["packages/react/compose-refs/src/composeRefs.tsx", "packages/react/compose-refs/src/composeRefs.test.tsx"]),
          tertiary={"root_cause": 2, "style": 2, "scale": 2, "judge": "blinded"},
          session="omp-jsonl")
write_run("radix", "dsv4-a-r2", "dsv4", "A", 2, "2A",
          p123(True, True, True), sec(461, 10100, 2300, 4700, {"read": 7, "edit": 2, "bash": 6}, 4, True, 24, 2, ["packages/react/compose-refs/src/composeRefs.tsx", "packages/react/compose-refs/src/composeRefs.test.tsx"]),
          tertiary={"root_cause": 2, "style": 2, "scale": 2, "judge": "blinded"})
write_run("radix", "qwen-a-r1", "qwen", "A", 1, "2A",
          p123(True, True, True), sec(1180, 9700, 3600, 12100, {"read": 9, "edit": 3, "bash": 7}, 5, True, 19, 1, ["packages/react/compose-refs/src/composeRefs.tsx", "packages/react/compose-refs/src/composeRefs.test.tsx"]),
          tertiary={"root_cause": 2, "style": 1, "scale": 2, "judge": "blinded"}, session="html")
write_run("radix", "qwen-a-r2", "qwen", "A", 2, "2A",
          p123(True, True, False, p3r="Model's own regression test does not fail on the pre-fix base commit (it asserts on the fixed behavior directly), so it does not demonstrate the bug was caught."),
          sec(1340, 9900, 3800, 13400, {"read": 11, "edit": 4, "bash": 9}, 6, True, 31, 3, ["packages/react/compose-refs/src/composeRefs.tsx"]),
          tertiary={"root_cause": 1, "style": 1, "scale": 2, "judge": "blinded"})
write_run("radix", "qwen-medium-a-r1", "qwen-medium", "A", 1, "2A",
          p123(True, True, True), sec(760, 9600, 2900, 5200, {"read": 8, "edit": 3, "bash": 6}, 4, True, 21, 2, ["packages/react/compose-refs/src/composeRefs.tsx", "packages/react/compose-refs/src/composeRefs.test.tsx"]),
          tertiary={"root_cause": 2, "style": 2, "scale": 2, "judge": "blinded"})
write_run("radix", "dsv4-b-r1", "dsv4", "B", 1, "2A",
          p123(True, True, True), sec(512, 10400, 2500, 4900, {"read": 6, "edit": 2, "bash": 5}, 3, True, 22, 2, ["packages/react/compose-refs/src/composeRefs.tsx", "packages/react/compose-refs/src/composeRefs.test.tsx"]))
write_run("radix", "qwen-b-r1", "qwen", "B", 1, "2A",
          p123(True, False, True, p2r="full slot suite has 1 unrelated failure introduced by the edit (forwardedRef clone path)."),
          sec(1490, 9800, 4100, 14200, {"read": 14, "edit": 5, "bash": 11}, 7, True, 28, 4, ["packages/react/compose-refs/src/composeRefs.tsx"],
              events=[{"turn": 2, "type": "parse_error", "recoverable": True, "detail": "OpenCode emitted a malformed tool-call block (unterminated JSON); harness re-prompted and the model retried successfully."}]),
          tests_log=FAKE_TESTS_LOG_FAIL)
write_run("radix", "dsv4-c-r1", "dsv4", "C", 1, "2A",
          p123(True, True, True), sec(2210, 8900, 3100, 0, {}, 2, True, 22, 2, ["packages/react/compose-refs/src/composeRefs.tsx", "packages/react/compose-refs/src/composeRefs.test.tsx"]),
          session="lane_c")
write_run("radix", "qwen-c-r1", "qwen", "C", 1, "2A",
          p123(True, True, True), sec(3040, 9100, 3400, 0, {}, 3, True, 23, 2, ["packages/react/compose-refs/src/composeRefs.tsx", "packages/react/compose-refs/src/composeRefs.test.tsx"]),
          session="lane_c")

# ---- anyio: 2A, lanes A/B ---------------------------------------------------
ANYIO_DIFF = FAKE_DIFF.replace("composeRefs", "capacity_limiter").replace("slot", "synchronization")
write_run("anyio", "dsv4-a-r1", "dsv4", "A", 1, "2A", p123(True, True, True),
          sec(390, 7200, 1800, 3300, {"read": 5, "edit": 2, "bash": 4}, 3, True, 14, 1, ["src/anyio/_backends/_asyncio.py"]),
          diff_text=ANYIO_DIFF, tests_log="12 passed in 0.41s\n")
write_run("anyio", "dsv4-a-r2", "dsv4", "A", 2, "2A", p123(True, True, True),
          sec(410, 7300, 1900, 3500, {"read": 6, "edit": 2, "bash": 4}, 3, True, 15, 1, ["src/anyio/_backends/_asyncio.py"]),
          diff_text=ANYIO_DIFF, tests_log="12 passed in 0.44s\n")
write_run("anyio", "qwen-a-r1", "qwen", "A", 1, "2A", p123(True, True, True),
          sec(920, 7100, 2900, 8100, {"read": 8, "edit": 3, "bash": 6}, 5, True, 16, 1, ["src/anyio/_backends/_asyncio.py"]),
          diff_text=ANYIO_DIFF, tests_log="12 passed in 0.39s\n")
write_run("anyio", "qwen-a-r2", "qwen", "A", 2, "2A", p123(True, True, True),
          sec(880, 7000, 2800, 7600, {"read": 7, "edit": 3, "bash": 5}, 4, True, 15, 1, ["src/anyio/_backends/_asyncio.py"]),
          diff_text=ANYIO_DIFF, tests_log="12 passed in 0.37s\n")
write_run("anyio", "dsv4-b-r1", "dsv4", "B", 1, "2A", p123(True, True, True),
          sec(455, 7400, 2000, 3600, {"read": 6, "edit": 2, "bash": 4}, 3, True, 14, 1, ["src/anyio/_backends/_asyncio.py"]),
          diff_text=ANYIO_DIFF, tests_log="12 passed in 0.42s\n")
write_run("anyio", "qwen-b-r1", "qwen", "B", 1, "2A",
          p123(False, True, True, p1r="Reference test does not fail on the OpenCode worktree's base commit (env mismatch under investigation) -- CONFIG issue, not scored as a model loss per SCORING.md sec 1.3, but P1 fails as run."),
          sec(1510, 7200, 3300, 9200, {"read": 12, "edit": 4, "bash": 8}, 6, False, 18, 2, ["src/anyio/_backends/_asyncio.py"]),
          diff_text=ANYIO_DIFF, tests_log="11 passed, 1 failed in 0.51s\n")

# ---- hatetris: 2A, lane A only ----------------------------------------------
HT_DIFF = FAKE_DIFF.replace("composeRefs", "replay").replace("packages/react/compose-refs/src/", "src/")
write_run("hatetris", "dsv4-a-r1", "dsv4", "A", 1, "2A", p123(True, True, True),
          sec(340, 6100, 1600, 2900, {"read": 4, "edit": 1, "bash": 3}, 2, True, 11, 0, ["src/reducers/game.js"]),
          diff_text=HT_DIFF, tests_log="100% coverage. 41 passed.\n")
write_run("hatetris", "dsv4-a-r2", "dsv4", "A", 2, "2A", p123(True, True, True),
          sec(355, 6200, 1650, 3000, {"read": 4, "edit": 1, "bash": 3}, 2, True, 11, 0, ["src/reducers/game.js"]),
          diff_text=HT_DIFF, tests_log="100% coverage. 41 passed.\n")
write_run("hatetris", "qwen-a-r1", "qwen", "A", 1, "2A",
          p123(False, True, False, p1r="Frozen repro (replay D) still soft-locks after the model's fix -- the model handled a different replay path.",
               p3r="No new regression test added; existing suite stays green only because coverage gate ignores untouched branches."),
          sec(1290, 6300, 2900, 9800, {"read": 10, "edit": 4, "bash": 7}, 5, False, 9, 2, ["src/reducers/game.js"]),
          diff_text=HT_DIFF, tests_log="100% coverage. 41 passed.\n")
write_run("hatetris", "qwen-a-r2", "qwen", "A", 2, "2A", p123(True, True, True),
          sec(1150, 6200, 2700, 8900, {"read": 9, "edit": 3, "bash": 6}, 4, True, 13, 0, ["src/reducers/game.js"]),
          diff_text=HT_DIFF, tests_log="100% coverage. 42 passed.\n")

# ---- chessground: 2A hidden-ref #386, lane A only ---------------------------
CG_DIFF = FAKE_DIFF.replace("composeRefs", "board").replace("packages/react/compose-refs/src/", "src/")
write_run("chessground", "dsv4-a-r1", "dsv4", "A", 1, "2A", p123(True, True, True),
          sec(305, 5400, 1400, 2600, {"read": 4, "edit": 1, "bash": 3}, 2, True, 9, 1, ["src/board.ts"]),
          diff_text=CG_DIFF, tests_log="18 passed.\n")
write_run("chessground", "dsv4-a-r2", "dsv4", "A", 2, "2A", p123(True, True, True),
          sec(1290, 5500, 1450, 2650, {"read": 5, "edit": 1, "bash": 4}, 3, True, 9, 1, ["src/board.ts"],
              events=[{"turn": 2, "type": "harness_crash", "recoverable": False,
                        "detail": "OMP process killed by the 90m watchdog mid tsc compile; re-run once per SCORING.md sec 3, event kept in this report."}]),
          diff_text=CG_DIFF, tests_log="18 passed.\n")
write_run("chessground", "qwen-a-r1", "qwen", "A", 1, "2A", p123(True, True, True),
          sec(880, 5300, 2400, 7100, {"read": 8, "edit": 2, "bash": 5}, 4, True, 12, 1, ["src/board.ts"]),
          diff_text=CG_DIFF, tests_log="18 passed.\n")
write_run("chessground", "qwen-a-r2", "qwen", "A", 2, "2A", p123(True, True, True),
          sec(910, 5400, 2500, 7300, {"read": 8, "edit": 2, "bash": 5}, 4, True, 12, 1, ["src/board.ts"]),
          diff_text=CG_DIFF, tests_log="18 passed.\n")

# ---- chessjs: 2B live bug, lanes A/C -----------------------------------------
CJ_DIFF = FAKE_DIFF.replace("composeRefs", "chess").replace("packages/react/compose-refs/src/", "src/")
write_run("chessjs", "dsv4-a-r1", "dsv4", "A", 1, "2B", p123(True, True, True),
          sec(295, 5900, 1500, 2700, {"read": 4, "edit": 1, "bash": 3}, 2, True, 8, 0, ["src/chess.ts"]),
          p4={"status": "pending", "note": "PR opened 2026-08-20; 30-day outcome not yet known."},
          diff_text=CJ_DIFF, tests_log="211 passed.\n", session="html")
write_run("chessjs", "dsv4-a-r2", "dsv4", "A", 2, "2B", p123(True, True, True),
          sec(310, 6000, 1550, 2800, {"read": 5, "edit": 1, "bash": 3}, 2, True, 8, 0, ["src/chess.ts"]),
          p4={"status": "pending", "note": "PR opened 2026-08-20; 30-day outcome not yet known."},
          diff_text=CJ_DIFF, tests_log="211 passed.\n")
write_run("chessjs", "qwen-a-r1", "qwen", "A", 1, "2B", p123(True, True, True),
          sec(870, 5800, 2600, 7400, {"read": 7, "edit": 2, "bash": 5}, 4, True, 10, 0, ["src/chess.ts"]),
          p4={"status": "pending", "note": "PR opened 2026-08-20; 30-day outcome not yet known."},
          diff_text=CJ_DIFF, tests_log="211 passed.\n", session="omp-jsonl")
write_run("chessjs", "qwen-a-r2", "qwen", "A", 2, "2B",
          p123(True, False, True, p2r="Unrelated snapshot test regressed after the edit (promotion move ordering)."),
          sec(940, 5900, 2700, 7700, {"read": 8, "edit": 3, "bash": 6}, 5, True, 14, 1, ["src/chess.ts"]),
          diff_text=CJ_DIFF, tests_log="209 passed, 2 failed.\n")
write_run("chessjs", "dsv4-c-r1", "dsv4", "C", 1, "2B", p123(True, True, True),
          sec(1680, 5200, 1900, 0, {}, 2, True, 8, 0, ["src/chess.ts"]),
          diff_text=CJ_DIFF, tests_log="211 passed.\n", session="lane_c")
write_run("chessjs", "qwen-c-r1", "qwen", "C", 1, "2B", p123(True, True, True),
          sec(2340, 5400, 2100, 0, {}, 3, True, 9, 0, ["src/chess.ts"]),
          diff_text=CJ_DIFF, tests_log="211 passed.\n", session="lane_c")

# ---- deeweb: 2C private, lane A only, n=1 -----------------------------------
DEEWEB_CHECKLIST = [
    "Pinned chats always render in the backend-stored order, stable across refetches",
    "Pinning a new chat adds it to the end of the pinned section, never above older pins",
    "Unpinning keeps the remaining pins in their existing order",
    "Drag handles are not visible until the user turns on Edit",
    "In edit mode the user can check/uncheck to pin/unpin, and drag pinned chats to reorder",
    "Save persists both the new pin set and the new order in one request, and the order survives a reload",
    "Cancel leaves the pinned chats exactly as they were",
    "Outside edit mode, rows still open the chat on click",
    "The drag handle is reachable and operable by keyboard",
]
d = ROOT / "_runs" / "deeweb" / "dsv4-a-r1"
wj(d / "score.json", {
    "task": "deeweb", "label": "dsv4-a-r1", "model": "dsv4", "lane": "A", "rep": 1,
    "checklist": [{"label": c, "pass": p} for c, p in zip(DEEWEB_CHECKLIST, [True, True, True, True, True, False, True, True, True])],
    "checklist_extra": {"suite_green": True, "typecheck_clean": True, "lint_clean": False},
    "secondary": {"wall_s": 6100, "tokens": {"prompt": 41000, "completion": 12800, "reasoning": 26000},
                  "tool_calls": {"by_name": {"read": 34, "edit": 21, "bash": 19}, "total": 74},
                  "diff": diff_stats(1290, 118, ["ContactList/index.tsx", "ChannelMenu.tsx", "PinnedRow.tsx", "usePinnedOrder.ts", "usePinnedOrder.test.ts", "..."]),
                  "redirects": 3, "coderabbit": {"blocker": 0, "major": 1, "minor": 4}},
    "tertiary": {"ux_quality": 4, "code_quality": 4, "scale": 5, "judge": "Jason — NOT blinded, illustrative only"},
})
w(d / "final.diff", FAKE_DIFF.replace("composeRefs", "usePinnedOrder"))
w(d / "final-tests.log", "132 passed, 0 failed. lint: 2 warnings. typecheck: 1 error (PinnedRow.tsx:41).\n")
w(d / "driver.log", "[private lane -- driver log summary only]\n")

d = ROOT / "_runs" / "deeweb" / "qwen-a-r1"
wj(d / "score.json", {
    "task": "deeweb", "label": "qwen-a-r1", "model": "qwen", "lane": "A", "rep": 1,
    "checklist": [{"label": c, "pass": p} for c, p in zip(DEEWEB_CHECKLIST, [True, True, True, False, True, False, True, True, False])],
    "checklist_extra": {"suite_green": True, "typecheck_clean": True, "lint_clean": True},
    "secondary": {"wall_s": 9800, "tokens": {"prompt": 44000, "completion": 19100, "reasoning": 58000},
                  "tool_calls": {"by_name": {"read": 51, "edit": 33, "bash": 28}, "total": 112},
                  "diff": diff_stats(1610, 96, ["ContactList/index.tsx", "ChannelMenu.tsx", "PinnedRow.tsx", "..."]),
                  "redirects": 6, "coderabbit": {"blocker": 1, "major": 2, "minor": 6}},
    "tertiary": {"ux_quality": 3, "code_quality": 3, "scale": 5, "judge": "Jason — NOT blinded, illustrative only"},
})
w(d / "final.diff", FAKE_DIFF.replace("composeRefs", "usePinnedOrder"))
w(d / "final-tests.log", "128 passed, 4 failed. lint: 0 warnings. typecheck: clean.\n")
w(d / "driver.log", "[private lane -- driver log summary only]\n")

# ---- raptor: 2D ladder, lane A only, n=1 ------------------------------------
def milestone(mid, label, passed, time_to_s=None, ssim=None, palette=None):
    m = {"id": mid, "label": label, "pass": passed}
    if time_to_s is not None:
        m["time_to_s"] = time_to_s
    if ssim is not None:
        m["ssim"] = ssim
    if palette is not None:
        m["palette_coverage"] = palette
    return m

RAPTOR_MS = {
    "M1": "background + player ship render",
    "M2": "movement + fire",
    "M3": "wave-1 enemies + hit/death",
    "M4": "HUD + audio",
    "M5": "sector-1 loop",
}

d = ROOT / "_runs" / "raptor" / "dsv4-a-r1"
ms_dsv4 = [
    milestone("M1", RAPTOR_MS["M1"], True, 910, 0.84, 0.93),
    milestone("M2", RAPTOR_MS["M2"], True, 1540),
    milestone("M3", RAPTOR_MS["M3"], True, 3260, ssim=0.79),
    milestone("M4", RAPTOR_MS["M4"], False),
    milestone("M5", RAPTOR_MS["M5"], False),
]
wj(d / "score.json", {
    "task": "raptor", "label": "dsv4-a-r1", "model": "dsv4", "lane": "A", "rep": 1,
    "milestones": ms_dsv4, "milestones_reached": 3,
    "secondary": {"tokens": {"prompt": 210000, "completion": 88000, "reasoning": 61000},
                  "tool_calls": {"by_name": {"read": 140, "edit": 96, "bash": 71}, "total": 307},
                  "reverts": 2},
    "tertiary": {"fidelity": 4, "feel": 3, "scale": 5, "judge": "jason"},
})
w(d / "driver.log", "[raptor lane A driver log -- milestone commits M1..M3]\n")

d = ROOT / "_runs" / "raptor" / "qwen-a-r1"
ms_qwen = [
    milestone("M1", RAPTOR_MS["M1"], True, 1120, 0.81, 0.90),
    milestone("M2", RAPTOR_MS["M2"], True, 2380),
    milestone("M3", RAPTOR_MS["M3"], False, ssim=0.62),
    milestone("M4", RAPTOR_MS["M4"], False),
    milestone("M5", RAPTOR_MS["M5"], False),
]
wj(d / "score.json", {
    "task": "raptor", "label": "qwen-a-r1", "model": "qwen", "lane": "A", "rep": 1,
    "milestones": ms_qwen, "milestones_reached": 2,
    "secondary": {"tokens": {"prompt": 198000, "completion": 121000, "reasoning": 190000},
                  "tool_calls": {"by_name": {"read": 168, "edit": 122, "bash": 89}, "total": 379},
                  "reverts": 5},
    "tertiary": {"fidelity": 3, "feel": 2, "scale": 5, "judge": "jason"},
})
w(d / "driver.log", "[raptor lane A driver log -- milestone commits M1..M2, wave-3 enemy HP bug unresolved]\n")


# --------------------------------------------------------------------------
# _runs/calibration/<harness>/<label>.json
# --------------------------------------------------------------------------

CAL_ITEMS = ["READ", "EDIT", "RUN+READ OUTPUT", "CHAIN", "RECOVER"]

def cal_entry(harness, label, model, results, wall_s, prompt, completion):
    items = []
    for i, (name, ok, tc, pe) in enumerate(results, start=1):
        items.append({"id": i, "name": name, "pass": ok, "tool_calls": tc, "parse_errors": pe})
    wj(ROOT / "_runs" / "calibration" / harness / f"{label}.json", {
        "harness": harness, "label": label, "model": model, "items": items,
        "wall_s": wall_s, "tokens": {"prompt": prompt, "completion": completion},
    })

cal_entry("omp", "dsv4", "dsv4",
          [(n, True, tc, 0) for n, tc in zip(CAL_ITEMS, [1, 1, 2, 3, 4])], 52, 1400, 380)
cal_entry("omp", "qwen", "qwen",
          [(n, True, tc, 0) for n, tc in zip(CAL_ITEMS, [1, 2, 2, 3, 5])], 118, 1600, 520)
cal_entry("omp", "qwen-medium", "qwen-medium",
          [(n, True, tc, 0) for n, tc in zip(CAL_ITEMS, [1, 1, 2, 3, 4])], 74, 1500, 440)
cal_entry("opencode", "dsv4", "dsv4",
          [(n, True, tc, 0) for n, tc in zip(CAL_ITEMS, [1, 1, 2, 4, 4])], 61, 1450, 400)
cal_entry("opencode", "qwen", "qwen",
          [("READ", True, 1, 0), ("EDIT", True, 2, 0), ("RUN+READ OUTPUT", True, 2, 0),
           ("CHAIN", True, 4, 0), ("RECOVER", False, 3, 1)], 140, 1650, 560)

print(f"Fixture written to {ROOT}")
