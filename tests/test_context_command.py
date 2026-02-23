from unittest.mock import MagicMock, patch

from aletheia.commands import ContextInfo


def _make_orchestrator(
    state: dict | None = None,
    instructions: str = "",
    tools: list | None = None,
    messages: list | None = None,
) -> MagicMock:
    """Create a mock orchestrator with agent_session state."""
    orchestrator = MagicMock()
    orchestrator.agent_session.state = {
        "context_window": state or {},
        "in_memory": {"messages": messages or []},
    }
    orchestrator.agent.default_options = {
        "instructions": instructions,
        "tools": tools or [],
    }
    return orchestrator


def test_context_command_with_data():
    """Test /context command displays context info when data is available."""
    cmd = ContextInfo()
    mock_console = MagicMock()
    mock_config = MagicMock()
    mock_config.max_context_window = 128000
    mock_config.context_reserved_ratio = 0.225

    state = {
        "system_prompt_tokens": 2000,
        "tools_tokens": 10000,
        "memory_tokens": 500,
        "messages_tokens": 3000,
        "actual_input_tokens": 50000,
    }

    with patch("aletheia.commands.LLMClient") as mock_llm:
        mock_llm.return_value.model = "gpt-4o"
        mock_llm.return_value.provider = "openai"
        cmd.execute(
            mock_console,
            orchestrator=_make_orchestrator(state),
            completion_usage={
                "input_token_count": 50000,
                "output_token_count": 2000,
            },
            config=mock_config,
        )

    mock_console.print.assert_called_once()
    call_arg = mock_console.print.call_args[0][0]
    markup = call_arg.markup
    assert "gpt-4o" in markup
    assert "System prompt" in markup
    assert "Tools" in markup


def test_context_command_no_orchestrator():
    """Test /context command with no orchestrator shows message."""
    cmd = ContextInfo()
    mock_console = MagicMock()

    cmd.execute(mock_console)

    mock_console.print.assert_called_once_with(
        "No active session. Send a message first."
    )


def test_context_command_empty_state():
    """Test /context command with empty context state."""
    cmd = ContextInfo()
    mock_console = MagicMock()
    mock_config = MagicMock()
    mock_config.max_context_window = 128000
    mock_config.context_reserved_ratio = 0.225

    with patch("aletheia.commands.LLMClient") as mock_llm:
        mock_llm.return_value.model = "gpt-4o"
        mock_llm.return_value.provider = "openai"
        cmd.execute(
            mock_console,
            orchestrator=_make_orchestrator(),
            config=mock_config,
        )

    mock_console.print.assert_called_once()
    call_arg = mock_console.print.call_args[0][0]
    markup = call_arg.markup
    assert "Context Usage" in markup


def test_context_command_high_utilization():
    """Test /context command shows warning when utilization > 80%."""
    cmd = ContextInfo()
    mock_console = MagicMock()
    mock_config = MagicMock()
    mock_config.max_context_window = 100000
    mock_config.context_reserved_ratio = 0.0

    state = {
        "system_prompt_tokens": 85000,
        "tools_tokens": 0,
        "memory_tokens": 0,
        "messages_tokens": 0,
    }

    with patch("aletheia.commands.LLMClient") as mock_llm:
        mock_llm.return_value.model = "gpt-4o"
        mock_llm.return_value.provider = "openai"
        cmd.execute(
            mock_console,
            orchestrator=_make_orchestrator(state),
            config=mock_config,
        )

    call_arg = mock_console.print.call_args[0][0]
    markup = call_arg.markup
    assert "Warning" in markup


def test_context_command_visual_bar():
    """Test /context command includes visual bar."""
    cmd = ContextInfo()
    mock_console = MagicMock()
    mock_config = MagicMock()
    mock_config.max_context_window = 100000
    mock_config.context_reserved_ratio = 0.2

    state = {
        "system_prompt_tokens": 50000,
        "tools_tokens": 0,
        "memory_tokens": 0,
        "messages_tokens": 0,
    }

    with patch("aletheia.commands.LLMClient") as mock_llm:
        mock_llm.return_value.model = "test-model"
        mock_llm.return_value.provider = "test"
        cmd.execute(
            mock_console,
            orchestrator=_make_orchestrator(state),
            completion_usage={
                "input_token_count": 50000,
                "output_token_count": 1000,
            },
            config=mock_config,
        )

    call_arg = mock_console.print.call_args[0][0]
    markup = call_arg.markup
    # Bar should contain colored blocks
    assert "\U0001f7e6" in markup or "\u2b1c" in markup or "\u2b1b" in markup


def test_context_dump_shows_sections():
    """Test /context dump displays all context sections."""
    cmd = ContextInfo()
    mock_console = MagicMock()
    mock_config = MagicMock()
    mock_config.max_context_window = 100000
    mock_config.context_reserved_ratio = 0.2

    state = {
        "system_prompt_tokens": 2000,
        "tools_tokens": 500,
        "memory_tokens": 100,
        "memory_tokens_details": [],
        "messages_tokens": 300,
    }

    tool = MagicMock()
    tool.name = "my_tool"
    tool.description = "Does something useful"

    with patch("aletheia.commands.LLMClient") as mock_llm:
        mock_llm.return_value.model = "gpt-4o"
        mock_llm.return_value.provider = "openai"
        cmd.execute(
            mock_console,
            "dump",
            orchestrator=_make_orchestrator(
                state=state,
                instructions="You are a helpful assistant.",
                tools=[tool],
            ),
            config=mock_config,
            channel="tui",
        )

    mock_console.print.assert_called_once()
    call_arg = mock_console.print.call_args[0][0]
    markup = call_arg.markup
    assert "Context Dump" in markup
    assert "System Prompt" in markup
    assert "You are a helpful assistant." in markup
    assert "my_tool" in markup
    assert "Summary" in markup


def test_context_dump_no_orchestrator():
    """Test /context dump with no orchestrator shows message."""
    cmd = ContextInfo()
    mock_console = MagicMock()

    cmd.execute(mock_console, "dump", channel="tui")

    mock_console.print.assert_called_once_with(
        "No active session. Send a message first."
    )


def test_context_dump_disabled_on_telegram():
    """Test /context dump is disabled on Telegram channel."""
    cmd = ContextInfo()
    mock_console = MagicMock()

    cmd.execute(
        mock_console,
        "dump",
        channel="telegram",
        orchestrator=_make_orchestrator(),
    )

    mock_console.print.assert_called_once_with(
        "The /context dump command is not available on Telegram."
    )


def test_context_dump_works_on_web():
    """Test /context dump produces structured data on Web channel."""
    cmd = ContextInfo()
    mock_console = MagicMock()
    mock_console.structured_data = None
    mock_config = MagicMock()
    mock_config.max_context_window = 100000
    mock_config.context_reserved_ratio = 0.2

    state = {
        "system_prompt_tokens": 1000,
        "tools_tokens": 0,
        "memory_tokens": 0,
        "memory_tokens_details": [],
        "messages_tokens": 0,
    }

    with patch("aletheia.commands.LLMClient") as mock_llm:
        mock_llm.return_value.model = "gpt-4o"
        mock_llm.return_value.provider = "openai"
        cmd.execute(
            mock_console,
            "dump",
            orchestrator=_make_orchestrator(state=state, instructions="Be helpful."),
            config=mock_config,
            channel="web",
        )

    # Web channel sets structured_data instead of printing markdown
    assert mock_console.structured_data is not None
    data = mock_console.structured_data
    assert data["model"] == "gpt-4o"
    assert data["provider"] == "openai"
    assert len(data["sections"]) == 4
    assert data["sections"][0]["key"] == "system_prompt"
    assert data["sections"][0]["content"] == "Be helpful."
    mock_console.print.assert_not_called()


def test_context_no_args_still_shows_summary():
    """Test /context with no args still shows the summary bar chart."""
    cmd = ContextInfo()
    mock_console = MagicMock()
    mock_config = MagicMock()
    mock_config.max_context_window = 100000
    mock_config.context_reserved_ratio = 0.2

    with patch("aletheia.commands.LLMClient") as mock_llm:
        mock_llm.return_value.model = "gpt-4o"
        mock_llm.return_value.provider = "openai"
        cmd.execute(
            mock_console,
            orchestrator=_make_orchestrator(),
            config=mock_config,
        )

    call_arg = mock_console.print.call_args[0][0]
    markup = call_arg.markup
    # Summary view has "Context Usage", not "Context Dump"
    assert "Context Usage" in markup
