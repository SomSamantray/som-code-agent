"""
SOM.md Configuration System — project context injection.

Equivalent to Claude Code's CLAUDE.md and Codex CLI's AGENTS.md.

Resolution order (first found wins):
  1. SOM.local.md  (gitignored, personal preferences)
  2. .som/SOM.md   (project-local config dir)
  3. SOM.md         (project root)
  4. ~/.som/SOM.md  (global user config)

Supports @import syntax for including other files.
"""

import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SomConfig:
    """Parsed SOM.md configuration."""
    content: str
    path: str
    level: str  # local, project, global
    imports: list[str] = field(default_factory=list)


class SomConfigLoader:
    """
    Discovers and loads SOM.md files following the resolution hierarchy.
    """

    MAX_IMPORT_DEPTH = 5
    MAX_CONTENT_CHARS = 50_000

    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root or os.getcwd()).resolve()
        self._loaded: Optional[SomConfig] = None

    def discover(self) -> Optional[SomConfig]:
        """Find and load the appropriate SOM.md file."""
        if self._loaded:
            return self._loaded

        # Resolution order
        candidates = [
            (self.project_root / "SOM.local.md", "local"),
            (self.project_root / ".som" / "SOM.md", "project"),
            (self.project_root / "SOM.md", "project"),
            (Path.home() / ".som" / "SOM.md", "global"),
        ]

        for path, level in candidates:
            if path.exists():
                config = self._load_file(path, level)
                if config:
                    self._loaded = config
                    return config

        return None

    def _load_file(self, path: Path, level: str, depth: int = 0) -> Optional[SomConfig]:
        """Load a SOM.md file and resolve @import directives."""
        if depth > self.MAX_IMPORT_DEPTH:
            return None

        try:
            content = path.read_text()
        except Exception:
            return None

        imports = []
        
        # Resolve @import directives
        import_pattern = re.compile(r'^@import\s+"([^"]+)"\s*$', re.MULTILINE)
        for match in import_pattern.finditer(content):
            import_path = match.group(1)
            
            # Resolve relative imports
            if not import_path.startswith("/"):
                resolved = (path.parent / import_path).resolve()
            else:
                resolved = Path(import_path)
            
            if resolved.exists() and resolved != path:
                try:
                    imported_content = resolved.read_text()
                    # Replace @import with the actual content
                    content = content.replace(match.group(0), imported_content)
                    imports.append(str(resolved))
                except Exception:
                    content = content.replace(match.group(0), f"[Could not import: {import_path}]")

        # Truncate if too large
        if len(content) > self.MAX_CONTENT_CHARS:
            content = content[:self.MAX_CONTENT_CHARS] + "\n\n... (SOM.md truncated)"

        return SomConfig(
            content=content,
            path=str(path),
            level=level,
            imports=imports,
        )

    def get_system_prompt_block(self) -> str:
        """Generate the SOM.md section for the system prompt."""
        config = self.discover()
        if not config:
            return ""

        return (
            "## Project Context (SOM.md)\n"
            "The following is the project's SOM.md configuration. "
            "It describes conventions, architecture, and important project details. "
            "Follow these instructions.\n\n"
            f"{config.content}\n"
        )

    @staticmethod
    def create_default(project_root: str = None) -> str:
        """Create a default SOM.md template."""
        project_root = Path(project_root or os.getcwd())
        template = f"""# {project_root.name}

## Project Overview
[Brief description of this project]

## Tech Stack
- [Language/Framework]
- [Database]
- [Tools]

## Conventions
- [Coding style]
- [Naming conventions]
- [Commit message format]

## Commands
# Build: [command]
# Test: [command]
# Lint: [command]
# Run: [command]

## Architecture
# src/       — Source code
# tests/     — Tests
# docs/      — Documentation

## Important Notes
- [Any important project-specific information]
"""
        return template

    @staticmethod
    def init(project_root: str = None) -> str:
        """Initialize a SOM.md file in the project root."""
        project_root = Path(project_root or os.getcwd())
        project_root.mkdir(parents=True, exist_ok=True)
        path = project_root / "SOM.md"
        
        if path.exists():
            return f"SOM.md already exists at {path}"
        
        path.write_text(SomConfigLoader.create_default(str(project_root)))
        return f"Created SOM.md at {path}"
