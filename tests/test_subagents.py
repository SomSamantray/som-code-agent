import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from harness.sandbox import SubprocessSandbox  # noqa: E402
from som.tools.all_tools import create_som_tools  # noqa: E402


class SubagentScaffoldTests(unittest.TestCase):
    def test_subagent_tools_register_and_do_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'package.json').write_text('{"scripts":{"test":"node --test"}}')
            Path(tmp, 'src').mkdir()
            Path(tmp, 'src', 'index.ts').write_text('export const x = 1')
            sandbox = SubprocessSandbox(workspace=tmp)
            registry = create_som_tools(sandbox)

            for name in ('subagent_repo_map', 'subagent_review', 'subagent_test_plan'):
                self.assertIn(name, registry._tools)

            repo_map = registry._tools['subagent_repo_map']['function'](10)
            review = registry._tools['subagent_review']['function']('packaging')
            test_plan = registry._tools['subagent_test_plan']['function']()

            self.assertTrue(repo_map.success)
            self.assertIn('src/index.ts', repo_map.output)
            self.assertTrue(review.success)
            self.assertIn('does not modify files', review.output)
            self.assertTrue(test_plan.success)
            self.assertIn('npm test', test_plan.output)
            self.assertEqual(sandbox.files_written, set())


if __name__ == '__main__':
    unittest.main()
