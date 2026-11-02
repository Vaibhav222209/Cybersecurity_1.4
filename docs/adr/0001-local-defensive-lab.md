# ADR 0001: Local, synthetic defensive banking lab

- Date: 2026-11-02
- Status: Accepted for the proposed architecture; runtime controls remain unimplemented in Phase 1.
- Project: `portburg-secure-bank`

## Context

Portburg Bank is a fictional private bank headquartered in Zurich. The project demonstrates defensive security engineering and security documentation. It must be reproducible without a cloud account, contain no real credentials or personal data, and be safe to publish as a portfolio. The existing GitHub repository is `Vaibhav222209/Cybersecurity_1.4`; the project name does not require renaming its remote or checkout.

The initial checkout is an empty repository on the local `work` branch. Phase 1 creates its first commit in that existing checkout. Changing branches, creating worktrees, pushing, and publishing are outside this phase. Each cloud task already has an isolated checkout; future tasks should use it and create a worktree only at the user's explicit request.

## Decision

### Run locally with explicit trust boundaries

Use Docker Compose as the eventual application runtime, with the `dmz`, `app`, `data`, and `mgmt` zones described in the [architecture](../architecture.md). Only the intended local ingress endpoint should be published to loopback. Management services must not become public interfaces. No externally hosted identity, analytics, telemetry, or paid service is required.

Use Python 3.12 for repository tooling and the planned API, synthetic event generation, and fraud analysis. Prefer the standard library for Phase 1 checks. Future application dependencies, scanner versions, image digests, artifact integrity checks, and SBOM generation belong to the phases that introduce those artifacts. Do not install unpinned components merely to make the scaffold appear complete.

### Keep every scenario synthetic and defensive

Use names explicitly identified as invented, reserved documentation IP ranges, and opaque non-routable account identifiers such as `PB-DEMO-ACCOUNT-0001`. Do not generate banking identifiers that could accidentally resolve to an actual account. If future UI examples resemble IBANs, label them invalid fixtures and test that the application cannot send payments to a banking network.

All events, transactions, payment changes, phishing-awareness examples, and incident exercises are synthetic. No credentials, real keys, customer records, malware, working exploits, live-target scans, or attack tooling are permitted. The pentest-lab directory will hold defensive checklists and reports against this demo application only.

Document configuration names and non-secret defaults in `.env.example`. Runtime credentials and private key material must be generated locally in ignored storage or held in the planned secret manager. Never commit them, include them in saved setup scripts, or send them to an external API. A local Vault instance is a secret-management demonstration, not an HSM or a production key-custody service.

### Treat Swiss residency as a deployment assumption

The fictional design assumes that the host, persistent volumes, encrypted backups, and any authorized operator access remain within Switzerland. A local laptop or this cloud editing environment is not evidence of Swiss residency. No actual residency, financial-service authorization, banking compliance, certification, or production suitability is claimed.

Before any future deployment claims residency, record and verify the location of the host and storage, backup destinations, log exports, support access, and dependency/telemetry behavior. Installing public packages can contact external registries; that does not authorize sending application data to those registries. The lab must be able to operate with application-service egress denied after required images and dependencies are present.

### Separate plans from demonstrated controls

Phase 1 provides documentation and scaffold checks only. TLS 1.3, service mTLS, MFA, WAF filtering, encryption at rest, fraud decisions, monitoring, backups, and supply-chain signing are design requirements until their implementations and tests exist. Compose networks provide coarse network separation; they do not alone enforce a deny-by-default egress policy or zero trust.

Framework references express intended control mappings, not legal advice or compliance assertions. Phase 6 must verify primary-source versions, effective dates, scope, and applicability. In particular, do not treat the requested PCI DSS 4.0 baseline as proof of the current revision, assume DORA applies directly to a Swiss fictional bank, or assert that every cybersecurity incident triggers the Swiss 24-hour reporting duty.

## Alternatives considered

| Alternative | Reason for this decision |
| --- | --- |
| Cloud-managed identity, SIEM, or key management | Would add credentials, cost, residency dependencies, and a cloud-account requirement. |
| Realistic production/customer datasets | Unnecessary for demonstrable controls and incompatible with the synthetic-data requirement. |
| Deploying all services in Phase 1 | Would bypass the requested phase gates and prevent focused review of architecture and threats. |
| Static claims that controls are already effective | Documentation needs implementation and test evidence before those claims can be made. |

## Consequences and review triggers

The local stack will require sufficient host resources, local certificate bootstrap, secret lifecycle procedures, and a clear distinction between host controls and container controls. A single host cannot demonstrate production fault-domain independence or hardware-backed key isolation. Future phases must document these limits and test failure paths.

Revisit this ADR before adding any external service, real payment integration, production identity, persistent real data, publicly exposed endpoint, changed residency claim, or alternative deployment platform. Such a change requires explicit scope review; it is not an implied extension of this defensive lab.
