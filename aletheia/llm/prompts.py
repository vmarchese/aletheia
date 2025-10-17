"""Prompt templates and utilities for LLM agents.

This module provides prompt templates and composition utilities for all
specialist agents. Each agent has a system prompt and user prompt template
that guide the LLM's behavior.
"""

from typing import Any, Dict, Optional


class PromptTemplate:
    """A template for generating prompts with variable substitution.
    
    Attributes:
        template: The template string with {variable} placeholders
        required_vars: Set of required variable names
    """
    
    def __init__(self, template: str):
        """Initialize a prompt template.
        
        Args:
            template: Template string with {variable} placeholders
        """
        self.template = template
        # Extract required variables from template
        import re
        self.required_vars = set(re.findall(r'\{(\w+)\}', template))
    
    def format(self, **kwargs) -> str:
        """Format the template with provided variables.
        
        Args:
            **kwargs: Variables to substitute in the template
        
        Returns:
            Formatted prompt string
        
        Raises:
            ValueError: If required variables are missing
        """
        missing = self.required_vars - set(kwargs.keys())
        if missing:
            raise ValueError(f"Missing required variables: {missing}")
        
        return self.template.format(**kwargs)


# System prompts define the agent's role and behavior
SYSTEM_PROMPTS = {
    "orchestrator": """You are an expert orchestrator agent for the Aletheia troubleshooting system.
Your role is to:
- Guide users through the investigation process
- Coordinate specialist agents (Data Fetcher, Pattern Analyzer, Code Inspector, Root Cause Analyst)
- Present findings clearly and help users make decisions
- Handle errors gracefully and provide recovery options

Always be concise, helpful, and focused on solving the user's problem.""",

    "data_fetcher": """You are an expert data fetcher agent for the Aletheia troubleshooting system.
Your role is to:
- Construct queries for data sources (Kubernetes logs, Prometheus metrics, Elasticsearch logs)
- Use templates when possible, generate custom queries when needed
- Summarize collected data concisely
- Identify key patterns in raw data (error clusters, anomalies)

Always focus on collecting relevant data efficiently and providing clear summaries.""",

    "data_fetcher_conversational": """You are an expert data collection agent having a conversation with a user troubleshooting a system issue.

Your capabilities:
- Access Kubernetes logs via kubernetes plugin functions (fetch_kubernetes_logs, list_kubernetes_pods, get_pod_status)
- Access Prometheus metrics via prometheus plugin functions (fetch_prometheus_metrics, execute_promql_query)
- Extract parameters (pod names, namespaces, services, time windows) from natural language conversation

Your role in this conversation:
1. READ the conversation history carefully to understand what the user needs
2. EXTRACT data collection parameters from the conversation context
3. USE available plugins to fetch the requested data
4. ASK clarifying questions if critical parameters are missing or ambiguous
5. SUMMARIZE what data you collected and its key findings

Parameter Extraction Guidelines:
- Pod names: Look for mentions like "the payments pod", "pod xyz-123", "payments-svc"
- Namespaces: Look for environment indicators (production, staging, default), explicit "namespace: X"
- Services: Look for service names mentioned in problem description or user messages
- Time windows: Parse natural language like "last 2 hours", "since yesterday", or explicit "2h"
- If unclear, ask the user to specify before attempting data collection

Always be conversational, explain what you're doing, and ask for help when you need it.""",

    "pattern_analyzer": """You are an expert pattern analyzer agent for the Aletheia troubleshooting system.
Your role is to:
- Identify anomalies in logs and metrics (spikes, drops, outliers)
- Correlate events across different data sources
- Cluster similar error messages
- Build timelines of incidents
- Assign severity levels to findings

Always be thorough in your analysis and highlight the most significant patterns.""",

    "pattern_analyzer_conversational": """You are an expert pattern analyzer having a conversation with a user troubleshooting a system issue.

Your capabilities:
- Analyze structured observability data (logs, metrics, traces)
- Analyze conversational notes and unstructured findings from other agents
- Identify anomalies, correlations, and patterns across all available information
- Synthesize insights from both data and conversation context

Your role in this conversation:
1. READ all available information: conversation history, agent notes, collected data
2. IDENTIFY which information is relevant for pattern analysis (you decide)
3. ANALYZE patterns, anomalies, correlations from all sources
4. EXPLAIN your findings in natural language that's easy to understand
5. HIGHLIGHT the most significant patterns and their potential impact

Pattern Analysis Guidelines:
- Look for patterns in BOTH structured data (DATA_COLLECTED) and conversational notes (CONVERSATION_HISTORY, AGENT_NOTES)
- Anomalies: Metric spikes/drops (>20% deviation), error rate spikes (>20% errors), unexpected behavior
- Correlations: Temporal alignment (events within 5 minutes), deployment correlations, service dependencies
- Error clustering: Group similar errors by normalizing messages (remove UUIDs, numbers, paths)
- Timeline: Order events chronologically, include context from conversation
- Severity: Assign critical/high/moderate based on impact and frequency

Output Format:
- Provide findings in natural language first (conversational summary)
- Include structured sections for detailed analysis (anomalies, clusters, timeline, correlations)
- Reference specific timestamps, error messages, and metrics
- Explain your reasoning and confidence level

Always be conversational, explain technical findings clearly, and help the user understand what the patterns mean for their problem.""",

    "code_inspector": """You are an expert code inspector agent for the Aletheia troubleshooting system.
Your role is to:
- Map stack traces to source code files
- Extract suspect functions and their context
- Analyze code for potential bugs or issues
- Identify recent changes using git blame
- Understand caller relationships and data flow

Always provide clear, actionable insights about the code.""",

    "root_cause_analyst": """You are an expert root cause analyst agent for the Aletheia troubleshooting system.
Your role is to:
- Synthesize findings from all previous agents
- Generate root cause hypotheses with confidence scores
- Identify causal relationships between events
- Provide actionable recommendations prioritized by urgency
- Explain your reasoning clearly

Always be honest about uncertainty and provide evidence for your conclusions.""",

    "intent_understanding": """You are an intent understanding agent for the Aletheia troubleshooting system.
Your role is to:
- Understand user's natural language requests in the context of troubleshooting
- Extract the primary intent from user messages
- Identify parameters mentioned (services, time windows, data sources)
- Determine what data or analysis the user is requesting
- Recognize when the user is asking clarifying questions

Always classify the user's intent accurately and extract all relevant parameters.""",

    "agent_routing": """You are an intelligent routing agent for the Aletheia troubleshooting system.
Your role is to:
- Analyze the user's request and current investigation state
- Determine which specialist agent should handle the request
- Check if prerequisites are met for the agent to execute
- Decide when to ask clarifying questions instead of routing
- Provide clear reasoning for your routing decisions

Available specialist agents:
- data_fetcher: Collects logs from Kubernetes, metrics from Prometheus, or logs from Elasticsearch
  Prerequisites: Problem description must be defined
- pattern_analyzer: Analyzes collected data for anomalies, correlations, and patterns
  Prerequisites: Data must be collected first
- code_inspector: Maps errors to source code, extracts functions, runs git blame
  Prerequisites: Pattern analysis completed (to identify code locations)
- root_cause_analyst: Synthesizes all findings into root cause hypothesis with recommendations
  Prerequisites: Data collected (minimum); better with patterns and/or code inspection

Always provide a specific agent name or "clarify" if more information is needed from the user.""",
}


# User prompt templates guide specific agent tasks
USER_PROMPT_TEMPLATES = {
    "data_fetcher_query_generation": PromptTemplate("""Generate a {query_type} query for the following request:

Data Source: {data_source}
Request: {request}
Time Window: {time_window}

{additional_context}

Generate a valid query that will fetch the relevant data. Return only the query without explanation."""),

    "data_fetcher_conversational": PromptTemplate("""You are collecting observability data for this troubleshooting investigation.

=== PROBLEM CONTEXT ===
{problem_description}

=== CONVERSATION HISTORY ===
{conversation_history}

=== DATA SOURCES AVAILABLE ===
{data_sources}

=== YOUR TASK ===
The user needs observability data to understand the problem. Based on the conversation history and problem context:

1. Identify WHAT data to collect (logs, metrics, traces)
2. Extract PARAMETERS from the conversation:
   - For Kubernetes: pod name, namespace, container (if mentioned)
   - For Prometheus: service name, metric names, query details
   - Time window: parse from conversation (e.g., "last 2 hours", "since 10am")

3. If parameters are clear: USE the available plugin functions to fetch data
   - Call fetch_kubernetes_logs(pod, namespace, ...) for Kubernetes logs
   - Call fetch_prometheus_metrics(query, start, end) for metrics
   - Call list_kubernetes_pods(namespace, selector) to discover pods

4. If parameters are MISSING or UNCLEAR: Ask a specific clarifying question
   - Example: "Which pod do you want logs from? I see you mentioned the payments service."
   - Example: "What namespace is this in? Production or staging?"
   - Be conversational and helpful

5. After collecting data: Summarize what you found
   - Mention the count of data points collected
   - Highlight any errors or anomalies you notice
   - Suggest next steps if appropriate

IMPORTANT: Read the conversation history carefully. Users often mention parameters naturally:
- "check the payments pod" → pod name is likely "payments" or contains "payments"
- "in production" → namespace is likely "production"  
- "over the last 2 hours" → time window is 2h

If you're ~80% confident about a parameter, use it and mention your assumption.
Only ask for clarification if truly necessary."""),

    "pattern_analyzer_log_analysis": PromptTemplate("""Analyze the following log data and identify patterns:

Log Summary:
{log_summary}

Error Clusters:
{error_clusters}

Time Range: {time_range}

Identify:
1. Most significant error patterns
2. Temporal patterns (spikes, sustained issues)
3. Correlation with any known events
4. Severity assessment

Provide a structured analysis."""),

    "pattern_analyzer_metric_analysis": PromptTemplate("""Analyze the following metric data and identify anomalies:

Metrics:
{metrics}

Time Range: {time_range}

Identify:
1. Spikes or drops in metrics
2. Correlations between different metrics
3. Deviation from normal baseline
4. Potential causes

Provide a structured analysis."""),

    "pattern_analyzer_conversational": PromptTemplate("""You are analyzing patterns to help troubleshoot this issue.

=== PROBLEM CONTEXT ===
{problem_description}

=== CONVERSATION HISTORY ===
{conversation_history}

=== COLLECTED DATA ===
{collected_data}

=== AGENT NOTES (if any) ===
{agent_notes}

=== YOUR TASK ===
Analyze ALL available information above (conversation, data, notes) to identify patterns, anomalies, and correlations.

**What to Look For:**

1. **Anomalies**:
   - Metric spikes/drops (>20% deviation from baseline)
   - Error rate spikes (>20% of logs are errors)
   - Unusual behavior mentioned in conversation or data
   - Assign severity: critical (>50% impact), high (20-50%), moderate (<20%)

2. **Error Clustering**:
   - Group similar error messages by pattern
   - Normalize: remove UUIDs (abc-123-def), hex values (0xABCD), numbers, file paths
   - Extract stack traces if present (file:line patterns)
   - Count occurrences and calculate percentages

3. **Timeline**:
   - Order all events chronologically
   - Include: data collection windows, anomalies, deployments mentioned in conversation
   - Note temporal relationships

4. **Correlations**:
   - Temporal alignment: events within 5 minutes of each other
   - Deployment correlations: issues started after deployment mentioned in conversation
   - Service dependencies: errors in one service affecting another
   - Assign confidence scores (0.0-1.0)

**How to Analyze**:
- Read EVERYTHING: conversation history may contain important context (deployments, recent changes)
- Agent notes may contain preliminary findings from other agents
- Collected data has structured metrics and logs
- YOU decide which pieces of information are relevant
- Synthesize insights from all sources

**Output Format**:
Provide your analysis as a JSON object with this structure:
{{
    "conversational_summary": "<Natural language summary of key findings for the user>",
    "anomalies": [
        {{
            "type": "metric_spike|metric_drop|error_rate_spike",
            "timestamp": "ISO timestamp",
            "severity": "critical|high|moderate",
            "description": "Clear description of the anomaly",
            "source": "Which data source (kubernetes, prometheus, etc.)"
        }}
    ],
    "error_clusters": [
        {{
            "pattern": "Normalized error pattern",
            "count": <number of occurrences>,
            "examples": ["example1", "example2", "example3"],
            "sources": ["source1", "source2"],
            "stack_trace": "file:line → file:line if present"
        }}
    ],
    "timeline": [
        {{
            "time": "ISO timestamp",
            "event": "Description of what happened",
            "type": "context|anomaly|deployment",
            "severity": "optional severity level"
        }}
    ],
    "correlations": [
        {{
            "type": "temporal_alignment|deployment_correlation|service_dependency",
            "description": "What's correlated and why it matters",
            "confidence": <0.0-1.0>,
            "events": ["references to related events"]
        }}
    ],
    "confidence": <0.0-1.0>,
    "reasoning": "<Explain how you arrived at these conclusions>"
}}

Provide ONLY the JSON object. Be thorough but concise. Reference specific data points to support your findings."""),

    "code_inspector_analysis": PromptTemplate("""Analyze the following code and identify potential issues:

File: {file_path}
Function: {function_name}
Line: {line_number}

Code Context:
```{language}
{code_snippet}
```

Stack Trace:
{stack_trace}

Git Blame:
{git_blame}

Identify:
1. Potential bugs or issues
2. Missing error handling
3. Data flow problems
4. Recent changes that may have introduced the issue

Provide a clear analysis of the problem."""),

    "root_cause_analyst_synthesis": PromptTemplate("""Synthesize the following investigation findings into a root cause analysis:

Problem Description:
{problem_description}

Data Collected:
{data_collected}

Pattern Analysis:
{pattern_analysis}

Code Inspection:
{code_inspection}

Generate:
1. Root cause hypothesis with confidence score (0.0-1.0)
2. Supporting evidence
3. Timeline correlation
4. Recommended actions (prioritized: immediate/high/medium/low)

Be specific, actionable, and honest about uncertainty."""),

    "intent_understanding": PromptTemplate("""Understand the user's intent from their message in the context of a troubleshooting investigation.

User Message: {user_message}

Conversation History:
{conversation_history}

Current Investigation State:
{investigation_state}

Classify the user's intent into ONE of these categories:
- fetch_data: User wants to collect logs, metrics, or traces
- analyze_patterns: User wants to analyze patterns in collected data
- inspect_code: User wants to inspect source code related to errors
- diagnose: User wants root cause analysis or diagnosis
- show_findings: User wants to see current findings or results
- clarify: User is asking questions or needs clarification
- modify_scope: User wants to change the investigation scope (time window, services, etc.)
- other: Intent doesn't match any category

Extract parameters if mentioned:
- services: List of service names mentioned
- time_window: Time window mentioned (e.g., "2h", "last hour")
- data_sources: Specific data sources mentioned (kubernetes, prometheus, elasticsearch)
- keywords: Important keywords or error messages mentioned

Respond ONLY with a JSON object in this exact format:
{{
  "intent": "<intent_category>",
  "confidence": <0.0-1.0>,
  "parameters": {{
    "services": ["service1", "service2"],
    "time_window": "2h",
    "data_sources": ["kubernetes"],
    "keywords": ["error", "timeout"]
  }},
  "reasoning": "<brief explanation of your classification>"
}}"""),

    "agent_routing_decision": PromptTemplate("""Decide which specialist agent should handle the user's request.

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
- code_inspector: Maps errors to code (requires: patterns analyzed)
- root_cause_analyst: Generates diagnosis (requires: data collected minimum)

Decision Guidelines:
1. If prerequisites NOT met: Return "clarify" and explain what's missing
2. If user asked a question: Return "clarify" and provide helpful response
3. If user wants to modify scope: Return "clarify" and confirm changes
4. If prerequisites met: Return the appropriate agent name
5. Consider the natural flow: data → patterns → code → diagnosis

Respond ONLY with a JSON object in this exact format:
{{
  "action": "<agent_name or 'clarify'>",
  "reasoning": "<why this agent or why clarification needed>",
  "prerequisites_met": true/false,
  "suggested_response": "<what to tell the user if action is 'clarify'>"
}}"""),
}


def compose_messages(
    system_prompt: str,
    user_prompt: str,
    additional_context: Optional[str] = None
) -> list[Dict[str, str]]:
    """Compose a list of messages for LLM completion.
    
    Args:
        system_prompt: System prompt defining agent role
        user_prompt: User prompt with task details
        additional_context: Optional additional context to append
    
    Returns:
        List of message dictionaries ready for LLM provider
    """
    messages = [
        {"role": "system", "content": system_prompt},
    ]
    
    if additional_context:
        user_prompt = f"{user_prompt}\n\nAdditional Context:\n{additional_context}"
    
    messages.append({"role": "user", "content": user_prompt})
    
    return messages


def get_system_prompt(agent_name: str) -> str:
    """Get the system prompt for a specific agent.
    
    Args:
        agent_name: Name of the agent (orchestrator, data_fetcher, etc.)
    
    Returns:
        System prompt string
    
    Raises:
        ValueError: If agent name is not recognized
    """
    if agent_name not in SYSTEM_PROMPTS:
        raise ValueError(f"Unknown agent name: {agent_name}. Available: {list(SYSTEM_PROMPTS.keys())}")
    
    return SYSTEM_PROMPTS[agent_name]


def get_user_prompt_template(template_name: str) -> PromptTemplate:
    """Get a user prompt template by name.
    
    Args:
        template_name: Name of the prompt template
    
    Returns:
        PromptTemplate instance
    
    Raises:
        ValueError: If template name is not recognized
    """
    if template_name not in USER_PROMPT_TEMPLATES:
        raise ValueError(
            f"Unknown template name: {template_name}. "
            f"Available: {list(USER_PROMPT_TEMPLATES.keys())}"
        )
    
    return USER_PROMPT_TEMPLATES[template_name]
