import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "package_claude_skill.py"
SKILL_DIR = ROOT / "skills" / "bounty-program-finder"


def load_tool():
    spec = importlib.util.spec_from_file_location("package_claude_skill", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ClaudePackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool()

    def test_package_has_skill_folder_root_and_excludes_private_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = self.tool.package(SKILL_DIR, Path(tmp))
            self.assertTrue(zip_path.exists())
            with zipfile.ZipFile(zip_path) as archive:
                names = set(archive.namelist())

        self.assertIn("bounty-program-finder/skill.md", names)
        self.assertIn("bounty-program-finder/references/source-policy.md", names)
        self.assertNotIn("bounty-program-finder/SKILL.md", names)
        self.assertFalse(any("/.cache/" in name for name in names))


if __name__ == "__main__":
    unittest.main()
