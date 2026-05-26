#!/usr/bin/env python3
"""
SOM-CODE Backend Server — JSONL protocol server for the TypeScript TUI.

Communicates with the TUI via stdin/stdout JSONL messages.
Each message is one line of JSON, flushed immediately.

Protocol:
  TUI → PY: {id, type: 'task'|'answer'|'plan_approve'|'plan_refine'|'cancel'|'ping', payload}
  PY → TUI: {id, type: 'delta'|'tool_call'|'tool_result'|'thinking'|'question'|'done'|'plan_enter'|'plan_exit'|'compact'|'error'|'pong', payload}
"""

import sys
sys.dont_write_bytecode = True
import os
import json
import argparse
import signal
import traceback
from pathlib import Path

# Add harness to path
_harness_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'llm-harness')
if os.path.isdir(_harness_dir):
    sys.path.insert(0, _harness_dir)

from harness.core import CodingHarness
from harness.sandbox import SubprocessSandbox
from harness.skills import get_skill_loader
from harness.hooks import HookSystem, create_path_protection_hook

from som.tools.all_tools import create_som_tools
from som.agent.plan import PlanModeManager
from som.agent.compact import ContextCompactor
from som.context.som_md import SomConfigLoader


READ_ONLY_TOOLS = {
    "read", "ls", "grep", "glob_tool", "web_fetch", "web_search",
    "todo_write", "ask_user_question", "enter_plan_mode", "exit_plan_mode",
    "compact_context", "skill_search", "skill_view", "skill_list",
    "subagent_repo_map", "subagent_review", "subagent_test_plan",
}
WRITE_TOOLS = {"write", "edit"}
EXEC_TOOLS = {"bash"}
DANGEROUS_COMMAND_PATTERNS = (
    "rm -rf", "sudo", "mkfs", "dd if=", ":(){", "chmod -R 777",
    "chown -R", "curl ", "wget ", "npm publish", "git push", "ssh ", "scp ",
)


def create_permission_hook(permission: str):
    mode = permission or "default"

    def permission_hook(ctx):
        tool_name = ctx.data.get("tool_name", "")
        args = ctx.data.get("args", {}) or {}
        command = str(args.get("command", "")).lower()

        if mode == "bypass":
            return ctx

        if mode == "plan" and tool_name not in READ_ONLY_TOOLS:
            ctx.blocked = True
            ctx.block_reason = (
                f"Permission mode 'plan' blocks tool '{tool_name}'. "
                "Research/read-only tools are allowed; present a plan before edits or shell execution."
            )
            return ctx

        if mode == "default" and tool_name in WRITE_TOOLS:
            ctx.blocked = True
            ctx.block_reason = (
                f"Permission mode 'default' blocks write tool '{tool_name}'. "
                "Ask for approval or use acceptEdits/bypass mode before modifying files."
            )
            return ctx

        if mode in {"default", "acceptEdits"} and tool_name in EXEC_TOOLS:
            if any(pattern in command for pattern in DANGEROUS_COMMAND_PATTERNS):
                ctx.blocked = True
                ctx.block_reason = (
                    f"Permission mode '{mode}' blocked potentially dangerous command: {args.get('command', '')}. "
                    "Use a safer command or explicit bypass mode."
                )
                return ctx

        return ctx

    return permission_hook


def build_finish_gate(result) -> dict:
    """Summarize whether the harness reached a trustworthy completion state."""
    completed = bool(getattr(result, "success", False))
    error = getattr(result, "error", None)
    turns = len(getattr(result, "turns", []) or [])
    tool_calls = int(getattr(result, "total_tool_calls", 0) or 0)
    if completed:
        reason = "task_complete"
        verified = True
    elif error:
        reason = "error"
        verified = False
    elif turns <= 0:
        reason = "no_turns"
        verified = False
    else:
        reason = "incomplete_no_task_complete"
        verified = False
    return {
        "verified": verified,
        "finish_reason": reason,
        "requires_review": not verified,
        "turns": turns,
        "tool_calls": tool_calls,
        "error": error or "",
    }


class BackendServer:
    """JSONL backend server for SOM-CODE TUI."""

    def __init__(self, model: str, workspace: str = None):
        self.model = model
        self.workspace = workspace or os.path.join(os.getcwd(), '.som_workspace')
        self.sandbox = None
        self.harness = None
        self.running = False
        self.current_task_id = None
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        self.running = False
        sys.exit(0)

    def send(self, msg_type: str, payload=None, msg_id: str = None):
        """Send a JSONL message to the TUI."""
        msg = {
            "id": msg_id or self.current_task_id or "0",
            "type": msg_type,
            "payload": payload,
            "timestamp": __import__('time').time(),
        }
        line = json.dumps(msg, default=str)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

    def send_error(self, error: str):
        self.send("error", {"error": error})

    def handle_task(self, msg_id: str, payload: dict):
        """Handle an incoming task execution request."""
        self.current_task_id = msg_id
        task = payload.get("task", "")
        permission = payload.get("permission", "default")

        # Set up sandbox
        os.makedirs(self.workspace, exist_ok=True)
        self.sandbox = SubprocessSandbox(workspace=self.workspace)

        # Load SOM.md
        som_loader = SomConfigLoader(project_root=self.workspace)
        som_context = som_loader.get_system_prompt_block()

        # Set up hooks
        hooks = HookSystem()
        hooks.register("before_tool_exec", create_path_protection_hook(self.workspace))
        hooks.register("before_tool_exec", create_permission_hook(permission))

        # Plan mode blocks
        if permission == "plan":
            def plan_mode_block(ctx):
                from som.agent.plan import READ_ONLY_TOOLS
                tool_name = ctx.data.get("tool_name", "")
                if tool_name not in READ_ONLY_TOOLS:
                    ctx.blocked = True
                    ctx.block_reason = f"Tool '{tool_name}' not allowed in plan mode."
                return ctx
            hooks.register("before_tool_exec", plan_mode_block)

        # Build system prompt
        system_prompt = f"""You are SOM-CODE, a coding agent. Complete tasks using the tools available.

{som_context if som_context else ''}

## How to Work
1. Understand the request
2. Plan using todo_write
3. Explore with grep, glob, read
4. Write code
5. Test with bash
6. Call task_complete when done

## Permission Mode
Current permission mode: `{permission}`.
- `plan`: read/search/web/skill/todo only; no writes or shell execution.
- `default`: read/search plus safe shell; file writes require explicit user approval.
- `acceptEdits`: file writes are allowed; dangerous shell/network/publish commands are blocked.
- `bypass`: unrestricted inside the workspace guard.
If a needed tool is blocked, explain the exact permission change required instead of retrying blindly.

## Rules
- One step at a time
- Read before editing
- Test after writing
- Use ask_user_question when you need clarification
- If a skill matches your task, load it with skill_view(name) first
"""

        # Create harness with tool result streaming
        self.harness = CodingHarness(
            self.model,
            tools=create_som_tools(self.sandbox),
            hooks=hooks,
            system_prompt=system_prompt,
            max_turns=50,
        )

        # Monkey-patch tool execution to stream results
        original_execute = self.harness.tools.execute
        def stream_execute(name, arguments):
            # Send tool_call event
            self.send("tool_call", {
                "name": name,
                "args": arguments,
                "id": f"tc-{name}",
            })
            
            result = original_execute(name, arguments)
            
            # Send tool_result event
            self.send("tool_result", {
                "name": name,
                "success": result.success,
                "output": result.output[:5000] if result.output else "",
                "error": result.error[:2000] if result.error else "",
                "exit_code": result.exit_code,
                "metadata": result.metadata,
            })
            
            # Check for special metadata
            if result.metadata.get("plan_mode"):
                self.send("plan_enter", None)
            if result.metadata.get("plan_exit"):
                self.send("plan_exit", {"plan": result.metadata.get("plan", "")})
            if result.metadata.get("interactive"):
                self.send("question", result.metadata.get("questions"))
            if result.metadata.get("compact_requested"):
                compactor = ContextCompactor()
                result_compact = compactor.compact(
                    turns=[], task=task,
                    files_written=list(self.sandbox.files_written),
                    files_read=list(self.sandbox.files_read),
                )
                self.send("compact", {
                    "summary": result_compact.summary,
                    "files_modified": result_compact.files_modified,
                    "turn_count": result_compact.original_turn_count,
                })
            
            return result

        self.harness.tools.execute = stream_execute

        # Monkey-patch provider to stream deltas
        # (In a full implementation, this would use streaming API;
        # for now, we send the full response as a single delta)
        original_chat = self.harness.client.chat
        def stream_chat(*args, **kwargs):
            response = original_chat(*args, **kwargs)
            content = response.choices[0].message.content or ""
            
            # Check for thinking content (model-specific)
            if hasattr(response.choices[0].message, 'reasoning_content'):
                thinking = getattr(response.choices[0].message, 'reasoning_content', '')
                if thinking:
                    self.send("thinking", {"content": thinking})
            
            # Send content as delta
            if content:
                self.send("delta", {"content": content})
            
            return response
        
        self.harness.client.chat = stream_chat

        # Run the task
        try:
            result = self.harness.run(task, self.sandbox)
            
            finish_gate = build_finish_gate(result)
            self.send("done", {
                "summary": result.final_response,
                "success": result.success,
                "turns": len(result.turns),
                "tool_calls": result.total_tool_calls,
                "tokens": result.total_tokens,
                "finish_reason": finish_gate["finish_reason"],
                "verified": finish_gate["verified"],
                "requires_review": finish_gate["requires_review"],
                "error": finish_gate["error"],
            })
        except Exception as e:
            self.send_error(f"Task execution failed: {e}\n{traceback.format_exc()}")
        finally:
            if self.sandbox:
                self.sandbox.cleanup()

    def run(self):
        """Main server loop — read JSONL from stdin, process, respond."""
        self.running = True
        self.send("pong", {"status": "ready"})

        for line in sys.stdin:
            if not self.running:
                break
            
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self.send_error(f"Invalid JSON: {line[:100]}")
                continue

            msg_id = msg.get("id", "0")
            msg_type = msg.get("type", "")
            payload = msg.get("payload", {})

            if msg_type == "ping":
                self.send("pong", {"status": "ok"})
            
            elif msg_type == "task":
                self.handle_task(msg_id, payload)
            
            elif msg_type == "cancel":
                self.running = False
                self.send("done", {"summary": "Cancelled", "success": False, "finish_reason": "cancelled", "verified": False, "requires_review": True})
                break
            
            elif msg_type == "answer":
                # In a full implementation, this would be fed back to the harness
                # For now, acknowledge
                self.send("delta", {"content": "\n[User answered the question]\n"})
            
            else:
                self.send_error(f"Unknown message type: {msg_type}")


def main():
    parser = argparse.ArgumentParser(description="SOM-CODE Backend Server")
    parser.add_argument("--model", "-m", default="openrouter/anthropic/claude-sonnet-4")
    parser.add_argument("--workspace", "-w", default=None)
    args = parser.parse_args()

    server = BackendServer(model=args.model, workspace=args.workspace)
    server.run()


if __name__ == "__main__":
    main()
