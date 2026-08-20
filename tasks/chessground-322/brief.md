# Task: fix a reported bug in `chessground`

## Bug report (verbatim from the project's issue tracker)
**eraseOnClick doesn't work as expected**

The shape on the board can be erased by either clicking - which deleted all shapes - or by redrawing the same shape - which deletes just that shape.

There is a property on chessground.state.drawable called eraseOnClick, which by name should enable or disable the functionality to erase all shapes when clicking. However, as shown by this line:

https://github.com/lichess-org/chessground/blob/aad96fd5f5c6f95168d894986f106ab1846c2205/src/drag.ts#L35

the `drawClear` function will executed regardless of the eraseOnClick setting if one clicks on an empty square or one having a piece different from the turn color.

Also, drawClear is not something that is exposed by chessground, so I can't even override it.

I would like to be able to disable the "erase on click" functionality somehow.

Thanks.

## Standing instructions (identical for every run)
You are working in the repository at the current working directory. Work like a careful open-source contributor:
1. Reproduce the bug first (write a minimal failing test or script) before changing code.
2. Find the root cause; fix the cause, not the symptom. Keep the change minimal and in the project's style.
3. Add or update a regression test that fails before your fix and passes after.
4. Run the project's test suite and make it green. Do not modify or delete unrelated tests.
5. When done, summarize: root cause, the files you changed, how you verified it.
Do not ask me for permission between steps; proceed until the task is complete, then report.

Test command for this repo: `npm test`
