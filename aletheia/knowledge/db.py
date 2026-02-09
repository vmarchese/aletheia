"""SQLite database layer for knowledge: documents, chunks, vector search, and FTS5."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import sqlite_vec
import structlog

logger = structlog.get_logger(__name__)


def _load_extensions(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec extension."""
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL,
    text TEXT NOT NULL,
    hash TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES knowledge_documents(id)
);

CREATE INDEX IF NOT EXISTS idx_kchunks_doc ON knowledge_chunks(document_id);

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_vector USING vec0(
    chunk_id INTEGER PRIMARY KEY,
    embedding FLOAT[1536]
);

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts USING fts5(
    text,
    content=knowledge_chunks,
    content_rowid=chunk_id
);
"""


class KnowledgeDB:
    """SQLite database for knowledge document storage, vector search, and FTS."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = self._connect()
        logger.info(f"knowledge_db_opened path={db_path}")

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

    def insert_document(
        self,
        doc_id: str,
        text: str,
        metadata: dict[str, str],
        chunk_texts: list[str],
        chunk_hashes: list[str],
        embeddings: list[list[float]],
    ) -> None:
        """Insert a document and its chunks. Replaces existing document with same ID."""
        logger.debug(
            f"insert_document_start doc_id={doc_id} num_chunks={len(chunk_texts)}"
        )
        # Remove old version if exists
        self.delete_document(doc_id)

        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO knowledge_documents (id, text, metadata, created_at)"
            " VALUES (?, ?, ?, ?)",
            (doc_id, text, json.dumps(metadata), datetime.now().isoformat()),
        )

        for chunk_text, chunk_hash, embedding in zip(
            chunk_texts, chunk_hashes, embeddings, strict=True
        ):
            cur.execute(
                "INSERT INTO knowledge_chunks (document_id, text, hash)"
                " VALUES (?, ?, ?)",
                (doc_id, chunk_text, chunk_hash),
            )
            chunk_id = cur.lastrowid
            cur.execute(
                "INSERT INTO knowledge_chunks_vector (chunk_id, embedding)"
                " VALUES (?, ?)",
                (chunk_id, sqlite_vec.serialize_float32(embedding)),
            )
            cur.execute(
                "INSERT INTO knowledge_chunks_fts (rowid, text) VALUES (?, ?)",
                (chunk_id, chunk_text),
            )

        self._conn.commit()
        logger.info(
            f"document_inserted doc_id={doc_id} chunks_inserted={len(chunk_texts)}"
        )

    def delete_document(self, doc_id: str) -> None:
        """Delete a document and all its chunks, vectors, and FTS entries."""
        cur = self._conn.cursor()

        existing_ids = [
            row[0]
            for row in cur.execute(
                "SELECT chunk_id FROM knowledge_chunks WHERE document_id = ?",
                (doc_id,),
            ).fetchall()
        ]

        if existing_ids:
            logger.debug(f"removing_chunks doc_id={doc_id} count={len(existing_ids)}")
            placeholders = ",".join("?" for _ in existing_ids)
            cur.execute(
                f"DELETE FROM knowledge_chunks_vector"
                f" WHERE chunk_id IN ({placeholders})",
                existing_ids,
            )
            # FTS5 content-sync: delete via special command
            for cid in existing_ids:
                row = cur.execute(
                    "SELECT text FROM knowledge_chunks WHERE chunk_id = ?", (cid,)
                ).fetchone()
                if row:
                    cur.execute(
                        "INSERT INTO knowledge_chunks_fts"
                        "(knowledge_chunks_fts, rowid, text)"
                        " VALUES('delete', ?, ?)",
                        (cid, row[0]),
                    )
            cur.execute(
                f"DELETE FROM knowledge_chunks WHERE chunk_id IN ({placeholders})",
                existing_ids,
            )

        cur.execute("DELETE FROM knowledge_documents WHERE id = ?", (doc_id,))
        self._conn.commit()
        logger.debug(f"document_deleted doc_id={doc_id}")

    def list_documents(self) -> tuple[list[str], list[str]]:
        """Return (ids, documents) for all stored documents."""
        rows = self._conn.execute(
            "SELECT id, text FROM knowledge_documents ORDER BY created_at"
        ).fetchall()
        ids = [row[0] for row in rows]
        documents = [row[1] for row in rows]
        return ids, documents

    def vector_search(
        self, embedding: list[float], limit: int = 20
    ) -> list[tuple[int, float]]:
        """Return (chunk_id, distance) pairs sorted by distance ascending."""
        rows = self._conn.execute(
            """
            SELECT chunk_id, distance
            FROM knowledge_chunks_vector
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
            """,
            (sqlite_vec.serialize_float32(embedding), limit),
        ).fetchall()
        return [(row[0], float(row[1])) for row in rows]

    def fts_search(self, query: str, limit: int = 20) -> list[tuple[int, float]]:
        """Return (chunk_id, rank) pairs. Rank is negative (closer to 0 = better)."""
        # Escape for FTS5: quote each term with double quotes so special
        # characters (apostrophes, operators, etc.) are treated as literals.
        escaped = " ".join(
            '"' + token.replace('"', '""') + '"'
            for token in query.split()
            if token.strip()
        )
        if not escaped:
            return []
        try:
            rows = self._conn.execute(
                """
                SELECT rowid, rank
                FROM knowledge_chunks_fts
                WHERE knowledge_chunks_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (escaped, limit),
            ).fetchall()
        except Exception:
            logger.debug(f"fts_search_failed query={query}")
            return []
        return [(row[0], float(row[1])) for row in rows]

    def hybrid_search(
        self,
        query_embedding: list[float],
        query_text: str,
        max_results: int = 5,
        min_score: float = 0.30,
    ) -> list[str]:
        """Combine vector and FTS results, return matching chunk texts."""
        logger.debug(
            f"hybrid_search_start query={query_text[:80]} max_results={max_results}"
        )
        vec_results = self.vector_search(query_embedding, limit=max_results * 3)
        fts_results = self.fts_search(query_text, limit=max_results * 3)
        logger.debug(
            f"hybrid_search_raw vec_hits={len(vec_results)}"
            f" fts_hits={len(fts_results)}"
        )

        # Normalize vector scores: distance -> similarity
        # sqlite-vec returns cosine distance in [0, 2]
        vec_scores: dict[int, float] = {}
        for cid, dist in vec_results:
            similarity = max(0.0, 1.0 - dist / 2.0)
            vec_scores[cid] = similarity

        # Normalize FTS scores: rank is negative, more negative = better
        fts_scores: dict[int, float] = {}
        if fts_results:
            min_rank = min(r for _, r in fts_results)
            for cid, rank in fts_results:
                normalized = rank / min_rank if min_rank != 0 else 0.0
                fts_scores[cid] = normalized

        # Combine scores: 70% vector + 30% FTS
        all_ids = set(vec_scores.keys()) | set(fts_scores.keys())
        scored: list[tuple[int, float]] = []
        for cid in all_ids:
            vs = vec_scores.get(cid, 0.0)
            fs = fts_scores.get(cid, 0.0)
            combined = 0.7 * vs + 0.3 * fs
            if combined >= min_score:
                scored.append((cid, combined))

        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[:max_results]

        # Fetch chunk texts
        texts: list[str] = []
        for cid, _score in scored:
            row = self._conn.execute(
                "SELECT text FROM knowledge_chunks WHERE chunk_id = ?", (cid,)
            ).fetchone()
            if row:
                texts.append(row[0])

        logger.info(
            f"hybrid_search_done query={query_text[:80]} results={len(texts)}"
            f" candidates={len(all_ids)}"
        )
        return texts
