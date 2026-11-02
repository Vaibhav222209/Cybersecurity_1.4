# Portbug Bank development conventions

Portbug Bank is a fictional Zurich bank. This is a local defensive cybersecurity simulation made by Vaibhav Thakur. Use synthetic records and reserved example addresses only. No malware, exploits, real payments, real credentials, or real customer data.

The user authorized a complete rebuild of the previous scaffold. Implement the runnable defense center, not the old phased project. Clearly separate implemented demo behavior from production requirements. Do not claim deployed MFA, WAF, HSMs, SIEM, Swiss residency, or regulatory compliance without evidence.

Use Python 3.12+ standard library for the local server and tests; plain HTML/CSS/JavaScript for the interface. No cloud account, npm installation, Make, or third-party runtime libraries should be needed. Keep Windows startup simple: `py -3.12 -m portbug`. Linux/macOS: `python3 -m portbug`.

Commands: `python3 -m unittest discover -s tests -v`, `python3 tools/check.py`, `node --check portbug/static/app.js`. Test meaningful success/failure behavior, preserve scanner findings, and never replace security evidence with status badges. Demo state, audit keys, and generated artifacts belong in ignored `.local/` or temporary directories. Do not commit secrets or runtime databases.

Use the existing isolated checkout; no worktrees unless requested. Review changes and use conventional commits. The user authorized pushing the rebuilt project to their existing GitHub repository. Preserve Git history, existing attribution, and unrelated user work; do not force-push.
