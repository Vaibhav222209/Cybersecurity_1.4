# Operate and verify the local bank

**Portbug Bank · Made by Vaibhav Thakur.** These procedures use synthetic accounts and local demonstration funds.

## Startup

From the project folder, run `py -m portbug` on Windows or `python3 -m portbug` on Linux/macOS. Open `http://127.0.0.1:8080`; keep the terminal running and use Ctrl+C to stop. Python 3.12 or later is required. If needed, add `--port 8081` and use the corresponding browser address.

The default state directory is `.local-banking/`. To start an independent exercise, pass `--data-dir .local-banking/exercise-two`. The former dashboard's `.local/` database is a different schema and must not be copied over the banking database. A fresh directory is the supported way to start a new demonstration.

Optional Docker startup is `docker compose up --build`; stop with `docker compose down`. Publish only to host loopback. Inspect persistent volumes before deleting them: removing the banking volume removes local accounts, passwords, enrollment state, and payment history.

## First-run account setup

Create the first administrator through the local setup screen. Choose a new demonstration password of at least 12 characters; no default account/password is supplied. Record the username privately. The administrator's synthetic starter funds are exercise data, not a connection to a real account.

Use administration to create additional customer/operator accounts. An operator account is useful for independent payment review. Give each account its own password and use separate browser profiles or explicit logout/login when testing role boundaries. Do not use real customer details or real bank passwords.

## Authenticator enrollment

Personal security settings support optional TOTP. Enter the displayed enrollment key into a compatible authenticator, then confirm a current code before relying on the enrollment. The key is displayed only for your local enrollment workflow; do not include it in screenshots, issues, logs, or Git. Keep the computer and authenticator clocks synchronized.

Do not enable an authenticator you cannot retain access to. This demonstration does not promise an enterprise recovery process or independent identity-proofing service. Protect a verified local backup and document how you will recover the exercise before changing account-security settings.

## Payment review exercise

1. Sign in as the account owner and note the source balance.
2. Submit a small trusted-beneficiary instruction; verify settlement and the ledger entries.
3. Submit an instruction at/above the configured high-value threshold or exceeding the configured velocity threshold; inspect the hold and its reasons.
4. Verify the sender's available balance reflects the held amount while the synthetic recipient has not been credited.
5. Sign in as another authorized operator. Enter a decision note and approve or reject the held instruction.
6. Verify a single recipient credit after approval, or a single sender refund after rejection. Try repeating the decision and confirm it is refused.
7. Inspect the case timeline and evidence. A sender attempting to approve their own instruction must be refused even if that sender is an administrator.

Candidate rule backtests are read-only evaluations. Compare their false positives/negatives before changing active thresholds. A useful result on labeled fixtures is not a production detection-rate estimate.

## Backup and recovery

Stop the server before creating a recovery copy. The verified command includes the SQLite database and corresponding audit key; the destination must be a **new directory**.

```bat
:: Windows
py -m portbug --backup ..\portbug-bank-backup-01
```

```sh
# Linux / macOS
python3 -m portbug --backup ../portbug-bank-backup-01
```

For a non-default workspace, include `--data-dir` pointing to that workspace. The backup is sensitive and unencrypted: it contains local identity/password-verification material, authenticator state, and the audit key as well as synthetic financial history. Store it privately and outside the repository. Do not upload it as evidence.

To rehearse recovery, copy the backup to another new directory, retain the original, and start with `--data-dir` pointing to the recovery copy. Verify local account login, expected balances, held-payment statuses, ledger totals, audit count/head, and the ability to perform one permitted new operation. Record elapsed time and any missing changes. The backup cannot recover instructions accepted after its creation, and the demo promises no production RTO/RPO.

The audit chain depends on the matching key. Restoring a whole earlier database/key pair can be internally valid without proving that history was never rolled back; independent reference evidence is required for stronger assurance.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Make/npm is missing | Neither is required to run the bank; use the Python entrypoint. |
| `py` is unavailable or selects an older Python | Install Python 3.12+ and reopen the terminal; `py --list` lists Windows installations. |
| Port is occupied | Use another `--port`; do not terminate unrelated processes. |
| Login or authenticator code is rejected | Check the local username/password and time synchronization; do not disable verification. |
| A transfer is held | Read its reasons and use an independent operator for a reason-bearing decision. |
| A payment is rejected | Check account ownership, available funds, input precision, role, and current state. |
| A write reports a CSRF/session problem | Reload/sign in again through the same local origin. Do not bypass validation. |
| Audit verification fails | Preserve the data, stop banking mutations, investigate, and restore a verified copy. Do not silently generate a replacement key. |

## Production review boundary

The application is a local engineering project. A production Swiss-bank design requires separate work on verified TLS, hardware/independent key custody, identity proofing and recovery, protected network segments, fraud operations, independently retained evidence, resilient infrastructure, and legal applicability. Primary-source review would include FINMA guidance, Swiss data protection/banking secrecy, cyberattack reporting duties, and relevant international frameworks. No current-version legal review, certification, or Swiss hosting claim is made here.
