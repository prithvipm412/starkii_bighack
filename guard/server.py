"""Tiny local HTTP API for LanguageBarrierGuard (stdlib only).

  python -m guard.server [--port 8787] [--host 127.0.0.1]

  POST /check   {"text": "...", "reply": "..." (optional)}  -> verdict JSON
  GET  /health  -> {"ok": true, "models_loaded": bool}
CORS is open (Access-Control-Allow-Origin: *) so dashboard/ can call it from localhost.
Models load once on first request (or at start with --preload); requests are serialised with a lock.
Request text is never logged or echoed back.
"""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from guard.guard import LanguageBarrierGuard

MAX_BODY = 32 * 1024
GUARD = LanguageBarrierGuard()
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = "LanguageBarrierGuard/1.0"

    def _send(self, code, obj):
        body = b"" if code == 204 else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # method, path and status only; never the body
        print(f"{self.address_string()} {self.command} {self.path} {args[1] if len(args) > 1 else ''}", flush=True)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        if self.path.rstrip("/") == "/health":
            return self._send(200, {"ok": True, "models_loaded": GUARD._guard is not None})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.rstrip("/") != "/check":
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._send(400, {"error": "bad Content-Length"})
        if n <= 0 or n > MAX_BODY:
            return self._send(413 if n > MAX_BODY else 400, {"error": f"body must be 1..{MAX_BODY} bytes"})
        try:
            data = json.loads(self.rfile.read(n).decode("utf-8"))
            text = data["text"]
            reply = data.get("reply")
            if not isinstance(text, str) or (reply is not None and not isinstance(reply, str)):
                raise TypeError
        except (ValueError, KeyError, TypeError, AttributeError):
            return self._send(400, {"error": 'expected JSON {"text": str, "reply": str (optional)}'})
        try:
            with LOCK:
                verdict = GUARD.check(text, reply=reply)
        except Exception as e:
            return self._send(500, {"verdict": "error", "error": type(e).__name__})
        self._send(200, verdict)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--preload", action="store_true", help="load models before serving")
    args = ap.parse_args()
    if args.preload:
        with LOCK:
            GUARD.preload()
            GUARD.check("hello")
            GUARD.check("\u0ca8\u0cae\u0cb8\u0ccd\u0c95\u0cbe\u0cb0")  # warm up the multilingual path
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"LanguageBarrierGuard on http://{args.host}:{args.port}  (POST /check, GET /health)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
