"""
Defines the SkillLoader class for loading skills with Skills Open Format.

Expected structure:
skill_folder/
  skill_name/
    SKILL.md
    scripts/
      script1.py
      script2.py

SKILL.md format (Skills Open Format):
---
name: skill-name
description: Skill description
license: Apache-2.0 (optional)
metadata:
  author: example-org (optional)
  version: "1.0" (optional)
---
Markdown instructions content
"""
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional, Sequence
import re
import yaml


class Skill:
    """Represents a skill with its metadata and scripts."""
    def __init__(self,
                 name: str,
                 instructions: str,
                 description: str,
                 path: str,
                 scripts: Optional[List] = None,
                 scripts_dir: Optional[str] = None,
                 license: Optional[str] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.name = name
        self.instructions = instructions
        self.description = description
        self.path = path
        self.scripts = scripts if scripts else []
        self.scripts_dir = scripts_dir
        self.license = license
        self.metadata = metadata if metadata else {}


class SkillLoader:
    """
    Loads skills from a directory structure following Skills Open Format.

    Expected structure:
    skills_directory/
      skill_name/
        SKILL.md
        scripts/
          *.py
    """
    def __init__(self,
                 skills_directory: str):
        self.skills_directory = skills_directory
        self.skills = self.load_skills()

    @staticmethod
    def parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
        """
        Parses YAML frontmatter from markdown content.

        Args:
            content: Full markdown file content

        Returns:
            Tuple of (frontmatter dict, markdown content)
        """
        # Match YAML frontmatter pattern: ---\n...yaml...\n---\n
        pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return {}, content

        try:
            frontmatter = yaml.safe_load(match.group(1))
            markdown_content = match.group(2).strip()
            return frontmatter if frontmatter else {}, markdown_content
        except yaml.YAMLError:
            return {}, content

    def load_skill(self, skill_dir: Path) -> Optional[Skill]:
        """
        Loads a single skill from a directory using Skills Open Format.

        Args:
            skill_dir: Path to the skill directory

        Returns:
            Skill object if successfully loaded, None otherwise
        """
        skill_file = skill_dir / "SKILL.md"

        # Check if SKILL.md exists
        if not skill_file.exists():
            return None

        try:
            # Read SKILL.md file
            with open(skill_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse frontmatter and content
            frontmatter, instructions = self.parse_frontmatter(content)

            # Extract required fields
            name = frontmatter.get('name')
            description = frontmatter.get('description')

            if not name or not description:
                return None

            # Extract optional fields
            license_info = frontmatter.get('license')
            metadata = frontmatter.get('metadata', {})

            # Discover scripts in the scripts/ subdirectory
            scripts_dir = skill_dir / "scripts"
            script_files = []

            if scripts_dir.exists() and scripts_dir.is_dir():
                script_files = [
                    {
                        "relative_path": str(script.relative_to(self.skills_directory)),
                        "absolute_path": str(script.absolute())
                    }
                    for script in scripts_dir.glob("*.py")
                ]

            # Create skill entry
            return Skill(
                name=name,
                instructions=instructions,
                description=description,
                path=str(skill_dir.absolute()),
                scripts=script_files,
                scripts_dir=str(scripts_dir.absolute()) if scripts_dir.exists() else None,
                license=license_info,
                metadata=metadata)

        except (OSError, yaml.YAMLError):
            # Silently skip invalid skill files
            return None

    def load_skills(self) -> Sequence[Skill]:
        """
        Loads skills from the directory structure using Skills Open Format.

        Discovers skills where each skill directory contains:
        - SKILL.md: Skill definition with YAML frontmatter and markdown instructions
        - scripts/: Optional directory containing Python scripts
        """
        skills_path = Path(self.skills_directory)

        if not skills_path.exists():
            return []

        # Iterate through skill directories
        _skills = []
        for skill_dir in skills_path.iterdir():
            if not skill_dir.is_dir():
                continue

            skill = self.load_skill(skill_dir)
            if skill:
                _skills.append(skill)

        return _skills

    def get_skill_instructions(self,
                               location: Annotated[str, "Path to the skill directory or SKILL.md file"]) -> str:
        """
        Loads skill instructions from a SKILL.md file.

        Args:
            location: Path to the skill directory or SKILL.md file

        Returns:
            String content of the markdown instructions (without frontmatter)
        """
        # Handle both directory path and direct SKILL.md path
        path = Path(location)
        if path.is_file() and path.name == "SKILL.md":
            skill_file = path
        else:
            skill_file = path / "SKILL.md"

        print(f"Loading skill from: {skill_file}")

        with open(skill_file, 'r', encoding='utf-8') as file:
            content = file.read()

        # Parse and return just the instructions (markdown content)
        _, instructions = self.parse_frontmatter(content)
        return instructions

    def load_file(self, 
                  location: Annotated[str, "Path to the skill directory"],
                  resource: Annotated[str, "Resource file name within the skill directory"]) -> str:
        """
        Loads a specific resource file from a skill directory.
        Args:
            location: Path to the skill directory
            resource: Resource file name within the skill directory
        Returns:

            String content of the resource file
        """
        resource_path = Path(resource)
        if resource_path.is_absolute() or ".." in resource_path.parts:
            raise ValueError("Resource must be a relative file name without path traversal.")
        skill_dir = Path(location)
        resource_file = skill_dir / resource
        with open(resource_file, 'r', encoding='utf-8') as file:
            content = file.read()
        return content

