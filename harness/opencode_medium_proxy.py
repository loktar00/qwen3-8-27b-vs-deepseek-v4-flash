#!/usr/bin/env python3
"""
Fallback proxy for the "medium reasoning effort" Qwen entry in Lane B (OpenCode).

NOT started by default / not wired into opencode.jsonc by default. Only needed if verification
shows OpenCode's native `variants.medium.reasoningEffort` -- which serializes to a top-level
OpenAI-style `reasoning_effort` field in the request body -- does NOT reach vLLM's chat template
for Qwen. This mirrors the exact fallback the OMP lane already planned for itself
(ab/omp-pod-providers.yml: "fall back to the lane-C style chat_template_kwargs via a tiny local
proxy on :8003"). This one listens on :8004 so it can run alongside OMP's :8003 proxy if both
lanes need it at once.

What it does: sits in front of the real vLLM server (default http://localhost:8001), and for any
POST request whose JSON body it can parse, injects
    body["chat_template_kwargs"] = {"reasoning_effort": MEDIUM_LEVEL}
before forwarding, then streams the response back byte-for-byte (works for both a plain JSON
response and an SSE streaming completion). Every other verb/path is proxied unmodified.

Usage (once the pod tunnel to :8001 is up):
    python opencode_medium_proxy.py                     # listens :8004 -> forwards to :8001
    TARGET_PORT=8001 PROXY_PORT=8004 MEDIUM_LEVEL=medium python opencode_medium_proxy.py

Then point pod-qwen-medium's baseURL in opencode.jsonc at http://localhost:8004/v1 and drop the
"variants" block (no longer needed -- every request through this proxy carries the kwarg).
"""
import http.client
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TARGET_HOST = os.environ.get("TARGET_HOST", "localhost")
TARGET_PORT = int(os.environ.get("TARGET_PORT", "8001"))
PROXY_PORT = int(os.environ.get("PROXY_PORT", "8004"))
MEDIUM_LEVEL = os.environ.get("MEDIUM_LEVEL", "medium")

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-length",
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _proxy(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""

        if raw:
            try:
                body = json.loads(raw)
                if isinstance(body, dict):
                    ctk = body.setdefault("chat_template_kwargs", {})
                    if isinstance(ctk, dict):
                        ctk["reasoning_effort"] = MEDIUM_LEVEL
                    raw = json.dumps(body).encode("utf-8")
                    print(f"[proxy] injected chat_template_kwargs.reasoning_effort={MEDIUM_LEVEL!r} "
                          f"into {self.command} {self.path}", file=sys.stderr)
            except (ValueError, TypeError) as e:
                print(f"[proxy] passthrough (non-JSON or unparsable body): {e}", file=sys.stderr)

        fwd_headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
        fwd_headers["Content-Length"] = str(len(raw))
        fwd_headers["Host"] = f"{TARGET_HOST}:{TARGET_PORT}"

        conn = http.client.HTTPConnection(TARGET_HOST, TARGET_PORT, timeout=300)
        try:
            conn.request(self.command, self.path, body=raw or None, headers=fwd_headers)
            resp = conn.getresponse()
            self.send_response(resp.status, resp.reason)
            for k, v in resp.getheaders():
                if k.lower() not in HOP_BY_HOP:
                    self.send_header(k, v)
            self.send_header("Connection", "close")
            self.end_headers()
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except (ConnectionError, OSError, TimeoutError) as e:
            self.send_response(502)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"proxy error: {e}".encode("utf-8"))
        finally:
            conn.close()

    def do_GET(self):
        self._proxy()

    def do_POST(self):
        self._proxy()

    def do_PUT(self):
        self._proxy()

    def do_DELETE(self):
        self._proxy()

    def log_message(self, fmt, *args):
        print(f"[proxy] {self.address_string()} - {fmt % args}", file=sys.stderr)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PROXY_PORT), Handler)
    print(f"[proxy] listening :{PROXY_PORT} -> http://{TARGET_HOST}:{TARGET_PORT} "
          f"(injecting chat_template_kwargs.reasoning_effort={MEDIUM_LEVEL!r})", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
