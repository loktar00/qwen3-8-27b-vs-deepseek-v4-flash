# Answer Keys

These are the upstream fix diffs, frozen reproduction tests, and original issue data for
each task, kept out of the model's context at run time and published here after the fact so
scoring can be independently verified.

- `fix-pr-*.diff` — the actual upstream pull request that fixed the issue, used as a
  reference (not a strict pass/fail oracle — see [../methodology/SCORING.md](../methodology/SCORING.md)
  for how diffs from the reference fix are scored).
- `issue-*.json` — the raw GitHub issue data for the bug report each task is based on.
- `repro-*.test.ts` — a frozen regression test that reproduces the reported bug, run against
  each model's final diff as part of scoring.
- `RETIRED-*.txt` — notes on candidate issues that were pulled from the active task list
  after verification (already fixed upstream, or the affected code path no longer exists).

These files are the ground truth the harness scores against — nothing here was shown to
either model during a run.
