# Policy as code plan

Phase 3 will use OPA/Conftest to reject privileged containers, broad port publications, mutable image tags, missing resource bounds, unsafe mounts, and incorrect network attachments. Each policy needs positive and negative fixtures. Do not equate static Compose checks with enforcement of runtime egress or service identity.
