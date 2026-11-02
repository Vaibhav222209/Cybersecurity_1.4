# Local infrastructure — Phase 2 planned

`docker-compose.yml` will define the `dmz`, `app`, `data`, and `mgmt` networks, internal service attachments, loopback-only entry ports, resource limits, and health checks. Public images must be pinned to reviewed immutable digests. Local bootstrap must generate temporary secrets and certificates outside version control.

Planned service configurations live under [nginx](nginx/README.md), [modsecurity](modsecurity/README.md), [keycloak](keycloak/README.md), and [vault](vault/README.md). There are no service manifests in Phase 1; `make up` deliberately fails until startup and functional requests have been verified. See the [architecture](../docs/architecture.md).
