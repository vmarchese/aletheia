"""Unit tests for SK HandoffOrchestration integration."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from semantic_kernel.contents import ChatMessageContent, AuthorRole

from aletheia.agents.orchestration_sk import (
    AletheiaHandoffOrchestration,
    create_aletheia_handoffs,
    create_orchestration_with_sk_agents
)
from aletheia.scratchpad import Scratchpad


@pytest.fixture
def mock_scratchpad():
    """Create a mock scratchpad."""
    scratchpad = Mock(spec=Scratchpad)
    scratchpad.write_section = Mock()
    scratchpad.read_section = Mock(return_value={})
    return scratchpad


@pytest.fixture
def mock_console():
    """Create a mock Rich console."""
    console = Mock()
    console.print = Mock()
    return console


@pytest.fixture
def mock_agent():
    """Create a mock SK agent."""
    agent = Mock()
    agent.name = "test_agent"
    agent.description = "Test agent"
    return agent


class TestAletheiaHandoffOrchestration:
    """Tests for AletheiaHandoffOrchestration class."""
    
    def test_initialization_with_mock_orchestration(self, mock_agent, mock_scratchpad, mock_console):
        """Test orchestration initialization with mocked HandoffOrchestration."""
        agents = [mock_agent]
        handoffs = {}
        
        with patch('aletheia.agents.orchestration_sk.HandoffOrchestration') as mock_handoff_orch:
            mock_handoff_orch.return_value = Mock()
            
            orchestration = AletheiaHandoffOrchestration(
                agents=agents,
                handoffs=handoffs,
                scratchpad=mock_scratchpad,
                console=mock_console,
                confirmation_level="normal"
            )
            
            assert orchestration.agents == agents
            assert orchestration.handoffs == handoffs
            assert orchestration.scratchpad == mock_scratchpad
            assert orchestration.console == mock_console
            assert orchestration.confirmation_level == "normal"
            assert orchestration.runtime is None
            mock_handoff_orch.assert_called_once()
    
    def test_agent_response_callback_with_content(self, mock_agent, mock_scratchpad, mock_console):
        """Test agent response callback with message content."""
        with patch('aletheia.agents.orchestration_sk.HandoffOrchestration'):
            orchestration = AletheiaHandoffOrchestration(
                agents=[mock_agent],
                handoffs={},
                scratchpad=mock_scratchpad,
                console=mock_console
            )
            
            message = ChatMessageContent(
                role=AuthorRole.ASSISTANT,
                content="Test response",
                name="test_agent"
            )
            
            # Should not raise
            orchestration._agent_response_callback(message)
            
            # Console should print agent activity
            mock_console.print.assert_called_once()
    
    def test_agent_response_callback_without_content(self, mock_agent, mock_scratchpad, mock_console):
        """Test agent response callback without message content."""
        with patch('aletheia.agents.orchestration_sk.HandoffOrchestration'):
            orchestration = AletheiaHandoffOrchestration(
                agents=[mock_agent],
                handoffs={},
                scratchpad=mock_scratchpad,
                console=mock_console
            )
            
            message = ChatMessageContent(
                role=AuthorRole.ASSISTANT,
                content=None,
                name="test_agent"
            )
            
            # Should not raise
            orchestration._agent_response_callback(message)
            
            # Console should still print (with processing indicator)
            mock_console.print.assert_called_once()
    
    def test_human_response_function(self, mock_agent, mock_scratchpad, mock_console):
        """Test human response function."""
        with patch('aletheia.agents.orchestration_sk.HandoffOrchestration'):
            with patch('rich.prompt.Prompt.ask', return_value="User input"):
                orchestration = AletheiaHandoffOrchestration(
                    agents=[mock_agent],
                    handoffs={},
                    scratchpad=mock_scratchpad,
                    console=mock_console
                )
                
                response = orchestration._human_response_function()
                
                assert isinstance(response, ChatMessageContent)
                assert response.role == AuthorRole.USER
                assert response.content == "User input"
    
    @pytest.mark.asyncio
    async def test_start_runtime(self, mock_agent, mock_scratchpad, mock_console):
        """Test starting the runtime."""
        with patch('aletheia.agents.orchestration_sk.HandoffOrchestration'):
            with patch('aletheia.agents.orchestration_sk.InProcessRuntime') as mock_runtime_class:
                mock_runtime = Mock()
                mock_runtime.start = Mock()
                mock_runtime_class.return_value = mock_runtime
                
                orchestration = AletheiaHandoffOrchestration(
                    agents=[mock_agent],
                    handoffs={},
                    scratchpad=mock_scratchpad,
                    console=mock_console
                )
                
                await orchestration.start_runtime()
                
                assert orchestration.runtime is not None
                mock_runtime.start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_runtime(self, mock_agent, mock_scratchpad, mock_console):
        """Test stopping the runtime."""
        with patch('aletheia.agents.orchestration_sk.HandoffOrchestration'):
            with patch('aletheia.agents.orchestration_sk.InProcessRuntime') as mock_runtime_class:
                mock_runtime = Mock()
                mock_runtime.start = Mock()
                mock_runtime.stop_when_idle = AsyncMock()
                mock_runtime_class.return_value = mock_runtime
                
                orchestration = AletheiaHandoffOrchestration(
                    agents=[mock_agent],
                    handoffs={},
                    scratchpad=mock_scratchpad,
                    console=mock_console
                )
                
                await orchestration.start_runtime()
                await orchestration.stop_runtime()
                
                assert orchestration.runtime is None
                mock_runtime.stop_when_idle.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_invoke_without_runtime(self, mock_agent, mock_scratchpad, mock_console):
        """Test invoke raises error without runtime."""
        with patch('aletheia.agents.orchestration_sk.HandoffOrchestration'):
            orchestration = AletheiaHandoffOrchestration(
                agents=[mock_agent],
                handoffs={},
                scratchpad=mock_scratchpad,
                console=mock_console
            )
            
            with pytest.raises(RuntimeError, match="Runtime not started"):
                await orchestration.invoke("Test task")
    
    @pytest.mark.asyncio
    async def test_invoke_with_runtime(self, mock_agent, mock_scratchpad, mock_console):
        """Test invoke with runtime."""
        with patch('aletheia.agents.orchestration_sk.HandoffOrchestration') as mock_handoff_orch:
            with patch('aletheia.agents.orchestration_sk.InProcessRuntime') as mock_runtime_class:
                # Setup mocks
                mock_runtime = Mock()
                mock_runtime.start = Mock()
                mock_runtime_class.return_value = mock_runtime
                
                mock_result = Mock()
                mock_result.get = AsyncMock(return_value="Final result")
                
                mock_orch_instance = Mock()
                mock_orch_instance.invoke = AsyncMock(return_value=mock_result)
                mock_handoff_orch.return_value = mock_orch_instance
                
                orchestration = AletheiaHandoffOrchestration(
                    agents=[mock_agent],
                    handoffs={},
                    scratchpad=mock_scratchpad,
                    console=mock_console
                )
                
                await orchestration.start_runtime()
                result = await orchestration.invoke("Test task", timeout=10.0)
                
                assert result == "Final result"
                mock_orch_instance.invoke.assert_called_once()
                mock_result.get.assert_called_once_with(timeout=10.0)


class TestCreateAletheiaHandoffs:
    """Tests for create_aletheia_handoffs function."""
    
    def test_create_aletheia_handoffs_returns_dict(self):
        """Test that create_aletheia_handoffs returns a dict."""
        # This is a placeholder until agents are SK-based
        result = create_aletheia_handoffs()
        assert isinstance(result, dict)


class TestCreateOrchestrationWithSKAgents:
    """Tests for create_orchestration_with_sk_agents function."""
    
    def test_create_orchestration_with_agents(self, mock_scratchpad, mock_console):
        """Test creating orchestration with SK agents."""
        # Create mock agents
        data_fetcher = Mock()
        data_fetcher.name = "data_fetcher"
        data_fetcher.description = "Fetches data"
        
        pattern_analyzer = Mock()
        pattern_analyzer.name = "pattern_analyzer"
        pattern_analyzer.description = "Analyzes patterns"
        
        code_inspector = Mock()
        code_inspector.name = "code_inspector"
        code_inspector.description = "Inspects code"
        
        root_cause_analyst = Mock()
        root_cause_analyst.name = "root_cause_analyst"
        root_cause_analyst.description = "Analyzes root cause"
        
        # Mock both OrchestrationHandoffs and HandoffOrchestration
        with patch('aletheia.agents.orchestration_sk.OrchestrationHandoffs') as mock_handoffs_class:
            with patch('aletheia.agents.orchestration_sk.HandoffOrchestration') as mock_handoff_orch:
                # Setup mock handoffs
                mock_handoffs = Mock()
                mock_handoffs.Add = Mock(return_value=mock_handoffs)
                mock_handoffs_class.StartWith = Mock(return_value=mock_handoffs)
                
                # Setup mock orchestration
                mock_handoff_orch.return_value = Mock()
                
                orchestration = create_orchestration_with_sk_agents(
                    data_fetcher=data_fetcher,
                    pattern_analyzer=pattern_analyzer,
                    code_inspector=code_inspector,
                    root_cause_analyst=root_cause_analyst,
                    scratchpad=mock_scratchpad,
                    console=mock_console,
                    confirmation_level="verbose"
                )
                
                assert isinstance(orchestration, AletheiaHandoffOrchestration)
                assert orchestration.confirmation_level == "verbose"
                assert len(orchestration.agents) == 4
                
                # Verify handoffs were configured
                mock_handoffs_class.StartWith.assert_called_once_with(data_fetcher)
                # Verify Add was called (4 times for the handoff rules)
                assert mock_handoffs.Add.call_count == 4


class TestIntegration:
    """Integration tests for SK orchestration."""
    
    def test_orchestration_initialization_complete(self, mock_scratchpad, mock_console):
        """Test complete orchestration initialization."""
        with patch('aletheia.agents.orchestration_sk.HandoffOrchestration') as mock_handoff_orch:
            mock_handoff_orch.return_value = Mock()
            
            agents = [Mock(name=f"agent_{i}") for i in range(3)]
            handoffs = {}
            
            orchestration = AletheiaHandoffOrchestration(
                agents=agents,
                handoffs=handoffs,
                scratchpad=mock_scratchpad,
                console=mock_console,
                confirmation_level="minimal"
            )
            
            # Verify all components are properly initialized
            assert orchestration.agents == agents
            assert orchestration.handoffs == handoffs
            assert orchestration.scratchpad == mock_scratchpad
            assert orchestration.console == mock_console
            assert orchestration.runtime is None
            assert orchestration.orchestration is not None
