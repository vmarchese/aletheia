from typing import Any



from semantic_kernel.agents import HandoffOrchestration, OrchestrationHandoffs
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.contents import ChatMessageContent, AuthorRole

from aletheia.agents.orchestrator import OrchestratorAgent
from aletheia.agents.kubernetes_data_fetcher import KubernetesDataFetcher
from aletheia.agents.prometheus_data_fetcher import PrometheusDataFetcher
from aletheia.agents.pattern_analyzer import PatternAnalyzerAgent
from aletheia.agents.log_file_data_fetcher import LogFileDataFetcher
from aletheia.utils.logging import log_debug
from aletheia.session import Session
from aletheia.agents.history import ConversationHistory

class AletheiaHandoffOrchestration:

    """Wrapper for SK HandoffOrchestration with Aletheia-specific configuration.
    
    This class manages the SK HandoffOrchestration with appropriate callbacks
    for scratchpad updates, user interaction, and progress tracking.
    """
    
    def __init__(
        self,
        session: Session,
        orchestration_agent: OrchestratorAgent,
        kubernetes_fetcher_agent: KubernetesDataFetcher,
        prometheus_fetcher_agent: PrometheusDataFetcher,
        pattern_analyzer_agent: PatternAnalyzerAgent,
        log_file_data_fetcher_agent: LogFileDataFetcher,
        console: Any,
    ):
        log_debug("AletheiaHandoffOrchestration::__init__:: called")
        self.console = console
        self.session = session
        log_debug("AletheiaHandoffOrchestration::__init__:: setting up handoffs")
        handoffs = (
            OrchestrationHandoffs()
            .add_many(
                source_agent=orchestration_agent.name,
                target_agents={
                    kubernetes_fetcher_agent.name: "Transfer to this agent if the user needs Kubernetes logs, pod information, or container data",
                    prometheus_fetcher_agent.name: "Transfer to this agent if the user needs Prometheus metrics, dashboards, time-series data, or PromQL queries",
                    pattern_analyzer_agent.name: "Transfer to this agent if the user wants to analyze patterns, anomalies, problems, errors or correlations in data",
                    log_file_data_fetcher_agent.name: "Transfer to this agent if the user needs to read the logs from a file",
                },
            ).add_many(
                source_agent=kubernetes_fetcher_agent.name,
                target_agents={
                    orchestration_agent.name: "Transfer back to orchestrator if you have completed your task"
                },
            ).add_many(
                source_agent=log_file_data_fetcher_agent.name,
                target_agents={
                    orchestration_agent.name: "Transfer back to orchestrator if you have completed your task"
                },
            ).add_many(
                source_agent=prometheus_fetcher_agent.name,
                target_agents={
                    orchestration_agent.name: "Transfer back to orchestrator if you have completed your task",
                },
            ).add_many(
                source_agent=pattern_analyzer_agent.name,
                target_agents={
                    orchestration_agent.name: "Transfer back to orchestrator if you have completed your task",
                },  
            )
        )

        self.conversation_history = ConversationHistory(session=session)
        self.orchestration_handoffs = HandoffOrchestration(
            members=[
                orchestration_agent.agent,
                kubernetes_fetcher_agent.agent,
                log_file_data_fetcher_agent.agent,
                prometheus_fetcher_agent.agent,
                pattern_analyzer_agent.agent
            ],
            handoffs=handoffs,
            agent_response_callback=self._agent_response_callback,
            human_response_function=self._human_response_function
        )
        
    
    def _agent_response_callback(self, message: ChatMessageContent) -> None:
        """Callback invoked when an agent produces a response.
        
        This is called for all agent responses, including tool calls and
        internal processing messages. We use this to update the scratchpad
        and provide feedback to the user.
        
        Args:
            message: The agent's response message
        """
        # Always display agent activity to make it clear who is operating
        if self.console and message.name:
            # Format agent name nicely
            agent_display_name = self._format_agent_name(message.name)
            
            # Show which agent is currently active
            if message.content:
                # Agent produced content - show it
                self.console.print(
                    f"\n[[bold yellow]{self.session.session_id}[/bold yellow]] [bold cyan]🤖 {agent_display_name}:[/bold cyan]",
                    end=" "
                )
                self.console.print(f"{message.content}")
                self.conversation_history.add_message(message)
            else:
                # Agent is processing (e.g., calling functions)
                self.console.print(
                    f"[dim yellow]{self.session.session_id}[/dim yellow][dim cyan]   → {agent_display_name} processing...[/dim cyan]"
                )
        
        # Update scratchpad based on agent and message content
        # This would be expanded as agents are converted to SK
        # For now, this is a placeholder for the pattern
        
    def _format_agent_name(self, agent_name: str) -> str:
        """Format agent name for display.
        
        Converts agent_name from snake_case to Title Case.
        
        Args:
            agent_name: Agent name in snake_case
        
        Returns:
            Formatted agent name for display
        """
        # Convert snake_case to Title Case
        # e.g., "data_fetcher" -> "Data Fetcher"
        return " ".join(word.capitalize() for word in agent_name.split("_"))
    
    def _human_response_function(self) -> ChatMessageContent:
        """Callback for human-in-the-loop interaction.
        
        This is called when an agent needs user input.
        
        Returns:
            ChatMessageContent with user input
        """
        from rich.prompt import Prompt
        
        # Prompt user for input
        user_input = Prompt.ask(f"\n[[bold yellow]{self.session.session_id}[/bold yellow]] [bold yellow]👤 Your input[/bold yellow]")
        
        content =  ChatMessageContent(
            role=AuthorRole.USER,
            content=user_input
        )
        self.conversation_history.add_message(content)
        return content
    
    def start_runtime(self) -> InProcessRuntime:
        """Start the SK InProcessRuntime."""
        runtime = InProcessRuntime()
        runtime.start()
        return runtime
    
    async def stop_runtime(self) -> None:
        """Stop the SK InProcessRuntime."""
        if self.runtime:
            await self.runtime.stop_when_idle()
            self.runtime = None
