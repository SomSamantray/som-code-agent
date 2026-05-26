"""
Skill loader — discovers, parses, and loads SKILL.md files.

Hermes-compatible: YAML frontmatter + markdown body.
Auto-discovers skills from directory trees.
Provides search and injection into system prompts.
"""
import os
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Skill:
    """A loaded skill from a SKILL.md file."""
    name: str
    description: str
    version: str = "1.0.0"
    category: str = ""
    path: str = ""
    body: str = ""           # Full markdown body
    frontmatter: dict = field(default_factory=dict)

    @property
    def preview(self) -> str:
        """Short preview for skill listings."""
        return f"**{self.name}** (v{self.version}): {self.description}"


class SkillLoader:
    """
    Discovers and loads SKILL.md files from directories.

    Format (Hermes-compatible):
        ---
        name: my-skill
        description: What this skill does
        version: 1.0.0
        ---

        # Skill Title
        ...markdown body...
    """

    def __init__(self, skills_dirs: list[str] = None):
        """
        Args:
            skills_dirs: Directories to scan for SKILL.md files.
                         Defaults to ~/.hermes/skills/ and ./skills/
        """
        self.skills_dirs = skills_dirs or [
            os.path.expanduser("~/.hermes/skills"),
            os.path.join(os.getcwd(), "skills"),
        ]
        self._skills: dict[str, Skill] = {}
        self._loaded = False

    def discover(self) -> dict[str, Skill]:
        """Scan all skills directories and load SKILL.md files."""
        if self._loaded:
            return self._skills

        for skills_dir in self.skills_dirs:
            if not os.path.isdir(skills_dir):
                continue

            for root, dirs, files in os.walk(skills_dir):
                # Skip hidden dirs
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                if "SKILL.md" in files:
                    skill_path = os.path.join(root, "SKILL.md")
                    try:
                        skill = self._parse_skill_file(skill_path)
                        if skill:
                            # Derive category from path relative to skills dir
                            rel = os.path.relpath(root, skills_dir)
                            if rel != ".":
                                skill.category = rel.replace(os.sep, "/")
                            self._skills[skill.name] = skill
                    except Exception as e:
                        print(f"  ⚠ Failed to load skill: {skill_path}: {e}")

        self._loaded = True
        return self._skills

    def search(self, query: str) -> list[Skill]:
        """
        Search loaded skills by name, description, or body content.
        Returns matching skills sorted by relevance.
        """
        self.discover()
        query_lower = query.lower()
        results = []

        for skill in self._skills.values():
            score = 0
            if query_lower in skill.name.lower():
                score += 10
            if query_lower in skill.description.lower():
                score += 5
            if query_lower in skill.body.lower():
                score += 1
            if score > 0:
                results.append((score, skill))

        results.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in results]

    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        self.discover()
        return self._skills.get(name)

    def list_all(self) -> list[Skill]:
        """Return all loaded skills."""
        self.discover()
        return sorted(self._skills.values(), key=lambda s: s.name)

    def inject_skills_prompt(self, skills: list[Skill] = None) -> str:
        """
        Generate a system prompt section with available skills.
        If skills is None, injects ALL loaded skills.
        """
        self.discover()
        skills = skills or list(self._skills.values())

        if not skills:
            return ""

        lines = ["## Available Skills"]
        lines.append("You have access to the following skills. Use skill_view(name) to load a skill's full instructions before tackling a related task.")
        lines.append("")

        for skill in skills:
            lines.append(f"- **{skill.name}**: {skill.description}")

        return "\n".join(lines)

    # ── Parsing ───────────────────────────────────────────────────────

    def _parse_skill_file(self, path: str) -> Optional[Skill]:
        """Parse a SKILL.md file with YAML frontmatter."""
        with open(path, "r") as f:
            content = f.read()

        # Parse YAML frontmatter between --- delimiters
        frontmatter = {}
        body = content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = self._parse_yaml_simple(parts[1])
                body = parts[2].strip()

        name = frontmatter.get("name", self._derive_name_from_path(path))
        description = frontmatter.get("description", "No description")
        version = frontmatter.get("version", "1.0.0")

        return Skill(
            name=name,
            description=description,
            version=version,
            path=path,
            body=body,
            frontmatter=frontmatter,
        )

    @staticmethod
    def _parse_yaml_simple(text: str) -> dict:
        """
        Lightweight YAML parser for frontmatter.
        Handles the common case without requiring PyYAML.
        """
        result = {}
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                result[key] = value
        return result

    @staticmethod
    def _derive_name_from_path(path: str) -> str:
        """Derive a skill name from its file path."""
        # e.g., /path/to/skills/my-skill/SKILL.md → my-skill
        parent = os.path.basename(os.path.dirname(path))
        return parent.replace(" ", "-").lower()


# ── Singleton for easy access ─────────────────────────────────────────

_default_loader: Optional[SkillLoader] = None


def get_skill_loader(skills_dirs: list[str] = None) -> SkillLoader:
    """Get or create the default skill loader."""
    global _default_loader
    if _default_loader is None or skills_dirs:
        _default_loader = SkillLoader(skills_dirs)
    return _default_loader
