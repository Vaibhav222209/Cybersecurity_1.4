# Contributing to Portbug Bank

**Made by Vaibhav Thakur.** Keep contributions focused on a clear banking or security behavior and preserve the distinction between local demonstration evidence and production assurance.

## Development

Use the existing checkout with Python 3.12 or later. The runtime and tests use the standard library; the interface uses local HTML/CSS/JavaScript. Start with `py -m portbug` on Windows or `python3 -m portbug` on Linux/macOS. Use a separate `--data-dir` for experiments.

Before committing:

```sh
python3 -m unittest discover -s tests -v
python3 tools/check.py
node --check portbug/static/app.js
git diff --check
```

On Windows, replace `python3` with `py`. Node is needed only for the JavaScript syntax check. Changes to the interface also need browser checks for keyboard navigation, mobile layout, authentication/session changes, and the affected payment workflow.

## Financial and security invariants

- Store CHF money as integer cents and reject unsupported precision, negative amounts, and insufficient funds.
- Enforce account ownership and roles on the server, including direct API requests.
- Preserve total synthetic funds across balances and pending reservations.
- Make duplicate submissions safe through idempotency; reject reuse of a key with different payment contents.
- Prevent an instruction's author from approving it; require a reason-bearing decision and retain its history.
- Test accepted and rejected operations, atomic rollback, restart persistence, concurrency, and recovery.
- Do not weaken CSRF, session, password, TOTP, or audit validation to make a test pass.

Use invented identifiers and reserved documentation addresses. Never add real bank data, credentials, private keys, runtime databases, or external telemetry. Describe material limitations and unrun checks accurately. Use conventional commits such as `fix: reject duplicate payment decisions` and explain the concrete trigger, changed behavior, and validation in a pull request.
