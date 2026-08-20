"""Lane C — "no harness" multi-turn runner.

Plain chat completions, ZERO tools exposed to the model. A scripted human sits at the
chat box and does only what a person would: paste a file when asked, apply a full-file
or unified-diff the model returns, run the project's test command and paste the output
back, and deliver the pre-written follow-up turns at fixed points. The same script runs
for every model, so the only variable is the model.

usage:
  python lane_c_runner.py --task tasks/zombie-mod.json --model dsv4 [--out runs/]
  task json: {
    "name": "zombie-mod",
    "repo": "D:/path/to/worktree",            # files live here; runner reads/writes inside it only
    "test_cmd": "npm test -- --run",           # optional; "" = no tests (human just says 'ok, next')
    "opening": "<the task brief>",
    "turns": ["<follow-up 1>", "<follow-up 2>", ...],   # delivered in order once the model says it is done with the current step
    "max_exchanges": 40,
    "seed_files": ["index.html"]               # pasted into the opening message (optional)
  }
Endpoints/effort come from MODELS below; DSV4 Max is baked server-side, Qwen effort is a
per-request chat_template_kwargs (verified 2026-08-20 via prompt-token render diff).
"""
import argparse, json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

MODELS = {
    "dsv4":        ("http://localhost:8002", "deepseek-v4-flash-0731", {}),
    "qwen":        ("http://localhost:8001", "qwen3.8-27b-bf16", {}),
    "qwen-medium": ("http://localhost:8001", "qwen3.8-27b-bf16", {"chat_template_kwargs": {"reasoning_effort": "medium"}}),
}

HUMAN_SYSTEM = None  # no system prompt: the model gets exactly what a chat-box user gives it

FILE_REQ = re.compile(r"(?:show|paste|send|share|see|provide|need|open|cat)\s+(?:me\s+)?(?:the\s+)?(?:contents?\s+of\s+)?[`\"']?([\w./\\-]+\.[\w]+)[`\"']?", re.I)
FENCE = re.compile(r"```(?P<lang>[\w+-]*)(?:\s*(?:title=|file=|path=)?[\"']?(?P<path>[\w./\\-]+\.[\w]+)[\"']?)?\s*\n(?P<body>.*?)```", re.S)
DIFF_HDR = re.compile(r"^\+\+\+\s+(?:b/)?([\w./\\-]+)", re.M)

def chat(base, model, messages, extra, max_tokens):
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "stream": False}
    body.update(extra)
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=3600) as r:
        d = json.loads(r.read().decode())
    msg = d["choices"][0]["message"]
    return msg.get("content") or "", msg.get("reasoning_content") or msg.get("reasoning") or "", d.get("usage", {}), time.time() - t0

def safe_path(repo: Path, rel: str):
    p = (repo / rel).resolve()
    if repo.resolve() not in p.parents and p != repo.resolve():
        return None
    return p

def apply_model_output(repo: Path, text: str, log):
    """Apply full-file code blocks that name a path, or unified diffs. Returns list of touched files."""
    touched = []
    # unified diffs first
    for m in re.finditer(r"```(?:diff|patch)\s*\n(.*?)```", text, re.S):
        patch = m.group(1)
        pf = repo / ".lane_c.patch"; pf.write_text(patch, encoding="utf-8")
        r = subprocess.run(["git", "apply", "--whitespace=nowarn", str(pf)], cwd=repo, capture_output=True, text=True)
        log(f"[human] git apply -> rc={r.returncode} {r.stderr.strip()[:200]}")
        if r.returncode == 0: touched += DIFF_HDR.findall(patch)
        pf.unlink(missing_ok=True)
    # full files: fenced block whose first line or fence header names a path
    for m in FENCE.finditer(text):
        lang, path, body = m.group("lang"), m.group("path"), m.group("body")
        if lang in ("diff", "patch"): continue
        if not path:
            first = body.splitlines()[0] if body.strip() else ""
            fm = re.match(r"^\s*(?://|#|<!--|/\*)\s*(?:file:|path:)?\s*([\w./\\-]+\.[\w]+)", first, re.I)
            if fm: path = fm.group(1); body = "\n".join(body.splitlines()[1:]) + "\n"
        if not path: continue
        p = safe_path(repo, path)
        if not p: log(f"[human] refused path outside repo: {path}"); continue
        p.parent.mkdir(parents=True, exist_ok=True); p.write_text(body, encoding="utf-8")
        touched.append(path); log(f"[human] wrote {path} ({len(body)} chars)")
    return touched

def run_tests(repo: Path, cmd: str, log):
    if not cmd: return None
    r = subprocess.run(cmd, cwd=repo, shell=True, capture_output=True, text=True, timeout=900)
    out = (r.stdout + "\n" + r.stderr).strip()
    log(f"[human] tests rc={r.returncode}")
    return f"I ran `{cmd}` — exit code {r.returncode}. Output (tail):\n```\n{out[-6000:]}\n```"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True); ap.add_argument("--model", required=True, choices=MODELS)
    ap.add_argument("--out", default="runs"); ap.add_argument("--max-tokens", type=int, default=32768)
    a = ap.parse_args()
    task = json.loads(Path(a.task).read_text(encoding="utf-8"))
    base, model, extra = MODELS[a.model]
    repo = Path(task["repo"])
    out = Path(a.out) / task["name"] / a.model; out.mkdir(parents=True, exist_ok=True)
    transcript = out / "transcript.jsonl"; logf = out / "human.log"
    def log(s):
        print(s, flush=True); logf.open("a", encoding="utf-8").write(time.strftime("%H:%M:%S ") + s + "\n")
    def record(role, content, **meta):
        transcript.open("a", encoding="utf-8").write(json.dumps({"t": time.time(), "role": role, "content": content, **meta}) + "\n")

    opening = task["opening"]
    for f in task.get("seed_files", []):
        opening += f"\n\nHere is `{f}`:\n```\n{(repo / f).read_text(encoding='utf-8')}\n```"
    messages = ([{"role": "system", "content": HUMAN_SYSTEM}] if HUMAN_SYSTEM else []) + [{"role": "user", "content": opening}]
    record("user", opening, turn="opening")
    turns = list(task.get("turns", [])); exchanges = 0
    while exchanges < task.get("max_exchanges", 40):
        exchanges += 1
        content, reasoning, usage, secs = chat(base, model, messages, extra, a.max_tokens)
        messages.append({"role": "assistant", "content": content})
        record("assistant", content, reasoning_chars=len(reasoning), usage=usage, secs=round(secs, 1))
        log(f"[model] exchange {exchanges}: {usage.get('completion_tokens')} tok in {secs:.0f}s, reasoning {len(reasoning)} chars")
        # --- scripted human ---
        touched = apply_model_output(repo, content, log)
        reply_parts = []
        if touched:
            reply_parts.append(f"Applied your changes to: {', '.join(sorted(set(touched)))}.")
            t = run_tests(repo, task.get("test_cmd", ""), log)
            if t: reply_parts.append(t)
        asked = [p for p in FILE_REQ.findall(content) if safe_path(repo, p) and safe_path(repo, p).is_file()]
        for p in sorted(set(asked))[:4]:
            reply_parts.append(f"Here is `{p}`:\n```\n{safe_path(repo, p).read_text(encoding='utf-8')[:60000]}\n```")
        done_signal = bool(touched) or re.search(r"\b(done|complete[d]?|finished|that should|let me know)\b", content[-600:], re.I)
        if not reply_parts and not asked:
            if done_signal and turns:
                reply_parts.append(turns.pop(0))
            elif done_signal and not turns:
                log("[human] all scripted turns delivered and model reports done — stopping"); break
            else:
                reply_parts.append("Go ahead — you have everything you need. If you need a file, name it and I will paste it.")
        elif touched and not asked and turns and done_signal:
            reply_parts.append(turns.pop(0))
        reply = "\n\n".join(reply_parts)
        messages.append({"role": "user", "content": reply}); record("user", reply, turn=f"human-{exchanges}")
    log(f"[human] finished after {exchanges} exchanges; transcript at {transcript}")

if __name__ == "__main__":
    main()
