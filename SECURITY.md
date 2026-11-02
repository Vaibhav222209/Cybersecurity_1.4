# Security policy

Portbug Bank is fictional. This local defensive exercise is made by Vaibhav Thakur and must not receive real banking credentials, account details, customer records, or production secrets.

## Safe reporting

For non-sensitive defects, open a GitHub issue with the affected commit, operating system/Python version, expected behavior, observed behavior, and minimal synthetic reproduction. Do not attach `.local/`, database files, audit keys, personal information, browser session tokens, or screenshots containing secrets.

For a sensitive vulnerability, use GitHub's private vulnerability reporting option **if the repository owner has enabled it**. If it is unavailable, open a minimal issue asking for a private reporting channel without disclosing exploit details. No private-reporting feature or response SLA is implied by this file.

## Testing boundaries

Test only your own local copy with synthetic fixtures. Do not scan real banks, real customers, payment networks, or unrelated infrastructure. This repository contains no malware, working exploits, credential attacks, or live-target tooling. Scenario generation produces event records, not attack traffic.

## Deployment limits

- Bind the application to loopback; container port publications must also remain on loopback.
- The session token and same-origin checks are CSRF defenses, not authentication or enterprise RBAC.
- Local HTTP has no TLS; SQLite storage has no application-provided encryption.
- The audit key and database share a host trust domain. A host administrator can forge/rewrite history; chain validation is not immutability or non-repudiation.
- Response actions modify synthetic exercise state only. Production IAM, WAF, MFA, mTLS, SIEM, HSMs, and network segmentation are not deployed integrations.
- Swiss residency, banking authorization, and regulatory compliance are not attested.

Keep dependencies, base images, action pins, and host security reviewed. CI/static checks are evidence about the checks executed; they do not establish freedom from vulnerabilities. See the [threat model](docs/threat-model.md) and [control register](docs/control-register.csv) for remaining risks.
