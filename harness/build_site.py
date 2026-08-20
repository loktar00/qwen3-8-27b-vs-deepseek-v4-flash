#!/usr/bin/env python3
"""build_site.py -- static results-site generator for the DSV4 vs Qwen3.8 coding A/B.

Reads the pre-registered scoring spec (SCORING.md) plus a run-results tree and
renders a self-contained static site: a scoreboard, one page per task, a
calibration page, a rendered Method page, and a Raptor milestone-ladder page.
No external services, no CDNs, no build step other than this script; every
page is inline HTML/CSS/JS so the output directory can be zipped, emailed, or
served from anywhere (including opened directly via file://).

USAGE
    python build_site.py [--runs DIR] [--out DIR] [--scoring FILE]

    --runs DIR      root that contains _briefs/, _calib/, and _runs/
                     (default: D:/dev/ab-tasks)
    --out DIR       output directory for the built site
                     (default: D:/dev/ab-tasks/_site)
    --scoring FILE  path to SCORING.md, rendered as the Method page
                     (default: alongside this script)

INPUT SHAPES (see ab/SCORING.md for what each field means; every key below is
treated as OPTIONAL -- a run with a thin score.json still renders, just with
blanks where data is missing):

  <runs>/_runs/<task>/<label>/score.json
      {
        "task": "radix", "label": "dsv4-a-r1", "model": "dsv4", "lane": "A", "rep": 1,
        "P1": {"pass": true, "reason": "..."},   // or a bare bool + "P1_reason"
        "P2": {"pass": true, "reason": "..."},
        "P3": {"pass": false, "reason": "..."},
        "pass": false,                            // P1 and P2 and P3
        "p4": {"status": "pending", "note": "..."},   // 2B lagging indicator, never scored
        "checklist": [{"label": "...", "pass": true}, ...],   // 2C (deeweb) instead of P1-P3
        "checklist_extra": {"suite_green": true, "typecheck_clean": true, "lint_clean": true},
        "milestones": [{"id": "M1", "label": "...", "pass": true, "time_to_s": 812,
                         "ssim": 0.86, "palette_coverage": 0.94}, ...],  // 2D (raptor)
        "milestones_reached": 3,
        "secondary": {
          "wall_s": 1423, "tokens": {"prompt": 12000, "completion": 3400, "reasoning": 8900},
          "tool_calls": {"by_name": {"read": 12, "edit": 4, "bash": 9}},
          "test_runs": 6, "reproduced_first": true,
          "diff": {"added": 42, "removed": 8, "files": ["path/a.ts", "path/b.ts"]},
          "precision": "subset",              // subset | superset | disjoint | exact
          "harness_events": [{"turn": 2, "type": "parse_error", "recoverable": true, "detail": "..."}],
          "redirects": 2, "reverts": 0,
          "coderabbit": {"blocker": 0, "major": 1, "minor": 3}
        },
        "tertiary": {"root_cause": 2, "style": 1, "scale": 2, "judge": "blinded"}
      }
  <runs>/_runs/<task>/<label>/final.diff, final-tests.log, driver.log, install.log
  <runs>/_runs/<task>/<label>/sessions/*.html   (OMP --export)
  <runs>/_runs/<task>/<label>/sessions/*.jsonl  (OMP raw session, or lane C transcript.jsonl)
  <runs>/_runs/calibration/<harness>/<label>.json
      {"harness": "omp", "label": "dsv4", "model": "dsv4",
       "items": [{"id": 1, "name": "READ", "pass": true, "tool_calls": 1, "parse_errors": 0}, ...],
       "wall_s": 41, "tokens": {"prompt": 900, "completion": 210}}
  <runs>/_briefs/<task>/brief.md
  <runs>/_briefs/<task>/turns.json           {"turns": [...], "test_cmd": "...", "install": "..."}
  <runs>/_briefs/<task>/lane_c_task.json     {"opening": "...", "turns": [...], "test_cmd": "..."}

Never writes into <runs>/_runs -- this script only reads from --runs and
writes to --out.
"""
from __future__ import annotations

import argparse
import html as _html
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# Registry: static facts about models, lanes and tasks that aren't reliably
# derivable from the files themselves.
# --------------------------------------------------------------------------

MODELS = {
    "dsv4":        {"display": "DeepSeek V4 Flash 0731", "effort": "Max (server default)", "slot": 1, "short": "DSV4"},
    "qwen":        {"display": "Qwen3.8-27B BF16",        "effort": "shipped default",       "slot": 2, "short": "Qwen"},
    "qwen-medium": {"display": "Qwen3.8-27B BF16",        "effort": "medium",                "slot": 2, "short": "Qwen (medium)"},
}
MODEL_ORDER = ["dsv4", "qwen", "qwen-medium"]

LANES = {
    "A": {"name": "OMP", "desc": "all tasks"},
    "B": {"name": "OpenCode", "desc": "radix, anyio \u2014 tool-heaviest, robustness check"},
    "C": {"name": "No-harness scripted human", "desc": "chess.js #577, one hidden-reference task"},
    "D": {"name": "Existing 0-shots", "desc": "control, already public elsewhere"},
}
LANE_ORDER = ["A", "B", "C", "D"]

CLASS_LABELS = {
    "2A": "Hidden-reference bug fix",
    "2B": "Live bug",
    "2C": "deeweb ticket (private)",
    "2D": "Raptor \u2192 web port ladder",
}

TASKS_META = {
    "radix":       {"class": "2A", "lanes": ["A", "B", "C"], "ref": "radix #3799"},
    "anyio":       {"class": "2A", "lanes": ["A", "B"],       "ref": "anyio #1170"},
    "hatetris":    {"class": "2A", "lanes": ["A"],            "ref": "HATETRIS #301"},
    "chessground": {"class": "2A", "lanes": ["A"],            "ref": "chessground #386",
                    "note": "#344 retired 2026-08-20: its code path was removed upstream; "
                            "chessground is scored as hidden-ref #386 with a frozen leak test as P1."},
    "chessjs":     {"class": "2B", "lanes": ["A", "C"],       "ref": "chess.js #577 (+#574 if time)"},
    "deeweb":      {"class": "2C", "lanes": ["A"],            "ref": "CAL-7207", "private": True, "reps": 1},
    "raptor":      {"class": "2D", "lanes": ["A"],            "ref": "Raptor sector 1", "reps": 1},
}
TASK_ORDER = ["radix", "anyio", "hatetris", "chessground", "chessjs", "deeweb", "raptor"]

# Set by main() when --banner is passed (or auto-detected from --runs pointing at a
# fixture path). Read by page_shell() on every page. A plain module global rather than
# a threaded parameter, matching CSS/JS above -- this is a single-process, single-run
# script, so there is nothing to isolate it from.
BANNER_TEXT: Optional[str] = None


def esc(s: Any) -> str:
    return _html.escape("" if s is None else str(s), quote=True)


def read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def read_text(path: Path, limit: Optional[int] = None) -> Optional[str]:
    if not path.exists():
        return None
    try:
        t = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if limit and len(t) > limit:
        t = t[:limit] + f"\n\n... [truncated, {len(t) - limit} more characters -- see the full file]"
    return t


def fnum(x, digits=0):
    if x is None:
        return "\u2014"
    try:
        if digits == 0:
            return f"{int(round(x)):,}"
        return f"{x:,.{digits}f}"
    except (TypeError, ValueError):
        return str(x)


def fmt_wall(s):
    if s is None:
        return "\u2014"
    try:
        s = float(s)
    except (TypeError, ValueError):
        return "\u2014"
    if s < 90:
        return f"{s:.0f}s"
    m = s / 60
    if m < 90:
        return f"{m:.1f}m"
    return f"{m / 60:.1f}h"


# --------------------------------------------------------------------------
# Markdown: a small renderer sufficient for SCORING.md / brief.md's dialect
# (headings, bold, inline code, code fences, links, bullet + numbered lists
# with word-wrapped continuation lines, horizontal rules).
# --------------------------------------------------------------------------

def _inline_md(text: str) -> str:
    text = esc(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
    return text


def render_markdown(md: str) -> str:
    lines = md.replace("\r\n", "\n").split("\n")
    out, i, n = [], 0, len(lines)
    in_table = False
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            body = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            cls = f' class="lang-{esc(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>{esc(chr(10).join(body))}</code></pre>")
            continue

        if not stripped:
            i += 1
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            level = min(len(m.group(1)) + 1, 6)  # keep h1 for the page title
            out.append(f"<h{level}>{_inline_md(m.group(2))}</h{level}>")
            i += 1
            continue

        if re.match(r"^-{3,}$", stripped):
            out.append("<hr>")
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < n and re.match(r"^\|?[\s:|-]+\|?$", lines[i + 1].strip()):
            header = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            thead = "".join(f"<th>{_inline_md(c)}</th>" for c in header)
            tbody = "".join("<tr>" + "".join(f"<td>{_inline_md(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f'<div class="md-table"><table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>')
            continue

        is_bullet = re.match(r"^[-*]\s+", stripped)
        is_num = re.match(r"^\d+[.)]\s+", stripped)
        if is_bullet or is_num:
            tag = "ul" if is_bullet else "ol"
            items = []
            while i < n:
                s = lines[i].strip()
                bm = re.match(r"^[-*]\s+(.*)$", s)
                nm = re.match(r"^\d+[.)]\s+(.*)$", s)
                if tag == "ul" and bm:
                    items.append(bm.group(1))
                    i += 1
                elif tag == "ol" and nm:
                    items.append(nm.group(1))
                    i += 1
                elif s and not re.match(r"^[-*]\s+", s) and not re.match(r"^\d+[.)]\s+", s) and not s.startswith("#"):
                    if items:
                        items[-1] += " " + s
                    i += 1
                else:
                    break
            out.append(f"<{tag}>" + "".join(f"<li>{_inline_md(it)}</li>" for it in items) + f"</{tag}>")
            continue

        para = [stripped]
        i += 1
        while i < n and lines[i].strip() and not re.match(r"^(#{1,4})\s", lines[i].strip()) \
                and not re.match(r"^[-*]\s+|\d+[.)]\s+", lines[i].strip()) and not lines[i].strip().startswith("```"):
            para.append(lines[i].strip())
            i += 1
        out.append(f"<p>{_inline_md(' '.join(para))}</p>")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class Run:
    label: str
    dir: Path
    score: dict = field(default_factory=dict)

    @property
    def model(self) -> str:
        return self.score.get("model") or self.label.split("-")[0]

    @property
    def lane(self) -> str:
        return (self.score.get("lane") or "A").upper()

    @property
    def rep(self) -> int:
        return int(self.score.get("rep") or 1)

    def check(self, key: str):
        """Returns (pass|None, reason|None) for P1/P2/P3."""
        v = self.score.get(key)
        if isinstance(v, dict):
            return v.get("pass"), v.get("reason")
        if isinstance(v, bool):
            return v, self.score.get(f"{key}_reason")
        return None, None

    @property
    def overall_pass(self) -> Optional[bool]:
        if "pass" in self.score:
            return self.score.get("pass")
        vals = [self.check(k)[0] for k in ("P1", "P2", "P3")]
        if all(v is not None for v in vals):
            return all(vals)
        return None

    @property
    def secondary(self) -> dict:
        return self.score.get("secondary") or {}

    @property
    def tertiary(self) -> dict:
        return self.score.get("tertiary") or {}

    def artifact(self, *names) -> Optional[Path]:
        for name in names:
            p = self.dir / name
            if p.exists():
                return p
        return None

    @property
    def transcript_html(self) -> Optional[Path]:
        sess = self.dir / "sessions"
        if sess.is_dir():
            found = sorted(sess.glob("*.html"))
            if found:
                return found[0]
        return None

    @property
    def transcript_jsonl(self) -> Optional[Path]:
        for cand in [self.dir / "transcript.jsonl"]:
            if cand.exists():
                return cand
        sess = self.dir / "sessions"
        if sess.is_dir():
            found = sorted(sess.glob("*.jsonl"))
            if found:
                return found[0]
        return None


@dataclass
class Task:
    id: str
    meta: dict
    brief_md: Optional[str] = None
    turns: Optional[dict] = None
    runs: list = field(default_factory=list)

    @property
    def task_class(self) -> str:
        return self.meta.get("class", "2A")

    @property
    def title(self) -> str:
        if self.brief_md:
            m = re.search(r"^\*\*(.+?)\*\*\s*$", self.brief_md, re.M)
            if m:
                return m.group(1).strip()
            m = re.search(r"^#\s*Task:\s*(.+)$", self.brief_md, re.M)
            if m:
                return m.group(1).strip()
        if self.turns and self.turns.get("opening"):
            m = re.search(r"^\*\*(.+?)\*\*\s*$", self.turns["opening"], re.M)
            if m:
                return m.group(1).strip()
        return self.meta.get("ref", self.id)

    def runs_by_cell(self):
        """dict[(model,lane)] -> list[Run], reps sorted."""
        cells = {}
        for r in self.runs:
            cells.setdefault((r.model, r.lane), []).append(r)
        for v in cells.values():
            v.sort(key=lambda r: r.rep)
        return cells


def load_task(root: Path, task_id: str) -> Task:
    meta = TASKS_META[task_id]
    t = Task(id=task_id, meta=meta)
    brief_dir = root / "_briefs" / task_id
    t.brief_md = read_text(brief_dir / "brief.md")
    turns = read_json(brief_dir / "turns.json")
    lane_c = read_json(brief_dir / "lane_c_task.json")
    if turns or lane_c:
        t.turns = {**(turns or {}), **({"opening_from_lane_c": True, **lane_c} if lane_c else {})}
    run_root = root / "_runs" / task_id
    if run_root.is_dir():
        for label_dir in sorted(p for p in run_root.iterdir() if p.is_dir()):
            score = read_json(label_dir / "score.json") or {}
            t.runs.append(Run(label=label_dir.name, dir=label_dir, score=score))
    return t


def load_calibration(root: Path) -> dict:
    """dict[harness] -> list[dict] (one per label), from _runs/calibration/<harness>/<label>.json"""
    out = {}
    calib_root = root / "_runs" / "calibration"
    if not calib_root.is_dir():
        return out
    for harness_dir in sorted(p for p in calib_root.iterdir() if p.is_dir()):
        entries = []
        for f in sorted(harness_dir.glob("*.json")):
            d = read_json(f)
            if d:
                d.setdefault("label", f.stem)
                entries.append(d)
        if entries:
            out[harness_dir.name] = entries
    return out


# --------------------------------------------------------------------------
# CSS + JS (shared across every page; inline, no CDNs)
# --------------------------------------------------------------------------

CSS = r"""
:root, [data-theme="light"] {
  color-scheme: light;
  --page:        #f9f9f7;
  --surface:     #fcfcfb;
  --surface-2:   #f2f1ec;
  --ink:         #0b0b0b;
  --ink-2:       #52514e;
  --ink-muted:   #898781;
  --line:        #e1e0d9;
  --line-strong: #c3c2b7;
  --border:      rgba(11,11,11,0.10);
  --accent-a:    #2a78d6;   /* DeepSeek */
  --accent-a-ink:#0d3a70;
  --accent-b:    #eb6834;   /* Qwen */
  --accent-b-ink:#7a3110;
  --good:        #0ca30c;
  --good-ink:    #006300;
  --warn:        #b9760f;
  --warn-bg:     #fdf1da;
  --serious:     #c15a2f;
  --serious-bg:  #fbe8dd;
  --critical:    #d03b3b;
  --critical-bg: #fbe2e2;
  --harness:     #5b5a52;
  --harness-bg:  #eeece3;
  --shadow:      0 1px 2px rgba(11,11,11,0.06), 0 4px 14px rgba(11,11,11,0.05);
  --radius:      6px;
  --mono: ui-monospace, "Cascadia Mono", "Cascadia Code", "SF Mono", "JetBrains Mono", Consolas, "Liberation Mono", monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, "Helvetica Neue", Arial, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page:        #0d0d0d;
    --surface:     #1a1a19;
    --surface-2:   #221f1a;
    --ink:         #ffffff;
    --ink-2:       #c3c2b7;
    --ink-muted:   #8f8d86;
    --line:        #2c2c2a;
    --line-strong: #3a3935;
    --border:      rgba(255,255,255,0.12);
    --accent-a:    #4c96f0;
    --accent-a-ink:#bfe0ff;
    --accent-b:    #e8813e;
    --accent-b-ink:#ffd9bd;
    --good:        #23c623;
    --good-ink:    #7be07b;
    --warn:        #e8b545;
    --warn-bg:     #3a2f10;
    --serious:     #e08657;
    --serious-bg:  #3a2416;
    --critical:    #ef6a6a;
    --critical-bg: #3a1717;
    --harness:     #b8b6ab;
    --harness-bg:  #262521;
    --shadow:      0 1px 2px rgba(0,0,0,0.3), 0 4px 14px rgba(0,0,0,0.25);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page:        #0d0d0d;
  --surface:     #1a1a19;
  --surface-2:   #221f1a;
  --ink:         #ffffff;
  --ink-2:       #c3c2b7;
  --ink-muted:   #8f8d86;
  --line:        #2c2c2a;
  --line-strong: #3a3935;
  --border:      rgba(255,255,255,0.12);
  --accent-a:    #4c96f0;
  --accent-a-ink:#bfe0ff;
  --accent-b:    #e8813e;
  --accent-b-ink:#ffd9bd;
  --good:        #23c623;
  --good-ink:    #7be07b;
  --warn:        #e8b545;
  --warn-bg:     #3a2f10;
  --serious:     #e08657;
  --serious-bg:  #3a2416;
  --critical:    #ef6a6a;
  --critical-bg: #3a1717;
  --harness:     #b8b6ab;
  --harness-bg:  #262521;
  --shadow:      0 1px 2px rgba(0,0,0,0.3), 0 4px 14px rgba(0,0,0,0.25);
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--page); color: var(--ink);
  font-family: var(--sans); font-size: 15px; line-height: 1.55;
  text-rendering: optimizeLegibility;
}
h1,h2,h3,h4 { font-family: var(--mono); font-weight: 600; text-wrap: balance; margin: 0 0 .5em; letter-spacing: -0.01em; }
h1 { font-size: 1.7rem; } h2 { font-size: 1.25rem; margin-top: 2.2em; } h3 { font-size: 1.02rem; margin-top: 1.6em; } h4 { font-size: .92rem; }
p { margin: 0 0 1em; max-width: 68ch; }
a { color: var(--accent-a); }
:root[data-theme="light"] a, :root:not([data-theme="dark"]) a { color: #1c5cab; }
[data-theme="dark"] a, :root:not([data-theme="light"]) a { }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) a { color: #7cb4f2; } }
:root[data-theme="dark"] a { color: #7cb4f2; }
a:focus-visible, button:focus-visible, summary:focus-visible, .cell:focus-visible { outline: 2px solid var(--accent-a); outline-offset: 2px; }
code, pre, .mono { font-family: var(--mono); }
code { background: var(--surface-2); padding: .1em .35em; border-radius: 4px; font-size: .88em; }
pre { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: .9em 1em; overflow-x: auto; font-size: .82rem; line-height: 1.5; }
pre code { background: none; padding: 0; }
hr { border: none; border-top: 1px solid var(--line); margin: 2em 0; }

.shell { max-width: 1180px; margin: 0 auto; padding: 0 1.25rem 4rem; }
.stick-top { position: sticky; top: 0; z-index: 50; }
.top-banner {
  background: var(--warn-bg); color: var(--warn); border-bottom: 1px solid color-mix(in srgb, var(--warn) 55%, transparent);
  font-family: var(--mono); font-weight: 700; font-size: .82rem; text-align: center; letter-spacing: .02em;
  padding: .55em 1rem; text-transform: uppercase;
}
.topbar {
  background: var(--page);
  border-bottom: 1px solid var(--line); backdrop-filter: blur(6px);
}
.topbar-inner { max-width: 1180px; margin: 0 auto; padding: .8rem 1.25rem; display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap; }
.brand { font-family: var(--mono); font-weight: 700; font-size: .95rem; letter-spacing: -0.01em; white-space: nowrap; }
.brand small { display:block; font-weight: 400; color: var(--ink-muted); font-size: .72rem; letter-spacing: 0; }
.nav { display: flex; gap: 1.1rem; flex-wrap: wrap; margin-left: auto; font-family: var(--mono); font-size: .82rem; }
.nav a { color: var(--ink-2); text-decoration: none; padding: .3em 0; border-bottom: 2px solid transparent; }
.nav a:hover, .nav a.active { color: var(--ink); border-bottom-color: var(--accent-a); }
.theme-btn {
  font-family: var(--mono); font-size: .76rem; border: 1px solid var(--line-strong); background: var(--surface);
  color: var(--ink-2); border-radius: 5px; padding: .35em .6em; cursor: pointer;
}
.theme-btn:hover { color: var(--ink); }

.page-head { padding: 2.2rem 0 .5rem; }
.eyebrow { font-family: var(--mono); font-size: .74rem; text-transform: uppercase; letter-spacing: .08em; color: var(--ink-muted); margin: 0 0 .5em; }
.lede { color: var(--ink-2); max-width: 72ch; }

.card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); }
.card > .card-pad { padding: 1.1rem 1.3rem; }
.section { margin-top: 2.4rem; }

/* ---- badges / chips / pips ---- */
.badge { display: inline-flex; align-items: center; gap: .35em; font-family: var(--mono); font-size: .72rem;
  padding: .18em .55em; border-radius: 4px; border: 1px solid var(--line-strong); color: var(--ink-2); background: var(--surface-2); white-space: nowrap; }
.badge.accent-a { border-color: color-mix(in srgb, var(--accent-a) 55%, var(--line-strong)); color: var(--accent-a-ink); background: color-mix(in srgb, var(--accent-a) 12%, var(--surface)); }
.badge.accent-b { border-color: color-mix(in srgb, var(--accent-b) 55%, var(--line-strong)); color: var(--accent-b-ink); background: color-mix(in srgb, var(--accent-b) 12%, var(--surface)); }

.chip { display: inline-flex; align-items: center; gap: .4em; font-family: var(--mono); font-weight: 600; font-size: .78rem;
  padding: .3em .65em; border-radius: 5px; line-height: 1; white-space: nowrap; }
.chip .n { font-weight: 400; opacity: .8; margin-left: .15em; }
.chip.pass { color: var(--good-ink); background: color-mix(in srgb, var(--good) 16%, var(--surface)); border: 1px solid color-mix(in srgb, var(--good) 45%, transparent); }
.chip.fail { color: var(--critical); background: var(--critical-bg); border: 1px solid color-mix(in srgb, var(--critical) 45%, transparent); }
.chip.mixed { color: var(--warn); background: var(--warn-bg); border: 1px solid color-mix(in srgb, var(--warn) 45%, transparent); }
.chip.unknown { color: var(--ink-muted); background: var(--surface-2); border: 1px solid var(--line); }
.chip.harness { color: var(--harness); background: var(--harness-bg); border: 1px solid var(--line-strong); }
.chip::before { content: ""; width: .5em; height: .5em; border-radius: 50%; background: currentColor; flex: none; }

.pips { display: inline-flex; gap: .3em; font-family: var(--mono); }
.pip { display: inline-flex; align-items: center; justify-content: center; width: 1.5em; height: 1.5em; border-radius: 4px;
  font-size: .68rem; font-weight: 700; border: 1px solid var(--line-strong); color: var(--ink-muted); background: var(--surface-2); }
.pip.pass { color: var(--good-ink); background: color-mix(in srgb, var(--good) 18%, var(--surface)); border-color: color-mix(in srgb, var(--good) 50%, transparent); }
.pip.fail { color: var(--critical); background: var(--critical-bg); border-color: color-mix(in srgb, var(--critical) 50%, transparent); }
.pip.empty { border-style: dashed; }

.star-row { display: inline-flex; gap: .15em; }
.star { width: .95em; height: .95em; border-radius: 2px; background: var(--line-strong); display: inline-block; }
.star.filled { background: var(--accent-a); }
.star-row.b .star.filled { background: var(--accent-b); }

/* ---- stat tiles ---- */
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .8rem; margin-top: 1.2rem; }
.tile { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: .9rem 1rem; }
.tile .tl { font-family: var(--mono); font-size: .7rem; text-transform: uppercase; letter-spacing: .06em; color: var(--ink-muted); margin-bottom: .4em; }
.tile .tv { font-family: var(--mono); font-size: 1.5rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.tile .ts { font-size: .78rem; color: var(--ink-2); margin-top: .3em; }
.tile.a .tv { color: var(--accent-a); } .tile.b .tv { color: var(--accent-b); }

.verdict { border-left: 3px solid var(--accent-a); background: var(--surface); border: 1px solid var(--line); border-left-width: 3px;
  border-radius: var(--radius); padding: 1rem 1.2rem; margin-top: 1.2rem; }
.verdict .vlabel { font-family: var(--mono); font-size: .72rem; text-transform: uppercase; letter-spacing: .07em; color: var(--ink-muted); }
.verdict .vtext { font-family: var(--mono); font-size: 1.02rem; margin-top: .35em; }
.verdict.decided { border-left-color: var(--good); }
.verdict.tie { border-left-color: var(--warn); }
blockquote.rule { margin: .8rem 0 0; padding: .7rem 1rem; border-left: 3px solid var(--line-strong); background: var(--surface-2);
  border-radius: 0 4px 4px 0; font-size: .88rem; color: var(--ink-2); }

/* ---- scoreboard table ---- */
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); margin-top: 1.4rem; }
table.board { border-collapse: collapse; width: 100%; min-width: 780px; font-size: .86rem; }
table.board th, table.board td { padding: .55em .8em; text-align: left; border-bottom: 1px solid var(--line); white-space: nowrap; }
table.board thead th { position: sticky; top: 0; background: var(--surface); font-family: var(--mono); font-size: .72rem;
  text-transform: uppercase; letter-spacing: .04em; color: var(--ink-muted); border-bottom: 1px solid var(--line-strong); z-index: 2; }
table.board thead tr.lanehead th { font-size: .68rem; padding-bottom: 0; color: var(--ink-muted); font-weight: 400; }
table.board tbody th { position: sticky; left: 0; background: var(--surface); z-index: 1; font-family: var(--mono); font-weight: 600; }
table.board tbody tr:hover td, table.board tbody tr:hover th { background: var(--surface-2); }
table.board td.cell { white-space: normal; }
.rowmeta { display: block; font-weight: 400; color: var(--ink-muted); font-size: .74rem; margin-top: .1em; }
.tasklink { color: var(--ink); text-decoration: none; }
.tasklink:hover { text-decoration: underline; }
.cellbox { display: flex; align-items: center; gap: .5em; flex-wrap: wrap; }
.na { color: var(--ink-muted); font-family: var(--mono); }
.classhead td { background: var(--surface-2); font-family: var(--mono); font-size: .72rem; text-transform: uppercase;
  letter-spacing: .06em; color: var(--ink-muted); padding: .5em .8em; border-bottom: 1px solid var(--line-strong); }

/* ---- task page ---- */
.tagrow { display: flex; gap: .5em; flex-wrap: wrap; align-items: center; margin: .6em 0 0; }
details.brief { margin-top: 1.2rem; }
details.brief > summary { cursor: pointer; font-family: var(--mono); font-size: .84rem; padding: .7em 1em; background: var(--surface);
  border: 1px solid var(--line); border-radius: var(--radius); list-style: none; display: flex; align-items: center; gap: .5em; }
details.brief > summary::-webkit-details-marker { display: none; }
details.brief > summary::before { content: "\25b8"; display: inline-block; transition: transform .15s; color: var(--ink-muted); }
details.brief[open] > summary::before { transform: rotate(90deg); }
details.brief .brief-body { border: 1px solid var(--line); border-top: none; border-radius: 0 0 var(--radius) var(--radius);
  padding: 1.2rem 1.4rem; background: var(--surface); }
.prose h1, .prose h2, .prose h3, .prose h4 { font-family: var(--sans); }
.prose h1 { font-size: 1.25rem; } .prose h2 { font-size: 1.08rem; margin-top: 1.4em; } .prose h3 { font-size: .98rem; margin-top: 1.2em; }
.prose p, .prose li { max-width: 78ch; color: var(--ink-2); }
.prose strong { color: var(--ink); }
.prose ul, .prose ol { padding-left: 1.3em; }
.prose li { margin-bottom: .4em; }
.md-table { overflow-x: auto; }
.md-table table { border-collapse: collapse; width: 100%; font-size: .84rem; }
.md-table th, .md-table td { border: 1px solid var(--line); padding: .4em .6em; text-align: left; }
.md-table th { background: var(--surface-2); font-family: var(--mono); font-size: .72rem; }

ol.turns { padding-left: 1.4em; }
ol.turns li { margin-bottom: .6em; padding-left: .2em; }
ol.turns code { white-space: pre-wrap; }

.compare { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem; align-items: start; }
@media (max-width: 820px) { .compare { grid-template-columns: 1fr; } }
.modelcol { border-radius: var(--radius); border: 1px solid var(--line); background: var(--surface); overflow: hidden; }
.modelcol .mhead { padding: .8em 1em; border-bottom: 1px solid var(--line); border-left: 4px solid var(--line-strong); }
.modelcol.a .mhead { border-left-color: var(--accent-a); }
.modelcol.b .mhead { border-left-color: var(--accent-b); }
.modelcol .mname { font-family: var(--mono); font-weight: 700; }
.modelcol.a .mname { color: var(--accent-a); } .modelcol.b .mname { color: var(--accent-b); }
.modelcol .meffort { font-size: .78rem; color: var(--ink-muted); }
.rep { padding: 1em; border-top: 1px dashed var(--line); }
.rep:first-of-type { border-top: none; }
.rep-label { font-family: var(--mono); font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; color: var(--ink-muted); margin-bottom: .6em; display:flex; align-items:center; gap:.5em; }

dl.kv { display: grid; grid-template-columns: auto 1fr; gap: .35em 1em; margin: .8em 0; font-size: .86rem; }
dl.kv dt { color: var(--ink-muted); font-family: var(--mono); font-size: .78rem; white-space: nowrap; }
dl.kv dd { margin: 0; font-variant-numeric: tabular-nums; }
.toolcalls { display: flex; flex-wrap: wrap; gap: .35em; margin-top: .3em; }
.toolcalls .tc { font-family: var(--mono); font-size: .72rem; background: var(--surface-2); border: 1px solid var(--line); border-radius: 4px; padding: .1em .45em; }

.check-row { display: flex; align-items: baseline; gap: .6em; padding: .35em 0; border-bottom: 1px solid var(--line); font-size: .86rem; }
.check-row:last-child { border-bottom: none; }
.check-row .clabel { font-family: var(--mono); font-weight: 700; min-width: 2.2em; }
.check-reason { color: var(--ink-2); font-size: .82rem; margin: .1em 0 .5em 2.8em; }

.harness-list { margin-top: .5em; display: flex; flex-direction: column; gap: .4em; }
.harness-item { font-size: .8rem; background: var(--harness-bg); border: 1px solid var(--line-strong); border-radius: 4px; padding: .45em .6em; color: var(--harness); }
.harness-item b { color: var(--ink); }

.linkrow { display: flex; flex-wrap: wrap; gap: .5em; margin-top: .8em; }
.linkrow a.filelink { font-family: var(--mono); font-size: .76rem; border: 1px solid var(--line-strong); border-radius: 4px;
  padding: .3em .6em; text-decoration: none; color: var(--ink-2); background: var(--surface-2); }
.linkrow a.filelink:hover { color: var(--ink); border-color: var(--ink-muted); }

.diffline { white-space: pre; }
.d-add { color: var(--good-ink); } .d-del { color: var(--critical); } .d-hunk { color: var(--accent-a); } .d-hdr { color: var(--ink); font-weight: 700; }

.transcripts { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem; }
@media (max-width: 820px) { .transcripts { grid-template-columns: 1fr; } }
.transcripts .tpane { border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; background: var(--surface); }
.transcripts .thead { padding: .5em .8em; font-family: var(--mono); font-size: .78rem; border-bottom: 1px solid var(--line); font-weight: 700; }
.transcripts iframe { width: 100%; height: 560px; border: none; background: var(--surface); display: block; }

.turn { border-bottom: 1px solid var(--line); padding: .7em .9em; font-size: .82rem; }
.turn:last-child { border-bottom: none; }
.turn .who { font-family: var(--mono); font-weight: 700; font-size: .72rem; text-transform: uppercase; letter-spacing: .05em; color: var(--ink-muted); }
.turn.user .who { color: var(--accent-a); }
.turn pre { margin: .4em 0 0; }

/* ---- calibration ---- */
.calib-grid { display: grid; gap: 1rem; margin-top: 1rem; }
.calib-card { border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); padding: 1rem 1.2rem; }
.calib-items { display: flex; gap: .4em; margin-top: .5em; flex-wrap: wrap; }

/* ---- meter (raptor) ---- */
.ladder { display: flex; flex-direction: column; gap: .5em; margin-top: .8em; }
.mstep { display: flex; align-items: center; gap: .8em; }
.mstep .mid { font-family: var(--mono); font-weight: 700; width: 2.6em; }
.mstep .mtrack { flex: 1; height: 1.4em; background: var(--surface-2); border-radius: 4px; overflow: hidden; border: 1px solid var(--line); position: relative; }
.mstep .mfill { height: 100%; }
.mstep.a .mfill { background: var(--accent-a); } .mstep.b .mfill { background: var(--accent-b); }
.mstep .mtime { font-family: var(--mono); font-size: .78rem; color: var(--ink-2); min-width: 5em; text-align: right; }
.shot-pair { display: grid; grid-template-columns: 1fr 1fr; gap: .8em; margin-top: .6em; }
.shot { border: 1px dashed var(--line-strong); border-radius: 4px; aspect-ratio: 320/200; display: flex; align-items: center;
  justify-content: center; color: var(--ink-muted); font-family: var(--mono); font-size: .72rem; background: var(--surface-2); text-align: center; padding: .5em; }

footer.sitefoot { margin-top: 4rem; padding-top: 1.5rem; border-top: 1px solid var(--line); color: var(--ink-muted); font-size: .78rem; }

@media (max-width: 640px) {
  body { font-size: 14.5px; }
  .shell { padding: 0 1rem 3rem; }
  h1 { font-size: 1.4rem; }
}
"""

JS = r"""
(function(){
  var KEY = 'ab-site-theme';
  var root = document.documentElement;
  function apply(t){ if(t){ root.setAttribute('data-theme', t); } else { root.removeAttribute('data-theme'); } }
  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch(e){}
  apply(saved);
  function label(){
    var t = root.getAttribute('data-theme');
    return t === 'dark' ? 'dark' : (t === 'light' ? 'light' : 'auto');
  }
  document.addEventListener('DOMContentLoaded', function(){
    var btn = document.getElementById('theme-toggle');
    if(!btn) return;
    btn.textContent = 'theme: ' + label();
    btn.addEventListener('click', function(){
      var cur = root.getAttribute('data-theme');
      var next = cur === null ? 'dark' : (cur === 'dark' ? 'light' : null);
      apply(next);
      try { if(next) localStorage.setItem(KEY, next); else localStorage.removeItem(KEY); } catch(e){}
      btn.textContent = 'theme: ' + label();
    });
  });
})();
"""


def page_shell(title: str, active: str, body: str, root_prefix: str = "") -> str:
    nav_items = [
        ("index.html", "Scoreboard"),
        ("calibration.html", "Calibration"),
        ("method.html", "Method"),
        ("raptor.html", "Raptor ladder"),
    ]
    nav = "".join(
        f'<a href="{root_prefix}{href}"{" class=\"active\"" if href.split(".")[0] == active else ""}>{label}</a>'
        for href, label in nav_items
    )
    banner_html = f'<div class="top-banner">{esc(BANNER_TEXT)}</div>' if BANNER_TEXT else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="stick-top">
{banner_html}
<div class="topbar"><div class="topbar-inner">
  <div class="brand">DSV4 vs Qwen3.8 &middot; coding A/B<small>pre-registered {esc("2026-08-20")}</small></div>
  <nav class="nav">{nav}</nav>
  <button class="theme-btn" id="theme-toggle" type="button">theme: auto</button>
</div></div>
</div>
<div class="shell">
{body}
<footer class="sitefoot">Every run, diff, log, transcript and calibration result on this site is published as generated &mdash;
including harness re-runs. No cherry-picking. See the <a href="{root_prefix}method.html">Method</a> page for the full pre-registered spec.</footer>
</div>
<script>{JS}</script>
</body>
</html>"""


# --------------------------------------------------------------------------
# Small render helpers
# --------------------------------------------------------------------------

def chip(state: str, text: str, n: Optional[str] = None) -> str:
    cls = {"pass": "pass", "fail": "fail", "mixed": "mixed", "harness": "harness"}.get(state, "unknown")
    ntxt = f'<span class="n">{esc(n)}</span>' if n else ""
    return f'<span class="chip {cls}">{esc(text)}{ntxt}</span>'


def pip(letter: str, val: Optional[bool]) -> str:
    cls = "pass" if val is True else ("fail" if val is False else "empty")
    mark = "\u2713" if val is True else ("\u2715" if val is False else "\u00b7")
    return f'<span class="pip {cls}" title="{esc(letter)}">{mark}</span>'

def pips_row(run: Run) -> str:
    parts = []
    for k in ("P1", "P2", "P3"):
        v, _ = run.check(k)
        parts.append(pip(k, v))
    return f'<span class="pips">{"".join(parts)}</span>'


def stars(value: Optional[int], scale: int, cls: str = "a") -> str:
    if value is None:
        return '<span class="na">\u2014</span>'
    scale = max(scale, value, 1)
    dots = "".join(f'<span class="star{" filled" if i < value else ""}"></span>' for i in range(scale))
    return f'<span class="star-row {cls}">{dots}</span>'


def model_badge_class(model_id: str) -> str:
    slot = MODELS.get(model_id, {}).get("slot", 1)
    return "accent-a" if slot == 1 else "accent-b"


def diff_to_html(text: str) -> str:
    out = []
    for line in text.split("\n"):
        e = esc(line)
        if line.startswith("+++") or line.startswith("---"):
            cls = "d-hdr"
        elif line.startswith("@@"):
            cls = "d-hunk"
        elif line.startswith("+"):
            cls = "d-add"
        elif line.startswith("-"):
            cls = "d-del"
        else:
            cls = ""
        out.append(f'<span class="diffline {cls}">{e}</span>')
    return "\n".join(out)


def render_transcript_jsonl(path: Path) -> str:
    """Best-effort turn-by-turn viewer for a jsonl session file. Lane C's
    shape (role/content/usage/secs) is read exactly; anything else (e.g. the
    real OMP event schema, not yet observed) falls back to a labeled JSON dump
    per line so nothing is silently dropped."""
    turns = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "<p>Could not read transcript.</p>"
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            continue
        role = d.get("role") or d.get("type") or "event"
        content = d.get("content")
        if content is None:
            content = d.get("text") or d.get("message")
        meta_bits = []
        if "usage" in d and isinstance(d["usage"], dict):
            u = d["usage"]
            meta_bits.append(f"{u.get('completion_tokens', '?')} tok")
        if "secs" in d:
            meta_bits.append(f"{d['secs']}s")
        if "reasoning_chars" in d:
            meta_bits.append(f"{d['reasoning_chars']} reasoning chars")
        meta = f' <span class="n">({", ".join(meta_bits)})</span>' if meta_bits else ""
        if content is None:
            content = json.dumps(d, indent=2)[:2000]
        turns.append(f'<div class="turn {esc(role)}"><div class="who">{esc(role)}{meta}</div><pre>{esc(content)}</pre></div>')
    if not turns:
        return "<p>Transcript present but empty or unrecognized format.</p>"
    return "".join(turns)


# --------------------------------------------------------------------------
# Artifact copying
# --------------------------------------------------------------------------

def copy_run_artifacts(run: Run, out_root: Path, task_id: str) -> dict:
    dest = out_root / "data" / task_id / run.label
    dest.mkdir(parents=True, exist_ok=True)
    links = {}
    for key, names in [
        ("diff", ["final.diff"]),
        ("tests_log", ["final-tests.log"]),
        ("driver_log", ["driver.log"]),
        ("install_log", ["install.log"]),
    ]:
        src = run.artifact(*names)
        if src:
            shutil.copy2(src, dest / src.name)
            links[key] = f"data/{task_id}/{run.label}/{src.name}"
    th = run.transcript_html
    if th:
        shutil.copy2(th, dest / "transcript.html")
        links["transcript_html"] = f"data/{task_id}/{run.label}/transcript.html"
    tj = run.transcript_jsonl
    if tj:
        shutil.copy2(tj, dest / tj.name)
        links["transcript_jsonl"] = f"data/{task_id}/{run.label}/{tj.name}"
        if "transcript_html" not in links:
            rendered = render_transcript_jsonl(tj)
            (dest / "transcript-rendered.html").write_text(
                f'<!doctype html><meta charset="utf-8"><style>{CSS}</style><body class="shell" style="padding-top:1rem">{rendered}</body>',
                encoding="utf-8",
            )
            links["transcript_html"] = f"data/{task_id}/{run.label}/transcript-rendered.html"
    return links


# --------------------------------------------------------------------------
# Verdict computation (mirrors SCORING.md section 5, literally)
# --------------------------------------------------------------------------

def compute_verdict(tasks: list) -> dict:
    """Counts primary PASSes per (model, lane) across 2A/2B tasks, checks
    whether one model wins the majority in every lane with data (no flip),
    and whether the margin survives both Qwen effort rows."""
    counts = {}  # (model, lane) -> [pass, total]
    for t in tasks:
        if t.task_class not in ("2A", "2B"):
            continue
        for r in t.runs:
            if r.overall_pass is None:
                continue
            key = (r.model, r.lane)
            counts.setdefault(key, [0, 0])
            counts[key][1] += 1
            if r.overall_pass:
                counts[key][0] += 1

    def lane_winner(lane: str, qwen_key: str):
        a = counts.get(("dsv4", lane), [0, 0])
        b = counts.get((qwen_key, lane), [0, 0])
        if a[1] == 0 and b[1] == 0:
            return None
        if a[0] == b[0]:
            return "tie"
        return "dsv4" if a[0] > b[0] else qwen_key

    lanes_with_data = [l for l in LANE_ORDER if counts.get(("dsv4", l), [0, 0])[1] or counts.get(("qwen", l), [0, 0])[1]]
    winners_default = [lane_winner(l, "qwen") for l in lanes_with_data]
    winners_medium = [lane_winner(l, "qwen-medium") for l in lanes_with_data]
    real_default = [w for w in winners_default if w]
    real_medium = [w for w in winners_medium if w]

    def decide(winners):
        non_tie = [w for w in winners if w != "tie"]
        if not non_tie:
            return None
        first = non_tie[0]
        no_flip = all(w in (first, "tie") for w in winners) and all(w == first for w in non_tie)
        return first if no_flip else "flip"

    d_default = decide(winners_default)
    d_medium = decide(winners_medium)

    if d_default and d_default != "flip" and d_default == d_medium:
        verdict = f"{MODELS[d_default]['display']} is clearly better"
        state = "decided"
    elif d_default == "flip" or d_medium == "flip":
        verdict = "No clear difference \u2014 ranking flips between lanes (harness-sensitive)"
        state = "tie"
    elif d_default and d_default != d_medium:
        verdict = "No clear difference \u2014 margin does not survive both Qwen effort settings"
        state = "tie"
    else:
        verdict = "No clear difference on these tasks yet (insufficient data)"
        state = "tie"

    return {"counts": counts, "verdict": verdict, "state": state, "lanes": lanes_with_data}


# --------------------------------------------------------------------------
# Page: index / scoreboard
# --------------------------------------------------------------------------

def cell_content(task: Task, model_id: str, lane: str, cells: dict) -> str:
    runs = cells.get((model_id, lane))
    if not runs:
        return '<span class="na">&mdash;</span>'
    if task.task_class == "2C":
        r = runs[0]
        items = r.score.get("checklist") or []
        if not items:
            return '<span class="na">pending</span>'
        passed = sum(1 for it in items if it.get("pass"))
        state = "pass" if passed == len(items) else ("fail" if passed == 0 else "mixed")
        return chip(state, f"{passed}/{len(items)}")
    if task.task_class == "2D":
        r = runs[0]
        ms = r.score.get("milestones") or []
        reached = r.score.get("milestones_reached", sum(1 for m in ms if m.get("pass")))
        state = "pass" if reached >= 4 else ("mixed" if reached >= 1 else "fail")
        return chip(state, f"M{reached}/5")
    passed = sum(1 for r in runs if r.overall_pass)
    unknown = sum(1 for r in runs if r.overall_pass is None)
    total = len(runs)
    if unknown == total:
        return '<span class="na">pending</span>'
    state = "pass" if passed == total - unknown and passed > 0 else ("fail" if passed == 0 else "mixed")
    label_txt = "PASS" if state == "pass" else ("FAIL" if state == "fail" else "MIXED")
    return chip(state, label_txt, n=f"{passed}/{total}")


def build_index(tasks: list, calib: dict, out: Path):
    columns = []
    for lane in LANE_ORDER:
        for model_id in MODEL_ORDER:
            if lane == "D":
                if model_id != "dsv4":
                    continue
            elif model_id == "qwen-medium" and lane != "A":
                continue
            columns.append((lane, model_id))

    thead_lane = "".join(
        f'<th colspan="{sum(1 for l, m in columns if l == lane)}">{esc(lane)} &middot; {esc(LANES[lane]["name"])}</th>'
        for lane in LANE_ORDER if any(l == lane for l, m in columns)
    )
    thead_model = "".join(f'<th>{esc(MODELS[m]["short"])}</th>' for l, m in columns)

    rows = []
    last_class = None
    for tid in TASK_ORDER:
        task = next((t for t in tasks if t.id == tid), None)
        if not task:
            continue
        if task.task_class != last_class:
            rows.append(f'<tr class="classhead"><td colspan="{1 + len(columns)}">{esc(task.task_class)} &middot; {esc(CLASS_LABELS[task.task_class])}</td></tr>')
            last_class = task.task_class
        cells = task.runs_by_cell()
        tds = []
        for lane, model_id in columns:
            if lane == "D":
                tds.append('<td class="cell"><span class="na">see public 0-shot results</span></td>')
                continue
            if lane not in task.meta.get("lanes", []):
                tds.append('<td class="cell"><span class="na">&mdash;</span></td>')
                continue
            tds.append(f'<td class="cell">{cell_content(task, model_id, lane, cells)}</td>')
        priv = ' <span class="badge">private</span>' if task.meta.get("private") else ""
        note = f'<span class="rowmeta">{esc(task.meta.get("note", ""))}</span>' if task.meta.get("note") else ""
        rows.append(
            f'<tr><th><a class="tasklink" href="task/{tid}.html">{esc(task.title)}</a>'
            f'<span class="rowmeta">{esc(task.meta.get("ref", tid))}{priv}</span>{note}</th>{"".join(tds)}</tr>'
        )

    verdict = compute_verdict(tasks)
    counts = verdict["counts"]
    tile_html = []
    for lane in verdict["lanes"]:
        a = counts.get(("dsv4", lane), [0, 0])
        b = counts.get(("qwen", lane), [0, 0])
        tile_html.append(
            f'<div class="tile a"><div class="tl">Lane {esc(lane)} &middot; DeepSeek</div>'
            f'<div class="tv">{a[0]}/{a[1]}</div><div class="ts">primary PASSes</div></div>'
        )
        tile_html.append(
            f'<div class="tile b"><div class="tl">Lane {esc(lane)} &middot; Qwen</div>'
            f'<div class="tv">{b[0]}/{b[1]}</div><div class="ts">primary PASSes</div></div>'
        )

    deeweb = next((t for t in tasks if t.id == "deeweb"), None)
    raptor = next((t for t in tasks if t.id == "raptor"), None)
    extra_tiles = []
    if deeweb and deeweb.runs:
        parts = []
        for r in deeweb.runs:
            items = r.score.get("checklist") or []
            passed = sum(1 for it in items if it.get("pass"))
            parts.append(f"{MODELS[r.model]['short']} {passed}/{len(items) or 9}")
        extra_tiles.append(f'<div class="tile"><div class="tl">deeweb CAL-7207 (n=1)</div><div class="tv" style="font-size:1rem">{" &middot; ".join(parts)}</div><div class="ts">acceptance criteria</div></div>')
    if raptor and raptor.runs:
        parts = []
        for r in raptor.runs:
            ms = r.score.get("milestones") or []
            reached = r.score.get("milestones_reached", sum(1 for m in ms if m.get("pass")))
            parts.append(f"{MODELS[r.model]['short']} M{reached}/5")
        extra_tiles.append(f'<div class="tile"><div class="tl">Raptor ladder (n=1)</div><div class="tv" style="font-size:1rem">{" &middot; ".join(parts)}</div><div class="ts"><a href="raptor.html">full ladder &rarr;</a></div></div>')

    body = f"""
<div class="page-head">
  <p class="eyebrow">Scoreboard</p>
  <h1>DeepSeek V4 Flash 0731 vs Qwen3.8-27B BF16</h1>
  <p class="lede">Multi-turn coding tasks, objective checks scored by script, harness events counted separately from
  model behavior, and a blinded human rubric reported alongside &mdash; never averaged into the verdict.
  See <a href="method.html">Method</a> for the full pre-registered spec.</p>
  <div class="verdict {verdict['state']}">
    <div class="vlabel">Computed verdict (from the published runs on this page)</div>
    <div class="vtext">{esc(verdict['verdict'])}</div>
    <blockquote class="rule">&ldquo;X is clearly better&rdquo; requires: X wins the majority of primary checks, AND no lane
    flips the ranking, AND the margin survives both Qwen effort settings. Anything short of that is published as
    &ldquo;no clear difference on these tasks&rdquo; &mdash; the honest outcome is an allowed outcome. (SCORING.md &sect;5)</blockquote>
  </div>
  <div class="tiles">{"".join(tile_html)}{"".join(extra_tiles)}</div>
</div>

<div class="section">
  <h2>Matrix</h2>
  <p class="lede">Rows = tasks, columns = model &times; lane. Cell = PASS/FAIL with n of reps run (bug-fix tasks are n=2),
  or a milestone/checklist score for Raptor and deeweb. Click a task name for the full breakdown.</p>
  <div class="table-wrap">
    <table class="board">
      <thead>
        <tr class="lanehead"><th></th>{thead_lane}</tr>
        <tr><th>Task</th>{thead_model}</tr>
      </thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </div>
</div>

<div class="section">
  <h2>Reading this table</h2>
  <p class="lede">A ranking that flips between lanes is reported as &ldquo;harness-sensitive,&rdquo; not averaged away.
  Ties are broken by process efficiency (wall-clock, then tokens, then turns) &mdash; see each task page.
  Harness events (malformed tool calls, parser errors, harness crashes) are never counted as model losses; a run
  killed by the harness is re-run once and the event stays in the report. See <a href="calibration.html">Calibration</a>
  for the per-harness gate each model had to clear before any of these numbers count.</p>
</div>
"""
    (out / "index.html").write_text(page_shell("Scoreboard \u2014 DSV4 vs Qwen3.8", "index", body), encoding="utf-8")


# --------------------------------------------------------------------------
# Page: task
# --------------------------------------------------------------------------

def run_column_block(run: Run, task: Task, links: dict) -> str:
    sec = run.secondary
    tok = sec.get("tokens") or {}
    tools = (sec.get("tool_calls") or {}).get("by_name") or {}
    diffi = sec.get("diff") or {}
    events = sec.get("harness_events") or []
    tert = run.tertiary

    if task.task_class == "2A" or task.task_class == "2B":
        checks_html = "".join(
            f'<div class="check-row"><span class="clabel">{k}</span>{pip(k, run.check(k)[0])}<span>{esc({"P1":"Reference test passes" if task.task_class=="2A" else "Repro test passes","P2":"No regressions","P3":"Test honesty"}.get(k,""))}</span></div>'
            + (f'<div class="check-reason">{esc(run.check(k)[1])}</div>' if run.check(k)[1] else "")
            for k in ("P1", "P2", "P3")
        )
        overall = run.overall_pass
        overall_chip = chip("pass" if overall else ("fail" if overall is False else "unknown"), "PASS" if overall else ("FAIL" if overall is False else "pending"))
        p4 = run.score.get("p4")
        p4_html = ""
        if p4:
            p4_html = f'<p class="rowmeta" style="margin-top:.6em">Lagging indicator (never scored): upstream PR {esc(p4.get("status","pending"))}{" &mdash; " + esc(p4["note"]) if p4.get("note") else ""}</p>'
        objective = f'<div>{overall_chip}</div><div style="margin-top:.6em">{checks_html}</div>{p4_html}'
    elif task.task_class == "2C":
        items = run.score.get("checklist") or []
        passed = sum(1 for it in items if it.get("pass"))
        rows = "".join(
            f'<div class="check-row"><span class="clabel">{"\u2713" if it.get("pass") else "\u2715"}</span><span>{esc(it.get("label",""))}</span></div>'
            for it in items
        )
        extra = run.score.get("checklist_extra") or {}
        extra_chips = " ".join(
            chip("pass" if extra.get(k) else "fail", k.replace("_", " "))
            for k in ("suite_green", "typecheck_clean", "lint_clean") if k in extra
        )
        objective = f'<div>{chip("pass" if passed==len(items) else ("fail" if passed==0 else "mixed"), f"{passed}/{len(items)}")} {extra_chips}</div><div style="margin-top:.6em">{rows}</div>'
    else:  # 2D
        ms = run.score.get("milestones") or []
        rows = "".join(
            f'<div class="mstep {"a" if run.model=="dsv4" else "b"}"><span class="mid">{esc(m.get("id"))}</span>'
            f'<div class="mtrack"><div class="mfill" style="width:{100 if m.get("pass") else 0}%"></div></div>'
            f'<span class="mtime">{fmt_wall(m.get("time_to_s"))}</span></div>'
            for m in ms
        )
        reached = run.score.get("milestones_reached", sum(1 for m in ms if m.get("pass")))
        objective = f'<div>{chip("pass" if reached>=4 else ("mixed" if reached>=1 else "fail"), f"M{reached}/5")}</div><div class="ladder" style="margin-top:.6em">{rows}</div>'

    tool_html = "".join(f'<span class="tc">{esc(k)} &times;{v}</span>' for k, v in tools.items())
    diff_files = diffi.get("files") or []
    metrics = f"""
<dl class="kv">
  <dt>wall-clock</dt><dd>{esc(fmt_wall(sec.get('wall_s')))}</dd>
  <dt>tokens (p/c/r)</dt><dd>{fnum(tok.get('prompt'))} / {fnum(tok.get('completion'))} / {fnum(tok.get('reasoning'))}</dd>
  <dt>tool calls</dt><dd>{fnum((sec.get('tool_calls') or {}).get('total', sum(tools.values()) if tools else None))}</dd>
  <dt>test runs</dt><dd>{fnum(sec.get('test_runs'))}</dd>
  <dt>reproduced first</dt><dd>{ "yes" if sec.get('reproduced_first') is True else ("no" if sec.get('reproduced_first') is False else "\u2014") }</dd>
  <dt>diff</dt><dd>+{fnum(diffi.get('added'))} / -{fnum(diffi.get('removed'))}, {len(diff_files)} file{'s' if len(diff_files)!=1 else ''}</dd>
  <dt>precision</dt><dd>{esc(sec.get('precision', '\u2014'))}</dd>
</dl>
{f'<div class="toolcalls">{tool_html}</div>' if tool_html else ''}
"""
    if events:
        ev_html = "".join(
            f'<div class="harness-item"><b>{esc(e.get("type","event"))}</b> turn {esc(e.get("turn","?"))}'
            f'{" (recovered)" if e.get("recoverable") else " (unrecovered)"} &mdash; {esc(e.get("detail",""))}</div>'
            for e in events
        )
        harness_block = f'<h4>Harness events <span class="badge">not a model loss</span></h4><div class="harness-list">{ev_html}</div>'
    else:
        harness_block = ""

    tert_rows = []
    scale = tert.get("scale", 2)
    for k, v in tert.items():
        if k in ("judge", "scale"):
            continue
        label_txt = k.replace("_", " ")
        tert_rows.append(f'<div class="check-row"><span style="min-width:9em">{esc(label_txt)}</span>{stars(v, scale, "a" if run.model=="dsv4" else "b")}</div>')
    tert_html = ""
    if tert_rows:
        judge = tert.get("judge", "blinded")
        tert_html = f'<h4>Tertiary (blinded rubric)</h4>{"".join(tert_rows)}<p class="rowmeta">judge: {esc(judge)}</p>'

    file_links = []
    label_map = {"diff": "diff", "tests_log": "tests log", "driver_log": "driver log", "install_log": "install log", "transcript_html": "transcript"}
    for key, txt in label_map.items():
        if key in links:
            file_links.append(f'<a class="filelink" href="{esc(links[key])}" target="_blank">{txt}</a>')
    diff_preview = ""
    dpath = links.get("__diff_path")
    if dpath:
        text = read_text(dpath, limit=6000)
        if text:
            diff_preview = f'<details style="margin-top:.8em"><summary style="cursor:pointer;font-family:var(--mono);font-size:.78rem;color:var(--ink-2)">diff preview</summary><pre>{diff_to_html(text)}</pre></details>'

    return f"""
<div class="rep">
  <div class="rep-label">rep {run.rep} <span class="badge">{esc(run.label)}</span></div>
  {objective}
  <h4>Process</h4>
  {metrics}
  {harness_block}
  {tert_html}
  <div class="linkrow">{''.join(file_links) if file_links else '<span class="na">no artifacts published yet</span>'}</div>
  {diff_preview}
</div>
"""


def build_task_page(task: Task, out: Path, root_prefix="../"):
    brief_html = f'<div class="prose">{render_markdown(task.brief_md)}</div>' if task.brief_md else "<p>Brief not yet published.</p>"
    turns_list = []
    opening_note = ""
    if task.turns:
        if task.turns.get("opening"):
            opening_note = '<p class="rowmeta">Opening brief delivered inline to the model in this lane (see brief above); scripted follow-ups below.</p>'
        turns_list = task.turns.get("turns", [])
    turns_html = "".join(f"<li><code>{esc(t)}</code></li>" for t in turns_list)
    test_cmd = (task.turns or {}).get("test_cmd")

    cells = task.runs_by_cell()
    lanes_present = [l for l in task.meta.get("lanes", []) if any(k[1] == l for k in cells)]
    if not lanes_present:
        lanes_present = task.meta.get("lanes", [])

    lane_sections = []
    for lane in lanes_present:
        model_ids = [m for m in MODEL_ORDER if (m, lane) in cells] or (["dsv4", "qwen"] if lane != "D" else [])
        cols = []
        transcripts = []
        for model_id in model_ids:
            runs = cells.get((model_id, lane), [])
            cls = "a" if MODELS[model_id]["slot"] == 1 else "b"
            blocks = []
            for r in runs:
                links = copy_run_artifacts(r, out, task.id)
                dpath = r.artifact("final.diff")
                if dpath:
                    links["__diff_path"] = dpath
                blocks.append(run_column_block(r, task, links))
                if "transcript_html" in links:
                    transcripts.append((model_id, cls, links["transcript_html"]))
            if not blocks:
                blocks = ['<div class="rep"><span class="na">no runs published yet</span></div>']
            cols.append(f"""
<div class="modelcol {cls}">
  <div class="mhead"><div class="mname">{esc(MODELS[model_id]['short'])}</div><div class="meffort">{esc(MODELS[model_id]['effort'])}</div></div>
  {''.join(blocks)}
</div>""")
        transcript_block = ""
        if len(transcripts) >= 2:
            panes = "".join(
                f'<div class="tpane"><div class="thead">{esc(MODELS[mid]["short"])}</div><iframe src="{esc(root_prefix)}{esc(link)}" loading="lazy"></iframe></div>'
                for mid, cls, link in transcripts[:2]
            )
            transcript_block = f'<h3>Session transcript</h3><div class="transcripts">{panes}</div>'
        lane_sections.append(f"""
<div class="section">
  <h2>Lane {esc(lane)} &middot; {esc(LANES[lane]['name'])}</h2>
  <p class="lede">{esc(LANES[lane]['desc'])}</p>
  <div class="compare">{''.join(cols)}</div>
  {transcript_block}
</div>""")

    note = f'<p class="lede" style="color:var(--warn)">{esc(task.meta.get("note"))}</p>' if task.meta.get("note") else ""
    priv = '<span class="badge">private &mdash; aggregate scores only</span>' if task.meta.get("private") else ""

    body = f"""
<div class="page-head">
  <p class="eyebrow"><a href="{root_prefix}index.html">&larr; Scoreboard</a> / {esc(CLASS_LABELS[task.task_class])}</p>
  <h1>{esc(task.title)}</h1>
  <div class="tagrow">
    <span class="badge">{esc(task.task_class)}</span>
    <span class="badge">{esc(task.meta.get('ref', task.id))}</span>
    {''.join(f'<span class="badge">lane {esc(l)}</span>' for l in task.meta.get('lanes', []))}
    {priv}
  </div>
  {note}
</div>

<details class="brief" open>
  <summary>Brief &mdash; exact text delivered to every model</summary>
  <div class="brief-body">{brief_html}</div>
</details>

{f'''<div class="section">
  <h2>Scripted follow-up turns</h2>
  {opening_note}
  <ol class="turns">{turns_html}</ol>
  {f'<p class="rowmeta">Test command: <code>{esc(test_cmd)}</code></p>' if test_cmd else ''}
</div>''' if turns_html else ''}

{''.join(lane_sections)}
"""
    (out / "task" / f"{task.id}.html").write_text(page_shell(f"{task.title} \u2014 A/B results", "task", body, root_prefix), encoding="utf-8")


# --------------------------------------------------------------------------
# Page: calibration
# --------------------------------------------------------------------------

def build_calibration(calib: dict, out: Path):
    cal_md = read_text(SCRIPT_DIR / "calibration.md")
    intro = f'<div class="prose">{render_markdown(cal_md)}</div>' if cal_md else ""
    cards = []
    for harness, entries in calib.items():
        for e in entries:
            items = e.get("items", [])
            passed = sum(1 for it in items if it.get("pass"))
            gate = passed == 5 and all((it.get("parse_errors", 0) or 0) == 0 or it.get("recovered") for it in items)
            model_id = e.get("model", e.get("label", "").split("-")[0])
            it_html = "".join(
                f'<span class="chip {"pass" if it.get("pass") else "fail"}" title="{esc(it.get("name",""))}">'
                f'{esc(it.get("id","?"))} {"\u2713" if it.get("pass") else "\u2715"}</span>'
                for it in items
            )
            cards.append(f"""
<div class="calib-card">
  <div class="tagrow">
    <span class="badge">{esc(harness)}</span>
    <span class="badge {model_badge_class(model_id)}">{esc(MODELS.get(model_id,{}).get('short', e.get('label')))}</span>
    {chip('pass' if gate else 'fail', 'GATE PASS' if gate else 'GATE FAIL')}
  </div>
  <div class="calib-items">{it_html}</div>
  <dl class="kv">
    <dt>tool calls</dt><dd>{fnum(sum(it.get('tool_calls',0) for it in items))}</dd>
    <dt>parse errors</dt><dd>{fnum(sum(it.get('parse_errors',0) for it in items))}</dd>
    <dt>wall-clock</dt><dd>{esc(fmt_wall(e.get('wall_s')))}</dd>
    <dt>tokens</dt><dd>{fnum((e.get('tokens') or {}).get('prompt'))} / {fnum((e.get('tokens') or {}).get('completion'))}</dd>
  </dl>
</div>""")
    body = f"""
<div class="page-head">
  <p class="eyebrow">Gate</p>
  <h1>Harness calibration</h1>
  <p class="lede">5 tool tasks per model &times; harness, run before anything head-to-head counts. Required: 5/5 with
  zero unrecoverable tool-call parse errors. A failing gate is a CONFIG problem, fixed and re-run &mdash; never
  compared on a failing gate.</p>
</div>
{intro}
<div class="section">
  <h2>Results</h2>
  <div class="calib-grid">{''.join(cards) if cards else '<p class="na">No calibration results published yet.</p>'}</div>
</div>
"""
    (out / "calibration.html").write_text(page_shell("Calibration \u2014 DSV4 vs Qwen3.8", "calibration", body), encoding="utf-8")


# --------------------------------------------------------------------------
# Page: method
# --------------------------------------------------------------------------

def build_method(scoring_path: Path, out: Path):
    md = read_text(scoring_path) or "# Method\n\nSCORING.md not found."
    body = f"""
<div class="page-head">
  <p class="eyebrow">Method</p>
  <h1>Pre-registered scoring spec</h1>
  <p class="lede">Rendered from <code>ab/SCORING.md</code>, unmodified. This is the exact document the scoreboard
  and task pages implement.</p>
</div>
<div class="prose section">{render_markdown(md)}</div>
"""
    (out / "method.html").write_text(page_shell("Method \u2014 DSV4 vs Qwen3.8", "method", body), encoding="utf-8")


# --------------------------------------------------------------------------
# Page: raptor ladder
# --------------------------------------------------------------------------

MILESTONE_LABELS = {
    "M1": "background + player ship render (SSIM \u2265 0.80, \u2265 90% palette)",
    "M2": "movement + fire spawns a projectile",
    "M3": "wave-1 enemies, HP/removal on hit, player can die",
    "M4": "HUD renders; Web Audio running, \u22651 SFX on fire",
    "M5": "sector-1 loop: wave 9 reached, sector-complete screen",
}


def build_raptor(task: Optional[Task], out: Path):
    rows = []
    shots = []
    if task and task.runs:
        for r in sorted(task.runs, key=lambda r: MODELS.get(r.model, {}).get("slot", 9)):
            cls = "a" if r.model == "dsv4" else "b"
            ms = {m.get("id"): m for m in (r.score.get("milestones") or [])}
            max_t = max([m.get("time_to_s") or 0 for m in ms.values()] + [1])
            rows.append(f'<div class="rowmeta" style="margin:.8em 0 .2em;font-family:var(--mono)">{esc(MODELS[r.model]["short"])}</div>')
            for mid in ("M1", "M2", "M3", "M4", "M5"):
                m = ms.get(mid, {})
                width = 0
                if m.get("pass"):
                    width = 100 if not m.get("time_to_s") else max(8, round(100 * m["time_to_s"] / max_t))
                rows.append(
                    f'<div class="mstep {cls}"><span class="mid" title="{esc(MILESTONE_LABELS.get(mid, ""))}">{mid}</span>'
                    f'<div class="mtrack"><div class="mfill" style="width:{width}%"></div></div>'
                    f'<span class="mtime">{fmt_wall(m.get("time_to_s")) if m.get("pass") else "not reached"}</span></div>'
                )
            sec = r.secondary
            reached = r.score.get("milestones_reached", sum(1 for m in ms.values() if m.get("pass")))
            tert = r.tertiary
            shots.append(f"""
<div class="modelcol {cls}">
  <div class="mhead"><div class="mname">{esc(MODELS[r.model]['short'])}</div><div class="meffort">reached M{reached}/5</div></div>
  <div class="rep">
    <dl class="kv">
      <dt>tokens</dt><dd>{fnum((sec.get('tokens') or {}).get('prompt'))} / {fnum((sec.get('tokens') or {}).get('completion'))}</dd>
      <dt>tool calls</dt><dd>{fnum((sec.get('tool_calls') or {}).get('total'))}</dd>
      <dt>reverts / dead-ends</dt><dd>{fnum(sec.get('reverts'))}</dd>
      <dt>SSIM @ M1 / M3</dt><dd>{fnum(ms.get('M1',{}).get('ssim'), 2)} / {fnum(ms.get('M3',{}).get('ssim'), 2)}</dd>
    </dl>
    <h4>Tertiary (Jason, 1&ndash;5)</h4>
    <div class="check-row"><span style="min-width:6em">fidelity</span>{stars(tert.get('fidelity'), tert.get('scale',5), cls)}</div>
    <div class="check-row"><span style="min-width:6em">feel</span>{stars(tert.get('feel'), tert.get('scale',5), cls)}</div>
    <div class="shot-pair">
      <div class="shot">reference (DOSBox)<br>M1 crop</div>
      <div class="shot">{esc(MODELS[r.model]['short'])} build<br>M1 crop &mdash; screenshot pending</div>
    </div>
  </div>
</div>""")

    body = f"""
<div class="page-head">
  <p class="eyebrow">2D</p>
  <h1>Raptor &rarr; web port ladder</h1>
  <p class="lede">Fixed budget per model: same scripted milestone turns, same wall-clock cap, set before the run.
  Highest milestone reached with its acceptance check passing, 0&ndash;5, each check scripted in Playwright against
  <code>window.__raptor</code>. n=1 (cost), stated plainly.</p>
</div>
<div class="section">
  <h2>Milestones</h2>
  <dl class="kv" style="grid-template-columns:auto 1fr">{''.join(f'<dt>{esc(mid)}</dt><dd>{esc(lbl)}</dd>' for mid, lbl in MILESTONE_LABELS.items())}</dl>
  <div class="ladder">{''.join(rows) if rows else '<p class="na">No Raptor runs published yet.</p>'}</div>
</div>
<div class="section">
  <h2>Per-model detail</h2>
  <div class="compare">{''.join(shots) if shots else ''}</div>
</div>
<div class="section">
  <h2>Grader interface</h2>
  <p class="lede">A canvas <code>#raptor-canvas</code> at a fixed 320&times;200 internal buffer; arrow keys move,
  Space fires; a live <code>window.__raptor</code> object exposes player/projectiles/enemies/HUD/audio/wave state
  for the Playwright grader to poll. See <code>_raptor-support/brief-draft.md</code> for the full contract.</p>
</div>
"""
    (out / "raptor.html").write_text(page_shell("Raptor ladder \u2014 DSV4 vs Qwen3.8", "raptor", body), encoding="utf-8")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", default="D:/dev/ab-tasks", help="root containing _briefs/, _calib/, _runs/")
    ap.add_argument("--out", default="D:/dev/ab-tasks/_site", help="output directory for the built site")
    ap.add_argument("--scoring", default=str(SCRIPT_DIR / "SCORING.md"), help="path to SCORING.md")
    ap.add_argument("--banner", default=None,
                     help='prominent, non-dismissable text shown at the top of every page (e.g. "SAMPLE DATA -- '
                          'fixture, not results"). Auto-enabled with that exact text when --runs points at a path '
                          'containing "_runs-fixture" or "fixture"; pass an explicit value to override, or '
                          '--banner "" to force it off.')
    args = ap.parse_args()

    root = Path(args.runs)
    out = Path(args.out)

    global BANNER_TEXT
    if args.banner is not None:
        BANNER_TEXT = args.banner or None
    else:
        runs_str = str(root).replace("\\", "/").lower()
        if "_runs-fixture" in runs_str or "fixture" in runs_str:
            BANNER_TEXT = "SAMPLE DATA — fixture, not results"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "task").mkdir(exist_ok=True)
    (out / "data").mkdir(exist_ok=True)

    tasks = [load_task(root, tid) for tid in TASK_ORDER if tid in TASKS_META]
    calib = load_calibration(root)

    build_index(tasks, calib, out)
    for t in tasks:
        build_task_page(t, out)
    build_calibration(calib, out)
    build_method(Path(args.scoring), out)
    raptor_task = next((t for t in tasks if t.id == "raptor"), None)
    build_raptor(raptor_task, out)

    n_runs = sum(len(t.runs) for t in tasks)
    print(f"Built site: {out}")
    print(f"  tasks: {len(tasks)}  runs found: {n_runs}  calibration harnesses: {len(calib)}")
    print(f"  banner: {BANNER_TEXT!r}" if BANNER_TEXT else "  banner: (none)")
    print(f"  open: {out / 'index.html'}")


if __name__ == "__main__":
    main()
