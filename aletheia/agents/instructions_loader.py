from pathlib import Path

class Loader:
    def __init__(self):
        package_dir = Path(__file__).parent.parent
        self.prompts_dir = package_dir / "agents"

    def load(self, agent_name: str, type: str, prefix: str = "") -> str:
        instructions_file_name= f"{prefix}_{agent_name}_{type}.md" if prefix else f"{agent_name}_{type}.md"
        prompt_file = self.prompts_dir / f"{agent_name}/{instructions_file_name}"
        with open(prompt_file, 'r') as file:
            content = file.read()
        return content