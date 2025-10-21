"""Unit tests for Kubernetes Data Fetcher Agent."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, AsyncMock, patch

from aletheia.agents.kubernetes_data_fetcher import KubernetesDataFetcher
from aletheia.fetchers.base import FetchResult, FetchError
from aletheia.scratchpad import Scratchpad, ScratchpadSection


# Helper to create async generator mock for SK ChatCompletionAgent.invoke()
async def create_async_generator_response(content: str):
    """Create an async generator that yields a mock ChatMessageContent.
    
    This simulates the behavior of SK's ChatCompletionAgent.invoke() which
    returns an async generator that yields ChatMessageContent objects.
    """
    mock_message = Mock()
    mock_message.content = content
    yield mock_message


class TestKubernetesDataFetcherInitialization:
    """Test Kubernetes Data Fetcher initialization."""
    
    def test_initialization_with_kubernetes_configured(self):
        """Test initialization with Kubernetes configured."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {
                "kubernetes": {"context": "test-context", "namespace": "default"}
            }
        }
        scratchpad = Mock(spec=Scratchpad)
        
        agent = KubernetesDataFetcher(config, scratchpad)
        
        assert agent.agent_name == "kubernetes_data_fetcher"
        assert agent.fetcher is not None
        assert agent.config == config
        assert agent.scratchpad == scratchpad
        assert agent._plugin_registered == False
    
    def test_initialization_without_kubernetes(self):
        """Test initialization without Kubernetes configured."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {}
        }
        scratchpad = Mock(spec=Scratchpad)
        
        agent = KubernetesDataFetcher(config, scratchpad)
        
        assert agent.fetcher is None


class TestPluginRegistration:
    """Test plugin registration logic."""
    
    def test_register_plugin(self):
        """Test plugin registration."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {
                "kubernetes": {"context": "test-context"}
            }
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        # Mock kernel
        agent._kernel = Mock()
        agent._kernel.add_plugin = Mock()
        
        agent._register_plugin()
        
        assert agent._plugin_registered == True
        agent._kernel.add_plugin.assert_called_once()
        assert agent._kernel.add_plugin.call_args[1]["plugin_name"] == "kubernetes"
    
    def test_register_plugin_idempotent(self):
        """Test that plugin registration is idempotent."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {
                "kubernetes": {"context": "test-context"}
            }
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        # Mock kernel
        agent._kernel = Mock()
        agent._kernel.add_plugin = Mock()
        
        # Register twice
        agent._register_plugin()
        agent._register_plugin()
        
        # Should only be called once
        assert agent._kernel.add_plugin.call_count == 1


class TestTimeWindowParsing:
    """Test time window parsing logic."""
    
    def test_parse_time_window_explicit(self):
        """Test parsing explicit time window."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        start, end = agent._parse_time_window("2h", {})
        
        assert isinstance(start, datetime)
        assert isinstance(end, datetime)
        assert (end - start).total_seconds() == pytest.approx(7200, rel=1)
    
    def test_parse_time_window_from_problem(self):
        """Test parsing time window from problem description."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        problem = {"time_window": "30m"}
        start, end = agent._parse_time_window(None, problem)
        
        assert (end - start).total_seconds() == pytest.approx(1800, rel=1)
    
    def test_parse_time_window_default(self):
        """Test parsing with default time window."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}},
            "session": {"default_time_window": "1h"}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        start, end = agent._parse_time_window(None, {})
        
        assert (end - start).total_seconds() == pytest.approx(3600, rel=1)


class TestParameterExtraction:
    """Test parameter extraction from problem descriptions."""
    
    def test_extract_pod_from_problem_explicit(self):
        """Test extracting pod name from explicit field."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        problem = {"pod": "payments-svc-abc123"}
        pod = agent._extract_pod_from_problem(problem)
        
        assert pod == "payments-svc-abc123"
    
    def test_extract_pod_from_description_colon(self):
        """Test extracting pod name from description with colon pattern."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        problem = {"description": "Check logs for pod: payments-svc-abc123"}
        pod = agent._extract_pod_from_problem(problem)
        
        assert pod == "payments-svc-abc123"
    
    def test_extract_pod_from_description_space(self):
        """Test extracting pod name from description with space pattern."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        problem = {"description": "Check pod payments-svc-abc123 logs"}
        pod = agent._extract_pod_from_problem(problem)
        
        assert pod == "payments-svc-abc123"
    
    def test_extract_pod_none_when_not_found(self):
        """Test that None is returned when pod is not found."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        problem = {"description": "Check logs for service"}
        pod = agent._extract_pod_from_problem(problem)
        
        assert pod is None
    
    def test_extract_namespace_from_problem_explicit(self):
        """Test extracting namespace from explicit field."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        problem = {"namespace": "production"}
        namespace = agent._extract_namespace_from_problem(problem)
        
        assert namespace == "production"
    
    def test_extract_namespace_from_description_colon(self):
        """Test extracting namespace from description with colon pattern."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        problem = {"description": "Check namespace: production for errors"}
        namespace = agent._extract_namespace_from_problem(problem)
        
        assert namespace == "production"
    
    def test_extract_namespace_none_when_not_found(self):
        """Test that None is returned when namespace is not found."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        problem = {"description": "Check logs"}
        namespace = agent._extract_namespace_from_problem(problem)
        
        assert namespace is None


class TestKubernetesFetching:
    """Test Kubernetes data fetching."""
    
    def test_fetch_kubernetes_with_explicit_pod(self):
        """Test fetching with explicit pod parameter."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test", "namespace": "default"}},
            "sampling": {"logs": {"default_sample_size": 200}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
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
        
        result = agent._fetch_kubernetes(
            mock_fetcher,
            (datetime.now() - timedelta(hours=2), datetime.now()),
            {},
            pod="test-pod"
        )
        
        assert result.count == 1
        mock_fetcher.fetch.assert_called_once()
        call_kwargs = mock_fetcher.fetch.call_args[1]
        assert call_kwargs["pod"] == "test-pod"
    
    def test_fetch_kubernetes_discover_pod_from_service(self):
        """Test fetching with pod discovery from affected services."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test", "namespace": "default"}},
            "sampling": {"logs": {"default_sample_size": 200}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
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
        
        problem = {"affected_services": ["payments-svc"]}
        result = agent._fetch_kubernetes(
            mock_fetcher,
            (datetime.now() - timedelta(hours=2), datetime.now()),
            problem
        )
        
        mock_fetcher.list_pods.assert_called_once()
        mock_fetcher.fetch.assert_called_once()
        call_kwargs = mock_fetcher.fetch.call_args[1]
        assert call_kwargs["pod"] == "payments-svc-abc123"
    
    def test_fetch_kubernetes_with_namespace_override(self):
        """Test fetching with namespace override."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test", "namespace": "default"}},
            "sampling": {"logs": {"default_sample_size": 200}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        # Mock fetcher
        mock_fetcher = Mock()
        mock_fetcher.config = {"namespace": "default"}
        mock_fetcher.fetch.return_value = FetchResult(
            source="kubernetes",
            data=[],
            summary="0 logs",
            count=0,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={}
        )
        
        result = agent._fetch_kubernetes(
            mock_fetcher,
            (datetime.now() - timedelta(hours=2), datetime.now()),
            {},
            pod="test-pod",
            namespace="production"
        )
        
        call_kwargs = mock_fetcher.fetch.call_args[1]
        assert call_kwargs["namespace"] == "production"


class TestSKIntegration:
    """Test Semantic Kernel integration."""
    
    def test_build_sk_prompt_guided_mode(self):
        """Test building SK prompt in guided mode."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        time_range = (datetime.now() - timedelta(hours=2), datetime.now())
        problem = {
            "description": "Payment service errors",
            "affected_services": ["payments-svc"]
        }
        
        prompt = agent._build_sk_prompt(time_range, problem)
        
        assert "Collect Kubernetes logs" in prompt
        assert "Payment service errors" in prompt
        assert "payments-svc" in prompt
        assert "kubernetes.fetch_kubernetes_logs()" in prompt
    
    def test_build_sk_prompt_conversational_mode(self):
        """Test building SK prompt in conversational mode."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        time_range = (datetime.now() - timedelta(hours=2), datetime.now())
        problem = {"description": "Payment service errors"}
        conversation_history = [
            {"role": "user", "content": "Check logs for payments pod"},
            {"role": "agent", "content": "Which namespace?"},
            {"role": "user", "content": "production"}
        ]
        
        with patch("aletheia.agents.kubernetes_data_fetcher.get_user_prompt_template") as mock_template:
            mock_template.return_value = "Problem: {problem_description}\nConversation: {conversation_history}"
            prompt = agent._build_sk_prompt(time_range, problem, conversation_history=conversation_history)
        
        assert "user: Check logs for payments pod" in prompt
        assert "user: production" in prompt
    
    def test_parse_sk_response_with_json(self):
        """Test parsing SK response with valid JSON."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        response = """I collected the logs. Here's what I found:
        {
            "count": 42,
            "summary": "Found 5 errors in the logs",
            "metadata": {"pod": "payments-svc-abc123", "namespace": "production"}
        }
        """
        
        result = agent._parse_sk_response(response)
        
        assert result["source"] == "kubernetes"
        assert result["count"] == 42
        assert result["summary"] == "Found 5 errors in the logs"
        assert result["metadata"]["pod"] == "payments-svc-abc123"
    
    def test_parse_sk_response_without_json(self):
        """Test parsing SK response without JSON."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        response = "I collected the logs successfully."
        
        result = agent._parse_sk_response(response)
        
        assert result["source"] == "kubernetes"
        assert result["count"] == 0
        assert "unexpected" in result["summary"].lower()


@pytest.mark.asyncio
class TestExecute:
    """Test execute methods."""
    
    async def test_execute_with_sk_success(self):
        """Test successful execution with SK mode."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}},
            "session": {"default_time_window": "2h"}
        }
        scratchpad = Mock(spec=Scratchpad)
        
        agent = KubernetesDataFetcher(config, scratchpad)
        
        # Mock scratchpad reads
        agent.read_scratchpad = Mock(return_value={"description": "Test problem"})
        
        # Mock SK components
        agent._register_plugin = Mock()
        agent.invoke_async = AsyncMock(return_value='{"count": 10, "summary": "Test logs"}')
        agent.write_scratchpad = Mock()
        
        result = await agent.execute(use_sk=True)
        
        assert result["success"] == True
        assert result["source"] == "kubernetes"
        assert result["sk_used"] == True
        agent._register_plugin.assert_called_once()
        agent.invoke_async.assert_called_once()
    
    async def test_execute_without_kubernetes_configured_raises_error(self):
        """Test that execute raises error when Kubernetes not configured."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        with pytest.raises(ValueError, match="not configured"):
            await agent.execute()
    
    async def test_execute_sk_fallback_to_direct_on_error(self):
        """Test that SK mode falls back to direct mode on error."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}},
            "sampling": {"logs": {"default_sample_size": 200}},
            "session": {"default_time_window": "2h"}
        }
        scratchpad = Mock(spec=Scratchpad)
        
        agent = KubernetesDataFetcher(config, scratchpad)
        
        # Mock scratchpad reads
        agent.read_scratchpad = Mock(return_value={"description": "Test problem"})
        
        # Mock fetcher for direct mode
        mock_fetcher = Mock()
        mock_fetcher.config = {"namespace": "default"}
        mock_fetcher.fetch.return_value = FetchResult(
            source="kubernetes",
            data=[],
            summary="0 logs",
            count=0,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={}
        )
        agent.fetcher = mock_fetcher
        
        # Mock SK failure
        agent._register_plugin = Mock()
        agent.invoke_async = AsyncMock(side_effect=Exception("SK error"))
        agent.write_scratchpad = Mock()
        
        result = await agent.execute(use_sk=True, pod="test-pod")
        
        assert result["success"] == True
        assert result["sk_used"] == False
        mock_fetcher.fetch.assert_called_once()
    
    async def test_execute_direct_mode(self):
        """Test execution in direct mode."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}},
            "sampling": {"logs": {"default_sample_size": 200}},
            "session": {"default_time_window": "2h"}
        }
        scratchpad = Mock(spec=Scratchpad)
        
        agent = KubernetesDataFetcher(config, scratchpad)
        
        # Mock scratchpad reads
        agent.read_scratchpad = Mock(return_value={"description": "Test problem"})
        
        # Mock fetcher
        mock_fetcher = Mock()
        mock_fetcher.config = {"namespace": "default"}
        mock_fetcher.fetch.return_value = FetchResult(
            source="kubernetes",
            data=[{"message": "error"}],
            summary="1 log",
            count=1,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={}
        )
        agent.fetcher = mock_fetcher
        agent.write_scratchpad = Mock()
        
        result = await agent.execute(use_sk=False, pod="test-pod")
        
        assert result["success"] == True
        assert result["source"] == "kubernetes"
        assert result["count"] == 1
        assert result["sk_used"] == False
        mock_fetcher.fetch.assert_called_once()


class TestScratchpadIntegration:
    """Test scratchpad integration."""
    
    def test_summarize_logs(self):
        """Test log summarization."""
        config = {
            "llm": {"default_model": "gpt-4o-mini"},
            "data_sources": {"kubernetes": {"context": "test"}}
        }
        scratchpad = Mock(spec=Scratchpad)
        agent = KubernetesDataFetcher(config, scratchpad)
        
        fetch_result = FetchResult(
            source="kubernetes",
            data=[
                {"message": "ERROR: Connection failed", "level": "ERROR"},
                {"message": "INFO: Starting service", "level": "INFO"}
            ],
            summary="2 logs",
            count=2,
            time_range=(datetime.now() - timedelta(hours=1), datetime.now()),
            metadata={}
        )
        
        summary = agent._summarize_logs(fetch_result)
        
        assert isinstance(summary, str)
        assert len(summary) > 0
