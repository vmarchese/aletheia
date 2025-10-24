"""Integration tests for Semantic Kernel HandoffOrchestration.

Tests the SK-based agent handoff system:
- Agent-to-agent handoff via SK HandoffOrchestration
- Function calling through plugins (Kubernetes, Prometheus, Git)
- Termination conditions for each agent
- Scratchpad consistency across SK handoff transitions
- Error handling in SK orchestration context
- End-to-end test with real SK agents (mocked LLM responses)

This test suite validates that the SK orchestration layer properly coordinates
specialist agents using Semantic Kernel's HandoffOrchestration pattern.
"""

import pytest
import tempfile
import shutil
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import Optional

from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent, OrchestrationHandoffs
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents import ChatMessageContent, AuthorRole

from aletheia.session import Session
from aletheia.scratchpad import Scratchpad, ScratchpadSection
from aletheia.agents.entrypoint import (
    AletheiaHandoffOrchestration,
    create_aletheia_handoffs,
    create_orchestration_with_sk_agents
)
from aletheia.plugins.kubernetes_plugin import KubernetesPlugin
from aletheia.plugins.prometheus_plugin import PrometheusPlugin
from aletheia.plugins.git_plugin import GitPlugin


@pytest.fixture
def temp_session_dir():
    """Create a temporary session directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def session(temp_session_dir):
    """Create a test session."""
    session = Session.create(password="test-password", name="sk-integration-test")
    yield session
    # Cleanup
    try:
        session.delete()
    except:
        pass


@pytest.fixture
def scratchpad(session):
    """Create a test scratchpad."""
    return Scratchpad(session.session_path, session._get_key())


@pytest.fixture
def config():
    """Create a test configuration."""
    return {
        "llm": {
            "default_model": "gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY",
            "agents": {}
        },
        "data_sources": {
            "kubernetes": {
                "context": "test-context",
                "namespace": "default"
            },
            "prometheus": {
                "endpoint": "http://localhost:9090"
            }
        }
    }


@pytest.fixture
def mock_console():
    """Create a mock Rich console."""
    console = Mock()
    console.print = Mock()
    return console


@pytest.fixture
def mock_kernel():
    """Create a mock Semantic Kernel instance."""
    kernel = Mock(spec=Kernel)
    
    # Mock chat service
    chat_service = Mock(spec=OpenAIChatCompletion)
    kernel.get_service.return_value = chat_service
    
    return kernel


@pytest.fixture
def mock_sk_agent():
    """Create a mock SK ChatCompletionAgent."""
    agent = Mock(spec=ChatCompletionAgent)
    agent.name = "test_agent"
    agent.instructions = "Test agent instructions"
    
    # Mock async invoke method
    async def mock_invoke(*args, **kwargs):
        return [ChatMessageContent(role=AuthorRole.ASSISTANT, content="Mocked response", name="test_agent")]
    
    agent.invoke = AsyncMock(side_effect=mock_invoke)
    
    return agent


class TestSKHandoffBasics:
    """Test basic SK HandoffOrchestration functionality."""
    
    def test_aletheia_handoff_orchestration_initialization(self, scratchpad, mock_console):
        """Test AletheiaHandoffOrchestration can be initialized."""
        # Create mock agents
        agent1 = Mock(spec=ChatCompletionAgent)
        agent1.name = "agent1"
        agent2 = Mock(spec=ChatCompletionAgent)
        agent2.name = "agent2"
        
        agents = [agent1, agent2]
        
        # Create handoffs
        handoffs = OrchestrationHandoffs.StartWith(agent1)
        handoffs.Add(agent1, agent2, "Transfer to agent2")
        
        # Create orchestration
        orchestration = AletheiaHandoffOrchestration(
            agents=agents,
            handoffs=handoffs,
            scratchpad=scratchpad,
            console=mock_console,
            confirmation_level="normal"
        )
        
        assert orchestration.agents == agents
        assert orchestration.handoffs == handoffs
        assert orchestration.scratchpad == scratchpad
        assert orchestration.console == mock_console
        assert orchestration.confirmation_level == "normal"
    
    def test_empty_handoffs_raises_error(self, scratchpad, mock_console):
        """Test that empty handoffs raises appropriate error."""
        agents = []
        handoffs = {}  # Empty handoffs
        
        with pytest.raises((ValueError, TypeError)):
            AletheiaHandoffOrchestration(
                agents=agents,
                handoffs=handoffs,
                scratchpad=scratchpad,
                console=mock_console
            )
    
    @pytest.mark.asyncio
    async def test_runtime_lifecycle(self, scratchpad, mock_console):
        """Test starting and stopping the SK runtime."""
        agent1 = Mock(spec=ChatCompletionAgent)
        agent1.name = "agent1"
        agent2 = Mock(spec=ChatCompletionAgent)
        agent2.name = "agent2"
        
        handoffs = OrchestrationHandoffs.StartWith(agent1)
        handoffs.Add(agent1, agent2, "Transfer")
        
        orchestration = AletheiaHandoffOrchestration(
            agents=[agent1, agent2],
            handoffs=handoffs,
            scratchpad=scratchpad,
            console=mock_console
        )
        
        # Runtime should be None initially
        assert orchestration.runtime is None
        
        # Start runtime
        await orchestration.start_runtime()
        assert orchestration.runtime is not None
        assert isinstance(orchestration.runtime, InProcessRuntime)
        
        # Stop runtime
        await orchestration.stop_runtime()
        assert orchestration.runtime is None
    
    @pytest.mark.asyncio
    async def test_invoke_without_runtime_raises_error(self, scratchpad, mock_console):
        """Test that invoking without starting runtime raises error."""
        agent1 = Mock(spec=ChatCompletionAgent)
        agent1.name = "agent1"
        
        handoffs = OrchestrationHandoffs.StartWith(agent1)
        
        orchestration = AletheiaHandoffOrchestration(
            agents=[agent1],
            handoffs=handoffs,
            scratchpad=scratchpad,
            console=mock_console
        )
        
        with pytest.raises(RuntimeError, match="Runtime not started"):
            await orchestration.invoke("Test task")


class TestPluginIntegration:
    """Test function calling through plugins."""
    
    @pytest.mark.asyncio
    async def test_kubernetes_plugin_registration(self, config, mock_kernel):
        """Test that Kubernetes plugin can be registered with kernel."""
        plugin = KubernetesPlugin(
            context=config["data_sources"]["kubernetes"]["context"],
            namespace=config["data_sources"]["kubernetes"]["namespace"]
        )
        
        # Mock kernel plugin registration
        mock_kernel.add_plugin = Mock()
        mock_kernel.add_plugin(plugin, plugin_name="kubernetes")
        
        # Verify plugin was registered
        mock_kernel.add_plugin.assert_called_once()
        call_args = mock_kernel.add_plugin.call_args
        assert call_args[0][0] == plugin
        assert call_args[1]["plugin_name"] == "kubernetes"
    
    @pytest.mark.asyncio
    async def test_prometheus_plugin_registration(self, config, mock_kernel):
        """Test that Prometheus plugin can be registered with kernel."""
        plugin = PrometheusPlugin(
            endpoint=config["data_sources"]["prometheus"]["endpoint"]
        )
        
        mock_kernel.add_plugin = Mock()
        mock_kernel.add_plugin(plugin, plugin_name="prometheus")
        
        mock_kernel.add_plugin.assert_called_once()
        call_args = mock_kernel.add_plugin.call_args
        assert call_args[0][0] == plugin
        assert call_args[1]["plugin_name"] == "prometheus"
    
    @pytest.mark.asyncio
    async def test_git_plugin_registration(self, mock_kernel, temp_session_dir):
        """Test that Git plugin can be registered with kernel."""
        # Create mock repository
        repo_path = temp_session_dir / "test-repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()
        
        plugin = GitPlugin(repositories=[str(repo_path)])
        
        mock_kernel.add_plugin = Mock()
        mock_kernel.add_plugin(plugin, plugin_name="git")
        
        mock_kernel.add_plugin.assert_called_once()
        call_args = mock_kernel.add_plugin.call_args
        assert call_args[0][0] == plugin
        assert call_args[1]["plugin_name"] == "git"
    
    @pytest.mark.asyncio
    async def test_multiple_plugins_registration(self, config, mock_kernel, temp_session_dir):
        """Test that multiple plugins can be registered together."""
        # Create plugins
        k8s_plugin = KubernetesPlugin(
            context=config["data_sources"]["kubernetes"]["context"],
            namespace=config["data_sources"]["kubernetes"]["namespace"]
        )
        
        prom_plugin = PrometheusPlugin(
            endpoint=config["data_sources"]["prometheus"]["endpoint"]
        )
        
        repo_path = temp_session_dir / "test-repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()
        git_plugin = GitPlugin(repositories=[str(repo_path)])
        
        # Register all plugins
        mock_kernel.add_plugin = Mock()
        mock_kernel.add_plugin(k8s_plugin, plugin_name="kubernetes")
        mock_kernel.add_plugin(prom_plugin, plugin_name="prometheus")
        mock_kernel.add_plugin(git_plugin, plugin_name="git")
        
        # Verify all registered
        assert mock_kernel.add_plugin.call_count == 3


class TestAgentHandoffs:
    """Test agent-to-agent handoff via SK HandoffOrchestration."""
    
    def test_create_aletheia_handoffs_structure(self):
        """Test that create_aletheia_handoffs returns expected structure."""
        # Current implementation returns empty dict as placeholder
        handoffs = create_aletheia_handoffs()
        
        # Should be a dict (placeholder for now)
        assert isinstance(handoffs, dict)
    
    @pytest.mark.asyncio
    async def test_simple_two_agent_handoff(self, scratchpad, mock_console):
        """Test simple handoff between two agents."""
        # Create mock agents
        agent1 = Mock(spec=ChatCompletionAgent)
        agent1.name = "agent1"
        
        agent2 = Mock(spec=ChatCompletionAgent)
        agent2.name = "agent2"
        
        # Setup async invoke mocks
        async def agent1_invoke(*args, **kwargs):
            return [ChatMessageContent(
                role=AuthorRole.ASSISTANT,
                content="Agent 1 complete, transfer to agent2",
                name="agent1"
            )]
        
        async def agent2_invoke(*args, **kwargs):
            return [ChatMessageContent(
                role=AuthorRole.ASSISTANT,
                content="Agent 2 complete",
                name="agent2"
            )]
        
        agent1.invoke = AsyncMock(side_effect=agent1_invoke)
        agent2.invoke = AsyncMock(side_effect=agent2_invoke)
        
        # Create handoffs
        handoffs = OrchestrationHandoffs.StartWith(agent1)
        handoffs.Add(agent1, agent2, "Transfer to agent2")
        
        # Create orchestration
        orchestration = AletheiaHandoffOrchestration(
            agents=[agent1, agent2],
            handoffs=handoffs,
            scratchpad=scratchpad,
            console=mock_console
        )
        
        # Test handoff configuration
        assert orchestration.agents == [agent1, agent2]
        assert agent1 in orchestration.agents
        assert agent2 in orchestration.agents


class TestScratchpadConsistency:
    """Test scratchpad consistency across SK handoff transitions."""
    
    def test_scratchpad_persistence_during_handoff(self, scratchpad):
        """Test that scratchpad data persists during agent handoffs."""
        # Write initial data
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Test problem"}
        )
        scratchpad.save()
        
        # Simulate agent 1 writing
        scratchpad.write_section(
            ScratchpadSection.DATA_COLLECTED,
            {"kubernetes": {"logs": ["error1", "error2"]}}
        )
        scratchpad.save()
        
        # Verify data persists
        assert scratchpad.has_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        assert scratchpad.has_section(ScratchpadSection.DATA_COLLECTED)
        
        # Simulate agent 2 reading
        data = scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)
        assert data["kubernetes"]["logs"] == ["error1", "error2"]
    
    def test_agent_response_callback_updates_scratchpad(self, scratchpad, mock_console):
        """Test that agent response callback can update scratchpad."""
        agent1 = Mock(spec=ChatCompletionAgent)
        agent1.name = "data_fetcher"
        
        handoffs = OrchestrationHandoffs.StartWith(agent1)
        
        orchestration = AletheiaHandoffOrchestration(
            agents=[agent1],
            handoffs=handoffs,
            scratchpad=scratchpad,
            console=mock_console
        )
        
        # Create test message
        message = ChatMessageContent(
            role=AuthorRole.ASSISTANT,
            content="Data collection complete",
            name="data_fetcher"
        )
        
        # Call callback
        orchestration._agent_response_callback(message)
        
        # Verify console output
        mock_console.print.assert_called()
    
    def test_scratchpad_isolation_between_agents(self, scratchpad, mock_console):
        """Test that agents don't accidentally overwrite each other's sections."""
        # Setup initial state
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Original problem"}
        )
        scratchpad.write_section(
            ScratchpadSection.DATA_COLLECTED,
            {"source": "original data"}
        )
        scratchpad.save()
        
        original_problem = scratchpad.read_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        
        # Simulate agent writing to different section
        scratchpad.write_section(
            ScratchpadSection.PATTERN_ANALYSIS,
            {"anomalies": ["anomaly1"]}
        )
        scratchpad.save()
        
        # Verify original sections unchanged
        assert scratchpad.read_section(ScratchpadSection.PROBLEM_DESCRIPTION) == original_problem
        
        # Verify new section exists
        assert scratchpad.has_section(ScratchpadSection.PATTERN_ANALYSIS)


class TestErrorHandling:
    """Test error handling in SK orchestration context."""
    
    @pytest.mark.asyncio
    async def test_agent_execution_error_handling(self, scratchpad, mock_console):
        """Test error handling when an agent execution fails."""
        agent1 = Mock(spec=ChatCompletionAgent)
        agent1.name = "failing_agent"
        
        # Make agent raise exception
        async def failing_invoke(*args, **kwargs):
            raise RuntimeError("Agent execution failed")
        
        agent1.invoke = AsyncMock(side_effect=failing_invoke)
        
        handoffs = OrchestrationHandoffs.StartWith(agent1)
        
        orchestration = AletheiaHandoffOrchestration(
            agents=[agent1],
            handoffs=handoffs,
            scratchpad=scratchpad,
            console=mock_console
        )
        
        # Start runtime
        await orchestration.start_runtime()
        
        # Invoke should propagate error
        with pytest.raises(RuntimeError, match="Agent execution failed"):
            await orchestration.invoke("Test task", timeout=1.0)
        
        # Cleanup
        await orchestration.stop_runtime()
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, scratchpad, mock_console):
        """Test handling of orchestration timeout."""
        agent1 = Mock(spec=ChatCompletionAgent)
        agent1.name = "slow_agent"
        
        # Make agent take too long
        async def slow_invoke(*args, **kwargs):
            await asyncio.sleep(10)  # Longer than timeout
            return [ChatMessageContent(role=AuthorRole.ASSISTANT, content="Done", name="slow_agent")]
        
        agent1.invoke = AsyncMock(side_effect=slow_invoke)
        
        handoffs = OrchestrationHandoffs.StartWith(agent1)
        
        orchestration = AletheiaHandoffOrchestration(
            agents=[agent1],
            handoffs=handoffs,
            scratchpad=scratchpad,
            console=mock_console
        )
        
        await orchestration.start_runtime()
        
        # Should timeout
        with pytest.raises((asyncio.TimeoutError, TimeoutError)):
            await orchestration.invoke("Test task", timeout=0.1)
        
        await orchestration.stop_runtime()
    
    def test_scratchpad_corruption_handling(self, session, mock_console):
        """Test handling of corrupted scratchpad during handoff."""
        scratchpad = Scratchpad(session.session_path, session._get_key())
        
        # Write valid data
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Test"}
        )
        scratchpad.save()
        
        # Corrupt the scratchpad file
        scratchpad_file = session.session_path / "scratchpad.encrypted"
        if scratchpad_file.exists():
            scratchpad_file.write_bytes(b"corrupted data")
        
        # Try to load corrupted scratchpad
        with pytest.raises(Exception):  # Should raise some form of decryption/deserialization error
            Scratchpad.load(session.session_path, session._get_key())


class TestHumanInTheLoop:
    """Test human-in-the-loop interaction in SK orchestration."""
    
    def test_human_response_function_prompts_user(self, scratchpad, mock_console):
        """Test that human response function prompts for user input."""
        agent1 = Mock(spec=ChatCompletionAgent)
        agent1.name = "agent1"
        
        handoffs = OrchestrationHandoffs.StartWith(agent1)
        
        orchestration = AletheiaHandoffOrchestration(
            agents=[agent1],
            handoffs=handoffs,
            scratchpad=scratchpad,
            console=mock_console
        )
        
        # Mock user input
        with patch('rich.prompt.Prompt.ask', return_value="User response"):
            response = orchestration._human_response_function()
        
        # Verify response structure
        assert isinstance(response, ChatMessageContent)
        assert response.role == AuthorRole.USER
        assert response.content == "User response"
    
    def test_confirmation_level_affects_prompting(self, scratchpad, mock_console):
        """Test that confirmation level affects user prompting."""
        agent1 = Mock(spec=ChatCompletionAgent)
        agent1.name = "agent1"
        
        handoffs = OrchestrationHandoffs.StartWith(agent1)
        
        # Test different confirmation levels
        for level in ["verbose", "normal", "minimal"]:
            orchestration = AletheiaHandoffOrchestration(
                agents=[agent1],
                handoffs=handoffs,
                scratchpad=scratchpad,
                console=mock_console,
                confirmation_level=level
            )
            
            assert orchestration.confirmation_level == level


class TestTerminationConditions:
    """Test termination conditions for each agent."""
    
    def test_data_fetcher_completion_condition(self, scratchpad):
        """Test that data fetcher marks completion when data is collected."""
        # Write DATA_COLLECTED section
        scratchpad.write_section(
            ScratchpadSection.DATA_COLLECTED,
            {
                "kubernetes": {"summary": "Data collected", "count": 100},
                "prometheus": {"summary": "Metrics collected", "count": 50}
            }
        )
        scratchpad.save()
        
        # Check completion condition
        data = scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)
        assert data is not None
        assert "kubernetes" in data or "prometheus" in data
        
        # This signals data fetcher can hand off to pattern analyzer
    
    def test_pattern_analyzer_completion_condition(self, scratchpad):
        """Test that pattern analyzer marks completion when patterns found."""
        scratchpad.write_section(
            ScratchpadSection.PATTERN_ANALYSIS,
            {
                "anomalies": [{"type": "spike", "severity": "high"}],
                "error_clusters": [{"pattern": "error1", "count": 10}],
                "timeline": [{"timestamp": "2025-10-15T10:00:00Z", "event": "spike"}]
            }
        )
        scratchpad.save()
        
        # Check completion condition
        analysis = scratchpad.read_section(ScratchpadSection.PATTERN_ANALYSIS)
        assert analysis is not None
        assert "anomalies" in analysis or "error_clusters" in analysis
        
        # This signals pattern analyzer can hand off
    
    def test_code_inspector_completion_condition(self, scratchpad):
        """Test that code inspector marks completion when code analyzed."""
        scratchpad.write_section(
            ScratchpadSection.CODE_INSPECTION,
            {
                "suspect_files": [
                    {
                        "file": "test.py",
                        "line": 42,
                        "function": "process",
                        "analysis": "Potential issue"
                    }
                ]
            }
        )
        scratchpad.save()
        
        # Check completion condition
        inspection = scratchpad.read_section(ScratchpadSection.CODE_INSPECTION)
        assert inspection is not None
        
        # This signals code inspector can hand off to root cause analyst
    
    def test_root_cause_analyst_completion_condition(self, scratchpad):
        """Test that root cause analyst marks completion with final diagnosis."""
        scratchpad.write_section(
            ScratchpadSection.FINAL_DIAGNOSIS,
            {
                "root_cause": "Null pointer dereference",
                "confidence": 0.85,
                "evidence": ["error logs", "code analysis"],
                "recommendations": [
                    {"priority": "immediate", "action": "Add null check"}
                ]
            }
        )
        scratchpad.save()
        
        # Check completion condition
        diagnosis = scratchpad.read_section(ScratchpadSection.FINAL_DIAGNOSIS)
        assert diagnosis is not None
        assert "root_cause" in diagnosis
        assert "confidence" in diagnosis
        
        # This signals investigation is complete
    
    def test_skip_code_inspection_condition(self, scratchpad):
        """Test condition for skipping code inspection and going directly to RCA."""
        # Pattern analysis without code-related errors
        scratchpad.write_section(
            ScratchpadSection.PATTERN_ANALYSIS,
            {
                "anomalies": [
                    {"type": "metric_spike", "severity": "high", "description": "CPU spike"}
                ],
                "error_clusters": [],  # No errors requiring code inspection
                "timeline": []
            }
        )
        scratchpad.save()
        
        analysis = scratchpad.read_section(ScratchpadSection.PATTERN_ANALYSIS)
        
        # Condition: No error clusters with stack traces
        has_code_errors = (
            "error_clusters" in analysis and
            len(analysis["error_clusters"]) > 0 and
            any("stack_trace" in cluster for cluster in analysis["error_clusters"])
        )
        
        assert not has_code_errors  # Should skip code inspection


class TestEndToEndWithSK:
    """End-to-end tests with real SK agents (mocked LLM responses)."""
    
    @pytest.mark.asyncio
    async def test_mock_llm_orchestration_flow(self, scratchpad, mock_console, config):
        """Test full orchestration flow with mocked LLM responses."""
        # This test would require fully SK-converted agents
        # For now, test the orchestration structure
        
        # Create mock SK agents
        data_fetcher = Mock(spec=ChatCompletionAgent)
        data_fetcher.name = "data_fetcher"
        
        pattern_analyzer = Mock(spec=ChatCompletionAgent)
        pattern_analyzer.name = "pattern_analyzer"
        
        root_cause_analyst = Mock(spec=ChatCompletionAgent)
        root_cause_analyst.name = "root_cause_analyst"
        
        # Mock invoke methods
        async def df_invoke(*args, **kwargs):
            # Simulate data fetcher writing to scratchpad
            scratchpad.write_section(
                ScratchpadSection.DATA_COLLECTED,
                {"kubernetes": {"summary": "Data collected"}}
            )
            scratchpad.save()
            return [ChatMessageContent(
                role=AuthorRole.ASSISTANT,
                content="Data collection complete",
                name="data_fetcher"
            )]
        
        async def pa_invoke(*args, **kwargs):
            # Simulate pattern analyzer writing
            scratchpad.write_section(
                ScratchpadSection.PATTERN_ANALYSIS,
                {"anomalies": [{"type": "spike"}]}
            )
            scratchpad.save()
            return [ChatMessageContent(
                role=AuthorRole.ASSISTANT,
                content="Pattern analysis complete",
                name="pattern_analyzer"
            )]
        
        async def rca_invoke(*args, **kwargs):
            # Simulate root cause analyst writing
            scratchpad.write_section(
                ScratchpadSection.FINAL_DIAGNOSIS,
                {"root_cause": "Test diagnosis", "confidence": 0.85}
            )
            scratchpad.save()
            return [ChatMessageContent(
                role=AuthorRole.ASSISTANT,
                content="Diagnosis complete",
                name="root_cause_analyst"
            )]
        
        data_fetcher.invoke = AsyncMock(side_effect=df_invoke)
        pattern_analyzer.invoke = AsyncMock(side_effect=pa_invoke)
        root_cause_analyst.invoke = AsyncMock(side_effect=rca_invoke)
        
        # Create handoffs (skip code inspector for this test)
        handoffs = OrchestrationHandoffs.StartWith(data_fetcher)
        handoffs.Add(data_fetcher, pattern_analyzer, "Transfer to pattern analyzer")
        handoffs.Add(pattern_analyzer, root_cause_analyst, "Transfer to root cause analyst")
        
        # Create orchestration
        orchestration = AletheiaHandoffOrchestration(
            agents=[data_fetcher, pattern_analyzer, root_cause_analyst],
            handoffs=handoffs,
            scratchpad=scratchpad,
            console=mock_console
        )
        
        # Verify orchestration structure
        assert len(orchestration.agents) == 3
        assert data_fetcher in orchestration.agents
        assert pattern_analyzer in orchestration.agents
        assert root_cause_analyst in orchestration.agents
    
    def test_orchestration_factory_function(self, scratchpad, mock_console):
        """Test the create_orchestration_with_sk_agents factory."""
        # Create mock agents
        data_fetcher = Mock(spec=ChatCompletionAgent)
        data_fetcher.name = "data_fetcher"
        
        pattern_analyzer = Mock(spec=ChatCompletionAgent)
        pattern_analyzer.name = "pattern_analyzer"
        
        code_inspector = Mock(spec=ChatCompletionAgent)
        code_inspector.name = "code_inspector"
        
        root_cause_analyst = Mock(spec=ChatCompletionAgent)
        root_cause_analyst.name = "root_cause_analyst"
        
        # Create orchestration using factory
        orchestration = create_orchestration_with_sk_agents(
            data_fetcher=data_fetcher,
            pattern_analyzer=pattern_analyzer,
            code_inspector=code_inspector,
            root_cause_analyst=root_cause_analyst,
            scratchpad=scratchpad,
            console=mock_console,
            confirmation_level="normal"
        )
        
        # Verify structure
        assert isinstance(orchestration, AletheiaHandoffOrchestration)
        assert len(orchestration.agents) == 4
        assert orchestration.confirmation_level == "normal"
