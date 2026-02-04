"""SQLite database layer for engram: chunks, vector search, and FTS5."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec
import structlog

logger = structlog.get_logger(__name__)

from .models import ChunkRecord, SearchHit


def _load_extensions(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec extension."""
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    text TEXT NOT NULL,
    hash TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vector USING vec0(
    id INTEGER PRIMARY KEY,
    embedding FLOAT[1536]
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    content=chunks,
    content_rowid=id
);
"""


class MemoryDB:
    """SQLite database for memory chunk storage, vector search, and full-text search."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = self._connect()
        logger.info(f"database_opened path={db_path}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _load_extensions(conn)
        conn.executescript(_SCHEMA)
        conn.commit()
        return conn

    def __getstate__(self) -> dict[str, object]:
        state = self.__dict__.copy()
        del state["_conn"]
        return state

    def __setstate__(self, state: dict[str, object]) -> None:
        self.__dict__.update(state)
        self._conn = self._connect()

    def close(self) -> None:
        self._conn.close()

    def index_file(
        self,
        path: str,
        chunks: list[ChunkRecord],
        embeddings: list[list[float]],
    ) -> None:
        """Delete old chunks for path and insert new ones."""
        logger.debug(f"index_file_start path={path} num_chunks={len(chunks)}")
        cur = self._conn.cursor()

        # Get existing IDs for this path to clean up vector/fts tables
        existing_ids = [
            row[0]
            for row in cur.execute(
                "SELECT id FROM chunks WHERE path = ?", (path,)
            ).fetchall()
        ]

        if existing_ids:
            logger.debug(f"removing_old_chunks path={path} count={len(existing_ids)}")
            placeholders = ",".join("?" for _ in existing_ids)
            cur.execute(
                f"DELETE FROM chunks_vector WHERE id IN ({placeholders})",
                existing_ids,
            )
            # FTS5 content-sync: delete via special command
            for cid in existing_ids:
                row = cur.execute(
                    "SELECT text FROM chunks WHERE id = ?", (cid,)
                ).fetchone()
                if row:
                    fts_del = (
                        "INSERT INTO chunks_fts"
                        "(chunks_fts, rowid, text)"
                        " VALUES('delete', ?, ?)"
                    )
                    cur.execute(fts_del, (cid, row[0]))
            cur.execute(
                f"DELETE FROM chunks WHERE id IN ({placeholders})",
                existing_ids,
            )

        # Insert new chunks
        for chunk, embedding in zip(chunks, embeddings):
            insert_sql = (
                "INSERT INTO chunks"
                " (path, start_line, end_line, text, hash)"
                " VALUES (?, ?, ?, ?, ?)"
            )
            cur.execute(
                insert_sql,
                (chunk.path, chunk.start_line, chunk.end_line, chunk.text, chunk.hash),
            )
            row_id = cur.lastrowid
            cur.execute(
                "INSERT INTO chunks_vector (id, embedding) VALUES (?, ?)",
                (row_id, sqlite_vec.serialize_float32(embedding)),
            )
            cur.execute(
                "INSERT INTO chunks_fts (rowid, text) VALUES (?, ?)",
                (row_id, chunk.text),
            )

        self._conn.commit()
        logger.info(f"file_indexed path={path} chunks_inserted={len(chunks)}")

    def vector_search(
        self, embedding: list[float], limit: int = 20
    ) -> list[tuple[int, float]]:
        """Return (chunk_id, distance) pairs sorted by distance ascending."""
        rows = self._conn.execute(
            """
            SELECT id, distance
            FROM chunks_vector
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
            """,
            (sqlite_vec.serialize_float32(embedding), limit),
        ).fetchall()
        return [(row[0], float(row[1])) for row in rows]

    def fts_search(self, query: str, limit: int = 20) -> list[tuple[int, float]]:
        """Return (chunk_id, rank) pairs.

        Rank is negative (closer to 0 = better match).
        """
        rows = self._conn.execute(
            """
            SELECT rowid, rank
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
        return [(row[0], float(row[1])) for row in rows]

    def hybrid_search(
        self,
        query_embedding: list[float],
        query_text: str,
        max_results: int = 10,
        min_score: float = 0.35,
    ) -> list[SearchHit]:
        """Combine vector and FTS results: 0.7*vec_score + 0.3*fts_score."""
        logger.debug(
            f"hybrid_search_start query={query_text[:80]} max_results={max_results}"
        )
        vec_results = self.vector_search(query_embedding, limit=max_results * 3)
        fts_results = self.fts_search(query_text, limit=max_results * 3)
        logger.debug(
            f"hybrid_search_raw vec_hits={len(vec_results)} fts_hits={len(fts_results)}"
        )

        # Normalize vector scores: distance -> similarity (1 - distance for cosine)
        # sqlite-vec returns cosine distance in [0, 2]
        vec_scores: dict[int, float] = {}
        for cid, dist in vec_results:
            similarity = max(0.0, 1.0 - dist / 2.0)
            vec_scores[cid] = similarity
            logger.debug(
                f"vec_score chunk_id={cid} distance={round(dist, 4)} similarity={round(similarity, 4)}"
            )

        # Normalize FTS scores: rank is negative, more negative = better
        fts_scores: dict[int, float] = {}
        if fts_results:
            min_rank = min(r for _, r in fts_results)
            logger.debug(f"fts_min_rank min_rank={round(min_rank, 4)}")
            for cid, rank in fts_results:
                # Normalize to [0, 1] where 1 is best
                normalized = rank / min_rank if min_rank != 0 else 0.0
                fts_scores[cid] = normalized
                logger.debug(
                    f"fts_score chunk_id={cid} raw_rank={round(rank, 4)} normalized={round(normalized, 4)}"
                )

        # Combine scores
        all_ids = set(vec_scores.keys()) | set(fts_scores.keys())
        logger.debug(f"hybrid_candidate_ids total={len(all_ids)}")
        scored: list[tuple[int, float]] = []
        for cid in all_ids:
            vs = vec_scores.get(cid, 0.0)
            fs = fts_scores.get(cid, 0.0)
            combined = 0.7 * vs + 0.3 * fs
            logger.debug(
                f"hybrid_combine chunk_id={cid} vec={round(vs, 4)} fts={round(fs, 4)} combined={round(combined, 4)} above_min={combined >= min_score}"
            )
            if combined >= min_score:
                scored.append((cid, combined))

        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[:max_results]
        logger.debug(
            f"hybrid_filtered above_threshold={len(scored)} min_score={min_score}"
        )

        # Fetch chunk details
        hits: list[SearchHit] = []
        for cid, score in scored:
            row = self._conn.execute(
                "SELECT path, start_line, end_line, text FROM chunks WHERE id = ?",
                (cid,),
            ).fetchone()
            if row:
                source = "long_term" if row[0].endswith("MEMORY.md") else "memory"
                logger.debug(
                    f"hybrid_hit chunk_id={cid} path={row[0]} lines={row[1]}-{row[2]} score={round(score, 4)} source={source}"
                )
                hits.append(
                    SearchHit(
                        path=row[0],
                        startLine=row[1],
                        endLine=row[2],
                        score=round(score, 4),
                        snippet=row[3][:200],
                        source=source,
                    )
                )

        logger.info(
            f"hybrid_search_done query={query_text[:80]} results={len(hits)} candidates={len(all_ids)} vec_hits={len(vec_results)} fts_hits={len(fts_results)}"
        )
        return hits

    def get_chunk(self, chunk_id: int) -> ChunkRecord | None:
        """Get a chunk by ID."""
        row = self._conn.execute(
            "SELECT id, path, start_line, end_line, text, hash"
            " FROM chunks WHERE id = ?",
            (chunk_id,),
        ).fetchone()
        if row is None:
            return None
        return ChunkRecord(
            id=row[0],
            path=row[1],
            start_line=row[2],
            end_line=row[3],
            text=row[4],
            hash=row[5],
        )
