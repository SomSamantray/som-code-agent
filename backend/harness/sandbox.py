"""
Subprocess sandbox — isolated execution environment for tool calls.

Uses subprocess with working directory restriction instead of Docker
(when Docker is unavailable). Falls back gracefully.
"""
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolResult:
    """Structured result from tool execution."""
    success: bool
    output: str = ""
    error: str = ""
    exit_code: int = 0
    truncated: bool = False
    metadata: dict = field(default_factory=dict)


class SubprocessSandbox:
    """
    Isolated execution environment using subprocess with:
    - Working directory restriction
    - Command timeouts
    - Output truncation
    - Environment variable control
    """

    def __init__(self, workspace: str = None, max_output: int = 100_000):
        """
        workspace: Root directory for all file operations.
                   Tool calls cannot access paths outside this directory.
        max_output: Maximum bytes of combined stdout+stderr before truncation.
        """
        self.workspace = os.path.abspath(workspace or tempfile.mkdtemp(prefix="harness_sandbox_"))
        self.max_output = max_output
        os.makedirs(self.workspace, exist_ok=True)

        # Track modified files for context compaction
        self.files_read: set[str] = set()
        self.files_written: set[str] = set()
        self.commands_run: list[str] = []

    # ── File operations ───────────────────────────────────────────────

    def read_file(self, path: str, offset: int = 0, limit: int = 500) -> ToolResult:
        """Read a file within the workspace."""
        full_path = self._resolve_path(path)
        if full_path is None:
            return ToolResult(success=False, error=f"Path '{path}' is outside workspace")

        try:
            with open(full_path, "r") as f:
                lines = f.readlines()

            total_lines = len(lines)
            selected = lines[offset:offset + limit]
            content = "".join(selected)

            self.files_read.add(path)

            return ToolResult(
                success=True,
                output=content,
                metadata={
                    "path": path,
                    "total_lines": total_lines,
                    "offset": offset,
                    "lines_returned": len(selected),
                    "truncated": (offset + limit) < total_lines,
                }
            )
        except FileNotFoundError:
            return ToolResult(success=False, error=f"File not found: {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def write_file(self, path: str, content: str) -> ToolResult:
        """Write a file within the workspace. Creates parent directories."""
        full_path = self._resolve_path(path)
        if full_path is None:
            return ToolResult(success=False, error=f"Path '{path}' is outside workspace")

        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)
            self.files_written.add(path)
            return ToolResult(
                success=True,
                output=f"Wrote {len(content)} bytes to {path}",
                metadata={"path": path, "bytes": len(content)},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def list_dir(self, path: str = ".") -> ToolResult:
        """List directory contents."""
        full_path = self._resolve_path(path)
        if full_path is None:
            return ToolResult(success=False, error=f"Path '{path}' is outside workspace")

        try:
            entries = os.listdir(full_path)
            result_lines = []
            for name in sorted(entries):
                entry_path = os.path.join(full_path, name)
                entry_type = "d" if os.path.isdir(entry_path) else "f"
                size = os.path.getsize(entry_path) if os.path.isfile(entry_path) else "-"
                result_lines.append(f"{entry_type} {size:>8} {name}")

            return ToolResult(
                success=True,
                output="\n".join(result_lines) or "(empty)",
                metadata={"path": path, "count": len(entries)},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    # ── Command execution ─────────────────────────────────────────────

    def exec(self, command: str, timeout: int = 120, workdir: str = None) -> ToolResult:
        """
        Execute a shell command in the workspace.

        command: Shell command to execute
        timeout: Max seconds before killing
        workdir: Relative path within workspace (default: workspace root)
        """
        cwd = self.workspace
        if workdir:
            resolved = self._resolve_path(workdir)
            if resolved is None:
                return ToolResult(success=False, error=f"Workdir '{workdir}' is outside workspace")
            cwd = resolved

        self.commands_run.append(command)

        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "HOME": self.workspace},
            )

            stdout = proc.stdout or ""
            stderr = proc.stderr or ""

            # Truncate if too large
            truncated = False
            if len(stdout) + len(stderr) > self.max_output:
                truncated = True
                half = self.max_output // 2
                stdout = stdout[:half] + f"\n... [truncated {len(stdout) - half} bytes]"
                stderr = stderr[:half] + f"\n... [truncated {len(stderr) - half} bytes]"

            return ToolResult(
                success=(proc.returncode == 0),
                output=stdout,
                error=stderr,
                exit_code=proc.returncode,
                truncated=truncated,
                metadata={
                    "command": command,
                    "workdir": workdir or ".",
                    "duration": timeout,  # approximate
                },
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Command timed out after {timeout}s: {command}",
                exit_code=-1,
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), exit_code=-1)

    # ── Helpers ───────────────────────────────────────────────────────

    def _resolve_path(self, path: str) -> Optional[str]:
        """Resolve a path and verify it's within the workspace."""
        full = os.path.normpath(os.path.join(self.workspace, path))
        if not full.startswith(os.path.normpath(self.workspace)):
            return None
        return full

    def cleanup(self):
        """Remove the workspace directory."""
        import shutil
        if os.path.exists(self.workspace):
            shutil.rmtree(self.workspace, ignore_errors=True)

    def get_state(self) -> dict:
        """Return current sandbox state for context compaction."""
        return {
            "workspace": self.workspace,
            "files_read": sorted(self.files_read),
            "files_written": sorted(self.files_written),
            "commands_run": self.commands_run[-20:],  # last 20 commands
        }


class DockerSandbox(SubprocessSandbox):
    """
    Docker-based sandbox. Falls back to subprocess if Docker unavailable.

    Usage:
        sandbox = DockerSandbox(image="python:3.11-slim", workspace="/workspace")
    """

    def __init__(self, image: str = "python:3.11-slim", workspace: str = "/workspace"):
        import shutil
        if shutil.which("docker"):
            self._init_docker(image, workspace)
        else:
            print("⚠ Docker not available, using subprocess sandbox", file=__import__('sys').stderr)
            super().__init__(workspace=workspace)

    def _init_docker(self, image, workspace):
        """Initialize Docker container."""
        import docker
        self.docker_client = docker.from_env()
        self.container = self.docker_client.containers.run(
            image,
            command="tail -f /dev/null",
            volumes={os.path.abspath(workspace): {"bind": "/workspace", "mode": "rw"}},
            working_dir="/workspace",
            detach=True,
            remove=True,
        )
        self.workspace = "/workspace"
        self._docker_mode = True
        super().__init__(workspace=workspace)

    def exec(self, command: str, timeout: int = 120, workdir: str = None) -> ToolResult:
        """Execute in Docker if available."""
        if getattr(self, "_docker_mode", False):
            cwd = workdir or "/workspace"
            try:
                exec_result = self.container.exec_run(
                    f"sh -c '{command}'",
                    workdir=cwd,
                )
                return ToolResult(
                    success=(exec_result.exit_code == 0),
                    output=exec_result.output.decode("utf-8", errors="replace"),
                    exit_code=exec_result.exit_code,
                )
            except Exception as e:
                return ToolResult(success=False, error=str(e))
        return super().exec(command, timeout, workdir)
