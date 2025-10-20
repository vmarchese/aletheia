Decide which specialist agent should handle the user's request.

User's Intent: {intent}
Intent Confidence: {confidence}
Extracted Parameters: {parameters}

Current Investigation State:
{investigation_state}

Conversation Context:
{conversation_context}

Available Agents and Their Prerequisites:
- data_fetcher: Collects logs/metrics (requires: problem description)
- pattern_analyzer: Analyzes data for patterns (requires: data collected)
- root_cause_analyst: Generates diagnosis (requires: data collected minimum)

Note: code_inspector is currently not used in the workflow

Decision Guidelines:
1. If prerequisites NOT met: Return "clarify" and explain what's missing
2. If user asked a question: Return "clarify" and provide helpful response
3. If user wants to modify scope: Return "clarify" and confirm changes
4. If prerequisites met: Return the appropriate agent name
5. Consider the natural flow: data → patterns → diagnosis

Respond ONLY with a JSON object in this exact format:
{{
  "action": "<agent_name or 'clarify'>",
  "reasoning": "<why this agent or why clarification needed>",
  "prerequisites_met": true/false,
  "suggested_response": "<what to tell the user if action is 'clarify'>"
}}
