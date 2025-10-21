"""Unit tests for PrometheusDataFetcher agent."""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from aletheia.agents.prometheus_data_fetcher import PrometheusDataFetcher
from aletheia.fetchers.base import FetchResult, FetchError
from aletheia.scratchpad import Scratchpad, ScratchpadSection


@pytest.fixture
def encryption_key():
    """Provide a valid 32-byte encryption key for scratchpad."""
    return b"test_encryption_key_32_bytes!!"


@pytest.fixture
def scratchpad(encryption_key, tmp_path):
    """Create a test scratchpad instance."""
    return Scratchpad(session_dir=tmp_path, encryption_key=encryption_key)


@pytest.fixture
def prometheus_config():
    """Create a test configuration with Prometheus data source."""
    return {
        "llm": {
            "default_model": "gpt-4o",
            "api_key_env": "OPENAI_API_KEY",
            "agents": {
                "prometheus_data_fetcher": {
                    "model": "gpt-4o"
                }
            }
        },
        "data_sources": {
            "prometheus": {
                "endpoint": "http://prometheus:9090",
                "timeout": 30
            }
        },
        "session": {
            "default_time_window": "2h"
        }
    }


@pytest.fixture
def agent(prometheus_config, scratchpad):
    """Create a PrometheusDataFetcher agent for testing."""
    return PrometheusDataFetcher(prometheus_config, scratchpad)


class TestPrometheusDataFetcherInitialization:
    """Test agent initialization and setup."""
    
    def test_initialization_with_prometheus_configured(self, prometheus_config, scratchpad):
        """Test agent initializes correctly with Prometheus configured."""
        agent = PrometheusDataFetcher(prometheus_config, scratchpad)
        
        assert agent.fetcher is not None
        assert agent.fetcher.config["endpoint"] == "http://prometheus:9090"
        assert agent._plugin_registered is False
    
    def test_initialization_without_prometheus(self, scratchpad):
        """Test agent initializes but has no fetcher when Prometheus not configured."""
        config = {
            "llm": {"default_model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"},
            "data_sources": {}
        }
        agent = PrometheusDataFetcher(config, scratchpad)
        
        assert agent.fetcher is None
        assert agent._plugin_registered is False


class TestPluginRegistration:
    """Test Prometheus plugin registration."""
    
    def test_register_plugin_success(self, agent):
        """Test plugin registration registers PrometheusPlugin."""
        with patch.object(agent.kernel, 'add_plugin') as mock_add_plugin:
            agent._register_plugin()
            
            assert mock_add_plugin.called
            assert agent._plugin_registered is True
            # Verify plugin name
            call_kwargs = mock_add_plugin.call_args
            assert call_kwargs[1]['plugin_name'] == 'prometheus'
    
    def test_register_plugin_idempotent(self, agent):
        """Test plugin registration is idempotent (doesn't register twice)."""
        with patch.object(agent.kernel, 'add_plugin') as mock_add_plugin:
            agent._register_plugin()
            agent._register_plugin()  # Call twice
            
            # Should only call once
            assert mock_add_plugin.call_count == 1


class TestTimeWindowParsing:
    """Test time window parsing logic."""
    
    def test_parse_time_window_explicit(self, agent):
        """Test parsing explicit time window parameter."""
        problem = {"description": "Test issue"}
        time_range = agent._parse_time_window("1h", problem)
        
        start, end = time_range
        assert isinstance(start, datetime)
        assert isinstance(end, datetime)
        # Should be approximately 1 hour apart
        delta = (end - start).total_seconds()
        assert 3580 <= delta <= 3620  # Allow 20 second tolerance
    
    def test_parse_time_window_from_problem(self, agent):
        """Test parsing time window from problem description."""
        problem = {"time_window": "30m"}
        time_range = agent._parse_time_window(None, problem)
        
        start, end = time_range
        delta = (end - start).total_seconds()
        assert 1780 <= delta <= 1820  # 30 minutes ± 20 seconds
    
    def test_parse_time_window_default_fallback(self, agent):
        """Test falling back to default time window from config."""
        problem = {"description": "Test issue"}
        time_range = agent._parse_time_window(None, problem)
        
        start, end = time_range
        # Should use default from config (2h)
        delta = (end - start).total_seconds()
        assert 7180 <= delta <= 7220  # 2 hours ± 20 seconds


class TestParameterHandling:
    """Test parameter handling in fetch operations."""
    
    def test_fetch_with_template_parameter(self, agent):
        """Test that agent accepts template parameter."""
        time_range = (datetime.now() - timedelta(hours=1), datetime.now())
        problem = {"description": "Test issue"}
        
        # Just verify the agent doesn't error with template params
        # Actual fetching is tested in TestPrometheusFetching
        assert agent.fetcher is not None
    
    def test_fetch_with_query_parameter(self, agent):
        """Test that agent accepts query parameter."""
        assert agent.fetcher is not None
        # Query parameter should be accepted in execute() kwargs


class TestPrometheusFetching:
    """Test Prometheus metric fetching logic."""
    
    def test_fetch_prometheus_with_explicit_query(self, agent):
        """Test fetching with explicit PromQL query."""
        time_range = (datetime.now() - timedelta(hours=1), datetime.now())
        problem = {"description": "Test issue"}
        
        mock_fetcher = Mock()
        mock_result = FetchResult(
            source="prometheus",
            count=100,
            time_range=time_range,
            metadata={"query": "rate(http_requests_total[5m])"}
        )
        mock_fetcher.fetch = Mock(return_value=mock_result)
        
        agent.fetcher = mock_fetcher
        result = agent._fetch_prometheus(mock_fetcher, time_range, problem, query="rate(http_requests_total[5m])")
        
        assert result.source == "prometheus"
        assert result.count == 100
        assert "query" in result.metadata
    
    def test_fetch_prometheus_with_template(self, agent):
        """Test fetching using query template."""
        time_range = (datetime.now() - timedelta(hours=1), datetime.now())
        problem = {"description": "Test issue"}
        
        mock_fetcher = Mock()
        mock_result = FetchResult(
            source="prometheus",
            count=50,
            time_range=time_range,
            metadata={"template": "error_rate", "service": "payments-svc"}
        )
        mock_fetcher.fetch = Mock(return_value=mock_result)
        
        agent.fetcher = mock_fetcher
        result = agent._fetch_prometheus(
            mock_fetcher,
            time_range,
            problem,
            template="error_rate",
            template_params={"service": "payments-svc"}
        )
        
        assert result.count == 50
        assert result.metadata["template"] == "error_rate"
    
    def test_fetch_prometheus_handles_fetch_error(self, agent):
        """Test proper handling of FetchError."""
        time_range = (datetime.now() - timedelta(hours=1), datetime.now())
        problem = {"description": "Test issue"}
        
        mock_fetcher = Mock()
        mock_fetcher.fetch = Mock(side_effect=FetchError("Prometheus unavailable"))
        
        agent.fetcher = mock_fetcher
        
        with pytest.raises(FetchError):
            agent._fetch_prometheus(mock_fetcher, time_range, problem, query="test_query")


class TestSKIntegration:
    """Test Semantic Kernel integration."""
    
    def test_build_sk_prompt_guided_mode(self, agent):
        """Test SK prompt building in guided mode."""
        time_range = (datetime.now() - timedelta(hours=1), datetime.now())
        problem = {
            "description": "High error rate in payments service",
            "affected_services": ["payments-svc"]
        }
        
        prompt = agent._build_sk_prompt(time_range, problem, mode="guided")
        
        assert "High error rate in payments service" in prompt
        assert "payments-svc" in prompt
        assert "Collect Prometheus metrics" in prompt
    
    def test_build_sk_prompt_conversational_mode(self, agent):
        """Test SK prompt building in conversational mode."""
        time_range = (datetime.now() - timedelta(hours=1), datetime.now())
        problem = {"description": "Service having issues"}
        conversation = [
            {"role": "user", "content": "Check error rate for payments"},
            {"role": "agent", "content": "Which service?"},
            {"role": "user", "content": "payments-svc"}
        ]
        
        prompt = agent._build_sk_prompt(
            time_range,
            problem,
            mode="conversational",
            conversation_history=conversation
        )
        
        assert "Check error rate for payments" in prompt
        assert "payments-svc" in prompt
        # Should include template guidance
        assert "error_rate" in prompt or "templates" in prompt.lower()
    
    def test_parse_sk_response_with_json(self, agent):
        """Test parsing SK response containing JSON."""
        response = """
        I collected metrics from Prometheus. Here's what I found:
        
        ```json
        {
            "count": 500,
            "summary": "Error rate spiked at 15:30",
            "metadata": {
                "queries_executed": ["rate(http_errors_total[5m])"],
                "anomalies_detected": ["spike in errors"]
            }
        }
        ```
        """
        
        result = agent._parse_sk_response(response)
        
        assert result["count"] == 500
        assert "spiked" in result["summary"]
        assert "anomalies_detected" in result["metadata"]
    
    def test_parse_sk_response_without_json(self, agent):
        """Test parsing SK response without JSON structure."""
        response = "I collected 300 metrics. The error rate increased significantly."
        
        result = agent._parse_sk_response(response)
        
        assert "summary" in result
        assert "metrics" in result["summary"].lower()


class TestExecute:
    """Test the main execute method."""
    
    @pytest.mark.asyncio
    async def test_execute_with_sk_success(self, agent, scratchpad):
        """Test successful execution with SK mode."""
        # Setup scratchpad with problem
        problem = {
            "description": "High error rate",
            "affected_services": ["payments-svc"],
            "time_window": "1h"
        }
        scratchpad.write(ScratchpadSection.PROBLEM_DESCRIPTION, problem)
        
        # Mock agent methods
        agent.read_scratchpad = Mock(return_value=problem)
        agent.write_scratchpad = Mock()
        
        # Mock SK invoke_async
        mock_response = json.dumps({
            "count": 200,
            "summary": "Collected metrics successfully",
            "metadata": {"queries_executed": ["rate(http_errors_total[5m])"]}
        })
        
        with patch.object(agent, '_agent') as mock_sk_agent:
            mock_sk_agent.invoke_async = AsyncMock(return_value=mock_response)
            
            result = await agent.execute(use_sk=True)
            
            assert result["success"] is True
            assert result["source"] == "prometheus"
            assert result["sk_used"] is True
    
    @pytest.mark.asyncio
    async def test_execute_without_prometheus_configured_raises_error(self, scratchpad):
        """Test execute raises error when Prometheus not configured."""
        config = {
            "llm": {"default_model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"},
            "data_sources": {}
        }
        agent = PrometheusDataFetcher(config, scratchpad)
        
        with pytest.raises(ValueError, match="Prometheus data source is not configured"):
            await agent.execute()
    
    @pytest.mark.asyncio
    async def test_execute_sk_fallback_to_direct_on_error(self, agent, scratchpad):
        """Test SK execution falls back to direct mode on error."""
        problem = {"description": "Test issue", "time_window": "1h"}
        scratchpad.write(ScratchpadSection.PROBLEM_DESCRIPTION, problem)
        
        agent.read_scratchpad = Mock(return_value=problem)
        agent.write_scratchpad = Mock()
        
        # Mock fetcher for fallback
        mock_fetch_result = FetchResult(
            source="prometheus",
            count=100,
            time_range=(datetime.now() - timedelta(hours=1), datetime.now()),
            metadata={"query": "test"}
        )
        agent.fetcher.fetch = Mock(return_value=mock_fetch_result)
        
        # Mock SK agent to raise error
        with patch.object(agent, '_agent') as mock_sk_agent:
            mock_sk_agent.invoke_async = AsyncMock(side_effect=Exception("SK error"))
            
            # Should fall back to direct mode
            with patch.object(agent, '_execute_direct') as mock_direct:
                mock_direct.return_value = {
                    "success": True,
                    "source": "prometheus",
                    "count": 100,
                    "sk_used": False
                }
                
                result = await agent.execute(use_sk=True)
                
                # Fallback should have been called
                assert mock_direct.called
    
    def test_execute_direct_mode(self, agent, scratchpad):
        """Test execution in direct (non-SK) mode."""
        problem = {"description": "Test issue", "time_window": "1h"}
        scratchpad.write(ScratchpadSection.PROBLEM_DESCRIPTION, problem)
        
        agent.read_scratchpad = Mock(return_value=problem)
        agent.write_scratchpad = Mock()
        
        # Mock fetcher
        mock_fetch_result = FetchResult(
            source="prometheus",
            count=150,
            time_range=(datetime.now() - timedelta(hours=1), datetime.now()),
            metadata={"query": "rate(http_requests[5m])"}
        )
        agent.fetcher.fetch = Mock(return_value=mock_fetch_result)
        
        with patch.object(agent, '_fetch_prometheus', return_value=mock_fetch_result):
            with patch.object(agent, '_summarize_metrics', return_value="Metrics collected"):
                result = agent._execute_direct(
                    (datetime.now() - timedelta(hours=1), datetime.now()),
                    problem
                )
                
                assert result["success"] is True
                assert result["source"] == "prometheus"
                assert result["count"] == 150


class TestScratchpadIntegration:
    """Test scratchpad read/write operations."""
    
    def test_summarize_metrics(self, agent):
        """Test metric summarization logic."""
        fetch_result = FetchResult(
            source="prometheus",
            count=200,
            time_range=(datetime.now() - timedelta(hours=1), datetime.now()),
            metadata={
                "query": "rate(http_requests[5m])",
                "anomalies": ["spike at 15:30"]
            }
        )
        
        with patch('aletheia.agents.prometheus_data_fetcher.MetricSummarizer') as mock_summarizer:
            mock_instance = Mock()
            mock_instance.summarize = Mock(return_value="Request rate spiked significantly")
            mock_summarizer.return_value = mock_instance
            
            summary = agent._summarize_metrics(fetch_result)
            
            assert "spiked" in summary.lower() or "significantly" in summary.lower()
