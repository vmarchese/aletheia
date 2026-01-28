"""Polling-based file watcher for memory files."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from aletheia.utils.logging import log_debug, log_info


class MemoryWatcher:
    """Watches memory files for changes and triggers reindexing.

    Uses polling (2s interval) to detect file modifications.

    Args:
        root: Root directory of the memory identity.
        on_change: Callback invoked with the changed file path.
    """

    def __init__(
        self,
        root: Path,
        on_change: Callable[[Path], None],
        poll_interval: float = 2.0,
    ) -> None:
        self._root = root
        self._on_change = on_change
        self._poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._mtimes: dict[Path, float] = {}

    def start(self) -> None:
        """Start the watcher in a daemon thread."""
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._mtimes = self._snapshot()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the watcher thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _watched_files(self) -> list[Path]:
        """Get list of files to watch."""
        files: list[Path] = []
        memory_file = self._root / "MEMORY.md"
        if memory_file.exists():
            files.append(memory_file)
        memory_dir = self._root / "memory"
        if memory_dir.exists():
            files.extend(sorted(memory_dir.glob("*.md")))
        return files

    def _snapshot(self) -> dict[Path, float]:
        """Get current mtimes for all watched files."""
        return {f: f.stat().st_mtime for f in self._watched_files()}

    def _poll_loop(self) -> None:
        """Main polling loop."""
        while not self._stop_event.is_set():
            try:
                current = self._snapshot()
                for path, mtime in current.items():
                    old_mtime = self._mtimes.get(path)
                    if old_mtime is None or mtime > old_mtime:
                        log_info(f"file_changed path={path}")
                        self._on_change(path)
                self._mtimes = current
            except Exception:
                log_debug("poll_error")
            self._stop_event.wait(self._poll_interval)
