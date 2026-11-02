"""Exercise the real HTTP adapter with synthetic local account credentials."""

import http.client
import json
import tempfile
import threading
import unittest
from http.cookies import SimpleCookie
from unittest.mock import patch

from portbug.auth import totp
from portbug.server import Server
from portbug.store import Store

# Test fixtures only; the application ships no default credentials.
TEST_PASSWORD = "Fixture-only-passphrase-2026"


class Client:
    def __init__(self, test):
        self.test = test
        self.cookie = None
        self.csrf = None

    def request(self, path, payload=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.test.server.server_port, timeout=5)
        values = {"Cookie": self.cookie} if self.cookie else {}
        body = json.dumps(payload) if payload is not None else None
        if payload is not None:
            values.update({"Origin": self.test.origin, "Content-Type": "application/json", "X-CSRF-Token": self.csrf or ""})
        values.update(headers or {})
        connection.request("POST" if payload is not None else "GET", path, body, values)
        response = connection.getresponse()
        status, response_headers, raw = response.status, dict(response.getheaders()), response.read()
        connection.close()
        if "Set-Cookie" in response_headers:
            cookie = SimpleCookie(response_headers["Set-Cookie"])["portbug_session"].value
            self.cookie = "portbug_session=" + cookie if cookie else None
        data = json.loads(raw) if "application/json" in response_headers.get("Content-Type", "") else raw
        if isinstance(data, dict) and "csrf_token" in data:
            self.csrf = data["csrf_token"]
        return status, response_headers, data

    def session(self):
        return self.request("/api/session")[2]


class BankingHTTPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(self.directory.name)
        self.server = Server(("127.0.0.1", 0), self.store)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.cleanup)
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        self.client = Client(self)
        self.client.session()

    def cleanup(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def setup_admin(self):
        status, headers, data = self.client.request("/api/setup", {"username": "demo_admin", "password": TEST_PASSWORD, "display_name": "Demo Administrator"})
        self.assertEqual(status, 200)
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        self.assertEqual(data["user"]["role"], "admin")

    def create_user(self, username, role):
        status, _, data = self.client.request("/api/users", {"username": username, "password": TEST_PASSWORD, "display_name": "Synthetic Local User", "role": role})
        self.assertEqual(status, 200)
        return data["user"]

    def login(self, username, otp=""):
        client = Client(self)
        client.session()
        status, _, data = client.request("/api/login", {"username": username, "password": TEST_PASSWORD, "otp": otp})
        self.assertEqual(status, 200)
        self.assertNotIn("password_hash", data["user"])
        return client

    def transfer(self, client=None, amount="125.00", key="payment-fixture-0001"):
        return (client or self.client).request("/api/transfer", {"from_account": "ACC-0001-C", "beneficiary_id": "BEN-LIMMAT", "amount": amount, "reference": "Synthetic invoice", "idempotency_key": key})

    def test_first_setup_login_session_and_logout(self):
        self.assertTrue(self.client.session()["setup_required"])
        self.assertEqual(self.client.request("/api/state")[0], 401)
        self.setup_admin()
        self.assertFalse(self.client.session()["setup_required"])
        self.assertEqual(self.client.request("/api/state")[0], 200)
        self.assertEqual(self.client.request("/api/logout", {})[0], 200)
        self.assertEqual(self.client.request("/api/state")[0], 401)
        self.client.session()
        self.assertEqual(self.client.request("/api/login", {"username": "demo_admin", "password": "Incorrect-fixture-password"})[0], 401)
        self.assertEqual(self.client.request("/api/login", {"username": "demo_admin", "password": TEST_PASSWORD})[0], 200)

    def test_customer_cannot_read_others_or_access_security_routes(self):
        self.setup_admin()
        user = self.create_user("customer_demo", "customer")
        customer = self.login("customer_demo")
        status, _, state = customer.request("/api/state")
        self.assertEqual(status, 200)
        self.assertTrue(state["accounts"])
        self.assertTrue(all(account["owner_id"] == user["id"] for account in state["accounts"]))
        self.assertEqual(state["audit"]["entries"], [])
        self.assertEqual(state["events"], [])
        self.assertEqual(self.transfer(customer)[0], 403)
        self.assertEqual(customer.request("/api/users")[0], 403)
        self.assertEqual(customer.request("/api/evidence")[0], 403)
        self.assertEqual(customer.request("/api/rules", {"high_value_chf": "5000", "velocity_limit": 2})[0], 403)

    def test_payment_idempotency_and_independent_approval(self):
        self.setup_admin()
        self.create_user("operator_demo", "operator")
        reviewer = self.login("operator_demo")
        before = self.client.request("/api/state")[2]["accounts"][0]["balance_cents"]
        status, _, data = self.transfer(amount="12000.00")
        self.assertEqual(status, 200)
        payment = data["result"]["transfer"]
        self.assertEqual(payment["status"], "pending_review")
        self.assertEqual(self.transfer(amount="12000.00")[2]["result"]["replayed"], True)
        after = self.client.request("/api/state")[2]["accounts"][0]["balance_cents"]
        self.assertEqual(before - after, 1_200_000)
        decision = {"transfer_id": payment["id"], "decision": "approve", "note": "Independent synthetic invoice verified"}
        self.assertEqual(self.client.request("/api/decision", decision)[0], 403)
        status, _, approved = reviewer.request("/api/decision", decision)
        self.assertEqual(status, 200)
        self.assertEqual(approved["result"]["transfer"]["status"], "settled")
        self.assertEqual(reviewer.request("/api/decision", decision)[0], 409)

    def test_rules_backtest_and_evidence_are_real_and_secret_free(self):
        self.setup_admin()
        status, _, result = self.client.request("/api/backtest", {"high_value_chf": "10000", "velocity_limit": 3})
        self.assertEqual(status, 200)
        self.assertIn("precision", result["result"])
        self.assertTrue(result["result"]["cases"])
        self.assertEqual(self.client.request("/api/rules", {"high_value_chf": "5000", "velocity_limit": 2})[0], 200)
        status, headers, evidence = self.client.request("/api/evidence")
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        serialized = json.dumps(evidence)
        self.assertNotIn(TEST_PASSWORD, serialized)
        self.assertNotIn("csrf_token", serialized)
        self.assertNotIn("password_hash", serialized)
        self.assertTrue(evidence["state"]["audit"]["valid"])

    def test_totp_enrollment_changes_actual_login_requirements(self):
        self.setup_admin()
        import time
        timestamp = time.time()
        with patch("portbug.auth.time.time", return_value=timestamp):
            status, _, enrollment = self.client.request("/api/mfa/enroll", {})
            self.assertEqual(status, 200)
            self.assertTrue(enrollment["otpauth_uri"].startswith("otpauth://totp/"))
            code = totp(enrollment["secret"])
            status, _, confirmed = self.client.request("/api/mfa/confirm", {"code": code})
            self.assertEqual(status, 200)
            self.assertTrue(confirmed["user"]["mfa_enabled"])
            self.client.request("/api/logout", {})
            self.client.session()
            self.assertEqual(self.client.request("/api/login", {"username": "demo_admin", "password": TEST_PASSWORD})[0], 401)
            self.assertEqual(self.client.request("/api/login", {"username": "demo_admin", "password": TEST_PASSWORD, "otp": code})[0], 401)
        with patch("portbug.auth.time.time", return_value=timestamp + 30):
            self.assertEqual(self.client.request("/api/login", {"username": "demo_admin", "password": TEST_PASSWORD, "otp": totp(enrollment["secret"])})[0], 200)

    def test_csrf_host_origin_and_bounded_schema(self):
        self.setup_admin()
        payload = {"high_value_chf": "5000", "velocity_limit": 2}
        self.assertEqual(self.client.request("/api/rules", payload, {"Origin": "https://untrusted.invalid"})[0], 403)
        self.assertEqual(self.client.request("/api/rules", payload, {"X-CSRF-Token": "é"})[0], 403)
        self.assertEqual(self.client.request("/api/session", headers={"Host": "untrusted.invalid"})[0], 403)
        self.assertEqual(self.client.request("/api/rules", payload | {"unexpected": "field"})[0], 400)
        self.assertEqual(self.client.request("/api/rules", {"high_value_chf": "x" * 9000, "velocity_limit": 2})[0], 413)
        for path in ("/../auth.py", "/%2e%2e/store.py", "/.local/audit.key"):
            self.assertEqual(self.client.request(path)[0], 404)

    def test_failed_login_rate_limit_persists_in_workspace(self):
        self.setup_admin()
        anonymous = Client(self)
        anonymous.session()
        for _ in range(7):
            self.assertEqual(anonymous.request("/api/login", {"username": "demo_admin", "password": "Incorrect-fixture-password"})[0], 401)
        self.assertEqual(anonymous.request("/api/login", {"username": "demo_admin", "password": TEST_PASSWORD})[0], 429)

    def test_integrity_failure_blocks_payment_and_degrades_health(self):
        self.setup_admin()
        with self.store.connect() as connection:
            connection.execute("UPDATE audit SET detail='modified' WHERE sequence=1")
        self.assertEqual(self.client.request("/api/health")[0], 503)
        self.assertEqual(self.transfer()[0], 409)

    def test_customer_creation_rolls_back_if_bank_audit_cannot_commit(self):
        self.setup_admin()
        with self.store.connect() as connection:
            connection.execute("UPDATE audit SET detail='modified' WHERE sequence=1")
        status, _, _ = self.client.request("/api/users", {"username": "rolled_back_user", "password": TEST_PASSWORD, "display_name": "Synthetic Local User", "role": "customer"})
        self.assertEqual(status, 409)
        self.assertEqual([user["username"] for user in self.server.auth.users()], ["demo_admin"])

    def test_static_headers_and_health_have_no_customer_data(self):
        for path in ("/", "/style.css", "/app.js"):
            status, headers, data = self.client.request(path)
            self.assertEqual(status, 200)
            self.assertTrue(data)
            self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
            self.assertNotIn("Access-Control-Allow-Origin", headers)
        status, _, health = self.client.request("/api/health")
        self.assertEqual(status, 200)
        self.assertNotIn("accounts", health)
