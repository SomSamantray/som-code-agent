"""
Context Compaction Engine — preserve operational state across long sessions.

Based on Pi.dev and OpenCode's structured compaction approach:
- Decision-centric, not literary
- Preserves errors, file state, and active context
- Re-injects project config, memory, and skills after compaction
"""

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CompactionResult:
    """Result of context compaction."""
    summary: str
    original_turn_count: int
    compacted_turn_count: int
    files_modified: list[str]
    key_decisions: list[str]
    errors_preserved: list[str]
    timestamp: float = field(default_factory=time.time)


class ContextCompactor:
    """
    Manages context compaction for long-running sessions.

    Two modes:
    1. Auto-compaction: triggered when context > 80% of model max
    2. Manual compaction: agent calls compact_context() or user runs /compact

    The compaction preserves operational state using a structured template:
    - Goal
    - Completed Actions 
    - In Progress / Blocked
    - Key Decisions
    - Active State (files, errors)
    - Relevant Files
    """

    # Auto-trigger threshold (% of model's max context)
    AUTO_COMPACT_THRESHOLD = 0.80
    
    # Tail turns to preserve after compaction
    PRESERVE_TAIL_TURNS = 2
    
    # Max tokens for tool output in compaction
    MAX_TOOL_OUTPUT_CHARS = 2000
    
    # Max tokens for skill bodies after re-injection
    MAX_SKILL_TOKENS = 5000

    def __init__(self, model_max_context: int = 128000):
        self.model_max_context = model_max_context
        self.compaction_count = 0

    def should_auto_compact(self, estimated_tokens: int) -> bool:
        """Check if auto-compaction should trigger."""
        return estimated_tokens >= int(self.model_max_context * self.AUTO_COMPACT_THRESHOLD)

    def compact(
        self,
        turns: list,
        task: str,
        files_written: list[str],
        files_read: list[str],
        instructions: str = "",
    ) -> CompactionResult:
        """
        Generate a structured compaction summary.

        Args:
            turns: All completed turns in the session
            task: Original user task
            files_written: Files created/modified
            files_read: Files examined
            instructions: Optional guidance on what to emphasize

        Returns:
            CompactionResult with structured summary
        """
        self.compaction_count += 1
        
        # Extract key information from turns
        tool_calls = []
        errors = []
        decisions = []
        completed = []
        
        for turn in turns:
            for tc in turn.tool_calls if hasattr(turn, 'tool_calls') else []:
                if isinstance(tc, dict):
                    tool_calls.append(tc.get("name", "unknown"))
            
            for tr in turn.tool_results if hasattr(turn, 'tool_results') else []:
                if hasattr(tr, 'error') and tr.error:
                    errors.append(tr.error[:500])
                if hasattr(tr, 'success') and tr.success:
                    if hasattr(tr, 'output') and tr.output:
                        completed.append(tr.output[:200])

        # Build structured summary
        summary_parts = [
            "## Session Compaction Summary",
            f"\n**Compaction #{self.compaction_count}** — {time.ctime()}",
            "",
            "### Original Task",
            task,
            "",
            "### Completed Actions",
        ]
        
        if completed:
            for i, c in enumerate(completed[-10:], 1):  # Last 10 actions
                summary_parts.append(f"- {c}")
        else:
            summary_parts.append("- (no actions recorded yet)")
        
        summary_parts.extend([
            "",
            "### Files Modified",
        ])
        if files_written:
            for f in files_written:
                summary_parts.append(f"- `{f}`")
        else:
            summary_parts.append("- (no files modified)")
        
        summary_parts.extend([
            "",
            "### Files Examined",
        ])
        if files_read:
            for f in files_read[-15:]:  # Last 15
                summary_parts.append(f"- `{f}`")
        
        summary_parts.extend([
            "",
            "### Errors Encountered",
        ])
        if errors:
            for e in errors[-5:]:  # Last 5 errors
                summary_parts.append(f"- {e[:300]}")
        else:
            summary_parts.append("- No errors")
        
        if instructions:
            summary_parts.extend([
                "",
                "### Special Instructions for Continuation",
                instructions,
            ])
        
        summary_parts.extend([
            "",
            "### Key Decisions",
        ])
        if decisions:
            for d in decisions:
                summary_parts.append(f"- {d}")
        else:
            summary_parts.append("- (to be recorded by agent)")
        
        summary_parts.extend([
            "",
            "---",
            "_Continue from where you left off. Use the information above to maintain context._",
        ])
        
        return CompactionResult(
            summary="\n".join(summary_parts),
            original_turn_count=len(turns),
            compacted_turn_count=max(1, len(turns) - self.PRESERVE_TAIL_TURNS),
            files_modified=files_written,
            key_decisions=decisions,
            errors_preserved=errors[-5:],
        )

    def get_rehydration_context(
        self,
        som_md_content: str = "",
        memory_items: list[str] = None,
        skill_bodies: list[str] = None,
    ) -> str:
        """
        Build the re-injection context block that gets added after compaction.
        This re-establishes project context, user preferences, and active skills.
        """
        parts = []
        
        if som_md_content:
            parts.append("## Project Context (SOM.md)\n" + som_md_content[:5000] + ("\n..." if len(som_md_content) > 5000 else ""))
        
        if memory_items:
            parts.append("\n## User Preferences & Environment\n")
            for item in memory_items:
                parts.append(f"- {item}")
        
        if skill_bodies:
            parts.append("\n## Active Skills\n")
            for body in skill_bodies:
                truncated = body[:self.MAX_SKILL_TOKENS * 4]  # ~chars to tokens
                parts.append(truncated)
                if len(body) > len(truncated):
                    parts.append("\n_(skill truncated)_")
        
        return "\n\n".join(parts)
