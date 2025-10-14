"""Unit tests for Data Fetcher Agent."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, PropertyMock

from aletheia.agents.data_fetcher import DataFetcherAgent
from aletheia.fetchers.base import FetchResult, FetchError, ConnectionError
from aletheia.scratchpad import Scratchpad, ScratchpadSection
from aletheia.llm.provider import LLMResponse


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
    
    def test_execute_success(self):
        """Test successful execution with data fetching."""
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
        
        result = agent.execute(sources=["kubernetes"], pod="test-pod")
        
        assert result["success"] is True
        assert "kubernetes" in result["sources_fetched"]
        assert len(result["sources_failed"]) == 0
        assert result["total_data_points"] == 1
        scratchpad.write_section.assert_called_once()
    
    def test_execute_with_failure(self):
        """Test execution with fetching failure."""
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
        
        result = agent.execute(sources=["kubernetes"], pod="test-pod")
        
        assert result["success"] is False
        assert "kubernetes" in result["sources_failed"]
        assert result["total_data_points"] == 0
    
    def test_execute_no_sources_error(self):
        """Test execution fails when no sources available."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {}
        }
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = {}
        
        agent = DataFetcherAgent(config, scratchpad)
        
        with pytest.raises(ValueError, match="No data sources"):
            agent.execute()
    
    def test_execute_retry_logic(self):
        """Test that retry logic is applied on failures."""
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
        
        result = agent.execute(sources=["kubernetes"], pod="test-pod")
        
        # Should succeed after retries
        assert result["success"] is True
        assert mock_fetcher.fetch.call_count == 3


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
    
    def test_handle_fetch_error(self):
        """Test handling FetchError during execution."""
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
        
        result = agent.execute(sources=["kubernetes"], pod="test-pod")
        
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
    
    def test_write_to_scratchpad(self):
        """Test writing collected data to scratchpad."""
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
        
        agent.execute(sources=["kubernetes"], pod="test-pod")
        
        # Verify scratchpad write
        scratchpad.write_section.assert_called_once()
        section, data = scratchpad.write_section.call_args[0]
        
        assert section == ScratchpadSection.DATA_COLLECTED
        assert "kubernetes" in data
        assert data["kubernetes"]["source"] == "kubernetes"
        assert data["kubernetes"]["count"] == 1
        assert "summary" in data["kubernetes"]
        assert "metadata" in data["kubernetes"]
    
    def test_read_problem_description(self):
        """Test reading problem description from scratchpad."""
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
        
        agent.execute(sources=["kubernetes"])
        
        # Should read problem description
        scratchpad.read_section.assert_called_with(ScratchpadSection.PROBLEM_DESCRIPTION)
