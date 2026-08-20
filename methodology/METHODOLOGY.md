# Methodology: DeepSeek-V4-Flash-0731 vs Qwen3.8-27B — a multi-turn coding comparison

This document explains how we compared two models on real coding work, in enough detail to
check our work or repeat it yourself. It's written for readers who are (rightly) skeptical of
one-shot demos and marketing benchmarks. It summarizes the pre-registered scoring spec in
[`SCORING.md`](./SCORING.md); if the two ever disagree, `SCORING.md` is the source of truth.

## 1. Why this exists

A tweet claimed DeepSeek-V4-Flash (at its "Max" reasoning setting) beats Qwen3.8-27B in
real-world multi-turn use. That's testable, and testing it properly means committing to a
scoring method *before* running anything, so the outcome can't be shaped after the fact to fit
a preferred conclusion. `SCORING.md` was written and time-stamped on 2026-08-20, before any
comparison run started; every change since is logged and dated at the bottom of that file.

## 2. What's being compared

Both models were served on a single rented cloud pod (3×H200 GPUs), with vLLM 0.27.1, so
neither one gets a hardware advantage:

**DeepSeek-V4-Flash-0731** — 2×H200, tensor-parallel degree 2 with expert parallelism, FP8 KV
cache, DSpark speculative decoding (bundled in the checkpoint), `max-model-len` 393,216 tokens.
Reasoning effort "max" is this model's own server default, set via chat-template kwargs — we
didn't dial it up. Sampling (temperature 1.0, top_p 0.95) is the model card's recommendation.
Measured throughput: ~300 tok/s.

**Qwen3.8-27B (BF16)** — 1×H200, 131,072-token context, sampling per the model card, reasoning
parser `qwen3`, tool parser `qwen3_coder`. Qwen runs as **two full scoreboard rows with equal
standing**, neither one a fallback for the other: the shipped default, which is Qwen's
*highest* effort tier, `xhigh` — verified, not assumed: rendering the chat template with the
default and with `xhigh` explicitly set produces identical output — and `medium`, our own
day-to-day setting, which launch-day evidence suggests avoids `xhigh`'s over-thinking failure
mode. Each model is compared at both its shipped default and its best-known configuration; §7
covers how a split result between the two Qwen rows is reported. Qwen is also served with its
official MTP speculative-decoding head enabled in vLLM (`--speculative-config
'{"method":"mtp","num_speculative_tokens":1}'`; the MTP weights ship inside the official
checkpoint) for parity with DeepSeek's bundled DSpark draft model. Measured throughput: ~64-67
tok/s without MTP; with MTP: *to be measured at calibration*.

**One deliberate asymmetry: Qwen is served with vision enabled** (`--language-model-only` is
NOT set, verified at calibration with a live image request); DeepSeek-V4-Flash-0731 is
text-only. Not an oversight — Jason wants Qwen compared at its full real capability. Both
harness model entries declare their true modality, and every image artifact a task uses
(Raptor's DOSBox reference frames, UI screenshots, deeweb mock renders) goes to *both* models as
a worktree file: Qwen looks at it directly, DeepSeek reasons from text/code or scripts its own
pixel analysis. A real capability gap, disclosed rather than papered over — see §6.

Both models get the same tools, worktree commit, turn/time budget, and scripted follow-up text.
Modality aside, the only thing that varies between a DeepSeek run and a Qwen run is the model.

## 3. Harness lanes

A model's behavior isn't only a function of the model — the harness around it (how tool calls
are parsed, what system prompt gets assembled, how errors are recovered) matters too. So every
task runs through more than one harness, and lanes are reported separately, never averaged
together. A ranking that flips between lanes is reported as "harness-sensitive," not smoothed
over.

- **Lane A — OMP** (oh-my-pi v17.3.5, our daily tool), run vanilla
  (`--no-extensions --no-skills --no-rules`), identical flags for both models. Every task.
- **Lane B — OpenCode** (v1.14.29), vanilla config, its "Claude Code compatibility" layer
  explicitly disabled (`OPENCODE_DISABLE_CLAUDE_CODE=1`) — left on, it silently pulls in our
  personal global config, making the lane non-reproducible for anyone else. The two most
  tool-heavy tasks (radix, anyio), as a robustness check.
- **Lane C — no-harness chat.** Plain chat-completions API, zero tools. A scripted human (a
  Python script, not a person improvising) pastes files, applies the model's diffs, runs tests,
  and pastes output back — only what a developer at a chat box would do. Same script for every
  model. One hidden-reference task and the live chess.js bug.
- **Lane D — existing one-shots.** The already-public single-prompt demos, as a control point,
  not head-to-head data.

## 4. The tasks

Every bug-fix task (2A and 2B below) carries the identical standing instructions, quoted here
verbatim from the brief:

> You are working in the repository at the current working directory. Work like a careful
> open-source contributor:
> 1. Reproduce the bug first (write a minimal failing test or script) before changing code.
> 2. Find the root cause; fix the cause, not the symptom. Keep the change minimal and in the
>    project's style.
> 3. Add or update a regression test that fails before your fix and passes after.
> 4. Run the project's test suite and make it green. Do not modify or delete unrelated tests.
> 5. When done, summarize: root cause, the files you changed, how you verified it.
>
> Do not ask me for permission between steps; proceed until the task is complete, then report.

### 4A. Hidden-reference bug fixes

Four real, historical GitHub issues with a real, already-merged upstream fix: radix-ui `Slot`
infinite-loop (#3799), anyio `CapacityLimiter` over-granting tokens (#1170), HATETRIS replay
soft-lock (#301), and chessground's `ResizeObserver` leak (#386 — the reporter's own proposed
patch was stripped from the brief first). "Hidden-reference": the model never sees the upstream
fix, but we have it and score against it. Scoring is binary and scripted, not vibes:
- **P1** — the upstream fix PR's own test file(s), copied into the model's tree, pass. (Where
  upstream shipped no test, as with chessground, P1 is our own frozen test, pre-validated to
  fail before the fix and pass after.)
- **P2** — the full pre-registered test suite is green (no regressions).
- **P3** — the model's *own* regression test fails on the unfixed code and passes on its fix
  (we run it against both trees to confirm).

PASS requires all three. Secondary numbers (wall-clock, tokens, tool calls, turns, diff size,
whether the model reproduced the bug before editing) and a blinded tertiary rubric (root-cause
match, code-style fit), scored on anonymized A/B diffs and revealed only after, are also recorded.

### 4B. Live open bugs

The same treatment applied to bugs with **no existing public fix**: chess.js #577 (BigInt error
generating pawn moves on edge ranks), and chessground #322 (`eraseOnMovablePieceClick`, the
option the issue calls `eraseOnClick`, is ignored on any empty-square or opponent-piece click —
drawings are cleared regardless of the setting). Here P1 is a repro test written
and frozen *before* any run, built directly from the issue's reported repro steps. We also
track, separately and never scored, whether a PR opened from the model's diff is later merged
upstream (P4, checked at 30 days) — a real-world signal, but a lagging one that can't
retroactively change a published verdict.

### 4C. deeweb CAL-7207 (private company task)

Real company code: Jason drives the session by hand in OMP rather than the automated harness,
and only aggregate scores are published — no company source. Runs in two phases:

- **Phase 1 — design.** Each model produces three static mockups from the ticket. Jason picks
  one blind (mockups labeled A/B/C, mapping revealed after the pick). This is subjective and
  illustrative only — it does not feed the verdict.
- **Phase 2 — implementation.** The model implements the agreed direction; scored objectively —
  the ticket's 9 acceptance criteria as a checklist, verified in the running app with the same
  manual script, plus suite/typecheck/lint, against a real, already-merged reference PR (#1866)
  hidden from both models. Secondary numbers (turns, redirects Jason had to give, diff size vs.
  the reference) and a non-blinded tertiary rubric (Jason drives the session and knows the
  model — illustrative only, never the verdict) round it out.

### 4D. Raptor: Call of the Shadows → HTML5 canvas port

The counterweight to memorization risk: porting the shareware sector-1 levels of a 1994 DOS
shooter (GPL-licensed source) to an HTML5 canvas — something, as far as we could find, never done
before. Both models get the same fixed budget of scripted milestone turns and wall-clock cap.
Progress is milestone-based (M1 rendering → M2 controls → M3 combat → M4 HUD/audio → M5 full
sector loop), each with a scripted, automated check (Playwright, SSIM against a reference DOSBox
frame, exposed state hooks) — not a human's impression of "does it look right." Both ports are
published in one repository, as separate trees with per-milestone branches, so any claimed
milestone can be checked against the actual commit.

## 5. Calibration gate

Before any head-to-head result counts, each model/harness pairing clears a calibration gate:
five basic tool-use tasks (read, edit, run+read output, a three-step chain, recover from an
error — full spec in [`calibration.md`](./calibration.md)), 5/5 correct with zero unrecoverable
tool-call parse errors required. A failing gate is a harness/config problem, not a model loss —
it's fixed and re-run, never used as a comparison point.

## 6. Fairness controls and disclosures

A few rules we committed to before running anything:

- **Harness events aren't model losses.** A malformed tool call or a harness crash is a logged
  HARNESS event; a run the harness kills is re-run once, and the event stays in the report.
- **Context-ceiling asymmetry is disclosed.** Qwen's context window (131k) is smaller than
  DeepSeek's (393k). Prompt-token usage is reported per run; crossing 80% of a model's ceiling
  is flagged CONFIG and excluded from the PASS count — not scored as a loss.
- **Modality asymmetry is disclosed, not equalized away.** Qwen is served with vision; DeepSeek
  is text-only. Image artifacts go to both models as worktree files regardless — no task is
  scored on image understanding for its own sake, images are inputs, and the same PASS/FAIL
  checks apply either way.
- **Memorization is a real confound we can't remove, only disclose.** The hidden-reference tasks
  are public issues with public fixes; either model may have seen them in training. Raptor and
  deeweb are the counterweights — neither has a public solution to memorize.
- anyio's issue text, as filed, narrates its own fix mechanism — its root-cause rubric score
  carries that caveat.
- deeweb's tertiary rubric isn't blind, since Jason drives that session and knows the model;
  published as illustrative only, never part of the verdict.
- Bug-fix tasks (4A/4B) run **twice per model**, different seeds, both reported. deeweb and
  Raptor run once each, for cost — stated plainly, not implied equivalent rigor.

## 7. The verdict rule

The scoreboard is tasks × (model × lane), each cell a PASS/FAIL or a milestone number. We only
publish "**X is clearly better**" if X wins the majority of primary checks, no lane flips the
ranking, and the margin holds under both of Qwen's effort settings. Anything short of that is
published as "no clear difference on these tasks" — an allowed, honest outcome, not a failure. A
split result across the two Qwen rows — say, DeepSeek beats Qwen-xhigh but not Qwen-medium — is
reported as exactly that, not smoothed into a single headline number.

We also committed to a few things we will *not* do: no cherry-picked re-runs (every run is
reported, including harness-forced ones); no editing briefs or scripted turns between one
model's run and the other's; no scoring by Claude alone — every rubric score is Jason's, given
blind, with an optional third-model judge reported as an extra column, never as the verdict.

## 8. How to reproduce this

You'll need two models behind OpenAI-compatible endpoints (we used a rented multi-GPU cloud pod
tunnelled to localhost — substitute your own hardware/provider) and a local clone of the target
repositories.

```bash
# Lane A (OMP): worktree per task/model, run brief + scripted turns, export session
bash run_omp_task.sh <task> <model-ref> <label>   # e.g. radix pod-dsv4/deepseek-v4-flash-0731 dsv4

# Lane B (OpenCode): same semantics, OpenCode CLI shape
bash run_opencode_task.sh <task> <model-ref> <label>

# Lane C (no-harness chat): scripted human, plain chat completions, zero tools
python lane_c_runner.py --task tasks/<task>.json --model <dsv4|qwen|qwen-medium>

# Score any run against the pre-registered checks
python score_task.py <task> <label>       # or --all for every run + a scoreboard.md
```

`<task>` is one of `radix | anyio | hatetris | chessground | chessjs`; briefs and scripted turns
for each live under `_briefs/<task>/brief.md` and `turns.json`, so the exact prompt text is
inspectable, not paraphrased. Every run's raw session export, final diff, and test log is
published alongside the scoreboard — nothing is summarized-only. For the precise scoring logic
and running change log behind every number in this document, see [`SCORING.md`](./SCORING.md).
