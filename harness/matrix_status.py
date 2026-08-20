#!/usr/bin/env python3
"""matrix_status.py -- pretty-print run_matrix.sh's status.tsv, annotated with whether score.json
exists yet for each done job, so the orchestrator knows when it's time to run
`python score_task.py --all`.

usage:
  python matrix_status.py                    # read the default status.tsv
  python matrix_status.py --tsv PATH         # read a different status.tsv (e.g. an older run)
  python matrix_status.py --runs-root PATH   # look for score.json somewhere other than _runs/
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

DEFAULT_TSV = Path("D:/dev/ab-tasks/_runs/_matrix/status.tsv")
DEFAULT_RUNS_ROOT = Path("D:/dev/ab-tasks/_runs")

COLUMNS = ["task", "label", "state", "start", "end", "scored", "last_driver_log_line"]
MAX_LOG_COL = 70


def load_rows(tsv_path: Path, runs_root: Path) -> list[dict]:
    with tsv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)

    for row in rows:
        score_path = runs_root / row["task"] / row["label"] / "score.json"
        if row.get("state") != "done":
            row["scored"] = "-"
        else:
            row["scored"] = "yes" if score_path.exists() else "no"
    return rows


def render_table(rows: list[dict]) -> str:
    widths = {}
    for c in COLUMNS:
        w = len(c)
        for r in rows:
            w = max(w, len(str(r.get(c, ""))))
        if c == "last_driver_log_line":
            w = min(w, MAX_LOG_COL)
        widths[c] = w

    def fmt(vals: dict) -> str:
        cells = []
        for c in COLUMNS:
            v = str(vals.get(c, ""))[: widths[c]]
            cells.append(v.ljust(widths[c]))
        return "  ".join(cells).rstrip()

    lines = [fmt({c: c for c in COLUMNS}), "  ".join("-" * widths[c] for c in COLUMNS)]
    lines.extend(fmt(r) for r in rows)
    return "\n".join(lines)


def render_summary(rows: list[dict]) -> str:
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.get("state", "")] = counts.get(r.get("state", ""), 0) + 1
    done = counts.get("done", 0)
    scored = sum(1 for r in rows if r.get("state") == "done" and r.get("scored") == "yes")
    parts = [f"total={len(rows)}"]
    for k in ("queued", "running", "done", "failed"):
        parts.append(f"{k}={counts.get(k, 0)}")
    line = "  ".join(parts) + f"\ndone+scored={scored}/{done}"
    if done and scored < done:
        line += "\nhint: run `python score_task.py --all` to score newly finished runs"
    return line


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tsv", type=Path, default=DEFAULT_TSV, help="status.tsv path")
    ap.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS_ROOT,
                     help="_runs root to look for <task>/<label>/score.json under")
    args = ap.parse_args()

    if not args.tsv.exists():
        print(f"no status file at {args.tsv} (has run_matrix.sh been run yet?)", file=sys.stderr)
        return 1

    rows = load_rows(args.tsv, args.runs_root)
    if not rows:
        print("status file is empty")
        return 0

    print(render_table(rows))
    print()
    print(render_summary(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
