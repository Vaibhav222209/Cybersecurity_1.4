"""Loopback-first HTTP adapter for an offline, single-operator simulation."""

import hmac
import json
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

STATIC = Path(__file__).with_name("static")
FILES = {"/": ("index.html", "text/html"), "/style.css": ("style.css", "text/css"), "/app.js": ("app.js", "text/javascript")}
MAX_BODY = 4096


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, store, rate_limit=240):
        self.store = store
        self.csrf_token = secrets.token_urlsafe(32)
        self.rate_limit = rate_limit
        self.requests = defaultdict(deque)
        self.limiter_lock = threading.Lock()
        super().__init__(address, Handler)

    def allowed(self, peer):
        with self.limiter_lock:
            now = time.monotonic()
            queue = self.requests[peer]
            while queue and queue[0] <= now - 60:
                queue.popleft()
            if len(queue) >= self.rate_limit:
                return False
            queue.append(now)
            return True


class Handler(BaseHTTPRequestHandler):
    server_version = "PortbugLocal/1.0"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, format, *args):
        # Do not log request bodies, tokens, or arbitrary user-supplied headers.
        pass

    def send(self, status, body, content_type="application/json", attachment=False):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        if status == 429:
            self.send_header("Retry-After", "60")
        if attachment:
            self.send_header("Content-Disposition", 'attachment; filename="portbug-evidence.json"')
        self.end_headers()
        self.wfile.write(body)

    def guard(self):
        hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.headers.get("Host") not in hosts:
            self.send(403, {"error": "Untrusted Host header. Use the local startup URL."})
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {f"http://{host}" for host in hosts}:
            self.send(403, {"error": "Cross-origin requests are not allowed"})
            return False
        if not self.server.allowed(self.client_address[0]):
            self.send(429, {"error": "Local request limit reached; retry in 60 seconds"})
            return False
        return True

    def do_GET(self):
        if not self.guard():
            return
        path = unquote(urlsplit(self.path).path)
        if path in FILES:
            filename, content_type = FILES[path]
            self.send(200, (STATIC / filename).read_bytes(), content_type)
        elif path == "/api/session":
            self.send(200, {"csrf_token": self.server.csrf_token})
        elif path in {"/api/state", "/api/evidence", "/api/health"}:
            try:
                state = self.server.store.snapshot()
            except (ValueError, TypeError, sqlite3.DatabaseError):
                self.send(503, {"status": "integrity-failed", "audit_valid": False, "error": "Local state cannot be verified. Restore a verified backup."})
                return
            if path == "/api/health":
                valid = state["audit"]["valid"]
                self.send(200 if valid else 503, {"status": "ok" if valid else "integrity-failed", "mode": "local-simulation", "audit_valid": valid})
            elif path == "/api/evidence":
                self.send(200, {"project": "Portbug Bank", "author": "Vaibhav Thakur", "disclaimer": "Synthetic local demonstration; not a compliance attestation", "state": state}, attachment=True)
            else:
                self.send(200, state)
        else:
            self.send(404, {"error": "Not found"})

    def do_POST(self):
        if not self.guard():
            return
        if self.headers.get("Origin") != f"http://{self.headers.get('Host')}":
            self.send(403, {"error": "An exact same-origin Origin header is required"})
            return
        token = self.headers.get("X-CSRF-Token", "")
        if not token.isascii() or not hmac.compare_digest(token, self.server.csrf_token):
            self.send(403, {"error": "Invalid local CSRF token. Refresh the page."})
            return
        path = urlsplit(self.path).path
        required = {"/api/scenarios": {"scenario"}, "/api/respond": {"alert_id", "action"}}
        if path not in required:
            self.send(404, {"error": "Not found"})
            return
        if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            self.send(415, {"error": "Use a bounded application/json request"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY:
            self.send(413, {"error": "JSON body must be between 1 and 4096 bytes"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict) or set(payload) != required[path]:
                raise ValueError("Unexpected or missing JSON fields")
            if not all(isinstance(value, str) and 0 < len(value) <= 80 for value in payload.values()):
                raise ValueError("All fields must be nonempty strings of at most 80 characters")
        except (ValueError, UnicodeError) as exc:
            self.send(400, {"error": str(exc)})
            return
        try:
            result = self.server.store.change("scenario" if path == "/api/scenarios" else "response", payload)
        except ValueError as exc:
            self.send(409, {"error": str(exc)})
            return
        except (TypeError, sqlite3.DatabaseError):
            self.send(503, {"error": "Local state cannot be verified. Restore a verified backup."})
            return
        self.send(200, result)
