"""Dependency-free source, documentation, and repository hygiene checks.

This is a focused project check, not a replacement for a professional scanner.
"""

import ast
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".local", ".venv", "__pycache__", "backups", "artifacts"}
TEXT = {".py", ".md", ".html", ".css", ".js", ".yaml", ".yml", ".csv"}
LINKS = re.compile(r"\[[^\]]+\]\(([^\s)]+)\)")
FORBIDDEN = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
)


def main():
    errors = []
    for path in sorted(ROOT.rglob("*")):
        if any(part in EXCLUDED for part in path.relative_to(ROOT).parts) or not path.is_file():
            continue
        if path.suffix not in TEXT and path.name not in {"LICENSE", "Dockerfile", ".gitattributes", ".gitignore", ".dockerignore"}:
            continue
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        name = path.relative_to(ROOT)
        if b"\r" in raw or not raw.endswith(b"\n"):
            errors.append(f"{name}: use LF and a final newline")
        if any(line != line.rstrip() for line in text.splitlines()):
            errors.append(f"{name}: trailing whitespace")
        if any(pattern.search(text) for pattern in FORBIDDEN):
            errors.append(f"{name}: possible secret material")
        if path.suffix == ".py":
            try:
                ast.parse(text, filename=str(name), feature_version=(3, 12))
            except SyntaxError as exc:
                errors.append(f"{name}: {exc}")
        if path.suffix == ".md":
            if sum(line.startswith("```") for line in text.splitlines()) % 2:
                errors.append(f"{name}: unbalanced code fences")
            for target in LINKS.findall(text):
                if ":" not in target and not target.startswith("#"):
                    local = (path.parent / target.split("#")[0]).resolve()
                    if not local.is_relative_to(ROOT) or not local.exists():
                        errors.append(f"{name}: broken local link {target}")
    register = ROOT / "docs/control-register.csv"
    if register.exists():
        with register.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows or any(None in row or any(value is None or not value.strip() for value in row.values()) for row in rows):
            errors.append("control-register.csv: empty or malformed rows")
    if errors:
        print("\n".join(errors))
        return 1
    print("Source syntax, text hygiene, documentation links, control register and focused secret-pattern checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
