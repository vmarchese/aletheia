"""sqlite-vec based Knowledge implementation."""

from __future__ import annotations

import hashlib
from pathlib import Path

import structlog

from aletheia.engram.embeddings import EmbeddingProvider
from aletheia.knowledge.db import KnowledgeDB
from aletheia.knowledge.knowledge import Knowledge

logger = structlog.get_logger(__name__)


class SqliteKnowledge(Knowledge):
    """Knowledge implementation using SQLite with sqlite-vec and FTS5.

    Args:
        db_path: Path to the SQLite database file.
        collection_name: Collection name (passed to base class).
        n_results: Number of results to return from queries.
    """

    def __init__(
        self,
        db_path: str = ".aletheia/knowledge.db",
        collection_name: str = "aletheia_common",
        n_results: int = 5,
    ) -> None:
        super().__init__(collection_name=collection_name)
        self._db = KnowledgeDB(Path(db_path))
        self._embedder = EmbeddingProvider()
        self._n_results = n_results
        logger.info(
            f"sqlite_knowledge_initialized db_path={db_path} n_results={n_results}"
        )

    def add_document(self, id: str, document: str, metadata: dict) -> str:
        """Add a document: chunk, embed, and store."""
        from chonkie import TokenChunker

        chunker = TokenChunker(chunk_size=400, chunk_overlap=80)
        raw_chunks = chunker.chunk(document)
        chunk_texts = [rc.text for rc in raw_chunks]
        chunk_hashes = [hashlib.sha256(t.encode()).hexdigest() for t in chunk_texts]

        logger.debug(f"embedding_batch doc_id={id} count={len(chunk_texts)}")
        embeddings = self._embedder.embed_batch(chunk_texts)

        self._db.insert_document(
            doc_id=id,
            text=document,
            metadata=metadata,
            chunk_texts=chunk_texts,
            chunk_hashes=chunk_hashes,
            embeddings=embeddings,
        )
        return id

    def delete_document(self, id: str) -> None:
        """Delete a document and all its chunks."""
        self._db.delete_document(id)

    def query(self, question: str) -> str:
        """Query the knowledge base using hybrid vector + FTS search."""
        embedding = self._embedder.embed(question)
        chunks = self._db.hybrid_search(
            query_embedding=embedding,
            query_text=question,
            max_results=self._n_results,
        )
        logger.debug(f"query_results question={question} count={len(chunks)}")
        return "\n".join(chunks)

    def search(self, question: str) -> list[str]:
        """Search the knowledge base and return matching chunks as a list."""
        embedding = self._embedder.embed(question)
        return self._db.hybrid_search(
            query_embedding=embedding,
            query_text=question,
            max_results=self._n_results,
        )

    def list_documents(self) -> tuple[list[str], list[str]]:
        """List all documents in the knowledge base."""
        return self._db.list_documents()
