"""Main Engram class providing memory read/write/search tools."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from aletheia.utils.logging import log_debug, log_info

from .db import MemoryDB
from .embeddings import EmbeddingProvider
from .models import GetResponse, SearchResponse
from .watcher import MemoryWatcher


class Engram:
    """Multi-layered memory framework with markdown files + SQLite vector/FTS search.

    Args:
        identity: Root directory path for this memory identity.
        embedding_provider: An EmbeddingProvider instance. Defaults to OpenAI client.
    """

    def __init__(
        self,
        identity: str,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._root = Path(identity).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._memory_dir = self._root / "memory"
        self._memory_dir.mkdir(exist_ok=True)
        self._memory_file = self._root / "MEMORY.md"

        self._embedder = embedding_provider or EmbeddingProvider()

        db_path = self._root / ".engram" / "index.db"
        self._db = MemoryDB(db_path)
        self._watcher: MemoryWatcher | None = None
        log_info(
            f"engram_initialized root={self._root} provider={type(self._embedder).__name__} model={self._embedder.model_name}"
        )

    def __getstate__(self) -> dict[str, object]:
        state = self.__dict__.copy()
        state["_watcher"] = None
        return state

    def __setstate__(self, state: dict[str, object]) -> None:
        self.__dict__.update(state)

    def close(self) -> None:
        """Stop watcher and close database."""
        self.stop_watcher()
        self._db.close()

    def long_term_memory_write(self, memory: str) -> str:
        """Append a memory to MEMORY.md.

        Args:
            memory: The text to append.

        Returns:
            Confirmation message.
        """
        with open(self._memory_file, "a", encoding="utf-8") as f:
            f.write(f"\n{memory}\n")
        log_info(f"long_term_write file={self._memory_file}")
        log_debug(f"long_term_write_content memory={memory[:100]}")
        return f"Appended to {self._memory_file}"

    def daily_memory_write(self, memory: str) -> str:
        """Append a memory to today's daily file.

        Args:
            memory: The text to append.

        Returns:
            Confirmation message.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        daily_file = self._memory_dir / f"{today}.md"
        with open(daily_file, "a", encoding="utf-8") as f:
            f.write(f"\n{memory}\n")
        log_info(f"daily_write file={daily_file}")
        log_debug(f"daily_write_content memory={memory[:100]}")
        return f"Appended to {daily_file}"

    def read_daily_memories(self, n_of_days: int = 1) -> str:
        """Read the latest n days of daily memories.

        Args:
            n_of_days: Number of days to read (e.g., 2 = today and yesterday).

        Returns:
            Combined text from the daily files.
        """
        result_parts: list[str] = []
        today = datetime.now().date()
        for i in range(n_of_days):
            day = today - timedelta(days=i)
            daily_file = self._memory_dir / f"{day.isoformat()}.md"
            if daily_file.exists():
                text = daily_file.read_text(encoding="utf-8")
                result_parts.append(f"## {day.isoformat()}\n{text}")
        log_debug(f"read_daily n_of_days={n_of_days} files_found={len(result_parts)}")
        return "\n\n".join(result_parts) if result_parts else "No memories found."

    def read_long_term_memory(self) -> str:
        """Read the full contents of MEMORY.md (long-term memory).

        Returns:
            The text of the long-term memory file, or a message if empty/missing.
        """
        if not self._memory_file.exists():
            return "No long-term memories found."
        text = self._memory_file.read_text(encoding="utf-8")
        if not text.strip():
            return "No long-term memories found."
        log_debug(f"read_long_term length={len(text)}")
        return text

    def memory_search(
        self,
        query: str,
        max_results: int = 6,
        min_score: float = 0.35,
    ) -> dict:
        """Semantically search all memory files using hybrid vector + FTS.

        Args:
            query: Search query text.
            max_results: Maximum number of results.
            min_score: Minimum combined score threshold.

        Returns:
            SearchResponse with ranked results.
        """
        log_info(f"memory_search query={query[:80]} max_results={max_results}")
        embedding = self._embedder.embed(query)
        hits = self._db.hybrid_search(embedding, query, max_results, min_score)
        log_debug(f"memory_search_done results={len(hits)}")
        return SearchResponse(
            results=hits,
            provider=type(self._embedder).__name__,
            model=self._embedder.model_name,
        ).model_dump()

    def memory_get(self, path: str, from_line: int = 1, lines: int = 15) -> dict:
        """Read specific lines from a memory file.

        Args:
            path: Relative path to the memory file (e.g., "memory/2026-01-20.md").
            from_line: Starting line number (1-indexed).
            lines: Number of lines to read.

        Returns:
            GetResponse with the extracted text.
        """
        file_path = self._root / path
        if not file_path.exists():
            return GetResponse(path=path, text="").model_dump()
        all_lines = file_path.read_text(encoding="utf-8").splitlines()
        start = max(0, from_line - 1)
        end = start + lines
        selected = all_lines[start:end]
        return GetResponse(path=path, text="\n".join(selected)).model_dump()

    def index_all(self) -> None:
        """Manually reindex all memory files."""
        files_to_index: list[Path] = []
        if self._memory_file.exists():
            files_to_index.append(self._memory_file)
        files_to_index.extend(sorted(self._memory_dir.glob("*.md")))
        log_info(f"index_all_start file_count={len(files_to_index)}")
        for file_path in files_to_index:
            self._index_file(file_path)
        log_info(f"index_all_done file_count={len(files_to_index)}")

    def start_watcher(self) -> None:
        """Start the background file watcher."""
        if self._watcher is not None:
            return
        self._watcher = MemoryWatcher(self._root, self._index_file)
        self._watcher.start()
        log_info(f"watcher_started root={self._root}")

    def stop_watcher(self) -> None:
        """Stop the background file watcher."""
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None
            log_info("watcher_stopped")

    def _index_file(self, file_path: Path) -> None:
        """Chunk, embed, and index a single file."""
        from chonkie import TokenChunker

        log_debug(f"indexing_file path={file_path}")
        text = file_path.read_text(encoding="utf-8")
        if not text.strip():
            log_debug(f"indexing_skipped_empty path={file_path}")
            return

        chunker = TokenChunker(chunk_size=400, chunk_overlap=80)
        raw_chunks = chunker.chunk(text)
        log_debug(f"chunking_done path={file_path} chunks={len(raw_chunks)}")

        lines = text.splitlines()
        from .models import ChunkRecord

        chunks: list[ChunkRecord] = []
        for rc in raw_chunks:
            chunk_text = rc.text
            start_line = _find_line_number(lines, chunk_text)
            end_line = start_line + chunk_text.count("\n")
            chunks.append(
                ChunkRecord(
                    path=str(file_path.relative_to(self._root)),
                    start_line=start_line,
                    end_line=end_line,
                    text=chunk_text,
                    hash=hashlib.sha256(chunk_text.encode()).hexdigest(),
                )
            )

        # Get embeddings for all chunks in one batch
        log_debug(f"embedding_batch count={len(chunks)}")
        embeddings = self._embedder.embed_batch([c.text for c in chunks])

        rel_path = str(file_path.relative_to(self._root))
        self._db.index_file(rel_path, chunks, embeddings)

    def get_tools(self):
        """Get a list of available tool methods."""
        return [
            self.long_term_memory_write,
            self.daily_memory_write,
            self.read_daily_memories,
            self.read_long_term_memory,
            self.memory_search,
            self.memory_get,
        ]



def _find_line_number(lines: list[str], chunk_text: str) -> int:
    """Find the 1-indexed line number where chunk_text starts."""
    first_line = chunk_text.split("\n")[0]
    for i, line in enumerate(lines):
        if first_line in line:
            return i + 1
    return 1
