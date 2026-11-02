# Secrets and key management plan

Phase 2 will document local initialization/unseal, scoped service authentication, short-lived credentials, test CA issuance, and key rotation. Bootstrap secrets must remain outside Git. A local software Vault is not an HSM and does not provide hardware-backed key protection; any HSM-style demonstration must be labeled an approximation. Test denial of unauthorized secret access and recovery before relying on the service.
