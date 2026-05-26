import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from harness.skills import SkillLoader, get_skill_loader  # noqa: E402


class PackagedSkillTests(unittest.TestCase):
    def test_packaged_superpowers_skills_are_discovered_with_exact_names(self):
        backend_dir = Path(__file__).resolve().parents[1] / 'backend'
        packaged = backend_dir / 'skills'
        loader = SkillLoader([str(packaged)])
        skills = loader.discover()

        self.assertIn('writing-plans', skills)
        self.assertIn('verification-before-completion', skills)
        self.assertIn('systematic-debugging', skills)
        self.assertEqual(skills['writing-plans'].name, 'writing-plans')
        self.assertIn('multi-step task', skills['writing-plans'].description)

    def test_default_loader_includes_packaged_skills(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                loader = get_skill_loader([str(Path(__file__).resolve().parents[1] / 'backend' / 'skills')])
                self.assertIsNotNone(loader.get('writing-plans'))
            finally:
                os.chdir(cwd)


if __name__ == '__main__':
    unittest.main()
