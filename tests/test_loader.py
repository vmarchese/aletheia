from aletheia.agents.instructions_loader import Loader
import os

def test_loader_finds_timeline_instructions():
    loader = Loader()
    # verify expected path exists
    expected_path = loader.prompts_dir / "timeline/timeline_json_instructions.md"
    assert expected_path.exists(), f"File not found at {expected_path}"
    
    # verify load function
    content = loader.load("timeline", "json_instructions")
    assert "TimelineAgent" in content
    assert "Structure" in content or "JSON" in content
