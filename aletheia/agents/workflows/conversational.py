"""Conversational Mode Reference Implementation.

This module serves as a reference implementation demonstrating the LLM-First pattern
for conversational agent interactions in Aletheia. It shows how agents delegate ALL
logic (parameter extraction, intent understanding, routing decisions) to the LLM via
enhanced prompts, rather than implementing custom parsing or extraction code.

**Key Design Principles**:

1. **LLM-First Design**: All parameter extraction, parsing, and decision logic 
   delegated to LLM via Semantic Kernel prompts
   
2. **Plugin-Only External Calls**: Agents use SK plugins exclusively for kubectl, 
   git, Prometheus HTTP APIs - no direct subprocess calls
   
3. **Thin Agent Pattern**: Agents orchestrate by building prompts and invoking SK 
   with conversation context - minimal custom logic
   
4. **Prompt Engineering**: Focus on enhancing SK prompts to guide LLM behavior, 
   not custom Python logic
   
5. **No Custom Extraction**: Agents read scratchpad conversation context and pass 
   to LLM; LLM extracts parameters

**What This Module Demonstrates**:

- How LLM extracts parameters from conversational context (no custom parsing)
- How LLM determines next actions based on investigation state
- How agents use plugins via FunctionChoiceBehavior.Auto() for external operations
- How conversation history flows through scratchpad to LLM prompts
- How to structure prompts for effective conversational parameter extraction

**What This Module DOES NOT Do**:

- ❌ Custom parameter extraction logic (e.g., regex, string parsing)
- ❌ Hardcoded intent-to-agent mappings
- ❌ Custom routing decision logic
- ❌ Direct subprocess calls or API requests
- ❌ Manual conversation parsing or context extraction

**Conversational Flow Example**:

```
User: "Why is payments-svc failing?"
  ↓
Orchestrator reads conversation → passes to LLM
  ↓
LLM extracts: service="payments-svc", intent="investigate_failure"
LLM decides: route to Data Fetcher Agent
  ↓
Data Fetcher reads conversation → passes to LLM + registers plugins
  ↓
LLM extracts: pod="payments-svc", namespace="default"
LLM invokes: kubernetes.fetch_kubernetes_logs(pod="payments-svc", namespace="default")
  ↓
Data Fetcher writes results to scratchpad
Data Fetcher appends conversation: "I found 47 errors in payments-svc logs..."
  ↓
Orchestrator reads updated conversation → passes to LLM
LLM decides: route to Pattern Analyzer Agent
  ↓
[Continue investigation with LLM-driven workflow]
```

**Usage**:

This module is a REFERENCE IMPLEMENTATION. Copy patterns from here when implementing
conversational features in actual agents. Do not import this module directly in 
production code.

See Also:
    - AGENTS.md: "Conversational Orchestration" section
    - SPECIFICATION.md: Section 2.2 (Scratchpad Design)
    - TODO.md: REFACTOR-1 through REFACTOR-10
"""

from typing import Dict, Any, Optional, List


# ============================================================================
# EXAMPLE 1: LLM-Driven Intent Understanding (Orchestrator Pattern)
# ============================================================================

EXAMPLE_INTENT_UNDERSTANDING_PROMPT = """
You are an orchestrator agent for the Aletheia troubleshooting system.

**Your Task**: Understand the user's intent from this conversation:

{conversation_history}

**Current Investigation State**:
{investigation_state}

**Available Actions**:
- collect_data: Fetch logs, metrics, or traces from data sources
- analyze_patterns: Identify anomalies and correlations in collected data
- inspect_code: Map errors to source code and analyze git history
- diagnose_root_cause: Synthesize findings into root cause hypothesis
- clarify: Ask user for more information

**Your Response** (JSON format):
{{
    "intent": "collect_data|analyze_patterns|inspect_code|diagnose_root_cause|clarify",
    "confidence": 0.0-1.0,
    "parameters": {{
        // Extract ANY relevant parameters from conversation
        // Examples: service_name, pod_name, namespace, time_window, error_message
    }},
    "reasoning": "Why you chose this intent",
    "clarification_needed": "Optional: what to ask user if unclear"
}}

**Key Points**:
- Extract parameters from natural language (e.g., "payments service" → service_name="payments-svc")
- Consider what's been done already (investigation_state)
- If user's request is ambiguous, set intent="clarify" and provide clarification_needed
- Be specific with extracted parameters
"""


def orchestrator_understand_intent_example(
    conversation_history: str,
    investigation_state: Dict[str, Any]
) -> str:
    """Example: How orchestrator delegates intent understanding to LLM.
    
    This function demonstrates the pattern - it DOES NOT implement custom logic.
    The actual implementation would invoke the SK agent with this prompt.
    
    Args:
        conversation_history: Full conversation from scratchpad.get_conversation_context()
        investigation_state: Current state (which agents have run, what data exists)
        
    Returns:
        Prompt string to send to LLM (via SK agent.invoke())
        
    Example LLM Response:
        {
            "intent": "collect_data",
            "confidence": 0.95,
            "parameters": {
                "service_name": "payments-svc",
                "data_sources": ["kubernetes", "prometheus"],
                "time_window": "2h"
            },
            "reasoning": "User mentioned payments-svc failing, need to collect logs first",
            "clarification_needed": null
        }
    """
    # Build prompt with conversation context
    prompt = EXAMPLE_INTENT_UNDERSTANDING_PROMPT.format(
        conversation_history=conversation_history,
        investigation_state=investigation_state
    )
    
    # In actual implementation:
    # response = await self.invoke(prompt)
    # intent_data = json.loads(response)
    # return intent_data
    
    return prompt  # Return prompt to demonstrate pattern


# ============================================================================
# EXAMPLE 2: LLM-Driven Agent Routing (No Hardcoded Mappings)
# ============================================================================

EXAMPLE_AGENT_ROUTING_PROMPT = """
You are an orchestrator agent deciding which specialist agent to invoke next.

**Conversation History**:
{conversation_history}

**Current Investigation State**:
{investigation_state}

**User Intent**: {intent}
**Extracted Parameters**: {parameters}
**Confidence**: {confidence}

**Available Specialist Agents**:
1. **data_fetcher**: Collects logs, metrics, traces from Kubernetes/Prometheus
   - Prerequisites: Service name or pod name identified
   - Capabilities: Fetch logs, query metrics, sample intelligently

2. **pattern_analyzer**: Identifies anomalies, correlations, error clusters
   - Prerequisites: DATA_COLLECTED section exists in scratchpad
   - Capabilities: Spike detection, timeline creation, error clustering

3. **code_inspector**: Maps stack traces to code, runs git blame
   - Prerequisites: PATTERN_ANALYSIS exists, repository paths known
   - Capabilities: File mapping, code extraction, git history analysis

4. **root_cause_analyst**: Synthesizes all findings into diagnosis
   - Prerequisites: PATTERN_ANALYSIS exists (CODE_INSPECTION optional)
   - Capabilities: Evidence synthesis, confidence scoring, recommendations

**Your Decision** (JSON format):
{{
    "action": "route_to_agent|ask_clarification|complete",
    "agent": "data_fetcher|pattern_analyzer|code_inspector|root_cause_analyst|null",
    "reasoning": "Why this agent is appropriate now",
    "prerequisites_met": true|false,
    "suggested_response": "What to tell the user"
}}

**Rules**:
- Check prerequisites before routing (e.g., don't route to pattern_analyzer if no data collected)
- If prerequisites not met, set action="ask_clarification"
- If investigation is complete, set action="complete"
- Consider the natural flow: data → patterns → code → diagnosis
"""


def orchestrator_decide_next_agent_example(
    conversation_history: str,
    investigation_state: Dict[str, Any],
    intent: str,
    parameters: Dict[str, Any],
    confidence: float
) -> str:
    """Example: How orchestrator delegates routing decisions to LLM.
    
    This demonstrates NO hardcoded intent-to-agent mappings. The LLM decides
    which agent to invoke based on conversation context and investigation state.
    
    Args:
        conversation_history: Full conversation context
        investigation_state: Which agents have run, what sections exist
        intent: Classified intent from previous LLM call
        parameters: Extracted parameters from conversation
        confidence: Intent classification confidence
        
    Returns:
        Prompt string to send to LLM
        
    Example LLM Response:
        {
            "action": "route_to_agent",
            "agent": "data_fetcher",
            "reasoning": "User wants to investigate payments-svc. No data collected yet, so fetch logs first.",
            "prerequisites_met": true,
            "suggested_response": "I'll fetch logs from payments-svc pod in the default namespace..."
        }
    """
    prompt = EXAMPLE_AGENT_ROUTING_PROMPT.format(
        conversation_history=conversation_history,
        investigation_state=investigation_state,
        intent=intent,
        parameters=parameters,
        confidence=confidence
    )
    
    # In actual implementation:
    # response = await self.invoke(prompt)
    # decision = json.loads(response)
    # 
    # if decision["action"] == "route_to_agent":
    #     agent = self.agent_registry[decision["agent"]]
    #     await agent.execute()
    # elif decision["action"] == "ask_clarification":
    #     scratchpad.append_conversation("agent", decision["suggested_response"])
    
    return prompt


# ============================================================================
# EXAMPLE 3: LLM-Driven Parameter Extraction (Data Fetcher Pattern)
# ============================================================================

EXAMPLE_DATA_FETCHER_PROMPT = """
You are a data fetcher agent for the Aletheia troubleshooting system.

**Your Task**: Collect observability data based on this conversation:

{conversation_history}

**Problem Description**: {problem_description}

**Available Plugins**:
- kubernetes.fetch_kubernetes_logs(pod: str, namespace: str, since: str, tail_lines: int)
- kubernetes.list_kubernetes_pods(namespace: str, selector: str)
- prometheus.fetch_prometheus_metrics(query: str, start: str, end: str, step: str)
- prometheus.build_promql_from_template(template: str, params: dict)

**Your Actions**:
1. Extract parameters from the conversation:
   - Which service/pod to investigate? (Look for service names, pod names in conversation)
   - Which namespace? (default: "default")
   - What time window? (Look for phrases like "in the last 2 hours", "since 8am")
   - What type of data? (logs, metrics, traces)

2. Use the appropriate plugin function calls to collect data:
   - For logs: Call kubernetes.fetch_kubernetes_logs()
   - For metrics: Call prometheus.fetch_prometheus_metrics()

3. Summarize what you collected in natural language

**Example**:
If conversation mentions "payments-svc is failing in production namespace since 2 hours ago":
- Extract: pod="payments-svc", namespace="production", time_window="2h"
- Call: kubernetes.fetch_kubernetes_logs(pod="payments-svc", namespace="production", since="2h", tail_lines=200)
- Summarize: "I collected 200 log lines from payments-svc pod. Found 47 errors, mostly 'nil pointer dereference'."

**Important**: 
- DO NOT write custom extraction code - extract parameters from conversation directly
- Use FunctionChoiceBehavior.Auto() - you can call plugin functions automatically
- If parameters are missing, explain what information you need
"""


def data_fetcher_conversational_execution_example(
    conversation_history: str,
    problem_description: Dict[str, Any]
) -> str:
    """Example: How Data Fetcher extracts parameters from conversation via LLM.
    
    This demonstrates how the agent delegates ALL parameter extraction to the LLM.
    The agent does NOT implement custom parsing logic for pod names, namespaces, etc.
    
    Args:
        conversation_history: Full conversation from scratchpad
        problem_description: Initial problem from PROBLEM_DESCRIPTION section
        
    Returns:
        Prompt string to send to SK agent with plugins registered
        
    Example Flow:
        1. Agent builds this prompt with conversation context
        2. Agent invokes SK agent: await self.invoke(prompt)
        3. LLM extracts parameters from conversation
        4. LLM automatically calls kubernetes.fetch_kubernetes_logs() via plugin
        5. LLM returns summary of collected data
        6. Agent writes summary to DATA_COLLECTED section
    """
    prompt = EXAMPLE_DATA_FETCHER_PROMPT.format(
        conversation_history=conversation_history,
        problem_description=problem_description
    )
    
    # In actual implementation (see aletheia/agents/data_fetcher.py):
    # 
    # def _register_plugins(self):
    #     self.kernel.add_plugin(KubernetesPlugin(config), plugin_name="kubernetes")
    #     self.kernel.add_plugin(PrometheusPlugin(config), plugin_name="prometheus")
    # 
    # async def _execute_conversational(self):
    #     conversation = self.read_scratchpad("CONVERSATION_HISTORY")
    #     problem = self.read_scratchpad("PROBLEM_DESCRIPTION")
    #     
    #     prompt = self._build_conversational_prompt(conversation, problem)
    #     
    #     # LLM extracts params and calls plugins automatically
    #     response = await self.invoke(prompt)
    #     
    #     # Write results to scratchpad
    #     self.write_scratchpad("DATA_COLLECTED", response)
    #     self.scratchpad.append_conversation("agent", "Data collection complete...")
    
    return prompt


# ============================================================================
# EXAMPLE 4: LLM-Generated Clarifying Questions
# ============================================================================

EXAMPLE_CLARIFICATION_PROMPT = """
You are an agent in the Aletheia troubleshooting system.

**Conversation So Far**:
{conversation_history}

**What You Need To Know**:
{missing_information}

**Your Task**: Generate a natural, helpful clarifying question to ask the user.

**Guidelines**:
- Be specific about what information you need
- Explain why you need it (helps user understand)
- Provide examples if helpful
- Keep it conversational

**Example**:
Missing: namespace
Output: "I see you're investigating payments-svc. Which Kubernetes namespace is it running in? 
(Common examples: default, production, staging)"

**Your Question**:
"""


def generate_clarification_question_example(
    conversation_history: str,
    missing_information: str
) -> str:
    """Example: How agents generate clarifying questions via LLM.
    
    Instead of hardcoded question templates, agents ask the LLM to generate
    appropriate questions based on conversation context.
    
    Args:
        conversation_history: Current conversation
        missing_information: What parameter/info is needed
        
    Returns:
        Prompt for LLM to generate clarifying question
        
    Example LLM Response:
        "I found that you want to investigate payments-svc, but I need to know which 
        Kubernetes namespace it's in. Is it in the 'default' namespace, or a different 
        one like 'production' or 'staging'?"
    """
    prompt = EXAMPLE_CLARIFICATION_PROMPT.format(
        conversation_history=conversation_history,
        missing_information=missing_information
    )
    
    # In actual implementation:
    # question = await self.invoke(prompt)
    # scratchpad.append_conversation("agent", question)
    # # Return to user for response
    
    return prompt


# ============================================================================
# EXAMPLE 5: LLM-Driven Code Analysis (Code Inspector Pattern)
# ============================================================================

EXAMPLE_CODE_INSPECTOR_PROMPT = """
You are a code inspector agent for the Aletheia troubleshooting system.

**Conversation History**:
{conversation_history}

**Pattern Analysis Results**:
{pattern_analysis}

**Your Task**: Map errors to source code and analyze git history.

**Available Plugins**:
- git.find_file_in_repo(filename: str, repo: str) -> file path
- git.extract_code_context(file_path: str, line_number: int, context_lines: int) -> code snippet
- git.git_blame(file_path: str, line_number: int, repo: str) -> blame info

**Your Actions**:
1. Extract repository information from conversation:
   - Has the user mentioned any git repositories?
   - Are repository paths in the configuration?

2. Parse stack traces from pattern analysis:
   - Identify file names and line numbers
   - Extract function names from stack traces

3. Use plugins to map errors to code:
   - Call git.find_file_in_repo() to locate files
   - Call git.extract_code_context() to get code snippets
   - Call git.git_blame() to find recent changes

4. Analyze findings in natural language

**Example**:
If pattern analysis shows "nil pointer dereference at features.go:57":
- Extract: filename="features.go", line=57
- Call: git.find_file_in_repo(filename="features.go", repo="...")
- Call: git.extract_code_context(file_path=result, line_number=57, context_lines=10)
- Call: git.git_blame(file_path=result, line_number=57, repo="...")
- Analyze: "The error is in IsEnabled() function. Git blame shows it was changed yesterday by john.doe..."

**Important**:
- If repository paths are not in conversation, ask for them
- Extract file paths and line numbers from stack traces using your reasoning
- Use plugins for ALL git operations
"""


def code_inspector_conversational_execution_example(
    conversation_history: str,
    pattern_analysis: Dict[str, Any]
) -> str:
    """Example: How Code Inspector uses LLM to extract repository info.
    
    The agent does NOT implement custom logic to parse stack traces or extract
    file paths. The LLM does this reasoning and calls git plugins.
    
    Args:
        conversation_history: Full conversation (may contain repo paths)
        pattern_analysis: Results from Pattern Analyzer with stack traces
        
    Returns:
        Prompt for SK agent with git plugins registered
        
    Example Flow:
        1. Agent reads conversation history (user may have mentioned repos)
        2. Agent reads pattern analysis (contains stack traces)
        3. Agent builds prompt with both contexts
        4. LLM extracts file paths from stack traces
        5. LLM calls git plugins to find files and get blame info
        6. Agent writes CODE_INSPECTION section
    """
    prompt = EXAMPLE_CODE_INSPECTOR_PROMPT.format(
        conversation_history=conversation_history,
        pattern_analysis=pattern_analysis
    )
    
    # In actual implementation (see aletheia/agents/code_inspector.py):
    # 
    # def _register_plugins(self):
    #     self.kernel.add_plugin(GitPlugin(repositories), plugin_name="git")
    # 
    # async def _execute_conversational(self):
    #     conversation = self.scratchpad.get_conversation_context()
    #     patterns = self.read_scratchpad("PATTERN_ANALYSIS")
    #     
    #     prompt = self._build_conversational_prompt(conversation, patterns)
    #     
    #     # LLM extracts file paths and calls git plugins
    #     response = await self.invoke(prompt)
    #     
    #     self.write_scratchpad("CODE_INSPECTION", response)
    
    return prompt


# ============================================================================
# EXAMPLE 6: Complete Conversational Flow Walkthrough
# ============================================================================

def conversational_flow_walkthrough():
    """Complete example of conversational flow from start to finish.
    
    This demonstrates the full lifecycle of a conversational investigation,
    showing how LLM-delegation works at each step.
    
    **Note**: This is PSEUDOCODE for illustration. Real implementation uses
    actual SK agents, plugins, and async/await patterns.
    """
    
    # ========================================================================
    # STEP 1: User starts conversation
    # ========================================================================
    
    # User input (via CLI or UI)
    user_message = "Why is payments-svc returning 500 errors in production?"
    
    # Orchestrator appends to scratchpad
    # scratchpad.append_conversation("user", user_message)
    
    # ========================================================================
    # STEP 2: Orchestrator understands intent (LLM-driven)
    # ========================================================================
    
    # Orchestrator reads conversation
    conversation = "user: Why is payments-svc returning 500 errors in production?"
    investigation_state = {"data_collected": False, "agents_run": []}
    
    # Orchestrator asks LLM to understand intent
    intent_prompt = orchestrator_understand_intent_example(
        conversation_history=conversation,
        investigation_state=investigation_state
    )
    
    # LLM response (simulated):
    llm_intent_response = {
        "intent": "collect_data",
        "confidence": 0.95,
        "parameters": {
            "service_name": "payments-svc",
            "namespace": "production",
            "error_type": "500 errors"
        },
        "reasoning": "User wants to investigate 500 errors in payments-svc",
        "clarification_needed": None
    }
    
    # ========================================================================
    # STEP 3: Orchestrator decides next agent (LLM-driven, no hardcoded mapping)
    # ========================================================================
    
    # Orchestrator asks LLM which agent to route to
    routing_prompt = orchestrator_decide_next_agent_example(
        conversation_history=conversation,
        investigation_state=investigation_state,
        intent=llm_intent_response["intent"],
        parameters=llm_intent_response["parameters"],
        confidence=llm_intent_response["confidence"]
    )
    
    # LLM response (simulated):
    llm_routing_response = {
        "action": "route_to_agent",
        "agent": "data_fetcher",
        "reasoning": "No data collected yet. Need to fetch logs first.",
        "prerequisites_met": True,
        "suggested_response": "I'll fetch logs from payments-svc in production..."
    }
    
    # Orchestrator tells user what's happening
    # scratchpad.append_conversation("agent", llm_routing_response["suggested_response"])
    
    # ========================================================================
    # STEP 4: Data Fetcher executes (LLM extracts parameters)
    # ========================================================================
    
    # Data Fetcher reads conversation and problem description
    problem_desc = {
        "description": "Why is payments-svc returning 500 errors in production?",
        "affected_services": ["payments-svc"]
    }
    
    # Data Fetcher builds prompt for LLM
    fetch_prompt = data_fetcher_conversational_execution_example(
        conversation_history=conversation,
        problem_description=problem_desc
    )
    
    # Data Fetcher invokes SK agent with plugins registered
    # Kubernetes and Prometheus plugins available via FunctionChoiceBehavior.Auto()
    
    # LLM reasoning (internal):
    # - Extracts: pod="payments-svc", namespace="production", time="recent"
    # - Calls: kubernetes.fetch_kubernetes_logs(pod="payments-svc", namespace="production", since="1h")
    # - Returns: Summary of collected data
    
    # LLM response (simulated):
    llm_fetch_response = """
    I collected logs from payments-svc pod in production namespace.
    
    **Summary**:
    - 200 log lines collected from last hour
    - 47 ERROR level messages found
    - Top error: "nil pointer dereference at features.go:57" (45 occurrences)
    - Circuit breaker opened to promo-svc at 08:05:15
    
    **Key Finding**: Most errors are null pointer dereferences in feature flag code.
    """
    
    # Data Fetcher writes to scratchpad
    # scratchpad.write_section("DATA_COLLECTED", {"logs": [...], "summary": llm_fetch_response})
    # scratchpad.append_conversation("agent", llm_fetch_response)
    
    # ========================================================================
    # STEP 5: Orchestrator routes to next agent (Pattern Analyzer)
    # ========================================================================
    
    # Orchestrator reads updated conversation
    updated_conversation = conversation + "\n" + llm_fetch_response
    updated_state = {"data_collected": True, "agents_run": ["data_fetcher"]}
    
    # Orchestrator asks LLM what to do next
    next_routing_prompt = orchestrator_decide_next_agent_example(
        conversation_history=updated_conversation,
        investigation_state=updated_state,
        intent="investigate_further",
        parameters=llm_intent_response["parameters"],
        confidence=0.9
    )
    
    # LLM decides: route to pattern_analyzer
    # (Similar pattern continues through pattern_analyzer → code_inspector → root_cause_analyst)
    
    # ========================================================================
    # FINAL: Complete diagnosis presented to user
    # ========================================================================
    
    # Root Cause Analyst synthesizes everything and writes FINAL_DIAGNOSIS
    # Orchestrator presents diagnosis to user in natural language
    
    print("✅ Complete conversational flow demonstrated")
    print("✅ No custom parameter extraction logic")
    print("✅ All decisions made by LLM via prompts")
    print("✅ All external operations via SK plugins")


# ============================================================================
# KEY TAKEAWAYS FOR DEVELOPERS
# ============================================================================

"""
**When implementing conversational features, remember**:

1. **Always Delegate to LLM**:
   ✅ DO: Pass conversation context to LLM, let it extract parameters
   ❌ DON'T: Write regex or parsers to extract pod names, namespaces, etc.

2. **Use Plugins for External Operations**:
   ✅ DO: Register plugins, let LLM call them via FunctionChoiceBehavior.Auto()
   ❌ DON'T: Make direct subprocess calls or HTTP requests in agent code

3. **Thin Agent Pattern**:
   ✅ DO: Build prompts, invoke LLM, execute decisions
   ❌ DON'T: Implement complex logic in agent methods

4. **Prompt Engineering First**:
   ✅ DO: Enhance prompts to guide LLM behavior
   ❌ DON'T: Add Python code for decision logic

5. **Scratchpad for Context**:
   ✅ DO: Use scratchpad.get_conversation_context() for full history
   ❌ DON'T: Parse or transform conversation in agent code

6. **Natural Language All The Way**:
   ✅ DO: Let LLM generate responses, questions, summaries in natural language
   ❌ DON'T: Use hardcoded templates or formatted strings

**Example of GOOD conversational code**:

```python
async def execute_conversational(self):
    # Read context from scratchpad
    conversation = self.scratchpad.get_conversation_context()
    problem = self.read_scratchpad("PROBLEM_DESCRIPTION")
    
    # Build prompt with context
    prompt = f'''
    Based on this conversation:
    {conversation}
    
    Problem: {problem}
    
    Use kubernetes plugin to fetch relevant logs.
    '''
    
    # Let LLM do everything
    response = await self.invoke(prompt)
    
    # Write results
    self.write_scratchpad("DATA_COLLECTED", response)
```

**Example of BAD conversational code (custom extraction)**:

```python
async def execute_conversational(self):
    conversation = self.scratchpad.get_conversation_context()
    
    # ❌ WRONG: Custom parameter extraction
    pod_match = re.search(r'pod[:\s]+([a-z0-9-]+)', conversation)
    pod = pod_match.group(1) if pod_match else "default"
    
    # ❌ WRONG: Hardcoded intent mapping
    if "logs" in conversation.lower():
        action = "fetch_logs"
    elif "metrics" in conversation.lower():
        action = "fetch_metrics"
    
    # ❌ WRONG: Direct subprocess call
    logs = subprocess.run(["kubectl", "logs", pod], capture_output=True)
```

**When in doubt**: Ask yourself "Could the LLM do this based on conversation context?"
If yes, delegate it to the LLM via a prompt. If no, you probably need a plugin.
"""
