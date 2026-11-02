# Validation by phase

Run `make lint` and `make test` from the repository root with Python 3.12. Phase 1 uses only the standard library: the linter checks required files, local link targets (not URL availability or fragments), whitespace, balanced fenced blocks, Python syntax, JSON syntax, and private-key headers. The tests include deliberately broken fixtures so failures are observable. They also check the actual repository tree.

These checks do not replace a full secrets scan, Mermaid rendering, legal source review, application tests, or scanner findings. Later phases must add API/security tests, Compose startup and functional requests, actual scanner execution, rule positive/negative fixtures, fraud evaluation, and backup/restore and failure tests. Record failed, skipped, and unrun checks distinctly.
