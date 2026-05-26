import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from server import create_permission_hook, build_finish_gate  # noqa: E402
from harness.hooks import HookContext  # noqa: E402


def check(mode, tool, args=None):
    hook = create_permission_hook(mode)
    return hook(HookContext('before_tool_exec', {'tool_name': tool, 'args': args or {}}))


class PolicyTests(unittest.TestCase):
    def test_plan_blocks_writes_and_bash(self):
        self.assertTrue(check('plan', 'write', {'path': 'x'}).blocked)
        self.assertTrue(check('plan', 'bash', {'command': 'pytest'}).blocked)
        self.assertFalse(check('plan', 'read', {'path': 'x'}).blocked)

    def test_default_blocks_writes_but_allows_safe_bash(self):
        self.assertTrue(check('default', 'edit', {'path': 'x'}).blocked)
        self.assertFalse(check('default', 'bash', {'command': 'pytest -q'}).blocked)

    def test_accept_edits_blocks_dangerous_shell(self):
        self.assertFalse(check('acceptEdits', 'write', {'path': 'x'}).blocked)
        self.assertTrue(check('acceptEdits', 'bash', {'command': 'rm -rf .'}).blocked)

    def test_bypass_allows_policy_layer(self):
        self.assertFalse(check('bypass', 'bash', {'command': 'rm -rf .'}).blocked)

    def test_finish_gate_marks_task_complete_verified(self):
        result = type('Result', (), {'success': True, 'error': None, 'turns': [object()], 'total_tool_calls': 2})()
        gate = build_finish_gate(result)
        self.assertTrue(gate['verified'])
        self.assertEqual(gate['finish_reason'], 'task_complete')

    def test_finish_gate_marks_unfinished_for_review(self):
        result = type('Result', (), {'success': False, 'error': None, 'turns': [object()], 'total_tool_calls': 0})()
        gate = build_finish_gate(result)
        self.assertFalse(gate['verified'])
        self.assertTrue(gate['requires_review'])
        self.assertEqual(gate['finish_reason'], 'incomplete_no_task_complete')


if __name__ == '__main__':
    unittest.main()
