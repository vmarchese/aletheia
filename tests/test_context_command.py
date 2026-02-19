from unittest.mock import MagicMock

from aletheia.commands import ContextInfo


def test_context_command_with_data():
    """Test /context command displays context info when data is available."""
    cmd = ContextInfo()
    mock_console = MagicMock()
    mock_config = MagicMock()
    mock_config.max_context_window = 128000

    cmd.execute(
        console=mock_console,
        completion_usage={
            "input_token_count": 50000,
            "output_token_count": 2000,
        },
        config=mock_config,
        message_count=10,
        model_info={"provider": "openai", "model": "gpt-4o"},
    )

    mock_console.print.assert_called_once()
    # The argument is a Markdown object - check its markup content
    call_arg = mock_console.print.call_args[0][0]
    markup = call_arg.markup
    assert "50,000" in markup
    assert "128,000" in markup
    assert "openai" in markup
    assert "gpt-4o" in markup
    assert "39.1%" in markup
    assert "10" in markup


def test_context_command_no_data():
    """Test /context command with no usage data shows appropriate message."""
    cmd = ContextInfo()
    mock_console = MagicMock()

    cmd.execute(console=mock_console)

    mock_console.print.assert_called_once_with(
        "No context data available yet. Send a message first."
    )


def test_context_command_no_input_tokens():
    """Test /context command when input_token_count is 0."""
    cmd = ContextInfo()
    mock_console = MagicMock()

    cmd.execute(
        console=mock_console,
        completion_usage={"input_token_count": 0, "output_token_count": 0},
    )

    mock_console.print.assert_called_once_with(
        "No context data available yet. Send a message first."
    )


def test_context_command_high_utilization():
    """Test /context command shows warning when utilization > 80%."""
    cmd = ContextInfo()
    mock_console = MagicMock()
    mock_config = MagicMock()
    mock_config.max_context_window = 128000

    cmd.execute(
        console=mock_console,
        completion_usage={
            "input_token_count": 110000,
            "output_token_count": 3000,
        },
        config=mock_config,
        message_count=50,
        model_info={"provider": "openai", "model": "gpt-4o"},
    )

    call_arg = mock_console.print.call_args[0][0]
    markup = call_arg.markup
    assert "85.9%" in markup
    assert "Warning" in markup
    assert "80%" in markup


def test_context_command_default_model_info():
    """Test /context command with missing model_info uses defaults."""
    cmd = ContextInfo()
    mock_console = MagicMock()
    mock_config = MagicMock()
    mock_config.max_context_window = 128000

    cmd.execute(
        console=mock_console,
        completion_usage={
            "input_token_count": 10000,
            "output_token_count": 500,
        },
        config=mock_config,
    )

    call_arg = mock_console.print.call_args[0][0]
    markup = call_arg.markup
    assert "unknown" in markup
    assert "10,000" in markup


def test_context_command_visual_bar():
    """Test /context command includes visual progress bar."""
    cmd = ContextInfo()
    mock_console = MagicMock()
    mock_config = MagicMock()
    mock_config.max_context_window = 100000

    cmd.execute(
        console=mock_console,
        completion_usage={
            "input_token_count": 50000,
            "output_token_count": 1000,
        },
        config=mock_config,
    )

    call_arg = mock_console.print.call_args[0][0]
    markup = call_arg.markup
    # 50% utilization should have ~15 filled blocks out of 30
    assert "█" in markup
    assert "░" in markup
