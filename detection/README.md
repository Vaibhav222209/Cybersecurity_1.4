# Detection engineering — Phase 4 planned

Combine a local [SIEM](wazuh-or-elk/README.md), [Sigma rules](sigma/README.md), and a [synthetic log generator](log-generator/README.md). Emit event fixtures locally; do not perform attacks to produce logs. Rules will cover authentication failures, impossible travel, privilege changes, unusual exports, and simulated payment-instruction changes.

Every rule requires at least one verified MITRE ATT&CK technique ID, a positive fixture, a negative fixture, field/schema checks, and a reproducible evaluation test. Document correlation windows, baselines, and false positives. No rules or detection coverage are implemented in Phase 1.
