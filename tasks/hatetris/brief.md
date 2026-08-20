# Task: fix a reported bug in `hatetris`

## Bug report (verbatim from the project's issue tracker)
**Incomplete replays cause a softlock**

If you play a replay that doesn't end the game (for example, `D`), then the game will be stuck in replay mode even after there are no more inputs, forcing the user to refresh the page. This isn't that much of a problem since the game always outputs complete replays, though it should still probably allow the user to do something once the replay ends.

Image of replay `D`:
<img width="528" height="659" alt="Image" src="https://github.com/user-attachments/assets/b622b71b-a466-427c-9163-789db57b9125" />

## Standing instructions (identical for every run)
You are working in the repository at the current working directory. Work like a careful open-source contributor:
1. Reproduce the bug first (write a minimal failing test or script) before changing code.
2. Find the root cause; fix the cause, not the symptom. Keep the change minimal and in the project's style.
3. Add or update a regression test that fails before your fix and passes after.
4. Run the project's test suite and make it green. Do not modify or delete unrelated tests.
5. When done, summarize: root cause, the files you changed, how you verified it.
Do not ask me for permission between steps; proceed until the task is complete, then report.

Test command for this repo: `npm run unit`
