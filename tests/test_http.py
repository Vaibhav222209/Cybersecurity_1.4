import http.client
import json
import tempfile
import threading
import unittest

from portbug.server import Server
from portbug.store import Store


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(self.directory.name)
        self.server = Server(("127.0.0.1", 0), self.store)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.cleanup)
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def cleanup(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def request(self, path, method="GET", payload=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        body = json.dumps(payload) if payload is not None else None
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        status, response_headers, data = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return status, response_headers, data

    def auth(self):
        status, _, data = self.request("/api/session")
        self.assertEqual(status, 200)
        return {"Content-Type": "application/json", "Origin": self.origin, "X-CSRF-Token": json.loads(data)["csrf_token"]}

    def test_static_content_and_security_headers(self):
        for path in ("/", "/style.css", "/app.js"):
            status, headers, data = self.request(path)
            self.assertEqual(status, 200)
            self.assertTrue(data)
            self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_full_scenario_response_and_export(self):
        headers = self.auth()
        status, _, data = self.request("/api/scenarios", "POST", {"scenario": "credential_abuse"}, headers)
        self.assertEqual(status, 200)
        state = json.loads(data)["state"]
        alert = next(item for item in state["alerts"] if item["status"] == "open")
        for action, expected in (("triage", "investigating"), ("contain", "contained"), ("resolve", "resolved")):
            status, _, data = self.request("/api/respond", "POST", {"alert_id": alert["id"], "action": action}, headers)
            self.assertEqual(status, 200)
            state = json.loads(data)["state"]
            self.assertEqual(next(item for item in state["alerts"] if item["id"] == alert["id"])["status"], expected)
        status, response_headers, data = self.request("/api/evidence")
        self.assertEqual(status, 200)
        evidence = json.loads(data)
        self.assertTrue(evidence["state"]["audit"]["valid"])
        self.assertEqual(evidence["state"]["audit"]["count"], 5)
        self.assertIn("attachment", response_headers["Content-Disposition"])
        self.assertNotIn("csrf_token", data.decode())
        self.assertNotIn(self.store.key.hex(), data.decode())

    def test_csrf_missing_and_wrong_origin_rejected(self):
        self.assertEqual(self.request("/api/scenarios", "POST", {"scenario": "baseline"})[0], 403)
        headers = self.auth()
        headers["Origin"] = "https://untrusted.invalid"
        self.assertEqual(self.request("/api/scenarios", "POST", {"scenario": "baseline"}, headers)[0], 403)

    def test_non_ascii_csrf_is_rejected_without_disconnect(self):
        headers = self.auth()
        headers["X-CSRF-Token"] = "é"
        self.assertEqual(self.request("/api/scenarios", "POST", {"scenario": "baseline"}, headers)[0], 403)

    def test_malformed_state_reports_service_unavailable(self):
        with self.store.connect() as connection:
            connection.execute("UPDATE state SET body='invalid JSON'")
        for path in ("/api/health", "/api/state", "/api/evidence"):
            status, _, data = self.request(path)
            self.assertEqual(status, 503)
            self.assertFalse(json.loads(data)["audit_valid"])

    def test_rebinding_host_and_traversal_rejected(self):
        self.assertEqual(self.request("/api/session", headers={"Host": "untrusted.invalid"})[0], 403)
        for path in ("/../store.py", "/%2e%2e/store.py", "/.local/audit.key"):
            self.assertEqual(self.request(path)[0], 404)

    def test_input_limits_and_schema(self):
        headers = self.auth()
        self.assertEqual(self.request("/api/scenarios", "POST", {"scenario": "x" * 5000}, headers)[0], 413)
        self.assertEqual(self.request("/api/scenarios", "POST", {"scenario": "baseline", "extra": True}, headers)[0], 400)
        self.assertEqual(self.request("/api/scenarios", "POST", ["baseline"], headers)[0], 400)
        self.assertEqual(self.request("/api/scenarios", "POST", {"scenario": "unknown"}, headers)[0], 409)

    def test_rate_limit_returns_429(self):
        self.server.rate_limit = 1
        self.assertEqual(self.request("/api/health")[0], 200)
        self.assertEqual(self.request("/api/health")[0], 429)

    def test_audit_failure_degrades_health(self):
        with self.store.connect() as connection:
            connection.execute("UPDATE audit SET detail='changed'")
        status, _, data = self.request("/api/health")
        self.assertEqual(status, 503)
        self.assertFalse(json.loads(data)["audit_valid"])
