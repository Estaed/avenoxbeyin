"""Tests for component and skill exclusion (Issue #94 Item 7)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from v3_package_helpers import ROOT, build_package, isolated_env, run_python

START, END = "<!-- beyin-v3:start -->", "<!-- beyin-v3:end -->"


class ComponentExclusionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v3-component-exclusion-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.vault = self.base / "Örnek Vault"
        self.vault.mkdir()
        self.state = self.base / "state"
        self.env = isolated_env(self.base / "home")

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts/install_v3.py"),
                               "--vault", str(self.vault), "--state", str(self.state), *args],
                              cwd=ROOT, env=self.env, capture_output=True, text=True, encoding="utf-8", timeout=120)

    def manifest(self):
        return json.loads((self.state / "v3-install.json").read_text(encoding="utf-8"))

    def test_exclude_starter_skill_initial_install(self):
        result = self.cli("--exclude-component", "skills/beyin-guncelle")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.vault / ".claude/skills/beyin-guncelle/SKILL.md").exists())
        self.assertFalse((self.vault / ".agents/skills/beyin-guncelle/SKILL.md").exists())
        self.assertTrue((self.vault / ".claude/skills/beyin/SKILL.md").exists())
        self.assertTrue((self.vault / ".claude/skills/beyin-doktor/SKILL.md").exists())
        manifest = self.manifest()
        self.assertEqual(manifest.get("excluded_components"), ["skills/beyin-guncelle"])
        self.assertNotIn(".claude/skills/beyin-guncelle/SKILL.md", manifest["files"])

    def test_exclude_component_removes_unchanged_file(self):
        initial = self.cli()
        self.assertEqual(initial.returncode, 0, initial.stderr)
        self.assertTrue((self.vault / ".claude/skills/beyin-guncelle/SKILL.md").exists())

        update = self.cli("--exclude-component", "skills/beyin-guncelle")
        self.assertEqual(update.returncode, 0, update.stderr)
        self.assertFalse((self.vault / ".claude/skills/beyin-guncelle/SKILL.md").exists())
        self.assertFalse((self.vault / ".agents/skills/beyin-guncelle/SKILL.md").exists())
        manifest = self.manifest()
        self.assertNotIn(".claude/skills/beyin-guncelle/SKILL.md", manifest["files"])
        self.assertEqual(manifest.get("excluded_components"), ["skills/beyin-guncelle"])

    def test_exclude_component_preserves_modified_file_without_conflict(self):
        initial = self.cli()
        self.assertEqual(initial.returncode, 0, initial.stderr)
        target = self.vault / ".claude/skills/beyin-guncelle/SKILL.md"
        custom_content = "# Kullanıcının kendi güncelleyici skill'i\nprint('custom')\n"
        target.write_text(custom_content, encoding="utf-8")

        # In previous versions, this raised: Reinstall conflict: managed file changed
        update = self.cli("--exclude-component", "skills/beyin-guncelle")
        self.assertEqual(update.returncode, 0, update.stderr)
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), custom_content)
        manifest = self.manifest()
        self.assertNotIn(".claude/skills/beyin-guncelle/SKILL.md", manifest["files"])

    def test_exclude_launchers(self):
        result = self.cli("--exclude-component", "launchers")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.vault / "Beyni Guncelle.cmd").exists())
        self.assertFalse((self.vault / "Beyni Guncelle.command").exists())
        self.assertFalse((self.vault / "Beyni Güncelle.sh").exists())
        self.assertFalse((self.vault / "Beyni Güncelle.desktop").exists())

    def test_exclude_harness_codex(self):
        result = self.cli("--exclude-component", "harnesses/codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        codex_hooks = self.vault / ".codex/hooks.json"
        self.assertFalse(codex_hooks.exists())
        self.assertFalse((self.vault / ".codex/config.toml").exists())

    def test_exclude_agents_block(self):
        agents_md = self.vault / "AGENTS.md"
        agents_md.write_text("# My rules\nNever delete my notes.\n", encoding="utf-8")
        result = self.cli("--exclude-component", "agents_block")
        self.assertEqual(result.returncode, 0, result.stderr)
        text = agents_md.read_text(encoding="utf-8")
        self.assertNotIn(START, text)
        self.assertIn("Never delete my notes.", text)

    def test_preferences_file_excluded_components_respected(self):
        prefs_file = self.vault / ".beyin-preferences.json"
        prefs_file.write_text(json.dumps({"excluded_components": ["skills/beyin-doktor"]}), encoding="utf-8")
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.vault / ".claude/skills/beyin-doktor/SKILL.md").exists())
        self.assertTrue((self.vault / ".claude/skills/beyin/SKILL.md").exists())

    def test_re_include_component(self):
        self.cli("--exclude-component", "skills/beyin-guncelle")
        self.assertFalse((self.vault / ".claude/skills/beyin-guncelle/SKILL.md").exists())
        reinclude = self.cli("--include-component", "skills/beyin-guncelle")
        self.assertEqual(reinclude.returncode, 0, reinclude.stderr)
        self.assertTrue((self.vault / ".claude/skills/beyin-guncelle/SKILL.md").exists())
        manifest = self.manifest()
        self.assertNotIn("skills/beyin-guncelle", manifest.get("excluded_components", []))


if __name__ == "__main__":
    unittest.main()
