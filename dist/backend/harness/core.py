"""
Core Coding Agent Harness — the main agent loop.

Orchestrates: provider → hooks → repair → sandbox → tools → compaction.
"""
import json
import time
import sys
from typing import Optional
from dataclasses import dataclass, field

from .providers import ProviderClient, MockProviderClient, resolve_provider
from .sandbox import SubprocessSandbox, ToolResult
from .tools import ToolRegistry, create_coding_tools
from .repair import ToolInputRepair, RepairResult
from .hooks import HookSystem
from .skills import get_skill_loader


@dataclass
class Turn:
    """A single turn in the agent loop."""
    index: int
    role: str
    content: Optional[str] = None
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    repairs: list[dict] = field(default_factory=list)
    duration: float = 0.0
    tokens: dict = field(default_factory=dict)


@dataclass
class SessionResult:
    """Complete result of a coding session."""
    success: bool
    turns: list[Turn] = field(default_factory=list)
    final_response: str = ""
    total_duration: float = 0.0
    total_tokens: dict = field(default_factory=dict)
    total_tool_calls: int = 0
    total_repairs: int = 0
    error: Optional[str] = None
    sandbox_state: dict = field(default_factory=dict)


class CodingHarness:
    """
    The main coding agent harness.

    Usage:
        harness = CodingHarness("openai/gpt-4o-mini")
        sandbox = SubprocessSandbox(workspace="/tmp/my_project")

        result = harness.run(
            task="Write a Python function that sorts a list",
            sandbox=sandbox,
            max_turns=30,
        )

        print(result.final_response)
        sandbox.cleanup()
    """

    def __init__(
        self,
        provider_spec: str,
        tools: Optional[ToolRegistry] = None,
        hooks: Optional[HookSystem] = None,
        system_prompt: Optional[str] = None,
        max_turns: int = 30,
        max_retries: int = 3,
        mock_responses: list = None,  # For testing with MockProviderClient
    ):
        """
        Args:
            provider_spec: Provider/model spec (e.g., "openai/gpt-4o-mini", "ollama/qwen2.5:7b")
            tools: Tool registry (auto-created with standard coding tools if None)
            hooks: Hook system (created empty if None)
            system_prompt: Custom system prompt (uses default coding agent prompt if None)
            max_turns: Maximum agent turns before forcing completion
            max_retries: Max retries for API calls
            mock_responses: For testing — list of MockResponse objects
        """
        self.provider_spec = provider_spec

        # Use mock client for testing, real client otherwise
        if mock_responses is not None:
            self.client = MockProviderClient(mock_responses)
            self.config = self.client.config
            self.model_id = "mock-model"
        else:
            self.config, self.model_id = resolve_provider(provider_spec)
            self.client = ProviderClient(provider_spec)

        self.tools = tools
        self.hooks = hooks or HookSystem()
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.max_turns = max_turns
        self.max_retries = max_retries
        self.repair_engine = ToolInputRepair(enable_telemetry=True)

    # ── Main entry point ──────────────────────────────────────────────

    def run(
        self,
        task: str,
        sandbox: SubprocessSandbox,
        max_turns: Optional[int] = None,
    ) -> SessionResult:
        """
        Run a coding task through the agent loop.

        Args:
            task: The coding task description
            sandbox: Isolated sandbox for execution
            max_turns: Override default max_turns

        Returns:
            SessionResult with full trace of turns, tool calls, and outcome.
        """
        max_turns = max_turns or self.max_turns

        # Set up tools with this sandbox
        if self.tools is None:
            self.tools = create_coding_tools(sandbox)
        else:
            self.tools.set_sandbox(sandbox)

        # Initialize conversation
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]

        # Fire session_start hook
        self.hooks.fire("session_start", {"task": task, "sandbox": sandbox})

        turns = []
        total_tokens = {"prompt": 0, "completion": 0, "total": 0}
        total_tool_calls = 0
        total_repairs = 0
        start_time = time.time()

        try:
            for turn_idx in range(max_turns):
                turn_start = time.time()

                # ── Before model call hook ──
                hook_ctx = self.hooks.fire("before_model_call", {
                    "messages": messages,
                    "tools": self.tools.get_schemas(),
                    "turn": turn_idx,
                })
                if hook_ctx.blocked:
                    return SessionResult(
                        success=False,
                        turns=turns,
                        error=f"Blocked by before_model_call hook: {hook_ctx.block_reason}",
                    )

                # ── Call model ──
                response = self.client.chat(
                    messages=messages,
                    tools=self.tools.get_schemas() if self.tools._tools else None,
                    temperature=0.3,
                    max_tokens=4096,
                    max_retries=self.max_retries,
                )

                # ── After model call hook ──
                self.hooks.fire("after_model_call", {
                    "response": response,
                    "turn": turn_idx,
                })

                choice = response.choices[0]
                assistant_content = choice.message.content or ""

                # Track tokens
                if hasattr(response, "usage") and response.usage:
                    total_tokens["prompt"] += getattr(response.usage, "prompt_tokens", 0)
                    total_tokens["completion"] += getattr(response.usage, "completion_tokens", 0)
                    total_tokens["total"] += getattr(response.usage, "total_tokens", 0)

                turn = Turn(
                    index=turn_idx,
                    role="assistant",
                    content=assistant_content,
                    duration=time.time() - turn_start,
                    tokens={
                        "prompt": getattr(response.usage, "prompt_tokens", 0) if hasattr(response, "usage") else 0,
                        "completion": getattr(response.usage, "completion_tokens", 0) if hasattr(response, "usage") else 0,
                    },
                )

                # ── Check for tool calls ──
                has_tool_calls = (
                    choice.finish_reason == "tool_calls"
                    or (choice.message.tool_calls and len(choice.message.tool_calls) > 0)
                )

                if has_tool_calls:
                    # Process each tool call
                    tool_call_messages = []
                    tool_call_entries = []

                    for tc in choice.message.tool_calls:
                        tool_name = tc.function.name
                        raw_args = tc.function.arguments
                        total_tool_calls += 1

                        # ── Get tool schema for validation ──
                        tool_schema = None
                        if self.tools.has_tool(tool_name):
                            tool_schema = self.tools._tools[tool_name]["schema"]["parameters"]

                        # ── Validate + Repair ──
                        repair_result: RepairResult
                        if tool_schema:
                            repair_result = self.repair_engine.validate_and_repair(
                                tool_name, raw_args, tool_schema
                            )
                        else:
                            # No schema — try to parse directly
                            try:
                                parsed = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                                repair_result = RepairResult(valid=True, args=parsed)
                            except Exception as e:
                                repair_result = RepairResult(valid=False, error=str(e))

                        if repair_result.repaired:
                            total_repairs += 1
                            turn.repairs.extend(repair_result.repairs)

                        # ── Before tool hook ──
                        tool_hook_ctx = self.hooks.fire("before_tool_exec", {
                            "tool_name": tool_name,
                            "args": repair_result.args if repair_result.valid else {},
                            "raw_args": raw_args,
                            "repair_result": repair_result,
                        })

                        if tool_hook_ctx.blocked:
                            # Return block reason as tool result
                            tool_result = ToolResult(
                                success=False,
                                error=tool_hook_ctx.block_reason,
                            )
                        elif not repair_result.valid:
                            # Return repair error as tool result
                            tool_result = ToolResult(
                                success=False,
                                error=repair_result.error or "Invalid arguments",
                            )
                        else:
                            # Use (possibly hook-modified) args
                            final_args = tool_hook_ctx.data.get("args", repair_result.args)
                            tool_result = self.tools.execute(tool_name, final_args)

                            # ── After tool hook ──
                            self.hooks.fire("after_tool_exec", {
                                "tool_name": tool_name,
                                "args": final_args,
                                "result": tool_result,
                            })

                        # Record
                        tool_result_str = f"stdout:\n{tool_result.output}\n"
                        if tool_result.error:
                            tool_result_str += f"stderr:\n{tool_result.error}\n"
                        if tool_result.exit_code != 0:
                            tool_result_str += f"exit_code: {tool_result.exit_code}\n"
                        if tool_result.truncated:
                            tool_result_str += "(output truncated)\n"

                        turn.tool_calls.append({
                            "name": tool_name,
                            "arguments": raw_args,
                        })
                        turn.tool_results.append(tool_result)

                        # Append to messages
                        tool_call_messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": raw_args if isinstance(raw_args, str) else json.dumps(raw_args),
                                },
                            }],
                        })
                        tool_call_messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tool_result_str,
                        })

                    # Add all tool messages to conversation
                    messages.extend(tool_call_messages)
                    turn.tool_calls = tool_call_entries or turn.tool_calls

                    turns.append(turn)

                    # Check if task_complete was called — stop the loop
                    task_done = any(
                        tr.metadata.get("task_complete")
                        for tr in turn.tool_results
                    )
                    if task_done:
                        break

                else:
                    # No tool calls — model is done with this turn
                    messages.append({"role": "assistant", "content": assistant_content})
                    turns.append(turn)
                    # Always stop when model has no more tool calls
                    break

                # Safety: if we've gone too many turns, force stop
                if turn_idx == max_turns - 1:
                    break

        except Exception as e:
            import traceback
            return SessionResult(
                success=False,
                turns=turns,
                error=f"{e}\n{traceback.format_exc()}",
                total_duration=time.time() - start_time,
            )

        # Finalize
        final_response = turns[-1].content if turns else "No response"

        # Check for task_complete tool result as success signal
        task_completed = any(
            tr.metadata.get("task_complete")
            for turn in turns
            for tr in turn.tool_results
        )

        return SessionResult(
            success=task_completed,
            turns=turns,
            final_response=final_response,
            total_duration=time.time() - start_time,
            total_tokens=total_tokens,
            total_tool_calls=total_tool_calls,
            total_repairs=total_repairs,
            sandbox_state=sandbox.get_state(),
        )

    # ── Default system prompt ─────────────────────────────────────────

    def _default_system_prompt(self) -> str:
        """Generate the default coding agent system prompt with skills."""
        tool_list = []
        if self.tools:
            for name, info in self.tools._tools.items():
                desc = info["schema"]["description"]
                tool_list.append(f"- **{name}**: {desc}")

        tools_section = "\n".join(tool_list) if tool_list else "No tools available."

        # Inject available skills
        loader = get_skill_loader()
        loader.discover()
        skills_section = loader.inject_skills_prompt()

        return f"""You are a coding agent. Your job is to complete coding tasks by using the tools available to you.

## How to Work

1. Understand the user's request
2. Plan your approach
3. Use tools to explore, write, and test code
4. Verify your work
5. Call task_complete when finished

## Available Tools

{tools_section}

{skills_section}

## Rules

- Execute one step at a time
- Read files before editing them
- Test your code after writing it
- If a tool fails, read the error and try a different approach
- Always work within the provided workspace
- Be concise but thorough
- If a skill matches your task, load it with skill_view(name) before proceeding
"""
