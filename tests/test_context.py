"""Tests for aletheia.context module."""

from unittest.mock import MagicMock, patch

import pytest

from aletheia.context import (
    ContextSection,
    ContextWindow,
    ContextWindowProvider,
    _format_message_text,
    _measure_messages,
    _measure_tools,
    _serialize_message,
    estimate_tokens,
)


class TestEstimateTokens:
    def test_empty_string(self) -> None:
        assert estimate_tokens("") == 0

    def test_short_string(self) -> None:
        # "hello" is 5 chars -> 5 // 4 = 1
        assert estimate_tokens("hello") == 1

    def test_longer_string(self) -> None:
        text = "a" * 400
        assert estimate_tokens(text) == 100

    def test_minimum_one(self) -> None:
        # A single character should return 1 (not 0)
        assert estimate_tokens("x") == 1


class TestContextSection:
    def test_creation(self) -> None:
        section = ContextSection(
            name="System prompt",
            token_count=500,
            color="\U0001f7e6",
        )
        assert section.name == "System prompt"
        assert section.token_count == 500
        assert section.details == []

    def test_with_details(self) -> None:
        section = ContextSection(
            name="Memory files",
            token_count=300,
            color="\U0001f7e8",
            details=[("MEMORY.md", 200), ("2026-02-23.md", 100)],
        )
        assert len(section.details) == 2
        assert section.details[0] == ("MEMORY.md", 200)


class TestContextWindow:
    def _make_window(
        self,
        sections: list[ContextSection] | None = None,
        max_tokens: int = 100000,
        reserved_ratio: float = 0.2,
    ) -> ContextWindow:
        if sections is None:
            sections = [
                ContextSection("System prompt", 5000, "\U0001f7e6"),
                ContextSection("Tools", 10000, "\U0001f7e9"),
                ContextSection("Memory files", 1000, "\U0001f7e8"),
                ContextSection("Messages", 4000, "\U0001f7ea"),
            ]
        return ContextWindow(
            model="gpt-4o",
            provider="openai",
            max_tokens=max_tokens,
            sections=sections,
            reserved_ratio=reserved_ratio,
        )

    def test_estimated_used(self) -> None:
        ctx = self._make_window()
        assert ctx.estimated_used == 20000

    def test_reserved_tokens(self) -> None:
        ctx = self._make_window()
        assert ctx.reserved_tokens == 20000

    def test_free_tokens(self) -> None:
        ctx = self._make_window()
        # 100000 - 20000 (used) - 20000 (reserved) = 60000
        assert ctx.free_tokens == 60000

    def test_utilization_pct(self) -> None:
        ctx = self._make_window()
        assert ctx.utilization_pct == pytest.approx(20.0)

    def test_utilization_pct_zero_max(self) -> None:
        ctx = self._make_window(max_tokens=0)
        assert ctx.utilization_pct == 0.0

    def test_free_tokens_never_negative(self) -> None:
        sections = [ContextSection("Big", 90000, "\U0001f7e6")]
        ctx = self._make_window(sections=sections, max_tokens=100000)
        # 100000 - 90000 - 20000 = -10000 -> clamp to 0
        assert ctx.free_tokens == 0

    def test_render_contains_model(self) -> None:
        ctx = self._make_window()
        output = ctx.render()
        assert "gpt-4o" in output

    def test_render_contains_sections(self) -> None:
        ctx = self._make_window()
        output = ctx.render()
        assert "System prompt" in output
        assert "Tools" in output
        assert "Memory files" in output
        assert "Messages" in output
        assert "Free space" in output
        assert "Reserved buffer" in output

    def test_render_contains_percentages(self) -> None:
        ctx = self._make_window()
        output = ctx.render()
        assert "20.0%" in output  # utilization

    def test_render_warning_high_utilization(self) -> None:
        sections = [ContextSection("Big", 85000, "\U0001f7e6")]
        ctx = self._make_window(sections=sections, reserved_ratio=0.0)
        output = ctx.render()
        assert "Warning" in output

    def test_render_no_warning_low_utilization(self) -> None:
        ctx = self._make_window()
        output = ctx.render()
        assert "Warning" not in output

    def test_render_memory_details(self) -> None:
        sections = [
            ContextSection(
                "Memory files",
                300,
                "\U0001f7e8",
                details=[("MEMORY.md", 200), ("daily.md", 100)],
            ),
        ]
        ctx = self._make_window(sections=sections)
        output = ctx.render()
        assert "MEMORY.md" in output
        assert "200 tokens" in output

    def test_render_bar_length(self) -> None:
        ctx = self._make_window()
        output = ctx.render()
        # The bar line should contain 20 emoji blocks
        # Find the line with the bar (second non-empty line)
        lines = output.split("\n")
        bar_line = lines[2]  # After title and blank
        # Count emoji blocks (they're space-separated)
        blocks = bar_line.strip().split(" ")
        assert len(blocks) == 20

    def test_render_dump_contains_header(self) -> None:
        ctx = self._make_window()
        output = ctx.render_dump(instructions="You are helpful.")
        assert "Context Dump" in output
        assert "gpt-4o" in output

    def test_render_dump_contains_instructions(self) -> None:
        ctx = self._make_window()
        output = ctx.render_dump(instructions="You are a helpful assistant.")
        assert "System Prompt" in output
        assert "You are a helpful assistant." in output

    def test_render_dump_no_instructions(self) -> None:
        ctx = self._make_window()
        output = ctx.render_dump()
        assert "No instructions available" in output

    def test_render_dump_contains_tools(self) -> None:
        tool1 = MagicMock()
        tool1.name = "search"
        tool1.description = "Search for information"
        tool2 = MagicMock()
        tool2.name = "write"
        tool2.description = "Write to a file"
        ctx = self._make_window()
        output = ctx.render_dump(tools=[tool1, tool2])
        assert "Tools" in output
        assert "search" in output
        assert "write" in output
        assert "Search for information" in output

    def test_render_dump_no_tools(self) -> None:
        ctx = self._make_window()
        output = ctx.render_dump(tools=[])
        assert "No tools registered" in output

    def test_render_dump_contains_memory(self) -> None:
        ctx = self._make_window()
        output = ctx.render_dump(
            memory_contents=[
                ("MEMORY.md", "Important fact: the sky is blue."),
                ("memory/2026-02-23.md", "Daily note."),
            ]
        )
        assert "Memory Files" in output
        assert "MEMORY.md" in output
        assert "Important fact: the sky is blue." in output
        assert "Daily note." in output

    def test_render_dump_no_memory(self) -> None:
        ctx = self._make_window()
        output = ctx.render_dump(memory_contents=[])
        assert "No memory files found" in output

    def test_render_dump_contains_messages(self) -> None:
        msg1 = MagicMock()
        msg1.role = "user"
        msg1.text = "Hello"
        msg1.__str__ = lambda _: "Hello"
        msg2 = MagicMock()
        msg2.role = "assistant"
        msg2.text = "Hi there!"
        msg2.__str__ = lambda _: "Hi there!"
        ctx = self._make_window()
        output = ctx.render_dump(messages=[msg1, msg2])
        assert "Messages" in output
        assert "2 messages" in output
        assert "**user**: Hello" in output
        assert "**assistant**: Hi there!" in output

    def test_render_dump_truncates_many_messages(self) -> None:
        msgs = []
        for i in range(30):
            msg = MagicMock()
            msg.role = "user"
            msg.text = f"Message {i}"
            msg.__str__ = lambda _, n=i: f"Message {n}"
            msgs.append(msg)
        ctx = self._make_window()
        output = ctx.render_dump(messages=msgs)
        assert "Showing most recent 20" in output
        assert "30 messages" in output

    def test_render_dump_no_messages(self) -> None:
        ctx = self._make_window()
        output = ctx.render_dump(messages=[])
        assert "No messages in history" in output

    def test_render_dump_contains_summary_table(self) -> None:
        ctx = self._make_window()
        output = ctx.render_dump()
        assert "Summary" in output
        assert "Total Used" in output
        assert "Free" in output
        assert "Reserved" in output

    def test_from_state_empty(self) -> None:
        mock_config = MagicMock()
        mock_config.max_context_window = 100000
        mock_config.context_reserved_ratio = 0.2

        ctx = ContextWindow.from_state(
            state={},
            config=mock_config,
            model="test-model",
            provider="test-provider",
        )

        assert ctx.model == "test-model"
        assert ctx.max_tokens == 100000
        assert ctx.estimated_used == 0

    def test_from_state_with_data(self) -> None:
        mock_config = MagicMock()
        mock_config.max_context_window = 200000
        mock_config.context_reserved_ratio = 0.225

        state = {
            "system_prompt_tokens": 2000,
            "tools_tokens": 10000,
            "memory_tokens": 500,
            "memory_tokens_details": [("MEMORY.md", 500)],
            "messages_tokens": 3000,
            "actual_input_tokens": 16000,
        }

        ctx = ContextWindow.from_state(
            state=state,
            config=mock_config,
            model="gpt-4o",
            provider="openai",
        )

        assert ctx.estimated_used == 15500
        assert ctx.total_input_tokens == 16000
        assert len(ctx.sections) == 4
        assert ctx.sections[0].token_count == 2000  # system prompt
        assert ctx.sections[1].token_count == 10000  # tools


class TestMeasureTools:
    def test_empty_tools(self) -> None:
        assert _measure_tools([]) == 0

    def test_tools_with_name_and_description(self) -> None:
        tool = MagicMock()
        tool.name = "search"
        tool.description = "Search for information"
        tool.parameters.return_value = {"type": "object", "properties": {}}

        tokens = _measure_tools([tool])
        assert tokens > 0

    def test_tools_without_parameters(self) -> None:
        tool = MagicMock(spec=[])
        tool.name = "simple_tool"
        tool.description = None
        # No parameters method
        tokens = _measure_tools([tool])
        assert tokens > 0


class TestSerializeMessage:
    def test_with_to_json(self) -> None:
        msg = MagicMock()
        msg.to_json.return_value = '{"role": "user", "text": "hello"}'
        result = _serialize_message(msg)
        assert result == '{"role": "user", "text": "hello"}'

    def test_without_to_json(self) -> None:
        result = _serialize_message("plain string")
        assert result == "plain string"

    def test_to_json_raises(self) -> None:
        msg = MagicMock()
        msg.to_json.side_effect = RuntimeError("fail")
        msg.__str__ = lambda _: "fallback"
        result = _serialize_message(msg)
        assert result == "fallback"


class TestFormatMessageText:
    def test_message_with_text(self) -> None:
        msg = MagicMock()
        msg.text = "Hello world"
        assert _format_message_text(msg) == "Hello world"

    def test_message_with_function_call(self) -> None:
        content = MagicMock()
        content.type = "function_call"
        content.name = "get_pods"
        msg = MagicMock()
        msg.text = ""
        msg.contents = [content]
        result = _format_message_text(msg)
        assert "[call: get_pods]" in result

    def test_message_with_function_result(self) -> None:
        content = MagicMock()
        content.type = "function_result"
        content.name = "get_pods"
        content.result = "pod-1\npod-2"
        msg = MagicMock()
        msg.text = ""
        msg.contents = [content]
        result = _format_message_text(msg)
        assert "[result: get_pods]" in result
        assert "pod-1" in result

    def test_message_with_long_result_truncated(self) -> None:
        content = MagicMock()
        content.type = "function_result"
        content.name = "search"
        content.result = "x" * 300
        msg = MagicMock()
        msg.text = ""
        msg.contents = [content]
        result = _format_message_text(msg)
        assert result.endswith("...")
        assert len(result) < 350

    def test_message_empty_contents(self) -> None:
        msg = MagicMock()
        msg.text = ""
        msg.contents = []
        assert _format_message_text(msg) == "(empty)"

    def test_plain_object_no_text_no_contents(self) -> None:
        msg = MagicMock(spec=[])
        assert _format_message_text(msg) == "(empty)"


class TestMeasureMessages:
    def test_empty_messages(self) -> None:
        assert _measure_messages([]) == 0

    def test_messages_with_to_json(self) -> None:
        msg1 = MagicMock()
        msg1.to_json.return_value = '{"role": "user", "text": "Hello"}'
        msg2 = MagicMock()
        msg2.to_json.return_value = '{"role": "assistant", "text": "Hi"}'

        tokens = _measure_messages([msg1, msg2])
        assert tokens > 0

    def test_messages_without_to_json(self) -> None:
        tokens = _measure_messages(["Hello, how are you?", "Fine"])
        assert tokens > 0


class TestContextWindowProvider:
    @pytest.fixture()
    def provider(self) -> ContextWindowProvider:
        return ContextWindowProvider(max_tokens=100000, reserved_ratio=0.2)

    def test_init(self, provider: ContextWindowProvider) -> None:
        assert provider.source_id == "context_window"
        assert provider.max_tokens == 100000
        assert provider.reserved_ratio == 0.2

    def test_budget(self, provider: ContextWindowProvider) -> None:
        assert provider._budget == 80000

    @pytest.mark.asyncio
    async def test_before_run_measures_sections(
        self, provider: ContextWindowProvider
    ) -> None:
        agent = MagicMock()
        agent.default_options = {
            "instructions": "You are a helpful assistant." * 10,
            "tools": [],
        }

        session = MagicMock()
        session.state = {"in_memory": {"messages": []}}

        context = MagicMock()
        context.context_messages = {"in_memory": []}
        context.input_messages = []

        state: dict = {}

        with patch("aletheia.context._measure_memory_files", return_value=(0, [])):
            await provider.before_run(
                agent=agent,
                session=session,
                context=context,
                state=state,
            )

        assert "system_prompt_tokens" in state
        assert state["system_prompt_tokens"] > 0
        assert "tools_tokens" in state
        assert "messages_tokens" in state
        assert "total_estimated" in state
        assert state["messages_trimmed"] is False

    @pytest.mark.asyncio
    async def test_before_run_trims_history(
        self, provider: ContextWindowProvider
    ) -> None:
        """When history exceeds budget, oldest messages should be trimmed."""
        # Small budget provider
        small_provider = ContextWindowProvider(max_tokens=1000, reserved_ratio=0.2)

        agent = MagicMock()
        agent.default_options = {
            "instructions": "Short instructions",
            "tools": [],
        }

        # Create messages that exceed budget
        # Use to_json() since _serialize_message prefers it
        msgs = []
        for i in range(20):
            msg = MagicMock()
            long_text = f"Message number {i} " * 20
            msg.to_json.return_value = long_text
            msgs.append(msg)

        session = MagicMock()
        session.state = {"in_memory": {"messages": list(msgs)}}

        context = MagicMock()
        context.context_messages = {"in_memory": list(msgs)}
        context.input_messages = []

        state: dict = {}

        with patch("aletheia.context._measure_memory_files", return_value=(0, [])):
            await small_provider.before_run(
                agent=agent,
                session=session,
                context=context,
                state=state,
            )

        assert state["messages_trimmed"] is True
        # Trimmed messages should be fewer than original
        trimmed = context.context_messages["in_memory"]
        assert len(trimmed) < len(msgs)

    @pytest.mark.asyncio
    async def test_after_run_records_usage(
        self, provider: ContextWindowProvider
    ) -> None:
        response = MagicMock()
        response.usage_details = {
            "input_token_count": 5000,
            "output_token_count": 1000,
        }

        context = MagicMock()
        context.response = response

        state: dict = {}

        await provider.after_run(
            agent=MagicMock(),
            session=MagicMock(),
            context=context,
            state=state,
        )

        assert state["actual_input_tokens"] == 5000
        assert state["actual_output_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_after_run_no_response(self, provider: ContextWindowProvider) -> None:
        context = MagicMock()
        context.response = None

        state: dict = {}

        await provider.after_run(
            agent=MagicMock(),
            session=MagicMock(),
            context=context,
            state=state,
        )

        assert "actual_input_tokens" not in state
