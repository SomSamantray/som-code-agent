"""
Hook system — deterministic code at model/tool boundaries.

Inspired by Pi.dev's extension model and CommandCodeAI's hook architecture.
Hooks fire at lifecycle points and can inspect, modify, block, or annotate.
"""
from typing import Any, Callable
from dataclasses import dataclass, field


@dataclass
class HookContext:
    """Context passed to hooks. Mutable — hooks can modify it."""
    hook_point: str
    data: dict = field(default_factory=dict)
    blocked: bool = False
    block_reason: str = ""


class HookSystem:
    """
    Lifecycle hooks at model/tool boundaries.

    Hook points:
        session_start      — New session begins
        session_end        — Session ends
        before_model_call  — Before LLM API call (can modify messages, tools)
        after_model_call   — After LLM API call, before parsing
        before_tool_exec   — Before tool execution (can block, modify args)
        after_tool_exec    — After tool execution (can annotate result)
        before_compaction  — Before context compaction
    """

    HOOK_POINTS = [
        "session_start",
        "session_end",
        "before_model_call",
        "after_model_call",
        "before_tool_exec",
        "after_tool_exec",
        "before_compaction",
    ]

    def __init__(self):
        self._hooks: dict[str, list[Callable]] = {
            hp: [] for hp in self.HOOK_POINTS
        }

    def register(self, hook_point: str, callback: Callable[[HookContext], HookContext | None]):
        """
        Register a hook callback.

        Args:
            hook_point: One of HOOK_POINTS
            callback: Function that receives HookContext and returns (optionally modified) HookContext.
                     Return None to leave context unchanged.
                     Set context.blocked = True to block the operation.
        """
        if hook_point not in self.HOOK_POINTS:
            raise ValueError(f"Unknown hook point '{hook_point}'. Available: {self.HOOK_POINTS}")
        self._hooks[hook_point].append(callback)

    def fire(self, hook_point: str, context: dict = None) -> HookContext:
        """
        Fire all callbacks for a hook point.

        Returns:
            HookContext with any modifications from hooks.
            Check context.blocked to see if the operation should be blocked.
        """
        ctx = HookContext(hook_point=hook_point, data=context or {})

        for callback in self._hooks.get(hook_point, []):
            try:
                result = callback(ctx)
                if result is not None:
                    ctx = result
            except Exception as e:
                # Hook errors shouldn't crash the harness
                ctx.data["_hook_error"] = str(e)

        return ctx


# ── Built-in hooks ────────────────────────────────────────────────────

def create_path_protection_hook(workspace: str) -> Callable:
    """
    Block file operations that access paths outside the workspace.

    Usage:
        hooks.register("before_tool_exec", create_path_protection_hook("/workspace"))
    """
    import os

    def path_protection(ctx: HookContext) -> HookContext:
        tool_name = ctx.data.get("tool_name", "")
        if tool_name not in ("read", "write", "ls", "bash"):
            return ctx

        args = ctx.data.get("args", {})
        path = args.get("path", args.get("workdir", "."))
        full_path = os.path.normpath(os.path.join(workspace, path))

        if not full_path.startswith(os.path.normpath(workspace)):
            ctx.blocked = True
            ctx.block_reason = (
                f"Path '{path}' is outside the workspace '{workspace}'. "
                f"Tool calls are restricted to the workspace directory."
            )

        return ctx

    return path_protection


def create_destructive_command_hook() -> Callable:
    """
    Warn about potentially destructive shell commands.
    Doesn't block, just annotates the result.
    """
    DANGEROUS_PATTERNS = ["rm -rf /", "rm -rf ~", "dd if=", "mkfs.", ":(){ :|:& };:"]

    def destructive_check(ctx: HookContext) -> HookContext:
        if ctx.data.get("tool_name") != "bash":
            return ctx

        command = ctx.data.get("args", {}).get("command", "")
        for pattern in DANGEROUS_PATTERNS:
            if pattern in command.lower():
                ctx.data["_dangerous"] = True
                ctx.data["_warning"] = f"Potentially destructive command detected: '{pattern}'"
                break

        return ctx

    return destructive_check
