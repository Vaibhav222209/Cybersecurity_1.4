"""Focused repository hygiene checks, not a full security scanner."""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT = {".py", ".md", ".html", ".css", ".js", ".yaml", ".yml"}
LINK = re.compile(r"\[[^\]]+\]\(([^\s)]+)\)")
KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")


def main():
    errors = []
    required = ("README.md", "LICENSE", "AGENTS.md", "portbug/model.py", "portbug/auth.py", "portbug/server.py", "portbug/static/index.html", "portbug/static/app.js", "portbug/static/style.css")
    for name in required:
        if not (ROOT / name).is_file():
            errors.append(f"Missing required file: {name}")
    for path in sorted(ROOT.rglob("*")):
        parts = path.relative_to(ROOT).parts
        if any(part.startswith(".local") or part in {".git", ".venv", "__pycache__", "backups", "artifacts"} for part in parts) or not path.is_file():
            continue
        if path.suffix not in TEXT and path.name not in {"Dockerfile", "LICENSE", ".gitignore", ".gitattributes", ".dockerignore"}:
            continue
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        name = path.relative_to(ROOT)
        if b"\r" in raw or not raw.endswith(b"\n"):
            errors.append(f"{name}: use LF with a final newline")
        if any(line != line.rstrip() for line in text.splitlines()):
            errors.append(f"{name}: trailing whitespace")
        if KEY.search(text):
            errors.append(f"{name}: possible private key")
        if path.suffix == ".py":
            try:
                ast.parse(text, filename=str(name), feature_version=(3, 12))
            except SyntaxError as exc:
                errors.append(f"{name}: {exc}")
        if path.suffix == ".md":
            for target in LINK.findall(text):
                if ":" in target or target.startswith("#"):
                    continue
                local = (path.parent / target.split("#")[0]).resolve()
                if not local.is_relative_to(ROOT) or not local.exists():
                    errors.append(f"{name}: broken link {target}")
    if errors:
        print("\n".join(errors))
        return 1
    print("Repository syntax, links, text hygiene, and focused key-pattern checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
