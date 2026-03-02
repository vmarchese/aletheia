"""Tests for context compaction feature (issue #244)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agent_framework import Content, Message

from aletheia.config import Config
from aletheia.daemon.session_manager import GatewaySessionManager

# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


def test_compaction_threshold_default():
    """context_compaction_threshold defaults to 0.8."""
    with patch.dict("os.environ", {}, clear=False):
        config = Config()
        assert config.context_compaction_threshold == 0.8


def test_compaction_threshold_env_override():
    """context_compaction_threshold can be set via env var."""
    with patch.dict(
        "os.environ",
        {"ALETHEIA_CONTEXT_COMPACTION_THRESHOLD": "0.6"},
        clear=False,
    ):
        config = Config()
        assert config.context_compaction_threshold == 0.6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_manager(
    total_estimated: int = 0,
    max_context_window: int = 100_000,
    threshold: float = 0.8,
    messages: list | None = None,
) -> GatewaySessionManager:
    """Create a GatewaySessionManager with mocked internals.

    The compaction check sums individual section keys
    (system_prompt_tokens + tools_tokens + memory_tokens + messages_tokens).
    Fixed overhead is 5000+3000+1000 = 9000, so messages_tokens is set to
    total_estimated - 9000 to make the sum equal total_estimated.
    """

    config = MagicMock(spec=Config)
    config.max_context_window = max_context_window
    config.context_compaction_threshold = threshold
    config.context_reserved_ratio = 0.225

    sm = GatewaySessionManager(config=config)

    # Mock orchestrator and agent session
    sm.orchestrator = MagicMock()
    sm.orchestrator.agent_session = MagicMock()
    sm.orchestrator.agent_session.state = {
        "context_window": {
            "system_prompt_tokens": 5000,
            "tools_tokens": 3000,
            "memory_tokens": 1000,
            "messages_tokens": max(0, total_estimated - 9000),
        },
        "in_memory": {
            "messages": messages or [],
        },
    }

    # Mock active session with scratchpad
    sm.active_session = MagicMock()
    sm.active_session.scratchpad = MagicMock()

    return sm


# ---------------------------------------------------------------------------
# _maybe_compact_context tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_compaction_below_threshold():
    """No compaction chunks yielded when utilization < threshold."""
    sm = _make_session_manager(
        total_estimated=50_000,  # 50% utilization
        max_context_window=100_000,
        threshold=0.8,
    )

    chunks = []
    async for chunk in sm._maybe_compact_context():
        chunks.append(chunk)

    assert len(chunks) == 0


@pytest.mark.asyncio
async def test_no_compaction_no_orchestrator():
    """No compaction when orchestrator is None."""
    from aletheia.daemon.session_manager import GatewaySessionManager

    config = MagicMock(spec=Config)
    sm = GatewaySessionManager(config=config)
    sm.orchestrator = None
    sm.active_session = None

    chunks = []
    async for chunk in sm._maybe_compact_context():
        chunks.append(chunk)

    assert len(chunks) == 0


@pytest.mark.asyncio
async def test_no_compaction_too_few_messages():
    """No compaction when there are fewer than 2 messages."""
    msg = Message(role="user", contents=[Content.from_text("hello")])
    sm = _make_session_manager(
        total_estimated=90_000,  # 90%, above threshold
        max_context_window=100_000,
        threshold=0.8,
        messages=[msg],
    )

    chunks = []
    async for chunk in sm._maybe_compact_context():
        chunks.append(chunk)

    assert len(chunks) == 0


@pytest.mark.asyncio
async def test_compaction_yields_start_and_end():
    """Compaction yields start and end chunks when above threshold."""
    messages = [
        Message(role="user", contents=[Content.from_text("hello")]),
        Message(
            role="assistant",
            contents=[Content.from_text("hi there, how can I help?")],
        ),
        Message(
            role="user",
            contents=[Content.from_text("tell me about the system")],
        ),
    ]

    sm = _make_session_manager(
        total_estimated=85_000,  # 85%, above 80% threshold
        max_context_window=100_000,
        threshold=0.8,
        messages=messages,
    )

    # Mock _run_compaction
    sm._run_compaction = AsyncMock(
        return_value="## Summary\nUser asked about the system."
    )

    chunks = []
    async for chunk in sm._maybe_compact_context():
        chunks.append(chunk)

    assert len(chunks) == 2
    assert chunks[0]["type"] == "compaction_start"
    assert chunks[0]["content"]["context_pct"] == 85.0
    assert chunks[1]["type"] == "compaction_end"
    assert chunks[1]["content"]["initial_pct"] == 85.0
    assert "final_pct" in chunks[1]["content"]


@pytest.mark.asyncio
async def test_compaction_replaces_messages():
    """After compaction, in_memory messages are replaced with summary."""
    messages = [
        Message(role="user", contents=[Content.from_text("hello")]),
        Message(
            role="assistant",
            contents=[Content.from_text("hi there")],
        ),
    ]

    sm = _make_session_manager(
        total_estimated=85_000,
        max_context_window=100_000,
        threshold=0.8,
        messages=messages,
    )

    summary = "## Summary\nConversation about greetings."
    sm._run_compaction = AsyncMock(return_value=summary)

    chunks = []
    async for chunk in sm._maybe_compact_context():
        chunks.append(chunk)

    # Verify messages were replaced
    in_memory = sm.orchestrator.agent_session.state["in_memory"]
    assert len(in_memory["messages"]) == 1
    replaced_msg = in_memory["messages"][0]
    assert replaced_msg.role == "assistant"
    assert "[COMPACTED CONTEXT]" in replaced_msg.contents[0].text
    assert summary in replaced_msg.contents[0].text


@pytest.mark.asyncio
async def test_compaction_writes_scratchpad():
    """Compaction writes an entry to the scratchpad."""
    messages = [
        Message(role="user", contents=[Content.from_text("hello")]),
        Message(
            role="assistant",
            contents=[Content.from_text("hi")],
        ),
    ]

    sm = _make_session_manager(
        total_estimated=85_000,
        max_context_window=100_000,
        threshold=0.8,
        messages=messages,
    )

    sm._run_compaction = AsyncMock(return_value="compressed")

    chunks = []
    async for chunk in sm._maybe_compact_context():
        chunks.append(chunk)

    # Verify scratchpad was called
    scratchpad = sm.active_session.scratchpad
    scratchpad.write_journal_entry.assert_called_once()
    call_kwargs = scratchpad.write_journal_entry.call_args
    assert call_kwargs[1]["agent"] == "CompactionAgent"
    assert "85.0%" in call_kwargs[1]["text"]


# ---------------------------------------------------------------------------
# CompactionAgent instantiation test
# ---------------------------------------------------------------------------


def test_compaction_agent_instantiation():
    """CompactionAgent can be instantiated following TimelineAgent pattern."""
    with patch("aletheia.agents.client.LLMClient.get_client") as mock_get_client:
        mock_get_client.return_value = MagicMock()

        from aletheia.agents.compaction.compaction_agent import (
            CompactionAgent,
        )

        agent = CompactionAgent(
            name="test_compaction",
            instructions="Compress this conversation.",
            description="Test compaction agent",
        )

        assert agent.name == "test_compaction"
        assert agent.agent is not None
