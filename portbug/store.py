"""Transactional synthetic banking state and local audit verification."""

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from pathlib import Path

from . import model


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def state_digest(state):
    return hashlib.sha256(canonical(state).encode()).hexdigest()


def total_funds(state):
    return sum(account["balance_cents"] for account in state["accounts"]) + sum(payment["amount_cents"] for payment in state["transfers"] if payment["status"] == "pending_review")


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.database = self.directory / "bank.sqlite3"
        self.lock = threading.RLock()
        keyfile = self.directory / "audit.key"
        try:
            descriptor = os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(secrets.token_bytes(32))
        self.key = keyfile.read_bytes()
        if len(self.key) != 32:
            raise ValueError("Invalid audit key; restore the matching banking workspace backup.")
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)")
            connection.execute("""CREATE TABLE IF NOT EXISTS audit (
                sequence INTEGER PRIMARY KEY, timestamp TEXT NOT NULL,
                actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL,
                state_digest TEXT NOT NULL, previous_hash TEXT NOT NULL, hash TEXT NOT NULL)""")
            existing = connection.execute("SELECT body FROM state WHERE id=1").fetchone()
            if existing:
                state = json.loads(existing[0])
                if not isinstance(state, dict) or state.get("schema") != 3:
                    raise ValueError("Incompatible workspace. Select a NEW --data-dir; existing data has not been reset.")
            else:
                if connection.execute("SELECT 1 FROM audit LIMIT 1").fetchone():
                    raise ValueError("Missing banking state with existing history. Restore a verified backup.")
                state = model.initial_state()
                connection.execute("INSERT INTO state VALUES (1,?)", (canonical(state),))
                self.append(connection, state, "system", "workspace.created", "Synthetic banking ledger initialized")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def load(self, connection):
        row = connection.execute("SELECT body FROM state WHERE id=1").fetchone()
        if not row:
            raise ValueError("Banking state missing. Restore a verified backup.")
        state = json.loads(row[0])
        if not isinstance(state, dict) or state.get("schema") != 3:
            raise ValueError("Invalid banking workspace schema")
        return state

    def append(self, connection, state, actor, action, detail):
        last = connection.execute("SELECT sequence,hash FROM audit ORDER BY sequence DESC LIMIT 1").fetchone()
        record = {
            "sequence": last["sequence"] + 1 if last else 1,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "actor": str(actor), "action": action, "detail": detail,
            "state_digest": state_digest(state),
            "previous_hash": last["hash"] if last else "0" * 64,
        }
        signature = hmac.new(self.key, canonical(record).encode(), hashlib.sha256).hexdigest()
        connection.execute("INSERT INTO audit VALUES (?,?,?,?,?,?,?,?)", (*record.values(), signature))

    def verify(self, connection, state):
        rows = connection.execute("SELECT * FROM audit ORDER BY sequence").fetchall()
        previous = "0" * 64
        valid = bool(rows)
        for sequence, row in enumerate(rows, 1):
            entry = dict(row)
            signature = entry.pop("hash")
            expected = hmac.new(self.key, canonical(entry).encode(), hashlib.sha256).hexdigest()
            if entry["sequence"] != sequence or entry["previous_hash"] != previous or not hmac.compare_digest(signature, expected):
                valid = False
            previous = signature
        if rows and rows[-1]["state_digest"] != state_digest(state):
            valid = False
        return {"valid": valid, "count": len(rows), "head": previous, "entries": [dict(row) for row in reversed(rows[-100:])]}

    def raw_snapshot(self):
        with self.lock, self.connect() as connection:
            connection.execute("BEGIN")
            state = self.load(connection)
            state["audit"] = self.verify(connection, state)
            return state

    def snapshot(self, actor):
        if not actor:
            raise PermissionError("Sign in to view banking data")
        raw = self.raw_snapshot()
        audit = raw.pop("audit")
        filtered = model.view(raw, actor)
        if actor["role"] == "customer":
            audit = {"valid": audit["valid"], "count": audit["count"], "head": audit["head"], "entries": []}
        filtered["audit"] = audit
        return filtered

    def _change(self, connection, action, payload, actor):
        state = self.load(connection)
        if not self.verify(connection, state)["valid"]:
            raise ValueError("Audit integrity check failed; changes are blocked. Restore a verified backup.")
        before_funds = total_funds(state)
        result = model.apply(state, action, payload, actor)
        if any(type(account["balance_cents"]) is not int or account["balance_cents"] < 0 for account in state["accounts"]):
            raise ValueError("Ledger invariant failed: account balances must be nonnegative integer cents")
        if action in {"transfer", "decision"} and total_funds(state) != before_funds:
            raise ValueError("Ledger invariant failed: settled balances plus reserved funds must be conserved")
        connection.execute("UPDATE state SET body=? WHERE id=1", (canonical(state),))
        # Exclude all credential-bearing or arbitrary raw request data.
        detail = str(result.get("summary", result.get("message", action)))[:500]
        self.append(connection, state, actor.get("username", actor.get("id", "system")), action, detail)
        public = model.view(state, actor) if actor.get("role") != "system" else {}
        audit = self.verify(connection, state)
        if actor.get("role") == "customer":
            audit["entries"] = []
        public["audit"] = audit
        return {"state": public, "result": result}

    def change(self, action, payload, actor):
        if not actor:
            raise PermissionError("Sign in to continue")
        with self.lock, self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            return self._change(connection, action, payload, actor)

    def provision(self, user, actor, connection=None):
        payload = {"user_id": user["id"], "display_name": user["display_name"], "role": user["role"]}
        if connection is not None:
            return self._change(connection, "provision", payload, actor)
        return self.change("provision", payload, actor)

    def security_event(self, event_type, detail, user_id=0):
        return self.change("security_event", {"type": event_type, "detail": detail, "user_id": user_id}, {"id": 0, "username": "system", "role": "system"})

    def backtest(self, payload, actor):
        if not actor or actor.get("role") not in {"operator", "admin"}:
            raise PermissionError("Security operator access required")
        return {"result": model.backtest(payload)}

    def backup(self, destination):
        destination = Path(destination)
        with self.lock, self.connect() as source:
            state = self.load(source)
            if not self.verify(source, state)["valid"]:
                raise ValueError("Cannot back up a workspace with failed integrity verification")
            destination.mkdir(parents=True, exist_ok=False, mode=0o700)
            with closing(sqlite3.connect(destination / "bank.sqlite3")) as target:
                source.backup(target)
            descriptor = os.open(destination / "audit.key", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(self.key)
