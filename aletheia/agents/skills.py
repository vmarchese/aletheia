"""
Defines the SkillLoader class for loading skills with hierarchical structure.

New structure:
skill_folder/
  agent_name/
    skill_name/
      instructions.yaml
      scripts/
        script1.py
        script2.py
"""
from pathlib import Path
from typing import Annotated, List, Optional, Sequence
import yaml


class Skill:
    """Represents a skill with its metadata and scripts."""
    def __init__(self,
                 name: str,
                 instructions: str,
                 description: str,
                 path: str,
                 scripts: Optional[List] = None,
                 scripts_dir: Optional[str] = None):
        self.name = name
        self.instructions = instructions
        self.description = description
        self.path = path
        self.scripts = scripts if scripts else []
        self.scripts_dir = scripts_dir


class SkillLoader:
    """
    Loads skills from a hierarchical directory structure.

    Expected structure:
    skills_directory/
      agent_name/
        skill_name/
          instructions.yaml
          scripts/
            *.py
    """
    def __init__(self, 
                 skills_directory: str):
        self.skills_directory = skills_directory
        self.skills = self.load_skills()

    def load_skill(self, skill_dir: Path) -> Optional[Skill]:
        """
        Loads a single skill from a directory.

        Args:
            skill_dir: Path to the skill directory

        Returns:
            Skill object if successfully loaded, None otherwise
        """
        instructions_file = skill_dir / "instructions.yaml"

        # Check if instructions.yaml exists
        if not instructions_file.exists():
            return None

        try:
            # Load skill metadata from instructions.yaml
            with open(instructions_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            # Expecting 'name' and 'description' in the YAML
            name = data.get('name')
            description = data.get('description')

            if not name or not description:
                return None

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
                instructions=instructions_file,
                description=description,
                path=str(skill_dir.absolute()),
                scripts=script_files,
                scripts_dir=str(scripts_dir.absolute()) if scripts_dir.exists() else None)

        except (OSError, yaml.YAMLError):
            # Silently skip invalid skill files
            return None

    def load_skills(self) -> Sequence[Skill]:
        """
        Loads skills from the hierarchical directory structure.

        Discovers skills organized by agent, where each skill contains:
        - instructions.yaml: Skill definition and instructions
        - scripts/: Optional directory containing Python scripts
        """
        skills_path = Path(self.skills_directory)

        if not skills_path.exists():
            return []

        # Iterate through skill directories within each agent
        _skills = []
        for skill_dir in skills_path.iterdir():
            if not skill_dir.is_dir():
                continue

            skill = self.load_skill(skill_dir)
            if skill:
                _skills.append(skill)

        return _skills

    def get_skill_instructions(self,
                               location: Annotated[str, "Path to the skill instructions file"]) -> str:
        """
        Loads skill instructions from a file.

        Args:
            location: Path to the instructions.yaml file

        Returns:
            String content of the instructions
        """
        if location.endswith("instructions.yaml"):
            location = str(Path(location).parent)
        print(f"Loading skill from: {location}")
        with open(f"{location}/instructions.yaml", 'r', encoding='utf-8') as file:
            skill_info = yaml.safe_load(file)
            instructions = skill_info.get('instructions', '')
        return instructions

