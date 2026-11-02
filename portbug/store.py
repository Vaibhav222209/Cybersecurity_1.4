"""Atomic local simulation state and verifiable, keyed audit chains.

This detects changes without the local key. It does not protect against the host
owner, establish nonrepudiation, or detect restoration of an entire old snapshot.
"""

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import engine


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(state):
    return hashlib.sha256(canonical(state).encode()).hexdigest()


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.database = self.directory / "portbug.sqlite3"
        key_path = self.directory / "audit.key"
        # Exclusive creation avoids replacing an existing audit signing key.
        try:
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(secrets.token_bytes(32))
        self.key = key_path.read_bytes()
        if len(self.key) != 32:
            raise ValueError("Invalid local audit key; restore the matching state/key backup.")
        self.lock = threading.RLock()
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)")
            connection.execute("""CREATE TABLE IF NOT EXISTS audit (
                sequence INTEGER PRIMARY KEY, timestamp TEXT NOT NULL,
                action TEXT NOT NULL, detail TEXT NOT NULL,
                state_digest TEXT NOT NULL, previous_hash TEXT NOT NULL, hash TEXT NOT NULL)""")
            if not connection.execute("SELECT 1 FROM state").fetchone():
                if connection.execute("SELECT 1 FROM audit LIMIT 1").fetchone():
                    raise ValueError("Saved state is missing but audit history exists. Restore a verified backup.")
                state = engine.initial_state()
                connection.execute("INSERT INTO state VALUES (1, ?)", (canonical(state),))
                self.append(connection, state, "lab.initialized", "Synthetic demonstration workspace created")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def append(self, connection, state, action, detail):
        last = connection.execute("SELECT sequence, hash FROM audit ORDER BY sequence DESC LIMIT 1").fetchone()
        entry = {
            "sequence": last["sequence"] + 1 if last else 1,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "action": action,
            "detail": detail,
            "state_digest": digest(state),
            "previous_hash": last["hash"] if last else "0" * 64,
        }
        signature = hmac.new(self.key, canonical(entry).encode(), hashlib.sha256).hexdigest()
        connection.execute(
            "INSERT INTO audit VALUES (?, ?, ?, ?, ?, ?, ?)",
            (*entry.values(), signature),
        )

    def verify(self, connection, state):
        rows = connection.execute("SELECT * FROM audit ORDER BY sequence").fetchall()
        previous = "0" * 64
        valid = bool(rows)
        for expected, row in enumerate(rows, 1):
            entry = dict(row)
            signature = entry.pop("hash")
            computed = hmac.new(self.key, canonical(entry).encode(), hashlib.sha256).hexdigest()
            if entry["sequence"] != expected or entry["previous_hash"] != previous or not hmac.compare_digest(signature, computed):
                valid = False
            previous = signature
        if rows and rows[-1]["state_digest"] != digest(state):
            valid = False
        return {
            "valid": valid, "count": len(rows), "head": previous,
            "entries": [dict(row) for row in reversed(rows[-100:])],
        }

    def snapshot(self):
        with self.lock, self.connect() as connection:
            connection.execute("BEGIN")
            state = json.loads(connection.execute("SELECT body FROM state WHERE id=1").fetchone()[0])
            state["audit"] = self.verify(connection, state)
            return state

    def change(self, action, payload):
        with self.lock, self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = json.loads(connection.execute("SELECT body FROM state WHERE id=1").fetchone()[0])
            if not self.verify(connection, state)["valid"]:
                raise ValueError("Audit verification failed. Restore a verified local backup before making changes.")
            if action == "scenario":
                result = engine.apply_scenario(state, payload["scenario"])
                detail = payload["scenario"]
            elif action == "response":
                result = engine.respond(state, payload["alert_id"], payload["action"])
                detail = f"{payload['alert_id']}: {payload['action']} (simulation only)"
            else:
                raise ValueError("Unknown operation")
            connection.execute("UPDATE state SET body=? WHERE id=1", (canonical(state),))
            self.append(connection, state, f"lab.{action}", detail)
            state["audit"] = self.verify(connection, state)
            return {"state": state, "result": result}

    def backup(self, destination):
        """Use SQLite's backup API so WAL data is included consistently."""
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=False, mode=0o700)
        with self.lock, self.connect() as source:
            state = json.loads(source.execute("SELECT body FROM state WHERE id=1").fetchone()[0])
            if not self.verify(source, state)["valid"]:
                raise ValueError("Cannot back up a workspace with a failed integrity check")
            with sqlite3.connect(destination / "portbug.sqlite3") as target:
                source.backup(target)
            descriptor = os.open(destination / "audit.key", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(self.key)
