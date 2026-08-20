"""Smoke + speed check for the two tunnelled endpoints.
usage: python smoke.py [qwen|dsv4|both] [--prompt "..."] [--max-tokens N]
Checks: model identity in body, reasoning_content separated from content,
decode t/s from usage + wall-clock (streaming, first-token time too)."""
import json, sys, time, urllib.request

EPS = {
    "qwen": ("http://localhost:8001", "qwen3.8-27b-bf16", {}),
    "dsv4": ("http://localhost:8002", "deepseek-v4-flash-0731", {}),
}

def run(name, prompt, max_tokens, extra_body=None):
    base, model, _ = EPS[name]
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens, "stream": True,
            "stream_options": {"include_usage": True}}
    if extra_body: body.update(extra_body)
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time(); t_first = None; reasoning = []; content = []; usage = None; seen_model = None
    with urllib.request.urlopen(req, timeout=1800) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"): continue
            payload = line[5:].strip()
            if payload == "[DONE]": break
            ev = json.loads(payload)
            seen_model = ev.get("model", seen_model)
            if ev.get("usage"): usage = ev["usage"]
            for ch in ev.get("choices", []):
                d = ch.get("delta", {})
                rc = d.get("reasoning_content") or d.get("reasoning")
                c = d.get("content")
                if (rc or c) and t_first is None: t_first = time.time()
                if rc: reasoning.append(rc)
                if c: content.append(c)
    t_end = time.time()
    rtxt, ctxt = "".join(reasoning), "".join(content)
    comp = (usage or {}).get("completion_tokens")
    gen_s = (t_end - (t_first or t0))
    tps = (comp / gen_s) if (comp and gen_s > 0) else None
    print(f"== {name} :: served model={seen_model!r} (expected {model})")
    print(f"   ttft={((t_first or t_end)-t0):.2f}s  wall={t_end-t0:.1f}s  completion_tokens={comp}  decode~{tps and round(tps,1)} t/s")
    print(f"   reasoning_content chars={len(rtxt)}  content chars={len(ctxt)}  "
          f"{'SEPARATED' if rtxt and ctxt else ('NO-REASONING-FIELD' if not rtxt else 'EMPTY-CONTENT')}")
    print(f"   content head: {ctxt[:220].replace(chr(10),' ')!r}")
    print(f"   usage: {usage}")
    return dict(name=name, model=seen_model, ttft=(t_first or t_end)-t0, wall=t_end-t0, completion_tokens=comp, tps=tps,
                reasoning_chars=len(rtxt), content_chars=len(ctxt))

if __name__ == "__main__":
    args = sys.argv[1:]
    which = args[0] if args and not args[0].startswith("--") else "both"
    prompt = "Write a Python function that parses an ISO-8601 duration string (like 'P3DT4H5M6S') into total seconds, with tests. Keep it under 60 lines."
    max_tokens = 16384
    if "--prompt" in args: prompt = args[args.index("--prompt") + 1]
    if "--max-tokens" in args: max_tokens = int(args[args.index("--max-tokens") + 1])
    names = ["qwen", "dsv4"] if which == "both" else [which]
    for n in names:
        try: run(n, prompt, max_tokens)
        except Exception as e: print(f"== {n} :: ERROR {type(e).__name__}: {str(e)[:300]}")
