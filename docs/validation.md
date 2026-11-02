# Banking rebuild validation

Made by Vaibhav Thakur · 2 November 2026.

The previous standalone dashboard was replaced by a banking application whose security controls govern actual local account and payment operations. Every balance, beneficiary and payment in these checks is synthetic.

| Check | Result in the development environment |
| --- | --- |
| Python 3.12.14 / Linux | 56 unit and integration tests passed |
| Authentication | Salted scrypt, hashed session tokens, idle/absolute expiration, logout invalidation, session-bound CSRF, throttled sign-in, and private public-user projections tested |
| TOTP | RFC 6238 vectors, confirmed enrollment, missing/incorrect code rejection, consumed-code replay rejection, attempt throttling, and revocation of other sessions tested |
| Payments | Ownership, integer cents, insufficient funds, idempotent retries, atomic failure, concurrent overspending prevention, and persisted funds-conservation invariants tested |
| Independent approval | Creator cannot decide their own payment; another authorized operator can approve once or reject/refund once; decision note and case history retained |
| Privacy and roles | Customer API responses exclude other customers' accounts and security history; privileged endpoints reject customer sessions; user/account creation rolls back together on audit failure |
| Detection workbench | Fixed-label fixtures produce true/false positives and negatives; precision and recall actually recompute from candidate rules; backtesting does not change balances or policy |
| Recovery | Database/key restoration retains balances, audit verification, identities and session records; wrong/tampered state fails verification |
| Browser | First setup, identity creation, payment confirmation, settlement, held-payment approval as a separate operator, backtest, evidence download, TOTP enrollment, keyboard dialogs, and 390px mobile navigation/logout exercised in Chromium |
| Session presentation | Logging out clears privileged rendered data and draft passwords; signing in as another role starts in the permitted workspace |
| Source checks | Python syntax, documentation links, LF endings, focused key-pattern checks, and JavaScript syntax checked |
| Optional Docker | Digest-pinned non-root/read-only container built and passed readiness; host access and authenticated banking operations checked separately from a listening port |

Screenshots in this repository capture the real running interface with synthetic data. No runtime database, credentials, session tokens, TOTP seeds or audit keys are included. The browser test uses temporary random passwords and an isolated workspace.

The Windows/Linux Python 3.12/3.14 CI matrix is configured. Native Windows and Python 3.14 results require completed remote CI evidence; they are not inferred from the local Linux run. These checks do not establish production banking readiness, regulatory compliance, hardware key protection, immutable logs or Swiss hosting.
