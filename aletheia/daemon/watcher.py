"""Polling-based file watcher for skills and custom commands directories."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


class ConfigWatcher:
    """Watches skills and commands directories for changes and triggers reload.

    Uses polling (2s interval) to detect file modifications, additions,
    and deletions. Follows the same pattern as engram.watcher.MemoryWatcher.

    Args:
        skills_directories: List of skill directory paths to watch.
        commands_directory: Path to the custom commands directory.
        on_skills_changed: Callback invoked when skill files change.
        on_commands_changed: Callback invoked when command files change.
        poll_interval: Polling interval in seconds (default 2.0).
    """

    def __init__(
        self,
        skills_directories: list[str],
        commands_directory: str,
        on_skills_changed: Callable[[], None],
        on_commands_changed: Callable[[], None],
        poll_interval: float = 2.0,
    ) -> None:
        self._skills_directories = skills_directories
        self._commands_directory = commands_directory
        self._on_skills_changed = on_skills_changed
        self._on_commands_changed = on_commands_changed
        self._poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._skills_mtimes: dict[Path, float] = {}
        self._commands_mtimes: dict[Path, float] = {}

    def start(self) -> None:
        """Start the watcher in a daemon thread."""
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._skills_mtimes = self._snapshot_skills()
        self._commands_mtimes = self._snapshot_commands()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("ConfigWatcher started")

    def stop(self) -> None:
        """Stop the watcher thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("ConfigWatcher stopped")

    def _watched_skill_files(self) -> list[Path]:
        """Get list of SKILL.md files to watch across all skill directories."""
        files: list[Path] = []
        for skills_dir in self._skills_directories:
            skills_path = Path(skills_dir)
            if not skills_path.exists():
                continue
            # Watch all agent subdirectories and their skill subdirectories
            for agent_dir in skills_path.iterdir():
                if not agent_dir.is_dir():
                    continue
                for skill_dir in agent_dir.iterdir():
                    if not skill_dir.is_dir():
                        continue
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        files.append(skill_file)
        return files

    def _watched_command_files(self) -> list[Path]:
        """Get list of command .md files to watch."""
        commands_path = Path(self._commands_directory)
        if not commands_path.exists():
            return []
        return sorted(commands_path.glob("*.md"))

    def _snapshot_skills(self) -> dict[Path, float]:
        """Get current mtimes for all watched skill files."""
        snapshot: dict[Path, float] = {}
        for f in self._watched_skill_files():
            try:
                snapshot[f] = f.stat().st_mtime
            except OSError:
                pass
        return snapshot

    def _snapshot_commands(self) -> dict[Path, float]:
        """Get current mtimes for all watched command files."""
        snapshot: dict[Path, float] = {}
        for f in self._watched_command_files():
            try:
                snapshot[f] = f.stat().st_mtime
            except OSError:
                pass
        return snapshot

    def _poll_loop(self) -> None:
        """Main polling loop."""
        while not self._stop_event.is_set():
            try:
                # Check skills
                current_skills = self._snapshot_skills()
                if self._has_changes(self._skills_mtimes, current_skills):
                    logger.info("ConfigWatcher: skill files changed, triggering reload")
                    self._skills_mtimes = current_skills
                    try:
                        self._on_skills_changed()
                    except Exception as e:
                        logger.error(f"ConfigWatcher: error in skills callback: {e}")

                # Check commands
                current_commands = self._snapshot_commands()
                if self._has_changes(self._commands_mtimes, current_commands):
                    logger.info(
                        "ConfigWatcher: command files changed, triggering reload"
                    )
                    self._commands_mtimes = current_commands
                    try:
                        self._on_commands_changed()
                    except Exception as e:
                        logger.error(f"ConfigWatcher: error in commands callback: {e}")

            except Exception:
                logger.debug("ConfigWatcher: poll_error")
            self._stop_event.wait(self._poll_interval)

    @staticmethod
    def _has_changes(
        old_snapshot: dict[Path, float], new_snapshot: dict[Path, float]
    ) -> bool:
        """Check if there are any changes between two snapshots."""
        # Check for new or modified files
        for path, mtime in new_snapshot.items():
            old_mtime = old_snapshot.get(path)
            if old_mtime is None or mtime > old_mtime:
                return True
        # Check for deleted files
        for path in old_snapshot:
            if path not in new_snapshot:
                return True
        return False

    @staticmethod
    def get_skills_directories(config: object) -> list[str]:
        """Build the list of skills directories from config and env vars.

        Args:
            config: Aletheia Config object with skills_directory attribute.

        Returns:
            List of skills directory paths.
        """
        skills_directory = getattr(config, "skills_directory", None)
        directories = [skills_directory] if skills_directory else []

        user_skills_dirs = os.getenv("ALETHEIA_USER_SKILLS_DIRS")
        if user_skills_dirs:
            for dir_path in user_skills_dirs.split(os.pathsep):
                if dir_path.strip():
                    directories.append(dir_path.strip())

        return directories
