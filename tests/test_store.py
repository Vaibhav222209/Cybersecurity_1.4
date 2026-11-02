import json
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from portbug.store import Store
from portbug.auth import Auth

ADMIN = {"id": 1, "username": "owner", "display_name": "Synthetic owner", "role": "admin"}
OPERATOR = {"id": 2, "username": "reviewer", "display_name": "Synthetic reviewer", "role": "operator"}
CUSTOMER = {"id": 3, "username": "client", "display_name": "Synthetic client", "role": "customer"}


def money(cents):
    return f"{cents // 100}.{cents % 100:02}"


def funds(state):
    return sum(account["balance_cents"] for account in state["accounts"]) + sum(transfer["amount_cents"] for transfer in state["transfers"] if transfer["status"] == "pending_review")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.store = Store(self.directory / "bank")

    def payment(self, amount="125.50", key="synthetic-test-payment-0001"):
        state = self.store.raw_snapshot()
        account = next(account for account in state["accounts"] if account["owner_id"] == 1)
        beneficiary = state["beneficiaries"][0]
        return {"from_account": account["id"], "beneficiary_id": beneficiary["id"], "amount": amount, "reference": "Synthetic test payment", "idempotency_key": key}

    def test_bank_state_and_audit_persist(self):
        result = self.store.change("transfer", self.payment(), ADMIN)
        reopened = Store(self.directory / "bank")
        self.assertEqual(reopened.raw_snapshot(), self.store.raw_snapshot())
        self.assertTrue(result["state"]["audit"]["valid"])

    def test_failed_payment_is_atomic(self):
        before = self.store.raw_snapshot()
        payment = self.payment("999999999.00")
        with self.assertRaises(ValueError):
            self.store.change("transfer", payment, ADMIN)
        self.assertEqual(self.store.raw_snapshot(), before)

    def test_persistence_rejects_a_domain_funds_invariant_violation(self):
        before = self.store.raw_snapshot()

        def broken_domain(state, action, payload, actor):
            state["accounts"][0]["balance_cents"] += 1
            return {"summary": "Unbalanced payment"}

        with patch("portbug.store.model.apply", side_effect=broken_domain):
            with self.assertRaisesRegex(ValueError, "must be conserved"):
                self.store.change("transfer", self.payment(), ADMIN)
        self.assertEqual(self.store.raw_snapshot(), before)

    def test_concurrent_payments_cannot_overspend(self):
        before = self.store.raw_snapshot()
        account = next(account for account in before["accounts"] if account["owner_id"] == 1)
        amount = money(account["balance_cents"] // 2 + 1)

        def pay(index):
            try:
                self.store.change("transfer", self.payment(amount, f"concurrent-payment-{index:04d}"), ADMIN)
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=4) as pool:
            accepted = list(pool.map(pay, range(4)))
        after = self.store.raw_snapshot()
        self.assertEqual(sum(accepted), 1)
        self.assertEqual(funds(before), funds(after))
        self.assertTrue(after["audit"]["valid"])
        self.assertTrue(all(account["balance_cents"] >= 0 for account in after["accounts"]))

    def test_same_idempotency_key_never_debits_twice(self):
        payment = self.payment()
        self.store.change("transfer", payment, ADMIN)
        once = self.store.raw_snapshot()
        self.store.change("transfer", payment, ADMIN)
        twice = self.store.raw_snapshot()
        self.assertEqual(once["accounts"], twice["accounts"])
        self.assertEqual(once["ledger"], twice["ledger"])
        self.assertEqual(len(once["transfers"]), len(twice["transfers"]))

    def test_customer_state_has_no_other_customer_financial_data(self):
        self.store.provision(CUSTOMER, ADMIN)
        visible = self.store.snapshot(CUSTOMER)
        self.assertTrue(visible["accounts"])
        self.assertTrue(all(account["owner_id"] == 3 for account in visible["accounts"]))
        self.assertEqual(visible.get("events", []), [])
        self.assertEqual(visible["audit"]["entries"], [])

    def test_backtest_does_not_change_ledger_or_thresholds(self):
        before = self.store.raw_snapshot()
        result = self.store.backtest({"high_value_chf": "2500.00", "velocity_limit": 2}, OPERATOR)
        self.assertIn("precision", result["result"])
        self.assertEqual(before, self.store.raw_snapshot())
        with self.assertRaises(PermissionError):
            self.store.backtest({"high_value_chf": "2500.00", "velocity_limit": 2}, CUSTOMER)

    def test_modified_audit_blocks_payments(self):
        with self.store.connect() as connection:
            connection.execute("UPDATE audit SET detail='changed'")
        self.assertFalse(self.store.raw_snapshot()["audit"]["valid"])
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.store.change("transfer", self.payment(), ADMIN)

    def test_state_modification_is_detected(self):
        with self.store.connect() as connection:
            body = json.loads(connection.execute("SELECT body FROM state").fetchone()[0])
            body["accounts"][0]["balance_cents"] += 100
            connection.execute("UPDATE state SET body=?", (json.dumps(body),))
        self.assertFalse(self.store.raw_snapshot()["audit"]["valid"])

    def test_backup_restores_balances_and_key(self):
        self.store.change("transfer", self.payment(), ADMIN)
        destination = self.directory / "recovery"
        self.store.backup(destination)
        restored = Store(destination)
        self.assertEqual(self.store.raw_snapshot(), restored.raw_snapshot())
        restored.change("transfer", self.payment("50.00", "recovery-payment-0002"), ADMIN)
        self.assertTrue(restored.raw_snapshot()["audit"]["valid"])
        self.assertNotEqual(restored.raw_snapshot()["accounts"], self.store.raw_snapshot()["accounts"])

    def test_backup_contains_local_identities_and_session_records(self):
        auth = Auth(self.store)
        password = "Synthetic-fixture-only-2026"
        user = auth.create_user("fixtureowner", password, "Synthetic Owner", "admin", first=True)
        _, token, _ = auth.login("fixtureowner", password)
        destination = self.directory / "identity-recovery"
        self.store.backup(destination)
        recovered = Store(destination)
        restored_auth = Auth(recovered)
        self.assertEqual(restored_auth.session(token)["id"], user["id"])
        self.assertEqual(restored_auth.login("fixtureowner", password)[0]["id"], user["id"])
        self.assertTrue(recovered.raw_snapshot()["audit"]["valid"])

    def test_missing_state_never_resets_financial_history(self):
        with self.store.connect() as connection:
            connection.execute("DELETE FROM state")
        with self.assertRaisesRegex(ValueError, "Missing banking state"):
            Store(self.directory / "bank")
