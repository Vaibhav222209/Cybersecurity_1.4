# Security pipeline — Phase 3 planned

Phase 3 will wire SAST, dependency analysis, secrets scanning, Compose/IaC checks, container scanning, CycloneDX SBOM generation, OPA/Conftest policy, and local image-signing/verification demonstrations. Pin tools and inputs, retain machine-readable results, and make actionable findings fail the check. Keep narrow, justified, expiring exceptions visible.

The requested [workflow design directory](.github/workflows/README.md) is nested here for project organization. Active GitHub Actions must be installed at the repository root `.github/workflows/` in Phase 3: GitHub does not run nested workflow files. Avoid maintaining two executable copies. CI and scanner success have not been verified in Phase 1; `make scan` explicitly fails until implemented.

[Policy-as-code scope](policy-as-code/README.md).
