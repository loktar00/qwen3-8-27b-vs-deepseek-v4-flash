#!/usr/bin/env python3
"""raptor_secondary_metrics.py -- computes SCORING.md Sec 2D "Secondary" metrics
for a Raptor run (time-to-each-milestone already in score.json; this adds
tokens, tool calls, reverts/dead-ends, turns, wall, files/loc) and writes them
into that run's score.json as a top-level "secondary" object.

Reuses score_task.py's analyze_events()/wallclock_from_driver_log() directly
(imported, not reimplemented) for tokens/tool-calls/turns/wall -- those read
turn-*.json / sessions/*.jsonl / driver.log generically and need no
Raptor-specific logic.

Does NOT reuse secondary_metrics()'s loc/files computation as-is: that
function reads run_out/"final.diff" verbatim, but for a multi-commit session
(Raptor's models commit mid-session per milestone turn) that file only
captures the LAST uncommitted delta, not the whole base-to-final diff -- see
the discrepancy noted in the printed report. Instead this script computes
loc/files directly from git against the run's own worktree (base_sha vs the
current worktree state, i.e. committed history + whatever is still
uncommitted -- the same "actual working-tree state" the milestone checks
themselves score against).

reverts_dead_ends is Raptor-specific (SCORING.md Sec 2D lists it, the shared
score_task.py has no equivalent for the bug-fix tasks) -- mirrors
analyze_events()'s own event-collection loop (same load_ndjson_or_json /
walk_dicts helpers, imported) to pull every bash/run-tool call's argument
text, then regex-matches known revert/dead-end patterns.

Usage: python raptor_secondary_metrics.py <label>   (label = "dsv4" or "qwen")
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

AB_DIR = Path("D:/dev/style-pilot/labs/qwen38-day0/ab")
sys.path.insert(0, str(AB_DIR))
import score_task as st  # noqa: E402

RUN_ROOT = Path("D:/dev/ab-tasks/_runs/raptor")

REVERT_PATTERNS = [
    re.compile(r"git\s+checkout\s+--\s+\."),
    re.compile(r"git\s+checkout\s+\.\s*$"),
    re.compile(r"git\s+restore\b"),
    re.compile(r"git\s+reset\s+--hard"),
    re.compile(r"git\s+clean\s+-[a-z]*f[a-z]*d"),  # git clean -fd / -fdx / -df etc (mass delete of untracked)
    re.compile(r"rm\s+-rf\s+\S"),
    re.compile(r"Remove-Item\s+.*-Recurse"),
]


def find_revert_dead_ends(run_out: Path) -> dict:
    """Mirror analyze_events()'s event collection (turn-*.json preferred,
    sessions/*.jsonl fallback), scan every bash/run tool call's argument
    text for revert/dead-end command patterns."""
    turn_files = sorted(
        run_out.glob("turn-*.json"),
        key=lambda p: int(m.group(1)) if (m := re.search(r"turn-(\d+)", p.name)) else 0,
    )
    all_events = []
    for tf in turn_files:
        evs, _ = st.load_ndjson_or_json(tf)
        all_events.extend(evs)
    if not all_events:
        sess_dir = run_out / "sessions"
        sess_files = sorted(sess_dir.rglob("*.jsonl")) if sess_dir.exists() else []
        for sf in sess_files:
            evs, _ = st.load_ndjson_or_json(sf)
            all_events.extend(evs)

    hits = []
    for e in all_events:
        for node in st.walk_dicts(e):
            name = None
            argtext = ""
            if node.get("type") == "toolCall" and isinstance(node.get("name"), str):
                name = node["name"]
                args = node.get("arguments")
                if isinstance(args, dict):
                    argtext = " ".join(str(v) for v in args.values() if isinstance(v, (str, int, float)))
            elif node.get("type") == "custom" and node.get("customType") == "tool_execution_start":
                data = node.get("data") or {}
                name = data.get("toolName")
                a = data.get("args") if isinstance(data.get("args"), dict) else {}
                argtext = " ".join(str(v) for v in a.values())
            if not name or name.lower() not in st.RUN_TOOL_NAMES:
                continue
            for pat in REVERT_PATTERNS:
                m = pat.search(argtext)
                if m:
                    hits.append({"pattern": pat.pattern, "command_excerpt": argtext[:200]})
                    break

    return {"count": len(hits), "detail": hits}


def extract_token_usage(run_out: Path) -> dict:
    """analyze_events()'s token extraction looks for node.get("type")=="message"
    with a nested message.usage dict -- but this benchmark's actual OMP
    session/turn-*.json schema uses type=="message_start"/"message_end"/
    "message_update" instead (verified directly against turn-1.json), so that
    branch NEVER matches and every already-scored run's prompt/completion
    token sums are silently null (checked: anyio/dsv4-r1's score.json has the
    same None/None/None -- this is a benchmark-wide gap, not Raptor-specific,
    flagged separately to team-lead). This function reads the real schema:
    each assistant message's FINAL usage is on its "message_end" event
    (message_start's usage is present but all-zero, a streaming-start
    placeholder). Sums "input" across every assistant API call in the
    session (matches score_task.py's own usum() semantics of summing every
    captured usage dict -- NOT deduplicated across the accumulating-context
    calls of a long tool-calling loop, so this is "total billed input tokens
    across N API round-trips", not "unique conversation tokens"; "output" is
    additive/correct as-is since each call's output is genuinely newly
    generated content, not resent context).
    """
    turn_files = sorted(
        run_out.glob("turn-*.json"),
        key=lambda p: int(m.group(1)) if (m := re.search(r"turn-(\d+)", p.name)) else 0,
    )
    total_input = total_output = total_cache_read = total_cache_write = 0
    n_assistant_messages = 0
    per_turn = {}
    for tf in turn_files:
        turn_key = tf.stem
        text = tf.read_text(encoding="utf-8", errors="replace")
        t_in = t_out = 0
        t_n = 0
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(d, dict) or d.get("type") != "message_end":
                continue
            m = d.get("message")
            if not isinstance(m, dict) or m.get("role") != "assistant":
                continue
            u = m.get("usage")
            if not isinstance(u, dict):
                continue
            t_in += u.get("input", 0) or 0
            t_out += u.get("output", 0) or 0
            total_cache_read += u.get("cacheRead", 0) or 0
            total_cache_write += u.get("cacheWrite", 0) or 0
            t_n += 1
        total_input += t_in
        total_output += t_out
        n_assistant_messages += t_n
        per_turn[turn_key] = {"assistant_api_calls": t_n, "input_tokens_sum": t_in, "output_tokens_sum": t_out}

    return {
        "prompt_tokens_sum": total_input if n_assistant_messages else None,
        "completion_tokens_sum": total_output if n_assistant_messages else None,
        "reasoning_tokens_sum": None,  # not exposed as a separate field in this harness's usage schema
        "reasoning_tokens_note": "thinking content is present as text deltas (assistantMessageEvent thinking_delta) but no separate reasoning-token count is exposed in the usage dict; 'output' likely already includes thinking tokens for this reasoning model, undifferentiated from the final visible completion",
        "cache_read_tokens_sum": total_cache_read if n_assistant_messages else None,
        "cache_write_tokens_sum": total_cache_write if n_assistant_messages else None,
        "assistant_api_calls_total": n_assistant_messages,
        "assistant_api_calls_per_turn": per_turn,
    }


def per_turn_wall(run_out: Path) -> dict | None:
    """Parse driver.log's own [HH:MM:SS] turn N: ... / turn N rc=0 lines for
    exact per-turn wall-clock seconds (independent of, and a cross-check
    against, each milestone's own time_to_s already in score.json)."""
    f = run_out / "driver.log"
    if not f.exists():
        return None
    text = f.read_text(encoding="utf-8", errors="replace")
    # [HH:MM:SS] turn N: ...   and   [HH:MM:SS] turn N rc=...
    starts = {}
    ends = {}
    setup_start = None
    for line in text.splitlines():
        m = re.match(r"^\[(\d\d):(\d\d):(\d\d)\]\s+(.*)$", line)
        if not m:
            continue
        h, mi, s, rest = m.groups()
        sec = int(h) * 3600 + int(mi) * 60 + int(s)
        if setup_start is None:
            setup_start = sec
        tm = re.match(r"^turn (\d+):", rest)
        if tm:
            starts[int(tm.group(1))] = sec
        tm2 = re.match(r"^turn (\d+) rc=", rest)
        if tm2:
            ends[int(tm2.group(1))] = sec
        if rest.startswith("turn 0 rc="):
            ends[0] = sec
    if not starts and not ends:
        return None
    turns = {}
    prev_end = setup_start
    if 0 in ends:
        turns["turn_0_setup_s"] = ends[0] - setup_start
        prev_end = ends[0]
    for n in sorted(starts):
        if n in ends:
            turns[f"turn_{n}_s"] = ends[n] - starts[n]
    return turns


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "dsv4"
    run_out = RUN_ROOT / label
    scratch = run_out / "scratch"
    score_path = run_out / "score.json"

    turns_meta = st.load_turns("raptor")
    test_cmd = turns_meta.get("test_cmd", "")

    events = st.analyze_events(run_out, test_cmd)  # tool_call_counts etc -- verified working
    token_usage = extract_token_usage(run_out)  # replaces analyze_events()'s broken usage extraction (see docstring)
    wallclock_total = st.wallclock_from_driver_log(run_out)
    per_turn = per_turn_wall(run_out)
    reverts = find_revert_dead_ends(run_out)

    # loc/files: computed directly from git against the run's own worktree
    # (base_sha vs current state = committed history + uncommitted changes),
    # NOT from final.diff (see module docstring for why that file
    # under-counts when a session makes mid-run commits, as Raptor's does).
    base_sha_file = run_out / "base-sha.txt"
    base_sha = base_sha_file.read_text(encoding="utf-8").strip() if base_sha_file.exists() else None
    loc_info = {"base_sha": base_sha, "method": None}
    if base_sha and (scratch / ".git").exists():
        def git(args):
            return subprocess.run(
                ["git"] + args, cwd=str(scratch), capture_output=True, text=True, encoding="utf-8", errors="replace"
            ).stdout

        committed_numstat = git(["diff", f"{base_sha}..HEAD", "--numstat"])
        uncommitted_numstat = git(["diff", "HEAD", "--numstat"])
        untracked = [l[3:] for l in git(["status", "--porcelain"]).splitlines() if l.startswith("??")]

        files_loc = {}  # path -> [added, removed]

        def accumulate(numstat_text):
            for line in numstat_text.splitlines():
                parts = line.split("\t")
                if len(parts) != 3:
                    continue
                added, removed, path = parts
                if added == "-" or removed == "-":
                    continue  # binary
                a, r = files_loc.get(path, [0, 0])
                files_loc[path] = [a + int(added), r + int(removed)]

        accumulate(committed_numstat)
        accumulate(uncommitted_numstat)

        for path in untracked:
            fp = scratch / path
            if fp.is_file():
                try:
                    n = sum(1 for _ in fp.open(encoding="utf-8", errors="replace"))
                except Exception:
                    n = None
                if n is not None:
                    a, r = files_loc.get(path, [0, 0])
                    files_loc[path] = [a + n, r]

        loc_added = sum(v[0] for v in files_loc.values())
        loc_removed = sum(v[1] for v in files_loc.values())
        loc_info = {
            "base_sha": base_sha,
            "method": "git diff base_sha..HEAD (committed) + git diff HEAD (uncommitted tracked) + line-count of untracked new files -- the full base-to-final-worktree-state picture",
            "loc_added": loc_added,
            "loc_removed": loc_removed,
            "files_touched": sorted(files_loc.keys()),
            "files_touched_count": len(files_loc),
            "per_file": {k: {"added": v[0], "removed": v[1]} for k, v in sorted(files_loc.items())},
        }

    secondary = {
        "prompt_tokens": token_usage["prompt_tokens_sum"],
        "completion_tokens": token_usage["completion_tokens_sum"],
        "reasoning_tokens": token_usage["reasoning_tokens_sum"],
        "reasoning_tokens_note": token_usage["reasoning_tokens_note"],
        "cache_read_tokens": token_usage["cache_read_tokens_sum"],
        "cache_write_tokens": token_usage["cache_write_tokens_sum"],
        "assistant_api_calls_total": token_usage["assistant_api_calls_total"],
        "assistant_api_calls_per_turn": token_usage["assistant_api_calls_per_turn"],
        "token_usage_note": "analyze_events()'s own usage extraction returns null here (schema mismatch, see extract_token_usage() docstring) -- these figures are computed directly from message_end events instead",
        "tool_calls_total": sum(events["tool_call_counts"].values()) if events.get("tool_call_counts") else None,
        "tool_calls_by_tool": events.get("tool_call_counts"),
        "tool_call_count_source": events.get("tool_call_count_source"),
        "harness_parse_errors": events.get("harness_parse_errors"),
        "total_tool_errors": events.get("total_tool_errors"),
        "turns": len(list(run_out.glob("turn-*.json"))),
        "assistant_turns": events.get("assistant_turns"),  # null, same schema mismatch -- see assistant_api_calls_total above for the real figure
        "wall_s_total": wallclock_total,
        "wall_s_per_turn": per_turn,
        "reverts_dead_ends": reverts,
        "loc_and_files": loc_info,
        "event_source": events.get("event_source"),
    }

    score = json.loads(score_path.read_text(encoding="utf-8"))
    score["secondary"] = secondary
    score_path.write_text(json.dumps(score, indent=2), encoding="utf-8")

    print(json.dumps(secondary, indent=2, default=str))


if __name__ == "__main__":
    main()
