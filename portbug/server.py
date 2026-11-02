"""Authenticated, loopback-first adapter for the fictional banking workspace."""

import json
import sqlite3
import threading
import time
from collections import defaultdict, deque
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .auth import Auth

COOKIE = "portbug_session"
STATIC = Path(__file__).with_name("static")
FILES = {"/": ("index.html", "text/html"), "/style.css": ("style.css", "text/css"), "/app.js": ("app.js", "text/javascript"), "/favicon.svg": ("favicon.svg", "image/svg+xml")}
SCHEMAS = {
    "/api/setup": ({"username", "password", "display_name"}, set()),
    "/api/login": ({"username", "password"}, {"otp"}),
    "/api/logout": (set(), set()),
    "/api/transfer": ({"from_account", "beneficiary_id", "amount", "reference", "idempotency_key"}, set()),
    "/api/decision": ({"transfer_id", "decision", "note"}, set()),
    "/api/rules": ({"high_value_chf", "velocity_limit"}, set()),
    "/api/backtest": ({"high_value_chf", "velocity_limit"}, set()),
    "/api/users": ({"username", "password", "display_name", "role"}, set()),
    "/api/mfa/enroll": (set(), set()),
    "/api/mfa/confirm": ({"code"}, set()),
}


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, store, rate_limit=240):
        self.store = store
        self.auth = Auth(store)
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
    server_version = "PortbugLocal/3.0"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, format, *args):
        pass

    def raw_cookie(self):
        try:
            cookies = SimpleCookie(self.headers.get("Cookie", ""))
            return cookies[COOKIE].value if COOKIE in cookies else None
        except CookieError:
            return None

    def send(self, status, body, content_type="application/json", cookie=None, attachment=False):
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
        if cookie is not None:
            age = 0 if cookie == "" else 28800
            self.send_header("Set-Cookie", f"{COOKIE}={cookie}; Path=/; HttpOnly; SameSite=Strict; Max-Age={age}")
        if status == 429:
            self.send_header("Retry-After", "60")
        if attachment:
            self.send_header("Content-Disposition", 'attachment; filename="portbug-banking-evidence.json"')
        self.end_headers()
        self.wfile.write(body)

    def guard(self):
        hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.headers.get("Host") not in hosts:
            self.send(403, {"error": "Untrusted Host header. Open the local startup URL."})
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {f"http://{host}" for host in hosts}:
            self.send(403, {"error": "Cross-origin requests are not permitted."})
            return False
        if not self.server.allowed(self.client_address[0]):
            self.send(429, {"error": "Local request limit reached. Retry in a minute."})
            return False
        return True

    def current_user(self):
        user = self.server.auth.session(self.raw_cookie())
        if user is None:
            self.send(401, {"error": "Sign in to your local banking workspace."})
        return user

    def require_role(self, user, roles):
        if user["role"] not in roles:
            raise PermissionError("Your local role does not permit this operation.")

    def do_GET(self):
        if not self.guard():
            return
        try:
            self.get_route()
        except PermissionError as exc:
            self.send(403, {"error": str(exc)})
        except (ValueError, TypeError, sqlite3.DatabaseError):
            self.send(503, {"status": "integrity-failed", "audit_valid": False, "error": "Local state cannot be verified. Restore a verified backup."})

    def get_route(self):
        path = unquote(urlsplit(self.path).path)
        if path in FILES:
            filename, kind = FILES[path]
            self.send(200, (STATIC / filename).read_bytes(), kind)
            return
        if path == "/api/session":
            raw, csrf = self.server.auth.preauth(self.raw_cookie())
            self.send(200, {"setup_required": self.server.auth.setup_required(), "csrf_token": csrf, "user": self.server.auth.session(raw)}, cookie=raw)
            return
        if path == "/api/health":
            state = self.server.store.raw_snapshot()
            valid = state["audit"]["valid"]
            self.send(200 if valid else 503, {"status": "ok" if valid else "integrity-failed", "audit_valid": valid, "mode": "fictional-banking-lab"})
            return
        if path not in {"/api/state", "/api/users", "/api/evidence"}:
            self.send(404, {"error": "Not found."})
            return
        user = self.current_user()
        if user is None:
            return
        if path == "/api/users":
            self.require_role(user, {"admin"})
            self.send(200, {"users": self.server.auth.users()})
        elif path == "/api/evidence":
            self.require_role(user, {"admin", "operator"})
            self.send(200, {"project": "Portbug Bank", "author": "Vaibhav Thakur", "scope": "Fictional local banking exercise; synthetic funds and identifiers", "state": self.server.store.snapshot(user)}, attachment=True)
        else:
            self.send(200, self.server.store.snapshot(user))

    def read_payload(self, path):
        if path not in SCHEMAS:
            self.send(404, {"error": "Not found."})
            return None
        if self.headers.get("Origin") != f"http://{self.headers.get('Host')}":
            self.send(403, {"error": "An exact same-origin Origin header is required."})
            return None
        if not self.server.auth.csrf_valid(self.raw_cookie(), self.headers.get("X-CSRF-Token", "")):
            self.send(403, {"error": "Invalid or expired request token. Reload the page."})
            return None
        if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            self.send(415, {"error": "Use a bounded application/json request."})
            return None
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 0 < length <= 8192:
            self.send(413, {"error": "Request body must contain 1–8192 bytes."})
            return None
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            required, optional = SCHEMAS[path]
            if not isinstance(payload, dict) or not required <= set(payload) or set(payload) - required - optional:
                raise ValueError("Unexpected or missing request fields.")
            for name, value in payload.items():
                if name == "velocity_limit":
                    if isinstance(value, bool) or not isinstance(value, int):
                        raise ValueError("Velocity limit must be an integer.")
                elif not isinstance(value, str) or len(value) > (128 if name == "password" else 500):
                    raise ValueError("Request values must be bounded strings.")
            return payload
        except (ValueError, UnicodeError) as exc:
            self.send(400, {"error": str(exc)})
            return None

    def record(self, kind, detail, user_id=0):
        self.server.store.security_event(kind, detail, user_id)

    def do_POST(self):
        if not self.guard():
            return
        path = urlsplit(self.path).path
        payload = self.read_payload(path)
        if payload is None:
            return
        try:
            self.post_route(path, payload)
        except PermissionError as exc:
            self.send(403, {"error": str(exc)})
        except ValueError as exc:
            self.send(409, {"error": str(exc)})
        except (TypeError, sqlite3.DatabaseError):
            self.send(503, {"error": "Local state cannot be verified. Restore a verified backup."})

    def post_route(self, path, payload):
        auth = self.server.auth
        if path in {"/api/setup", "/api/login"}:
            if not auth.allow_login(self.client_address[0]):
                self.send(429, {"error": "Too many sign-in attempts. Wait a minute before retrying."})
                return
            if path == "/api/setup":
                user = auth.create_user(**payload, role="admin", first=True)
                raw, csrf = auth.new_session(user["id"])
                self.record("workspace_setup", "Local administrator account created.", user["id"])
            else:
                try:
                    user, raw, csrf = auth.login(**payload)
                except ValueError:
                    self.record("login_failed", "A local sign-in attempt was rejected.")
                    self.send(401, {"error": "Sign-in failed. Check your credentials and verification code."})
                    return
                self.record("login_success", "Local session established.", user["id"])
            auth.logout(self.raw_cookie())
            self.send(200, {"user": user, "csrf_token": csrf}, cookie=raw)
            return
        user = self.current_user()
        if user is None:
            return
        if path == "/api/logout":
            auth.logout(self.raw_cookie())
            self.record("logout", "Local session ended.", user["id"])
            self.send(200, {}, cookie="")
        elif path == "/api/users":
            self.require_role(user, {"admin"})
            # User credentials, starting accounts and audit evidence commit together.
            with self.server.store.lock, self.server.store.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                created = auth.create_user(**payload, connection=connection)
                self.server.store.provision(created, user, connection=connection)
            self.send(200, {"user": created})
        elif path == "/api/mfa/enroll":
            self.send(200, auth.enroll(user["id"]))
        elif path == "/api/mfa/confirm":
            updated = auth.confirm(user["id"], payload["code"], keep_token=self.raw_cookie())
            self.record("mfa_enabled", "Authenticator verification enabled for a local account.", user["id"])
            self.send(200, {"user": updated})
        elif path == "/api/backtest":
            self.require_role(user, {"operator", "admin"})
            self.send(200, self.server.store.backtest(payload, user))
        else:
            action = {"/api/transfer": "transfer", "/api/decision": "decision", "/api/rules": "rules"}[path]
            self.send(200, self.server.store.change(action, payload, user))
