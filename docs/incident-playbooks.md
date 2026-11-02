# Analyst playbooks

**Portbug Bank Cyber Defense Center — made by Vaibhav Thakur.** Every scenario and account is synthetic. Exercise actions change local state only. These playbooks demonstrate disciplined preparation; they are not authorization to operate on real systems.

## Common handling standard

1. **Validate:** inspect event provenance, timing, rule conditions, and contradictory benign evidence. A technique tag is a classification, not proof of compromise.
2. **Triage:** choose the alert and move it from open to investigating. Identify the affected synthetic asset and record the intended containment rationale in exercise notes/evidence.
3. **Contain:** advance only after triage. The console records a simulated containment state; real blocking or token revocation is outside this implementation.
4. **Recover and resolve:** confirm the exercise condition is understood, review residual risk, and resolve only after containment. Inspect the audit trail and export the evidence.
5. **Learn:** record false positives, missing telemetry, control gaps, and test cases for improved detections. Never delete inconvenient findings to make a dashboard look healthy.

## Credential abuse / suspicious geography

- Compare the local authentication pattern with the failed-login threshold, account history, event timing, and geography assumptions.
- Separate evidence of repeated failures from evidence of a successful unauthorized session. Impossible travel can reflect VPNs, shared identities, or imprecise location; treat it as an investigation signal.
- In production, approved responders would verify the identity owner, revoke affected sessions, rotate compromised factors, and preserve IdP evidence. Those integrations are planned, not executed by this demo.
- Exercise completion: a suspicious fixture produces the expected finding, a benign fixture does not, incident transitions are ordered, and audit verification remains valid.

## Suspicious payment-instruction change

- Inspect the synthetic payment, amount, destination change, velocity, and fraud explanation. Do not treat a risk score as a legal AML determination.
- Compare the change with an authorized approval chain. Demonstrate separation of duties in the exercise narrative and mark missing approval integrations as gaps.
- Production treatment would hold the affected instruction under approved authority, verify it through a trusted independent channel, and use dual control for release. The demo sends no payment and cannot hold real funds.
- Exercise completion: reason codes explain the finding, no score authorizes a payment, and the review decision is preserved in evidence.

## Unusual data export

- Validate the measured event volume, actor, sensitivity label, and export destination in the synthetic record.
- Check whether an approved operational activity explains the pattern. Preserve a bounded redacted record rather than copying an entire hypothetical dataset.
- Production containment would require authorized session/device restrictions and a legal/privacy assessment. Notification scope and deadlines require current primary-source review.
- Exercise completion: expected threshold behavior is reproducible; external destinations are not contacted; the investigation and response sequence is auditable.

## Privileged role or access change

- Compare the synthetic role change with an approved request, expected administrator, and separate customer/operator permissions.
- Investigate who requested, approved, and applied the change; a shared privileged identity prevents reliable attribution.
- A production response would revert unauthorized grants using controlled access, revoke affected sessions, and review related changes. The local workflow does not administer Keycloak, Active Directory, or another real IAM system.
- Exercise completion: the privileged-change fixture is detected, routine authorized behavior remains distinguishable, and the control register records the missing production enforcement.

## Availability, integrity, and ransomware tabletop

- Use a controlled stop/restart or isolated recovery copy to model outage response. Do not run malware, encrypt files as an attack, or disrupt the host.
- If audit verification fails, preserve the affected data directory and compare against independent prior evidence. Do not generate a replacement key and present the new chain as the original.
- Rehearse the [backup/restore procedure](operations.md) into a new directory. Verify state invariants and the matching audit key, measure restoration time, and record data loss relative to the backup point.
- Production resilience requires separate fault domains, protected recovery credentials, immutable/offline backups, and rehearsed business continuity. A single-machine demo cannot establish those properties.

## Communications and escalation tabletop

Assign fictional roles for incident commander, security analyst, business owner, privacy/legal reviewer, and communications lead. Use synthetic notices with no real recipient addresses. Determine incident scope and applicable reporting duties from verified sources; do not assume every demo alert triggers the Swiss 24-hour reporting duty. This project sends no external messages or regulatory reports.
