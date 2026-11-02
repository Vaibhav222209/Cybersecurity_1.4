# Portbug Bank · Secure Digital Banking

Made by Vaibhav Thakur. Portbug Bank is a fictional Zurich bank. The user selected a banking application with security controls and authorized replacing the entire current tree and pushing it to the existing GitHub repository. Preserve Git history and unrelated user changes; do not force-push.

Build implemented banking workflows, not decorative controls. Local authentication, role/ownership checks, synthetic CHF transfers, independent payment approval, rule backtesting, event investigation, and verified recovery should produce testable evidence. Preserve integer-cent balances, idempotent receipts, and total funds across balances and pending reservations. Label synthetic funds and modeled bank infrastructure. Do not claim production security integrations, banking compliance, or Swiss residency.

Python 3.12+ standard library; no Make/npm/runtime packages required. Windows `py -m portbug`; Linux/macOS `python3 -m portbug`. Plain local HTML/CSS/JavaScript. Use no external API, fonts, telemetry, exploits, real banking data, or committed credentials. First-run local account setup accepts operator-chosen passwords; never ship default credentials. Generated state and keys remain in ignored `.local-banking/`.

Run `python3 -m unittest discover -s tests -v`, `python3 tools/check.py`, `node --check portbug/static/app.js`, actual HTTP tests and browser workflows. Test successful and rejected operations, cross-role access, self-approval rejection, retained decision history, trusted-key audit verification, and backup restoration. Record unrun native platform/CI checks accurately.

Use this isolated checkout without worktrees. Coordinate module contracts across parallel work. Conventional commits, clean diffs, no committed runtime files. The user has explicitly authorized publication of this rebuild to their repository.
