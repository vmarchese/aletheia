"""Unit tests for enhanced DEBUG logging functionality.

Tests cover:
- Operation start/complete logging with duration tracking
- Scratchpad operation logging
- State change logging
- Plugin invocation logging
- LLM invocation logging
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

from aletheia.utils.logging import (
    enable_trace_logging,
    disable_trace_logging,
    is_trace_enabled,
    log_debug,
    log_operation_start,
    log_operation_complete,
    log_scratchpad_operation,
    log_state_change,
    log_plugin_invocation,
    log_llm_invocation,
)


@pytest.fixture
def temp_session_dir():
    """Create a temporary session directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    # Cleanup
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


@pytest.fixture
def enabled_logging(temp_session_dir):
    """Fixture that enables logging for a test."""
    enable_trace_logging(temp_session_dir)
    yield temp_session_dir
    disable_trace_logging()


class TestDebugLogging:
    """Tests for DEBUG-level logging functions."""
    
    def test_log_debug_when_disabled(self):
        """Test that log_debug does nothing when logging is disabled."""
        # Ensure logging is disabled
        disable_trace_logging()
        
        # Should not raise an exception
        log_debug("Test message")
        
        assert not is_trace_enabled()
    
    def test_log_debug_when_enabled(self, enabled_logging):
        """Test that log_debug writes to log file when enabled."""
        log_debug("Debug test message")
        
        log_file = enabled_logging / "aletheia_trace.log"
        assert log_file.exists()
        
        content = log_file.read_text()
        assert "DEBUG" in content
        assert "Debug test message" in content


class TestOperationLogging:
    """Tests for operation start/complete logging."""
    
    def test_log_operation_start_returns_time(self):
        """Test that log_operation_start returns current time."""
        start_time = log_operation_start("test_operation")
        
        assert isinstance(start_time, datetime)
        # Should be very recent (within last second)
        assert (datetime.now() - start_time).total_seconds() < 1
    
    def test_log_operation_start_with_details(self, enabled_logging):
        """Test operation start logging with details."""
        details = {"param1": "value1", "param2": 42}
        start_time = log_operation_start(
            operation_name="fetch_logs",
            agent_name="DataFetcher",
            details=details
        )
        
        log_file = enabled_logging / "aletheia_trace.log"
        content = log_file.read_text()
        
        assert "DataFetcher | fetch_logs - STARTING" in content
        assert "param1: value1" in content
        assert "param2: 42" in content
    
    def test_log_operation_complete_calculates_duration(self, enabled_logging):
        """Test that operation complete logs duration."""
        start_time = log_operation_start("test_operation")
        
        # Simulate some work
        import time
        time.sleep(0.01)  # 10ms
        
        log_operation_complete(
            operation_name="test_operation",
            start_time=start_time,
            result_summary="Success"
        )
        
        log_file = enabled_logging / "aletheia_trace.log"
        content = log_file.read_text()
        
        assert "test_operation - COMPLETED" in content
        assert "duration:" in content
        assert "ms)" in content
        assert "Result: Success" in content
    
    def test_log_operation_with_agent_name(self, enabled_logging):
        """Test operation logging includes agent name."""
        start_time = log_operation_start(
            operation_name="analyze_patterns",
            agent_name="PatternAnalyzer"
        )
        
        log_operation_complete(
            operation_name="analyze_patterns",
            start_time=start_time,
            agent_name="PatternAnalyzer",
            result_summary="10 anomalies found"
        )
        
        log_file = enabled_logging / "aletheia_trace.log"
        content = log_file.read_text()
        
        assert "PatternAnalyzer | analyze_patterns" in content
        assert "10 anomalies found" in content


class TestScratchpadOperationLogging:
    """Tests for scratchpad operation logging."""
    
    def test_log_scratchpad_read(self, enabled_logging):
        """Test logging scratchpad read operations."""
        log_scratchpad_operation(
            operation="READ",
            section="DATA_COLLECTED",
            agent_name="PatternAnalyzer",
            data_summary="logs: 200 entries"
        )
        
        log_file = enabled_logging / "aletheia_trace.log"
        content = log_file.read_text()
        
        assert "PatternAnalyzer | SCRATCHPAD READ" in content
        assert "Section: DATA_COLLECTED" in content
        assert "Data: logs: 200 entries" in content
    
    def test_log_scratchpad_write(self, enabled_logging):
        """Test logging scratchpad write operations."""
        log_scratchpad_operation(
            operation="WRITE",
            section="PATTERN_ANALYSIS",
            agent_name="PatternAnalyzer"
        )
        
        log_file = enabled_logging / "aletheia_trace.log"
        content = log_file.read_text()
        
        assert "SCRATCHPAD WRITE" in content
        assert "Section: PATTERN_ANALYSIS" in content
    
    def test_log_scratchpad_truncates_long_data(self, enabled_logging):
        """Test that long data summaries are truncated."""
        long_data = "x" * 200
        log_scratchpad_operation(
            operation="APPEND",
            section="LOGS",
            data_summary=long_data
        )
        
        log_file = enabled_logging / "aletheia_trace.log"
        content = log_file.read_text()
        
        assert "..." in content  # Should be truncated
        assert "x" * 200 not in content  # Full string shouldn't appear


class TestStateChangeLogging:
    """Tests for state change logging."""
    
    def test_log_state_change_basic(self, enabled_logging):
        """Test basic state change logging."""
        log_state_change(
            entity="session",
            old_state="active",
            new_state="completed"
        )
        
        log_file = enabled_logging / "aletheia_trace.log"
        content = log_file.read_text()
        
        assert "STATE CHANGE" in content
        assert "session: active → completed" in content
    
    def test_log_state_change_with_reason(self, enabled_logging):
        """Test state change logging with reason."""
        log_state_change(
            entity="agent",
            old_state="idle",
            new_state="executing",
            reason="User initiated investigation"
        )
        
        log_file = enabled_logging / "aletheia_trace.log"
        content = log_file.read_text()
        
        assert "agent: idle → executing" in content
        assert "Reason: User initiated investigation" in content


class TestPluginInvocationLogging:
    """Tests for plugin invocation logging."""
    
    def test_log_plugin_invocation_basic(self, enabled_logging):
        """Test basic plugin invocation logging."""
        log_plugin_invocation(
            plugin_name="KubernetesPlugin",
            function_name="fetch_logs",
            parameters={"pod": "payments-svc", "namespace": "production"}
        )
        
        log_file = enabled_logging / "aletheia_trace.log"
        content = log_file.read_text()
        
        assert "PLUGIN CALL | KubernetesPlugin.fetch_logs" in content
        assert "pod: payments-svc" in content
        assert "namespace: production" in content
    
    def test_log_plugin_invocation_truncates_long_values(self, enabled_logging):
        """Test that long parameter values are truncated."""
        long_value = "x" * 300
        log_plugin_invocation(
            plugin_name="PrometheusPlugin",
            function_name="fetch_metrics",
            parameters={"query": long_value}
        )
        
        log_file = enabled_logging / "aletheia_trace.log"
        content = log_file.read_text()
        
        assert "..." in content
        assert "x" * 300 not in content


class TestLLMInvocationLogging:
    """Tests for LLM invocation logging."""
    
    def test_log_llm_invocation_basic(self, enabled_logging):
        """Test basic LLM invocation logging."""
        log_llm_invocation(
            agent_name="DataFetcher",
            model="gpt-4o",
            prompt_summary="Fetch logs from payments-svc pod"
        )
        
        log_file = enabled_logging / "aletheia_trace.log"
        content = log_file.read_text()
        
        assert "LLM INVOKE | DataFetcher" in content
        assert "Model: gpt-4o" in content
        assert "Prompt summary: Fetch logs from payments-svc pod" in content
    
    def test_log_llm_invocation_with_token_estimate(self, enabled_logging):
        """Test LLM invocation logging with token estimate."""
        log_llm_invocation(
            agent_name="RootCauseAnalyst",
            model="gpt-4o",
            prompt_summary="Synthesize findings from all agents",
            estimated_tokens=1500
        )
        
        log_file = enabled_logging / "aletheia_trace.log"
        content = log_file.read_text()
        
        assert "LLM INVOKE | RootCauseAnalyst" in content
        assert "(~1500 tokens)" in content


class TestLoggingWhenDisabled:
    """Tests that logging functions don't crash when logging is disabled."""
    
    def test_all_logging_functions_safe_when_disabled(self):
        """Test that all logging functions are safe to call when disabled."""
        disable_trace_logging()
        
        # All of these should work without raising exceptions
        log_debug("test")
        start_time = log_operation_start("test")
        log_operation_complete("test", start_time)
        log_scratchpad_operation("READ", "TEST_SECTION")
        log_state_change("entity", "old", "new")
        log_plugin_invocation("Plugin", "function", {})
        log_llm_invocation("Agent", "model", "summary")
        
        assert not is_trace_enabled()


class TestIntegrationWithAgents:
    """Integration tests for logging with agent operations."""
    
    @pytest.mark.asyncio
    async def test_agent_operation_full_cycle(self, enabled_logging):
        """Test complete logging cycle for an agent operation."""
        # Simulate agent execution with logging
        agent_name = "DataFetcher"
        
        # 1. Agent starts operation
        op_start = log_operation_start(
            operation_name="fetch_kubernetes_logs",
            agent_name=agent_name,
            details={"pod": "payments-svc", "namespace": "production"}
        )
        
        # 2. Agent reads scratchpad
        log_scratchpad_operation(
            operation="READ",
            section="PROBLEM_DESCRIPTION",
            agent_name=agent_name,
            data_summary="Service: payments-svc"
        )
        
        # 3. Plugin invocation
        log_plugin_invocation(
            plugin_name="KubernetesPlugin",
            function_name="fetch_logs",
            parameters={"pod": "payments-svc", "namespace": "production"}
        )
        
        # 4. LLM invocation
        log_llm_invocation(
            agent_name=agent_name,
            model="gpt-4o",
            prompt_summary="Fetch and summarize logs",
            estimated_tokens=500
        )
        
        # 5. Agent writes results
        log_scratchpad_operation(
            operation="WRITE",
            section="DATA_COLLECTED",
            agent_name=agent_name,
            data_summary="200 logs collected"
        )
        
        # 6. Operation complete
        log_operation_complete(
            operation_name="fetch_kubernetes_logs",
            start_time=op_start,
            agent_name=agent_name,
            result_summary="200 logs collected"
        )
        
        # Verify log file contains all operations in order
        log_file = enabled_logging / "aletheia_trace.log"
        content = log_file.read_text()
        
        # Check all operations are logged
        assert "fetch_kubernetes_logs - STARTING" in content
        assert "SCRATCHPAD READ" in content
        assert "PLUGIN CALL" in content
        assert "LLM INVOKE" in content
        assert "SCRATCHPAD WRITE" in content
        assert "fetch_kubernetes_logs - COMPLETED" in content
        
        # Check order (approximate - we look for relative positions)
        start_pos = content.find("fetch_kubernetes_logs - STARTING")
        complete_pos = content.find("fetch_kubernetes_logs - COMPLETED")
        assert start_pos < complete_pos


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
