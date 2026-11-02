import copy
import unittest

from portbug.engine import (
    RULES, SCENARIOS, apply_scenario, detect, evaluate_fraud, initial_state,
    respond, scenario_event,
)


class DetectionTests(unittest.TestCase):
    def test_each_rule_matches_its_positive_fixture_and_has_attack_mapping(self):
        for scenario in SCENARIOS[:-1]:
            with self.subTest(scenario=scenario):
                findings = detect([scenario_event(scenario)])
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0]["rule"], scenario)
                self.assertRegex(RULES[scenario]["technique"], r"^T\d{4}(?:\.\d{3})?$")

    def test_each_rule_rejects_benign_fixture(self):
        events = [
            {"type": "credential_abuse", "failures": 7, "window_seconds": 180},
            {"type": "payment_change", "beneficiary_changed": True, "dual_approval": True},
            {"type": "data_export", "rows": 1000, "baseline_rows": 300},
            {"type": "privilege_change", "privileged": True, "approved": True},
            {"type": "impossible_travel", "distance_km": 500, "elapsed_minutes": 60},
        ]
        for event in events:
            with self.subTest(rule=event["type"]):
                self.assertEqual(detect([event]), [])

    def test_time_window_and_speed_boundaries(self):
        self.assertEqual(detect([{"type": "credential_abuse", "failures": 100, "window_seconds": 301}]), [])
        self.assertEqual(detect([{"type": "impossible_travel", "distance_km": 900, "elapsed_minutes": 60}]), [])

    def test_rejects_invalid_numeric_values_and_oversized_batch(self):
        for value in (True, -1, float("nan"), float("inf"), "14"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                detect([{"type": "credential_abuse", "failures": value, "window_seconds": 180}])
        with self.assertRaises(ValueError):
            detect([{}] * 101)

    def test_rejects_truthy_string_as_approval(self):
        with self.assertRaises(ValueError):
            detect([{"type": "payment_change", "beneficiary_changed": True, "dual_approval": "false"}])


class FraudTests(unittest.TestCase):
    def test_baseline_is_allowed_with_explanation(self):
        result = evaluate_fraud({"amount_chf": 200, "velocity_count": 1})
        self.assertEqual((result["score"], result["decision"]), (0, "allow"))
        self.assertTrue(result["reasons"])

    def test_combined_signals_are_capped_and_explained(self):
        result = evaluate_fraud({"amount_chf": 50000, "velocity_count": 8, "new_beneficiary": True,
                                 "distance_km": 5900, "minutes_since_previous": 20, "fan_in_count": 9})
        self.assertEqual((result["score"], result["decision"]), (100, "review"))
        self.assertEqual(len(result["reasons"]), 4)

    def test_a_single_signal_is_advisory(self):
        result = evaluate_fraud({"amount_chf": 50000, "new_beneficiary": True})
        self.assertEqual((result["score"], result["decision"]), (35, "allow"))

    def test_invalid_inputs_rejected(self):
        for record in ({"amount_chf": -1}, {"velocity_count": "many"}, {"new_beneficiary": "yes"}):
            with self.subTest(record=record), self.assertRaises(ValueError):
                evaluate_fraud(record)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.state = initial_state()

    def test_seed_is_synthetic_and_independent(self):
        self.assertEqual(self.state["bank"], "Portbug Bank")
        self.assertEqual(self.state["author"], "Vaibhav Thakur")
        self.assertEqual(len(self.state["alerts"]), 5)
        self.state["alerts"].clear()
        self.assertEqual(len(initial_state()["alerts"]), 5)

    def test_baseline_evaluation_does_not_create_alert(self):
        count = len(self.state["alerts"])
        result = apply_scenario(self.state, "baseline")
        self.assertEqual(result["alerts_created"], 0)
        self.assertEqual(len(self.state["alerts"]), count)

    def test_scenario_changes_alert_metrics_and_fraud(self):
        before = self.state["metrics"][0]["value"]
        fraud_count = len(self.state["fraud"])
        apply_scenario(self.state, "payment_change")
        self.assertNotEqual(self.state["metrics"][0]["value"], before)
        self.assertEqual(len(self.state["fraud"]), fraud_count + 1)
        self.assertEqual(self.state["fraud"][0]["decision"], "review")

    def test_valid_response_lifecycle_updates_linked_incident(self):
        identifier = self.state["alerts"][0]["id"]
        for action, expected in (("triage", "investigating"), ("contain", "contained"), ("resolve", "resolved")):
            result = respond(self.state, identifier, action)
            self.assertEqual(self.state["alerts"][0]["status"], expected)
            self.assertEqual(self.state["incidents"][0]["status"], expected)
            self.assertIn(expected, result["title"])

    def test_out_of_order_or_unknown_response_does_not_mutate(self):
        before = copy.deepcopy(self.state)
        identifier = self.state["alerts"][0]["id"]
        for target, action in ((identifier, "contain"), (identifier, "delete"), ("unknown", "triage")):
            with self.subTest(target=target, action=action), self.assertRaises(ValueError):
                respond(self.state, target, action)
            self.assertEqual(self.state, before)

    def test_unknown_scenario_does_not_mutate(self):
        before = copy.deepcopy(self.state)
        with self.assertRaises(ValueError):
            apply_scenario(self.state, "external_scan")
        self.assertEqual(self.state, before)

    def test_history_is_bounded_and_ids_remain_unique(self):
        for _ in range(110):
            apply_scenario(self.state, "payment_change")
        for key in ("alerts", "incidents", "fraud"):
            self.assertEqual(len(self.state[key]), 100)
        self.assertEqual(len({a["id"] for a in self.state["alerts"]}), 100)


if __name__ == "__main__":
    unittest.main()
