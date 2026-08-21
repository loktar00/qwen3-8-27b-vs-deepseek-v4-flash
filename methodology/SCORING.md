# Scoring spec — DeepSeek V4 Flash 0731 (Max) vs Qwen3.8-27B BF16, multi-turn
Pre-registered 2026-08-20 before any comparison run. Changes after the first run are logged at the bottom.

## 0. Principles
1. **Objective before subjective.** Every task has binary PASS/FAIL checks that a script decides. Human judgment is
   collected separately, labeled as such, and never overrides an objective result.
2. **Identical inputs.** Same brief text, same scripted follow-up turns (pre-written, triggered by state not by model),
   same tools, same worktree commit, same sampling (model-card), same turn/time budget. Effort settings declared:
   DSV4 = Max (server default, its only row). Qwen runs as TWO full scoreboard rows with equal standing, neither
   "primary" nor "secondary": the shipped default, which IS Qwen's highest effort tier (xhigh; verified 2026-08-14 via
   /tokenize render diff: default and xhigh render identically, medium/low differ), and `medium`, our standing
   day-to-day setting — launch-day evidence suggests `medium` avoids xhigh's over-thinking failure mode. Each model is
   thus compared at both its shipped default and its best-known configuration; see §5 for how a split result across
   the two Qwen rows is handled.
3. **Harness events are not model losses.** Malformed tool calls, parser errors and harness crashes are counted and
   reported as HARNESS events; a run killed by the harness is re-run once, and the event stays in the report.
4. **Publish everything:** raw session exports, diffs, test logs, this spec, calibration results, the scoreboard.
5. **Blinded judgment:** any rubric score is given on diffs/screens labeled A/B; the mapping is revealed after scoring.
6. **Context-ceiling asymmetry is disclosed per run.** Qwen serves 131k, DSV4 393k. Prompt-token usage is reported for every run; any run that exceeds 80% of a model's context ceiling is flagged CONFIG (per principle 3) and excluded from the PASS count, not scored as a loss.
7. **Vision is on for the model that has it.** Qwen3.8-27B is served multimodal (vision tower enabled; verified at
   calibration with an image request); DeepSeek V4 Flash 0731 is text-only. Harness entries declare Qwen as text+image
   input. Every task artifact a human would look at (Raptor DOSBox reference frames, UI screenshots, deeweb mock
   renders) is provided to BOTH models as files in the worktree — Qwen can view them, DeepSeek must reason from
   text/code or script its own pixel analysis. This is a real capability difference and is disclosed, not equalized
   away; no task is scored on image understanding per se — images are inputs, the checks stay the same.

## 1. Calibration gate (per model × per harness, before anything counts)
5 tool tasks (read / edit / run+read / 3-step chain / recover-from-error), see `calibration.md`. Required: 5/5 with
zero unrecoverable tool-call parse errors. Reported: tool calls, parse errors, wall time, tokens. A failing gate is a
CONFIG problem — fix and re-run; never compare on a failing gate.

## 2. Task classes and their checks

### 2A. Hidden-reference bug fixes — radix #3799, anyio #1170, HATETRIS #301, chessground #386
Primary (binary, scripted):
- **P1 Upstream test passes**: copy ONLY the upstream fix PR's test file(s) into the model's worktree and run them.
  Where upstream shipped no test (chessground #386), P1 = our frozen test in `_hidden/` (validated: fails pre-fix, passes on the
  merged fix).
- **P2 No regressions**: the repo's pre-registered suite command is green.
- **P3 Test honesty**: the model's own regression test exists, FAILS on the base commit, PASSES on its fix
  (we run it against both trees).
PASS = P1 ∧ P2 ∧ P3.
Secondary (measured): wall-clock; prompt/completion/reasoning tokens; tool calls; test runs; turns consumed (of the
scripted budget); diff size (LOC) and files touched vs upstream (precision = touched ⊆ upstream-touched-or-tests);
"reproduced before editing" (trace check: a failing test/script run precedes the first edit — yes/no); harness events.
Tertiary (blinded rubric, 0–2 each): root-cause match (addresses the same cause as upstream / a superset / a symptom
patch); code-style fit.
Disclosure: these are real historical issues on public repos whose fixes are public; either model may have seen them. Memorization is a confound we cannot remove, only disclose; the Raptor port (no prior port exists anywhere) and deeweb (private code) are the non-memorizable counterweights. anyio #1170's issue text, as filed, narrates its own fix mechanism — its root-cause rubric score is reported with that caveat. chessground #386's brief had the reporter's proposed patch removed before any run (2026-08-20).

### 2B. Live bugs — chess.js #577, chessground #322. (chessground #344 retired: its code path was removed upstream 2025-11-04; repro passes on HEAD. chess.js #574 retired before entering the task list: already fixed upstream via PR #546, "Fix forceEnpassantSquare for when there is no capturing pawn", merged 2025-07-09; repro of the issue's own example passes on HEAD.)
Same as 2A except P1 = **our pre-written reproduction test** built from the issue's repro (e.g. the exact FEN/`put`+
`moves()` sequence) passes; it is written and frozen BEFORE runs and kept in `_hidden/`. Plus a lagging indicator,
reported separately and never scored: **P4 upstream outcome** of a PR opened from the model's diff (merged /
changes-requested / no response, at 30 days).

### 2C. deeweb CAL-7207 (private; Jason drives in OMP; Claude's PR #1866 is the reference bar, hidden from the models)
**Phase 1 — design**: each model produces 3 static mockups from the ticket; Jason picks one blind (labeled A/B/C,
mapping revealed after) before any implementation begins. Subjective/illustrative only — not scored toward the verdict.
**Phase 2 — implementation**: the model implements the ticket's agreed direction; scored objectively per the checklist
below, against the reference PR. Everything under Primary/Secondary/Tertiary here applies to Phase 2.
Primary: the ticket's **9 acceptance criteria** as a checklist, each verified in the running app with the SAME manual
script (pin 4 → unpin 2 → pin 2 → reload → order check; Edit toggle; bulk check/uncheck; drag reorder; keyboard reorder;
Save = exactly one PATCH in the network tab; Cancel restores; rows open chat outside edit). Score /9. Plus suite green,
typecheck clean, lint clean (each binary).
Secondary: turns used; number of redirects Jason had to give (counted from the transcript); diff size and files touched
vs the reference (+1458/−126, 23 files); CodeRabbit findings by severity on each branch (the team's normal reviewer —
mechanical and already trusted).
Tertiary (Jason, NOT blinded — he drives the session and knows the model; reported as illustrative only, never part of the verdict, 1–5): UX quality vs the reference; code quality. 'Redirects needed' is likewise illustrative.
Published: aggregate scores only (company code).

### 2D. Raptor → web port ladder (shareware sector 1 only)
Fixed budget per model: the same 6 scripted milestone turns. Wall-clock is REPORTED (time-to-milestone) but is not a cap; the only time limit is a 4-hour-per-turn runaway guard applied identically to both models.
Primary: **highest milestone with its acceptance check passing** (0–5), each check scripted in Playwright against the
model's build:
- M1 level-1 background + player ship rendered on canvas from the real GLB data: screenshot similarity (SSIM) to a DOSBox
  reference frame ≥ 0.80 on the playfield region, AND ≥ 90% of the reference palette present.
- M2 arrow keys move the ship; fire spawns a projectile (DOM/canvas state hooks exposed on `window.__raptor`).
- M3 wave-1 enemies spawn; a projectile hit decrements enemy HP / removes an enemy; player can die.
- M4 HUD (score/shields) renders; Web Audio context running and ≥1 SFX triggered on fire.
- M5 sector-1 loop: wave counter advances to 9 and the sector-complete screen appears (autoplay harness allowed).
Secondary: time-to-each-milestone; tokens; tool calls; reverts/dead-ends (count of `git checkout -- .`/mass deletions);
SSIM at M1/M3.
Tertiary (Jason, 1–5): fidelity and feel.

## 3. Lanes
A = OMP (all tasks)  ·  B = OpenCode (radix, anyio — tool-heaviest; robustness check)  ·  C = no-harness scripted human
(chess.js #577, one hidden-reference task)  ·  D = existing 0-shots (control, already public).
Each lane reported separately. A ranking that flips between lanes is reported as "harness-sensitive", not averaged away.

## 4. Repetition
Bug-fix tasks (2A/2B): **n=2 runs per model** (different seeds), both reported; PASS rate out of 2. deeweb and Raptor:
n=1 (cost), stated plainly.

## 5. Aggregation and the verdict rule
Scoreboard rows = tasks, columns = model × lane; cell = PASS/FAIL (or milestone). Headline = count of primary PASSes
(and Raptor milestone). Ties broken by process efficiency (wall-clock, then tokens, then turns).
"**X is clearly better**" requires: X wins the majority of primary checks, AND no lane flips the ranking, AND the margin
survives both Qwen effort settings. Anything short of that is published as "no clear difference on these tasks" — the
honest outcome is an allowed outcome. A split result across the two full Qwen rows (e.g. DSV4 beats Qwen-xhigh but not
Qwen-medium) is reported as exactly that, not resolved into a single headline verdict.

## 6. What we will NOT do
- No cherry-picked reruns (every run is reported, including harness re-runs).
- No editing briefs/turns between models.
- No scoring by Claude alone: rubric items are Jason's, blinded; an optional third-model judge may be reported as an
  extra column, never as the verdict.

## Change log
- 2026-08-20 (pre-run): chessground #344 retired (path removed upstream 2025-11-04); chessground becomes hidden-ref #386 with our frozen leak test as P1.
- 2026-08-20 (pre-run, after adversarial review): Qwen-default-is-ceiling made explicit; context-ceiling CONFIG rule added; memorization + anyio-narration + deeweb-not-blind disclosures added; chessground brief stripped of the reporter's patch.
- 2026-08-20 (pre-run): §2C split into Phase 1 (design: 3 static mocks per model, Jason picks blind, subjective/illustrative) and Phase 2 (implementation of the ticket's agreed direction, objective checklist vs reference PR); Raptor ports to be published in one repository (both models' trees + per-milestone branches).
- 2026-08-20 (pre-run): Qwen served with vision enabled (DSV4 is text-only); image artifacts provided to both models; disclosed as a capability difference.
- 2026-08-20 (pre-run): clarified that both Qwen effort rows (default/xhigh and medium) are full scoreboard rows; verdict must hold under both.
- 2026-08-20 (pre-run): live task chessground #322 added (open, no public fix; frozen repro test validated to fail on HEAD — `eraseOnMovablePieceClick: false` does not stop `drawClear` from firing on an empty-square or opponent-piece click). chess.js #574 was investigated for the same slot and retired before entering the task list: the exact behavior the issue reports is already fixed upstream via PR #546 ("Fix forceEnpassantSquare for when there is no capturing pawn", merged 2025-07-09); the frozen chessjs checkout's HEAD (commit d43e668) is identical to origin/master, `git log -S _fenEpSquare` traces the fix to that PR, and a repro built directly from the issue's own example (`chess.move('e4'); chess.fen({forceEnpassantSquare:true})`) passes cleanly, as do edge cases (a-file/h-file pawns, Black's big pawn moves, undo, and a fen()/load() round-trip). No substitute issue was picked; §2B runs with two live bugs instead of three.
- 2026-08-20 (pre-run): project-level AGENTS.md/CLAUDE.md/.cursorrules removed from every model worktree in every lane (only anyio ships one) so harness lanes see identical instructions; personal/global instructions already excluded.
- 2026-08-20 (pre-run): Qwen re-served with official MTP speculative decoding in vLLM (method mtp, 1 draft token) for parity with DSV4's DSpark; Qwen calibration rows re-run on the final config.
- 2026-08-20 (pre-verdict, after first chessground #322 run): frozen repro-322 rewritten to be design-agnostic (any erase-related drawable flag set false must prevent erase on an empty-square click; defaults must still erase) — the original assumed the fix would reuse `eraseOnMovablePieceClick`, which penalized a valid new-flag design; affected runs re-scored.
- 2026-08-20 (pre-verdict, during runs): scorer execution bug fixed — the scorer shelled out via cmd.exe, which cannot launch `.venv/Scripts/python`; one anyio run had been scored FAIL on a setup error; the scorer now runs every task command through Git Bash (`bash -c`, explicit path); all affected runs re-scored.
- 2026-08-20 (pre-run calibration): calibration item 5 wording aligned across harnesses (the OpenCode probe lacked the "if it fails, fix it" clause OMP's had); item 5 re-run for the OpenCode rows.
- 2026-08-20 (pre-verdict, after first hatetris runs): hatetris #301 P1 switched from the upstream PR's test file to a frozen behavioral test (too-short replay → keypress moves the piece): the upstream tests are coupled to an unrelated button-testid refactor in the same PR and fail on any correct fix that does not replicate it (and their throws contaminate later tests in the file); the frozen test is validated fail-on-base / pass-on-upstream-fix / pass-on-both-DSV4-fixes; affected runs re-scored.
- 2026-08-20 (pre-verdict): audit of OMP session logs showed OMP's "auto" thinking level sent DeepSeek a top-level reasoning_effort of high/low on every lane-A run (DeepSeek's template renders the full Max preamble only for "max"), so no DeepSeek OMP run had actually been at Max; OMP sends no effort field to the Qwen provider at all, so the Qwen rows (server default xhigh; medium via the local proxy) were correct. Several DeepSeek runs also spawned OMP subagents, whose model roles come from the operator's OMP config rather than the model under test. Fix: DeepSeek's model ref pinned to ':max' (verified by prompt-token render), OMP's subagent/task tools disabled for every lane-A run (--tools read,write,edit,bash,grep,glob), all DeepSeek lane-A runs and the Raptor run archived and re-run; the four Qwen runs interrupted during the pause were also re-queued; two completed Qwen runs (anyio) kept as valid. OpenCode (lane B) gives no visibility into the effort it requests — disclosed as a blind spot; its runs send no effort field by default and are kept.
- 2026-08-20 (pre-verdict): lane-C scripted-human runner fixed (file-request parsing for list formats; apply-failure feedback with full-file fallback) after its first runs failed on harness mechanics; affected lane-C runs archived and re-run.
- 2026-08-20 (pre-verdict): Raptor budget clarified — scored on milestones reached within the same 6 scripted turns; wall-clock is reported, not capped; the only time limit is a 4-hour-per-turn runaway guard applied identically to both models (the earlier 90-minute per-turn setting would have penalized the slower model); both in-flight Raptor runs restarted under the new rule and the earlier attempts archived.
- 2026-08-21 (pre-verdict): lane-C runner crash fixed (Windows cp1252 decode of vitest's UTF-8 output killed the runner); Qwen-medium lane-C attempt 2 archived and re-run; all lane-C runs for a model row count only under the final runner.

- 2026-08-20 (scorer robustness, no rule change): `score_task.py` `run_shell` now kills the whole process tree on
  timeout (`taskkill /T /F`) instead of `subprocess.run(timeout=…)`, which on Windows kills only the direct bash
  child and then blocks forever waiting for the stdout pipe that an orphaned grandchild still holds. Trigger:
  hatetris/dsv4-r2's own test file spins forever (CPU-bound) in its own worktree; the P3 "model's own test passes
  in the model's worktree" step timed out at 300s as designed, but the scorer then hung on the orphaned node
  process. A test that never finishes inside the timeout is scored exactly as before: P3 = FAIL ("model's own
  test does not pass in the model's worktree"). The run was re-scored under the fixed scorer; no other run's
  result is affected (no other scoring hit a timeout).
- 2026-08-20 (pre-verdict): Lane B pre-`--agent ab` runs audited by tool-call name: anyio/dsv4-oc, radix/qwen-oc,
  anyio/qwen-oc clean (no task/webfetch/websearch/skill) and kept; radix/dsv4-oc used webfetch against GitHub issue
  search → archived (_invalid-harness-20260820) and re-run. Qwen-medium OpenCode lane verified landing medium:
  same-config probe first-step input 8580 (default) vs 8543 (:medium), Δ37 tokens, consistent with the template's
  ~40-token preamble delta.

- 2026-08-20 (pre-verdict): lane C (no-harness) budget clarified, same ruling as Raptor — the budget is the scripted
  exchange count (30 per task); wall-clock is reported, not capped; the only time limit is a 4-hour-per-run runaway
  guard applied identically to both models. Trigger: the lane-C runner's operator had armed an ad-hoc 60-minute
  wall-clock watchdog that was not in this spec; it killed chessjs/qwen-c after 3 of 30 exchanges (Qwen is ~4× slower
  per token than DeepSeek on our servers, so a wall cap bites only the slower model). That attempt is archived under
  `_invalid-harness-20260820/chessjs/qwen-c-wallcap60/` and re-run under the 4-hour guard. No DeepSeek lane-C run
  came within a factor of 2 of 60 minutes, so no DeepSeek lane-C result changes. For the same reason the lane-A per-turn
  OMP runaway guard (`--max-time`, 90 min, never triggered on any run so far) is raised to 240 min for the remaining
  matrix jobs; no finished run was affected.

- 2026-08-20 (pre-verdict, pre-committed BEFORE the calibration result): Raptor M5 checker calibration. DeepSeek's
  port passes M2-M4 but fails M5 because the checker's naive autoplay (hold fire, random arrow jitter every ~1.5 s,
  5-min cap, no survivability hook) is shot down in wave 1 — 3/3 reruns (113 s, 74 s, 75 s), never near the cap. The
  port's own sector-loop mechanics demonstrably work under its godmode flag, which the checker does not use. Before
  Qwen is scored, the identical naive policy is driven against the ORIGINAL game in DOSBox (3 runs, same speed
  settings as the reference capture). Decision rule fixed now: (a) original survives ≥2 min or completes the sector
  in ≥2 of 3 runs → checker is passable by a faithful-difficulty port, DeepSeek's M5 FAIL stands, Qwen scored with the
  identical checker; (b) original also dies in <2 min in ≥2 of 3 → checker is unpassable by construction, M5 autoplay
  is amended identically for both models to a state-aware dodge using only `window.__raptor` contract fields (same
  code and seed for both, 5-min cap unchanged, pass = wave 9 + sectorComplete), DeepSeek re-scored under it, both
  results carry the note. M1 is NOT amended: its frame-timing sensitivity (the screenshot lands at a different scroll
  offset than the reference frame) is disclosed on the ladder page as a limitation and applies identically.

- 2026-08-20 (pre-verdict): lane C context-ceiling handling made mechanical. chessjs/qwen-med-c (attempt 3) ended with
  an HTTP 400 from vLLM at exchange 15: prompt ≈100k tokens (the model repeatedly asked for the full 77k-char
  `src/chess.ts` to be re-pasted, which the scripted human does for either model) plus the runner's fixed 32,768-token
  completion budget exceeded Qwen's 131,072 ceiling. Harness change, identical for both models: the completion budget
  now shrinks as the prompt grows (`min(32768, ceiling − prompt − 2048)`, the behaviour OMP/OpenCode already have), and
  a run whose prompt reaches 80% of its model's ceiling stops cleanly and is marked CONFIG (marker file `CONFIG.txt`)
  per §1 principle 6 — excluded from the PASS count, neither pass nor fail, counted as a completed planned run, shown
  as "CONFIG" on the board with the reason. The crashed attempt is archived under
  `_invalid-harness-20260820/chessjs/qwen-med-c-attempt3/`; attempt 4 runs under the patched runner. DeepSeek's lane-C
  runs (complete) never exceeded ~25% of its 393k ceiling and are unaffected.

- 2026-08-20 (pre-verdict, outcome of the pre-committed M5 calibration): the ORIGINAL shareware Raptor, driven in DOSBox
  (unmodified raptor.conf, same cycles as the reference capture) by the checker's exact naive policy (hold fire, one random
  arrow tap every 1.5 s), is destroyed in under 30 s in 3 of 3 runs (alive→dead at 3–6 s, 12–18 s, 18–24 s; never near
  sector-complete). Branch (b) applies: the M5 checker was unpassable by construction. Amendment, identical for both
  models: the M5 autoplay becomes a state-aware dodge that reads only `window.__raptor` contract fields (player x/y,
  alive enemies' x/y; enemy shots only if the contract marks them), steers toward the least-threatened reachable
  x-column each 100 ms, keeps firing, seeded PRNG, no survivability hook (`player.alive===false` still ends the run as a
  death); session cap 300 s → 600 s as a guard; pass = wave 9 reached AND sectorComplete within the cap; 3 attempts per
  model, pass if any attempt passes (the autoplay is the instrument, not the subject). Checker version recorded in each
  score.json; DeepSeek re-scored under the amended checker before Qwen is scored; DeepSeek's pre-amendment M5 result is
  kept in score.json as `m5_pre_amendment`. Calibration logs and frames are archived in the private raptor-web-ab repo.
  Process note: the calibration drove a visible DOSBox window on the operator's desktop and disrupted it — any future
  calibration must run headless/off-desktop; no other result depends on the desktop.

- 2026-08-20 (pre-verdict, Jason's call): deeweb CAL-7207 §2C simplified — Phase 1 (three static mocks per model + blind pick)
  is DROPPED. Each model gets one automated OMP session on its own branch from the same base commit (1f680c659), same
  prompt (the ticket text of `_briefs/deeweb/brief.md` above its judge section, verbatim), same flags as lane A
  (`--no-extensions --no-skills --no-rules`, tools read/write/edit/bash/grep/glob, DeepSeek at `:max`, Qwen at its
  default xhigh), and implements the ticket choosing its own UX. Scored by the unchanged 9-criteria checklist against the
  shipped PR #1866 (objective), plus a disclosed subjective UX note. Runs are driven by an agent, not by hand; company
  code never leaves the machine (only the ticket text and the per-criterion verdicts are published). DeepSeek runs first
  while its server is otherwise idle; Qwen runs on the Qwen server(s) afterwards.

- 2026-08-20 (pre-verdict, infra event): the DeepSeek vLLM server crashed on its own at 20:33:08 EDT (CUDA device-side
  assert during CUDA-graph capture; it returned one 500 and exited; nothing listened on its port afterwards). Runs that
  overlapped the crash are audited from their transcripts: chessjs/dsv4-r1 (20:30–20:37) and chessjs/dsv4-r2
  (20:32–20:48) are SUSPECT and, if the transcripts show server errors, are archived under
  `_invalid-infra-20260820/` and re-run when the server is restored — an infra failure is never scored as a model
  result; raptor/dsv4 (ended 20:32) is checked for a clean final turn. The lane-B radix/dsv4-oc re-run (started 20:56
  against the dead server) is archived as a harness/infra stall and re-run. While DeepSeek is down and all its other
  lane-A work is complete, once its remaining jobs are finished its two GPUs serve a second Qwen instance (qwen-b: byte-identical vLLM launch
  to the original Qwen server except `--tensor-parallel-size 2` on those two GPUs and the port; same weights, same
  generation-config override, MTP, vision) so queued Qwen jobs run on a faster per-stream server in addition to the
  original one. This is a serving-capacity change only: no model, sampling, or context change; which
  replica served a run is recorded in its driver.log (model ref). DeepSeek is restored with its original launch script
  for its remaining jobs (chessjs re-runs, lane-B radix, deeweb) before the matrix is declared complete.
  Audit outcome (transcripts, read-only): chessjs/dsv4-r1 — first error 20:33:08.876, its final scripted turn (turn 3) ran
  entirely after the crash as 11 failed agent-loop attempts with 0 tool calls/0 tokens; chessjs/dsv4-r2 — first error
  20:33:08.695 inside turn 0 after 63 real tool calls, turns 1–3 entirely empty retry loops. Both → INFRA-CONTAMINATED,
  archived under `_invalid-infra-20260820/chessjs/`, re-run with the restored server. raptor/dsv4 — no error signature in
  any of its 6 turns, last turn ended 20:32:37 (≈30 s before the crash) → VALID. Lane-B radix/dsv4-oc (two attempts, 20:56
  and 21:50, both against the dead server, 0 output) → archived as harness/infra stalls, re-run with the restored server.

- 2026-08-20 (pre-verdict, sampling-parameter audit — disclosure, no change): no harness (OMP verified from captured raw
  request bodies; OpenCode from config + transcripts; lane C from code) sends temperature/top_p/top_k/min_p/penalties; both
  models receive identical, sampling-free requests in every lane, and the server-side `--override-generation-config`
  applies. Effective sampling — DeepSeek V4 Flash: temperature 1.0, top_p 0.95 (= the vendor's "agentic scenarios"
  recommendation; top_k/min_p/penalties at vLLM defaults, no vendor guidance). Qwen3.8-27B: temperature 1.0, top_p 0.95,
  top_k 20, min_p 0, presence 0, repetition 1.0 (= the model's shipped generation_config; matches the vendor card's
  "Thinking – General Tasks" profile except presence_penalty 0 vs 1.5). The vendor card's "Thinking – Precise Coding"
  profile recommends temperature 0.6 (presence 0); it was NOT used. Disclosed as a possible, unquantified disadvantage for
  Qwen on these coding tasks. Not changed mid-run: a sampling change is a model-config change and would invalidate every
  Qwen run completed so far; a post-completion spot-check at temperature 0.6 is an optional extra, budget permitting.
  Note: vLLM 0.27.1 does not log per-request SamplingParams; evidence is the launch command lines, startup "non-default
  args" lines, and OMP's captured request bodies.

- 2026-08-20 (pre-verdict, duplicate dispatch): run_matrix.sh re-dispatched anyio/qwen-r2 at 21:37 although that job had
  completed at 20:16 and been scored (PASS) — the earlier run had been launched outside the matrix's own state. The
  second dispatch reused the existing worktree and therefore started from the first run's uncommitted edits (its test-file
  insertions stacked 61→127), so it is not an independent repetition. Rule applied: the FIRST valid run per (task, model,
  rep) is canonical; the duplicate is quarantined under `_runs/_invalid-dup-20260820/anyio/qwen-r2-dup/` and excluded. The run
  dir and worktree were restored to the first run's end state (its final.diff recovered from the public repo history, its
  OMP session transcript intact; its raw turn-*.json captures were overwritten and are lost) and the first run was
  re-scored on the restored tree to confirm the recorded PASS. No other job was dispatched twice (verified from the
  matrix state and driver.logs).

- 2026-08-20 (pre-verdict, harness event): radix/qwen-r2 (started 19:32, before the per-turn OMP runaway guard was raised
  from 90 to 240 min) had its third scripted turn aborted by the old 90-minute guard at 88m44s ("Deadline exceeded",
  mid-reasoning); the driver still recorded rc=0 and DONE, so the scorer's transcript check (stopReason/errorMessage per
  turn), not the exit code, is what catches this. Archived under `_invalid-harness-20260820/radix/qwen-r2-guard90/` and
  re-run under the 240-min guard; its sibling radix/qwen-r1 completed normally (longest turn 62 min). This is the only run
  the old guard truncated (all other finished runs audited: no turn ≥ 85 min, no abort events).
  Executed 22:46 EDT: DeepSeek server stopped (all its planned runs complete: lane A 12, lane B 2, lane C 1, Raptor, deeweb); a second Qwen
  instance (qwen-b, `--tensor-parallel-size 2`, otherwise byte-identical launch; verified in its startup log: same MTP config and the same
  generation-config override) came up on those GPUs at ~127 tok/s single-stream vs ~71 on the original; the remaining queued Qwen lane-A
  jobs and Qwen's deeweb session run there. Runs already in flight on the original Qwen server (lane C, Raptor, several lane-A) continue
  there untouched. Each run's driver.log records the model ref (server) it used.

- 2026-08-20 (pre-verdict, harness event): chessjs/qwen-c attempt 3 (started 20:58, i.e. on the lane-C runner BEFORE its
  dynamic-completion-budget/CONFIG patch at 21:03) crashed at exchange 8 with an unhandled HTTP 400 when prompt (~95k
  tokens) + the fixed 32,768-token completion budget exceeded Qwen's 131,072 ceiling — the exact failure the patch
  prevents. Harness failure, not a model result: archived under `_invalid-harness-20260820/chessjs/qwen-c-oldrunner400/`
  and re-run under the patched runner (same model, on the second Qwen instance), 4-hour guard. The chessjs/qwen-med-c
  attempt 4 ran on the patched runner and ended CONFIG by the 80% rule as recorded above.

- 2026-08-20 (pre-verdict, secondary-metrics restatement — pass/fail unaffected): an audit of the scorer's SECONDARY
  metrics found three defects in `score_task.py` (analyze_events / secondary_metrics): (1) token totals were read from the
  wrong event type, so prompt/completion token sums were null for every run; (2) tool-call counts counted every streaming
  snapshot of a call instead of distinct call ids (≈3.5–4× inflation); (3) LOC/files came from final.diff, which for a
  run that committed mid-session covers only the delta since its last commit. Fix: usage taken from message_end events
  (summed across assistant API calls — "input tokens billed across all calls", since context is re-sent each call);
  tool calls deduplicated by id; LOC/files computed base commit → final working tree (plus untracked files the model
  created, lockfiles excluded) with the number of mid-run commits recorded. All already-scored runs have their
  `secondary`/`events` fields recomputed in a tests-free "secondary-only" pass (`secondary_version: 2`,
  `secondary_restated_at`); P1/P2/P3/overall results are untouched. Previously published token/tool-call/LOC figures
  were wrong and are superseded; wall-clock figures were correct throughout.

- 2026-08-20 (disclosure, publication incident): the site generator copied every task's run artifacts (final diff,
  session transcript) into the public site's `data/` directory; for the deeweb task — whose company source code is
  private by rule — this published DeepSeek's diff and transcript for roughly 30–40 minutes (from the first site push
  after that run finished until the fix). Remediation: the generator now treats private tasks structurally (no artifact
  copy, no diff/transcript links or previews — only the judge's publishable verdicts, notes and mock-data UI screenshots),
  the affected paths were removed from the public repository's entire history (rewrite + force push, no external clones
  existed) and a cache purge was requested from GitHub. No benchmark result is affected.

- 2026-08-20 (pre-verdict, CORRECTION to §1 principle 6 — context ceilings): the original text said "Qwen serves 131k,
  DSV4 393k" as if those were the models' limits. They were our serving settings. Qwen3.8-27B's native context is 262,144
  tokens (config.json, no RoPE scaling applied); we launched its server with `--max-model-len 131072` — half the native
  window — while DeepSeek V4 Flash (native 1,048,576 via YaRN) was served at 393,216. This under-provisioned Qwen. Effect
  so far: the only runs that reached the cap are the two chess.js no-harness (lane C) Qwen runs (one CONFIG at 126,977
  tokens, one crash on the pre-patch runner); every lane-A/B Qwen run stayed below 80% of 131k per API call (the CONFIG
  flag never fired), and a compaction audit of every Qwen run (OMP/OpenCode compaction events, max prompt per call) is
  being recorded alongside this entry. Remedy: the second Qwen instance is restarted at `--max-model-len 262144` (the
  native maximum; KV capacity verified) as soon as the runs on it finish; both lane-C chess.js Qwen runs are re-run
  uncapped (the earlier CONFIG result is archived under `_invalid-config-cap131k/`, not counted); any remaining Qwen
  work is routed to the uncapped instance. The original Qwen instance (131k) is not restarted mid-run because Qwen's
  Raptor session is attached to it; whether that run was compaction-constrained is reported from its transcript.
  Ownership of the error: the orchestrator (pre-registered the serving cap without checking the model card).

- 2026-08-20 (publication hygiene, no result impact): (a) the public copy of the deeweb brief is reduced to the ticket
  text the models received, with file-path pointers and internal references redacted (the models saw them; readers do
  not); (b) one radix/qwen-r1 transcript captured a directory listing of an unrelated private folder reachable from the
  sandbox (filenames only); it is redacted in the published copy and removed from the public repository's history, and
  the sandbox weakness (models' shell can list sibling folders) is disclosed.
  Compaction audit (raptor): DeepSeek's run — 0 compaction events, max single-call input 329,131 tokens (393k window);
  Qwen's run under the 131k cap — 21 OMP auto-compaction cycles in its first scripted turn alone (3 overflow, 18
  threshold; 18 with "dead-end recovery" re-summarization), max single-call input 109,581 — i.e. the cap materially
  constrained Qwen on the one task built around a large, growing codebase. Ruling: Qwen's Raptor run is RE-RUN from
  scratch on the native-context (262,144) server with the harness window set to 262,144, same 6-turn budget and checks;
  the capped run is completed and scored for the record but kept under `_extra-capped-131k/`, excluded from results.
  Update (Jason's call, 2026-08-20 ~23:45 EDT): the capped Qwen Raptor run is KILLED rather than completed (cost), its
  partial run dir kept under quarantine for disclosure only; the uncapped re-run uses Qwen at MEDIUM thinking effort
  (`pod-qwen-b-medium`, reasoning_effort=medium injected; server at the native 262,144 context with the harness window
  set to match) — so on Raptor, DeepSeek ran at its max effort and Qwen at medium. This is a cost decision by the study
  owner after the context-cap error made the xhigh run unusable; it is an asymmetry in Qwen's disfavor and is stated
  wherever the Raptor result appears. Same 6 scripted turns, same checker version, same 3×M5 rule.
  Compaction audit (lanes A/B, all 41 finished runs): Qwen — 16 OMP compactions across 27 runs (max 4 in one run; max
  single-call input 98,588 — OMP compacts at ≈75% of its configured window, so Qwen's calls clustered at 96–98k);
  DeepSeek — 16 compactions across 14 runs (triggered at 45–92k, i.e. not by its window; two radix runs used 133k–191k
  context with no compaction). Conclusion: outside Raptor the 131k cap did not produce a one-sided handicap; no lane-A/B
  re-runs. Lane-B (OpenCode) compaction detection is uncertain (no explicit event type) and is stated as such.

- 2026-08-21 (disclosure, presentation only): the results site's visual design (palette, typography, logo badges,
  milestone "metro" strip, table styling) was produced by Qwen3.8-27B (FP8, on the study owner's local server) in a
  sandboxed session and merged by hand; data, wording, counts, the no-verdict gate and the privacy rules are unchanged by
  it. Logo marks are the models' public GitHub organisation avatars, used for identification only.

- 2026-08-21 ~00:25 EDT (study owner's call, cost): the lane-C (no-harness) chess.js run for Qwen at xhigh effort is
  CANCELLED after its two earlier attempts were invalidated by the serving cap / pre-patch runner; it is reported as
  "not run — cancelled for cost" and the planned total becomes 48 runs. The lane-C chess.js Qwen-medium run continues
  (uncapped). Completeness for the verdict gate is 48/48.

- 2026-08-21 00:40 EDT (deeweb §2C subjective part): both implementations pass the 9-criteria checklist 9/9. The study
  owner's disclosed subjective UX pick is Qwen's approach ("the same approach I took" in the shipped PR); the judge also
  notes, for Qwen, a "Done" control in the PINNED heading that discards (acts as Cancel) while the real Save/Cancel pair
  sits at the bottom of the list. Recorded in both judgment files as `owner_ux_pick`; shown on the site as subjective.
