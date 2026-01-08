"""Tests for custom command frontmatter support."""

from aletheia.commands import (
    parse_command_frontmatter,
    load_custom_command,
)


class TestFrontmatterParsing:
    """Test YAML frontmatter parsing functionality."""

    def test_parse_valid_frontmatter(self):
        """Test parsing valid YAML frontmatter."""
        content = """---
name: Test Command
description: A test command
---
Do something useful"""
        meta, instructions = parse_command_frontmatter(content)
        assert meta["name"] == "Test Command"
        assert meta["description"] == "A test command"
        assert instructions == "Do something useful"

    def test_parse_no_frontmatter(self):
        """Test parsing plain markdown without frontmatter (backward compatibility)."""
        content = "Just plain instructions"
        meta, instructions = parse_command_frontmatter(content)
        assert meta == {}
        assert instructions == content

    def test_parse_malformed_yaml(self):
        """Test error handling for malformed YAML."""
        content = """---
name: Test
invalid: [unclosed
---
Instructions"""
        meta, instructions = parse_command_frontmatter(content)
        # Should fallback to treating entire content as instructions
        assert meta == {}
        assert instructions == content

    def test_parse_empty_frontmatter(self):
        """Test parsing empty frontmatter section."""
        content = """---
---
Instructions"""
        meta, instructions = parse_command_frontmatter(content)
        # Empty frontmatter doesn't match the regex pattern, so entire content treated as instructions
        assert meta == {}
        assert instructions == content

    def test_parse_frontmatter_with_extra_fields(self):
        """Test parsing frontmatter with additional fields (should be ignored)."""
        content = """---
name: My Command
description: Does things
author: Test Author
version: 1.0
---
Do the thing"""
        meta, instructions = parse_command_frontmatter(content)
        assert meta["name"] == "My Command"
        assert meta["description"] == "Does things"
        assert "author" in meta  # Additional fields are preserved
        assert instructions == "Do the thing"

    def test_parse_multiline_instructions(self):
        """Test parsing with multiline instructions."""
        content = """---
name: Complex Command
description: Multi-line example
---
First line of instructions
Second line of instructions
Third line of instructions"""
        meta, instructions = parse_command_frontmatter(content)
        assert meta["name"] == "Complex Command"
        assert "First line" in instructions
        assert "Third line" in instructions


class TestCustomCommandLoading:
    """Test custom command loading from files."""

    def test_load_with_frontmatter(self, tmp_path):
        """Test loading command with full frontmatter."""
        cmd_file = tmp_path / "test.md"
        cmd_file.write_text(
            """---
name: My Command
description: Does things
---
Do the thing"""
        )

        cmd = load_custom_command("test", cmd_file)
        assert cmd is not None
        assert cmd.name == "My Command"
        assert cmd.description == "Does things"
        assert cmd.instructions == "Do the thing"
        assert cmd.file_path == cmd_file

    def test_load_without_frontmatter(self, tmp_path):
        """Test loading plain markdown file (backward compatibility)."""
        cmd_file = tmp_path / "simple.md"
        cmd_file.write_text("Just instructions")

        cmd = load_custom_command("simple", cmd_file)
        assert cmd is not None
        assert cmd.name == "Simple"  # Generated from filename
        assert cmd.description == "(from simple.md)"  # Fallback description
        assert cmd.instructions == "Just instructions"

    def test_load_with_underscored_filename(self, tmp_path):
        """Test name generation from filename with underscores."""
        cmd_file = tmp_path / "my_custom_command.md"
        cmd_file.write_text("Command instructions")

        cmd = load_custom_command("my_custom_command", cmd_file)
        assert cmd is not None
        assert cmd.name == "My Custom Command"  # Underscores replaced with spaces, title case
        assert cmd.instructions == "Command instructions"

    def test_load_with_minimal_valid_instructions(self, tmp_path):
        """Test loading with minimal but valid instructions."""
        cmd_file = tmp_path / "minimal.md"
        # A properly formed file with minimal instructions
        cmd_file.write_text("---\nname: Minimal\ndescription: Minimal test\n---\nX")

        cmd = load_custom_command("minimal", cmd_file)
        assert cmd is not None
        assert cmd.name == "Minimal"
        assert cmd.description == "Minimal test"
        assert cmd.instructions == "X"

    def test_load_only_frontmatter_no_separator(self, tmp_path):
        """Test handling of only frontmatter without closing separator."""
        cmd_file = tmp_path / "incomplete.md"
        cmd_file.write_text(
            """---
name: Incomplete
description: Missing closing separator"""
        )

        cmd = load_custom_command("incomplete", cmd_file)
        # Should treat entire content as instructions (no frontmatter detected)
        assert cmd is not None
        assert cmd.instructions.startswith("---")

    def test_load_partial_frontmatter(self, tmp_path):
        """Test loading with only name in frontmatter."""
        cmd_file = tmp_path / "partial.md"
        cmd_file.write_text(
            """---
name: Partial Command
---
Instructions here"""
        )

        cmd = load_custom_command("partial", cmd_file)
        assert cmd is not None
        assert cmd.name == "Partial Command"
        assert cmd.description == "(from partial.md)"  # Fallback description
        assert cmd.instructions == "Instructions here"

    def test_load_partial_frontmatter_description_only(self, tmp_path):
        """Test loading with only description in frontmatter."""
        cmd_file = tmp_path / "partial_desc.md"
        cmd_file.write_text(
            """---
description: Just a description
---
Do something"""
        )

        cmd = load_custom_command("partial_desc", cmd_file)
        assert cmd is not None
        assert cmd.name == "Partial Desc"  # Generated from filename
        assert cmd.description == "Just a description"
        assert cmd.instructions == "Do something"

    def test_load_file_not_found(self, tmp_path):
        """Test error handling when file doesn't exist."""
        cmd_file = tmp_path / "nonexistent.md"

        cmd = load_custom_command("nonexistent", cmd_file)
        assert cmd is None  # Should return None on error

    def test_load_file_with_utf8_content(self, tmp_path):
        """Test loading file with UTF-8 characters."""
        cmd_file = tmp_path / "unicode.md"
        cmd_file.write_text(
            """---
name: Unicode Command 🚀
description: Contains émojis and spëcial characters
---
List the Kubernetes pods ☸️""",
            encoding="utf-8",
        )

        cmd = load_custom_command("unicode", cmd_file)
        assert cmd is not None
        assert "🚀" in cmd.name
        assert "☸️" in cmd.instructions
