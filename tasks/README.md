# Tasks

Each task directory contains the exact brief and multi-turn prompt script (`turns.json`)
given to each model, unmodified between models/runs. See [../methodology/METHODOLOGY.md](../methodology/METHODOLOGY.md)
for how these were selected and administered, and [../answer-keys/](../answer-keys/) for the
withheld upstream fix / repro data used to score them.

| Task | Repo | Issue | Base commit | Lanes |
|---|---|---|---|---|
| `radix` | [radix-ui/primitives](https://github.com/radix-ui/primitives) | [#3799](https://github.com/radix-ui/primitives/issues/3799) — "installHook.js:1 Error: Maximum update depth exceeded - React 19 + Radix" | `bd41d0381c9f14c0e16f58903fa1fd56f1806038` | OMP (dsv4, qwen, qwen-medium), OpenCode (dsv4) |
| `anyio` | [agronholm/anyio](https://github.com/agronholm/anyio) | [#1170](https://github.com/agronholm/anyio/issues/1170) — "CapacityLimiter can over-grant tokens (`borrowed_tokens > total_tokens`)" | `6f82b2537cbbe98f3df3f295499056ab7de0b15b` | OMP (dsv4, qwen, qwen-medium), OpenCode (dsv4) |
| `hatetris` | [qntm/hatetris](https://github.com/qntm/hatetris) | [#301](https://github.com/qntm/hatetris/issues/301) — "Incomplete replays cause a softlock" | `e95241df79161ad4a735749dd2a3e134e24ef6ca` | OMP (dsv4) |
| `chessground` | [lichess-org/chessground](https://github.com/lichess-org/chessground) | [#386](https://github.com/lichess-org/chessground/issues/386) — "Disconnect ResizeObserver on destroy and on redraw" | `e47565c8d1b356bd1a30f92e7e96e4ae04d4b1` | OMP (dsv4) |
| `chessground-322` | [lichess-org/chessground](https://github.com/lichess-org/chessground) | [#322](https://github.com/lichess-org/chessground/issues/322) — "eraseOnClick doesn't work as expected" | queued — not yet run at time of publish; same repo family as `chessground` above | OMP (dsv4, qwen, qwen-medium) — queued |
| `chessjs` | [jhlywa/chess.js](https://github.com/jhlywa/chess.js) | [#577](https://github.com/jhlywa/chess.js/issues/577) — "BigInt error when generating moves for pawns on edge ranks" | queued — not yet run at time of publish | OMP (dsv4, qwen, qwen-medium) — queued |
| `raptor` | [skynettx/dosraptor](https://github.com/skynettx/dosraptor) (GPL source) | n/a — greenfield port task, not a bug-fix issue | `4403569505c215c6cebe02cc3344e670499def1d` | Manual/companion-repo lane (see [raptor-web-ab](https://github.com/loktar00/raptor-web-ab)), not part of the automated matrix |
| `deeweb` | Internal ticket — not public | Internal ticket — not public | not public | Manual lane; only `brief.md` and `phase1-prompt.md` are published, see root README |

Notes:

- "Queued" entries reflect the state of the run matrix at the time this repo was published;
  re-run `harness/matrix_status.py` or check `runs/_matrix/status.tsv` for the latest state,
  and re-sync with `sync_results.sh` once those jobs complete.
- `raptor` and `deeweb` are not driven by `harness/run_matrix.sh` (see `ALL_TASKS` in that
  script) — they use a separate single-task runner/lane.
- Two of the `_hidden` retired candidate issues (chessground #344, chess.js #574) were pulled
  from the active task list after confirming they were already fixed upstream or the affected
  code path no longer exists on the current `HEAD` of those repos — see
  `answer-keys/chessground/RETIRED-344.txt` and `answer-keys/chessjs/RETIRED-574.txt`.
