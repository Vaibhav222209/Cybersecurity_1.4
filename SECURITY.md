# Security policy

Portbug Bank is a fictional Zurich bank. This banking demonstration is **made by Vaibhav Thakur** and accepts synthetic funds, identities, beneficiaries, and instructions only.

## Reporting a defect

For ordinary defects, open an issue with the affected commit, operating system/Python version, expected result, and minimal synthetic reproduction. Do not upload a data directory, SQLite files, session cookies, password material, TOTP enrollment secrets, audit keys, or real personal/banking information.

For a sensitive vulnerability, use GitHub private vulnerability reporting if the repository owner has enabled it. Otherwise request a private contact channel without publishing exploit details. This file does not establish a reporting SLA or imply that a particular GitHub feature is enabled.

## Supported use

- Run the application on your own trusted machine and keep the listener on loopback.
- Choose new demonstration passwords. There are no shipped default logins.
- Use distinct local accounts to test customer, operator, and administrator boundaries.
- Exercise only this application's synthetic ledger. Do not target real banks, payment systems, or unrelated services.
- Keep generated databases, backups, keys, and authenticator secrets out of version control.

## Protection boundaries

The application implements local password authentication, optional TOTP, role/ownership validation, session/CSRF controls, rule-based review, independent payment decisions, and state-bound audit verification. Those controls do not turn the application into a licensed or production-ready bank.

Loopback HTTP has no TLS, so the local session cookie is not a production HTTPS deployment. SQLite, password hashes, pending/active TOTP material, sessions, and the audit key reside on the local host. File permissions and host disk encryption are operator responsibilities. A host administrator can inspect or replace those files and code. HMAC verification does not establish immutable or independently witnessed history, and authentication tables are outside the banking-state digest.

No production identity provider, WAF, HSM, external payment integration, protected multi-site recovery, or Swiss residency attestation is supplied. Review [the threat model](docs/threat-model.md) before changing exposure, identity boundaries, persistence, or payment behavior.
