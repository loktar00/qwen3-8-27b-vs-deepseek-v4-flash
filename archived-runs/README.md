# Archived Runs

Attempts invalidated by a configuration or harness defect (see [methodology §8
amendments](../methodology/METHODOLOGY.md)). Kept for the record; **NOT results and not
counted anywhere** — nothing here contributes to the scoreboard, and nothing here is
scored against the tasks' hidden references.

Each subdirectory here corresponds one-to-one with an orchestrator quarantine directory
that was set aside and re-run rather than published as a live result (naming convention:
`_invalid-*` for a run invalidated by a since-fixed configuration or harness bug,
`_restarted-*` for a run that was stopped and restarted). The task/label structure inside
each mirrors [`runs/`](../runs/), but with a smaller file set kept for reference:
`score.json`, `final.diff`, `driver.log`, `turn-*.json`, and session transcripts
(`*.jsonl`) — not the full raw log set that live `runs/` entries carry.

This directory exists purely for transparency: so that if a run disappears from `runs/`
and reappears with a different label or a later timestamp, there's a public record of
why, rather than an unexplained gap.
