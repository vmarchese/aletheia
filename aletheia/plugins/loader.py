from pathlib import Path

class PluginInfoLoader:
    def __init__(self):
        package_dir = Path(__file__).parent.parent
        self.prompts_dir = package_dir

    def load(self, plugin_name: str)  -> str:
        prompt_file = self.prompts_dir / f"plugins/{plugin_name}.md"
        content = ""
        try:
            with open(prompt_file, 'r') as file:
                content = file.read()
        except FileNotFoundError:
            content = ""
        except Exception as e:
            content = ""
        return content