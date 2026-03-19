"""Async job manager for Aletheia daemon.

Handles persistent async job lifecycle with SQLite storage and a sequential
execution queue (one job runs at a time).
"""

import asyncio
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Job:
    """Represents a single async job."""

    job_id: str
    session_id: str
    channel: str
    message: str
    status: str  # pending | running | completed | failed
    result: dict[str, Any] | None
    error: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dict."""
        return asdict(self)


class JobManager:
    """Manages async jobs with SQLite persistence and a sequential queue.

    Only one job runs at a time.  Additional submitted jobs are queued and
    executed in submission order.  The caller must start the worker via
    ``start_worker(execute_fn)`` after creating this instance.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._init_db()

    # ------------------------------------------------------------------
    # DB bootstrap
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id     TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    channel    TEXT NOT NULL,
                    message    TEXT NOT NULL,
                    status     TEXT NOT NULL DEFAULT 'pending',
                    result     TEXT,
                    error      TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        result: dict[str, Any] | None = (
            json.loads(row["result"]) if row["result"] else None
        )
        return Job(
            job_id=row["job_id"],
            session_id=row["session_id"],
            channel=row["channel"],
            message=row["message"],
            status=row["status"],
            result=result,
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def start_worker(
        self,
        execute_fn: Any,
        on_complete: Any = None,
        on_fail: Any = None,
    ) -> "asyncio.Task[None]":
        """Start the background worker task.

        Args:
            execute_fn: ``async (job_id: str) -> dict[str, Any]`` coroutine
                        called to execute the job.  Should raise on failure.
            on_complete: Optional ``async (job_id: str) -> None`` called after
                         the job is marked completed.
            on_fail:     Optional ``async (job_id: str, error: str) -> None``
                         called after the job is marked failed.

        Returns:
            The created asyncio Task.
        """
        return asyncio.create_task(self._worker(execute_fn, on_complete, on_fail))

    async def _worker(self, execute_fn: Any, on_complete: Any, on_fail: Any) -> None:
        """Consume jobs from the queue one at a time."""
        while True:
            job_id = await self._queue.get()
            await self.mark_running(job_id)
            try:
                result = await execute_fn(job_id)
                await self.mark_completed(job_id, result)
                if on_complete:
                    await on_complete(job_id)
            except Exception as exc:
                error_str = str(exc)
                await self.mark_failed(job_id, error_str)
                if on_fail:
                    await on_fail(job_id, error_str)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def enqueue(self, session_id: str, channel: str, message: str) -> Job:
        """Create a job record, persist it, and add it to the execution queue."""
        job = await self._create_job(session_id, channel, message)
        await self._queue.put(job.job_id)
        return job

    async def get_job(self, job_id: str) -> Job | None:
        def _fetch() -> sqlite3.Row | None:
            with self._connect() as conn:
                result: sqlite3.Row | None = conn.execute(
                    "SELECT * FROM jobs WHERE job_id=?", (job_id,)
                ).fetchone()
                return result

        row = await asyncio.to_thread(_fetch)
        return self._row_to_job(row) if row else None

    async def list_jobs(self, session_id: str) -> list[Job]:
        def _fetch() -> list[sqlite3.Row]:
            with self._connect() as conn:
                return conn.execute(
                    "SELECT * FROM jobs WHERE session_id=? ORDER BY created_at DESC",
                    (session_id,),
                ).fetchall()

        rows = await asyncio.to_thread(_fetch)
        return [self._row_to_job(r) for r in rows]

    async def mark_running(self, job_id: str) -> None:
        now = datetime.now().isoformat()

        def _update() -> None:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE jobs SET status='running', updated_at=? WHERE job_id=?",
                    (now, job_id),
                )

        await asyncio.to_thread(_update)

    async def mark_completed(self, job_id: str, result: dict[str, Any]) -> None:
        now = datetime.now().isoformat()
        result_json = json.dumps(result)

        def _update() -> None:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE jobs SET status='completed', result=?, updated_at=? WHERE job_id=?",
                    (result_json, now, job_id),
                )

        await asyncio.to_thread(_update)

    async def mark_failed(self, job_id: str, error: str) -> None:
        now = datetime.now().isoformat()

        def _update() -> None:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE jobs SET status='failed', error=?, updated_at=? WHERE job_id=?",
                    (error, now, job_id),
                )

        await asyncio.to_thread(_update)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _create_job(self, session_id: str, channel: str, message: str) -> Job:
        job = Job(
            job_id=str(uuid.uuid4()),
            session_id=session_id,
            channel=channel,
            message=message,
            status="pending",
            result=None,
            error=None,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

        def _insert() -> None:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO jobs
                        (job_id, session_id, channel, message, status,
                         result, error, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.job_id,
                        job.session_id,
                        job.channel,
                        job.message,
                        job.status,
                        None,
                        None,
                        job.created_at,
                        job.updated_at,
                    ),
                )

        await asyncio.to_thread(_insert)
        return job
