"""Semantic Kernel orchestration integration for Aletheia.

This module provides SK HandoffOrchestration integration for agent coordination,
replacing the custom routing logic with Semantic Kernel's orchestration pattern.
"""

import asyncio
from typing import Any, Dict, List, Optional, Callable

from semantic_kernel.agents import HandoffOrchestration, OrchestrationHandoffs, Agent
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.contents import ChatMessageContent, AuthorRole

from aletheia.scratchpad import Scratchpad, ScratchpadSection


class AletheiaHandoffOrchestration:
    """Wrapper for SK HandoffOrchestration with Aletheia-specific configuration.
    
    This class manages the SK HandoffOrchestration with appropriate callbacks
    for scratchpad updates, user interaction, and progress tracking.
    """
    
    def __init__(
        self,
        agents: List[Agent],
        handoffs: OrchestrationHandoffs,
        scratchpad: Scratchpad,
        console: Any,
        confirmation_level: str = "normal"
    ):
        """Initialize the Aletheia HandoffOrchestration.
        
        Args:
            agents: List of SK ChatCompletionAgent instances
            handoffs: OrchestrationHandoffs defining routing rules
            scratchpad: Scratchpad instance for shared state
            console: Rich console for output
            confirmation_level: Confirmation level (verbose/normal/minimal)
        """
        self.agents = agents
        self.handoffs = handoffs
        self.scratchpad = scratchpad
        self.console = console
        self.confirmation_level = confirmation_level
        self.runtime: Optional[InProcessRuntime] = None
        
        # Create orchestration with callbacks
        # Note: This will raise if handoffs is empty, which is expected
        # In production, handoffs should be properly configured with agents
        self.orchestration = HandoffOrchestration(
            members=agents,
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
                    f"\n[bold cyan]🤖 {agent_display_name}:[/bold cyan]",
                    end=" "
                )
                self.console.print(f"{message.content}")
            else:
                # Agent is processing (e.g., calling functions)
                self.console.print(
                    f"[dim cyan]   → {agent_display_name} processing...[/dim cyan]"
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
        
        This is called when an agent needs user input. In guided mode,
        we prompt the user for their response.
        
        Returns:
            ChatMessageContent with user input
        """
        from rich.prompt import Prompt
        
        # Prompt user for input
        user_input = Prompt.ask("\n[bold yellow]👤 Your input[/bold yellow]")
        
        return ChatMessageContent(
            role=AuthorRole.USER,
            content=user_input
        )
    
    async def start_runtime(self) -> None:
        """Start the SK InProcessRuntime."""
        self.runtime = InProcessRuntime()
        self.runtime.start()
    
    async def stop_runtime(self) -> None:
        """Stop the SK InProcessRuntime."""
        if self.runtime:
            await self.runtime.stop_when_idle()
            self.runtime = None
    
    async def invoke(self, task: str, timeout: float = 300.0) -> str:
        """Invoke the orchestration with a task.
        
        Args:
            task: The investigation task/problem description
            timeout: Timeout in seconds (default: 5 minutes)
        
        Returns:
            Final result from the orchestration
        
        Raises:
            RuntimeError: If runtime is not started
        """
        if not self.runtime:
            raise RuntimeError("Runtime not started. Call start_runtime() first.")
        
        # Display orchestration start
        if self.console:
            self.console.print("\n[bold]🔄 Starting Agent Orchestration[/bold]")
            self.console.print("[dim]Agents will coordinate to investigate the problem...[/dim]\n")
        
        # Invoke the orchestration
        orchestration_result = await self.orchestration.invoke(
            task=task,
            runtime=self.runtime
        )
        
        # Wait for results
        value = await orchestration_result.get(timeout=timeout)
        
        # Display completion
        if self.console:
            self.console.print("\n[bold green]✓ Orchestration Complete[/bold green]\n")
        
        return value


def create_aletheia_handoffs() -> OrchestrationHandoffs:
    """Create OrchestrationHandoffs for Aletheia agents.
    
    Defines the routing rules between specialist agents:
    - data_fetcher → pattern_analyzer (after data collection)
    - pattern_analyzer → code_inspector (after pattern analysis)
    - pattern_analyzer → root_cause_analyst (skip code inspection option)
    - code_inspector → root_cause_analyst (after code inspection)
    
    Returns:
        OrchestrationHandoffs configured for Aletheia workflow
    """
    # Note: This will be populated when agents are converted to SK
    # For now, this shows the structure
    
    # Placeholder - actual implementation requires SK agents
    # handoffs = OrchestrationHandoffs.StartWith(data_fetcher_agent)
    # handoffs.Add(data_fetcher_agent, pattern_analyzer_agent, "After data collection completes")
    # handoffs.Add(pattern_analyzer_agent, code_inspector_agent, "Analyze patterns in code")
    # handoffs.Add(pattern_analyzer_agent, root_cause_analyst_agent, "Skip code inspection")
    # handoffs.Add(code_inspector_agent, root_cause_analyst_agent, "After code inspection")
    
    # Return empty handoffs for now
    # This will be properly configured when agents are SK-based
    return {}  # type: ignore


def create_orchestration_with_sk_agents(
    data_fetcher: Agent,
    pattern_analyzer: Agent,
    code_inspector: Agent,
    root_cause_analyst: Agent,
    scratchpad: Scratchpad,
    console: Any,
    confirmation_level: str = "normal"
) -> AletheiaHandoffOrchestration:
    """Create AletheiaHandoffOrchestration with SK agents.
    
    This factory function will be used once all agents are converted to SK.
    
    Args:
        data_fetcher: SK-based DataFetcherAgent
        pattern_analyzer: SK-based PatternAnalyzerAgent  
        code_inspector: SK-based CodeInspectorAgent
        root_cause_analyst: SK-based RootCauseAnalystAgent
        scratchpad: Scratchpad for shared state
        console: Rich console for output
        confirmation_level: Confirmation level setting
    
    Returns:
        Configured AletheiaHandoffOrchestration
    """
    # Define handoff rules
    handoffs = OrchestrationHandoffs.StartWith(data_fetcher)
    handoffs.Add(
        data_fetcher,
        pattern_analyzer,
        "Transfer to pattern analyzer after data collection completes"
    )
    handoffs.Add(
        pattern_analyzer,
        code_inspector,
        "Transfer to code inspector to analyze source code"
    )
    handoffs.Add(
        pattern_analyzer,
        root_cause_analyst,
        "Transfer directly to root cause analyst if code inspection not needed"
    )
    handoffs.Add(
        code_inspector,
        root_cause_analyst,
        "Transfer to root cause analyst after code inspection completes"
    )
    
    # Create and return orchestration
    agents = [data_fetcher, pattern_analyzer, code_inspector, root_cause_analyst]
    
    return AletheiaHandoffOrchestration(
        agents=agents,
        handoffs=handoffs,
        scratchpad=scratchpad,
        console=console,
        confirmation_level=confirmation_level
    )
