"""Orchestrator agent for managing the investigation workflow.

This module provides the OrchestratorAgent class which manages the overall
investigation workflow, including:
- Session initialization
- User interaction (guided and conversational modes)
- Routing to specialist agents
- Presenting findings to the user
- Error handling and recovery

The orchestrator supports two interaction modes:
1. Guided mode: Menu-driven workflow with phase-based routing
2. Conversational mode: Natural language interaction with intent-based routing

And two routing strategies:
1. Custom routing (legacy): Direct agent-to-agent routing
2. SK HandoffOrchestration: Using Semantic Kernel's orchestration pattern
"""

import asyncio
import json
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
from aletheia.ui.conversation import ConversationalUI
from aletheia.utils.logging import log_agent_transition, is_trace_enabled

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


class UserIntent(Enum):
    """User intents in conversational mode."""
    FETCH_DATA = "fetch_data"
    ANALYZE_PATTERNS = "analyze_patterns"
    INSPECT_CODE = "inspect_code"
    DIAGNOSE = "diagnose"
    SHOW_FINDINGS = "show_findings"
    CLARIFY = "clarify"
    MODIFY_SCOPE = "modify_scope"
    OTHER = "other"


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
        self.conversational_ui = ConversationalUI(self.console)
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
        Supports both guided (menu-driven) and conversational (natural language) modes.
        
        Args:
            **kwargs: Execution parameters (mode, initial_problem, etc.)
        
        Returns:
            Dictionary containing investigation results
        """
        mode = kwargs.get("mode", "guided")
        
        if mode == "guided":
            return self._execute_guided_mode(**kwargs)
        elif mode == "conversational":
            return self._execute_conversational_mode(**kwargs)
        else:
            raise NotImplementedError(f"Mode '{mode}' not implemented yet")
    
    def _execute_guided_mode(self, **kwargs) -> Dict[str, Any]:
        """Execute investigation in guided (menu-driven) mode.
        
        Args:
            **kwargs: Execution parameters
        
        Returns:
            Dictionary containing investigation results
        """
        # Check if resuming an existing session
        is_resume = self.scratchpad.has_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        
        if is_resume:
            # Restore phase from scratchpad or determine from completed sections
            self._restore_phase_from_scratchpad()
            self.console.print("[cyan]Resuming investigation...[/cyan]")
            session_info = self.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION) or {}
        else:
            # Start new session
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
    
    def _execute_conversational_mode(self, **kwargs) -> Dict[str, Any]:
        """Execute investigation in conversational (natural language) mode.
        
        This mode allows users to interact naturally and the system routes
        to appropriate agents based on intent understanding.
        
        Args:
            **kwargs: Execution parameters
        
        Returns:
            Dictionary containing investigation results
        """
        # Check if resuming an existing session
        is_resume = self.scratchpad.has_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        
        if is_resume:
            self.console.print("[cyan]Resuming conversational session...[/cyan]")
            # Load conversation history
            conversation_history = self.read_scratchpad(ScratchpadSection.CONVERSATION_HISTORY) or []
            # Display recent conversation
            self.conversational_ui.display_conversation(conversation_history, show_all=False, max_messages=5)
        else:
            # Start new conversational session
            conversation_history = []
            
            # Display welcome message
            initial_message = kwargs.get("initial_message")
            self.conversational_ui.display_conversation_starter(problem_description=initial_message)
            
            # Get initial problem description if not provided
            if not initial_message:
                initial_message = self.conversational_ui.get_user_input(
                    prompt="Describe the problem you're investigating: "
                )
            
            # Add user's initial message to conversation
            conversation_history.append({
                "role": "user",
                "content": initial_message,
                "timestamp": datetime.now().isoformat()
            })
            
            # Process initial message to set up session
            self._process_initial_message(initial_message)
        
        # Main conversational loop
        investigation_complete = False
        
        while not investigation_complete:
            # Get user input using conversational UI
            user_message = self.conversational_ui.get_user_input()
            
            # Handle special commands
            if user_message.lower() in ["exit", "quit", "bye"]:
                self.console.print("[yellow]Ending investigation session.[/yellow]")
                break
            elif user_message.lower() == "help":
                self.conversational_ui.display_help()
                continue
            elif user_message.lower() == "history":
                self.conversational_ui.display_conversation(conversation_history, show_all=True)
                continue
            elif user_message.lower() == "status":
                self._display_investigation_status()
                continue
            
            # Add to conversation history
            conversation_history.append({
                "role": "user",
                "content": user_message,
                "timestamp": datetime.now().isoformat()
            })
            
            # Show agent is thinking
            self.conversational_ui.display_agent_thinking("Analyzing your request...")
            
            # Understand user intent using LLM
            intent_result = self._understand_user_intent(user_message, conversation_history)
            intent = intent_result.get("intent")
            parameters = intent_result.get("parameters", {})
            confidence = intent_result.get("confidence", 0.0)
            
            # Decide routing using LLM (LLM-First: no hardcoded logic)
            routing_decision = self._decide_next_agent(
                intent=intent,
                parameters=parameters,
                confidence=confidence,
                conversation_history=conversation_history
            )
            
            action = routing_decision.get("action")
            suggested_response = routing_decision.get("suggested_response", "")
            
            # Execute based on LLM's routing decision
            response = None
            if action == "clarify":
                # LLM determined we should clarify instead of routing to agent
                clarification_context = routing_decision.get("reasoning", "")
                self.conversational_ui.display_clarification_request(
                    question=suggested_response,
                    context=clarification_context if clarification_context else None
                )
                # Get clarification from user immediately
                continue
            elif action in self.agent_registry:
                # LLM determined we should route to a specialist agent
                self.conversational_ui.display_agent_thinking(f"Executing {action.replace('_', ' ')}...")
                response = self._execute_agent_and_generate_response(
                    agent_name=action,
                    parameters=parameters,
                    user_message=user_message
                )
                # Check if investigation is complete
                if action == "root_cause_analyst":
                    investigation_complete = self._check_if_complete()
            else:
                # Fallback if LLM returns unexpected action
                response = "I'm not sure how to proceed. Could you clarify your request?"
            
            # Display response using conversational UI
            if response:
                self.conversational_ui.format_agent_response(
                    response=response,
                    agent_name=action if action in self.agent_registry else None,
                    show_agent_name=self.agent_visibility
                )
                conversation_history.append({
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now().isoformat()
                })
            
            # Save conversation history to scratchpad
            self.write_scratchpad(ScratchpadSection.CONVERSATION_HISTORY, conversation_history)
        
        # Display session summary
        self.conversational_ui.display_session_summary(
            session_id=self.scratchpad.session_dir.name if self.scratchpad.session_dir else "unknown",
            status="completed" if investigation_complete else "interrupted",
            message_count=len(conversation_history)
        )
        
        # Get final findings
        findings = self.read_scratchpad(ScratchpadSection.FINAL_DIAGNOSIS) or {}
        
        return {
            "status": "completed" if investigation_complete else "interrupted",
            "mode": "conversational",
            "conversation_length": len(conversation_history),
            "findings": findings
        }
    
    def _understand_user_intent(
        self,
        user_message: str,
        conversation_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Understand user intent from their message using LLM.
        
        Args:
            user_message: The user's message
            conversation_history: Previous conversation messages
        
        Returns:
            Dictionary with intent, confidence, parameters, and reasoning
        """
        from aletheia.llm.prompts import get_system_prompt, get_user_prompt_template
        
        # Get current investigation state summary
        investigation_state = self._get_investigation_state_summary()
        
        # Format conversation history for prompt
        conv_history_str = "\n".join([
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in conversation_history[-5:]  # Last 5 messages for context
        ])
        
        # Build prompt
        intent_template = get_user_prompt_template("intent_understanding")
        user_prompt = intent_template.format(
            user_message=user_message,
            conversation_history=conv_history_str or "No previous conversation",
            investigation_state=investigation_state
        )
        
        # Get LLM response
        try:
            llm = self.get_llm()
            system_prompt = get_system_prompt("intent_understanding")
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = llm.complete(messages, temperature=0.3)  # Low temperature for consistent intent classification
            
            # Parse JSON response
            intent_data = json.loads(response)
            
            return intent_data
        
        except (json.JSONDecodeError, Exception) as e:
            # Fallback to default intent if parsing fails
            self.console.print(f"[yellow]Warning: Intent understanding failed: {e}[/yellow]")
            return {
                "intent": UserIntent.CLARIFY.value,
                "confidence": 0.0,
                "parameters": {},
                "reasoning": "Failed to parse intent"
            }
    
    def _decide_next_agent(
        self,
        intent: str,
        parameters: Dict[str, Any],
        confidence: float,
        conversation_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Decide which specialist agent to route to using LLM.
        
        This method delegates ALL routing logic to the LLM. No hardcoded mappings.
        
        Args:
            intent: User intent from intent understanding
            parameters: Extracted parameters from user message
            confidence: Confidence score of intent classification
            conversation_history: Recent conversation messages
        
        Returns:
            Dictionary with action, reasoning, prerequisites_met, and suggested_response
        """
        from aletheia.llm.prompts import get_system_prompt, get_user_prompt_template
        
        # Get current investigation state summary
        investigation_state = self._get_investigation_state_summary()
        
        # Format conversation context (last 3 messages)
        conversation_context = "\n".join([
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in conversation_history[-3:]
        ]) if conversation_history else "No previous conversation"
        
        # Build prompt for agent routing decision
        routing_template = get_user_prompt_template("agent_routing_decision")
        user_prompt = routing_template.format(
            intent=intent,
            confidence=confidence,
            parameters=json.dumps(parameters, indent=2),
            investigation_state=investigation_state,
            conversation_context=conversation_context
        )
        
        # Get LLM decision
        try:
            llm = self.get_llm()
            system_prompt = get_system_prompt("agent_routing")
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = llm.complete(messages, temperature=0.3)
            
            # Parse JSON response
            routing_decision = json.loads(response)
            
            return routing_decision
        
        except (json.JSONDecodeError, Exception) as e:
            # Fallback to clarification if parsing fails
            self.console.print(f"[yellow]Warning: Agent routing failed: {e}[/yellow]")
            return {
                "action": "clarify",
                "reasoning": "Failed to determine routing",
                "prerequisites_met": False,
                "suggested_response": "I need more information to proceed. Could you clarify your request?"
            }
    
    def _process_initial_message(self, initial_message: str) -> None:
        """Process the initial user message to set up the investigation.
        
        Args:
            initial_message: The user's initial message
        """
        # Use intent understanding to extract problem details
        intent_result = self._understand_user_intent(initial_message, [])
        parameters = intent_result.get("parameters", {})
        
        # Set up problem description in scratchpad
        problem_data = {
            "description": initial_message,
            "time_window": parameters.get("time_window", "2h"),
            "affected_services": parameters.get("services", []),
            "interaction_mode": "conversational",
            "started_at": datetime.now().isoformat(),
            "keywords": parameters.get("keywords", [])
        }
        
        self.write_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION, problem_data)
        
        self.console.print(
            f"[green]✓[/green] Investigation started. I understand you want to investigate: "
            f"[italic]{initial_message}[/italic]"
        )
    
    def _get_investigation_state_summary(self) -> str:
        """Get a summary of the current investigation state.
        
        Returns:
            String summary of completed sections and available data
        """
        state_parts = []
        
        if self.scratchpad.has_section(ScratchpadSection.PROBLEM_DESCRIPTION):
            state_parts.append("Problem description recorded")
        
        if self.scratchpad.has_section(ScratchpadSection.DATA_COLLECTED):
            data = self.read_scratchpad(ScratchpadSection.DATA_COLLECTED)
            if data:
                sources = list(data.keys())
                state_parts.append(f"Data collected from: {', '.join(sources)}")
        
        if self.scratchpad.has_section(ScratchpadSection.PATTERN_ANALYSIS):
            state_parts.append("Pattern analysis completed")
        
        if self.scratchpad.has_section(ScratchpadSection.CODE_INSPECTION):
            state_parts.append("Code inspection completed")
        
        if self.scratchpad.has_section(ScratchpadSection.FINAL_DIAGNOSIS):
            state_parts.append("Root cause diagnosis available")
        
        return "\n".join(state_parts) if state_parts else "Investigation just started"
    
    def _display_investigation_status(self) -> None:
        """Display the current investigation status to the user.
        
        This is a display-only method that shows what sections have been completed
        and what data is available.
        """
        status_summary = self._get_investigation_state_summary()
        
        self.console.print("\n[bold cyan]Investigation Status[/bold cyan]")
        self.console.print(f"[dim]{'─' * 50}[/dim]")
        self.console.print(status_summary)
        self.console.print(f"[dim]{'─' * 50}[/dim]\n")
    
    def _handle_fetch_data_intent(self, parameters: Dict[str, Any]) -> str:
        """Handle user intent to fetch data.
        
        Args:
            parameters: Extracted parameters (services, time_window, data_sources)
        
        Returns:
            Response message to user
        """
        # Update problem description with any new parameters
        self._update_problem_parameters(parameters)
        
        # Route to data fetcher agent
        result = self.route_to_agent("data_fetcher")
        
        if result.get("success"):
            return "I've collected the data. Would you like me to analyze it for patterns?"
        else:
            return f"I encountered an issue collecting data: {result.get('error', 'Unknown error')}"
    
    def _handle_analyze_patterns_intent(self, parameters: Dict[str, Any]) -> str:
        """Handle user intent to analyze patterns.
        
        Args:
            parameters: Extracted parameters
        
        Returns:
            Response message to user
        """
        # Check if we have data
        if not self.scratchpad.has_section(ScratchpadSection.DATA_COLLECTED):
            return "I need to collect data first. Would you like me to fetch logs and metrics?"
        
        # Route to pattern analyzer
        result = self.route_to_agent("pattern_analyzer")
        
        if result.get("success"):
            # Provide summary of findings
            patterns = self.read_scratchpad(ScratchpadSection.PATTERN_ANALYSIS)
            anomaly_count = len(patterns.get("anomalies", []))
            return f"I found {anomaly_count} significant patterns. Would you like to inspect the code or proceed to diagnosis?"
        else:
            return f"I encountered an issue analyzing patterns: {result.get('error', 'Unknown error')}"
    
    def _handle_inspect_code_intent(self, parameters: Dict[str, Any]) -> str:
        """Handle user intent to inspect code.
        
        Args:
            parameters: Extracted parameters (repositories)
        
        Returns:
            Response message to user
        """
        # Check dependencies
        if not self.scratchpad.has_section(ScratchpadSection.PATTERN_ANALYSIS):
            return "I should analyze patterns first to identify code locations. Shall I do that?"
        
        # Update with repository paths if provided
        if parameters.get("repositories"):
            # Store repository paths for code inspector
            pass
        
        # Route to code inspector
        result = self.route_to_agent("code_inspector")
        
        if result.get("success"):
            return "I've inspected the relevant code. Would you like me to provide a root cause diagnosis?"
        else:
            if result.get("skipped"):
                return "Code inspection was skipped. I can still provide a diagnosis based on the available data."
            return f"I encountered an issue inspecting code: {result.get('error', 'Unknown error')}"
    
    def _handle_diagnose_intent(self, parameters: Dict[str, Any]) -> str:
        """Handle user intent to get diagnosis.
        
        Args:
            parameters: Extracted parameters
        
        Returns:
            Response message to user
        """
        # Check if we have sufficient data
        if not self.scratchpad.has_section(ScratchpadSection.DATA_COLLECTED):
            return "I need to collect some data before I can provide a diagnosis. Shall I start?"
        
        # Route to root cause analyst
        result = self.route_to_agent("root_cause_analyst")
        
        if result.get("success"):
            # Present diagnosis
            diagnosis = self.read_scratchpad(ScratchpadSection.FINAL_DIAGNOSIS)
            root_cause = diagnosis.get("root_cause", {})
            confidence = root_cause.get("confidence", 0.0)
            description = root_cause.get("description", "No description available")
            
            response = f"Based on my analysis (confidence: {confidence:.2f}):\n\n{description}\n\n"
            response += "Would you like to see the detailed recommendations?"
            return response
        else:
            return f"I encountered an issue generating the diagnosis: {result.get('error', 'Unknown error')}"
    
    def _handle_show_findings_intent(self) -> str:
        """Handle user intent to show findings.
        
        Returns:
            Response message to user
        """
        # Present current findings
        self.present_findings()
        return "Is there anything else you'd like to investigate?"
    
    def _handle_clarify_intent(
        self,
        user_message: str,
        conversation_history: List[Dict[str, Any]]
    ) -> str:
        """Handle user clarification questions.
        
        Args:
            user_message: The user's clarification question
            conversation_history: Previous conversation
        
        Returns:
            Response to user's question
        """
        # Use LLM to generate contextual response
        try:
            llm = self.get_llm()
            
            # Build context from investigation state
            investigation_state = self._get_investigation_state_summary()
            
            system_prompt = """You are Aletheia, a troubleshooting assistant. Answer the user's question
based on the current investigation state. Be helpful, concise, and guide them toward next steps."""
            
            context_summary = f"Investigation state:\n{investigation_state}\n\nUser question: {user_message}"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_summary}
            ]
            
            response = llm.complete(messages, temperature=0.7)
            return response
        
        except Exception as e:
            return "I'm here to help investigate your issue. What would you like to know?"
    
    def _handle_modify_scope_intent(self, parameters: Dict[str, Any]) -> str:
        """Handle user intent to modify investigation scope.
        
        Args:
            parameters: New parameters (services, time_window, etc.)
        
        Returns:
            Response message to user
        """
        self._update_problem_parameters(parameters)
        
        changes = []
        if parameters.get("services"):
            changes.append(f"services to {', '.join(parameters['services'])}")
        if parameters.get("time_window"):
            changes.append(f"time window to {parameters['time_window']}")
        
        if changes:
            return f"I've updated the investigation scope: {', '.join(changes)}. What would you like me to do next?"
        else:
            return "What aspect of the investigation would you like to modify?"
    
    def _update_problem_parameters(self, parameters: Dict[str, Any]) -> None:
        """Update problem description with new parameters.
        
        Args:
            parameters: Parameters to update (services, time_window, etc.)
        """
        problem_data = self.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION) or {}
        
        if parameters.get("services"):
            problem_data["affected_services"] = parameters["services"]
        if parameters.get("time_window"):
            problem_data["time_window"] = parameters["time_window"]
        if parameters.get("keywords"):
            problem_data["keywords"] = parameters.get("keywords", [])
        
        problem_data["updated_at"] = datetime.now().isoformat()
        
        self.write_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION, problem_data)
    
    def _check_if_complete(self) -> bool:
        """Check if investigation is complete.
        
        Returns:
            True if investigation has reached a conclusion
        """
        return self.scratchpad.has_section(ScratchpadSection.FINAL_DIAGNOSIS)
    
    def _generate_clarification_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, Any]],
        reasoning: str
    ) -> str:
        """Generate a clarification response using LLM.
        
        This is called when the LLM determines clarification is needed instead of
        routing to a specialist agent.
        
        Args:
            user_message: The user's message
            conversation_history: Recent conversation
            reasoning: LLM's reasoning for why clarification is needed
        
        Returns:
            Clarification response to user
        """
        try:
            llm = self.get_llm()
            investigation_state = self._get_investigation_state_summary()
            
            system_prompt = """You are Aletheia, a helpful troubleshooting assistant.
Generate a clarifying response to guide the user. Be specific about what information is needed."""
            
            context = f"""User message: {user_message}

Investigation state:
{investigation_state}

Reason for clarification: {reasoning}

Generate a helpful response that:
1. Acknowledges the user's request
2. Explains what information is needed or what prerequisite is missing
3. Provides guidance on next steps"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ]
            
            return llm.complete(messages, temperature=0.7)
        
        except Exception as e:
            self.console.print(f"[yellow]Warning: Clarification generation failed: {e}[/yellow]")
            return "I need more information to proceed. Could you provide more details?"
    
    def _execute_agent_and_generate_response(
        self,
        agent_name: str,
        parameters: Dict[str, Any],
        user_message: str
    ) -> str:
        """Execute a specialist agent and generate a natural language response.
        
        This method:
        1. Updates scratchpad with parameters
        2. Routes to the specialist agent
        3. Generates a conversational response about the results
        
        Args:
            agent_name: Name of agent to execute
            parameters: Extracted parameters
            user_message: Original user message
        
        Returns:
            Natural language response to user
        """
        # Update problem parameters if provided
        if parameters:
            self._update_problem_parameters(parameters)
        
        # Execute the agent
        result = self.route_to_agent(agent_name)
        
        # Generate conversational response using LLM
        try:
            llm = self.get_llm()
            
            # Get what the agent found
            agent_results_summary = self._get_agent_results_summary(agent_name)
            
            system_prompt = f"""You are Aletheia, a troubleshooting assistant.
Generate a concise, conversational response about what the {agent_name.replace('_', ' ')} agent found.
Be natural, helpful, and suggest logical next steps."""
            
            context = f"""User requested: {user_message}

Agent executed: {agent_name}
Success: {result.get('success', False)}

Agent findings summary:
{agent_results_summary}

Generate a natural response that:
1. Summarizes what was found
2. Highlights key insights (if any)
3. Suggests next steps in the investigation"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ]
            
            return llm.complete(messages, temperature=0.7)
        
        except Exception as e:
            self.console.print(f"[yellow]Warning: Response generation failed: {e}[/yellow]")
            # Fallback response
            if result.get("success"):
                return f"I've completed the {agent_name.replace('_', ' ')} step. What would you like to do next?"
            else:
                return f"I encountered an issue with the {agent_name.replace('_', ' ')} step: {result.get('error', 'Unknown error')}"
    
    def _get_agent_results_summary(self, agent_name: str) -> str:
        """Get a summary of what an agent found in the scratchpad.
        
        Args:
            agent_name: Name of the agent
        
        Returns:
            Summary string of findings
        """
        # Map agents to their scratchpad sections
        agent_section_map = {
            "data_fetcher": ScratchpadSection.DATA_COLLECTED,
            "pattern_analyzer": ScratchpadSection.PATTERN_ANALYSIS,
            "code_inspector": ScratchpadSection.CODE_INSPECTION,
            "root_cause_analyst": ScratchpadSection.FINAL_DIAGNOSIS
        }
        
        section = agent_section_map.get(agent_name)
        if not section or not self.scratchpad.has_section(section):
            return "No results available yet"
        
        data = self.read_scratchpad(section)
        
        # Create a brief summary (avoid dumping entire scratchpad)
        if agent_name == "data_fetcher":
            sources = list(data.keys()) if isinstance(data, dict) else []
            return f"Collected data from {len(sources)} source(s): {', '.join(sources)}"
        elif agent_name == "pattern_analyzer":
            anomaly_count = len(data.get("anomalies", [])) if isinstance(data, dict) else 0
            return f"Found {anomaly_count} anomalies/patterns"
        elif agent_name == "code_inspector":
            findings = data.get("findings", []) if isinstance(data, dict) else []
            return f"Inspected {len(findings)} code location(s)"
        elif agent_name == "root_cause_analyst":
            root_cause = data.get("root_cause", {}) if isinstance(data, dict) else {}
            confidence = root_cause.get("confidence", 0.0)
            return f"Generated diagnosis with {confidence:.0%} confidence"
        
        return "Analysis complete"
    
    def _display_welcome_conversational(self) -> None:
        """Display welcome message for conversational mode."""
        panel = Panel(
            "[bold]Aletheia Investigation Assistant[/bold]\n\n"
            "I'll help you investigate production incidents through natural conversation.\n"
            "Just tell me what you'd like to investigate or ask questions as we go.\n\n"
            "Type 'exit' or 'quit' to end the session.",
            title="Welcome to Conversational Mode",
            border_style="cyan"
        )
        self.console.print(panel)
        self.console.print()
    
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
        
        # Log agent transition if trace logging is enabled
        if is_trace_enabled():
            from_agent = getattr(self, '_last_agent', None)
            log_agent_transition(
                from_agent=from_agent,
                to_agent=agent_name,
                reason=f"Phase: {self.current_phase.value if hasattr(self, 'current_phase') else 'unknown'}"
            )
            self._last_agent = agent_name
        
        # Always show which agent is executing for transparency
        agent_display_name = self._format_agent_name(agent_name)
        self.console.print(f"\n[bold cyan]🤖 {agent_display_name}:[/bold cyan] Starting...")
        
        # Execute agent with error handling
        try:
            result = agent.execute(**kwargs)
            self.console.print(f"[green]✓[/green] {agent_display_name} completed successfully\n")
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
    
    def _restore_phase_from_scratchpad(self) -> None:
        """Restore investigation phase from scratchpad state.
        
        Determines the current phase based on which sections have been completed
        in the scratchpad.
        """
        # Check which sections exist in the scratchpad
        has_problem = self.scratchpad.has_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        has_data = self.scratchpad.has_section(ScratchpadSection.DATA_COLLECTED)
        has_patterns = self.scratchpad.has_section(ScratchpadSection.PATTERN_ANALYSIS)
        has_code = self.scratchpad.has_section(ScratchpadSection.CODE_INSPECTION)
        has_diagnosis = self.scratchpad.has_section(ScratchpadSection.FINAL_DIAGNOSIS)
        
        # Determine phase based on completed sections
        if has_diagnosis:
            self.current_phase = InvestigationPhase.COMPLETED
        elif has_code:
            self.current_phase = InvestigationPhase.ROOT_CAUSE_ANALYSIS
        elif has_patterns:
            self.current_phase = InvestigationPhase.CODE_INSPECTION
        elif has_data:
            self.current_phase = InvestigationPhase.PATTERN_ANALYSIS
        elif has_problem:
            self.current_phase = InvestigationPhase.DATA_COLLECTION
        else:
            # Shouldn't reach here, but default to initialization
            self.current_phase = InvestigationPhase.INITIALIZATION
    
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

