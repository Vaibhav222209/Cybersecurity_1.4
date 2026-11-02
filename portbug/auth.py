"""Local password, session and optional TOTP authentication.

The host remains trusted. Passwords use scrypt; session bearer values are never
stored. TOTP seeds require local disk protection because verification needs them.
"""

import base64
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import struct
import threading
import time
from urllib.parse import quote, urlencode

USERNAME = re.compile(r"[a-z][a-z0-9_.-]{2,31}\Z")


def hash_password(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ValueError("Choose a password containing 12–128 characters.")
    salt = os.urandom(16)
    value = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${value.hex()}"


def verify_password(password, encoded):
    if not isinstance(password, str) or len(password) > 128:
        return False
    try:
        kind, n, r, p, salt, value = encoded.split("$")
        if (kind, n, r, p) != ("scrypt", "16384", "8", "1"):
            return False
        result = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=32)
        return hmac.compare_digest(result, bytes.fromhex(value))
    except (ValueError, TypeError):
        return False


def totp(secret, at=None):
    timestamp = time.time() if at is None else at
    seed = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    message = struct.pack(">Q", int(timestamp) // 30)
    digest = hmac.new(seed, message, hashlib.sha1).digest()
    offset = digest[-1] & 15
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1000000:06d}"


def _step(secret, code):
    if not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code):
        return None
    current = int(time.time()) // 30
    for step in (current, current - 1, current + 1):
        if hmac.compare_digest(totp(secret, step * 30), code):
            return step
    return None


def public_user(row):
    return {name: row[name] for name in ("id", "username", "display_name", "role")} | {"mfa_enabled": bool(row["totp_secret"])}


def token_hash(raw):
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


class Auth:
    def __init__(self, store):
        self.store = store
        self.lock = getattr(store, "lock", threading.RLock())
        self.dummy_hash = hash_password(secrets.token_urlsafe(24))
        with store.connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL, role TEXT NOT NULL,
                password_hash TEXT NOT NULL, totp_secret TEXT, totp_pending TEXT,
                pending_at REAL, last_totp_step INTEGER NOT NULL DEFAULT -1)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id INTEGER, csrf TEXT NOT NULL,
                created_at REAL NOT NULL, last_seen REAL NOT NULL, expires_at REAL NOT NULL)""")
            connection.execute("CREATE TABLE IF NOT EXISTS login_attempts (peer TEXT NOT NULL, at REAL NOT NULL)")

    def setup_required(self):
        with self.store.connect() as connection:
            return not bool(connection.execute("SELECT 1 FROM users LIMIT 1").fetchone())

    def create_user(self, username, password, display_name, role, first=False, connection=None):
        if not isinstance(username, str) or not USERNAME.fullmatch(username.lower()):
            raise ValueError("Username must be 3–32 letters, numbers, dots, dashes or underscores, starting with a letter.")
        if not isinstance(display_name, str) or not 1 <= len(display_name.strip()) <= 80 or any(ord(char) < 32 for char in display_name):
            raise ValueError("Display name must contain 1–80 printable characters.")
        if role not in ({"admin"} if first else {"operator", "customer"}):
            raise ValueError("Unsupported account role.")
        encoded = hash_password(password)
        if connection is None:
            with self.lock, self.store.connect() as owned:
                owned.execute("BEGIN IMMEDIATE")
                return self._insert(owned, username.lower(), encoded, display_name.strip(), role, first)
        return self._insert(connection, username.lower(), encoded, display_name.strip(), role, first)

    def _insert(self, connection, username, encoded, display_name, role, first):
        if first and connection.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            raise ValueError("The local workspace is already configured. Sign in instead.")
        if not first and not connection.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            raise ValueError("Create the workspace administrator first.")
        try:
            if first:
                cursor = connection.execute("INSERT INTO users (id,username,display_name,role,password_hash) VALUES (1,?,?,?,?)", (username, display_name, role, encoded))
            else:
                cursor = connection.execute("INSERT INTO users (username,display_name,role,password_hash) VALUES (?,?,?,?)", (username, display_name, role, encoded))
        except sqlite3.IntegrityError as exc:
            raise ValueError("That local username is already in use.") from exc
        return public_user(connection.execute("SELECT * FROM users WHERE id=?", (cursor.lastrowid,)).fetchone())

    def delete_user(self, user_id):
        with self.lock, self.store.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            connection.execute("DELETE FROM users WHERE id=? AND id<>1", (user_id,))

    def _new_session(self, connection, user_id):
        raw, csrf, now = secrets.token_urlsafe(32), secrets.token_urlsafe(32), time.time()
        lifetime = 8 * 3600 if user_id is not None else 600
        connection.execute("DELETE FROM sessions WHERE expires_at <= ? OR last_seen <= ?", (now, now - 1800))
        connection.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?)", (token_hash(raw), user_id, csrf, now, now, now + lifetime))
        return raw, csrf

    def new_session(self, user_id):
        with self.lock, self.store.connect() as connection:
            return self._new_session(connection, user_id)

    def _session_row(self, connection, raw, touch=True):
        if not isinstance(raw, str) or not raw.isascii() or len(raw) > 128:
            return None
        row = connection.execute("SELECT * FROM sessions WHERE token_hash=?", (token_hash(raw),)).fetchone()
        now = time.time()
        if row is None:
            return None
        if row["expires_at"] <= now or row["last_seen"] <= now - 1800:
            connection.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(raw),))
            return None
        if touch:
            connection.execute("UPDATE sessions SET last_seen=? WHERE token_hash=?", (now, token_hash(raw)))
        return row

    def session(self, raw):
        with self.lock, self.store.connect() as connection:
            session = self._session_row(connection, raw)
            if session is None or session["user_id"] is None:
                return None
            row = connection.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
            return public_user(row) if row else None

    def preauth(self, raw=None):
        with self.lock, self.store.connect() as connection:
            row = self._session_row(connection, raw)
            if row is not None:
                return raw, row["csrf"]
            return self._new_session(connection, None)

    def csrf_valid(self, raw, provided):
        if not isinstance(provided, str) or not provided.isascii():
            return False
        with self.lock, self.store.connect() as connection:
            row = self._session_row(connection, raw, touch=False)
            return row is not None and hmac.compare_digest(row["csrf"], provided)

    def logout(self, raw):
        if isinstance(raw, str) and raw.isascii():
            with self.store.connect() as connection:
                connection.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(raw),))

    def allow_login(self, peer):
        with self.lock, self.store.connect() as connection:
            now = time.time()
            connection.execute("DELETE FROM login_attempts WHERE at <= ?", (now - 60,))
            count = connection.execute("SELECT COUNT(*) FROM login_attempts WHERE peer=?", (peer,)).fetchone()[0]
            if count >= 8:
                return False
            connection.execute("INSERT INTO login_attempts VALUES (?,?)", (peer, now))
            return True

    def login(self, username, password, otp=""):
        if not isinstance(username, str):
            raise ValueError("Sign-in failed. Check your credentials and verification code.")
        with self.lock, self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM users WHERE username=?", (username.lower(),)).fetchone()
            verified = verify_password(password, row["password_hash"] if row else self.dummy_hash)
            if row is None or not verified:
                raise ValueError("Sign-in failed. Check your credentials and verification code.")
            if row["totp_secret"]:
                step = _step(row["totp_secret"], otp)
                if step is None or step <= row["last_totp_step"]:
                    raise ValueError("Sign-in failed. Check your credentials and verification code.")
                connection.execute("UPDATE users SET last_totp_step=? WHERE id=?", (step, row["id"]))
            raw, csrf = self._new_session(connection, row["id"])
            return public_user(row), raw, csrf

    def users(self):
        with self.store.connect() as connection:
            return [public_user(row) for row in connection.execute("SELECT * FROM users ORDER BY id")]

    def enroll(self, user_id):
        with self.lock, self.store.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if row is None:
                raise ValueError("Local user not found.")
            if row["totp_secret"]:
                raise ValueError("Two-step verification is already enabled.")
            secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
            connection.execute("UPDATE users SET totp_pending=?,pending_at=? WHERE id=?", (secret, time.time(), user_id))
            uri = "otpauth://totp/" + quote("Portbug Bank:" + row["username"]) + "?" + urlencode({"secret": secret, "issuer": "Portbug Bank", "algorithm": "SHA1", "digits": 6, "period": 30})
            return {"secret": secret, "otpauth_uri": uri}

    def confirm(self, user_id, code, keep_token=None):
        if not self.allow_login(f"mfa-confirm:{user_id}"):
            raise ValueError("Too many verification attempts. Wait a minute before retrying.")
        with self.lock, self.store.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if row is None or not row["totp_pending"] or row["pending_at"] < time.time() - 600:
                raise ValueError("Enrollment expired. Start two-step verification setup again.")
            step = _step(row["totp_pending"], code)
            if step is None:
                raise ValueError("Verification code is invalid. Check your authenticator clock and try again.")
            connection.execute("UPDATE users SET totp_secret=totp_pending,totp_pending=NULL,pending_at=NULL,last_totp_step=? WHERE id=?", (step, user_id))
            if isinstance(keep_token, str) and keep_token.isascii():
                connection.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user_id, token_hash(keep_token)))
            else:
                connection.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            return public_user(connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
