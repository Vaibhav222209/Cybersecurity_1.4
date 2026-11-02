# Contributing

This is **Portbug Bank Cyber Defense Center, made by Vaibhav Thakur**. Read [AGENTS.md](AGENTS.md), [architecture](docs/architecture.md), and [security policy](SECURITY.md) before changing the project.

Use Python 3.12+ standard-library code and local HTML/CSS/JavaScript. Keep startup independent of Make, npm packages, cloud services, and real credentials. Maintain Windows-friendly paths and explicit LF output when generating text fixtures.

## Checks

```sh
python3 -m unittest discover -s tests -v
python3 tools/check.py
node --check portbug/static/app.js
git diff --check
```

On Windows, replace `python3` with an installed supported launcher such as `py -3.12`; Node is needed only for the JavaScript syntax check. Do not claim a browser test, scanner, CI job, or restore rehearsal passed unless it was actually executed.

## Review requirements

- Use synthetic inputs and reserved example network addresses only. No real IBANs, payment endpoints, credentials, customer names, or host telemetry.
- Give every detection meaningful positive and negative tests. Explain thresholds, technique references, expected false positives, and data-source requirements.
- Keep fraud decisions advisory and explainable. Bound inputs, reject invalid data, and preserve ordered incident transitions.
- Validate request boundaries and persist state/audit changes consistently. A control should fail closed without pretending unavailable dependencies are healthy.
- Treat UI labels as claims: mark implemented behavior, modeled scenarios, and planned production controls accurately.
- Preserve author attribution and MIT terms. Use conventional commits such as `fix: reject invalid incident transitions`.
- Keep `.local/`, keys, databases, exports, and backups out of version control. Inspect the staged diff before committing.

Document behavior changes and remaining risks with the same care as implementation. Never suppress a finding solely to make a demonstration appear advanced.
