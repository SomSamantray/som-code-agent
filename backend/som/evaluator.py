"""
Evaluator Agent — a specialized agent that grades generator output against criteria.

Based on Anthropic's GAN-inspired evaluator pattern:
- NOT the same agent doing the work (generator)
- Uses structured grading criteria
- Hard thresholds — if any criterion fails, sprint fails
- Returns detailed, actionable feedback

Also includes the Backpressure Pipeline:
- Auto build → lint → type-check → test after every code change
- Fast feedback loop prevents bad code from accumulating
"""

import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════════════
# EVALUATOR
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Criterion:
    """A single grading criterion."""
    name: str
    description: str
    weight: float = 1.0  # Higher = more important
    threshold: float = 0.5  # Minimum score to pass (0.0-1.0)
    score: Optional[float] = None
    feedback: str = ""


@dataclass
class EvaluationResult:
    """Complete evaluation of a sprint/feature."""
    passed: bool
    overall_score: float
    criteria: list[Criterion]
    summary: str
    bugs_found: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    failed_criteria: list[str] = field(default_factory=list)


class EvaluatorAgent:
    """
    A specialized evaluator agent that grades generator output.

    Inspired by Anthropic's design:
    - Uses grading criteria that turn subjective judgments into gradable terms
    - Hard thresholds per criterion — any failure = sprint fails
    - Returns structured feedback the generator can act on
    """

    # Default grading criteria (based on Anthropic's four criteria)
    DEFAULT_CRITERIA = [
        Criterion(
            name="Functionality",
            description="Does the feature work end-to-end? Can users complete the core tasks? Are edge cases handled?",
            weight=1.5,
            threshold=0.7,
        ),
        Criterion(
            name="Code Quality",
            description="Is the code well-structured, documented, and maintainable? Does it follow project conventions?",
            weight=1.0,
            threshold=0.5,
        ),
        Criterion(
            name="Completeness",
            description="Are all specified requirements implemented? Is anything stubbed out or placeholder?",
            weight=1.2,
            threshold=0.6,
        ),
        Criterion(
            name="Testing",
            description="Are there adequate tests? Do tests verify the feature behavior and edge cases?",
            weight=1.0,
            threshold=0.5,
        ),
        Criterion(
            name="Integration",
            description="Does the feature integrate cleanly with existing code? No broken imports, no regressions?",
            weight=1.0,
            threshold=0.6,
        ),
    ]

    def __init__(self, criteria: list[Criterion] = None):
        self.criteria = criteria or self.DEFAULT_CRITERIA

    def evaluate(self, feature_description: str, workspace: str,
                 test_results: dict = None) -> EvaluationResult:
        """
        Evaluate a completed feature against grading criteria.

        Args:
            feature_description: What was supposed to be built
            workspace: Path to the workspace
            test_results: Optional pre-run test results

        Returns:
            EvaluationResult with scores, feedback, and pass/fail
        """
        # Run automated checks
        if test_results is None:
            test_results = self._run_automated_checks(workspace)

        # Grade each criterion
        graded_criteria = []
        for criterion in self.criteria:
            score, feedback = self._grade_criterion(
                criterion, feature_description, workspace, test_results
            )
            graded = Criterion(
                name=criterion.name,
                description=criterion.description,
                weight=criterion.weight,
                threshold=criterion.threshold,
                score=score,
                feedback=feedback,
            )
            graded_criteria.append(graded)

        # Calculate overall
        total_weight = sum(c.weight for c in graded_criteria)
        weighted_sum = sum((c.score or 0) * c.weight for c in graded_criteria)
        overall_score = weighted_sum / total_weight if total_weight > 0 else 0

        # Determine pass/fail
        failed = [
            c.name for c in graded_criteria 
            if c.score is not None and c.score < c.threshold
        ]
        passed = len(failed) == 0

        # Collect bugs and suggestions
        bugs = test_results.get("test_failures", [])
        suggestions = []
        for c in graded_criteria:
            if c.score is not None and c.score < 0.8:
                suggestions.append(f"[{c.name}] {c.feedback[:200]}")

        # Build summary
        if passed:
            summary = (
                f"✅ PASSED — Score: {overall_score:.1%}. "
                f"All criteria above thresholds."
            )
        else:
            summary = (
                f"❌ FAILED — Score: {overall_score:.1%}. "
                f"Failed criteria: {', '.join(failed)}."
            )

        return EvaluationResult(
            passed=passed,
            overall_score=round(overall_score, 3),
            criteria=graded_criteria,
            summary=summary,
            bugs_found=bugs,
            suggestions=suggestions,
            failed_criteria=failed,
        )

    def _grade_criterion(self, criterion: Criterion, feature_desc: str,
                         workspace: str, test_results: dict) -> tuple[float, str]:
        """Grade a single criterion using automated checks + heuristics."""
        score = 0.5  # Start neutral
        feedback_parts = []

        # Functionality: check test results
        if criterion.name == "Functionality":
            if test_results.get("tests_passed", 0) > 0:
                pass_rate = test_results.get("pass_rate", 0)
                score = pass_rate
                feedback_parts.append(f"Test pass rate: {pass_rate:.0%}")
            if test_results.get("test_failures"):
                score = max(0.1, score - 0.3)
                feedback_parts.append(f"Failures: {test_results['test_failures'][:3]}")

        # Code Quality: check lint + structure
        elif criterion.name == "Code Quality":
            if test_results.get("lint_passed", True):
                score = 0.8
                feedback_parts.append("Lint passes")
            else:
                score = 0.3
                feedback_parts.append("Lint issues found")
            # Check for documentation
            py_files = list(Path(workspace).glob("**/*.py"))
            if py_files:
                has_docs = any(
                    '"""' in f.read_text()[:200] 
                    for f in py_files[-5:] 
                    if f.exists()
                )
                if has_docs:
                    score = min(1.0, score + 0.1)
                    feedback_parts.append("Documentation present")

        # Completeness: heuristic check
        elif criterion.name == "Completeness":
            # Check for TODO/FIXME/HACK markers
            todo_count = self._count_markers(workspace, ["TODO", "FIXME", "HACK", "stub"])
            if todo_count == 0:
                score = 0.9
                feedback_parts.append("No TODO/stub markers found")
            elif todo_count < 3:
                score = 0.6
                feedback_parts.append(f"{todo_count} TODO/stub markers")
            else:
                score = 0.3
                feedback_parts.append(f"{todo_count} TODO/stub markers — may be incomplete")

        # Testing: check test coverage
        elif criterion.name == "Testing":
            test_count = test_results.get("test_count", 0)
            if test_count > 5:
                score = 0.8
                feedback_parts.append(f"{test_count} tests found")
            elif test_count > 0:
                score = 0.5
                feedback_parts.append(f"Only {test_count} tests — consider more coverage")
            else:
                score = 0.1
                feedback_parts.append("No tests found")

        # Integration: check imports + git status
        elif criterion.name == "Integration":
            # Check for import errors
            import_ok = test_results.get("import_check", True)
            if import_ok:
                score = 0.8
                feedback_parts.append("Imports check out")
            else:
                score = 0.2
                feedback_parts.append("Import errors detected")

        return min(1.0, max(0.0, score)), "; ".join(feedback_parts)

    def _run_automated_checks(self, workspace: str) -> dict:
        """Run automated build/test/lint checks on the workspace."""
        results = {
            "tests_passed": 0,
            "tests_failed": 0,
            "test_failures": [],
            "pass_rate": 0.0,
            "test_count": 0,
            "lint_passed": True,
            "lint_output": "",
            "import_check": True,
        }

        wsp = Path(workspace)

        # Run tests
        test_cmd = self._find_test_command(wsp)
        if test_cmd:
            try:
                proc = subprocess.run(
                    test_cmd, cwd=str(wsp), capture_output=True, text=True,
                    timeout=120, shell=True,
                )
                output = proc.stdout + proc.stderr
                # Parse pytest-style output
                if "passed" in output or "failed" in output:
                    import re
                    passed_match = re.search(r'(\d+)\s+passed', output)
                    failed_match = re.search(r'(\d+)\s+failed', output)
                    if passed_match:
                        results["tests_passed"] = int(passed_match.group(1))
                    if failed_match:
                        results["tests_failed"] = int(failed_match.group(1))
                    
                    total = results["tests_passed"] + results["tests_failed"]
                    results["test_count"] = total
                    results["pass_rate"] = results["tests_passed"] / max(total, 1)
                    
                    if results["tests_failed"] > 0:
                        # Extract failure messages
                        fail_lines = [l for l in output.split('\n') if 'FAILED' in l or 'AssertionError' in l or 'Error' in l]
                        results["test_failures"] = fail_lines[:5]
            except Exception:
                results["lint_passed"] = False

        # Run lint
        lint_cmd = self._find_lint_command(wsp)
        if lint_cmd:
            try:
                proc = subprocess.run(
                    lint_cmd, cwd=str(wsp), capture_output=True, text=True,
                    timeout=60, shell=True,
                )
                results["lint_output"] = (proc.stdout + proc.stderr)[:500]
                results["lint_passed"] = proc.returncode == 0
            except Exception:
                results["lint_passed"] = False

        # Check imports (Python)
        py_files = list(wsp.glob("**/*.py"))
        if py_files:
            # Quick syntax check on recent files
            for f in py_files[-10:]:
                try:
                    compile(f.read_text(), str(f), 'exec')
                except SyntaxError:
                    results["import_check"] = False
                    break

        return results

    def _find_test_command(self, wsp: Path) -> Optional[str]:
        """Find the project's test command."""
        if (wsp / "pytest.ini").exists() or (wsp / "pyproject.toml").exists():
            return "python -m pytest -x --tb=short -q 2>&1"
        if list(wsp.glob("*test*.py")) or list(wsp.glob("tests/test_*.py")):
            return "python -m pytest -x --tb=short -q 2>&1"
        if (wsp / "package.json").exists():
            try:
                pkg = json.loads((wsp / "package.json").read_text())
                if "test" in pkg.get("scripts", {}):
                    return "npm test 2>&1"
            except Exception:
                pass
        return None

    def _find_lint_command(self, wsp: Path) -> Optional[str]:
        """Find the project's lint command."""
        if (wsp / "pyproject.toml").exists():
            return "python -m ruff check . 2>&1 || python -m flake8 . 2>&1 || true"
        if (wsp / "package.json").exists():
            try:
                pkg = json.loads((wsp / "package.json").read_text())
                if "lint" in pkg.get("scripts", {}):
                    return "npm run lint 2>&1"
            except Exception:
                pass
        return None

    @staticmethod
    def _count_markers(workspace: str, markers: list[str]) -> int:
        """Count TODO/FIXME/HACK markers in code files."""
        count = 0
        wsp = Path(workspace)
        for ext in ['*.py', '*.js', '*.ts', '*.tsx', '*.go', '*.rs']:
            for f in wsp.glob(f"**/{ext}"):
                try:
                    content = f.read_text()
                    for marker in markers:
                        count += content.count(marker)
                except Exception:
                    pass
        return count


# ═══════════════════════════════════════════════════════════════════
# SPRINT CONTRACT
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SprintContract:
    """
    A negotiated agreement between generator and evaluator about what
    "done" looks like for a sprint, BEFORE any code is written.

    Based on Anthropic's harness design:
    - Generator proposes what to build + verification criteria
    - Evaluator reviews and negotiates
    - Both agree before coding starts
    - Generator builds against the contract
    - Evaluator checks against the contract
    """
    feature_id: str
    description: str
    proposed_by: str  # 'generator'
    reviewed_by: str  # 'evaluator'
    agreed: bool = False
    verification_criteria: list[str] = field(default_factory=list)
    files_to_change: list[str] = field(default_factory=list)
    tests_to_add: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    negotiation_log: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "feature_id": self.feature_id,
            "description": self.description,
            "agreed": self.agreed,
            "verification_criteria": self.verification_criteria,
            "files_to_change": self.files_to_change,
            "tests_to_add": self.tests_to_add,
            "risks": self.risks,
        }

    def to_prompt_block(self) -> str:
        """Generate a prompt block for the generator to work from."""
        lines = [
            "## Sprint Contract",
            f"**Feature:** {self.description}",
            "",
            "### Verification Criteria (must ALL pass):",
        ]
        for i, criterion in enumerate(self.verification_criteria, 1):
            lines.append(f"{i}. {criterion}")
        
        lines.extend([
            "",
            "### Expected File Changes:",
        ])
        for f in self.files_to_change:
            lines.append(f"- `{f}`")
        
        lines.extend([
            "",
            "### Required Tests:",
        ])
        for t in self.tests_to_add:
            lines.append(f"- {t}")
        
        if self.risks:
            lines.extend(["", "### Risks:", ""])
            for r in self.risks:
                lines.append(f"- {r}")
        
        lines.extend([
            "",
            "**IMPORTANT:** You MUST satisfy ALL verification criteria before calling task_complete.",
            "The evaluator will check each criterion. If any fails, the sprint will be rejected.",
        ])
        
        return "\n".join(lines)
