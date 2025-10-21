"""Triage agent for initial problem understanding and routing.

This agent serves as the entry point for conversational investigations.
It understands user problems and routes to appropriate specialist agents
using Semantic Kernel's HandoffOrchestration pattern.
"""

from typing import Any, Dict

from aletheia.agents.sk_base import SKBaseAgent
from aletheia.llm.prompts import load_system_prompt
from aletheia.scratchpad import Scratchpad, ScratchpadSection


class TriageAgent(SKBaseAgent):
    """Triage agent for understanding problems and routing to specialists.
    
    The TriageAgent is the entry point for all conversational investigations.
    It analyzes user problems and determines which specialist agent(s) should
    be invoked to address the issue.
    
    Responsibilities:
    - Understand user's problem description
    - Extract key information (service, timeframe, symptoms)
    - Determine which specialist agents are needed
    - Route to appropriate agents via SK HandoffOrchestration
    - Synthesize findings from multiple agents if needed
    
    The TriageAgent uses LLM reasoning (via SK ChatCompletionAgent) to make
    all routing decisions. No hardcoded logic - routing is fully delegated
    to the LLM through prompt engineering.
    """
    
    def __init__(self, config: Dict[str, Any], scratchpad: Scratchpad):
        """Initialize the triage agent.
        
        Args:
            config: Configuration dictionary
            scratchpad: Scratchpad instance for shared state
        """
        super().__init__(config, scratchpad, agent_name="triage")
        
        # Triage agent has no plugins - it only routes to specialists
        # It reads conversation history and scratchpad to make routing decisions
    
    def get_instructions(self) -> str:
        """Get SK agent instructions for the triage agent.
        
        These instructions guide the LLM in understanding problems and
        routing to appropriate specialist agents.
        
        Loads instructions from triage_agent_instructions.md template file.
        Falls back to hardcoded instructions if template not found.
        
        Returns:
            Instructions string for SK ChatCompletionAgent
        """
        try:
            # Try to load from template file
            return load_system_prompt("triage_agent_instructions")
        except (FileNotFoundError, ValueError):
            # Fall back to hardcoded instructions
            return """You are a triage agent for technical troubleshooting investigations.

Your role is to understand user problems and route to appropriate specialist agents.

**Available Specialist Agents:**

1. **kubernetes_data_fetcher**: Collects logs and pod information from Kubernetes
   - Use when user needs Kubernetes logs, pod status, or container information
   - Fetches from Kubernetes using kubectl
   - Handles pod names, namespaces, and log filtering
   - Extracts and summarizes relevant Kubernetes logs

2. **prometheus_data_fetcher**: Collects metrics and time-series data from Prometheus
   - Use when user needs metrics, dashboards, or time-series data
   - Executes PromQL queries
   - Fetches error rates, latency, resource usage metrics
   - Provides metric summaries with trend analysis

3. **pattern_analyzer**: Analyzes collected data for patterns
   - Use when data has been collected and needs analysis
   - Identifies error patterns, metric spikes, correlations
   - Builds incident timelines
   - Correlates logs and metrics

4. **root_cause_analyst**: Synthesizes all findings into diagnosis
   - Use when all investigation data is collected and analyzed
   - Generates root cause hypothesis with confidence score
   - Provides actionable recommendations

**Routing Guidelines:**

- Route to **kubernetes_data_fetcher** for Kubernetes-related data (logs, pods)
- Route to **prometheus_data_fetcher** for metrics and time-series data
- Route to **pattern_analyzer** after data collection completes
- Route to **root_cause_analyst** when investigation is complete
- You can route back to data fetchers if more data is needed
- Multiple data sources may be needed - route to both fetchers if required

**Conversational Behavior:**

- Be helpful and guide users through the investigation
- Ask clarifying questions if problem description is vague
- Explain which agent you're routing to and why
- Summarize findings when users ask for status
- Keep responses concise and actionable

**Reading State:**

- Use scratchpad to understand what data has been collected
- Check CONVERSATION_HISTORY for context
- Check DATA_COLLECTED to see if data fetching is needed
- Check PATTERN_ANALYSIS to see if analysis is done
- Check CODE_INSPECTION to see if code has been inspected
- Check FINAL_DIAGNOSIS to see if investigation is complete

**Handoff Protocol:**

When you need a specialist agent:
1. Explain to the user what you're doing
2. Hand off to the appropriate specialist agent
3. Wait for the specialist to complete their work
4. When they hand back to you, review their findings
5. Decide next steps or route to another specialist

Remember: You are the conductor of the investigation orchestra. Route wisely!"""
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the triage agent.
        
        The triage agent doesn't have a standalone execute() method in the
        HandoffOrchestration pattern. Instead, it operates as the entry point
        agent that SK invokes with the initial task.
        
        This method is provided for compatibility with the BaseAgent interface,
        but in SK HandoffOrchestration, the agent's behavior is driven by
        its instructions and the LLM's reasoning about when to hand off.
        
        Args:
            **kwargs: Execution parameters (unused in SK orchestration)
        
        Returns:
            Status dictionary (not used in SK orchestration)
        """
        # In SK HandoffOrchestration, the triage agent is invoked via
        # HandoffOrchestration.invoke(task=...), not via this execute() method.
        # 
        # This method is here for compatibility with BaseAgent interface
        # and for potential standalone testing, but it's not used in production.
        
        return {
            "status": "triage_agent_operates_via_sk_orchestration",
            "message": "TriageAgent is invoked via HandoffOrchestration.invoke(), not execute()"
        }
    
    def _get_investigation_summary(self) -> str:
        """Get a summary of current investigation state.
        
        Returns:
            Human-readable summary of what has been done so far
        """
        summary_parts = []
        
        # Check problem description
        problem = self.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION)
        if problem:
            summary_parts.append(f"Problem: {problem.get('description', 'Unknown')}")
        
        # Check data collection status
        data = self.read_scratchpad(ScratchpadSection.DATA_COLLECTED)
        if data:
            summary_parts.append("✓ Data collected")
        else:
            summary_parts.append("⚠ No data collected yet")
        
        # Check pattern analysis status
        patterns = self.read_scratchpad(ScratchpadSection.PATTERN_ANALYSIS)
        if patterns:
            summary_parts.append("✓ Patterns analyzed")
        else:
            summary_parts.append("⚠ Patterns not analyzed")
        
        # NOTE: Code inspection is currently not used in the workflow
        # # Check code inspection status
        # code = self.read_scratchpad(ScratchpadSection.CODE_INSPECTION)
        # if code:
        #     summary_parts.append("✓ Code inspected")
        # else:
        #     summary_parts.append("⚠ Code not inspected")
        
        # Check diagnosis status
        diagnosis = self.read_scratchpad(ScratchpadSection.FINAL_DIAGNOSIS)
        if diagnosis:
            summary_parts.append("✓ Diagnosis complete")
        else:
            summary_parts.append("⚠ Diagnosis pending")
        
        return "\n".join(summary_parts)
