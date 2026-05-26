import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from harness.sandbox import SubprocessSandbox  # noqa: E402
from som.tools.design import design_audit, design_repair_brief  # noqa: E402
from som.tools.all_tools import create_som_tools  # noqa: E402


class DesignToolTests(unittest.TestCase):
    def test_design_audit_detects_smells_and_writes_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, 'src')
            src.mkdir()
            Path(src, 'Dashboard.tsx').write_text('''
export function Dashboard() {
  const isLoading = false;
  if (isLoading) return <div>Loading...</div>;
  return <main className="min-h-screen flex items-center justify-center text-center bg-gradient-to-br from-blue-500 to-purple-600">
    <section className="backdrop-blur rounded-2xl shadow-xl grid grid-cols-3">
      <div className="feature card">Metric status analytics</div>
    </section>
  </main>;
}
''')
            sandbox = SubprocessSandbox(workspace=tmp)
            result = design_audit('src', sandbox=sandbox)

            self.assertTrue(result.success, result.error)
            report = result.metadata['design_audit']
            self.assertEqual(report['purpose'], 'Monitor')
            self.assertGreater(report['smells']['indigo_purple_default_palette'], 0)
            self.assertGreater(report['smells']['unearned_blur_glass'], 0)
            self.assertFalse(report['tokens']['oklch_present'])
            self.assertIn('empty', report['state_coverage']['missing_required'])
            self.assertIn('report_paths', report)
            self.assertTrue(Path(tmp, report['report_paths']['json']).exists())
            self.assertTrue(Path(tmp, report['report_paths']['markdown']).exists())

    def test_design_repair_brief_mentions_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'App.tsx').write_text('export function App(){ return <div className="text-center">No results</div> }')
            sandbox = SubprocessSandbox(workspace=tmp)
            result = design_repair_brief('.', purpose='Operate', sandbox=sandbox)

            self.assertTrue(result.success, result.error)
            self.assertIn('Purpose contract: **Operate**', result.output)
            self.assertIn('OKLCH/OKLAB', result.output)
            self.assertIn('loading, empty, error, disabled, and success states', result.output)
            self.assertIn('Report JSON:', result.output)

    def test_design_tools_are_registered(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = create_som_tools(SubprocessSandbox(workspace=tmp))
            self.assertIn('design_audit', registry._tools)
            self.assertIn('design_repair_brief', registry._tools)


if __name__ == '__main__':
    unittest.main()
