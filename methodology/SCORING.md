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
Fixed budget per model: same number of scripted milestone turns and the same wall-clock cap (set before run; e.g. 6h).
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
