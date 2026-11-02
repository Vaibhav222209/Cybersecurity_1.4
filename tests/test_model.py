import copy
import unittest

from portbug import model

ADMIN = {"id": 1, "role": "admin", "username": "local-admin"}
REVIEWER = {"id": 2, "role": "operator", "username": "local-reviewer"}
CUSTOMER = {"id": 3, "role": "customer", "username": "local-customer"}


class BankingModelTests(unittest.TestCase):
    def setUp(self):
        self.state = model.initial_state()

    def payment(self, amount="25.00", beneficiary="BEN-ALPINE", key="payment-key-001", source="ACC-0001-C"):
        return {"from_account": source, "beneficiary_id": beneficiary, "amount": amount, "reference": "Synthetic invoice", "idempotency_key": key}

    def total(self):
        return sum(account["balance_cents"] for account in self.state["accounts"]) + sum(payment["amount_cents"] for payment in self.state["transfers"] if payment["status"] == "pending_review")

    def test_seed_is_balanced_and_non_routable(self):
        self.assertEqual(self.state["accounts"][0]["balance_cents"], 14_285_075)
        self.assertEqual(sum(item["amount_cents"] for item in self.state["ledger"]), 0)
        self.assertTrue(all(account["identifier"].startswith("PB-DEMO-") for account in self.state["accounts"]))

    def test_trusted_low_value_payment_settles_and_conserves_money(self):
        total = self.total()
        balance = self.state["accounts"][0]["balance_cents"]
        result = model.apply(self.state, "transfer", self.payment("12.34"), ADMIN)
        self.assertEqual(result["transfer"]["status"], "settled")
        self.assertEqual(self.state["accounts"][0]["balance_cents"], balance - 1234)
        self.assertEqual(self.total(), total)
        self.assertEqual(sum(entry["amount_cents"] for entry in self.state["ledger"]), 0)

    def test_large_payment_reserves_then_credits_only_after_independent_approval(self):
        total = self.total()
        result = model.apply(self.state, "transfer", self.payment("12500.00"), ADMIN)
        payment = result["transfer"]
        self.assertEqual(payment["status"], "pending_review")
        self.assertEqual(self.total(), total)
        receiver = next(account for account in self.state["accounts"] if account["id"] == payment["to_account"])
        balance = receiver["balance_cents"]
        model.apply(self.state, "decision", {"transfer_id": payment["id"], "decision": "approve", "note": "Independent fixture review"}, REVIEWER)
        self.assertEqual(receiver["balance_cents"], balance + 1_250_000)
        self.assertEqual(self.total(), total)
        self.assertEqual(self.state["cases"][0]["status"], "settled")
        self.assertEqual(len(self.state["cases"][0]["timeline"]), 2)

    def test_rejection_returns_reserved_money_exactly_once(self):
        balance = self.state["accounts"][0]["balance_cents"]
        result = model.apply(self.state, "transfer", self.payment("75", "BEN-NEW"), ADMIN)
        payload = {"transfer_id": result["transfer_id"], "decision": "reject", "note": "Synthetic beneficiary verification failed"}
        model.apply(self.state, "decision", payload, REVIEWER)
        self.assertEqual(self.state["accounts"][0]["balance_cents"], balance)
        before = copy.deepcopy(self.state)
        with self.assertRaises(ValueError):
            model.apply(self.state, "decision", payload, REVIEWER)
        self.assertEqual(self.state, before)

    def test_self_approval_and_customer_approval_are_forbidden(self):
        result = model.apply(self.state, "transfer", self.payment("11000"), ADMIN)
        payload = {"transfer_id": result["transfer_id"], "decision": "approve", "note": "A review"}
        before = copy.deepcopy(self.state)
        for actor in (ADMIN, CUSTOMER):
            with self.assertRaises(PermissionError):
                model.apply(self.state, "decision", payload, actor)
            self.assertEqual(self.state, before)

    def test_account_ownership_applies_even_to_administrator(self):
        before = copy.deepcopy(self.state)
        for actor, source in ((CUSTOMER, "ACC-0001-C"), (ADMIN, "DEMO-RECIPIENT-01")):
            with self.assertRaises(PermissionError):
                model.apply(self.state, "transfer", self.payment(source=source), actor)
        self.assertEqual(before, self.state)

    def test_operator_cannot_initiate_payment(self):
        with self.assertRaises(PermissionError):
            model.apply(self.state, "transfer", self.payment(), REVIEWER)

    def test_integer_cents_and_invalid_money_inputs(self):
        self.assertEqual(model.money("0.01"), 1)
        self.assertEqual(model.money("1234.56"), 123456)
        for amount in ("0", "-1", "1.001", "NaN", "Infinity", "1e3", 2.5, True, " 10", "1000000.01"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                model.money(amount)

    def test_insufficient_funds_does_not_leave_partial_entries(self):
        before = copy.deepcopy(self.state)
        with self.assertRaises(ValueError):
            model.apply(self.state, "transfer", self.payment("999999"), ADMIN)
        self.assertEqual(self.state, before)

    def test_identical_retry_is_idempotent_but_reused_key_cannot_change_payment(self):
        request = self.payment()
        first = model.apply(self.state, "transfer", request, ADMIN)
        before = copy.deepcopy(self.state)
        second = model.apply(self.state, "transfer", request, ADMIN)
        self.assertEqual(first["transfer_id"], second["transfer_id"])
        self.assertTrue(second["replayed"])
        # as_of can be refreshed by apply; no financial/event duplication.
        for field in ("accounts", "transfers", "ledger", "events", "receipts"):
            self.assertEqual(before[field], self.state[field])
        with self.assertRaises(ValueError):
            model.apply(self.state, "transfer", {**request, "amount": "26"}, ADMIN)

    def test_velocity_hold_is_based_on_actual_recent_payments(self):
        for index in range(4):
            result = model.apply(self.state, "transfer", self.payment(key=f"velocity-key-{index}"), ADMIN)
            self.assertEqual(result["transfer"]["status"], "settled" if index < 3 else "pending_review")
        self.assertTrue(any("Velocity" in reason for reason in result["transfer"]["reasons"]))

    def test_customer_views_exclude_other_accounts_and_security_history(self):
        model.apply(self.state, "provision", {"user_id": 3, "display_name": "Synthetic Client", "role": "customer"}, ADMIN)
        customer = model.view(self.state, CUSTOMER)
        self.assertEqual({account["owner_id"] for account in customer["accounts"]}, {3})
        self.assertEqual(customer["transfers"], [])
        self.assertEqual(customer["events"], [])
        self.assertNotIn("receipts", customer)
        customer["accounts"][0]["balance_cents"] = 0
        self.assertNotEqual(next(account for account in self.state["accounts"] if account["owner_id"] == 3)["balance_cents"], 0)

    def test_provision_retries_do_not_duplicate_opening_funds(self):
        payload = {"user_id": 3, "display_name": "Synthetic Client"}
        model.apply(self.state, "provision", payload, ADMIN)
        total = self.total()
        model.apply(self.state, "provision", payload, ADMIN)
        self.assertEqual(self.total(), total)
        self.assertEqual(sum(account["owner_id"] == 3 for account in self.state["accounts"]), 2)

    def test_rules_are_admin_only_and_pending_decisions_are_not_rewritten(self):
        result = model.apply(self.state, "transfer", self.payment("12000"), ADMIN)
        payload = {"high_value_chf": "50000", "velocity_limit": 10}
        with self.assertRaises(PermissionError):
            model.apply(self.state, "rules", payload, REVIEWER)
        model.apply(self.state, "rules", payload, ADMIN)
        self.assertEqual(next(payment for payment in self.state["transfers"] if payment["id"] == result["transfer_id"])["status"], "pending_review")

    def test_backtest_has_fixed_labels_and_real_false_positive_negative_tradeoff(self):
        default = model.backtest({"high_value_chf": "10000", "velocity_limit": 3})
        self.assertEqual((default["tp"], default["fp"], default["tn"], default["fn"]), (3, 1, 3, 1))
        self.assertEqual((default["precision"], default["recall"]), (0.75, 0.75))
        strict = model.backtest({"high_value_chf": "100", "velocity_limit": 1})
        self.assertGreater(strict["fp"], default["fp"])
        self.assertGreater(strict["recall"], default["recall"])
        relaxed = model.backtest({"high_value_chf": "50000", "velocity_limit": 20})
        self.assertGreater(relaxed["fn"], default["fn"])

    def test_rule_input_bounds(self):
        for payload in ({"high_value_chf": "99", "velocity_limit": 3}, {"high_value_chf": "10000", "velocity_limit": True}, {"high_value_chf": "10000", "velocity_limit": 0}, {"high_value_chf": "10000", "velocity_limit": 21}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                model.rule_validation(payload)

    def test_review_note_required_and_unknown_operation_rejected(self):
        result = model.apply(self.state, "transfer", self.payment("12000"), ADMIN)
        with self.assertRaises(ValueError):
            model.apply(self.state, "decision", {"transfer_id": result["transfer_id"], "decision": "approve", "note": ""}, REVIEWER)
        with self.assertRaises(ValueError):
            model.apply(self.state, "unknown", {}, ADMIN)


if __name__ == "__main__":
    unittest.main()
