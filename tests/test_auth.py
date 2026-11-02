"""Authentication behavior with synthetic credentials and isolated local state."""

import base64
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from portbug.auth import Auth, hash_password, totp, verify_password


# This is a deliberately public test fixture, never a shipped login credential.
FIXTURE_PASSWORD = "Synthetic-Only-Password-42!"


class AuthTestStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.database = self.directory / "auth-test.sqlite3"

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()


class PasswordTests(unittest.TestCase):
    def test_salted_password_verification_and_wrong_password(self):
        encoded = hash_password(FIXTURE_PASSWORD)
        self.assertTrue(verify_password(FIXTURE_PASSWORD, encoded))
        self.assertFalse(verify_password("Different-Synthetic-Password!", encoded))
        self.assertNotIn(FIXTURE_PASSWORD, encoded)
        self.assertNotEqual(encoded, hash_password(FIXTURE_PASSWORD))

    def test_invalid_stored_hash_fails_closed(self):
        self.assertFalse(verify_password(FIXTURE_PASSWORD, "invalid-stored-record"))

    def test_totp_rfc6238_sha1_vectors(self):
        # Public RFC test seed, not an application secret. Expected final six digits.
        secret = base64.b32encode(b"12345678901234567890").decode()
        for timestamp, expected in (
            (59, "287082"), (1111111109, "081804"),
            (1111111111, "050471"), (1234567890, "005924"),
            (2000000000, "279037"), (20000000000, "353130"),
        ):
            with self.subTest(timestamp=timestamp):
                self.assertEqual(totp(secret, at=timestamp), expected)


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = AuthTestStore(self.temporary.name)
        self.auth = Auth(self.store)

    def setup_admin(self):
        return self.auth.create_user("demo.admin", FIXTURE_PASSWORD, "Synthetic Administrator", "admin", first=True)

    def test_setup_is_explicit_and_only_allowed_once(self):
        self.assertTrue(self.auth.setup_required())
        admin = self.setup_admin()
        self.assertEqual(admin["id"], 1)
        self.assertEqual(admin["role"], "admin")
        self.assertFalse(self.auth.setup_required())
        with self.assertRaises(ValueError):
            self.auth.create_user("other.admin", FIXTURE_PASSWORD, "Other Administrator", "admin", first=True)

    def test_first_account_cannot_be_non_administrator(self):
        with self.assertRaises(ValueError):
            self.auth.create_user("demo.client", FIXTURE_PASSWORD, "Synthetic Customer", "customer", first=True)
        self.assertTrue(self.auth.setup_required())

    def test_user_validation_and_duplicate_username(self):
        self.setup_admin()
        for username, password, role in (
            ("bad user name", FIXTURE_PASSWORD, "customer"),
            ("demo.client", "short", "customer"),
            ("demo.client", "x" * 129, "customer"),
            ("demo.client", FIXTURE_PASSWORD, "root"),
        ):
            with self.subTest(username=username, role=role):
                with self.assertRaises(ValueError):
                    self.auth.create_user(username, password, "Synthetic Customer", role)
        self.auth.create_user("demo.client", FIXTURE_PASSWORD, "Synthetic Customer", "customer")
        with self.assertRaises(ValueError):
            self.auth.create_user("demo.client", FIXTURE_PASSWORD, "Duplicate Customer", "customer")

    def test_login_uses_opaque_server_side_sessions(self):
        admin = self.setup_admin()
        user, token, csrf = self.auth.login("demo.admin", FIXTURE_PASSWORD)
        self.assertEqual(user["id"], admin["id"])
        self.assertGreaterEqual(len(token), 32)
        self.assertTrue(self.auth.csrf_valid(token, csrf))
        self.assertEqual(self.auth.session(token)["id"], admin["id"])
        with self.store.connect() as connection:
            serialized = "\n".join(connection.iterdump())
        self.assertNotIn(token, serialized)
        self.assertNotIn(FIXTURE_PASSWORD, serialized)
        self.assertIsNone(self.auth.session("unrecognized-session"))

    def test_login_rejects_wrong_password_and_unknown_user(self):
        self.setup_admin()
        for username, password in (("demo.admin", "Incorrect-Synthetic-Password!"), ("unknown.user", FIXTURE_PASSWORD)):
            with self.subTest(username=username):
                with self.assertRaises(ValueError):
                    self.auth.login(username, password)

    def test_preauth_token_is_csrf_bound_but_never_authenticated(self):
        first_token, first_csrf = self.auth.preauth()
        second_token, second_csrf = self.auth.preauth()
        self.assertIsNone(self.auth.session(first_token))
        self.assertTrue(self.auth.csrf_valid(first_token, first_csrf))
        self.assertFalse(self.auth.csrf_valid(first_token, second_csrf))
        self.assertFalse(self.auth.csrf_valid(second_token, first_csrf))
        self.assertFalse(self.auth.csrf_valid(first_token, "é"))

    def test_logout_revokes_session_and_write_token(self):
        self.setup_admin()
        _, token, csrf = self.auth.login("demo.admin", FIXTURE_PASSWORD)
        self.auth.logout(token)
        self.assertIsNone(self.auth.session(token))
        self.assertFalse(self.auth.csrf_valid(token, csrf))

    def test_session_idle_expiration(self):
        self.setup_admin()
        with patch("portbug.auth.time.time", return_value=1000000000):
            _, token, csrf = self.auth.login("demo.admin", FIXTURE_PASSWORD)
        with patch("portbug.auth.time.time", return_value=1000001801):
            self.assertIsNone(self.auth.session(token))
            self.assertFalse(self.auth.csrf_valid(token, csrf))

    def test_absolute_expiration_even_with_regular_session_use(self):
        self.setup_admin()
        origin = 1000000000
        with patch("portbug.auth.time.time", return_value=origin):
            _, token, _ = self.auth.login("demo.admin", FIXTURE_PASSWORD)
        for delta in range(1200, 28800, 1200):
            with patch("portbug.auth.time.time", return_value=origin + delta):
                self.assertIsNotNone(self.auth.session(token))
        with patch("portbug.auth.time.time", return_value=origin + 28801):
            self.assertIsNone(self.auth.session(token))

    def test_public_user_records_never_expose_authentication_material(self):
        self.setup_admin()
        self.auth.create_user("demo.operator", FIXTURE_PASSWORD, "Synthetic Reviewer", "operator")
        users = self.auth.users()
        self.assertEqual(len(users), 2)
        for user in users:
            self.assertIn(user["role"], {"admin", "operator"})
            self.assertIsInstance(user["mfa_enabled"], bool)
            for forbidden in ("password", "password_hash", "salt", "totp_secret", "totp_pending", "session_token"):
                self.assertNotIn(forbidden, user)

    def test_totp_requires_confirmation_and_then_a_valid_login_code(self):
        admin = self.setup_admin()
        origin = 1000000020
        with patch("portbug.auth.time.time", return_value=origin):
            enrollment = self.auth.enroll(admin["id"])
            self.assertTrue(enrollment["otpauth_uri"].startswith("otpauth://totp/"))
            self.assertFalse(self.auth.users()[0]["mfa_enabled"])
            with self.assertRaises(ValueError):
                self.auth.confirm(admin["id"], "invalid")
            code = totp(enrollment["secret"], at=origin)
            user = self.auth.confirm(admin["id"], code)
            self.assertTrue(user["mfa_enabled"])
            with self.assertRaises(ValueError):
                self.auth.login("demo.admin", FIXTURE_PASSWORD)
            with self.assertRaises(ValueError):
                self.auth.login("demo.admin", FIXTURE_PASSWORD, "invalid")
            with self.assertRaises(ValueError):
                self.auth.login("demo.admin", FIXTURE_PASSWORD, code)
        with patch("portbug.auth.time.time", return_value=origin + 30):
            next_code = totp(enrollment["secret"], at=origin + 30)
            logged_in, token, _ = self.auth.login("demo.admin", FIXTURE_PASSWORD, next_code)
            self.assertTrue(logged_in["mfa_enabled"])
            self.assertIsNotNone(self.auth.session(token))
            with self.assertRaises(ValueError):
                self.auth.login("demo.admin", FIXTURE_PASSWORD, next_code)

    def test_totp_confirmation_revokes_other_sessions_but_preserves_current(self):
        admin = self.setup_admin()
        origin = 1000000020
        with patch("portbug.auth.time.time", return_value=origin):
            _, current_token, current_csrf = self.auth.login("demo.admin", FIXTURE_PASSWORD)
            _, other_token, _ = self.auth.login("demo.admin", FIXTURE_PASSWORD)
            enrollment = self.auth.enroll(admin["id"])
            code = totp(enrollment["secret"], at=origin)
            self.auth.confirm(admin["id"], code, keep_token=current_token)
            self.assertIsNone(self.auth.session(other_token))
            self.assertTrue(self.auth.session(current_token)["mfa_enabled"])
            self.assertTrue(self.auth.csrf_valid(current_token, current_csrf))

    def test_totp_confirmation_attempts_are_limited_then_recover(self):
        admin = self.setup_admin()
        origin = 1000000020
        with patch("portbug.auth.time.time", return_value=origin):
            enrollment = self.auth.enroll(admin["id"])
            for _ in range(8):
                with self.assertRaises(ValueError):
                    self.auth.confirm(admin["id"], "invalid")
            with self.assertRaisesRegex(ValueError, "Too many verification attempts"):
                self.auth.confirm(admin["id"], totp(enrollment["secret"], at=origin))
            self.assertFalse(self.auth.users()[0]["mfa_enabled"])
        with patch("portbug.auth.time.time", return_value=origin + 61):
            user = self.auth.confirm(admin["id"], totp(enrollment["secret"], at=origin + 61))
            self.assertTrue(user["mfa_enabled"])

    def test_deleting_a_user_revokes_their_sessions(self):
        self.setup_admin()
        customer = self.auth.create_user("demo.client", FIXTURE_PASSWORD, "Synthetic Customer", "customer")
        _, token, _ = self.auth.login("demo.client", FIXTURE_PASSWORD)
        self.auth.delete_user(customer["id"])
        self.assertIsNone(self.auth.session(token))


if __name__ == "__main__":
    unittest.main()
