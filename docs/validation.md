# Rebuild validation record

Portbug Bank Cyber Defense Center · Made by Vaibhav Thakur · 2 November 2026.

The rebuilt source was checked in the development environment before publication. These observations are about this local synthetic demonstration, not a security assessment of a real bank.

| Check | Observed result |
| --- | --- |
| Python 3.12.14 / Linux, `python3 -m unittest discover -s tests -v` | 34 tests passed, including actual HTTP requests and SQLite operations |
| Detection and fraud behavior | All five rule families tested against matching/nonmatching fixtures; boundary and malformed inputs tested; weighted fraud reasons checked |
| Incident response | Ordered triage, containment, resolution accepted; skipped/repeated transitions rejected |
| Local HTTP controls | Valid writes accepted; foreign Host/Origin, missing/malformed CSRF, oversized/malformed bodies, unknown fields, rate excess and file traversal rejected |
| Audit and persistence | Restart persistence, concurrent updates, modified audit/state, wrong key, and malformed saved JSON exercised; integrity failures detected |
| Recovery | SQLite backup restored into a separate temporary directory with the matching key; restored state and chain matched, then accepted a new mutation |
| Source hygiene | Python syntax, local documentation links, LF endings, CSV structure and focused secret-pattern checks passed with `python3 tools/check.py` |
| JavaScript | `node --check portbug/static/app.js` passed |
| Chromium browser | All six views, scenario execution, ordered incident actions, evidence download, keyboard dialog/focus behavior, and 390px mobile layout passed; no JavaScript/CSP console errors observed |
| Docker Compose | Digest-pinned image built; non-root/read-only container passed health checks; host browser loaded the loopback publication and executed a payment scenario with a valid audit append |

The repository includes a Windows/Linux Python 3.12/3.14 CI matrix. Native Windows and Python 3.14 were not available for these local checks; inspect the completed GitHub Actions run before claiming those combinations pass. No production SAST/SCA/container-scanner assessment, external IAM/SIEM integration, independent audit, regulatory certification, or real incident-response capability is implied.

The README screenshot is a capture of the actual dashboard with synthetic initial state. Chart history and initial alerts are seeded illustrations. Response actions affect this demonstration only. Backup tests show consistent local recovery; they do not measure a production RTO or guarantee recovery after loss of the host and key.
