# Delivery phases and validation gates

The requested scope is seven phases. Phase 1 is complete; Phases 2–7 are pending. This roadmap names intended capabilities, not deployed controls. See [ADR 0001](adr/0001-local-defensive-lab.md) for assumptions and [the threat model](threat-model.md) for security concerns.

For each phase: implement only the authorized scope, update the status and limitations, run the applicable tests and linters, inspect the diff for secrets or unintended outputs, make a conventional commit, and summarize the evidence. A failed or unrun required check must be reported; recording a future command does not count as executing it.

| Phase | Status | Deliverables | Required completion evidence |
| --- | --- | --- | --- |
| 1. Scaffold and design | Complete | Contributor conventions, README, MIT license, directory scaffold, architecture and trust boundaries, STRIDE threat model with conceptual attack trees, this roadmap, initial ADR, and documentation checks. | `make lint` and `make test` pass; relative documentation links resolve; no credentials or real data are committed; phase limits are clear; a conventional commit records the delivery. |
| 2. Application and infrastructure | Pending | Minimal FastAPI e-banking API using synthetic records; segmented Compose services; Nginx/OWASP CRS WAF; Keycloak SSO, MFA and RBAC; Vault; local TLS/mTLS bootstrap and ignored secret storage. | From a clean clone, `make up` starts required services; functional requests exercise authorized and rejected operations; verify JWT claims, object ownership, validation, rate limits, audit events, certificate trust, service isolation, and restart behavior. |
| 3. Security pipeline | Pending | SAST, dependency/SCA, secrets, IaC and container scanning; OPA/Conftest policy; pinned dependencies/images; CycloneDX SBOM; documented image signing and verification with cosign. | `make scan` runs real scanners and preserves their exit status; deliberately insecure fixtures are rejected where appropriate; applicable policy checks pass; SBOM and signature verification evidence belongs to current artifacts; CI completes successfully. |
| 4. Detection and response | Pending | Local SIEM configuration and dashboards; Sigma rules for brute force, impossible travel, privilege escalation, exfiltration signals and suspicious payment changes; synthetic log generator; ATT&CK coverage matrix; controlled account-lock and token-revocation helpers. | Every rule has a technique ID and positive/negative test; actual event ingestion and alert correlation are demonstrated; helpers default to dry run and act only on local fixtures; authorization, audit and false-positive behavior are tested. |
| 5. Fraud signals | Pending | Explainable velocity, geography and mule-pattern rules plus a simple ML model using deterministic synthetic training/evaluation data. | Unit and integration checks cover each signal and reason code, reproducibility, validation and representative benign cases; evaluate false positives and model limitations; no automatic real-world payment action or AML determination is claimed. |
| 6. Governance and resilience | Pending | Incident-response plan and five playbooks; access, crypto, logging, vendor-risk and BCP/DR policies; reviewed compliance mapping; owned risk register; backup/restore procedures; phishing awareness and tabletop exercises. | Every risk links to a control and existing document; primary-source framework version/applicability review is recorded; actual isolated backup/restore and service-failure tests validate stated RTO/RPO targets; playbook/tabletop evidence uses synthetic cases. |
| 7. Portfolio release polish | Pending | Verified status badges, ATT&CK coverage heatmap, local demo script, CONTRIBUTING guide, SECURITY policy, evidence index, and final documentation review. | Clean-clone quickstart, `make up`, `make test`, `make scan`, functional readiness, restore tests and CI pass; verify no committed secrets; validate every claimed capability against evidence. |

## Command contract

In Phase 1, `make lint` checks documentation/file hygiene and `make test` checks the scaffold contract. They do not validate application security. `make up` and `make scan` must fail explicitly until their implementations exist, so missing capabilities cannot be mistaken for passing checks.

Phase 2 must replace the startup gate with real Compose startup and functional readiness checks; a running PID or listening port is insufficient. Phase 3 must replace the scan gate with real scanners, pinned invocation versions, reviewed policy and useful output. All later phases extend `make test` with meaningful tests for their own capabilities. CI configuration intended to run on GitHub must be installed under the repository-root `.github/workflows/`; `devsecops/.github/workflows/` can document reusable source/templates but is not itself a GitHub Actions discovery location.

## Compliance source review planned for Phase 6

Use authoritative sources and record the retrieval date, exact document version, effective date, applicable scope, control mapping, and limits. Do not copy paywalled standard text into the repository or assert certification. Phase 1 does not verify the current legal or standards versions.

| Requested reference | Primary-source review and question |
| --- | --- |
| FINMA Circular 2023/1 and cyber-risk guidance | [FINMA documentation](https://www.finma.ch/en/documentation/) — confirm current circular text, subsequent amendments/guidance, intended institution scope, operational resilience and incident-reporting expectations. |
| Swiss nFADP/nDSG and Banking Act Article 47 | [Fedlex](https://www.fedlex.admin.ch/en/) and [FDPIC](https://www.edoeb.admin.ch/en) — verify current statutory text, secrecy/data-protection scope, and clearly separate simulated controls from legal compliance. |
| Swiss critical-infrastructure cyberattack reporting | [Federal Office for Cyber Security](https://www.ncsc.admin.ch/ncsc/en/home.html) — verify current authority naming, covered entities, qualifying cyberattacks, the 24-hour initial-report window, exceptions and follow-up duties. Do not generalize the duty to all events. |
| ISO/IEC 27001:2022 Annex A | [ISO standards catalogue](https://www.iso.org/standards.html) — confirm applicable edition/amendments and use control identifiers without reproducing licensed text. |
| NIST CSF 2.0 | [NIST CSF](https://www.nist.gov/cyberframework) — confirm current publications and map outcomes, including Govern, without implying certification. |
| PCI DSS 4.0 | [PCI SSC document library](https://www.pcisecuritystandards.org/document_library/) — distinguish the requested 4.0 baseline from 4.0.1 and any later current revision; confirm the simulated card-data scope before mapping. |
| SWIFT CSP | [SWIFT Customer Security Programme](https://www.swift.com/myswift/customer-security-programme-csp) — identify the current CSCF version and relevant architecture category; simulated payment records do not establish SWIFT connectivity or compliance. |
| EU DORA | [EUR-Lex](https://eur-lex.europa.eu/eli/reg/2022/2554/oj) — review the regulation and relevant technical standards as a reference; explain actual applicability rather than assuming a fictional Swiss bank is directly in scope. |

## Evidence boundaries

Docker Compose is a single-host teaching environment. Its successful execution does not prove Swiss residency, banking authorization, production resilience, hardware-backed cryptography, or regulatory compliance. Every later deliverable must state implemented behavior, remaining limits, and the tests actually executed. Phase 1 has no application stack, SIEM, ML model, scanners, signed images, or CI run to claim.
