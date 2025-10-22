from pathlib import Path

class Loader:
    def __init__(self):
        package_dir = Path(__file__).parent.parent
        self.prompts_dir = package_dir / "prompts"

    def load(self, agent_name: str, type: str) -> str:
        prompt_file = self.prompts_dir / f"{agent_name}_{type}.md"
        with open(prompt_file, 'r') as file:
            content = file.read()
        return content