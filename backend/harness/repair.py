"""
Tool-Input Repair Engine — Ahmad Awais' harness engineering techniques.

Core philosophy: Validate first, then repair only failing schema paths.
Never mutate already-valid inputs. Return model-readable errors.

Patterns:
    1. null for optional field → remove key
    2. Stringified array → JSON.parse
    3. Bare string where array expected → wrap in array
    4. Single-arg wrapper object → unwrap
    5. Markdown autolink in path → strip autolink
    6. Missing relational pair (offset/limit) → default sensible values
"""
import json
import re
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class RepairResult:
    """Result of validating and repairing tool inputs."""
    valid: bool
    args: Optional[dict] = None
    error: Optional[str] = None
    repaired: bool = False
    repairs: list[dict] = field(default_factory=list)
    telemetry: str = ""


@dataclass
class PathRepair:
    """Result of repairing a single schema path."""
    success: bool
    args: Optional[dict] = None
    description: str = ""


class ToolInputRepair:
    """
    Validate → repair only failing schema paths → re-validate.

    Usage:
        repair = ToolInputRepair()
        result = repair.validate_and_repair("read", raw_args, schema)

        if result.valid:
            execute_tool(result.args)
        else:
            return model_readable_error(result.error)
    """

    def __init__(self, enable_telemetry: bool = True):
        self.enable_telemetry = enable_telemetry
        self.repair_counts: dict[str, int] = {}  # key = tool_name:repair_type

    def validate_and_repair(
        self,
        tool_name: str,
        raw_args: str | dict,
        schema: dict,
    ) -> RepairResult:
        """
        Validate tool inputs against schema, repair if needed.

        Args:
            tool_name: Name of the tool being called (for telemetry)
            raw_args: Raw arguments from the model (JSON string or dict)
            schema: OpenAI function parameters schema

        Returns:
            RepairResult with (validated + possibly repaired) args or error
        """
        # Phase 1: Parse raw arguments
        args = self._parse_args(raw_args)
        if args is None:
            return RepairResult(
                valid=False,
                error=json.dumps({
                    "error": "Could not parse tool arguments as JSON",
                    "received": str(raw_args)[:200],
                    "help": "Provide valid JSON matching the tool's parameter schema.",
                }),
                telemetry=f"tool_input_unparseable:{tool_name}",
            )

        # Phase 1.5: Always sanitize string values (markdown autolinks, etc.)
        sanitized = self._sanitize_strings(args)
        args = sanitized

        # Phase 2: Validate against schema
        try:
            import jsonschema
            validator = jsonschema.Draft7Validator(schema)
            errors = list(validator.iter_errors(args))
        except ImportError:
            # jsonschema not available — skip validation, trust the args
            return RepairResult(valid=True, args=dict(args), repaired=False)
        except Exception as e:
            return RepairResult(
                valid=False,
                error=f"Schema validation error: {e}",
                telemetry=f"tool_schema_error:{tool_name}",
            )

        # Already valid — never touch it
        if not errors:
            return RepairResult(valid=True, args=dict(args), repaired=False)

        # Phase 3: Repair only failing paths
        repaired_args = dict(args)
        repair_log = []

        for error in errors:
            path = list(error.absolute_path)
            repair = self._repair_path(tool_name, repaired_args, path, error, schema)

            if repair.success and repair.args:
                repaired_args = repair.args
                repair_log.append({
                    "path": [str(p) for p in path],
                    "problem": error.message,
                    "repair": repair.description,
                })

        # Phase 4: Re-validate repaired args
        try:
            re_errors = list(validator.iter_errors(repaired_args))
        except Exception:
            re_errors = []

        if not re_errors:
            # Successfully repaired
            repair_type = "+".join(r["repair"][:20] for r in repair_log)
            telemetry = f"tool_input_repaired:{tool_name}:{repair_type}" if repair_log else ""
            return RepairResult(
                valid=True,
                args=repaired_args,
                repaired=True,
                repairs=repair_log,
                telemetry=telemetry,
            )

        # Phase 5: Still invalid — return model-readable error
        error_messages = self._model_readable_errors(re_errors, schema)
        return RepairResult(
            valid=False,
            error=json.dumps(error_messages, indent=2),
            repairs=repair_log,
            telemetry=f"tool_input_invalid:{tool_name}",
        )

    # ── String sanitization ─────────────────────────────────────────

    def _sanitize_strings(self, obj):
        """Recursively sanitize string values (markdown autolinks, etc.)."""
        if isinstance(obj, dict):
            return {k: self._sanitize_strings(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_strings(v) for v in obj]
        elif isinstance(obj, str):
            return self._strip_markdown_autolink(obj)
        return obj

    # ── Parsing ───────────────────────────────────────────────────────

    def _parse_args(self, raw_args: str | dict) -> Optional[dict]:
        """Parse raw arguments from the model into a dict."""
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            # Try direct JSON parse
            try:
                parsed = json.loads(raw_args)
                if isinstance(parsed, dict):
                    return parsed
                # If it parsed to non-dict (list, string), that's wrong
                return None
            except json.JSONDecodeError:
                pass
            # Try to extract JSON from text (model wrapped it in markdown etc.)
            return self._extract_json_from_text(raw_args)
        return None

    @staticmethod
    def _extract_json_from_text(text: str) -> Optional[dict]:
        """Extract a JSON object from text that may contain extra content."""
        if not text:
            return None

        # Try markdown code blocks
        match = re.search(r'```(?:json)?\s*\n?(\{.*?\})\s*\n?```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Find outermost {}
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        return None
        return None

    # ── Path repair ───────────────────────────────────────────────────

    def _repair_path(
        self,
        tool_name: str,
        args: dict,
        path: list,
        error,
        schema: dict,
    ) -> PathRepair:
        """
        Apply specific repairs based on error type and schema expectations.

        Order matters: stringify parse BEFORE bare string wrap.
        """
        instance = error.instance
        schema_type = error.schema.get("type", "?") if hasattr(error, "schema") else "?"

        # Repair 1: null for optional field → remove key
        if instance is None:
            if self._delete_path(args, path):
                return PathRepair(success=True, args=args,
                    description=f"Removed null value at {'/'.join(str(p) for p in path) if path else 'root'}")

        # Repair 2: string instead of array → try JSON.parse first
        if isinstance(instance, str) and schema_type == "array":
            # Try parse stringified array
            try:
                parsed = json.loads(instance)
                if isinstance(parsed, list):
                    self._set_path(args, path, parsed)
                    return PathRepair(success=True, args=args,
                        description=f"Parsed stringified array at {path}")
            except (json.JSONDecodeError, TypeError):
                pass
            # Bare string → wrap in array
            self._set_path(args, path, [instance])
            return PathRepair(success=True, args=args,
                description=f"Wrapped bare string in array at {path}")

        # Repair 3: array instead of string → join
        if isinstance(instance, list) and schema_type == "string" and len(instance) > 0:
            joined = " ".join(str(x) for x in instance)
            self._set_path(args, path, joined)
            return PathRepair(success=True, args=args,
                description=f"Joined array into string at {path}")

        # Repair 4: Markdown autolink in path string
        if schema_type == "string" and isinstance(instance, str):
            cleaned = self._strip_markdown_autolink(instance)
            if cleaned != instance:
                self._set_path(args, path, cleaned)
                return PathRepair(success=True, args=args,
                    description="Stripped markdown autolink from path")

        # Repair 5: Missing relational pair (offset/limit)
        if error.validator == "required":
            return self._repair_relational(args, error, tool_name)

        # Repair 6: Wrong type at root — if args is a list/string and schema expects object
        if not path and schema_type == "object":
            if isinstance(instance, list) and len(instance) == 1 and isinstance(instance[0], dict):
                return PathRepair(success=True, args=instance[0],
                    description="Unwrapped single-element array to object")

        return PathRepair(success=False, description=f"No repair for: {error.message}")

    def _repair_relational(self, args: dict, error, tool_name: str) -> PathRepair:
        """Handle missing relational invariants (e.g., offset without limit)."""
        missing = getattr(error, "validator_value", [])
        repaired = False

        # offset + limit pair
        if "limit" in missing and "offset" in args:
            args["limit"] = 500
            repaired = True
        if "offset" in missing and "limit" in args:
            args["offset"] = 0
            repaired = True

        if repaired:
            return PathRepair(success=True, args=args,
                description=f"Defaulted missing relational fields: {missing}")

        return PathRepair(success=False, description=f"Missing required fields: {missing}")

    # ── Path manipulation helpers ─────────────────────────────────────

    def _set_path(self, obj, path, value):
        """Set a value at a nested path in a dict."""
        if not path:
            return  # Can't replace root
        current = obj
        for key in path[:-1]:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and isinstance(key, int) and key < len(current):
                current = current[key]
            else:
                return
        last = path[-1]
        if isinstance(current, dict):
            current[last] = value
        elif isinstance(current, list) and isinstance(last, int) and last < len(current):
            current[last] = value

    def _delete_path(self, obj, path) -> bool:
        """Delete a key at a nested path. Returns True if deleted."""
        if not path:
            return False
        current = obj
        for key in path[:-1]:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return False
        last = path[-1]
        if isinstance(current, dict) and last in current:
            del current[last]
            return True
        return False

    # ── Markdown autolink stripping ────────────────────────────────────

    @staticmethod
    def _strip_markdown_autolink(text: str) -> str:
        """
        Strip degenerate markdown autolinks where the link text
        matches the URL/path. E.g.: '[notes.md](http://notes.md)' → 'notes.md'
        """
        pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        def replacer(m):
            link_text = m.group(1)
            url = m.group(2)
            # Only strip if the link text is a subset or match of the URL
            if link_text in url or url.endswith(link_text):
                return link_text
            return m.group(0)
        return re.sub(pattern, replacer, text)

    # ── Model-readable errors ─────────────────────────────────────────

    @staticmethod
    def _model_readable_errors(errors, schema) -> list[dict]:
        """Convert jsonschema errors to messages the model can understand."""
        messages = []
        for e in errors[:5]:  # Cap at 5 errors to avoid overwhelming
            path = " → ".join(str(p) for p in e.absolute_path) or "root"
            expected = e.schema.get("type", "any") if hasattr(e, "schema") else "?"
            got = type(e.instance).__name__

            # Generate a corrected example
            example = {}
            props = schema.get("properties", {})
            for pname, pschema in props.items():
                if pschema.get("type") == "string":
                    example[pname] = f"<{pname}_value>"
                elif pschema.get("type") == "integer":
                    example[pname] = 0
                elif pschema.get("type") == "array":
                    example[pname] = []
                elif pschema.get("type") == "boolean":
                    example[pname] = False

            messages.append({
                "path": path,
                "problem": f"Expected type '{expected}', but got '{got}'",
                "message": e.message,
                "correct_example": example if example else None,
            })

        return {
            "error": "Tool call arguments are invalid",
            "issues": messages,
            "action": "Fix the issues and call the tool again with correct arguments.",
        }
