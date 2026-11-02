# Workflow design location

Phase 3 design notes and reusable scanner guidance belong here. Executable workflows must live in root `.github/workflows/` to run on GitHub. Pin actions to reviewed full commit SHAs, grant minimum permissions, and keep untrusted pull-request jobs separate from privileged signing/release jobs. No workflows or passing-CI badges exist yet.
