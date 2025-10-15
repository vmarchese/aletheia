"""Orchestrator agent for managing the investigation workflow.

This module provides the OrchestratorAgent class which manages the overall
investigation workflow, including:
- Session initialization
- User interaction (guided mode)
- Routing to specialist agents
- Presenting findings to the user
- Error handling and recovery

The orchestrator supports two modes:
1. Custom routing (legacy): Direct agent-to-agent routing
2. SK HandoffOrchestration: Using Semantic Kernel's orchestration pattern
"""

import asyncio
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from aletheia.agents.base import BaseAgent
from aletheia.scratchpad import ScratchpadSection

# SK orchestration support (optional, for future use)
try:
    from aletheia.agents.orchestration_sk import AletheiaHandoffOrchestration, create_aletheia_handoffs
    SK_ORCHESTRATION_AVAILABLE = True
except ImportError:
    SK_ORCHESTRATION_AVAILABLE = False


class InvestigationPhase(Enum):
    """Phases of the investigation workflow."""
    INITIALIZATION = "initialization"
    DATA_COLLECTION = "data_collection"
    PATTERN_ANALYSIS = "pattern_analysis"
    CODE_INSPECTION = "code_inspection"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    COMPLETED = "completed"


class OrchestratorAgent(BaseAgent):
    """Orchestrator agent that manages the investigation workflow.
    
    The orchestrator is responsible for:
    - Initializing investigation sessions
    - Managing user interaction in guided mode
    - Routing to appropriate specialist agents
    - Presenting findings to users
    - Handling errors and recovery
    
    Attributes:
        console: Rich console for formatted output
        current_phase: Current phase of the investigation
        agent_registry: Dictionary mapping agent names to agent instances
    """
    
    def __init__(self, config: Dict[str, Any], scratchpad, agent_name: Optional[str] = None):
        """Initialize the orchestrator agent.
        
        Args:
            config: Configuration dictionary
            scratchpad: Scratchpad instance for shared state
            agent_name: Optional agent name (defaults to 'orchestrator')
        """
        super().__init__(config, scratchpad, agent_name or "orchestrator")
        self.console = Console()
        self.current_phase = InvestigationPhase.INITIALIZATION
        self.agent_registry: Dict[str, BaseAgent] = {}
        
        # Get UI configuration
        ui_config = config.get("ui", {})
        self.confirmation_level = ui_config.get("confirmation_level", "normal")
        self.agent_visibility = ui_config.get("agent_visibility", False)
        
        # SK orchestration feature flag
        # Enable this when all agents are converted to SK ChatCompletionAgents
        self.use_sk_orchestration = self._should_use_sk_orchestration(config)
        self.sk_orchestration: Optional[Any] = None  # AletheiaHandoffOrchestration instance
    
    def _should_use_sk_orchestration(self, config: Dict[str, Any]) -> bool:
        """Determine if SK orchestration should be used.
        
        Checks (in order of precedence):
        1. Environment variable USE_SK_ORCHESTRATION
        2. Config setting orchestration.use_semantic_kernel
        3. Default: False (use custom routing)
        
        Args:
            config: Configuration dictionary
        
        Returns:
            True if SK orchestration should be used
        """
        # Environment variable takes precedence
        env_value = os.getenv("USE_SK_ORCHESTRATION", "").lower()
        if env_value in ("true", "1", "yes"):
            return SK_ORCHESTRATION_AVAILABLE and True
        if env_value in ("false", "0", "no"):
            return False
        
        # Check config
        orchestration_config = config.get("orchestration", {})
        use_sk = orchestration_config.get("use_semantic_kernel", False)
        
        return SK_ORCHESTRATION_AVAILABLE and use_sk
    
    def register_agent(self, name: str, agent: BaseAgent) -> None:
        """Register a specialist agent for routing.
        
        Args:
            name: Agent name (e.g., 'data_fetcher', 'pattern_analyzer')
            agent: Agent instance
        """
        self.agent_registry[name] = agent
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the orchestration workflow.
        
        This is the main entry point that coordinates the entire investigation.
        In guided mode, it prompts the user through each step.
        
        Args:
            **kwargs: Execution parameters (mode, initial_problem, etc.)
        
        Returns:
            Dictionary containing investigation results
        """
        mode = kwargs.get("mode", "guided")
        
        if mode == "guided":
            return self._execute_guided_mode(**kwargs)
        else:
            raise NotImplementedError(f"Mode '{mode}' not implemented yet")
    
    def _execute_guided_mode(self, **kwargs) -> Dict[str, Any]:
        """Execute investigation in guided (menu-driven) mode.
        
        Args:
            **kwargs: Execution parameters
        
        Returns:
            Dictionary containing investigation results
        """
        # Start session
        self._display_welcome()
        session_info = self.start_session(**kwargs)
        
        # Main investigation loop
        continue_investigation = True
        while continue_investigation:
            # Show current phase
            self._display_phase_status()
            
            # Route based on current phase
            if self.current_phase == InvestigationPhase.DATA_COLLECTION:
                success = self._route_data_collection()
                if success:
                    self.current_phase = InvestigationPhase.PATTERN_ANALYSIS
            
            elif self.current_phase == InvestigationPhase.PATTERN_ANALYSIS:
                success = self._route_pattern_analysis()
                if success:
                    self.current_phase = InvestigationPhase.CODE_INSPECTION
            
            elif self.current_phase == InvestigationPhase.CODE_INSPECTION:
                success = self._route_code_inspection()
                if success:
                    self.current_phase = InvestigationPhase.ROOT_CAUSE_ANALYSIS
            
            elif self.current_phase == InvestigationPhase.ROOT_CAUSE_ANALYSIS:
                success = self._route_root_cause_analysis()
                if success:
                    self.current_phase = InvestigationPhase.COMPLETED
                    continue_investigation = False
            
            elif self.current_phase == InvestigationPhase.COMPLETED:
                continue_investigation = False
        
        # Present final findings
        findings = self.present_findings()
        
        return {
            "status": "completed",
            "phase": self.current_phase.value,
            "session_info": session_info,
            "findings": findings
        }
    
    def start_session(self, **kwargs) -> Dict[str, Any]:
        """Initialize a new investigation session.
        
        Collects initial problem description and sets up the scratchpad.
        
        Args:
            **kwargs: Session parameters (problem_description, time_window, etc.)
        
        Returns:
            Dictionary containing session information
        """
        # Get problem description
        if "problem_description" in kwargs:
            problem_description = kwargs["problem_description"]
        else:
            problem_description = self._prompt_problem_description()
        
        # Get time window
        if "time_window" in kwargs:
            time_window = kwargs["time_window"]
        else:
            time_window = self._prompt_time_window()
        
        # Get affected services
        if "affected_services" in kwargs:
            affected_services = kwargs["affected_services"]
        else:
            affected_services = self._prompt_affected_services()
        
        # Write to scratchpad
        problem_data = {
            "description": problem_description,
            "time_window": time_window,
            "affected_services": affected_services,
            "interaction_mode": kwargs.get("mode", "guided"),
            "started_at": datetime.now().isoformat()
        }
        
        self.write_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION, problem_data)
        
        # Move to data collection phase
        self.current_phase = InvestigationPhase.DATA_COLLECTION
        
        self.console.print("[green]✓[/green] Session initialized successfully")
        
        return {
            "problem_description": problem_description,
            "time_window": time_window,
            "affected_services": affected_services
        }
    
    def route_to_agent(self, agent_name: str, **kwargs) -> Dict[str, Any]:
        """Route execution to a specialist agent.
        
        Args:
            agent_name: Name of the agent to route to
            **kwargs: Parameters to pass to the agent
        
        Returns:
            Dictionary containing agent execution results
        
        Raises:
            ValueError: If agent is not registered
        """
        if agent_name not in self.agent_registry:
            raise ValueError(f"Agent '{agent_name}' not registered")
        
        agent = self.agent_registry[agent_name]
        
        # Show agent execution (if visibility enabled)
        if self.agent_visibility:
            self.console.print(f"[cyan]→[/cyan] Executing {agent.__class__.__name__}")
        
        # Execute agent with error handling
        try:
            result = agent.execute(**kwargs)
            return {"success": True, "result": result}
        except Exception as e:
            return self.handle_error(agent_name, e)
    
    def handle_user_interaction(
        self,
        prompt_text: str,
        choices: Optional[List[str]] = None,
        default: Optional[str] = None
    ) -> str:
        """Handle user interaction with prompts and menus.
        
        Args:
            prompt_text: Text to display to the user
            choices: Optional list of choices for menu
            default: Optional default value
        
        Returns:
            User's input/choice
        """
        if choices:
            return self._display_menu(prompt_text, choices, default)
        else:
            return Prompt.ask(prompt_text, default=default)
    
    def present_findings(self) -> Dict[str, Any]:
        """Present investigation findings to the user.
        
        Displays the final diagnosis and recommendations from the scratchpad.
        
        Returns:
            Dictionary containing findings
        """
        # Read final diagnosis from scratchpad
        diagnosis = self.read_scratchpad(ScratchpadSection.FINAL_DIAGNOSIS)
        
        if not diagnosis:
            self.console.print("[yellow]⚠[/yellow] No diagnosis available")
            return {}
        
        # Display diagnosis
        self._display_diagnosis(diagnosis)
        
        return diagnosis
    
    def handle_error(self, agent_name: str, error: Exception) -> Dict[str, Any]:
        """Handle agent execution errors with recovery options.
        
        Args:
            agent_name: Name of the agent that failed
            error: The exception that occurred
        
        Returns:
            Dictionary containing error handling result
        """
        self.console.print(f"[red]✗[/red] Error in {agent_name}: {str(error)}")
        
        # Determine if error is retryable
        retryable = self._is_retryable_error(error)
        
        if retryable and self._should_retry():
            return self._retry_agent(agent_name)
        
        # Show recovery options
        recovery_action = self._prompt_recovery_action(agent_name)
        
        if recovery_action == "retry":
            return self._retry_agent(agent_name)
        elif recovery_action == "skip":
            return {"success": False, "skipped": True, "error": str(error)}
        elif recovery_action == "manual":
            return self._handle_manual_intervention(agent_name)
        else:  # abort
            raise error
    
    def _display_welcome(self) -> None:
        """Display welcome message."""
        panel = Panel(
            "[bold]Aletheia Investigation Assistant[/bold]\n\n"
            "I'll guide you through investigating production incidents.",
            title="Welcome",
            border_style="cyan"
        )
        self.console.print(panel)
        self.console.print()
    
    def _display_phase_status(self) -> None:
        """Display current investigation phase."""
        phase_names = {
            InvestigationPhase.INITIALIZATION: "Initialization",
            InvestigationPhase.DATA_COLLECTION: "Data Collection",
            InvestigationPhase.PATTERN_ANALYSIS: "Pattern Analysis",
            InvestigationPhase.CODE_INSPECTION: "Code Inspection",
            InvestigationPhase.ROOT_CAUSE_ANALYSIS: "Root Cause Analysis",
            InvestigationPhase.COMPLETED: "Completed"
        }
        
        phase_name = phase_names.get(self.current_phase, "Unknown")
        self.console.print(f"\n[bold cyan]Phase: {phase_name}[/bold cyan]\n")
    
    def _display_menu(
        self,
        prompt_text: str,
        choices: List[str],
        default: Optional[str] = None
    ) -> str:
        """Display a numbered menu and get user choice.
        
        Args:
            prompt_text: Menu prompt text
            choices: List of menu choices
            default: Optional default choice (1-indexed)
        
        Returns:
            Selected choice (zero-indexed)
        """
        self.console.print(prompt_text)
        for i, choice in enumerate(choices, 1):
            self.console.print(f"{i}. {choice}")
        
        while True:
            choice_str = Prompt.ask(
                "Select option",
                default=default or "1"
            )
            
            try:
                choice_num = int(choice_str)
                if 1 <= choice_num <= len(choices):
                    return choices[choice_num - 1]
                else:
                    self.console.print(f"[red]Please enter a number between 1 and {len(choices)}[/red]")
            except ValueError:
                self.console.print("[red]Please enter a valid number[/red]")
    
    def _display_diagnosis(self, diagnosis: Dict[str, Any]) -> None:
        """Display final diagnosis in formatted panel.
        
        Args:
            diagnosis: Diagnosis dictionary from scratchpad
        """
        # Extract diagnosis components
        root_cause = diagnosis.get("root_cause", {})
        confidence = root_cause.get("confidence", 0.0)
        description = root_cause.get("description", "No description available")
        
        # Create diagnosis panel
        panel_content = f"[bold]Confidence:[/bold] {confidence:.2f}\n\n"
        panel_content += f"[bold]Description:[/bold]\n{description}\n\n"
        
        # Add recommendations if available
        recommendations = diagnosis.get("recommended_actions", [])
        if recommendations:
            panel_content += "[bold]Recommended Actions:[/bold]\n"
            for rec in recommendations[:3]:  # Show top 3
                priority = rec.get("priority", "medium").upper()
                action = rec.get("action", "")
                panel_content += f"[{priority}] {action}\n"
        
        panel = Panel(
            panel_content,
            title="Root Cause Analysis",
            border_style="green" if confidence > 0.7 else "yellow"
        )
        self.console.print(panel)
    
    def _prompt_problem_description(self) -> str:
        """Prompt user for problem description.
        
        Returns:
            Problem description string
        """
        self.console.print("[bold]Describe the problem you're investigating:[/bold]")
        return Prompt.ask("Problem")
    
    def _prompt_time_window(self) -> str:
        """Prompt user for time window.
        
        Returns:
            Time window string (e.g., '2h', '30m')
        """
        choices = ["Last 30 minutes", "Last 2 hours", "Last 6 hours", "Custom"]
        choice = self._display_menu(
            "[bold]Select time window:[/bold]",
            choices
        )
        
        if choice == "Custom":
            return Prompt.ask("Enter time window (e.g., 2h, 30m)")
        elif choice == "Last 30 minutes":
            return "30m"
        elif choice == "Last 2 hours":
            return "2h"
        else:  # Last 6 hours
            return "6h"
    
    def _prompt_affected_services(self) -> List[str]:
        """Prompt user for affected services.
        
        Returns:
            List of service names
        """
        services_str = Prompt.ask(
            "[bold]Affected services[/bold] (comma-separated)",
            default=""
        )
        
        if not services_str:
            return []
        
        return [s.strip() for s in services_str.split(",") if s.strip()]
    
    def _route_data_collection(self) -> bool:
        """Route to data collection phase.
        
        Returns:
            True if successful, False otherwise
        """
        # Check if we should collect data
        if self._should_confirm("Collect data from sources?"):
            result = self.route_to_agent("data_fetcher")
            return result.get("success", False)
        else:
            return False
    
    def _route_pattern_analysis(self) -> bool:
        """Route to pattern analysis phase.
        
        Returns:
            True if successful, False otherwise
        """
        if self._should_confirm("Analyze patterns in collected data?"):
            result = self.route_to_agent("pattern_analyzer")
            return result.get("success", False)
        else:
            return False
    
    def _route_code_inspection(self) -> bool:
        """Route to code inspection phase.
        
        Returns:
            True if successful, False otherwise
        """
        # Check if user wants to skip code inspection
        choice = self._display_menu(
            "[bold]Code inspection:[/bold]",
            [
                "Inspect code (requires repository access)",
                "Skip code inspection and proceed to diagnosis"
            ]
        )
        
        if "Skip" in choice:
            return True  # Skip to next phase
        
        result = self.route_to_agent("code_inspector")
        return result.get("success", False)
    
    def _route_root_cause_analysis(self) -> bool:
        """Route to root cause analysis phase.
        
        Returns:
            True if successful, False otherwise
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            progress.add_task("Synthesizing findings...", total=None)
            result = self.route_to_agent("root_cause_analyst")
        
        return result.get("success", False)
    
    def _should_confirm(self, prompt_text: str) -> bool:
        """Check if confirmation is needed based on configuration.
        
        Args:
            prompt_text: Confirmation prompt text
        
        Returns:
            True if action should proceed
        """
        if self.confirmation_level == "minimal":
            return True
        elif self.confirmation_level == "verbose":
            return Confirm.ask(prompt_text, default=True)
        else:  # normal
            # Only confirm for major operations
            if "Collect data" in prompt_text or "repository" in prompt_text:
                return Confirm.ask(prompt_text, default=True)
            return True
    
    def _should_retry(self) -> bool:
        """Determine if agent should be retried automatically.
        
        Returns:
            True if should retry
        """
        # For now, always ask user
        return False
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if error is retryable.
        
        Args:
            error: Exception that occurred
        
        Returns:
            True if error can be retried
        """
        # Common retryable errors
        retryable_types = (
            ConnectionError,
            TimeoutError,
        )
        
        return isinstance(error, retryable_types)
    
    def _prompt_recovery_action(self, agent_name: str) -> str:
        """Prompt user for error recovery action.
        
        Args:
            agent_name: Name of the failed agent
        
        Returns:
            Recovery action ('retry', 'skip', 'manual', 'abort')
        """
        choices = [
            "Retry",
            "Skip this step",
            "Manual intervention",
            "Abort investigation"
        ]
        
        choice = self._display_menu(
            f"[bold yellow]What would you like to do?[/bold yellow]",
            choices
        )
        
        return choice.split()[0].lower()
    
    def _retry_agent(self, agent_name: str) -> Dict[str, Any]:
        """Retry agent execution.
        
        Args:
            agent_name: Name of agent to retry
        
        Returns:
            Dictionary containing retry result
        """
        self.console.print(f"[cyan]↻[/cyan] Retrying {agent_name}...")
        return self.route_to_agent(agent_name)
    
    def _handle_manual_intervention(self, agent_name: str) -> Dict[str, Any]:
        """Handle manual intervention for failed agent.
        
        Args:
            agent_name: Name of failed agent
        
        Returns:
            Dictionary containing intervention result
        """
        self.console.print(
            f"[yellow]Manual intervention required for {agent_name}[/yellow]"
        )
        self.console.print(
            "Please provide data manually or fix the issue, then press Enter to continue"
        )
        Prompt.ask("Press Enter when ready")
        
        return {"success": True, "manual": True}

