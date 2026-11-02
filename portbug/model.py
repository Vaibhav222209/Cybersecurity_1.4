"""Synthetic banking ledger with enforced ownership, holds and dual approval.

Money is stored as integer CHF cents. These payments are local records only;
there is no external banking connection or routable account identifier.
"""

import copy
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

MAX_TRANSFERS = 1000
MAX_AMOUNT_CENTS = 100_000_000


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def money(value, maximum=MAX_AMOUNT_CENTS):
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,2})?", value):
        raise ValueError("Amount must be a positive CHF decimal with at most two decimal places")
    cents = int(Decimal(value) * 100)
    if cents <= 0 or cents > maximum:
        raise ValueError("Amount is outside the permitted range")
    return cents


def require_role(actor, *roles):
    if not isinstance(actor, dict) or actor.get("role") not in roles:
        raise PermissionError("This role cannot perform that operation")


def text(value, name, maximum=140):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must contain 1–{maximum} characters")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{name} cannot contain control characters")
    return value.strip()


def rule_validation(payload):
    if not isinstance(payload, dict) or set(payload) != {"high_value_chf", "velocity_limit"}:
        raise ValueError("Specify high_value_chf and velocity_limit")
    threshold = money(payload["high_value_chf"])
    velocity = payload["velocity_limit"]
    if threshold < 10_000:
        raise ValueError("High-value threshold must be between CHF 100 and CHF 1,000,000")
    if isinstance(velocity, bool) or not isinstance(velocity, int) or not 1 <= velocity <= 20:
        raise ValueError("Velocity limit must be an integer between 1 and 20")
    return {"high_value_cents": threshold, "velocity_limit": velocity}


def evaluate(amount_cents, trusted, velocity_count, rules):
    reasons = []
    score = 0
    if amount_cents >= rules["high_value_cents"]:
        score += 65
        reasons.append(f"High value: CHF {amount_cents / 100:,.2f} meets the configured review threshold")
    if not trusted:
        score += 40
        reasons.append("Beneficiary is not on the trusted synthetic-recipient list")
    if velocity_count > rules["velocity_limit"]:
        score += 55
        reasons.append(f"Velocity: {velocity_count} payment requests in ten minutes exceeds {rules['velocity_limit']}")
    return {"risk_score": min(score, 100), "flagged": bool(reasons), "reasons": reasons or ["Within configured amount, beneficiary and velocity limits"]}


def backtest(payload):
    rules = rule_validation(payload)
    # Ground-truth labels are fixed educational fixtures, not generated from the
    # selected thresholds. Legitimate exceptions and a subtle risky case make
    # false positives/negatives visible when analysts tune the rules.
    fixtures = [
        ("Routine utility payment", 24_000, True, 1, False),
        ("Regular rent", 250_000, True, 1, False),
        ("Small trusted purchase", 9_900, True, 2, False),
        ("Large payment requiring independent review", 3_200_000, True, 1, True),
        ("Unverified new beneficiary", 75_000, False, 1, True),
        ("Rapid repeated payment requests", 12_000, True, 6, True),
        ("Legitimate high-value invoice exception", 1_500_000, True, 1, False),
        ("Risky payment below default amount threshold", 900_000, True, 1, True),
    ]
    result = {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "cases": []}
    for name, amount, trusted, count, expected in fixtures:
        decision = evaluate(amount, trusted, count, rules)
        flagged = decision["flagged"]
        result["tp" if flagged and expected else "fp" if flagged else "fn" if expected else "tn"] += 1
        result["cases"].append({
            "name": name, "expected": expected, "flagged": flagged,
            "amount_cents": amount, "velocity_count": count, "trusted": trusted,
            "reasons": decision["reasons"],
        })
    result["precision"] = round(result["tp"] / max(result["tp"] + result["fp"], 1), 4)
    result["recall"] = round(result["tp"] / max(result["tp"] + result["fn"], 1), 4)
    return result


def identifier(state, prefix):
    state["sequence"] += 1
    return f"{prefix}-{state['sequence']:06d}"


def event(state, kind, title, detail, user_id, severity="info", technique="—"):
    state["events"].insert(0, {
        "id": identifier(state, "EVT"), "time": now(), "type": kind,
        "title": title, "detail": detail, "severity": severity,
        "user_id": user_id, "technique": technique,
    })
    state["events"] = state["events"][:500]


def ledger_entry(state, transfer, account_id, amount, timestamp):
    state["ledger"].insert(0, {
        "id": identifier(state, "LED"), "transfer_id": transfer["id"],
        "account_id": account_id, "amount_cents": amount, "posted_at": timestamp,
    })


def transfer(state, payload, actor):
    require_role(actor, "customer", "admin")
    if not isinstance(payload, dict) or set(payload) != {"from_account", "beneficiary_id", "amount", "reference", "idempotency_key"}:
        raise ValueError("Specify account, beneficiary, amount, reference and idempotency key")
    if not isinstance(payload["idempotency_key"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", payload["idempotency_key"]):
        raise ValueError("Provide an 8–80 character idempotency key")
    amount = money(payload["amount"])
    reference = text(payload["reference"], "Payment reference")
    normalized = {"from_account": payload["from_account"], "beneficiary_id": payload["beneficiary_id"], "amount_cents": amount, "reference": reference}
    fingerprint = hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()
    key = f"{actor['id']}:{payload['idempotency_key']}"
    previous = state["receipts"].get(key)
    if previous:
        if previous["fingerprint"] != fingerprint:
            raise ValueError("Idempotency key was already used for a different payment")
        receipt = copy.deepcopy(previous["result"])
        receipt["replayed"] = True
        return receipt
    source = next((account for account in state["accounts"] if account["id"] == payload["from_account"]), None)
    if not source or source["owner_id"] != actor["id"]:
        raise PermissionError("You may transfer only from your own accounts")
    if source["status"] != "active":
        raise ValueError("This account is not active")
    beneficiary = next((item for item in state["beneficiaries"] if item["id"] == payload["beneficiary_id"]), None)
    if not beneficiary:
        raise ValueError("Unknown synthetic beneficiary")
    destination = next(account for account in state["accounts"] if account["id"] == beneficiary["account_id"])
    if source["id"] == destination["id"]:
        raise ValueError("Source and destination must differ")
    if source["balance_cents"] < amount:
        raise ValueError("Insufficient available funds")
    if len(state["transfers"]) >= MAX_TRANSFERS:
        raise ValueError("This demonstration has reached its 1,000-payment limit; archive it and start a new workspace")
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    velocity = 1 + sum(item["created_by"] == actor["id"] and datetime.fromisoformat(item["created_at"]) >= cutoff for item in state["transfers"])
    assessment = evaluate(amount, beneficiary["trusted"], velocity, state["rules"])
    timestamp = now()
    payment = {
        "id": identifier(state, "PAY"), "from_account": source["id"],
        "to_account": destination["id"], "beneficiary_name": beneficiary["name"],
        "amount_cents": amount, "reference": reference,
        "status": "pending_review" if assessment["flagged"] else "settled",
        "risk_score": assessment["risk_score"], "reasons": assessment["reasons"],
        "created_at": timestamp, "created_by": actor["id"], "approved_by": None,
    }
    source["balance_cents"] -= amount
    ledger_entry(state, payment, source["id"], -amount, timestamp)
    if payment["status"] == "settled":
        destination["balance_cents"] += amount
        ledger_entry(state, payment, destination["id"], amount, timestamp)
    else:
        state["cases"].insert(0, {
            "id": identifier(state, "CASE"), "transfer_id": payment["id"],
            "status": "pending_review",
            "timeline": [{"at": timestamp, "action": "held_for_review", "by": actor["id"], "detail": "; ".join(payment["reasons"])}],
        })
    state["transfers"].insert(0, payment)
    event(state, "payment.held" if assessment["flagged"] else "payment.settled", "Payment held for independent review" if assessment["flagged"] else "Payment settled", f"{payment['id']} · {reference}", actor["id"], "high" if assessment["flagged"] else "info", "T1565.001" if assessment["flagged"] else "—")
    result = {"title": "Payment awaiting approval" if assessment["flagged"] else "Payment completed", "summary": "Funds are reserved until a different operator reviews this payment." if assessment["flagged"] else "The synthetic recipient has been credited.", "transfer": copy.deepcopy(payment), "transfer_id": payment["id"], "replayed": False}
    state["receipts"][key] = {"fingerprint": fingerprint, "result": copy.deepcopy(result)}
    return result


def decision(state, payload, actor):
    require_role(actor, "operator", "admin")
    if not isinstance(payload, dict) or set(payload) != {"transfer_id", "decision", "note"}:
        raise ValueError("Specify transfer_id, decision and review note")
    if payload["decision"] not in {"approve", "reject"}:
        raise ValueError("Decision must be approve or reject")
    note = text(payload["note"], "Independent review note", 500)
    payment = next((item for item in state["transfers"] if item["id"] == payload["transfer_id"]), None)
    if not payment:
        raise ValueError("Unknown payment")
    if payment["created_by"] == actor["id"]:
        raise PermissionError("A different operator must review this payment; self-approval is forbidden")
    if payment["status"] != "pending_review":
        raise ValueError("This payment already has a final decision")
    timestamp = now()
    approved = payload["decision"] == "approve"
    account_id = payment["to_account"] if approved else payment["from_account"]
    recipient = next(account for account in state["accounts"] if account["id"] == account_id)
    recipient["balance_cents"] += payment["amount_cents"]
    ledger_entry(state, payment, account_id, payment["amount_cents"], timestamp)
    payment["status"] = "settled" if approved else "rejected"
    payment["approved_by"] = actor["id"]
    payment["review_note"] = note
    payment["reviewed_at"] = timestamp
    for case in state["cases"]:
        if case["transfer_id"] == payment["id"]:
            case["status"] = payment["status"]
            case["timeline"].append({"at": timestamp, "action": "approved" if approved else "rejected", "by": actor["id"], "detail": note})
    event(state, "payment.approved" if approved else "payment.rejected", "Independent payment decision", f"{payment['id']} · {payload['decision']} · {note}", actor["id"])
    return {"title": "Payment approved" if approved else "Payment rejected", "summary": "Recipient credited exactly once." if approved else "Reserved funds returned to the originating account.", "transfer": copy.deepcopy(payment), "transfer_id": payment["id"]}


def provision(state, payload, actor):
    require_role(actor, "admin")
    user_id = payload.get("user_id")
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id < 1:
        raise ValueError("User identifier must be a positive integer")
    name = text(payload.get("display_name"), "Display name", 80)
    if payload.get("role", "customer") not in {"operator", "customer", "admin"}:
        raise ValueError("Unknown user role")
    existing = [account["id"] for account in state["accounts"] if account["owner_id"] == user_id]
    if existing or payload.get("role") == "operator":
        return {"title": "Local user provisioned", "account_ids": existing}
    accounts = [
        {"id": f"ACC-{user_id:04d}-C", "owner_id": user_id, "label": "Private current", "kind": "current", "balance_cents": 2_500_000, "status": "active", "identifier": f"PB-DEMO-{user_id:04d}-CURRENT"},
        {"id": f"ACC-{user_id:04d}-S", "owner_id": user_id, "label": "Reserve savings", "kind": "savings", "balance_cents": 1_000_000, "status": "active", "identifier": f"PB-DEMO-{user_id:04d}-SAVINGS"},
    ]
    state["accounts"].extend(accounts)
    event(state, "customer.provisioned", "Synthetic customer workspace created", f"{name} · demonstration opening balances only", actor["id"])
    return {"title": "Local user provisioned", "account_ids": [account["id"] for account in accounts]}


def apply(state, action, payload, actor):
    if action == "transfer":
        result = transfer(state, payload, actor)
    elif action == "decision":
        result = decision(state, payload, actor)
    elif action == "rules":
        require_role(actor, "admin")
        rules = rule_validation(payload)
        state["rules"] = rules
        event(state, "rules.updated", "Payment controls updated", f"High-value threshold CHF {rules['high_value_cents'] / 100:,.2f}; velocity limit {rules['velocity_limit']}", actor["id"])
        result = {"title": "Payment policy saved", "summary": "New payments use this policy; existing held payments still require review.", "rules": copy.deepcopy(rules)}
    elif action == "provision":
        result = provision(state, payload, actor)
    elif action == "security_event":
        require_role(actor, "system")
        kind = text(payload.get("type"), "Event type", 80)
        detail = text(payload.get("detail"), "Event detail", 500)
        user_id = payload.get("user_id", 0)
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id < 0:
            raise ValueError("Invalid event user identifier")
        event(state, kind, kind.replace(".", " ").title(), detail, user_id, "medium" if "fail" in kind else "info")
        result = {"title": "Security event recorded"}
    else:
        raise ValueError("Unknown banking operation")
    state["as_of"] = now()
    return result


def view(state, actor):
    require_role(actor, "customer", "operator", "admin")
    result = copy.deepcopy(state)
    owned = {account["id"] for account in result["accounts"] if account["owner_id"] == actor["id"]}
    result["accounts"] = [account for account in result["accounts"] if account["id"] in owned]
    result.pop("receipts", None)
    if actor["role"] == "customer":
        result["transfers"] = [payment for payment in result["transfers"] if payment["from_account"] in owned or payment["to_account"] in owned]
        result["ledger"] = [entry for entry in result["ledger"] if entry["account_id"] in owned]
        visible_transfers = {payment["id"] for payment in result["transfers"]}
        result["cases"] = [case for case in result["cases"] if case["transfer_id"] in visible_transfers]
        result["events"] = []
    result["summary"] = {
        "available_cents": sum(account["balance_cents"] for account in result["accounts"]),
        "reserved_cents": sum(payment["amount_cents"] for payment in state["transfers"] if payment["from_account"] in owned and payment["status"] == "pending_review"),
        "pending_count": sum(payment["status"] == "pending_review" for payment in result["transfers"]),
    }
    return result


def initial_state():
    timestamp = now()
    state = {
        "schema": 3, "bank": "Portbug Bank", "author": "Vaibhav Thakur", "currency": "CHF",
        "as_of": timestamp, "seeded_at": timestamp, "sequence": 0,
        "accounts": [
            {"id": "ACC-0001-C", "owner_id": 1, "label": "Private current", "kind": "current", "balance_cents": 14_770_075, "status": "active", "identifier": "PB-DEMO-0001-CURRENT"},
            {"id": "ACC-0001-S", "owner_id": 1, "label": "Reserve savings", "kind": "savings", "balance_cents": 8_500_000, "status": "active", "identifier": "PB-DEMO-0001-SAVINGS"},
            {"id": "DEMO-RECIPIENT-01", "owner_id": 0, "label": "Alpine Living Demo", "kind": "recipient", "balance_cents": 1_000_000, "status": "active", "identifier": "PB-DEMO-RECIPIENT-01"},
            {"id": "DEMO-RECIPIENT-02", "owner_id": 0, "label": "Limmat Energy Demo", "kind": "recipient", "balance_cents": 1_000_000, "status": "active", "identifier": "PB-DEMO-RECIPIENT-02"},
            {"id": "DEMO-RECIPIENT-03", "owner_id": 0, "label": "New Recipient Demo", "kind": "recipient", "balance_cents": 1_000_000, "status": "active", "identifier": "PB-DEMO-RECIPIENT-03"},
        ],
        "beneficiaries": [
            {"id": "BEN-ALPINE", "name": "Alpine Living Demo", "account_id": "DEMO-RECIPIENT-01", "country": "CH", "trusted": True},
            {"id": "BEN-LIMMAT", "name": "Limmat Energy Demo", "account_id": "DEMO-RECIPIENT-02", "country": "CH", "trusted": True},
            {"id": "BEN-NEW", "name": "New Recipient Demo", "account_id": "DEMO-RECIPIENT-03", "country": "CH", "trusted": False},
        ],
        "transfers": [], "ledger": [], "events": [], "cases": [], "receipts": {},
        "rules": {"high_value_cents": 1_000_000, "velocity_limit": 3},
    }
    # Seed balanced historical entries so the bank home has reviewable history.
    # These are explicitly synthetic opening fixtures, not measured activity.
    for days, cents, beneficiary_id, reference in (
        (12, 325_000, "BEN-ALPINE", "Synthetic residence invoice"),
        (8, 125_000, "BEN-ALPINE", "Synthetic quarterly service"),
        (3, 35_000, "BEN-LIMMAT", "Synthetic energy invoice"),
    ):
        beneficiary = next(item for item in state["beneficiaries"] if item["id"] == beneficiary_id)
        posted_at = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        payment = {"id": identifier(state, "PAY"), "from_account": "ACC-0001-C", "to_account": beneficiary["account_id"], "beneficiary_name": beneficiary["name"], "amount_cents": cents, "reference": reference, "status": "settled", "risk_score": 0, "reasons": ["Synthetic opening-history fixture"], "created_at": posted_at, "created_by": 1, "approved_by": None}
        state["accounts"][0]["balance_cents"] -= cents
        next(account for account in state["accounts"] if account["id"] == payment["to_account"])["balance_cents"] += cents
        state["transfers"].insert(0, payment)
        ledger_entry(state, payment, payment["from_account"], -cents, posted_at)
        ledger_entry(state, payment, payment["to_account"], cents, posted_at)
    event(state, "workspace.initialized", "Synthetic banking workspace ready", "Opening balances and three balanced historical payment fixtures created", 1)
    return state
