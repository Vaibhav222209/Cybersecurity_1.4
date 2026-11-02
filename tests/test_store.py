import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from portbug.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = Store(self.root / "state")

    def test_persistence_and_key_reuse(self):
        self.store.change("scenario", {"scenario": "credential_abuse"})
        reopened = Store(self.root / "state")
        self.assertEqual(reopened.snapshot(), self.store.snapshot())
        self.assertTrue(reopened.snapshot()["audit"]["valid"])
        self.assertEqual(reopened.snapshot()["audit"]["count"], 2)

    def test_audit_tamper_detected_and_mutation_refused(self):
        with self.store.connect() as connection:
            connection.execute("UPDATE audit SET detail='modified' WHERE sequence=1")
        self.assertFalse(self.store.snapshot()["audit"]["valid"])
        with self.assertRaisesRegex(ValueError, "Audit verification failed"):
            self.store.change("scenario", {"scenario": "baseline"})

    def test_state_tamper_detected(self):
        with self.store.connect() as connection:
            state = self.store.snapshot()
            state.pop("audit")
            state["author"] = "modified"
            connection.execute("UPDATE state SET body=?", (json.dumps(state),))
        self.assertFalse(self.store.snapshot()["audit"]["valid"])

    def test_failed_operation_rolls_back(self):
        before = self.store.snapshot()
        with self.assertRaises(ValueError):
            self.store.change("scenario", {"scenario": "unknown"})
        self.assertEqual(before, self.store.snapshot())

    def test_concurrent_mutations_keep_chain_and_state_consistent(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: self.store.change("scenario", {"scenario": "baseline"}), range(12)))
        audit = self.store.snapshot()["audit"]
        self.assertTrue(audit["valid"])
        self.assertEqual(audit["count"], 13)

    def test_backup_restores_state_and_key(self):
        self.store.change("scenario", {"scenario": "payment_change"})
        destination = self.root / "recovery"
        self.store.backup(destination)
        restored = Store(destination)
        self.assertEqual(restored.snapshot(), self.store.snapshot())
        restored.change("scenario", {"scenario": "baseline"})
        self.assertTrue(restored.snapshot()["audit"]["valid"])
        self.assertEqual(self.store.snapshot()["audit"]["count"], 2)

    def test_backup_never_overwrites_existing_directory(self):
        with self.assertRaises(FileExistsError):
            self.store.backup(self.root / "state")

    def test_wrong_key_detected(self):
        (self.root / "state" / "audit.key").write_bytes(b"x" * 32)
        self.assertFalse(Store(self.root / "state").snapshot()["audit"]["valid"])

    def test_missing_state_never_silently_reinitializes_existing_history(self):
        with self.store.connect() as connection:
            connection.execute("DELETE FROM state")
        with self.assertRaisesRegex(ValueError, "Saved state is missing"):
            Store(self.root / "state")
