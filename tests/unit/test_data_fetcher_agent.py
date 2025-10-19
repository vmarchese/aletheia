"""Unit tests for Data Fetcher Agent."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, AsyncMock, patch, PropertyMock

from aletheia.agents.data_fetcher import DataFetcherAgent
from aletheia.fetchers.base import FetchResult, FetchError, ConnectionError
from aletheia.scratchpad import Scratchpad, ScratchpadSection
from aletheia.llm.provider import LLMResponse


# Helper to create async generator mock for SK ChatCompletionAgent.invoke()
async def create_async_generator_response(content: str):
    """Create an async generator that yields a mock ChatMessageContent.
    
    This simulates the behavior of SK's ChatCompletionAgent.invoke() which
    returns an async generator that yields ChatMessageContent objects.
    """
    # Create a mock message with content attribute
    mock_message = Mock()
    mock_message.content = content
    yield mock_message


class TestDataFetcherAgentInitialization:
    """Test Data Fetcher Agent initialization."""
    
    def test_initialization_with_kubernetes(self):
        """Test initialization with Kubernetes configured."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {
                "kubernetes": {"context": "test-context", "namespace": "default"}
            }
        }
        scratchpad = Mock(spec=Scratchpad)
        
        agent = DataFetcherAgent(config, scratchpad)
        
        assert agent.agent_name == "data_fetcher"
        assert "kubernetes" in agent.fetchers
        assert agent.config == config
        assert agent.scratchpad == scratchpad
    
    def test_initialization_with_prometheus(self):
        """Test initialization with Prometheus configured."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {
                "prometheus": {"endpoint": "http://localhost:9090"}
            }
        }
        scratchpad = Mock(spec=Scratchpad)
        
        agent = DataFetcherAgent(config, scratchpad)
        
        assert "prometheus" in agent.fetchers
    
    def test_initialization_with_both_sources(self):
        """Test initialization with both Kubernetes and Prometheus."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {
                "kubernetes": {"context": "test-context"},
                "prometheus": {"endpoint": "http://localhost:9090"}
            }
        }
        scratchpad = Mock(spec=Scratchpad)
        
        agent = DataFetcherAgent(config, scratchpad)
        
        assert len(agent.fetchers) == 2
        assert "kubernetes" in agent.fetchers
        assert "prometheus" in agent.fetchers
    
    def test_initialization_without_data_sources(self):
        """Test initialization without data sources configured."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {}
        }
        scratchpad = Mock(spec=Scratchpad)
        
        agent = DataFetcherAgent(config, scratchpad)
        
        assert len(agent.fetchers) == 0


class TestDetermineSourcesa:
    """Test source determination logic."""
    
    def test_determine_sources_with_explicit_sources(self):
        """Test source determination with explicitly specified sources."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {
                "kubernetes": {"context": "test"},
                "prometheus": {"endpoint": "http://localhost:9090"}
            }
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        sources = agent._determine_sources(["kubernetes"], {})
        
        assert sources == ["kubernetes"]
    
    def test_determine_sources_without_specification(self):
        """Test source determination without explicit sources."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {
                "kubernetes": {"context": "test"},
                "prometheus": {"endpoint": "http://localhost:9090"}
            }
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        sources = agent._determine_sources(None, {})
        
        assert set(sources) == {"kubernetes", "prometheus"}
    
    def test_determine_sources_with_unavailable_source(self):
        """Test source determination with unavailable source requested."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {
                "kubernetes": {"context": "test"}
            }
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        sources = agent._determine_sources(["prometheus"], {})
        
        assert sources == []


class TestTimeWindowParsing:
    """Test time window parsing logic."""
    
    def test_parse_time_window_explicit(self):
        """Test parsing explicit time window."""
        config = {"llm": {"default_model": "gpt-4o-mini"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        start, end = agent._parse_time_window("2h", {})
        
        assert isinstance(start, datetime)
        assert isinstance(end, datetime)
        assert (end - start).total_seconds() == pytest.approx(7200, rel=1)
    
    def test_parse_time_window_from_problem(self):
        """Test parsing time window from problem description."""
        config = {"llm": {"default_model": "gpt-4o-mini"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        problem = {"time_window": "30m"}
        start, end = agent._parse_time_window(None, problem)
        
        assert (end - start).total_seconds() == pytest.approx(1800, rel=1)
    
    def test_parse_time_window_default(self):
        """Test parsing with default time window."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "session": {"default_time_window": "1h"}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        start, end = agent._parse_time_window(None, {})
        
        assert (end - start).total_seconds() == pytest.approx(3600, rel=1)


class TestKubernetesFetching:
    """Test Kubernetes data fetching."""
    
    def test_fetch_kubernetes_with_pod(self):
        """Test fetching Kubernetes logs with explicit pod."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test", "namespace": "default"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock fetcher
        mock_fetcher = Mock()
        mock_fetcher.config = {"namespace": "default"}
        mock_fetcher.fetch.return_value = FetchResult(
            source="kubernetes",
            data=[{"message": "error occurred"}],
            summary="1 log",
            count=1,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={}
        )
        agent.fetchers["kubernetes"] = mock_fetcher
        
        result = agent._fetch_kubernetes(
            mock_fetcher,
            (datetime.now() - timedelta(hours=2), datetime.now()),
            {},
            pod="test-pod"
        )
        
        assert result.count == 1
        mock_fetcher.fetch.assert_called_once()
    
    def test_fetch_kubernetes_discover_pod(self):
        """Test fetching Kubernetes logs with pod discovery."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test", "namespace": "default"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock fetcher
        mock_fetcher = Mock()
        mock_fetcher.config = {"namespace": "default"}
        mock_fetcher.list_pods.return_value = ["payments-svc-abc123"]
        mock_fetcher.fetch.return_value = FetchResult(
            source="kubernetes",
            data=[],
            summary="0 logs",
            count=0,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={}
        )
        agent.fetchers["kubernetes"] = mock_fetcher
        
        problem = {"affected_services": ["payments-svc"]}
        result = agent._fetch_kubernetes(
            mock_fetcher,
            (datetime.now() - timedelta(hours=2), datetime.now()),
            problem
        )
        
        mock_fetcher.list_pods.assert_called_once()
        mock_fetcher.fetch.assert_called_once()


class TestPrometheusFetching:
    """Test Prometheus data fetching."""
    
    def test_fetch_prometheus_with_query(self):
        """Test fetching Prometheus metrics with explicit query."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"prometheus": {"endpoint": "http://localhost:9090"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock fetcher
        mock_fetcher = Mock()
        mock_fetcher.fetch.return_value = FetchResult(
            source="prometheus",
            data={"metric": []},
            summary="0 data points",
            count=0,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={}
        )
        agent.fetchers["prometheus"] = mock_fetcher
        
        result = agent._fetch_prometheus(
            mock_fetcher,
            (datetime.now() - timedelta(hours=2), datetime.now()),
            {},
            query='rate(http_requests_total[5m])'
        )
        
        assert result.count == 0
        mock_fetcher.fetch.assert_called_once()
    
    def test_fetch_prometheus_with_template(self):
        """Test fetching Prometheus metrics with template."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"prometheus": {"endpoint": "http://localhost:9090"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock fetcher
        mock_fetcher = Mock()
        mock_fetcher.fetch.return_value = FetchResult(
            source="prometheus",
            data={"metric": []},
            summary="0 data points",
            count=0,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={}
        )
        agent.fetchers["prometheus"] = mock_fetcher
        
        result = agent._fetch_prometheus(
            mock_fetcher,
            (datetime.now() - timedelta(hours=2), datetime.now()),
            {},
            template="error_rate",
            template_params={"metric_name": "http_requests_total", "service": "test", "window": "5m"}
        )
        
        mock_fetcher.fetch.assert_called_once()
    
    def test_fetch_prometheus_auto_template(self):
        """Test fetching Prometheus metrics with automatic template selection."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"prometheus": {"endpoint": "http://localhost:9090"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock fetcher
        mock_fetcher = Mock()
        mock_fetcher.fetch.return_value = FetchResult(
            source="prometheus",
            data={"metric": []},
            summary="0 data points",
            count=0,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={}
        )
        agent.fetchers["prometheus"] = mock_fetcher
        
        problem = {"affected_services": ["payments-svc"]}
        result = agent._fetch_prometheus(
            mock_fetcher,
            (datetime.now() - timedelta(hours=2), datetime.now()),
            problem
        )
        
        # Should use error_rate template automatically
        call_kwargs = mock_fetcher.fetch.call_args[1]
        assert call_kwargs["template"] == "error_rate"


class TestSummarization:
    """Test data summarization."""
    
    def test_summarize_kubernetes_data(self):
        """Test summarizing Kubernetes log data."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        fetch_result = FetchResult(
            source="kubernetes",
            data=[
                {"level": "ERROR", "message": "Connection failed", "timestamp": "2025-10-14T10:00:00Z"},
                {"level": "ERROR", "message": "Connection failed", "timestamp": "2025-10-14T10:01:00Z"},
                {"level": "INFO", "message": "Started", "timestamp": "2025-10-14T10:02:00Z"},
            ],
            summary="3 logs",
            count=3,
            time_range=(datetime.now() - timedelta(hours=1), datetime.now()),
            metadata={}
        )
        
        summary = agent._summarize_data("kubernetes", fetch_result)
        
        assert isinstance(summary, str)
        assert len(summary) > 0
    
    def test_summarize_prometheus_data(self):
        """Test summarizing Prometheus metric data."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"prometheus": {"endpoint": "http://localhost:9090"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        fetch_result = FetchResult(
            source="prometheus",
            data=[
                {
                    "metric": {"__name__": "http_requests_total"},
                    "values": [[1697270400, "1.5"], [1697270460, "2.3"]]
                }
            ],
            summary="2 data points",
            count=2,
            time_range=(datetime.now() - timedelta(hours=1), datetime.now()),
            metadata={}
        )
        
        summary = agent._summarize_data("prometheus", fetch_result)
        
        assert isinstance(summary, str)
        assert len(summary) > 0


class TestExecute:
    """Test agent execution."""
    
    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful execution with data fetching (direct mode)."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test", "namespace": "default"}},
            "sampling": {
                "logs": {
                    "default_sample_size": 200,
                    "always_include_levels": ["ERROR"]
                }
            }
        }
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = {"time_window": "2h"}
        
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock fetcher
        mock_fetcher = Mock()
        mock_fetcher.config = {"namespace": "default"}
        mock_fetcher.fetch.return_value = FetchResult(
            source="kubernetes",
            data=[{"level": "ERROR", "message": "test"}],
            summary="1 log",
            count=1,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={}
        )
        agent.fetchers["kubernetes"] = mock_fetcher
        
        # Execute in direct mode (backward compatibility)
        result = await agent.execute(sources=["kubernetes"], pod="test-pod", use_sk=False)
        
        assert result["success"] is True
        assert "kubernetes" in result["sources_fetched"]
        assert len(result["sources_failed"]) == 0
        assert result["total_data_points"] == 1
        assert result["sk_used"] is False
        scratchpad.write_section.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_with_failure(self):
        """Test execution with fetching failure (direct mode)."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = {}
        
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock fetcher that fails
        mock_fetcher = Mock()
        mock_fetcher.config = {}
        mock_fetcher.fetch.side_effect = ConnectionError("Connection failed")
        agent.fetchers["kubernetes"] = mock_fetcher
        
        result = await agent.execute(sources=["kubernetes"], pod="test-pod", use_sk=False)
        
        assert result["success"] is False
        assert "kubernetes" in result["sources_failed"]
        assert result["total_data_points"] == 0
        assert result["sk_used"] is False
    
    @pytest.mark.asyncio
    async def test_execute_no_sources_error(self):
        """Test execution fails when no sources available."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {}
        }
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = {}
        
        agent = DataFetcherAgent(config, scratchpad)
        
        with pytest.raises(ValueError, match="No data sources"):
            await agent.execute(use_sk=False)
    
    @pytest.mark.asyncio
    async def test_execute_retry_logic(self):
        """Test that retry logic is applied on failures (direct mode)."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = {}
        
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock fetcher that fails twice then succeeds
        mock_fetcher = Mock()
        mock_fetcher.config = {}
        mock_fetcher.fetch.side_effect = [
            ConnectionError("Fail 1"),
            ConnectionError("Fail 2"),
            FetchResult(
                source="kubernetes",
                data=[],
                summary="0 logs",
                count=0,
                time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
                metadata={}
            )
        ]
        agent.fetchers["kubernetes"] = mock_fetcher
        
        result = await agent.execute(sources=["kubernetes"], pod="test-pod", use_sk=False)
        
        # Should succeed after retries
        assert result["success"] is True
        assert mock_fetcher.fetch.call_count == 3
        assert result["sk_used"] is False


class TestQueryGeneration:
    """Test LLM-assisted query generation."""
    
    def test_generate_query_prometheus(self):
        """Test generating a Prometheus query."""
        config = {
            "llm": {"default_model": "gpt-4o-mini", "api_key": "test-key"},
            "data_sources": {"prometheus": {"endpoint": "http://localhost:9090"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock LLM provider
        mock_llm = Mock()
        mock_llm.complete.return_value = LLMResponse(
            content='rate(http_requests_total{status="500"}[5m])',
            model="gpt-4o-mini",
            usage={"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
            finish_reason="stop",
            metadata={}
        )
        agent._llm_provider = mock_llm
        
        # Mock the template and compose functions
        with patch('aletheia.agents.data_fetcher.get_user_prompt_template') as mock_template:
            mock_template.return_value = Mock(format=Mock(return_value="test prompt"))
            with patch('aletheia.agents.data_fetcher.compose_messages') as mock_compose:
                mock_compose.return_value = []
                
                query = agent.generate_query(
                    source="prometheus",
                    intent="Show me error rate for payments service",
                    context={"service": "payments-svc"}
                )
                
                assert isinstance(query, str)
                assert len(query) > 0
                mock_llm.complete.assert_called_once()
    
    def test_validate_query_valid(self):
        """Test validating a valid query."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        is_valid = agent.validate_query("prometheus", "rate(http_requests_total[5m])")
        
        assert is_valid is True
    
    def test_validate_query_empty(self):
        """Test validating an empty query."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        is_valid = agent.validate_query("prometheus", "")
        
        assert is_valid is False


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_handle_fetch_error(self):
        """Test handling FetchError during execution (direct mode)."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = {}
        
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock fetcher that always fails
        mock_fetcher = Mock()
        mock_fetcher.config = {}
        mock_fetcher.fetch.side_effect = FetchError("Persistent failure")
        agent.fetchers["kubernetes"] = mock_fetcher
        
        result = await agent.execute(sources=["kubernetes"], pod="test-pod", use_sk=False)
        
        # Execution should complete but mark source as failed
        assert result["success"] is False
        assert "kubernetes" in result["sources_failed"]
        
        # Should still write to scratchpad with error info
        scratchpad.write_section.assert_called_once()
        call_args = scratchpad.write_section.call_args[0]
        assert "kubernetes" in call_args[1]
        assert "error" in call_args[1]["kubernetes"]
    
    def test_handle_unknown_source(self):
        """Test handling unknown data source in fetch."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        time_range = (datetime.now() - timedelta(hours=2), datetime.now())
        
        with pytest.raises(ValueError, match="Unknown data source"):
            agent._fetch_from_source("unknown", time_range, {})


class TestScratchpadIntegration:
    """Test scratchpad read/write operations."""
    
    @pytest.mark.asyncio
    async def test_write_to_scratchpad(self):
        """Test writing collected data to scratchpad (direct mode)."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = {}
        
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock fetcher
        mock_fetcher = Mock()
        mock_fetcher.config = {}
        mock_fetcher.fetch.return_value = FetchResult(
            source="kubernetes",
            data=[{"message": "test"}],
            summary="1 log",
            count=1,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={"pod": "test-pod"}
        )
        agent.fetchers["kubernetes"] = mock_fetcher
        
        await agent.execute(sources=["kubernetes"], pod="test-pod", use_sk=False)
        
        # Verify scratchpad write
        scratchpad.write_section.assert_called_once()
        section, data = scratchpad.write_section.call_args[0]
        
        assert section == ScratchpadSection.DATA_COLLECTED
        assert "kubernetes" in data
        assert data["kubernetes"]["source"] == "kubernetes"
        assert data["kubernetes"]["count"] == 1
        assert "summary" in data["kubernetes"]
        assert "metadata" in data["kubernetes"]
    
    @pytest.mark.asyncio
    async def test_read_problem_description(self):
        """Test reading problem description from scratchpad (direct mode)."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = {
            "description": "API errors",
            "time_window": "2h",
            "affected_services": ["payments-svc"]
        }
        
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock fetcher
        mock_fetcher = Mock()
        mock_fetcher.config = {}
        mock_fetcher.list_pods.return_value = ["payments-svc-abc"]
        mock_fetcher.fetch.return_value = FetchResult(
            source="kubernetes",
            data=[],
            summary="0 logs",
            count=0,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={}
        )
        agent.fetchers["kubernetes"] = mock_fetcher
        
        await agent.execute(sources=["kubernetes"], use_sk=False)
        
        # Should read problem description
        scratchpad.read_section.assert_called_with(ScratchpadSection.PROBLEM_DESCRIPTION)


class TestSKIntegration:
    """Test Semantic Kernel integration and SK-based execution."""
    
    def test_register_plugins(self):
        """Test plugin registration with SK kernel."""
        config = {
            "llm": {"default_model": "gpt-4o-mini", "api_key": "test-key"},
            "data_sources": {
                "kubernetes": {"context": "test-context"},
                "prometheus": {"endpoint": "http://localhost:9090"}
            }
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        # Register plugins
        agent._register_plugins()
        
        assert agent._plugins_registered is True
        # Verify plugins are registered with kernel
        assert hasattr(agent.kernel, 'plugins')
    
    def test_build_sk_prompt(self):
        """Test building SK prompt for data collection."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        sources = ["kubernetes"]
        time_range = (datetime(2025, 10, 15, 10, 0, 0), datetime(2025, 10, 15, 12, 0, 0))
        problem = {
            "description": "API errors in payments service",
            "affected_services": ["payments-svc"]
        }
        
        prompt = agent._build_sk_prompt(sources, time_range, problem, pod="test-pod")
        
        assert "Collect observability data" in prompt
        assert "API errors" in prompt
        assert "payments-svc" in prompt
        assert "kubernetes" in prompt
        assert "test-pod" in prompt
    
    def test_parse_sk_response_json(self):
        """Test parsing SK response with JSON data."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        response = '''Based on the logs collected:
{
    "kubernetes": {
        "count": 150,
        "summary": "150 logs collected, 45 errors found",
        "metadata": {"pod": "test-pod"}
    }
}
'''
        
        data = agent._parse_sk_response(response, ["kubernetes"])
        
        assert "kubernetes" in data
        assert data["kubernetes"]["count"] == 150
        assert "summary" in data["kubernetes"]
    
    def test_parse_sk_response_no_json(self):
        """Test parsing SK response without JSON."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        response = "I collected the data successfully but forgot to format it as JSON."
        
        data = agent._parse_sk_response(response, ["kubernetes"])
        
        # Should create minimal structure
        assert "kubernetes" in data
        assert data["kubernetes"]["count"] == 0
        assert "raw_response" in data["kubernetes"]["metadata"]
    
    @pytest.mark.asyncio
    async def test_execute_with_sk_mode(self):
        """Test execution in SK mode with mocked invoke."""
        config = {
            "llm": {"default_model": "gpt-4o-mini", "api_key": "test-key"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = {"time_window": "2h"}
        
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock SK invoke method
        mock_response = '''{
    "kubernetes": {
        "count": 50,
        "summary": "50 logs with 12 errors",
        "metadata": {}
    }
}'''
        agent.invoke_async = AsyncMock(return_value=mock_response)
        
        result = await agent.execute(sources=["kubernetes"], pod="test-pod", use_sk=True)
        
        assert result["success"] is True
        assert result["sk_used"] is True
        assert "kubernetes" in result["sources_fetched"]
        assert result["total_data_points"] == 50
        agent.invoke_async.assert_called_once()
        scratchpad.write_section.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_sk_fallback_to_direct(self):
        """Test SK mode falls back to direct mode on error."""
        config = {
            "llm": {"default_model": "gpt-4o-mini", "api_key": "test-key"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = {}
        
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock SK invoke to raise exception
        agent.invoke_async = AsyncMock(side_effect=Exception("SK failed"))
        
        # Mock fetcher for fallback
        mock_fetcher = Mock()
        mock_fetcher.config = {}
        mock_fetcher.fetch.return_value = FetchResult(
            source="kubernetes",
            data=[],
            summary="0 logs",
            count=0,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={}
        )
        agent.fetchers["kubernetes"] = mock_fetcher
        
        result = await agent.execute(sources=["kubernetes"], pod="test-pod", use_sk=True)
        
        # Should fall back to direct mode
        assert result["success"] is True
        assert result["sk_used"] is False
        mock_fetcher.fetch.assert_called()
    
    @pytest.mark.asyncio
    async def test_sk_mode_with_prometheus(self):
        """Test SK mode with Prometheus plugin."""
        config = {
            "llm": {"default_model": "gpt-4o-mini", "api_key": "test-key"},
            "data_sources": {"prometheus": {"endpoint": "http://localhost:9090"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = {}
        
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock SK invoke method
        mock_response = '''{
    "prometheus": {
        "count": 120,
        "summary": "120 metric data points collected",
        "metadata": {"query": "rate(http_requests_total[5m])"}
    }
}'''
        agent.invoke_async = AsyncMock(return_value=mock_response)
        
        result = await agent.execute(
            sources=["prometheus"],
            query="rate(http_requests_total[5m])",
            use_sk=True
        )
        
        assert result["success"] is True
        assert result["sk_used"] is True
        assert "prometheus" in result["sources_fetched"]
        assert result["total_data_points"] == 120
    
    def test_sk_prompt_includes_prometheus_params(self):
        """Test SK prompt includes Prometheus-specific parameters."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"prometheus": {"endpoint": "http://localhost:9090"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        sources = ["prometheus"]
        time_range = (datetime(2025, 10, 15, 10, 0, 0), datetime(2025, 10, 15, 12, 0, 0))
        problem = {"description": "High latency"}
        
        prompt = agent._build_sk_prompt(
            sources,
            time_range,
            problem,
            query="rate(http_requests_total[5m])",
            template="error_rate"
        )
        
        assert "Prometheus" in prompt
        assert "rate(http_requests_total[5m])" in prompt
        assert "error_rate" in prompt


class TestKubernetesParameterExtraction:
    """Test that LLM receives proper context to infer Kubernetes parameters."""
    
    def test_prompt_includes_problem_description(self):
        """Test that SK prompt includes full problem description for LLM inference."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        sources = ["kubernetes"]
        time_range = (datetime(2025, 10, 15, 10, 0, 0), datetime(2025, 10, 15, 12, 0, 0))
        problem = {
            "description": "The payments-svc-abc123 pod is crashing repeatedly in production namespace",
            "affected_services": ["payments-svc"]
        }
        
        prompt = agent._build_sk_prompt(sources, time_range, problem)
        
        # Verify full context is included
        assert "payments-svc-abc123" in prompt
        assert "production" in prompt
        assert "crashing repeatedly" in prompt
        # Simple prompt should include description directly
        assert "Collect observability data" in prompt
    
    def test_prompt_includes_user_input_context(self):
        """Test that SK prompt includes user-provided information."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        sources = ["kubernetes"]
        time_range = (datetime(2025, 10, 15, 10, 0, 0), datetime(2025, 10, 15, 12, 0, 0))
        problem = {
            "description": "High memory usage issue",
            "affected_services": ["api-service"],
            "user_input": {
                "pod_name": "api-service-xyz789",
                "namespace": "staging",
                "environment": "staging cluster"
            }
        }
        
        prompt = agent._build_sk_prompt(sources, time_range, problem)
        
        # Verify user input is included
        assert "Additional context" in prompt
        assert "api-service-xyz789" in prompt
        assert "staging" in prompt
        assert "staging cluster" in prompt
    
    def test_prompt_guides_llm_to_infer_pod(self):
        """Test that prompt provides context for LLM to extract parameters."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        sources = ["kubernetes"]
        time_range = (datetime(2025, 10, 15, 10, 0, 0), datetime(2025, 10, 15, 12, 0, 0))
        problem = {
            "description": "Service is down",
            "affected_services": []
        }
        
        prompt = agent._build_sk_prompt(sources, time_range, problem)
        
        # Verify context is provided and instructions to use plugins
        assert "Service is down" in prompt
        assert "plugin" in prompt.lower()
        assert "kubernetes" in prompt.lower()
    
    def test_prompt_guides_llm_to_infer_namespace(self):
        """Test that prompt provides context for LLM to extract namespace."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        sources = ["kubernetes"]
        time_range = (datetime(2025, 10, 15, 10, 0, 0), datetime(2025, 10, 15, 12, 0, 0))
        problem = {
            "description": "Issue in production environment",
            "affected_services": []
        }
        
        prompt = agent._build_sk_prompt(sources, time_range, problem)
        
        # Verify context is present (system prompt handles extraction)
        assert "production" in prompt.lower()
        assert "kubernetes" in prompt.lower()
    
    def test_explicit_kwargs_shown_in_prompt(self):
        """Test that explicitly provided kwargs are shown as specified in prompt."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        sources = ["kubernetes"]
        time_range = (datetime(2025, 10, 15, 10, 0, 0), datetime(2025, 10, 15, 12, 0, 0))
        problem = {
            "description": "Generic issue",
            "affected_services": []
        }
        
        prompt = agent._build_sk_prompt(
            sources, 
            time_range, 
            problem,
            pod="specific-pod-123",
            namespace="production"
        )
        
        # Verify explicit values are in the prompt
        assert "specific-pod-123" in prompt
        assert "production" in prompt
        # Should be under explicit parameters section
        assert "Explicit parameters" in prompt or "Pod: specific-pod-123" in prompt
    
    def test_fetch_kubernetes_uses_explicit_kwargs(self):
        """Test that _fetch_kubernetes uses explicitly provided kwargs."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock fetcher
        mock_fetcher = Mock()
        mock_fetcher.config = {}
        mock_fetcher.fetch.return_value = FetchResult(
            source="kubernetes",
            data=[{"message": "test", "level": "ERROR"}],
            summary="1 log",
            count=1,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={}
        )
        agent.fetchers["kubernetes"] = mock_fetcher
        
        problem = {
            "description": "Generic issue with some pod",
            "affected_services": []
        }
        
        # Provide explicit kwargs
        result = agent._fetch_kubernetes(
            mock_fetcher,
            (datetime.now() - timedelta(hours=2), datetime.now()),
            problem,
            pod="correct-pod-456",
            namespace="testing"
        )
        
        # Verify explicit kwargs are passed to fetcher
        call_kwargs = mock_fetcher.fetch.call_args[1]
        assert call_kwargs["pod"] == "correct-pod-456"
        assert call_kwargs["namespace"] == "testing"
    
    def test_fetch_kubernetes_falls_back_to_config(self):
        """Test that _fetch_kubernetes falls back to config when no kwargs provided."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test", "namespace": "my-namespace"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock fetcher
        mock_fetcher = Mock()
        mock_fetcher.config = {"namespace": "my-namespace"}
        mock_fetcher.list_pods.return_value = ["payments-svc-pod-123"]
        mock_fetcher.fetch.return_value = FetchResult(
            source="kubernetes",
            data=[{"message": "test", "level": "ERROR"}],
            summary="1 log",
            count=1,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={}
        )
        agent.fetchers["kubernetes"] = mock_fetcher
        
        problem = {
            "description": "The payments service pod is having issues",
            "affected_services": ["payments-svc"]
        }
        
        result = agent._fetch_kubernetes(
            mock_fetcher,
            (datetime.now() - timedelta(hours=2), datetime.now()),
            problem
        )
        
        # Verify namespace falls back to config
        call_kwargs = mock_fetcher.fetch.call_args[1]
        assert call_kwargs["namespace"] == "my-namespace"
        # Pod should be discovered from affected services
        assert call_kwargs["pod"] == "payments-svc-pod-123"
    
    def test_prompt_provides_context_for_llm_discovery(self):
        """Test that prompt provides context for LLM to work with."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        sources = ["kubernetes"]
        time_range = (datetime(2025, 10, 15, 10, 0, 0), datetime(2025, 10, 15, 12, 0, 0))
        problem = {
            "description": "The web server is returning 500 errors",
            "affected_services": ["web-server"]
        }
        
        prompt = agent._build_sk_prompt(sources, time_range, problem)
        
        # Verify context is present
        assert "web server" in prompt.lower()
        assert "500 errors" in prompt or "web-server" in prompt
        assert "plugin" in prompt.lower()


class TestConversationalMode:
    """Test conversational mode with LLM-delegated parameter extraction."""
    
    def test_build_sk_prompt_with_conversation_history(self):
        """Test that _build_sk_prompt includes conversation history in conversational mode."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        sources = ["kubernetes"]
        time_range = (datetime(2025, 10, 15, 10, 0, 0), datetime(2025, 10, 15, 12, 0, 0))
        problem = {
            "description": "Payment service errors",
            "affected_services": ["payments"]
        }
        
        # Provide conversation history
        conversation_history = [
            {"role": "user", "content": "Check the payments pod for errors"},
            {"role": "assistant", "content": "Sure, let me collect the logs."},
            {"role": "user", "content": "Look in the production namespace"}
        ]
        
        prompt = agent._build_sk_prompt(sources, time_range, problem, conversation_history=conversation_history)
        
        # Verify conversational template is used
        assert "Check the payments pod for errors" in prompt
        assert "production namespace" in prompt
        assert "CONVERSATION HISTORY" in prompt
    
    def test_build_sk_prompt_conversational_mode_uses_template(self):
        """Test that conversational mode uses the conversational prompt template."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}, "prometheus": {"endpoint": "http://localhost:9090"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        sources = ["kubernetes", "prometheus"]
        time_range = (datetime(2025, 10, 15, 10, 0, 0), datetime(2025, 10, 15, 12, 0, 0))
        problem = {"description": "High error rate"}
        
        conversation_history = [
            {"role": "user", "content": "Get logs from the api-gateway pod in staging"}
        ]
        
        prompt = agent._build_sk_prompt(sources, time_range, problem, conversation_history=conversation_history)
        
        # Verify conversational elements
        assert "api-gateway pod" in prompt
        assert "staging" in prompt
        assert "plugin" in prompt.lower()
    
    def test_build_sk_prompt_guided_mode_without_conversation(self):
        """Test that guided mode uses structured prompt without conversation history."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        sources = ["kubernetes"]
        time_range = (datetime(2025, 10, 15, 10, 0, 0), datetime(2025, 10, 15, 12, 0, 0))
        problem = {"description": "Payment errors"}
        
        # No conversation history - guided mode
        prompt = agent._build_sk_prompt(sources, time_range, problem)
        
        # Verify guided mode format (simple, direct prompt)
        assert "Payment errors" in prompt
        assert "Collect observability data" in prompt
        assert "CONVERSATION HISTORY" not in prompt
    
    @pytest.mark.asyncio
    async def test_execute_with_sk_reads_conversation_from_scratchpad(self):
        """Test that execute_with_sk reads conversation history from scratchpad."""
        config = {
            "llm": {"default_model": "gpt-4o-mini", "api_key_env": "OPENAI_API_KEY"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        
        # Mock scratchpad with conversation history
        scratchpad = Mock()
        conversation_history = [
            {"role": "user", "content": "Check the web pod logs"},
            {"role": "assistant", "content": "I'll fetch those logs now."}
        ]
        scratchpad.write = Mock()
        
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock read_scratchpad to return conversation history
        with patch.object(agent, 'read_scratchpad', side_effect=lambda section: conversation_history if section == ScratchpadSection.CONVERSATION_HISTORY else {}):
            # Mock SK agent invocation with async generator
            mock_agent = AsyncMock()
            response_content = '{"kubernetes": {"count": 10, "summary": "10 logs collected"}}'
            mock_agent.invoke = Mock(return_value=create_async_generator_response(response_content))
            agent._agent = mock_agent
            
            # Mock kernel property to avoid creating actual kernel
            with patch.object(type(agent), 'kernel', new_callable=PropertyMock) as mock_kernel_prop:
                mock_kernel = Mock()
                mock_kernel.add_plugin = Mock()
                mock_kernel_prop.return_value = mock_kernel
                
                sources = ["kubernetes"]
                time_range = (datetime.now() - timedelta(hours=2), datetime.now())
                problem = {"description": "Web errors"}
                
                result = await agent._execute_with_sk(sources, time_range, problem)
                
                # Verify result was successful
                assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_execute_with_sk_passes_conversation_to_prompt(self):
        """Test that conversation history is passed to _build_sk_prompt."""
        config = {
            "llm": {"default_model": "gpt-4o-mini", "api_key_env": "OPENAI_API_KEY"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        
        scratchpad = Mock()
        conversation_history = [
            {"role": "user", "content": "Look at the payments service"}
        ]
        scratchpad.write = Mock()
        
        agent = DataFetcherAgent(config, scratchpad)
        
        # Mock read_scratchpad to return conversation history
        with patch.object(agent, 'read_scratchpad', side_effect=lambda section: conversation_history if section == ScratchpadSection.CONVERSATION_HISTORY else {}):
            # Mock SK agent with async generator
            mock_agent = AsyncMock()
            response_content = '{"kubernetes": {"count": 5, "summary": "5 logs"}}'
            mock_agent.invoke = Mock(return_value=create_async_generator_response(response_content))
            agent._agent = mock_agent
            
            with patch.object(type(agent), 'kernel', new_callable=PropertyMock) as mock_kernel_prop:
                mock_kernel = Mock()
                mock_kernel.add_plugin = Mock()
                mock_kernel_prop.return_value = mock_kernel
                
                with patch.object(agent, '_build_sk_prompt', return_value="test prompt") as mock_build:
                    sources = ["kubernetes"]
                    time_range = (datetime.now() - timedelta(hours=2), datetime.now())
                    problem = {"description": "Errors"}
                    
                    await agent._execute_with_sk(sources, time_range, problem)
                    
                    # Verify _build_sk_prompt was called with conversation_history
                    call_kwargs = mock_build.call_args[1]
                    assert "conversation_history" in call_kwargs
                    assert call_kwargs["conversation_history"] == conversation_history
    
    def test_conversation_history_format_list_of_dicts(self):
        """Test that conversation history as list of dicts is formatted correctly."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        conversation_history = [
            {"role": "user", "content": "Check pod logs"},
            {"role": "assistant", "content": "Fetching logs"},
            {"role": "user", "content": "Look in production"}
        ]
        
        prompt = agent._build_sk_prompt(
            ["kubernetes"],
            (datetime.now() - timedelta(hours=2), datetime.now()),
            {"description": "Issues"},
            conversation_history=conversation_history
        )
        
        # Verify all messages are in prompt
        assert "Check pod logs" in prompt
        assert "Fetching logs" in prompt
        assert "Look in production" in prompt
    
    def test_conversation_history_format_string(self):
        """Test that conversation history as string is handled correctly."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        conversation_history = "user: Check the API logs\nassistant: I'll get those for you."
        
        prompt = agent._build_sk_prompt(
            ["kubernetes"],
            (datetime.now() - timedelta(hours=2), datetime.now()),
            {"description": "Issues"},
            conversation_history=conversation_history
        )
        
        # Verify conversation text is in prompt
        assert "Check the API logs" in prompt
    
    def test_conversational_prompt_includes_llm_extraction_instructions(self):
        """Test that conversational prompt instructs LLM to extract parameters."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        conversation_history = [
            {"role": "user", "content": "Get logs from payments-api in production namespace"}
        ]
        
        prompt = agent._build_sk_prompt(
            ["kubernetes"],
            (datetime.now() - timedelta(hours=2), datetime.now()),
            {"description": "Errors"},
            conversation_history=conversation_history
        )
        
        # Verify prompt includes extraction instructions
        assert "extract" in prompt.lower() or "identify" in prompt.lower()
        assert "parameter" in prompt.lower() or "pod" in prompt.lower()
    
    def test_conversational_prompt_includes_clarification_instructions(self):
        """Test that conversational prompt instructs LLM to ask clarifying questions."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = DataFetcherAgent(config, scratchpad)
        
        conversation_history = [
            {"role": "user", "content": "Get the logs"}
        ]
        
        prompt = agent._build_sk_prompt(
            ["kubernetes"],
            (datetime.now() - timedelta(hours=2), datetime.now()),
            {"description": "Issues"},
            conversation_history=conversation_history
        )
        
        # Verify prompt includes clarification instructions
        assert "ask" in prompt.lower() or "clarif" in prompt.lower() or "question" in prompt.lower()
        # Verify prompt is conversational
        assert "conversation" in prompt.lower() or "parameter" in prompt.lower()
