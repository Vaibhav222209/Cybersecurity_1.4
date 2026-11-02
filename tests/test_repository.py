"""Exercise scaffold lint failures as well as the real documentation tree."""

import tempfile
import unittest
from pathlib import Path

from tools.check_repository import REQUIRED, check_repository


class RepositoryChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in REQUIRED:
            self.write(name, "# Fixture\n" if name.endswith(".md") else "# fixture\n")

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def assert_error(self, text):
        self.assertTrue(any(text in error for error in check_repository(self.root)))

    def test_valid_scaffold(self):
        self.assertEqual(check_repository(self.root), [])

    def test_missing_required_document(self):
        (self.root / "docs/architecture.md").unlink()
        self.assert_error("required nonempty file missing")

    def test_empty_required_document(self):
        self.write("docs/architecture.md", "\n")
        self.assert_error("required nonempty file missing")

    def test_broken_relative_link(self):
        self.write("README.md", "[missing](docs/missing.md)\n")
        self.assert_error("broken local link")

    def test_valid_relative_and_external_links(self):
        self.write("README.md", "[doc](docs/architecture.md#zones) [ref](https://example.invalid/)\n")
        self.assertEqual(check_repository(self.root), [])

    def test_link_outside_checkout(self):
        self.write("README.md", "[outside](../outside.md)\n")
        self.assert_error("local link escapes repository")

    def test_whitespace_and_missing_newline(self):
        self.write("README.md", "bad  \nno newline")
        self.assert_error("trailing whitespace")
        self.assert_error("missing final newline")

    def test_crlf_line_endings_rejected(self):
        (self.root / "README.md").write_bytes(b"# Windows line endings\r\n")
        self.assert_error("use LF line endings")

    def test_unbalanced_fence(self):
        self.write("README.md", "```mermaid\nflowchart LR\n")
        self.assert_error("unbalanced code fences")

    def test_invalid_python_and_json(self):
        self.write("tools/invalid.py", "def broken(\n")
        self.write("config.json", "{invalid}\n")
        self.assert_error("invalid Python")
        self.assert_error("invalid JSON")

    def test_private_key_header(self):
        header = "-----BEGIN " + "PRIVATE KEY-----\n"
        self.write("README.md", header)
        self.assert_error("private key material is forbidden")

    def test_local_environment_file(self):
        self.write(".env", "EXAMPLE=local-only\n")
        self.assert_error("local environment file must not be in scaffold")

    def test_actual_repository(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(check_repository(root), [])


if __name__ == "__main__":
    unittest.main()
