# Local operations and recovery

**Made by Vaibhav Thakur.** These procedures operate the fictional Portbug Bank exercise. Do not use real account records, customer details, tokens, or banking credentials.

## Startup and shutdown

From the repository root, run `py -3.12 -m portbug` on Windows or `python3 -m portbug` on Linux/macOS. Open `http://127.0.0.1:8080`. Keep that terminal running; stop with Ctrl+C. Use `--port 8081` if needed. Python 3.12 or later is supported; select the installed version explicitly when several are present.

State persists under ignored `.local/` by default. Use `--data-dir .local/exercise-two` to start a separate exercise without deleting an existing one. Treat each data directory and its generated audit key as one recovery unit. Do not share one directory between concurrent server instances.

`docker compose up --build` is an optional alternative. Stop with `docker compose down`. Inspect the Compose volume configuration before removing volumes; deleting a persistent volume deletes its exercise history. The container may listen on `0.0.0.0` internally, but the published host port must remain bound to `127.0.0.1`.

The container runs as a non-root user with a read-only root filesystem, dropped capabilities, resource limits, and a digest-pinned Python base image. Its single bridge network supports the loopback publication; it is not the bank's modeled four-zone segmentation or an outbound firewall. The application makes no external requests, but network-wide egress enforcement requires separate host controls.

## Routine exercise

1. Confirm the console is connected and its audit verification is valid.
2. Run a benign baseline scenario and review its expected non-alerting result.
3. Run one suspicious scenario. Inspect the generated observation, rule explanation, technique reference, and any fraud reasons.
4. Triage the new alert. Record the exercise decision; contain it, then resolve it in the permitted order.
5. Export evidence and inspect it before sharing. Exports contain synthetic observations and operational decisions, not the audit key.
6. Restart the application and confirm the exercise state and audit verification survive.

Response actions are local state changes. They do not revoke actual tokens, block an external host, stop a payment, or isolate a machine.

## Backup and restore

Stop the server and use the verified backup command, which uses SQLite's backup API and copies the matching audit key. The destination must be a **new directory**; it will not overwrite an existing backup. A failed integrity check refuses the backup.

```bat
:: Windows, from the project folder
py -3.12 -m portbug --data-dir .local --backup ..\portbug-backup-01
```

```sh
# Linux / macOS
python3 -m portbug --data-dir .local --backup ../portbug-backup-01
```

Keep the backup access-restricted. It contains the sensitive local verification key, and it is **not encrypted**. Do not commit it or assume ordinary file copies are protected. For a manual copy instead, stop the server first and copy the **entire data directory**; do not copy a live SQLite database piecemeal because acknowledged changes may still reside in its WAL files.

To rehearse recovery:

1. Export the exercise evidence and record the last observed audit count and chain head.
2. Stop the application. Create a verified backup in a new isolated directory with the command above.
3. Copy that backup to a new recovery directory; retain the original untouched.
4. Start the server with `--data-dir` pointing to the recovery directory, using another local port if necessary.
5. Confirm that the expected alerts, incident statuses, audit count/head, and chain verification match the prior observation.
6. Record elapsed recovery time and any missing events. A successful file copy alone is not restore evidence.

For example, test the Windows recovery copy with `py -3.12 -m portbug --data-dir ..\portbug-recovery-01 --port 8081`, then inspect `http://127.0.0.1:8081`. Use the corresponding forward-slash path and `python3` on Linux/macOS.

No production RTO/RPO is promised. For this exercise, use an explicit rehearsal target such as recovery within 10 minutes with no loss of acknowledged pre-backup state. Measure the actual result; a stopped-server backup cannot recover later changes. Losing the corresponding audit key invalidates the evidence-verification workflow.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `make` is not recognized | Make is unnecessary; use the Python commands in the README. |
| Requested Python version is missing | Run `py --list` on Windows, install a supported version, and reopen the terminal. |
| Address already in use | Stop your earlier instance or use `--port 8081`; do not terminate unrelated processes. |
| Console cannot connect | Confirm the server remains running and the browser uses the exact local address and port. |
| A write is rejected | Reload the page for a fresh session token; use the same origin, allowed scenario, and permitted incident transition. Do not disable checks. |
| Audit verification fails | Preserve a copy, stop the exercise, compare with a trusted backup/export, and investigate. Do not mark invalid evidence as valid or silently replace the key. |
| Local data must be reset | Stop the server and select a new `--data-dir`; archive the old directory if it matters. |

## Regulatory and framework review agenda

These are authoritative starting points for a future, separately scoped applicability review. They are not claims that the local exercise meets a regulation or that current versions have been legally verified.

| Topic | Primary source and question |
| --- | --- |
| FINMA | [FINMA documentation](https://www.finma.ch/en/documentation/): review Circular 2023/1, subsequent amendments and cyber-risk guidance against the actual institution's scope. |
| Swiss data protection and banking secrecy | [Fedlex](https://www.fedlex.admin.ch/en/) and [FDPIC](https://www.edoeb.admin.ch/en): verify current nFADP/nDSG provisions, Banking Act Article 47, access/retention duties, and applicability. |
| Cyberattack reporting | [Swiss Federal Office for Cyber Security](https://www.ncsc.admin.ch/ncsc/en/home.html): verify covered critical infrastructure, qualifying incidents, the 24-hour initial-report trigger, exceptions, and subsequent duties. Not every alert is reportable. |
| ISO/IEC 27001 | [ISO catalogue](https://www.iso.org/standards.html): confirm the 2022 edition, applicable amendments, and licensed Annex A control references. |
| NIST CSF | [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework): map CSF 2.0 outcomes and verify current supporting publications. |
| PCI DSS | [PCI SSC library](https://www.pcisecuritystandards.org/document_library/): verify card-data scope and the current revision; distinguish 4.0 from 4.0.1 and later revisions. |
| SWIFT CSP | [SWIFT Customer Security Programme](https://www.swift.com/myswift/customer-security-programme-csp): verify the current CSCF and architecture category only if actual SWIFT scope exists. |
| DORA | [EUR-Lex regulation](https://eur-lex.europa.eu/eli/reg/2022/2554/oj): review actual territorial/entity applicability and technical standards; a fictional Swiss bank is not automatically in scope. |

Document review dates, exact source editions/effective dates, applicability decisions, and implementation evidence before making a compliance claim. Do not reproduce licensed standard text in this repository.
