# Agent and contributor conventions

## Scope and safety

- This is `portburg-secure-bank`, a defensive portfolio for a **fictional** bank in Zurich. It is not banking software for production use.
- Use synthetic data only: invented names, non-routable account identifiers, and generated logs. Never use actual customer data, real credentials, malware, exploits, or live-target attack tooling.
- Use `.env.example` for variable documentation only. Do not commit `.env`, private keys, tokens, certificates with private material, or real identifiers. Future local secrets belong outside tracked files.
- The intended runtime is local Docker Compose. No cloud account or external security service is required. Do not send demo data to external APIs.
- Each cloud task already has an isolated checkout. Use it; do not create Git worktrees unless the user requests one.

## Workflow

1. Read `README.md`, the phase status, and applicable architecture decisions before making changes.
2. Work only on the requested phase. Record material assumptions in `docs/adr/`; distinguish implemented controls from proposed ones.
3. Python tooling targets Python 3.12. Use JSON/YAML for structured configuration; future dependencies and container images must be pinned and verified.
4. Run `make lint` and `make test`. For this documentation phase these check repository hygiene, local documentation links, and scaffold invariants using the standard library. Application and security validation must be added as those components land.
5. Review `git diff --check` and `git status`, then make a conventional commit such as `docs: scaffold bank security architecture`. Do not push or publish unless requested.

## Commands

```sh
make help       # available commands and phase boundaries
make lint       # documentation and file-hygiene checks
make test       # scaffold/documentation contract tests
```

`make up` and `make scan` intentionally fail with a phase-specific message until their real implementations land. Never replace required checks with an unconditional success, suppress findings, or claim CI is green without a completed run.

## Definition of done

For every phase: coherent documentation, passing applicable tests/linters, no secrets or real data, an explicit status/limitations update, and a conventional commit. Every implemented detection rule needs a test and MITRE ATT&CK technique ID. Every risk needs an owner, likelihood/impact, treatment, control, and documentation reference.

The final project additionally requires reproducible `make up`, `make test`, and `make scan`, verified CI, startup and functional smoke tests, scanner evidence, restore tests, and reviewed compliance references. Phase 1 alone does not satisfy those final requirements.
