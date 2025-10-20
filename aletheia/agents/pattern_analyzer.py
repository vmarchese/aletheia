"""Pattern Analyzer Agent for identifying anomalies and correlations.

This agent is responsible for:
- Examining collected data from the scratchpad
- Explaining what is happening in the system
- Identifying patterns, anomalies, and trends
- Providing natural language analysis
- Writing results to the scratchpad's PATTERN_ANALYSIS section

This agent uses the LLM to perform all analysis without hardcoded logic.
"""

from typing import Any, Dict
import json

from aletheia.agents.sk_base import SKBaseAgent
from aletheia.scratchpad import ScratchpadSection


class PatternAnalyzerAgent(SKBaseAgent):
    """Agent responsible for analyzing patterns in collected data.
    
    This agent uses the LLM to examine data collected in the scratchpad
    and explain what is happening without any hardcoded analysis logic.
    
    The Pattern Analyzer Agent:
    1. Reads the DATA_COLLECTED section from the scratchpad
    2. Reads the PROBLEM_DESCRIPTION for context
    3. Uses the LLM to analyze patterns, anomalies, and trends
    4. Writes results to the PATTERN_ANALYSIS section
    
    Attributes:
        config: Agent configuration including analysis settings
        scratchpad: Scratchpad for reading data and writing analysis
    """
    
    def __init__(self, config: Dict[str, Any], scratchpad: Any):
        """Initialize the Pattern Analyzer Agent.
        
        Args:
            config: Configuration dictionary with llm section
            scratchpad: Scratchpad instance for agent communication
        """
        super().__init__(config, scratchpad, agent_name="pattern_analyzer")
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the pattern analysis process.
        
        Uses the LLM to analyze collected data and identify patterns.
        
        Args:
            **kwargs: Additional parameters for analysis
        
        Returns:
            Dictionary with execution results:
                - success: bool - Whether execution succeeded
                - analysis_complete: bool - Whether analysis was completed
        
        Raises:
            ValueError: If DATA_COLLECTED section is missing or empty
        """
        # Read collected data from scratchpad
        collected_data = self.read_scratchpad(ScratchpadSection.DATA_COLLECTED)
        if not collected_data:
            raise ValueError("No data collected. Run Data Fetcher Agent first.")
        
        # Read problem description for context
        problem = self.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION) or {}
        
        # Check for conversational mode
        conversation_history = self.read_scratchpad(ScratchpadSection.CONVERSATION_HISTORY)
        conversational_mode = conversation_history is not None and len(conversation_history) > 0
        
        # Build prompt for LLM analysis
        prompt = self._build_analysis_prompt(collected_data, problem, conversational_mode)
        
        # Invoke LLM to perform analysis (synchronous)
        response = self.invoke(prompt)
        
        # Parse and structure the response
        analysis = self._parse_analysis_response(response)
        
        # Write analysis to scratchpad
        self.write_scratchpad(ScratchpadSection.PATTERN_ANALYSIS, analysis)
        
        # Return execution results with summary
        return {
            "success": True,
            "analysis_complete": True,
            "conversational_mode": conversational_mode,
            "summary": analysis.get("summary", "Analysis complete"),
            "key_findings": analysis.get("key_findings", []),
            "anomaly_count": len(analysis.get("anomalies", [])),
            "confidence": analysis.get("confidence", 0.5)
        }
    
    def _build_analysis_prompt(
        self,
        collected_data: Dict[str, Any],
        problem: Dict[str, Any],
        conversational_mode: bool = False
    ) -> str:
        """Build prompt for LLM pattern analysis.
        
        Args:
            collected_data: Collected data from DATA_COLLECTED section
            problem: Problem description from PROBLEM_DESCRIPTION section
            conversational_mode: Whether to use conversational prompt format
        
        Returns:
            Formatted prompt string for LLM
        """
        if conversational_mode:
            # Read conversation history for context
            conversation_history = self.read_scratchpad(ScratchpadSection.CONVERSATION_HISTORY) or []
            
            # Format conversation
            conv_str = self._format_conversation(conversation_history)
            
            prompt = f"""You are a Pattern Analyzer agent helping troubleshoot a system issue.

**Conversation History**:
{conv_str}

**Problem Description**:
{json.dumps(problem, indent=2)}

**Collected Data**:
{json.dumps(collected_data, indent=2)}

**Your Task**:
Analyze the collected data and explain what is happening in the system. Consider:

1. **Patterns & Trends**: What patterns do you see in the logs and metrics?
2. **Anomalies**: Are there any unusual events, spikes, or errors?
3. **Correlations**: Do events in different data sources relate to each other?
4. **Timeline**: What is the sequence of events?
5. **Key Findings**: What are the most important observations?

Provide your analysis in natural language, explaining what you found and why it matters.
Also provide a structured summary for other agents.

Return your response as JSON:
{{
    "summary": "Natural language summary of findings",
    "key_findings": ["finding 1", "finding 2", ...],
    "anomalies": ["anomaly 1", "anomaly 2", ...],
    "timeline": ["event 1", "event 2", ...],
    "correlations": ["correlation 1", "correlation 2", ...],
    "confidence": 0.0-1.0,
    "reasoning": "Explain your analysis process"
}}"""
        else:
            # Guided mode prompt
            prompt = f"""You are a Pattern Analyzer agent for system troubleshooting.

**Problem Context**:
{json.dumps(problem, indent=2)}

**Collected Data**:
{json.dumps(collected_data, indent=2)}

**Your Task**:
Analyze the collected data and identify patterns, anomalies, and correlations.

Consider:
1. **Anomalies**: Metric spikes/drops, error rate increases, unusual patterns
2. **Error Patterns**: Group similar errors and identify root error messages
3. **Timeline**: Chronological sequence of events
4. **Correlations**: Events that happen together or in sequence

Provide your analysis as JSON:
{{
    "summary": "Natural language summary of what's happening",
    "anomalies": [
        {{
            "type": "description of anomaly type",
            "description": "detailed description",
            "severity": "low|medium|high|critical",
            "timestamp": "when it occurred (if available)"
        }}
    ],
    "error_patterns": [
        {{
            "pattern": "normalized error pattern",
            "description": "what this error means",
            "frequency": "how often it occurs",
            "examples": ["example error messages"]
        }}
    ],
    "timeline": [
        {{
            "time": "timestamp or relative time",
            "event": "what happened",
            "significance": "why it matters"
        }}
    ],
    "correlations": [
        {{
            "description": "what events are related",
            "confidence": "high|medium|low",
            "reasoning": "why you think they're related"
        }}
    ],
    "key_findings": ["most important observation 1", "most important observation 2", ...],
    "confidence": 0.0-1.0,
    "reasoning": "explain your analysis approach"
}}

Provide ONLY the JSON object."""
        
        return prompt
    
    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM analysis response.
        
        Args:
            response: LLM response string
        
        Returns:
            Parsed analysis dictionary
        """
        # Try to extract JSON from response
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            try:
                analysis = json.loads(json_str)
                
                # Ensure required fields exist
                analysis.setdefault("summary", "Analysis completed")
                analysis.setdefault("key_findings", [])
                analysis.setdefault("anomalies", [])
                analysis.setdefault("timeline", [])
                analysis.setdefault("correlations", [])
                analysis.setdefault("confidence", 0.5)
                analysis.setdefault("reasoning", "")
                
                return analysis
            except json.JSONDecodeError:
                # If JSON parsing fails, return response as summary
                return {
                    "summary": response,
                    "key_findings": [],
                    "anomalies": [],
                    "timeline": [],
                    "correlations": [],
                    "confidence": 0.5,
                    "reasoning": "Analysis provided in natural language"
                }
        
        # If no JSON found, return response as summary
        return {
            "summary": response,
            "key_findings": [],
            "anomalies": [],
            "timeline": [],
            "correlations": [],
            "confidence": 0.5,
            "reasoning": "Analysis provided in natural language"
        }
    
    def _format_conversation(self, conversation_history: list) -> str:
        """Format conversation history for prompt.
        
        Args:
            conversation_history: List of conversation messages
        
        Returns:
            Formatted conversation string
        """
        if not conversation_history:
            return "(No conversation history)"
        
        formatted = []
        for msg in conversation_history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")
            formatted.append(f"[{timestamp}] {role}: {content}")
        
        return "\n".join(formatted)

