"""
Tool registry — auto-generates OpenAI-compatible schemas from Python functions.

Each tool is a function with type hints + docstring → automatic schema generation.
"""
import inspect
import json
from typing import Any, Callable, Optional
from dataclasses import dataclass, field

from .sandbox import SubprocessSandbox, ToolResult
from .skills import SkillLoader, get_skill_loader


# ── Type mapping ──────────────────────────────────────────────────────

def _python_type_to_json(annotation) -> str:
    """Map Python type hints to JSON Schema types."""
    if annotation is inspect.Parameter.empty:
        return "string"
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }
    origin = getattr(annotation, "__origin__", None)
    if origin is list:
        return "array"
    return type_map.get(annotation, "string")


def _function_to_openai_schema(fn: Callable) -> dict:
    """Convert a Python function to OpenAI function-calling schema."""
    sig = inspect.signature(fn)
    doc = inspect.getdoc(fn) or ""

    # Extract parameter descriptions from docstring
    param_descriptions = {}
    in_args = False
    for line in doc.split("\n"):
        line = line.strip()
        if line.startswith("Args:") or line.startswith("Arguments:"):
            in_args = True
            continue
        if in_args and ":" in line and not line.startswith(("Returns:", "Raises:")):
            name, desc = line.split(":", 1)
            name = name.strip()
            if name in sig.parameters:
                param_descriptions[name] = desc.strip()
        elif line.startswith(("Returns:", "Raises:")):
            in_args = False

    # Build JSON Schema
    properties = {}
    required = []
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        python_type = _python_type_to_json(param.annotation)
        prop = {
            "type": python_type,
            "description": param_descriptions.get(name, f"The {name} parameter"),
        }
        # Add defaults
        if param.default is not inspect.Parameter.empty:
            prop["default"] = param.default
        else:
            required.append(name)

        properties[name] = prop

    # First line of docstring is the description
    description = doc.split("\n")[0] if doc else f"Call the {fn.__name__} function"

    return {
        "name": fn.__name__,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


# ── Tool Registry ─────────────────────────────────────────────────────

class ToolRegistry:
    """
    Registry of callable tools with auto-generated OpenAI schemas.

    Usage:
        registry = ToolRegistry()

        @registry.register
        def bash(command: str, timeout: int = 120) -> ToolResult:
            '''Execute a shell command.'''
            ...
    """

    def __init__(self):
        self._tools: dict[str, dict] = {}
        self._sandbox: Optional[SubprocessSandbox] = None

    def set_sandbox(self, sandbox: SubprocessSandbox):
        """Set the sandbox for tool execution."""
        self._sandbox = sandbox

    def register(self, fn: Callable) -> Callable:
        """Register a function as a tool."""
        schema = _function_to_openai_schema(fn)
        self._tools[fn.__name__] = {
            "function": fn,
            "schema": schema,
        }
        return fn

    def get_schemas(self) -> list[dict]:
        """Return all tool schemas in OpenAI function-calling format."""
        return [
            {"type": "function", "function": t["schema"]}
            for t in self._tools.values()
        ]

    def get_tool_names(self) -> list[str]:
        """Return list of registered tool names."""
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def execute(self, name: str, arguments: dict) -> ToolResult:
        """Execute a tool by name with given arguments."""
        if name not in self._tools:
            return ToolResult(success=False, error=f"Tool '{name}' not found. Available: {self.get_tool_names()}")

        fn = self._tools[name]["function"]
        try:
            # Inject sandbox if the function expects it
            sig = inspect.signature(fn)
            if "sandbox" in sig.parameters:
                arguments = {**arguments, "sandbox": self._sandbox}

            result = fn(**arguments)

            # Normalize result to ToolResult
            if isinstance(result, ToolResult):
                return result
            elif isinstance(result, str):
                return ToolResult(success=True, output=result)
            elif isinstance(result, dict):
                return ToolResult(success=True, output=json.dumps(result, indent=2))
            else:
                return ToolResult(success=True, output=str(result))
        except TypeError as e:
            return ToolResult(
                success=False,
                error=f"Argument mismatch for tool '{name}': {e}\n"
                      f"Expected params: {list(sig.parameters.keys())}\n"
                      f"Received: {list(arguments.keys())}"
            )
        except Exception as e:
            import traceback
            return ToolResult(
                success=False,
                error=f"Tool '{name}' failed: {e}\n{traceback.format_exc()}"
            )


# ── Built-in Coding Agent Tools ───────────────────────────────────────

def create_coding_tools(sandbox: SubprocessSandbox) -> ToolRegistry:
    """Create a ToolRegistry with the standard coding agent tool set."""

    registry = ToolRegistry()
    registry.set_sandbox(sandbox)

    @registry.register
    def bash(command: str, timeout: int = 120) -> ToolResult:
        """Execute a shell command in the sandbox.

        command: The shell command to execute (e.g., 'python test.py', 'ls -la')
        timeout: Maximum execution time in seconds (default 120)
        """
        return sandbox.exec(command, timeout=timeout)

    @registry.register
    def read(path: str, offset: int = 0, limit: int = 500) -> ToolResult:
        """Read a file from the workspace.

        path: Relative or absolute path to the file
        offset: Line number to start reading from (0-indexed, default 0)
        limit: Maximum number of lines to return (default 500)
        """
        return sandbox.read_file(path, offset=offset, limit=limit)

    @registry.register
    def write(path: str, content: str) -> ToolResult:
        """Create or overwrite a file in the workspace.

        path: Relative or absolute path to the file
        content: The complete content to write to the file
        """
        return sandbox.write_file(path, content)

    @registry.register
    def ls(path: str = ".") -> ToolResult:
        """List files and directories in the workspace.

        path: Directory to list (default: workspace root)
        """
        return sandbox.list_dir(path)

    @registry.register
    def task_complete(summary: str) -> ToolResult:
        """Signal that the coding task is complete. Call this when you've finished.

        summary: Brief summary of what was accomplished
        """
        return ToolResult(
            success=True,
            output=f"Task completed: {summary}",
            metadata={"task_complete": True},
        )

    @registry.register
    def skill_search(query: str) -> ToolResult:
        """Search available skills by keyword.

        query: What to search for (e.g., 'python', 'debugging', 'testing')
        """
        loader = get_skill_loader()
        results = loader.search(query)
        if not results:
            return ToolResult(
                success=True,
                output=f"No skills found matching '{query}'.",
            )
        lines = [f"Found {len(results)} skill(s) matching '{query}':\n"]
        for s in results:
            lines.append(f"- **{s.name}**: {s.description}")
        return ToolResult(success=True, output="\n".join(lines))

    @registry.register
    def skill_view(name: str) -> ToolResult:
        """Load and view a skill's full instructions. Call this before using a skill.

        name: The exact skill name to load (e.g., 'strict-execution-protocol')
        """
        loader = get_skill_loader()
        skill = loader.get(name)
        if not skill:
            available = [s.name for s in loader.list_all()]
            return ToolResult(
                success=False,
                error=f"Skill '{name}' not found. Available: {', '.join(available[:20])}",
            )
        return ToolResult(
            success=True,
            output=f"# {skill.name} (v{skill.version})\n\n{skill.body}",
            metadata={"skill_name": name, "skill_loaded": True},
        )

    @registry.register
    def skill_list() -> ToolResult:
        """List all available skills."""
        loader = get_skill_loader()
        skills = loader.list_all()
        if not skills:
            return ToolResult(success=True, output="No skills available.")
        lines = [f"Available skills ({len(skills)}):\n"]
        for s in skills:
            lines.append(f"- **{s.name}**: {s.description}")
        return ToolResult(success=True, output="\n".join(lines))

    return registry
