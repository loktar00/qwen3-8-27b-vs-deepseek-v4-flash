# Task: fix a reported bug in `chessjs`

## Bug report (verbatim from the project's issue tracker)
**BigInt error when generating moves for pawns on edge ranks**

Error happens in cases like:

```
chess.put({ type: 'p', color: 'w' }, 'h8')
chess.moves({ square: 'h8', verbose: true }))
```

Output:
```
TypeError: Cannot mix BigInt and other types, use explicit conversions
    at Chess._movePiece (/app/node_modules/src/chess.ts:1737:24)
    at Chess._makeMove (/app/node_modules/src/chess.ts:1764:10)
    at Chess._moveToSan (/app/node_modules/src/chess.ts:2279:10)
    at new Move (/app/node_modules/src/chess.ts:160:35)
    at /app/node_modules/src/chess.ts:1452:34
    at Array.map (<anonymous>)
    at Chess.moves (/app/node_modules/src/chess.ts:1452:20)
```

## Standing instructions (identical for every run)
You are working in the repository at the current working directory. Work like a careful open-source contributor:
1. Reproduce the bug first (write a minimal failing test or script) before changing code.
2. Find the root cause; fix the cause, not the symptom. Keep the change minimal and in the project's style.
3. Add or update a regression test that fails before your fix and passes after.
4. Run the project's test suite and make it green. Do not modify or delete unrelated tests.
5. When done, summarize: root cause, the files you changed, how you verified it.
Do not ask me for permission between steps; proceed until the task is complete, then report.

Test command for this repo: `npm test`
