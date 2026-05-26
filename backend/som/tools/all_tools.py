"""
Som CLI — Complete tool registry.

Extends the base ToolRegistry with all Som-specific tools:
search (grep, glob), file ops (edit), web (fetch, search),
interactive (ask_user_question, plan_*), task (todo_write),
and control (compact_context).
"""

import json
import os
import re
import subprocess
import glob as pyglob
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.tools import ToolRegistry as BaseToolRegistry, create_coding_tools
from harness.sandbox import SubprocessSandbox, ToolResult


# ═══════════════════════════════════════════════════════════════════
# SEARCH TOOLS
# ═══════════════════════════════════════════════════════════════════

def tool_grep(
    pattern: str,
    path: str = ".",
    glob: str = "*",
    limit: int = 50,
    sandbox: SubprocessSandbox = None,
) -> ToolResult:
    """Search file contents using regex pattern (ripgrep-backed).

    pattern: Regex pattern to search for
    path: Directory or file to search in (default: workspace root)
    glob: File pattern filter (default: '*')
    limit: Maximum results to return (default: 50)
    """
    try:
        import shutil
        rg = shutil.which("rg")
        if rg:
            cmd = [
                rg, "--line-number", "--no-heading", "--color", "never",
                "-g", glob,
                "-m", str(limit * 2),
                pattern, path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=sandbox.workspace if sandbox else None)
            output = result.stdout.strip()
            if not output:
                return ToolResult(success=True, output=f"No matches found for '{pattern}'", metadata={"count": 0})
            lines = output.split("\n")[:limit]
            return ToolResult(
                success=True,
                output="\n".join(lines),
                metadata={"count": len(lines), "pattern": pattern, "path": path},
            )
        else:
            # Fallback: Python-based grep
            matches = []
            search_root = Path(path)
            if not search_root.is_absolute() and sandbox:
                search_root = Path(sandbox.workspace) / path
            
            for fpath in search_root.rglob(glob):
                if not fpath.is_file():
                    continue
                try:
                    content = fpath.read_text()
                    for i, line in enumerate(content.split("\n"), 1):
                        if re.search(pattern, line):
                            matches.append(f"{fpath}:{i}:{line}")
                            if len(matches) >= limit:
                                break
                except Exception:
                    continue
                if len(matches) >= limit:
                    break
            
            if not matches:
                return ToolResult(success=True, output=f"No matches found for '{pattern}'", metadata={"count": 0})
            return ToolResult(
                success=True,
                output="\n".join(matches),
                metadata={"count": len(matches), "pattern": pattern},
            )
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, error=f"Grep timed out searching for '{pattern}'")
    except Exception as e:
        return ToolResult(success=False, error=f"Grep error: {e}")


def tool_glob(
    pattern: str,
    path: str = ".",
    sandbox: SubprocessSandbox = None,
) -> ToolResult:
    """Find files matching a glob pattern.

    pattern: Glob pattern (e.g., '*.py', '**/*test*', 'src/**/*.js')
    path: Directory to search in (default: workspace root)
    """
    try:
        search_root = Path(path)
        if not search_root.is_absolute() and sandbox:
            search_root = Path(sandbox.workspace) / path
        
        matches = sorted(search_root.glob(pattern))
        # Filter to files only, limit to 200
        files = [str(m.relative_to(search_root) if search_root != Path(path) else m) for m in matches if m.is_file()][:200]
        
        if not files:
            return ToolResult(success=True, output=f"No files matching '{pattern}'", metadata={"count": 0})
        
        return ToolResult(
            success=True,
            output="\n".join(files),
            metadata={"count": len(files), "pattern": pattern},
        )
    except Exception as e:
        return ToolResult(success=False, error=f"Glob error: {e}")


# ═══════════════════════════════════════════════════════════════════
# EDIT TOOL
# ═══════════════════════════════════════════════════════════════════

def tool_edit(
    path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
    sandbox: SubprocessSandbox = None,
) -> ToolResult:
    """Make targeted edits to a file by finding and replacing text.

    Uses fuzzy matching (similar to Claude Code's Edit tool):
    - Leading/trailing whitespace is normalized for matching
    - The old_string must be unique in the file (unless replace_all=True)

    path: Absolute or workspace-relative path to the file
    old_string: The text to find and replace
    new_string: The replacement text
    replace_all: Replace all occurrences (default: False, requires unique match)
    """
    try:
        full_path = Path(path)
        if sandbox and not full_path.is_absolute():
            full_path = Path(sandbox.workspace) / path
        
        if not full_path.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        
        content = full_path.read_text()
        
        # Try exact match first
        count = content.count(old_string)
        
        if count == 0:
            # Try fuzzy match: normalize whitespace
            def _normalize(s):
                return re.sub(r'\s+', ' ', s).strip()
            
            old_norm = _normalize(old_string)
            lines = content.split('\n')
            matched = False
            new_lines = []
            
            for line in lines:
                if not matched and _normalize(line) == old_norm and line.strip() == old_string.strip():
                    new_lines.append(new_string)
                    matched = True
                else:
                    new_lines.append(line)
            
            if matched:
                new_content = '\n'.join(new_lines)
                count = 1
            else:
                return ToolResult(
                    success=False,
                    error=f"Could not find '{old_string[:100]}...' in {path}. The text must match exactly (whitespace-insensitive)."
                )
            content = new_content
        
        if count > 1 and not replace_all:
            # Find line numbers of matches
            match_lines = []
            for i, line in enumerate(content.split('\n'), 1):
                if old_string in line:
                    match_lines.append(str(i))
            
            return ToolResult(
                success=False,
                error=(
                    f"Found {count} matches for this string in {path}. "
                    f"Matches on lines: {', '.join(match_lines[:10])}. "
                    f"Add more context to make the match unique, or set replace_all=True."
                )
            )
        
        # Perform replacement
        new_content = content.replace(old_string, new_string) if replace_all else content.replace(old_string, new_string, 1)
        full_path.write_text(new_content)
        
        return ToolResult(
            success=True,
            output=f"Applied edit to {path}: replaced {count} occurrence(s)",
            metadata={"path": path, "replacements": count if replace_all else 1},
        )
    except Exception as e:
        return ToolResult(success=False, error=f"Edit error: {e}")


# ═══════════════════════════════════════════════════════════════════
# WEB TOOLS
# ═══════════════════════════════════════════════════════════════════

def tool_web_fetch(url: str) -> ToolResult:
    """Fetch and extract text content from a URL.

    url: The URL to fetch (must be http/https)
    """
    try:
        import requests
        
        if not url.startswith(("http://", "https://")):
            return ToolResult(success=False, error=f"Invalid URL: {url}. Must start with http:// or https://")
        
        headers = {
            "User-Agent": "SomCLI/1.0 (coding-agent)",
        }
        
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        
        # Extract text from HTML
        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type:
            # Simple HTML-to-text extraction
            text = re.sub(r'<script[^>]*>.*?</script>', '', resp.text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
        else:
            text = resp.text
        
        # Truncate if too large
        max_chars = 50_000
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars] + f"\n\n... [truncated {len(text) - max_chars} chars]"
        
        return ToolResult(
            success=True,
            output=text,
            metadata={
                "url": url,
                "status_code": resp.status_code,
                "content_type": content_type,
                "truncated": truncated,
                "size": len(text),
            },
        )
    except requests.RequestException as e:
        return ToolResult(success=False, error=f"Web fetch error for {url}: {e}")
    except Exception as e:
        return ToolResult(success=False, error=f"Web fetch error: {e}")


def tool_web_search(query: str, num_results: int = 5) -> ToolResult:
    """Search the web and return results.

    Uses DuckDuckGo instant answers + fallback to HTML scraping.

    query: The search query
    num_results: Number of results to return (default: 5, max: 10)
    """
    try:
        import requests
        
        num_results = min(num_results, 10)
        
        # Try DuckDuckGo HTML (non-JS version)
        headers = {
            "User-Agent": "SomCLI/1.0 (coding-agent)",
        }
        
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        
        # Parse results
        results = []
        # Extract result snippets
        snippets = re.findall(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
        links = re.findall(r'<a[^>]*class="result__url"[^>]*href="([^"]*)"', resp.text)
        titles = re.findall(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
        
        for i in range(min(num_results, len(titles))):
            results.append({
                "title": re.sub(r'<[^>]+>', '', titles[i]).strip() if i < len(titles) else "",
                "snippet": re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else "",
                "url": links[i] if i < len(links) else "",
            })
        
        if not results:
            return ToolResult(
                success=True,
                output=f"No results found for '{query}'. Try different keywords.",
                metadata={"query": query, "count": 0},
            )
        
        # Format output
        lines = [f"Web search results for '{query}':\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. **{r['title']}**")
            if r['snippet']:
                lines.append(f"   {r['snippet'][:200]}")
            if r['url']:
                lines.append(f"   {r['url']}")
            lines.append("")
        
        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"query": query, "count": len(results)},
        )
    except Exception as e:
        return ToolResult(success=False, error=f"Web search error: {e}")


# ═══════════════════════════════════════════════════════════════════
# TASK TOOLS
# ═══════════════════════════════════════════════════════════════════

# In-memory todo store (session-scoped)
_todos: list[dict] = []


def tool_todo_write(todos: list[dict], merge: bool = False) -> ToolResult:
    """Create or update a structured task list for the current session.

    Use this to track progress through complex multi-step tasks.
    One task in_progress at a time. Mark completed immediately when done.

    todos: List of task objects with: id (str), content (str), status (one of: pending, in_progress, completed, cancelled)
    merge: If True, update existing tasks by id and add new ones. If False, replace entire list.

    Example:
        [{"id": "1", "content": "Set up project structure", "status": "in_progress"},
         {"id": "2", "content": "Write main module", "status": "pending"},
         {"id": "3", "content": "Add tests", "status": "pending"}]
    """
    global _todos
    
    if not todos:
        # Return current list
        if not _todos:
            return ToolResult(success=True, output="No tasks tracked yet.")
        
        lines = ["Current tasks:"]
        for t in _todos:
            icon = {"pending": "⬜", "in_progress": "🔄", "completed": "✅", "cancelled": "❌"}.get(t.get("status", "pending"), "❓")
            lines.append(f"  {icon} [{t['id']}] {t['content']}")
        return ToolResult(success=True, output="\n".join(lines), metadata={"count": len(_todos)})
    
    if merge:
        # Update existing, add new
        existing_ids = {t["id"] for t in _todos}
        for new_t in todos:
            if new_t["id"] in existing_ids:
                for i, old_t in enumerate(_todos):
                    if old_t["id"] == new_t["id"]:
                        _todos[i] = new_t
                        break
            else:
                _todos.append(new_t)
    else:
        _todos = todos
    
    # Validate only one in_progress
    in_progress = [t for t in _todos if t["status"] == "in_progress"]
    if len(in_progress) > 1:
        return ToolResult(
            success=False,
            error=f"Only one task can be in_progress at a time. Found {len(in_progress)}: {[t['id'] for t in in_progress]}"
        )
    
    return tool_todo_write([])  # Show updated list


def tool_task_complete_tool(summary: str) -> ToolResult:
    """Signal that the coding task is complete. Call this when finished.

    summary: Brief summary of what was accomplished
    """
    return ToolResult(
        success=True,
        output=f"✅ Task completed: {summary}",
        metadata={"task_complete": True},
    )


# ═══════════════════════════════════════════════════════════════════
# INTERACTIVE TOOLS
# ═══════════════════════════════════════════════════════════════════

def tool_ask_user_question(questions: list[dict]) -> ToolResult:
    """Ask the user clarifying questions when multiple valid approaches exist.

    Each question is presented with 2-4 options. The user selects one
    (or types their own answer for the implicit 5th "Other" option).

    questions: List of question objects:
        - question (str): The complete question to ask
        - header (str): Short label, max 12 characters
        - options (list): 2-4 choices, each with:
            - label (str): Short option label
            - description (str): What this option means
        - multiSelect (bool, optional): Allow multiple selections

    Example:
        [{
            "question": "Which database should we use for this project?",
            "header": "Database",
            "options": [
                {"label": "PostgreSQL", "description": "Full-featured, ACID, great for complex queries"},
                {"label": "SQLite", "description": "Zero-config, file-based, perfect for small projects"},
                {"label": "MongoDB", "description": "Document store, flexible schema, good for rapid dev"}
            ]
        }]

    IMPORTANT: This tool will pause execution. The user's answers will be
    returned as structured data for you to act on.
    """
    if not questions:
        return ToolResult(success=False, error="No questions provided. Must include at least one question object.")
    
    for i, q in enumerate(questions):
        if "question" not in q or "options" not in q:
            return ToolResult(success=False, error=f"Question {i} missing required fields (question, options)")
        opts = q["options"]
        if not (2 <= len(opts) <= 4):
            return ToolResult(success=False, error=f"Question {i}: must have 2-4 options, got {len(opts)}")
    
    # Mark as needing user interaction
    return ToolResult(
        success=True,
        output="[INTERACTIVE] Questions presented to user. Awaiting response...",
        metadata={
            "interactive": True,
            "questions": questions,
        },
    )


# ═══════════════════════════════════════════════════════════════════
# PLAN TOOLS (stubs — full implementation in agent/plan.py)
# ═══════════════════════════════════════════════════════════════════

_plan_mode = False
_plan_data: dict = {}


def tool_enter_plan_mode() -> ToolResult:
    """Enter plan mode: read-only exploration before making changes.

    In plan mode, you can:
    - Read files, search code, browse the web
    - Ask the user clarifying questions
    - Present a structured plan

    You CANNOT:
    - Write or edit files
    - Run shell commands that modify anything

    When your plan is ready, call exit_plan_mode() to present it.
    """
    global _plan_mode
    _plan_mode = True
    return ToolResult(
        success=True,
        output=(
            "📋 Entered PLAN MODE. You are now in read-only exploration.\n"
            "- Research the codebase, gather context, and design your approach.\n"
            "- Use ask_user_question() to resolve ambiguities.\n"
            "- When ready, call exit_plan_mode() with your structured plan."
        ),
        metadata={"plan_mode": True},
    )


def tool_exit_plan_mode(plan: str) -> ToolResult:
    """Exit plan mode and present your implementation plan for approval.

    Your plan should include:
    1. What you'll build (architecture, components)
    2. File changes needed (create, modify, delete)
    3. Implementation order (step by step)
    4. Testing strategy
    5. Any risks or alternatives considered

    plan: Complete implementation plan as markdown text

    After this, the user will choose:
    - Approve and execute
    - Refine the plan
    - Save for later
    """
    global _plan_mode, _plan_data
    if not _plan_mode:
        return ToolResult(success=False, error="Not in plan mode. Call enter_plan_mode() first.")
    
    _plan_mode = False
    _plan_data = {"plan": plan, "timestamp": time.time()}
    
    return ToolResult(
        success=True,
        output=(
            "📋 PLAN PRESENTED FOR APPROVAL:\n\n"
            f"{plan}\n\n"
            "---\n"
            "Waiting for user approval. Options:\n"
            "1. Approve and execute\n"
            "2. Refine with feedback\n"
            "3. Save to .hermes/plans/"
        ),
        metadata={"plan_exit": True, "plan": plan},
    )


# ═══════════════════════════════════════════════════════════════════
# CONTEXT TOOL
# ═══════════════════════════════════════════════════════════════════

def tool_compact_context(instructions: str = "") -> ToolResult:
    """Compress the conversation history to save context space.

    This summarizes completed work so the model can continue with
    more complex tasks. It preserves:
    - Project context (SOM.md)
    - Key decisions and errors
    - Active file state
    - Last few turns for continuity

    instructions: Optional guidance on what to emphasize (e.g.,
                  "Focus on the API design decisions and keep all error messages")

    After compaction, you'll get a fresh context with:
    - A summary of everything done so far
    - Current file and test state
    - The original task goal
    - The most recent conversation turns
    """
    return ToolResult(
        success=True,
        output=(
            "📦 Context compaction requested.\n"
            f"{'Instructions: ' + instructions if instructions else 'No special instructions.'}\n\n"
            "The harness will summarize the conversation and re-inject project context, "
            "memory, and loaded skills into a fresh context window."
        ),
        metadata={"compact_requested": True, "instructions": instructions},
    )


# ═══════════════════════════════════════════════════════════════════
# SUBAGENT SCAFFOLDING TOOLS
# ═══════════════════════════════════════════════════════════════════

_SUBAGENT_IGNORE = {'.git', 'node_modules', 'dist', '.som-code', '.venv', '__pycache__'}


def _workspace_root(sandbox: SubprocessSandbox = None) -> Path:
    return Path(sandbox.workspace if sandbox else os.getcwd()).resolve()


def _safe_walk(root: Path, limit: int = 120) -> list[str]:
    files: list[str] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [d for d in sorted(dirs) if d not in _SUBAGENT_IGNORE]
        rel_dir = Path(current).relative_to(root)
        for name in sorted(names):
            if len(files) >= limit:
                return files
            rel = (rel_dir / name) if str(rel_dir) != '.' else Path(name)
            files.append(str(rel))
    return files


def tool_subagent_repo_map(sandbox: SubprocessSandbox = None, limit: int = 120) -> ToolResult:
    """Read-only repo-map subagent scaffold: summarize workspace structure."""
    root = _workspace_root(sandbox)
    files = _safe_walk(root, limit=limit)
    lines = [f"Workspace: {root}", f"Files mapped: {len(files)}", "", "Files:"]
    lines.extend(f"- {path}" for path in files)
    return ToolResult(success=True, output="\n".join(lines), metadata={"subagent": "repo_map", "files": files})


def tool_subagent_review(focus: str = "general", sandbox: SubprocessSandbox = None) -> ToolResult:
    """Read-only review subagent scaffold: inspect repo shape and suggest review checklist."""
    root = _workspace_root(sandbox)
    files = _safe_walk(root, limit=80)
    important = [p for p in files if p.endswith(('.py', '.ts', '.tsx', '.js', '.json', '.md', '.yml', '.yaml'))][:40]
    output = [
        f"Read-only review scaffold for focus: {focus}",
        f"Workspace: {root}",
        "This scaffold does not modify files or execute commands.",
        "",
        "Suggested review checklist:",
        "- Verify requested scope against changed files before editing.",
        "- Inspect tests/config/package metadata first.",
        "- Check permission mode before write/shell tools.",
        "- Require task_complete only after tests or explicit verification.",
        "",
        "High-signal files to inspect:",
    ]
    output.extend(f"- {path}" for path in important)
    return ToolResult(success=True, output="\n".join(output), metadata={"subagent": "review", "focus": focus, "files": important})


def tool_subagent_test_plan(sandbox: SubprocessSandbox = None) -> ToolResult:
    """Safe test subagent scaffold: suggest likely test commands without running them."""
    root = _workspace_root(sandbox)
    candidates = []
    if (root / 'package.json').exists():
        candidates.append('npm test')
        candidates.append('npm run typecheck')
    if (root / 'pyproject.toml').exists() or (root / 'pytest.ini').exists() or (root / 'tests').exists():
        candidates.append('python3 -m unittest discover -s tests')
    if (root / 'go.mod').exists():
        candidates.append('go test ./...')
    if not candidates:
        candidates.append('No obvious test command detected; inspect project files first.')
    output = [
        "Safe test-plan scaffold. No commands were executed.",
        f"Workspace: {root}",
        "Suggested verification commands:",
    ]
    output.extend(f"- {cmd}" for cmd in candidates)
    return ToolResult(success=True, output="\n".join(output), metadata={"subagent": "test_plan", "commands": candidates})


# REGISTRY BUILDER
# ═══════════════════════════════════════════════════════════════════

def create_som_tools(sandbox: SubprocessSandbox) -> BaseToolRegistry:
    """Create a complete ToolRegistry with all Som CLI coding tools."""
    
    registry = BaseToolRegistry()
    registry.set_sandbox(sandbox)
    
    # ── File I/O ──
    @registry.register
    def read(path: str, offset: int = 0, limit: int = 500) -> ToolResult:
        """Read a file from the workspace with line numbers.

        path: Absolute or workspace-relative path to the file
        offset: Line number to start reading from (0-indexed, default: 0)
        limit: Maximum lines to return (default: 500)
        """
        if sandbox:
            return sandbox.read_file(path, offset=offset, limit=limit)
        try:
            with open(path, 'r') as f:
                lines = f.readlines()
            selected = lines[offset:offset + limit]
            return ToolResult(success=True, output=''.join(selected),
                metadata={"path": path, "total_lines": len(lines), "lines_returned": len(selected)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    @registry.register
    def write(path: str, content: str) -> ToolResult:
        """Create or overwrite a file.

        path: Absolute or workspace-relative path
        content: Complete file content
        """
        if sandbox:
            return sandbox.write_file(path, content)
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(content)
            return ToolResult(success=True, output=f"Wrote {len(content)} bytes to {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    @registry.register
    def ls(path: str = ".") -> ToolResult:
        """List files and directories.

        path: Directory to list (default: workspace root)
        """
        if sandbox:
            return sandbox.list_dir(path)
        try:
            entries = sorted(os.listdir(path))
            lines = []
            for name in entries:
                ep = os.path.join(path, name)
                t = "d" if os.path.isdir(ep) else "f"
                s = os.path.getsize(ep) if os.path.isfile(ep) else "-"
                lines.append(f"{t} {str(s):>8} {name}")
            return ToolResult(success=True, output='\n'.join(lines) or '(empty)')
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    @registry.register
    def edit(path: str, old_string: str, new_string: str, replace_all: bool = False) -> ToolResult:
        """Make targeted edits by finding and replacing text (fuzzy match).
        
        path: File path
        old_string: Text to find (must be unique unless replace_all=True)
        new_string: Replacement text
        replace_all: Replace all occurrences instead of requiring unique match
        """
        return tool_edit(path, old_string, new_string, replace_all, sandbox)
    
    # ── Search ──
    @registry.register
    def grep(pattern: str, path: str = ".", glob: str = "*", limit: int = 50) -> ToolResult:
        """Search file contents with regex (ripgrep-backed).

        pattern: Regex pattern
        path: Directory or file to search
        glob: File pattern filter (e.g., '*.py')
        limit: Max results
        """
        return tool_grep(pattern, path, glob, limit, sandbox)
    
    @registry.register
    def glob_tool(pattern: str, path: str = ".") -> ToolResult:
        """Find files matching a glob pattern.

        pattern: Glob pattern (e.g., '**/*.py', 'src/**/*test*')
        path: Directory to search
        """
        return tool_glob(pattern, path, sandbox)
    
    # ── Execution ──
    @registry.register
    def bash(command: str, timeout: int = 120, workdir: str = None) -> ToolResult:
        """Execute a shell command.

        command: Shell command to execute
        timeout: Max seconds (default: 120)
        workdir: Working directory relative to workspace
        """
        if sandbox:
            return sandbox.exec(command, timeout=timeout, workdir=workdir)
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=workdir or '.')
            return ToolResult(
                success=proc.returncode == 0,
                output=proc.stdout or '',
                error=proc.stderr or '',
                exit_code=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error=f"Timed out after {timeout}s")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    # ── Web ──
    @registry.register
    def web_fetch(url: str) -> ToolResult:
        """Fetch and extract text from a URL.

        url: The URL (must start with http:// or https://)
        """
        return tool_web_fetch(url)
    
    @registry.register
    def web_search(query: str, num_results: int = 5) -> ToolResult:
        """Search the web (DuckDuckGo).

        query: Search query
        num_results: Number of results (default: 5, max: 10)
        """
        return tool_web_search(query, num_results)
    
    # ── Task Management ──
    @registry.register
    def todo_write(todos: list[dict] = None, merge: bool = False) -> ToolResult:
        """Track tasks through complex multi-step work.

        todos: List of {id, content, status} objects. Omit to view current list.
        merge: Update existing + add new (True) or replace all (False)

        Status: pending, in_progress, completed, cancelled
        """
        return tool_todo_write(todos or [], merge)
    
    @registry.register
    def task_complete(summary: str) -> ToolResult:
        """Signal task completion. Call when done.

        summary: What was accomplished
        """
        return tool_task_complete_tool(summary)
    
    # ── Interactive ──
    @registry.register
    def ask_user_question(questions: list[dict]) -> ToolResult:
        """Ask the user clarifying questions with multiple-choice options.

        questions: List of {question, header, options, multiSelect?} objects.
                   Each option: {label, description}. 2-4 options per question.
        """
        return tool_ask_user_question(questions)
    
    @registry.register
    def enter_plan_mode() -> ToolResult:
        """Enter read-only planning mode before making changes.
        Research, explore, and design before writing code.
        """
        return tool_enter_plan_mode()
    
    @registry.register
    def exit_plan_mode(plan: str) -> ToolResult:
        """Present your implementation plan for user approval.
        
        plan: Complete plan as markdown (architecture, file changes, order, testing)
        """
        return tool_exit_plan_mode(plan)
    
    # ── Context ──
    @registry.register
    def compact_context(instructions: str = "") -> ToolResult:
        """Compress conversation history to save context space.

        instructions: Optional guidance on what to emphasize
        """
        return tool_compact_context(instructions)
    
    # ── Skills ──
    from harness.skills import get_skill_loader
    
    @registry.register
    def skill_search(query: str) -> ToolResult:
        """Search available skills by keyword.

        query: What to search for (e.g., 'python', 'debugging')
        """
        loader = get_skill_loader()
        results = loader.search(query)
        if not results:
            return ToolResult(success=True, output=f"No skills found matching '{query}'.")
        lines = [f"Found {len(results)} skill(s) matching '{query}':"]
        for s in results:
            lines.append(f"- **{s.name}**: {s.description}")
        return ToolResult(success=True, output="\n".join(lines))
    
    @registry.register
    def skill_view(name: str) -> ToolResult:
        """Load and view a skill's full instructions.

        name: Exact skill name
        """
        loader = get_skill_loader()
        skill = loader.get(name)
        if not skill:
            available = [s.name for s in loader.list_all()]
            return ToolResult(success=False, error=f"Skill '{name}' not found. Available: {', '.join(available[:20])}")
        return ToolResult(success=True, output=f"# {skill.name} (v{skill.version})\n\n{skill.body}")
    
    @registry.register
    def skill_list() -> ToolResult:
        """List all available skills."""
        loader = get_skill_loader()
        skills = loader.list_all()
        if not skills:
            return ToolResult(success=True, output="No skills available.")
        lines = [f"Available skills ({len(skills)}):"]
        for s in skills:
            lines.append(f"- **{s.name}**: {s.description}")
        return ToolResult(success=True, output="\n".join(lines))
    
    @registry.register
    def subagent_repo_map(limit: int = 120) -> ToolResult:
        """Run a safe read-only repo-map subagent scaffold.

        limit: Maximum number of files to include
        """
        return tool_subagent_repo_map(sandbox, limit)

    @registry.register
    def subagent_review(focus: str = "general") -> ToolResult:
        """Run a safe read-only review subagent scaffold.

        focus: Review focus, e.g. security, tests, packaging, architecture
        """
        return tool_subagent_review(focus, sandbox)

    @registry.register
    def subagent_test_plan() -> ToolResult:
        """Run a safe test-planning subagent scaffold without executing commands."""
        return tool_subagent_test_plan(sandbox)

    return registry
