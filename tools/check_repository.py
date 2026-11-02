"""Lint the Phase 1 scaffold without installing external dependencies.

This is documentation validation, not a security scanner. It intentionally does
not fetch remote links or claim that documented controls are implemented.
"""

import ast
import json
import re
from pathlib import Path

REQUIRED = (
    "AGENTS.md",
    "README.md",
    "LICENSE",
    "Makefile",
    ".env.example",
    "docs/architecture.md",
    "docs/threat-model.md",
    "docs/adr/0001-local-defensive-lab.md",
    "docs/roadmap.md",
    "app/README.md",
    "infra/README.md",
    "devsecops/README.md",
    "detection/README.md",
    "fraud/README.md",
    "pentest-lab/README.md",
    "tests/test_repository.py",
)
IGNORED = {
    ".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".local", "artifacts", "backups", "build", "dist", "secrets",
}
LINK = re.compile(r"\[[^\]]*\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)")
PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")
TEXT_SUFFIXES = {".md", ".py", ".json", ".yml", ".yaml", ".csv", ".example"}


def check_repository(root: Path) -> list[str]:
    """Return actionable errors; keep the checkout unchanged."""
    root = root.resolve()
    errors = []
    for name in REQUIRED:
        path = root / name
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            errors.append(f"{name}: required nonempty file missing")

    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in IGNORED for part in relative.parts) or not path.is_file():
            continue
        name = str(relative)
        if path.name.startswith(".env") and path.name != ".env.example":
            errors.append(f"{name}: local environment file must not be in scaffold")
        if path.suffix not in TEXT_SUFFIXES and path.name not in {
            "LICENSE", "Makefile", ".gitignore",
        }:
            continue
        text = path.read_text(encoding="utf-8")
        if not text.endswith("\n"):
            errors.append(f"{name}: missing final newline")
        if "\r" in path.read_bytes().decode("utf-8"):
            errors.append(f"{name}: use LF line endings")
        for line_number, line in enumerate(text.splitlines(), 1):
            if line != line.rstrip():
                errors.append(f"{name}:{line_number}: trailing whitespace")
        if PRIVATE_KEY.search(text):
            errors.append(f"{name}: private key material is forbidden")
        if path.suffix == ".py":
            try:
                ast.parse(text, filename=name, feature_version=(3, 12))
            except SyntaxError as exc:
                errors.append(f"{name}: invalid Python: {exc.msg}")
        if path.suffix == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"{name}: invalid JSON: {exc.msg}")
        if path.suffix == ".md":
            fences = sum(line.startswith("```") for line in text.splitlines())
            if fences % 2:
                errors.append(f"{name}: unbalanced code fences")
            for target in LINK.findall(text):
                if ":" in target or target.startswith("#"):
                    continue
                local = target.split("#", 1)[0]
                destination = (path.parent / local).resolve()
                if not destination.is_relative_to(root):
                    errors.append(f"{name}: local link escapes repository: {target}")
                elif not destination.exists():
                    errors.append(f"{name}: broken local link: {target}")
    return errors


def main() -> int:
    errors = check_repository(Path(__file__).resolve().parents[1])
    if errors:
        print("\n".join(errors))
        return 1
    print("Scaffold checks passed: required files, local link targets, text, Python, JSON.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
