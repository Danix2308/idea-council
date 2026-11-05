"""Checks that the skill stays installable on Claude surfaces and Codex."""

import json
import re
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "research-council"
sys.path.insert(0, str(ROOT / "scripts"))

from package_skill import package_skill  # noqa: E402

LINK = re.compile(r"\]\(([^)\s]+)\)")


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    block = text.split("---", 2)[1]
    fields = {}
    for line in block.strip().splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


class SkillMetadataTests(unittest.TestCase):
    def test_name_and_description_fit_claude_upload_limits(self):
        fields = frontmatter(SKILL / "SKILL.md")
        self.assertEqual(fields["name"], "research-council")
        self.assertGreater(len(fields["description"]), 0)
        self.assertLessEqual(len(fields["description"]), 200)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.cache = SKILL / "scripts" / "__pycache__"
        self.made_cache = not self.cache.exists()
        self.cache.mkdir(exist_ok=True)
        self.fake_pyc = self.cache / "packaging_test_fake.pyc"
        self.fake_pyc.write_bytes(b"not real bytecode")

    def tearDown(self):
        self.fake_pyc.unlink(missing_ok=True)
        if self.made_cache:
            shutil.rmtree(self.cache, ignore_errors=True)
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_zip_has_one_folder_with_scripts_and_no_bytecode(self):
        output = self.temp / "research-council.zip"
        package_skill(output)
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
        self.assertEqual({name.split("/")[0] for name in names}, {"research-council"})
        for required in [
            "research-council/SKILL.md",
            "research-council/references/host-compatibility.md",
            "research-council/scripts/council_state.py",
        ]:
            self.assertIn(required, names)
        self.assertFalse([name for name in names if "__pycache__" in name or name.endswith(".pyc")])

    def test_output_inside_skill_folder_is_refused(self):
        with self.assertRaises(ValueError):
            package_skill(SKILL / "inside.zip")
        self.assertFalse((SKILL / "inside.zip").exists())


class PluginManifestTests(unittest.TestCase):
    def test_plugin_and_marketplace_agree(self):
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        listed = market["plugins"][0]
        self.assertEqual(plugin["name"], "idea-council")
        self.assertEqual(market["name"], "idea-council")
        self.assertEqual(listed["name"], "idea-council")
        self.assertEqual(listed["version"], plugin["version"])
        self.assertEqual(listed["source"], "./")


class MarkdownLinkTests(unittest.TestCase):
    def test_relative_links_resolve(self):
        files = [ROOT / "README.md"]
        files += sorted((ROOT / "docs").glob("*.md"))
        files += sorted(SKILL.rglob("*.md"))
        broken = []
        for path in files:
            for target in LINK.findall(path.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                relative = target.split("#", 1)[0]
                if not (path.parent / relative).exists():
                    broken.append(f"{path.relative_to(ROOT)} -> {target}")
        self.assertEqual(broken, [])


if __name__ == "__main__":
    unittest.main()
