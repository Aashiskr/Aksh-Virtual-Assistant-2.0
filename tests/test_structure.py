import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
IGNORED_PARTS = {
    ".git",
    ".gradle",
    ".venv",
    "archive",
    "build",
    "node_modules",
    "tmp",
    "venv",
}


class StructureTests(unittest.TestCase):
    def test_all_python_files_parse(self):
        files = [
            path
            for path in ROOT.rglob("*.py")
            if "__pycache__" not in path.parts
            and not IGNORED_PARTS.intersection(path.parts)
        ]
        for path in files:
            with self.subTest(path=path):
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))

    def test_modern_modules_are_task_sized(self):
        files = list((ROOT / "backend").rglob("*.py")) + list(
            (ROOT / "frontend" / "desktop").rglob("*.py")
        )
        oversized = {
            str(path.relative_to(ROOT)): len(path.read_text(encoding="utf-8").splitlines())
            for path in files
            if len(path.read_text(encoding="utf-8").splitlines()) > 300
        }
        self.assertEqual(oversized, {})

    def test_supported_runtime_does_not_import_legacy_tree(self):
        files = list((ROOT / "backend").rglob("*.py")) + list(
            (ROOT / "frontend" / "desktop").rglob("*.py")
        )
        forbidden = (
            "from Automation",
            "from Features",
            "from Speechtotext",
            "from TextToSpeech",
            "from Time_Operations",
            "aksh_core",
            "aksh_ui",
        )
        violations = {
            str(path.relative_to(ROOT)): marker
            for path in files
            for marker in forbidden
            if marker in path.read_text(encoding="utf-8")
        }
        self.assertEqual(violations, {})


if __name__ == "__main__":
    unittest.main()
