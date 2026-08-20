# Qwen3.8-27B vs DeepSeek V4 Flash 0731 — Multi-Turn Coding A/B

**RUNS IN PROGRESS — scoreboard updates as jobs finish.**

This repo tests a claim that DeepSeek V4 Flash at Max beats Qwen3.8-27B in real-world
multi-turn use. Rather than argue about it, we built a pre-registered methodology and ran
both models head-to-head on the same real-world multi-turn coding tasks: real GitHub
issues on real open-source repos, a from-scratch HTML5 game port, and a real internal web
ticket (results for that last one are limited to score data — see below).

- **Live scoreboard:** https://loktar00.github.io/qwen3-8-27b-vs-deepseek-v4-flash/
- **Methodology:** [methodology/METHODOLOGY.md](methodology/METHODOLOGY.md)
- **Scoring rubric:** [methodology/SCORING.md](methodology/SCORING.md)
- **Calibration notes:** [methodology/calibration.md](methodology/calibration.md)
- **Companion repo (Raptor HTML5 port, private until publish):** https://github.com/loktar00/raptor-web-ab

## What's in this repo

| Path | Contents |
|---|---|
| `docs/` | The built scoreboard site (GitHub Pages source) |
| `methodology/` | Pre-registered methodology, scoring rubric, calibration notes |
| `harness/` | All scripts used to run and score the tasks |
| `tasks/` | Task briefs and the exact multi-turn prompt scripts (`turns.json`) given to each model |
| `answer-keys/` | Upstream fix diffs, frozen repro tests, and issue data — withheld from the models at run time, published here for verifiability |
| `calibration/` | Raw calibration run data used to sanity-check the harness before the real matrix |
| `runs/` | Raw per-task, per-model results: diffs, test logs, driver logs, session transcripts |
| `raptor-support/` | Reference material for the Raptor HTML5 port task (screenshots, format notes, verification checks) |

## The `deeweb` task

One task (`deeweb`) is drawn from a real internal work ticket rather than an open-source
issue. Only the task brief and prompt are published here (`tasks/deeweb/`); the ticket's
source repo, diffs, and session transcripts are not public. Scored results for this task
(when available) will appear on the scoreboard as `score.json` data only.

## How to reproduce

See [methodology/METHODOLOGY.md §8](methodology/METHODOLOGY.md) for the full reproduction
steps, and `harness/` for the actual scripts (`run_matrix.sh`, `run_omp_task.sh`,
`run_opencode_task.sh`, `score_task.py`, `build_site.py`). The harness assumes local model
endpoints reachable over `localhost` (see `harness/omp-pod-providers.yml`); no infrastructure
details beyond that are included.

## License

MIT for the scripts and docs in this repository (see below). Third-party repositories used
as task subjects (anyio, chessground, chess.js, hatetris, Radix Primitives, Raptor: Call of
the Shadows) remain under their own licenses and are not vendored here — only briefs, diffs,
and result artifacts referencing them are included.

```
MIT License

Copyright (c) 2026 Jason Brown

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
