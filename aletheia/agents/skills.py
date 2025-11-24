"""
Defines the SkillLoader class for loading
"""
import os
from typing import Annotated
import yaml


class SkillLoader:
    """
    Loads skills from YAML files in a specified directory.
    """
    def __init__(self, skills_directory: str):
        self.skills_directory = skills_directory
        self.skills = []
        self.load_skills()

    def load_skills(self):
        """Loads skills from the specified directory."""
        for root, _, files in os.walk(self.skills_directory):
            for file in files:
                if file.endswith('.yml') or file.endswith('.yaml'):
                    path = os.path.join(root, file)
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            data = yaml.safe_load(f)
                            # Expecting 'name' and 'description' in each YAML
                            name = data.get('name')
                            description = data.get('description')
                            if name and description:
                                skill = {
                                    "name": name,
                                    "file": path,
                                    "description": description
                                }
                                self.skills.append(skill)
                    except (OSError, yaml.YAMLError):
                        pass

    def load_skill(self,
                   location: Annotated[str, "Path to the skill file"]) -> str:
        """Loads a skill from a file containing instructions."""
        print("Loading skill from:", location)
        with open(location, 'r', encoding='utf-8') as file:
            instructions = file.read()
        return instructions
