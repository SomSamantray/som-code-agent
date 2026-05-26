"""
Plan Mode Manager — research → plan → approve → execute flow.

Based on Claude Code's plan mode pattern (the industry standard):
- Read-only exploration
- Structured plan presentation
- User approval with 4 options
- Handoff to execution mode
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlanState:
    """Current state of plan mode."""
    active: bool = False
    plan: str = ""
    research_notes: str = ""
    questions_asked: int = 0
    files_read: list[str] = field(default_factory=list)
    start_time: float = 0.0


class PlanModeManager:
    """
    Manages the plan → approve → execute lifecycle.

    Usage:
        mgr = PlanModeManager()
        
        # Agent enters plan mode
        mgr.enter()
        
        # Agent does read-only research
        mgr.record_file_read("src/main.py")
        
        # Agent presents plan
        plan_text = mgr.format_plan(files_changed=[...], steps=[...])
        mgr.set_plan(plan_text)
        
        # User approves → execute
        mgr.exit(approved=True)
    """

    APPROVAL_OPTIONS = {
        "1": "approve_execute",
        "2": "approve_review_edits",
        "3": "refine_with_feedback",
        "4": "save_for_later",
    }

    def __init__(self, plans_dir: str = None):
        self.state = PlanState()
        self.plans_dir = plans_dir or os.path.expanduser("~/.hermes/plans")
        os.makedirs(self.plans_dir, exist_ok=True)

    def enter(self) -> str:
        """Enter plan mode. Returns instructions for the agent."""
        self.state = PlanState(
            active=True,
            start_time=time.time(),
        )
        return (
            "📋 PLAN MODE ACTIVE — Read-Only Research\n\n"
            "You are now in planning mode. You CAN:\n"
            "- Read files and search the codebase\n"
            "- Search the web for best practices\n"
            "- Ask clarifying questions via ask_user_question()\n"
            "- Explore the project structure\n\n"
            "You CANNOT:\n"
            "- Write or edit files\n"
            "- Run shell commands that modify anything\n"
            "- Create files or directories\n\n"
            "When your research is complete, present your plan using exit_plan_mode().\n"
            "Your plan should include architecture, file changes, implementation order, and testing strategy."
        )

    def exit(self, approved: bool, mode: str = "execute") -> str:
        """Exit plan mode. Returns transition message."""
        self.state.active = False
        
        if approved and mode == "save":
            self._save_plan()
            return "📋 Plan saved to ~/.hermes/plans/. Use 'som resume-plan' to continue later."
        
        if approved:
            return (
                "✅ PLAN APPROVED — Switching to execution mode.\n"
                "All tools are now available. Follow the approved plan.\n"
                "Use todo_write() to track your progress through the plan steps."
            )
        
        return "📋 Plan mode exited without approval. Returning to normal mode."

    def _save_plan(self):
        """Save the current plan to disk."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"plan_{timestamp}.md"
        filepath = os.path.join(self.plans_dir, filename)
        
        with open(filepath, "w") as f:
            f.write(f"# Plan — {timestamp}\n\n")
            f.write(f"**Created:** {time.ctime(self.state.start_time)}\n\n")
            f.write(self.state.plan)
        
        return filepath

    def record_file_read(self, path: str):
        """Track files read during research."""
        if path not in self.state.files_read:
            self.state.files_read.append(path)

    def set_plan(self, plan_text: str):
        """Set the plan text for presentation."""
        self.state.plan = plan_text

    def get_plan(self) -> Optional[str]:
        """Get the current plan text."""
        return self.state.plan

    @staticmethod
    def format_approval_prompt(plan_text: str) -> str:
        """Format the approval prompt for the user."""
        return (
            "📋 **PLAN READY FOR REVIEW**\n\n"
            f"{plan_text}\n\n"
            "---\n"
            "**Approval Options:**\n"
            "1️⃣ **Approve & Execute** — Start coding immediately\n"
            "2️⃣ **Approve & Review Edits** — Show each change for manual review\n"
            "3️⃣ **Refine with Feedback** — Tell me what to change\n"
            "4️⃣ **Save for Later** — Save to ~/.hermes/plans/\n"
        )

    def load_saved_plan(self, plan_path: str) -> Optional[str]:
        """Load a previously saved plan."""
        if os.path.exists(plan_path):
            with open(plan_path, "r") as f:
                return f.read()
        return None

    def list_saved_plans(self) -> list[dict]:
        """List all saved plans."""
        plans = []
        if os.path.isdir(self.plans_dir):
            for fname in sorted(os.listdir(self.plans_dir), reverse=True):
                if fname.endswith(".md"):
                    fpath = os.path.join(self.plans_dir, fname)
                    plans.append({
                        "name": fname,
                        "path": fpath,
                        "size": os.path.getsize(fpath),
                        "modified": time.ctime(os.path.getmtime(fpath)),
                    })
        return plans[:20]  # Latest 20


# ═══════════════════════════════════════════════════════════════════
# Permission modes mapper
# ═══════════════════════════════════════════════════════════════════

READ_ONLY_TOOLS = {
    "read", "ls", "grep", "glob_tool", "web_fetch", "web_search",
    "skill_search", "skill_view", "skill_list",
    "ask_user_question", "enter_plan_mode", "exit_plan_mode",
    "compact_context", "todo_write",
}

WRITE_TOOLS = {
    "write", "edit", "bash",
}

ALL_TOOLS = READ_ONLY_TOOLS | WRITE_TOOLS | {"task_complete"}


def is_tool_allowed(tool_name: str, mode: str = "default") -> bool:
    """Check if a tool is allowed in the current permission mode.
    
    Modes:
    - 'plan': read-only tools only
    - 'default': read + write, ask for dangerous
    - 'acceptEdits': read + write auto-approved
    - 'bypass': everything allowed
    """
    if mode == "bypass":
        return True
    if mode == "plan":
        return tool_name in READ_ONLY_TOOLS
    # default and acceptEdits allow everything
    return tool_name in ALL_TOOLS
