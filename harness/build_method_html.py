#!/usr/bin/env python3
"""
Builds ab/method.html from ab/METHODOLOGY.md and ab/SCORING.md.

Regenerate any time either .md changes:

    python build_method_html.py

Output is a *content-only* HTML fragment (no <!DOCTYPE>/<html>/<head>/<body>) so
it can be published directly as a claude.ai Artifact -- the artifact host wraps
it. All CSS/JS is inlined; the only network dependency is a Google Fonts
stylesheet link (with real fallback stacks) for Source Serif 4 / IBM Plex.

This is a small hand-rolled Markdown -> HTML converter, not a general-purpose
one. It supports exactly the subset used by METHODOLOGY.md and SCORING.md:
ATX headings (#..####), paragraphs, ordered/unordered lists (with wrapped
continuation lines), blockquotes (recursively parsed, so a list can live
inside a blockquote), fenced code blocks, GFM pipe tables, and inline code /
bold / italics / links. It is deliberately not a full CommonMark
implementation.
"""

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METHOD_MD = ROOT / "METHODOLOGY.md"
SCORING_MD = ROOT / "SCORING.md"
OUT_HTML = ROOT / "method.html"


# --------------------------------------------------------------------------
# Inline parsing: code spans, bold, italics, links. HTML-escapes raw text.
# --------------------------------------------------------------------------

def inline(text: str) -> str:
    text = html.escape(text, quote=False)

    stash = []

    def stash_code(m):
        stash.append(f"<code>{m.group(1)}</code>")
        return f"\x00{len(stash) - 1}\x00"

    # Code spans first, so nothing inside them is touched by bold/italic/link.
    text = re.sub(r"`([^`]+)`", stash_code, text)

    # Links: [text](url) -- text may itself contain a stashed code token.
    def link_repl(m):
        link_text, url = m.group(1), m.group(2)
        safe_url = html.escape(url, quote=True)
        return f'<a href="{safe_url}">{link_text}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_repl, text)

    # Bold, then italic (single asterisk; docs don't use _underscore_ emphasis).
    text = re.sub(r"\*\*([^*]+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", text)

    for i, val in enumerate(stash):
        text = text.replace(f"\x00{i}\x00", val)

    return text


# --------------------------------------------------------------------------
# Heading ids
# --------------------------------------------------------------------------

_id_re = re.compile(r"[^a-z0-9]+")


def make_id(text: str, registry: dict) -> str:
    plain = text.replace("`", "").replace("*", "")
    slug = _id_re.sub("-", plain.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug) or "section"
    if len(slug) > 64:
        slug = slug[:64].rsplit("-", 1)[0] or slug[:64]
    base = slug
    n = registry.get(base, 0)
    registry[base] = n + 1
    if n == 0:
        return base
    slug = f"{base}-{n + 1}"
    registry[slug] = 1
    return slug


# --------------------------------------------------------------------------
# Block-level parsing
# --------------------------------------------------------------------------

FENCE_RE = re.compile(r"^```(\w*)\s*$")
HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
UL_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")
OL_RE = re.compile(r"^(\s*)\d+[.)]\s+(.*)$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")


def render_code_block(code: str, lang: str) -> str:
    cls = f' class="lang-{html.escape(lang)}"' if lang else ""
    escaped = html.escape(code, quote=False)
    return f'<div class="code-wrap"><pre><code{cls}>{escaped}</code></pre></div>'


def parse_table(lines, start):
    header = [c.strip() for c in lines[start].strip().strip("|").split("|")]
    sep = [c.strip() for c in lines[start + 1].strip().strip("|").split("|")]
    aligns = []
    for c in sep:
        left, right = c.startswith(":"), c.endswith(":")
        if left and right:
            aligns.append("center")
        elif right:
            aligns.append("right")
        elif left:
            aligns.append("left")
        else:
            aligns.append("")
    i = start + 2
    rows = []
    while i < len(lines) and "|" in lines[i] and lines[i].strip():
        rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
        i += 1

    def style(idx):
        a = aligns[idx] if idx < len(aligns) else ""
        return f' style="text-align:{a}"' if a else ""

    thead = "<tr>" + "".join(
        f"<th{style(j)}>{inline(c)}</th>" for j, c in enumerate(header)
    ) + "</tr>"
    tbody_rows = []
    for r in rows:
        cells = "".join(f"<td{style(j)}>{inline(c)}</td>" for j, c in enumerate(r))
        tbody_rows.append(f"<tr>{cells}</tr>")
    tbody = "".join(tbody_rows)
    table_html = (
        '<div class="table-wrap"><table class="md-table">'
        f"<thead>{thead}</thead><tbody>{tbody}</tbody>"
        "</table></div>"
    )
    return table_html, i - start


def parse_list(lines, start, headings, registry):
    is_ol = bool(OL_RE.match(lines[start]))
    marker_re = OL_RE if is_ol else UL_RE
    base_indent = len(marker_re.match(lines[start]).group(1))

    items = []  # list of list-of-source-lines (joined later)
    i = start
    n = len(lines)
    current = None

    while i < n:
        line = lines[i]
        if line.strip() == "":
            # Peek ahead: does the list continue after this blank line?
            j = i + 1
            if j < n and marker_re.match(lines[j]) and len(marker_re.match(lines[j]).group(1)) == base_indent:
                i += 1
                continue
            break
        m = marker_re.match(line)
        if m and len(m.group(1)) == base_indent:
            current = [m.group(2)]
            items.append(current)
            i += 1
            continue
        if current is not None and (line.startswith(" " * (base_indent + 2)) or line.startswith(" " * (base_indent + 3))):
            current.append(line.strip())
            i += 1
            continue
        break

    tag = "ol" if is_ol else "ul"
    li_html = []
    for it in items:
        text = " ".join(s for s in it if s != "")
        li_html.append(f"<li>{inline(text)}</li>")
    out = f"<{tag}>" + "".join(li_html) + f"</{tag}>"
    return out, i - start


def dedent_blockquote(lines):
    out = []
    for line in lines:
        rest = line[1:] if line.startswith(">") else line
        if rest.startswith(" "):
            rest = rest[1:]
        out.append(rest)
    return out


def parse_blocks(lines, headings, registry):
    parts = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        if line.strip() == "":
            i += 1
            continue

        fence = FENCE_RE.match(line)
        if fence:
            lang = fence.group(1)
            i += 1
            code_lines = []
            while i < n and not re.match(r"^```\s*$", lines[i]):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            parts.append(render_code_block("\n".join(code_lines), lang))
            continue

        m = HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            hid = make_id(text, registry)
            headings.append((level, hid, text))
            parts.append(f'<h{level} id="{hid}">{inline(text)}</h{level}>')
            i += 1
            continue

        if line.startswith(">"):
            bq_lines = []
            while i < n and lines[i].startswith(">"):
                bq_lines.append(lines[i])
                i += 1
            inner = parse_blocks(dedent_blockquote(bq_lines), headings, registry)
            parts.append(f"<blockquote>{inner}</blockquote>")
            continue

        if i + 1 < n and "|" in line and TABLE_SEP_RE.match(lines[i + 1]):
            table_html, consumed = parse_table(lines, i)
            parts.append(table_html)
            i += consumed
            continue

        if UL_RE.match(line) or OL_RE.match(line):
            list_html, consumed = parse_list(lines, i, headings, registry)
            parts.append(list_html)
            i += consumed
            continue

        para_lines = []
        while (
            i < n
            and lines[i].strip() != ""
            and not HEADING_RE.match(lines[i])
            and not lines[i].startswith(">")
            and not FENCE_RE.match(lines[i])
            and not UL_RE.match(lines[i])
            and not OL_RE.match(lines[i])
        ):
            para_lines.append(lines[i].strip())
            i += 1
        parts.append(f"<p>{inline(' '.join(para_lines))}</p>")

    return "\n".join(parts)


def convert(md_text: str, headings, registry):
    lines = md_text.splitlines()
    return parse_blocks(lines, headings, registry)


# --------------------------------------------------------------------------
# Page assembly
# --------------------------------------------------------------------------

CSS = """
:root {
  color-scheme: light;
  --paper:        #f6f6f3;
  --surface:      #fcfcfa;
  --surface-2:    #ecece7;
  --ink:          #14171a;
  --ink-2:        #494c50;
  --ink-muted:    #82858a;
  --line:         #dcdcd7;
  --line-strong:  #bcbcb5;
  --accent:       #0e6660;
  --accent-ink:   #094440;
  --accent-soft:  rgba(14,102,96,.09);
  --model-a:      #2467b8;
  --model-b:      #b5541c;
  --shadow:       0 1px 2px rgba(20,23,26,.05), 0 6px 20px rgba(20,23,26,.05);
  --radius:       7px;
  --serif: "Source Serif 4", Georgia, "Iowan Old Style", "Times New Roman", serif;
  --sans:  "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, Arial, sans-serif;
  --mono:  "IBM Plex Mono", ui-monospace, "Cascadia Mono", "SF Mono", Consolas, "Liberation Mono", monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --paper:        #101213;
    --surface:      #17191b;
    --surface-2:    #1e2123;
    --ink:          #eef0ef;
    --ink-2:        #c2c5c3;
    --ink-muted:    #8b8e8c;
    --line:         #292c2d;
    --line-strong:  #3a3d3e;
    --accent:       #3fb2a8;
    --accent-ink:   #bdeae4;
    --accent-soft:  rgba(63,178,168,.14);
    --model-a:      #6da3e0;
    --model-b:      #e2954f;
    --shadow:       0 1px 2px rgba(0,0,0,.35), 0 6px 20px rgba(0,0,0,.3);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --paper:        #101213;
  --surface:      #17191b;
  --surface-2:    #1e2123;
  --ink:          #eef0ef;
  --ink-2:        #c2c5c3;
  --ink-muted:    #8b8e8c;
  --line:         #292c2d;
  --line-strong:  #3a3d3e;
  --accent:       #3fb2a8;
  --accent-ink:   #bdeae4;
  --accent-soft:  rgba(63,178,168,.14);
  --model-a:      #6da3e0;
  --model-b:      #e2954f;
  --shadow:       0 1px 2px rgba(0,0,0,.35), 0 6px 20px rgba(0,0,0,.3);
}

* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 16px;
  line-height: 1.6;
  text-rendering: optimizeLegibility;
  font-variant-numeric: tabular-nums;
}
::selection { background: var(--accent-soft); }

.page { max-width: 74rem; margin: 0 auto; padding: 0 1.5rem 5rem; }

/* -------- masthead -------- */
.masthead { padding: 3.2rem 0 2rem; max-width: 52rem; }
.eyebrow {
  font-family: var(--mono); font-size: .78rem; text-transform: uppercase;
  letter-spacing: .09em; color: var(--ink-muted); margin: 0 0 .9em;
}
.masthead h1 {
  font-family: var(--serif); font-weight: 600; text-wrap: balance;
  font-size: clamp(1.9rem, 1.4rem + 2vw, 2.8rem);
  line-height: 1.15; margin: 0 0 .5em; letter-spacing: -0.01em;
}
.masthead h1 .model-a { color: var(--model-a); }
.masthead h1 .model-b { color: var(--model-b); }
.masthead .dek {
  font-size: 1.08rem; color: var(--ink-2); max-width: 46rem; margin: 0 0 1.1em;
}
.masthead .meta {
  font-family: var(--mono); font-size: .8rem; color: var(--ink-muted);
  display: flex; gap: .6em; flex-wrap: wrap; align-items: center;
}
.masthead .meta .dot { color: var(--line-strong); }
.masthead .meta strong { color: var(--ink-2); font-weight: 600; }

/* -------- layout: sticky TOC rail + doc column -------- */
.layout { display: grid; grid-template-columns: 15.5rem minmax(0, 1fr); gap: 3rem; align-items: start; }

nav.toc {
  position: sticky; top: 1.5rem;
  max-height: calc(100vh - 3rem); overflow-y: auto;
  padding: 1.1rem 1.2rem; border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--surface); box-shadow: var(--shadow);
}
nav.toc h2 {
  font-family: var(--mono); font-size: .72rem; text-transform: uppercase;
  letter-spacing: .08em; color: var(--ink-muted); margin: 0 0 .6em;
}
nav.toc .toc-group + .toc-group { margin-top: 1.4em; padding-top: 1.2em; border-top: 1px solid var(--line); }
nav.toc ol, nav.toc ul { list-style: none; margin: 0; padding: 0; }
nav.toc li { margin: 0; }
nav.toc a {
  display: block; padding: .3em 0; font-family: var(--mono); font-size: .82rem;
  color: var(--ink-2); text-decoration: none; border-left: 2px solid transparent;
  padding-left: .7em; margin-left: -.7em; line-height: 1.4;
}
nav.toc a:hover { color: var(--ink); }
nav.toc a.active { color: var(--accent-ink); border-left-color: var(--accent); font-weight: 500; }
nav.toc > details > summary { display: none; }

@media (max-width: 62rem) {
  .layout { grid-template-columns: 1fr; gap: 1.25rem; }
  nav.toc {
    position: sticky; top: 0; z-index: 20; max-height: none;
    padding: 0; border-radius: 0; border: none; border-bottom: 1px solid var(--line);
    background: color-mix(in srgb, var(--surface) 92%, transparent);
    backdrop-filter: blur(8px);
    box-shadow: none;
  }
  nav.toc > details { padding: .8rem 1.25rem; }
  nav.toc > details > summary {
    display: flex; cursor: pointer;
    font-family: var(--mono); font-size: .8rem; color: var(--ink-2);
    list-style: none; align-items: center; gap: .5em;
  }
  nav.toc > details > summary::-webkit-details-marker { display: none; }
  nav.toc > details > summary::before { content: "\\25B8"; transition: transform .15s; color: var(--ink-muted); }
  nav.toc > details[open] > summary::before { transform: rotate(90deg); }
  nav.toc > details[open] { padding-bottom: 1.1rem; }
  nav.toc .toc-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 1.2rem; margin-top: .8rem; }
  nav.toc .toc-group + .toc-group { margin-top: 0; padding-top: 0; border-top: none; }
}

/* -------- document body -------- */
.doc { min-width: 0; padding-bottom: 2rem; }
.doc h1.part-title {
  font-family: var(--serif); font-weight: 600; font-size: clamp(1.55rem, 1.25rem + 1.2vw, 2.05rem);
  line-height: 1.2; text-wrap: balance; margin: 0 0 .3em; letter-spacing: -0.01em;
  scroll-margin-top: 1.5rem;
}
.doc .part-kicker {
  font-family: var(--mono); font-size: .78rem; text-transform: uppercase; letter-spacing: .08em;
  color: var(--accent-ink); margin: 2.4rem 0 .5em;
}
.doc .part-lede { color: var(--ink-2); max-width: 65ch; margin: 0 0 1.6em; font-size: 1rem; }
.doc h2 {
  font-family: var(--serif); font-weight: 600; font-size: 1.4rem; line-height: 1.3;
  text-wrap: balance; margin: 2.1em 0 .55em; letter-spacing: -0.005em;
  scroll-margin-top: 1.5rem;
}
.doc h3 {
  font-family: var(--serif); font-weight: 600; font-size: 1.12rem; line-height: 1.35;
  text-wrap: balance; margin: 1.7em 0 .5em; color: var(--ink);
  scroll-margin-top: 1.5rem;
}
.doc h2:first-of-type { margin-top: 1.4em; }
.doc p { margin: 0 0 1.05em; max-width: 65ch; }
.doc ul, .doc ol { margin: 0 0 1.1em; padding-left: 1.4em; max-width: 65ch; }
.doc li { margin: 0 0 .5em; }
.doc li:last-child { margin-bottom: 0; }
.doc li::marker { color: var(--ink-muted); font-family: var(--mono); font-size: .92em; }
.doc strong { font-weight: 600; color: var(--ink); }
.doc em { font-style: italic; }
.doc a { color: var(--accent-ink); text-decoration-color: color-mix(in srgb, var(--accent) 45%, transparent); text-underline-offset: .15em; }
.doc a:hover { text-decoration-color: currentColor; }
.doc code { font-family: var(--mono); font-size: .88em; background: var(--surface-2); padding: .12em .38em; border-radius: 4px; }

.doc blockquote {
  margin: 1.4em 0; padding: .2em 0 .2em 1.1em; border-left: 3px solid var(--accent);
  color: var(--ink-2); max-width: 65ch;
}
.doc blockquote p { margin: 0 0 .9em; }
.doc blockquote ol, .doc blockquote ul { margin: .3em 0 .9em; }
.doc blockquote > *:last-child { margin-bottom: 0; }

.code-wrap { overflow-x: auto; margin: 1.3em 0; max-width: 100%; }
.doc pre {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
  padding: .95em 1.1em; margin: 0; font-size: .85rem; line-height: 1.55;
}
.doc pre code { background: none; padding: 0; font-size: 1em; }

.table-wrap { overflow-x: auto; margin: 1.4em 0; border: 1px solid var(--line); border-radius: var(--radius); }
table.md-table { border-collapse: collapse; width: 100%; font-size: .88rem; }
table.md-table th, table.md-table td { padding: .55em .8em; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
table.md-table th { font-family: var(--mono); font-size: .75rem; text-transform: uppercase; letter-spacing: .04em; color: var(--ink-muted); background: var(--surface-2); }
table.md-table tr:last-child td { border-bottom: none; }

hr.part-divider { border: none; border-top: 1px solid var(--line-strong); margin: 3.2rem 0 0; }

.doc-footer {
  margin-top: 3.5rem; padding-top: 1.5rem; border-top: 1px solid var(--line);
  font-family: var(--mono); font-size: .78rem; color: var(--ink-muted); max-width: 65ch;
}
.doc-footer a { color: var(--ink-muted); }

@media (max-width: 30rem) {
  .masthead { padding-top: 2.2rem; }
}
"""

SCRIPT = """
(function () {
  try {
    var links = Array.prototype.slice.call(document.querySelectorAll('nav.toc a[href^="#"]'));
    if (!links.length || !('IntersectionObserver' in window)) return;
    var map = {};
    links.forEach(function (a) {
      var id = a.getAttribute('href').slice(1);
      var el = document.getElementById(id);
      if (el) map[id] = a;
    });
    var current = null;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var link = map[entry.target.id];
        if (!link) return;
        if (entry.isIntersecting) {
          if (current) current.classList.remove('active');
          link.classList.add('active');
          current = link;
        }
      });
    }, { rootMargin: '-10% 0px -70% 0px', threshold: 0 });
    Object.keys(map).forEach(function (id) {
      io.observe(document.getElementById(id));
    });
  } catch (e) { /* non-essential */ }
})();
"""


def build_toc(headings, only_level=2):
    items = []
    for level, hid, text in headings:
        if level != only_level:
            continue
        items.append(f'<li><a href="#{hid}">{inline(text)}</a></li>')
    return "<ul>" + "".join(items) + "</ul>"


def main():
    method_md = METHOD_MD.read_text(encoding="utf-8")
    scoring_md = SCORING_MD.read_text(encoding="utf-8")

    registry = {}

    # Split off each doc's own H1 title line so we can render it as a
    # part-title (h1 element, styled as a big display heading) rather than
    # burying it as a generic <h2>, while the page's single true <h1> lives
    # in the masthead.
    def split_title(md_text):
        lines = md_text.splitlines()
        title_line = lines[0]
        m = HEADING_RE.match(title_line)
        title_text = m.group(2).strip() if m else title_line.strip("# ").strip()
        rest = "\n".join(lines[1:])
        return title_text, rest

    method_title, method_rest = split_title(method_md)
    scoring_title, scoring_rest = split_title(scoring_md)

    # Rewrite the METHODOLOGY.md cross-reference links to SCORING.md so they
    # jump to the Scoring part of this same page instead of a dead relative
    # link; leave other relative links (e.g. calibration.md) untouched.
    method_rest = method_rest.replace("(./SCORING.md)", "(#scoring)")

    # Reserve the "methodology" / "scoring" ids used by the hard-coded part
    # headings below, so any body heading that happens to slugify the same
    # way gets a disambiguating suffix instead of a duplicate id.
    registry["methodology"] = 1
    registry["scoring"] = 1

    method_headings = []
    scoring_headings = []
    method_body = convert(method_rest, method_headings, registry)
    scoring_body = convert(scoring_rest, scoring_headings, registry)

    methodology_toc = build_toc(method_headings, only_level=2)
    scoring_toc = build_toc(scoring_headings, only_level=2)

    page_title = "DeepSeek V4 Flash vs Qwen3.8-27B · Methodology"

    html_out = f"""<title>{page_title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;8..60,600;8..60,700&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
<div class="page">
  <header class="masthead">
    <p class="eyebrow">Pre-registered 2026-08-20 &middot; before any comparison run</p>
    <h1 id="top"><span class="model-a">DeepSeek V4 Flash</span> vs <span class="model-b">Qwen3.8-27B</span></h1>
    <p class="dek">How we compared two models on real multi-turn coding work, and the scoring
    spec we committed to before running anything &mdash; published so the work can be checked
    or repeated.</p>
    <p class="meta"><strong>Two documents.</strong><span class="dot">&middot;</span>Methodology summarizes the spec<span class="dot">&middot;</span><a href="#scoring" style="color:inherit">SCORING.md is the source of truth</a> on any disagreement</p>
  </header>

  <div class="layout">
    <nav class="toc" aria-label="Contents">
      <details open id="toc-details">
        <summary>Contents</summary>
        <div class="toc-cols">
          <div class="toc-group">
            <h2 id="toc-methodology">Methodology</h2>
            {methodology_toc}
          </div>
          <div class="toc-group">
            <h2 id="toc-scoring">Scoring spec</h2>
            {scoring_toc}
          </div>
        </div>
      </details>
    </nav>

    <main class="doc">
      <h1 class="part-title" id="methodology">{inline(method_title)}</h1>
      {method_body}

      <hr class="part-divider">
      <p class="part-kicker">Part two</p>
      <p class="part-lede">The pre-registered scoring spec &mdash; the exact PASS/FAIL logic behind every
      number in the methodology above, time-stamped before any comparison run.</p>
      <h1 class="part-title" id="scoring">{inline(scoring_title)}</h1>
      {scoring_body}

      <footer class="doc-footer">
        Generated from <code>METHODOLOGY.md</code> and <code>SCORING.md</code> by
        <code>build_method_html.py</code> &mdash; edits to either source file flow through on
        the next build. Pre-registered 2026-08-20, before any comparison run.
      </footer>
    </main>
  </div>
</div>
<script>{SCRIPT}</script>
"""

    OUT_HTML.write_text(html_out, encoding="utf-8")
    print(f"Wrote {OUT_HTML} ({OUT_HTML.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
