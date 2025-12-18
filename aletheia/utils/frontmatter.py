"""
Frontmatter parsing utilities for agent responses.
"""
from typing import Optional, Dict, Any, Tuple
import yaml


class FrontmatterParser:
    """Parser for agent responses with YAML frontmatter."""

    @staticmethod
    def parse_incremental(buffer: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Parse YAML frontmatter from an incremental buffer.

        Args:
            buffer: Accumulated response text that may contain frontmatter

        Returns:
            Tuple of:
            - frontmatter_complete: Whether frontmatter has been fully parsed
            - frontmatter: Parsed frontmatter dict (None if not complete)
            - content: The content after frontmatter (may be empty if still accumulating)
        """
        if not buffer.startswith("---"):
            # No frontmatter detected
            return True, None, buffer

        # Check if we have the closing ---
        parts = buffer.split("---", 2)
        if len(parts) < 3:
            # Frontmatter not complete yet
            return False, None, ""

        # Frontmatter is complete
        try:
            frontmatter = yaml.safe_load(parts[1])
            content = parts[2]
            return True, frontmatter, content
        except yaml.YAMLError:
            # Invalid YAML, treat as no frontmatter
            return True, None, buffer

    @staticmethod
    def parse(text: str) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Parse YAML frontmatter from complete text.

        Args:
            text: Complete response text that may contain frontmatter

        Returns:
            Tuple of (frontmatter dict or None, content without frontmatter)
        """
        if not text.startswith("---"):
            return None, text

        parts = text.split("---", 2)
        if len(parts) < 3:
            return None, text

        try:
            frontmatter = yaml.safe_load(parts[1])
            content = parts[2].lstrip("\n")  # Remove leading newlines after frontmatter
            return frontmatter, content
        except yaml.YAMLError:
            return None, text
