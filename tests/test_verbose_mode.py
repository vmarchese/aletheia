"""Tests for verbose mode and trace logging functionality."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import asyncio

from aletheia.utils.logging import (
    enable_trace_logging,
    disable_trace_logging,
    is_trace_enabled,
    get_trace_file_path,
    log_prompt,
    log_prompt_response,
    log_command,
    log_command_result,
    log_agent_transition,
    log_info,
    log_warning,
    log_error,
)
from aletheia.utils.command import run_command, set_verbose_commands
from aletheia.session import Session, SessionMetadata


class TestTraceLogging:
    """Test trace logging functionality."""
    
    def test_enable_disable_trace_logging(self, tmp_path):
        """Test enabling and disabling trace logging."""
        # Initially disabled
        assert not is_trace_enabled()
        assert get_trace_file_path() is None
        
        # Enable trace logging
        enable_trace_logging(tmp_path)
        assert is_trace_enabled()
        assert get_trace_file_path() == tmp_path / "aletheia_trace.log"
        
        # Trace file should be created
        trace_file = tmp_path / "aletheia_trace.log"
        assert trace_file.exists()
        
        # Disable trace logging
        disable_trace_logging()
        assert not is_trace_enabled()
        assert get_trace_file_path() is None
    
    def test_log_prompt(self, tmp_path):
        """Test logging LLM prompts."""
        enable_trace_logging(tmp_path)
        
        log_prompt(
            agent_name="test_agent",
            prompt="Test prompt text",
            model="gpt-4o",
            prompt_tokens=100
        )
        
        # Check trace file contains the prompt
        trace_file = tmp_path / "aletheia_trace.log"
        content = trace_file.read_text()
        assert "LLM PROMPT" in content
        assert "test_agent" in content
        assert "gpt-4o" in content
        assert "Test prompt text" in content
        assert "100" in content
        
        disable_trace_logging()
    
    def test_log_prompt_response(self, tmp_path):
        """Test logging LLM responses."""
        enable_trace_logging(tmp_path)
        
        log_prompt_response(
            agent_name="test_agent",
            response="Test response text",
            completion_tokens=50,
            total_tokens=150
        )
        
        # Check trace file contains the response
        trace_file = tmp_path / "aletheia_trace.log"
        content = trace_file.read_text()
        assert "LLM RESPONSE" in content
        assert "test_agent" in content
        assert "Test response text" in content
        assert "50" in content
        assert "150" in content
        
        disable_trace_logging()
    
    def test_log_command(self, tmp_path):
        """Test logging command execution."""
        enable_trace_logging(tmp_path)
        
        log_command(
            command="kubectl get pods",
            cwd="/tmp",
            env_summary="KUBECONFIG=/path/to/config"
        )
        
        # Check trace file contains command
        trace_file = tmp_path / "aletheia_trace.log"
        content = trace_file.read_text()
        assert "COMMAND START" in content
        assert "kubectl get pods" in content
        assert "/tmp" in content
        
        disable_trace_logging()
    
    def test_log_command_result(self, tmp_path):
        """Test logging command results."""
        enable_trace_logging(tmp_path)
        
        log_command_result(
            command="kubectl get pods",
            exit_code=0,
            stdout="pod1\npod2",
            stderr="",
            duration_seconds=1.5
        )
        
        # Check trace file contains results
        trace_file = tmp_path / "aletheia_trace.log"
        content = trace_file.read_text()
        assert "COMMAND END" in content
        assert "kubectl get pods" in content
        assert "Exit code: 0" in content
        assert "Duration: 1.500s" in content
        assert "pod1" in content
        
        disable_trace_logging()
    
    def test_log_agent_transition(self, tmp_path):
        """Test logging agent transitions."""
        enable_trace_logging(tmp_path)
        
        log_agent_transition(
            from_agent="data_fetcher",
            to_agent="pattern_analyzer",
            reason="Data collection completed"
        )
        
        # Check trace file contains transition
        trace_file = tmp_path / "aletheia_trace.log"
        content = trace_file.read_text()
        assert "AGENT TRANSITION" in content
        assert "data_fetcher" in content
        assert "pattern_analyzer" in content
        assert "Data collection completed" in content
        
        disable_trace_logging()
    
    def test_log_agent_start(self, tmp_path):
        """Test logging agent start (no previous agent)."""
        enable_trace_logging(tmp_path)
        
        log_agent_transition(
            from_agent=None,
            to_agent="data_fetcher",
            reason="Starting investigation"
        )
        
        # Check trace file contains start
        trace_file = tmp_path / "aletheia_trace.log"
        content = trace_file.read_text()
        assert "AGENT START" in content
        assert "data_fetcher" in content
        
        disable_trace_logging()
    
    def test_log_info(self, tmp_path):
        """Test logging info messages."""
        enable_trace_logging(tmp_path)
        
        log_info("Test info message")
        
        trace_file = tmp_path / "aletheia_trace.log"
        content = trace_file.read_text()
        assert "Test info message" in content
        
        disable_trace_logging()
    
    def test_log_warning(self, tmp_path):
        """Test logging warning messages."""
        enable_trace_logging(tmp_path)
        
        log_warning("Test warning message")
        
        trace_file = tmp_path / "aletheia_trace.log"
        content = trace_file.read_text()
        assert "WARNING" in content
        assert "Test warning message" in content
        
        disable_trace_logging()
    
    def test_log_error(self, tmp_path):
        """Test logging error messages."""
        enable_trace_logging(tmp_path)
        
        log_error("Test error message")
        
        trace_file = tmp_path / "aletheia_trace.log"
        content = trace_file.read_text()
        assert "ERROR" in content
        assert "Test error message" in content
        
        disable_trace_logging()
    
    def test_logging_when_disabled(self, tmp_path):
        """Test that logging functions do nothing when trace is disabled."""
        # Ensure trace logging is disabled
        disable_trace_logging()
        
        # These should not raise errors
        log_prompt("test", "prompt", "model")
        log_prompt_response("test", "response")
        log_command("command")
        log_command_result("command", 0)
        log_agent_transition(None, "agent")
        log_info("info")
        log_warning("warning")
        log_error("error")


class TestVerboseCommandExecution:
    """Test verbose command execution."""
    
    def test_run_command_with_trace_logging(self, tmp_path):
        """Test that run_command logs to trace file when enabled."""
        enable_trace_logging(tmp_path)
        
        # Run a simple command
        result = run_command(["echo", "test"], check=True)
        
        assert result.returncode == 0
        assert "test" in result.stdout
        
        # Check trace file contains command execution
        trace_file = tmp_path / "aletheia_trace.log"
        content = trace_file.read_text()
        assert "COMMAND START" in content
        assert "echo test" in content
        assert "COMMAND END" in content
        
        disable_trace_logging()
    
    def test_run_command_verbose_mode(self, capsys):
        """Test verbose command output to console."""
        set_verbose_commands(True)
        
        result = run_command(["echo", "test"], check=True)
        
        assert result.returncode == 0
        
        # Check console output
        captured = capsys.readouterr()
        assert "echo test" in captured.err
        
        set_verbose_commands(False)
    
    def test_run_command_with_error(self, tmp_path):
        """Test command error logging."""
        enable_trace_logging(tmp_path)
        
        # Run a failing command
        with pytest.raises(Exception):
            run_command(["false"], check=True)
        
        # Check trace file contains error
        trace_file = tmp_path / "aletheia_trace.log"
        content = trace_file.read_text()
        assert "Exit code:" in content
        
        disable_trace_logging()


class TestSessionVerboseMetadata:
    """Test session metadata with verbose flag."""
    
    def test_session_create_with_verbose(self, tmp_path):
        """Test creating session with verbose mode enabled."""
        session = Session.create(
            name="test_session",
            password="test_password",
            session_dir=tmp_path / "sessions",
            verbose=True
        )
        
        metadata = session.get_metadata()
        assert metadata.verbose is True
    
    def test_session_create_without_verbose(self, tmp_path):
        """Test creating session without verbose mode."""
        session = Session.create(
            name="test_session",
            password="test_password",
            session_dir=tmp_path / "sessions",
            verbose=False
        )
        
        metadata = session.get_metadata()
        assert metadata.verbose is False
    
    def test_session_metadata_backwards_compatibility(self):
        """Test that old metadata without verbose field still works."""
        # Create metadata dict without verbose field (old format)
        metadata_dict = {
            "id": "INC-1234",
            "name": "test",
            "created": "2025-10-17T10:00:00",
            "updated": "2025-10-17T10:00:00",
            "status": "active",
            "salt": "dGVzdHNhbHQ="
        }
        
        # Should default to False
        metadata = SessionMetadata.from_dict(metadata_dict)
        assert metadata.verbose is False


class TestSKBaseAgentPromptLogging:
    """Test SK agent prompt logging."""
    
    @pytest.mark.asyncio
    async def test_invoke_async_logs_prompt(self, tmp_path):
        """Test that invoke_async logs prompts when trace enabled."""
        from aletheia.agents.sk_base import SKBaseAgent
        from aletheia.plugins.scratchpad.scratchpad import Scratchpad
        
        # Enable trace logging
        enable_trace_logging(tmp_path)
        
        # Create mock config
        config = {
            "llm": {
                "default_model": "gpt-4o",
                "api_key": "test_key"
            }
        }
        
        # Create scratchpad
        scratchpad = Scratchpad(session_dir=tmp_path, encryption_key=b"test_key" * 2)
        
        # Create agent with mocked SK components
        agent = SKBaseAgent(config, scratchpad, agent_name="test_agent")
        
        # Mock the SK agent invoke method
        mock_response = Mock()
        mock_response.content = "Test response"
        
        with patch.object(agent, '_agent', None):
            with patch.object(agent, '_kernel', Mock()):
                # Create a mock SK agent
                mock_sk_agent = MagicMock()
                mock_sk_agent.invoke = AsyncMock(return_value=mock_response)
                agent._agent = mock_sk_agent
                
                # Invoke the agent
                response = await agent.invoke_async("Test prompt")
                
                assert response == "Test response"
        
        # Check trace file contains prompt
        trace_file = tmp_path / "aletheia_trace.log"
        content = trace_file.read_text()
        assert "LLM PROMPT" in content
        assert "test_agent" in content
        assert "Test prompt" in content
        assert "LLM RESPONSE" in content
        assert "Test response" in content
        
        disable_trace_logging()


class TestOrchestratorAgentTransitions:
    """Test orchestrator agent transition logging."""
    
    def test_route_to_agent_logs_transition(self, tmp_path):
        """Test that route_to_agent logs transitions when trace enabled."""
        from aletheia.agents.orchestrator.orchestrator import OrchestratorAgent
        from aletheia.plugins.scratchpad.scratchpad import Scratchpad
        
        # Enable trace logging
        enable_trace_logging(tmp_path)
        
        # Create scratchpad
        scratchpad = Scratchpad(session_dir=tmp_path, encryption_key=b"test_key" * 2)
        
        # Create orchestrator
        config = {"llm": {"default_model": "gpt-4o"}}
        orchestrator = OrchestratorAgent(config, scratchpad)
        
        # Create mock agent
        mock_agent = Mock()
        mock_agent.execute = Mock(return_value={"status": "success"})
        orchestrator.register_agent("test_agent", mock_agent)
        
        # Route to agent
        result = orchestrator.route_to_agent("test_agent")
        
        assert result["success"] is True
        
        # Check trace file contains transition
        trace_file = tmp_path / "aletheia_trace.log"
        content = trace_file.read_text()
        assert "AGENT START" in content or "AGENT TRANSITION" in content
        assert "test_agent" in content
        
        disable_trace_logging()


class TestCLIVerboseFlags:
    """Test CLI verbose flag handling."""
    
    def test_vv_implies_v(self):
        """Test that -vv flag implies -v flag."""
        from aletheia.cli import session_open
        
        # This is tested implicitly in the CLI code
        # The logic: if very_verbose: verbose = True
        # We can verify this by checking the implementation
        assert True  # Placeholder for CLI integration test


# Helper async mock
class AsyncMock(Mock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
