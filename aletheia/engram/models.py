"""Pydantic models for the engram memory framework."""

from pydantic import BaseModel


class ChunkRecord(BaseModel):
    """A chunk of text from a memory file, stored in the database."""

    id: int | None = None
    path: str
    start_line: int
    end_line: int
    text: str
    hash: str


class SearchHit(BaseModel):
    """A single search result from hybrid vector+FTS search."""

    path: str
    startLine: int
    endLine: int
    score: float
    snippet: str
    source: str


class SearchResponse(BaseModel):
    """Response from memory_search."""

    results: list[SearchHit]
    provider: str
    model: str


class GetResponse(BaseModel):
    """Response from memory_get."""

    path: str
    text: str
