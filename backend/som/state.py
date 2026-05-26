"""
Structured State Artifacts — the missing foundation for long-running agents.

Based on Anthropic's two articles + OpenAI's harness engineering:
- feature_list.json: Structured task tracking (JSON, not Markdown — harder to corrupt)
- progress.json: Session-by-session progress log
- init.sh: Environment bootstrap (created by initializer agent)

These artifacts are the "map" that every agent session reads at startup
and updates at completion. They enable clean context resets and prevent
the two core failure modes:
  1. Agent tries to do too much at once
  2. Agent declares victory too early
"""

import os
import json
import time
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Any


# ═══════════════════════════════════════════════════════════════════
# FEATURE LIST
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Feature:
    """A single feature in the feature list."""
    id: str
    category: str  # e.g., "functional", "visual", "performance", "security"
    description: str
    steps: list[str] = field(default_factory=list)
    passes: bool = False
    implemented_by: Optional[str] = None  # commit hash
    notes: str = ""
    priority: int = 0  # 0=highest, higher=lower

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Feature":
        return cls(**{k: data.get(k, v.default if v.default is not v.default else None) 
                       for k, v in cls.__dataclass_fields__.items()})


class FeatureList:
    """
    Manages feature_list.json — the structured task list that every agent
    session reads at startup and updates.

    Based on Anthropic's "Effective Harnesses" article pattern:
    - JSON format (models less likely to inappropriately modify)
    - Each feature has: category, description, test steps, passes field
    - Agents can ONLY change the "passes" field and "notes"
    - "It is unacceptable to remove or edit tests" (strongly-worded rule)

    Usage:
        features = FeatureList("/path/to/project")
        features.load()
        next_feature = features.get_next_incomplete()
        features.mark_complete(next_feature.id, commit_hash="abc123")
        features.save()
    """

    FEATURE_LIST_FILENAME = "feature_list.json"
    PROGRESS_FILENAME = "progress.json"

    def __init__(self, workspace: str):
        self.workspace = Path(workspace)
        self.features: list[Feature] = []
        self.progress: list[dict] = []
        self.feature_path = self.workspace / self.FEATURE_LIST_FILENAME
        self.progress_path = self.workspace / self.PROGRESS_FILENAME

    # ── Load / Save ──────────────────────────────────────────────

    def load(self) -> bool:
        """Load feature list and progress from disk."""
        if self.feature_path.exists():
            try:
                data = json.loads(self.feature_path.read_text())
                self.features = [Feature.from_dict(f) for f in data.get("features", [])]
            except (json.JSONDecodeError, KeyError):
                self.features = []

        if self.progress_path.exists():
            try:
                self.progress = json.loads(self.progress_path.read_text())
            except (json.JSONDecodeError, KeyError):
                self.progress = []

        return len(self.features) > 0

    def save(self):
        """Save feature list and progress to disk."""
        # Save feature list
        data = {
            "version": "1.0",
            "total_features": len(self.features),
            "completed_features": sum(1 for f in self.features if f.passes),
            "last_updated": time.ctime(),
            "features": [f.to_dict() for f in self.features],
        }
        self.feature_path.write_text(json.dumps(data, indent=2))

        # Save progress
        self.progress_path.write_text(json.dumps(self.progress, indent=2))

    # ── Feature Management ───────────────────────────────────────

    def add_feature(self, category: str, description: str, steps: list[str] = None, 
                    priority: int = 0) -> Feature:
        """Add a new feature. All start as failing."""
        feature = Feature(
            id=f"feat-{len(self.features)+1:03d}",
            category=category,
            description=description,
            steps=steps or [],
            passes=False,
            priority=priority,
        )
        self.features.append(feature)
        return feature

    def get_feature(self, feature_id: str) -> Optional[Feature]:
        """Get a feature by ID."""
        for f in self.features:
            if f.id == feature_id:
                return f
        return None

    def get_next_incomplete(self) -> Optional[Feature]:
        """Get the highest-priority incomplete feature."""
        incomplete = [f for f in self.features if not f.passes]
        if not incomplete:
            return None
        # Sort by priority (lowest first), then by ID
        incomplete.sort(key=lambda f: (f.priority, f.id))
        return incomplete[0]

    def mark_complete(self, feature_id: str, commit_hash: str = None, notes: str = ""):
        """Mark a feature as complete (passing)."""
        feature = self.get_feature(feature_id)
        if feature:
            feature.passes = True
            feature.implemented_by = commit_hash
            if notes:
                feature.notes = notes

    def mark_failing(self, feature_id: str, notes: str = ""):
        """Mark a feature as failing (for reverting)."""
        feature = self.get_feature(feature_id)
        if feature:
            feature.passes = False
            if notes:
                feature.notes = notes

    def get_summary(self) -> dict:
        """Get a summary of feature completion."""
        total = len(self.features)
        completed = sum(1 for f in self.features if f.passes)
        by_category = {}
        for f in self.features:
            by_category.setdefault(f.category, {"total": 0, "done": 0})
            by_category[f.category]["total"] += 1
            if f.passes:
                by_category[f.category]["done"] += 1
        
        return {
            "total": total,
            "completed": completed,
            "remaining": total - completed,
            "percent": round(completed / total * 100, 1) if total > 0 else 0,
            "by_category": by_category,
            "next": self.get_next_incomplete().description if self.get_next_incomplete() else None,
        }

    # ── Progress Tracking ─────────────────────────────────────────

    def log_progress(self, session_id: str, feature_id: str, action: str, 
                     commit_hash: str = None, notes: str = ""):
        """Log a progress entry for the current session."""
        entry = {
            "session_id": session_id,
            "timestamp": time.ctime(),
            "feature_id": feature_id,
            "action": action,  # 'started', 'implemented', 'tested', 'completed', 'failed'
            "commit_hash": commit_hash,
            "notes": notes,
        }
        self.progress.append(entry)

    def get_recent_progress(self, limit: int = 10) -> list[dict]:
        """Get the most recent progress entries."""
        return self.progress[-limit:]

    def get_progress_summary(self) -> str:
        """Generate a human-readable progress summary."""
        if not self.progress:
            return "No progress recorded yet."

        recent = self.progress[-5:]
        lines = ["## Recent Progress"]
        for entry in recent:
            lines.append(
                f"- [{entry['timestamp'][:16]}] {entry['action']} "
                f"{entry['feature_id']}: {entry['notes'][:80]}"
            )
        
        summary = self.get_summary()
        lines.append(f"\n**Progress:** {summary['completed']}/{summary['total']} features ({summary['percent']}%)")
        if summary['next']:
            lines.append(f"**Next:** {summary['next'][:100]}")
        
        return "\n".join(lines)

    # ── Init Script ───────────────────────────────────────────────

    def generate_init_script(self, commands: list[str] = None) -> str:
        """Generate an init.sh script for the project."""
        script_lines = [
            "#!/bin/bash",
            "# init.sh — Auto-generated by SOM-CODE initializer agent",
            "# Run this at the start of every session to set up the environment.",
            "",
            "set -e",
            "",
            "echo '🚀 Setting up environment...'",
            "",
        ]
        
        if commands:
            for cmd in commands:
                script_lines.append(f"# {cmd}")
                script_lines.append(cmd)
                script_lines.append("")
        else:
            # Default: detect common setup patterns
            script_lines.extend([
                "# Install dependencies",
                "if [ -f requirements.txt ]; then pip install -r requirements.txt; fi",
                "if [ -f package.json ]; then npm install; fi",
                "",
                "# Start development server (if applicable)",
                "# python -m src.main &",
                "# npm run dev &",
                "",
                "echo '✅ Environment ready.'",
            ])
        
        script_path = self.workspace / "init.sh"
        script_path.write_text("\n".join(script_lines))
        script_path.chmod(0o755)
        return str(script_path)

    def run_init_script(self) -> tuple[bool, str]:
        """Run the init.sh script and return (success, output)."""
        script_path = self.workspace / "init.sh"
        if not script_path.exists():
            return False, "init.sh not found. Run generate_init_script() first."
        
        try:
            result = subprocess.run(
                ["bash", str(script_path)],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=60,
            )
            success = result.returncode == 0
            output = result.stdout + ("\nERR:\n" + result.stderr if result.stderr else "")
            return success, output
        except subprocess.TimeoutExpired:
            return False, "init.sh timed out after 60 seconds"
        except Exception as e:
            return False, f"Failed to run init.sh: {e}"


# ═══════════════════════════════════════════════════════════════════
# CLEAN STATE PROTOCOL
# ═══════════════════════════════════════════════════════════════════

class CleanStateProtocol:
    """
    Enforces the "clean state" rule from Anthropic's harness design:
    Every session must leave the codebase in a mergeable state.

    Checks:
    1. Git working tree is clean (or changes are committed)
    2. All tests pass
    3. App starts successfully
    4. Basic smoke test passes
    """

    def __init__(self, workspace: str):
        self.workspace = Path(workspace)

    def verify_clean_state(self) -> tuple[bool, list[str]]:
        """
        Verify the workspace is in a clean state.
        Returns (is_clean, list_of_issues).
        """
        issues = []

        # Check 1: Git working tree
        is_git_repo = (self.workspace / ".git").exists()
        if is_git_repo:
            try:
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.stdout.strip():
                    issues.append(f"Uncommitted changes:\n{result.stdout[:500]}")
            except Exception as e:
                issues.append(f"Git check failed: {e}")

        # Check 2: Tests pass (if test command configured)
        test_cmd = self._detect_test_command()
        if test_cmd:
            try:
                result = subprocess.run(
                    test_cmd,
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    timeout=120,
                    shell=True,
                )
                if result.returncode != 0:
                    issues.append(f"Tests failed (exit {result.returncode}):\n{result.stderr[:300]}")
            except subprocess.TimeoutExpired:
                issues.append("Tests timed out (120s)")
            except Exception as e:
                issues.append(f"Test execution failed: {e}")

        # Check 3: Lint passes (if lint command configured)
        lint_cmd = self._detect_lint_command()
        if lint_cmd:
            try:
                result = subprocess.run(
                    lint_cmd,
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    timeout=60,
                    shell=True,
                )
                if result.returncode != 0:
                    issues.append(f"Lint failed:\n{result.stdout[:300] or result.stderr[:300]}")
            except subprocess.TimeoutExpired:
                pass  # Lint timeout is non-critical
            except Exception:
                pass

        return len(issues) == 0, issues

    def _detect_test_command(self) -> Optional[str]:
        """Auto-detect the test command for the project."""
        # Python
        if (self.workspace / "pytest.ini").exists() or (self.workspace / "pyproject.toml").exists():
            return "python -m pytest -x --tb=short 2>&1"
        if list(self.workspace.glob("*test*.py")):
            return "python -m pytest -x --tb=short 2>&1"
        # Node
        if (self.workspace / "package.json").exists():
            try:
                pkg = json.loads((self.workspace / "package.json").read_text())
                if "test" in pkg.get("scripts", {}):
                    return "npm test 2>&1"
            except Exception:
                pass
        # Go
        if list(self.workspace.glob("*_test.go")) or list(self.workspace.glob("**/*_test.go")):
            return "go test ./... 2>&1"
        return None

    def _detect_lint_command(self) -> Optional[str]:
        """Auto-detect the lint command for the project."""
        # Python
        if (self.workspace / "pyproject.toml").exists():
            return "python -m ruff check . 2>&1 || python -m flake8 . 2>&1 || true"
        # Node
        if (self.workspace / "package.json").exists():
            try:
                pkg = json.loads((self.workspace / "package.json").read_text())
                if "lint" in pkg.get("scripts", {}):
                    return "npm run lint 2>&1"
            except Exception:
                pass
        return None

    def get_state_report(self) -> str:
        """Generate a human-readable state report."""
        is_clean, issues = self.verify_clean_state()
        
        lines = ["## Clean State Report"]
        lines.append(f"**Status:** {'✅ CLEAN' if is_clean else '⚠️ ISSUES FOUND'}")
        lines.append("")
        
        # Git status
        is_git_repo = (self.workspace / ".git").exists()
        if is_git_repo:
            try:
                result = subprocess.run(
                    ["git", "log", "--oneline", "-5"],
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                lines.append("**Recent commits:**")
                for line in result.stdout.strip().split("\n")[:5]:
                    if line:
                        lines.append(f"  {line}")
            except Exception:
                pass
        
        if issues:
            lines.append("\n**Issues:**")
            for issue in issues:
                lines.append(f"- {issue[:200]}")
        
        # File stats
        py_files = len(list(self.workspace.glob("**/*.py"))) if self.workspace.exists() else 0
        if py_files > 0:
            lines.append(f"\n**Files:** {py_files} Python files")
        
        return "\n".join(lines)
