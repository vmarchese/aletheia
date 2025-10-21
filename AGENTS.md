# AGENTS.md - Python Development Guide

## Overview

This document provides guidelines for AI agents working on this Python project. Follow these instructions to ensure consistent development practices and maintain code quality.

## Prerequisites

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) package manager
- Git with worktree support

## Package Management

This project uses **uv** as the package manager. All dependency management should be done through uv.

### Common uv Commands

```bash
# Install dependencies
uv pip install -r requirements.txt

# Install package in editable mode
uv pip install -e .

# Add a new dependency
uv pip install <package-name>

# Sync dependencies
uv pip sync requirements.txt
```

## Session Workflow

### 0. General instructions
- Use a memory file to store information between interactions. The memory file should be named `.claude/memory/<task-id>-<task-description>.md` where `<task-id>` is the id of the task you are working on (example: `./claude/memory/2.4-prometheus-fetcher-16.md`)
- NEVER change files outside the current worktree. 
- When updating `TODO.md` and `.claude/memory/<task-id>-<task-description>.md` ALWAYS use the workingtree you are working in
- ALWAYS keep the code simple and clean, DO NOT overengineer

### 1. Start of Session - Feature Branch Setup

At the beginning of every development session, you **MUST**:
- Read thouroughlly the file SPECIFICATION.md
- Read the `TODO.md` file and the `.claude/memory/*.md` files to check what is still missing
- Create a new worktree and branch:
  1. **Ask the user for the feature name:**
   ```
   "What feature would you like to work on? Please provide a short feature name (e.g., 'user-auth', 'api-endpoint', 'bug-fix-123')"
   ```
  2. **Create the worktree and branch:**
   ```bash
   git worktree add worktrees/feat/<task-id>-<feat-name> -b feat/<task-id>-<feat-name>
   ```
   where `<task-id>` is the id of the task in the `TODO.md` file the user requested to implement

  3. **Navigate to the worktree:**
   ```bash
   cd worktrees/feat/<task-id>-<feat-name>
   ```

  4. **Set up the environment:**
   ```bash
   # Install dependencies
   uv pip install -r requirements.txt
   
   # Install development dependencies if they exist
   uv pip install -r requirements-dev.txt  # if applicable
   ```
- Create a new virtual environment in the worktree `worktrees/feat/<task-id>-<feat-name>` with `uv venv --python 3.12`
- activate the virtual environment with `source .venv/bin/activate`
- install the required dependencies with `uv pip install --prerelease=allow -r requirements.txt -r requirements-dev.txt`

### 2. Development Phase

- Make changes in the worktree directory
- Follow Python best practices (PEP 8, type hints, docstrings)
- Write tests for new functionality
- Commit changes regularly with clear, descriptive messages

```bash
git add .
git commit -m "feat: descriptive message about the change"
```

### 3. End of Session - Testing & Validation

Before considering the session complete, you **MUST**:

1. **Run all tests in the repository:**
   ```bash
   # Common test commands (adjust based on project setup)
   
   # If using pytest
   pytest
   
   # If using unittest
   python -m unittest discover
   
   # If using tox
   tox
   
   # With coverage
   pytest --cov=. --cov-report=term-missing
   ```

2. **Verify all tests pass:**
   - All tests must pass before finishing the session
   - If tests fail, fix the issues before concluding
   - Document any known issues or test failures

3. **Summary before finishing:**
   - Provide a summary of changes made
   - Confirm all tests passed
   - Note the branch name and worktree location
   - summarize the key points and write them to the memory file.
   - Use the following example template for the memory file start:
```
## Session Update - 2025-10-14 (Prometheus Fetcher Implementation)

### Completed: TODO Step 2.4 - Prometheus Fetcher

**Status**: ✅ COMPLETE

**Worktree**: `worktrees/feat/2.4-prometheus-fetcher`
**Branch**: `feat/2.4-prometheus-fetcher`
**Commit**: `658c681`

#### What Was Implemented:
...details
```
   - update the TODO.md file marking the task as completed

## Git Worktree Management

### Listing Worktrees
```bash
git worktree list
```

### Removing a Worktree (after merging)
```bash
# Remove the worktree
git worktree remove worktrees/feat/<task-id>-<feat-name>

# Delete the branch (if merged)
git branch -d feat/<task-id>-<feat-name>
```

### Switching Between Worktrees
Navigate to different worktrees using standard `cd` commands:
```bash
cd worktrees/feat/<task-id>-<different-feat-name>
```

## Code Quality Standards

### Style Guide
- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Maximum line length: 88 characters (Black formatter default)

### Type Hints
- Use type hints for function parameters and return values
- Use `typing` module for complex types

```python
from typing import List, Dict, Optional

def process_data(items: List[str], config: Dict[str, any]) -> Optional[str]:
    """Process data with given configuration."""
    pass
```

### Documentation
- Write docstrings for all public functions, classes, and modules
- Use Google or NumPy docstring format consistently
- Include examples in docstrings where helpful

### Testing
- Write unit tests for all new functionality
- Aim for >80% code coverage
- Use fixtures for common test setup
- Test edge cases and error conditions

## Project Structure

```
project/
├── src/                  # Source code
├── tests/                # Test files
├── worktrees/            # Git worktrees
│   └── feat/             # Feature worktrees
├── requirements.txt      # Production dependencies
├── requirements-dev.txt  # Development dependencies
├── pyproject.toml        # Project configuration
├── AGENTS.md            # This file
├── SPECIFICATION.md     # Product requirements and architecture
└── MIGRATION_SK.md      # Semantic Kernel migration guide
```

## Semantic Kernel Development Patterns

### Overview

Aletheia uses **Microsoft Semantic Kernel** as its AI orchestration framework. All new agent implementations should use the SK-based patterns described below.

### Creating SK-Based Agents

#### 1. Agent Base Class

All specialist agents inherit from `SKBaseAgent`:

```python
from aletheia.agents.sk_base import SKBaseAgent
from aletheia.scratchpad import Scratchpad

class MyAgent(SKBaseAgent):
    """My specialist agent using Semantic Kernel."""
    
    def __init__(self, config: Dict[str, Any], scratchpad: Scratchpad):
        # Agent name used for config lookup (config.llm.agents.my_agent)
        super().__init__(config, scratchpad, agent_name="my_agent")
        
        # Register plugins
        from aletheia.plugins.my_plugin import MyPlugin
        self.kernel.add_plugin(MyPlugin(config), plugin_name="my_tool")
    
    async def execute(self) -> Dict[str, Any]:
        """Main execution method."""
        # Read from scratchpad
        problem = self.read_scratchpad("PROBLEM_DESCRIPTION")
        
        # Invoke SK agent with task
        task = f"Analyze the problem: {problem}"
        response = await self.invoke(task)
        
        # Write results to scratchpad
        self.write_scratchpad("MY_SECTION", {
            "analysis": response,
            "confidence": 0.85
        })
        
        return {"status": "success"}
```

**Key Points**:
- Inherit from `SKBaseAgent` (not the deprecated `BaseAgent`)
- Use `agent_name` parameter for config lookup
- Register plugins in `__init__` via `self.kernel.add_plugin()`
- Use `await self.invoke(task)` for LLM interactions
- Maintain scratchpad read/write for state sharing

#### 2. Creating Plugins

Plugins expose external tools as kernel functions:

```python
from semantic_kernel.functions import kernel_function
from typing import Annotated

class MyPlugin:
    """Semantic Kernel plugin for my tool."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        # Initialize your tool/client here
    
    @kernel_function(
        name="my_operation",
        description="Performs my operation with the specified parameters"
    )
    def my_operation(
        self,
        param1: Annotated[str, "Description of param1 for the LLM"],
        param2: Annotated[int, "Description of param2"] = 10,
    ) -> Annotated[str, "Description of return value"]:
        """Detailed docstring for developers.
        
        The LLM uses the @kernel_function decorator's description
        and Annotated type hints to understand how to call this function.
        
        Args:
            param1: Parameter description for developers
            param2: Parameter description for developers
            
        Returns:
            Result description for developers
        """
        # Implement your operation
        result = self._do_operation(param1, param2)
        
        # Return as JSON string for complex results
        import json
        return json.dumps({
            "success": True,
            "result": result,
            "metadata": {...}
        })
```

**Key Points**:
- Use `@kernel_function` decorator with `name` and `description`
- Use `Annotated[type, "description"]` for all parameters
- Return JSON strings for complex results
- Keep functions focused and composable

#### 3. Function Choice Behavior

The LLM automatically calls plugin functions via `FunctionChoiceBehavior.Auto()`:

```python
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior

# This is set automatically in SKBaseAgent, but can be customized:
execution_settings = OpenAIChatPromptExecutionSettings(
    function_choice_behavior=FunctionChoiceBehavior.Auto()
)
```

**Execution Flow**:
1. Agent receives task: "Fetch logs from pod payments-svc"
2. LLM determines to call `fetch_kubernetes_logs`
3. SK invokes function with parameters: `pod="payments-svc", namespace="default"`
4. Function returns results to LLM
5. LLM synthesizes results and continues reasoning

#### 4. Testing SK Agents

Test SK agents by mocking plugins and kernel services:

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch
from aletheia.agents.my_agent import MyAgent
from aletheia.scratchpad import Scratchpad

@pytest.fixture
def mock_kernel():
    """Mock SK kernel."""
    kernel = Mock()
    kernel.add_plugin = Mock()
    return kernel

@pytest.fixture
def mock_agent():
    """Mock SK ChatCompletionAgent."""
    agent = AsyncMock()
    agent.invoke = AsyncMock(return_value="Mocked response")
    return agent

@pytest.mark.asyncio
async def test_my_agent_execution(mock_kernel, mock_agent, tmp_path):
    """Test agent execution with mocked SK components."""
    config = {
        "llm": {"default_model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"},
        "my_config": "value"
    }
    scratchpad = Scratchpad(encryption_key=b"test_key" * 2)
    
    agent = MyAgent(config, scratchpad)
    
    # Mock kernel and agent
    with patch.object(agent, '_kernel', mock_kernel), \
         patch.object(agent, '_agent', mock_agent):
        
        result = await agent.execute()
        
        assert result["status"] == "success"
        mock_agent.invoke.assert_called_once()
```

**Testing Best Practices**:
- Mock the kernel and SK agent for unit tests
- Mock plugin operations to isolate agent logic
- Test plugin implementations separately with their own mocks
- Use `pytest-asyncio` for async agent tests
- Verify scratchpad writes with assertions

#### 5. Dual-Mode Support

During migration, agents support both SK and custom patterns:

```python
class MyAgent(SKBaseAgent):
    async def execute(self, use_sk: bool = True) -> Dict[str, Any]:
        """Execute with optional SK usage."""
        if use_sk:
            # SK-based execution
            response = await self.invoke(task)
        else:
            # Legacy execution
            response = self._legacy_execute()
        
        self.write_scratchpad("MY_SECTION", response)
        return {"status": "success"}
```

**Feature Flag Configuration**:
```yaml
agents:
  use_sk_agents: true  # Use SK-based agents (default: true)
```

### LLM Configuration

Aletheia supports flexible LLM configuration including custom OpenAI-compatible endpoints.

#### Default Configuration

Configure default settings that apply to all agents:

```yaml
llm:
  default_model: "gpt-4o"
  base_url: "https://api.openai.com/v1"  # Optional: custom endpoint
  api_key_env: "OPENAI_API_KEY"
```

#### Agent-Specific Configuration

Override settings per agent with agent-specific precedence:

```yaml
llm:
  default_model: "gpt-4o"
  base_url: "https://api.openai.com/v1"
  
  agents:
    data_fetcher:
      model: "gpt-4o"
      base_url: "https://custom-endpoint.example.com/v1"  # Override default
    
    pattern_analyzer:
      model: "gpt-4o-mini"
      # No base_url - uses default from llm.base_url
    
    root_cause_analyst:
      model: "o1"
      # Uses default base_url for reasoning tasks
```

#### Azure OpenAI Example

```yaml
llm:
  default_model: "gpt-4"
  base_url: "https://my-resource.openai.azure.com/openai/deployments/gpt-4"
  api_key_env: "AZURE_OPENAI_API_KEY"
```

**Note**: The above uses `base_url` for Azure OpenAI. For full Azure OpenAI Services support with native SK integration, see the Azure OpenAI Configuration section below.

#### Azure OpenAI Services (Native Support)

Aletheia provides native Azure OpenAI Services support through Semantic Kernel's `AzureChatCompletion`:

**Default Azure Configuration**:
```yaml
llm:
  use_azure: true
  azure_deployment: "gpt-4o"
  azure_endpoint: "https://my-resource.openai.azure.com/"
  azure_api_version: "2024-02-15-preview"  # Optional, uses SK default if omitted
  api_key_env: "AZURE_OPENAI_API_KEY"
```

**Agent-Specific Azure Configuration**:
```yaml
llm:
  # Default: Standard OpenAI
  default_model: "gpt-4o"
  api_key_env: "OPENAI_API_KEY"
  
  agents:
    data_fetcher:
      # This agent uses Azure OpenAI
      use_azure: true
      azure_deployment: "gpt-4o"
      azure_endpoint: "https://my-resource.openai.azure.com/"
    
    pattern_analyzer:
      # This agent uses standard OpenAI
      model: "gpt-4o-mini"
```

**Mixed Configuration (Azure as Default)**:
```yaml
llm:
  # Default: Azure OpenAI for all agents
  use_azure: true
  azure_deployment: "gpt-4o"
  azure_endpoint: "https://default-resource.openai.azure.com/"
  api_key_env: "AZURE_OPENAI_API_KEY"
  
  agents:
    code_inspector:
      # Override to use standard OpenAI for this agent
      use_azure: false
      model: "gpt-4o"
      api_key_env: "OPENAI_API_KEY"
```

**Required Azure Fields**:
- `use_azure`: Set to `true` to enable Azure OpenAI
- `azure_deployment`: Azure deployment name (required when `use_azure=true`)
- `azure_endpoint`: Azure resource endpoint URL (required when `use_azure=true`)

**Optional Azure Fields**:
- `azure_api_version`: API version (e.g., "2024-02-15-preview"). If omitted, SK uses its default

**Configuration Priority** (Azure vs. Standard OpenAI):
1. Agent-specific `use_azure` (highest priority)
2. Default `llm.use_azure`
3. Standard OpenAI (default: `use_azure=false`)

#### Local/Self-Hosted LLM Example

```yaml
llm:
  default_model: "llama-3.1-70b"
  base_url: "http://localhost:8000/v1"  # Local OpenAI-compatible server
```

**Configuration Priority**:
1. Agent-specific `base_url` (highest priority)
2. Default `llm.base_url`
3. SDK default (OpenAI API if not specified)

### Plugin Examples

#### Kubernetes Plugin
```python
from aletheia.plugins.kubernetes_plugin import KubernetesPlugin

# In agent __init__:
self.kernel.add_plugin(
    KubernetesPlugin(self.config),
    plugin_name="kubernetes"
)

# LLM can now call:
# - fetch_kubernetes_logs(pod, namespace, ...)
# - list_kubernetes_pods(namespace, selector)
# - get_pod_status(pod, namespace)
```

#### Prometheus Plugin
```python
from aletheia.plugins.prometheus_plugin import PrometheusPlugin

# In agent __init__:
self.kernel.add_plugin(
    PrometheusPlugin(self.config),
    plugin_name="prometheus"
)

# LLM can now call:
# - fetch_prometheus_metrics(query, start, end, ...)
# - execute_promql_query(query)
# - build_promql_from_template(template, params)
```

#### Git Plugin
```python
from aletheia.plugins.git_plugin import GitPlugin

# In agent __init__:
git_plugin = GitPlugin(repositories=self.config.get("repositories", []))
self.kernel.add_plugin(git_plugin, plugin_name="git")

# LLM can now call:
# - git_blame(file_path, line_number, repo)
# - find_file_in_repo(filename, repo)
# - extract_code_context(file_path, line_number, context_lines)
```

### Specialized Data Fetcher Agents

Aletheia uses **specialized data fetcher agents** for better separation of concerns and maintainability:

#### When to Create Specialized vs General-Purpose Agents

**Create Specialized Agents When**:
- Each data source has distinct configuration and authentication
- Different plugins are needed for each source (KubernetesPlugin vs PrometheusPlugin)
- Query patterns and sampling strategies differ significantly
- Testing isolation is beneficial (mock K8s separately from Prometheus)
- LLM context becomes clearer with focused agent instructions

**Benefits of Specialized Agents**:
- **Single Responsibility**: Each agent focuses on one data source
- **Easier Testing**: Mock and test each data source in isolation
- **Better Prompts**: More focused instructions lead to better LLM performance
- **Scalability**: Easy to add new data sources (Elasticsearch, Jaeger, Datadog)
- **Clear Orchestration**: Explicit routing via HandoffOrchestration

#### Kubernetes Data Fetcher Agent

**Purpose**: Collect Kubernetes logs and pod information exclusively.

**Implementation Pattern**:
```python
from aletheia.agents.sk_base import SKBaseAgent
from aletheia.plugins.kubernetes_plugin import KubernetesPlugin

class KubernetesDataFetcher(SKBaseAgent):
    \"\"\"SK-based agent specialized for Kubernetes data collection.\"\"\"
    
    def __init__(self, config: Dict[str, Any], scratchpad: Scratchpad):
        super().__init__(config, scratchpad, agent_name=\"kubernetes_data_fetcher\")
        
        # Register only Kubernetes plugin
        self.kernel.add_plugin(
            KubernetesPlugin(config),
            plugin_name=\"kubernetes\"
        )
    
    async def execute(self) -> Dict[str, Any]:
        \"\"\"Collect Kubernetes logs and pod data.\"\"\"
        problem = self.read_scratchpad(\"PROBLEM_DESCRIPTION\")
        
        # Build focused prompt for K8s data collection
        task = f\"\"\"
        Collect Kubernetes logs for this problem:
        {problem}
        
        Use kubernetes plugin to:
        1. Extract pod name and namespace from problem description
        2. Fetch logs using fetch_kubernetes_logs()
        3. Summarize findings
        \"\"\"
        
        response = await self.invoke(task)
        
        # Write results to scratchpad under \"kubernetes\" key
        self.write_scratchpad(\"DATA_COLLECTED\", {
            \"kubernetes\": {
                \"summary\": response,
                \"source\": \"kubernetes\"
            }
        })
        
        return {\"status\": \"success\"}
```

**Key Points**:
- Registers **only** KubernetesPlugin (focused scope)
- Agent name: `\"kubernetes_data_fetcher\"` (for HandoffOrchestration routing)
- Writes results under `\"kubernetes\"` key in DATA_COLLECTED section
- LLM receives focused instructions about K8s operations

#### Prometheus Data Fetcher Agent

**Purpose**: Collect metrics and time-series data from Prometheus exclusively.

**Implementation Pattern**:
```python
from aletheia.agents.sk_base import SKBaseAgent
from aletheia.plugins.prometheus_plugin import PrometheusPlugin

class PrometheusDataFetcher(SKBaseAgent):
    \"\"\"SK-based agent specialized for Prometheus metrics collection.\"\"\"
    
    def __init__(self, config: Dict[str, Any], scratchpad: Scratchpad):
        super().__init__(config, scratchpad, agent_name=\"prometheus_data_fetcher\")
        
        # Register only Prometheus plugin
        self.kernel.add_plugin(
            PrometheusPlugin(config),
            plugin_name=\"prometheus\"
        )
    
    async def execute(self) -> Dict[str, Any]:
        \"\"\"Collect Prometheus metrics.\"\"\"
        problem = self.read_scratchpad(\"PROBLEM_DESCRIPTION\")
        
        # Build focused prompt for metrics collection
        task = f\"\"\"
        Collect Prometheus metrics for this problem:
        {problem}
        
        Use prometheus plugin to:
        1. Build PromQL queries using templates or custom queries
        2. Fetch metrics using fetch_prometheus_metrics()
        3. Identify metric spikes and anomalies
        \"\"\"
        
        response = await self.invoke(task)
        
        # Write results to scratchpad under \"prometheus\" key
        self.write_scratchpad(\"DATA_COLLECTED\", {
            \"prometheus\": {
                \"summary\": response,
                \"source\": \"prometheus\"
            }
        })
        
        return {\"status\": \"success\"}
```

**Key Points**:
- Registers **only** PrometheusPlugin (focused scope)
- Agent name: `\"prometheus_data_fetcher\"` (for HandoffOrchestration routing)
- Writes results under `\"prometheus\"` key in DATA_COLLECTED section
- LLM receives focused instructions about metrics and PromQL

#### Orchestration with Specialized Fetchers

**HandoffOrchestration Configuration**:

```python
from aletheia.agents.orchestration_sk import create_orchestration_with_sk_agents
from semantic_kernel.agents import OrchestrationHandoffs

# Create specialized fetcher agents
k8s_fetcher = KubernetesDataFetcher(config, scratchpad)
prom_fetcher = PrometheusDataFetcher(config, scratchpad)
pattern_analyzer = PatternAnalyzerAgent(config, scratchpad)
root_cause_analyst = RootCauseAnalystAgent(config, scratchpad)

# Define handoff rules for specialized fetchers
handoffs = OrchestrationHandoffs(
    # Triage routes to specialized fetchers
    (\"triage_agent\", \"kubernetes_data_fetcher\", \"Transfer for K8s logs\"),
    (\"triage_agent\", \"prometheus_data_fetcher\", \"Transfer for metrics\"),
    
    # Fetchers return to triage
    (\"kubernetes_data_fetcher\", \"triage_agent\", \"Transfer back after K8s data collection\"),
    (\"prometheus_data_fetcher\", \"triage_agent\", \"Transfer back after metrics collection\"),
    
    # Triage routes to analysis
    (\"triage_agent\", \"pattern_analyzer\", \"Transfer for pattern analysis\"),
)

# Create orchestration with all agents
orchestration = create_orchestration_with_sk_agents(
    agents=[triage, k8s_fetcher, prom_fetcher, pattern_analyzer, root_cause_analyst],
    handoffs=handoffs,
    scratchpad=scratchpad
)
```

**Triage Agent Instructions** (routes to correct fetcher):

```markdown
You are a triage agent that routes user requests to specialist agents.

**Available Specialist Agents**:

1. **kubernetes_data_fetcher**: Use when user needs:
   - Kubernetes pod logs
   - Pod status information
   - Container logs
   - Keywords: \"pod\", \"container\", \"kubectl\", \"k8s\"

2. **prometheus_data_fetcher**: Use when user needs:
   - Metrics and time-series data
   - Error rates, latency, throughput
   - Dashboard queries
   - Keywords: \"metrics\", \"prometheus\", \"dashboard\", \"rate\"

3. **pattern_analyzer**: Use after data collection to analyze patterns

4. **root_cause_analyst**: Use after analysis to synthesize diagnosis
```

**Example Routing Flow**:

```
User: \"Check logs for payments-svc pod in production namespace\"
  ↓
Triage Agent: Detects K8s keywords → routes to kubernetes_data_fetcher
  ↓
KubernetesDataFetcher: Collects logs → writes to scratchpad → returns to triage
  ↓
Triage Agent: Data collected → routes to pattern_analyzer
  ↓
PatternAnalyzerAgent: Analyzes patterns → writes to scratchpad → returns to triage
  ↓
...
```

### Orchestration with SK

For multi-agent coordination, use `AletheiaHandoffOrchestration`:

```python
from aletheia.agents.orchestration_sk import AletheiaHandoffOrchestration
from semantic_kernel.agents import OrchestrationHandoffs

# Define handoff rules
handoffs = OrchestrationHandoffs(
    # Define routing: agent_name -> [next_agent1, next_agent2, ...]
)

# Create orchestration
orchestration = AletheiaHandoffOrchestration(
    agents=[triage, kubernetes_fetcher, prometheus_fetcher, pattern_analyzer, code_inspector, root_cause_analyst],
    handoffs=handoffs,
    scratchpad=scratchpad,
    console=console
)

# Execute orchestration
await orchestration.execute(initial_agent=triage)
```

**Handoff Configuration**:
```yaml
agents:
  use_sk_orchestration: true  # Use SK HandoffOrchestration (default: false)
```

### Migration Guidance

**Deprecated Patterns**:
- ❌ Custom `BaseAgent` class → Use `SKBaseAgent`
- ❌ Custom `LLMProvider` abstraction → Use SK `OpenAIChatCompletion` service
- ❌ Direct subprocess calls in agents → Use plugins with `@kernel_function`

**Migration Steps**:
1. Convert agent to inherit from `SKBaseAgent`
2. Create plugins for external tools (kubectl, git, HTTP APIs)
3. Register plugins in agent `__init__`
4. Use `await self.invoke(task)` for LLM interactions
5. Update tests to mock SK components

**See**: `MIGRATION_SK.md` for detailed migration guide

## Conversational Mode Development Patterns

### Overview

**Conversational Mode** enables natural language interaction with Aletheia. This section describes the **LLM-First pattern** for implementing conversational features.

**Key Principle**: Agents build prompts and invoke the LLM; the LLM does ALL reasoning, extraction, and decision-making. Agents do NOT implement custom parsing, extraction, or classification logic.

### LLM-First Pattern

#### What is LLM-First?

Traditional agent systems implement custom logic:
```python
# ❌ OLD WAY: Custom extraction logic
def extract_pod_name(user_input: str) -> str:
    match = re.search(r'pod[:\s]+([a-z0-9-]+)', user_input)
    return match.group(1) if match else "default"
```

LLM-First pattern delegates to the LLM:
```python
# ✅ NEW WAY: LLM extraction
async def execute(self):
    conversation = self.scratchpad.get_conversation_context()
    prompt = f"""
    Based on this conversation:
    {conversation}
    
    Extract the pod name and use kubernetes.fetch_kubernetes_logs() to collect logs.
    """
    response = await self.invoke(prompt)  # LLM extracts & calls plugin
```

#### Core Principles

**1. Agents Build Prompts, LLMs Extract Parameters**

```python
prompt = f"""
You are a data fetcher agent.

Conversation: {self.scratchpad.get_conversation_context()}
Problem: {self.read_scratchpad("PROBLEM_DESCRIPTION")}

Available plugins:
- kubernetes.fetch_kubernetes_logs(pod, namespace, since, tail_lines)

Task: Extract parameters from conversation and use plugins to collect data.
"""
response = await self.invoke(prompt)
```

**2. Plugins for ALL External Operations**

```python
# ✅ CORRECT: Register plugins, let LLM call them
self.kernel.add_plugin(KubernetesPlugin(config), plugin_name="kubernetes")

# LLM automatically calls:
# kubernetes.fetch_kubernetes_logs(pod="payments-svc", namespace="production")
```

```python
# ❌ WRONG: Direct subprocess calls
logs = subprocess.run(["kubectl", "logs", pod_name], capture_output=True)
```

**3. No Hardcoded Routing Logic**

```python
# ❌ WRONG: Hardcoded intent mapping
intent_to_agent = {"collect_data": data_fetcher, "analyze": pattern_analyzer}
```

```python
# ✅ CORRECT: LLM decides routing
prompt = f"""
Based on conversation and state, which agent should run next?
Available: data_fetcher, pattern_analyzer, code_inspector, root_cause_analyst
"""
decision = await self.invoke(prompt)
```

**4. Conversation History is the Context**

```python
# Read full conversation from scratchpad
conversation = self.scratchpad.get_conversation_context()

# Include in prompt for LLM
prompt = f"Based on this conversation:\n{conversation}\n\nYour task: ..."
```

**5. LLM Generates Clarifying Questions**

```python
# ❌ WRONG: Hardcoded templates
if missing_namespace:
    question = "Which namespace? (default, production, staging)"
```

```python
# ✅ CORRECT: LLM generates questions
prompt = f"""
Conversation: {conversation}
Missing: namespace
Generate a natural, helpful question.
"""
question = await self.invoke(prompt)
```

### Implementing Conversational Agents

#### Step 1: Read Conversation Context

```python
async def _execute_conversational(self):
    # Read conversation history from scratchpad
    conversation = self.scratchpad.get_conversation_context()
    
    # Read other relevant sections
    problem = self.read_scratchpad("PROBLEM_DESCRIPTION")
    data = self.read_scratchpad("DATA_COLLECTED")
```

#### Step 2: Build Conversational Prompt

```python
def _build_conversational_prompt(self, conversation: str, problem: dict) -> str:
    return f"""
You are a data fetcher agent for troubleshooting.

**Conversation History**:
{conversation}

**Problem Description**:
{problem}

**Your Task**:
1. Extract parameters from the conversation (pod name, namespace, time window)
2. Use kubernetes plugin to fetch logs
3. Summarize findings in natural language

**Available Plugins**:
- kubernetes.fetch_kubernetes_logs(pod: str, namespace: str, since: str)
- prometheus.fetch_prometheus_metrics(query: str, start: str, end: str)

**Guidelines**:
- Extract parameters naturally ("payments service" → pod="payments-svc")
- If information missing, ask clarifying questions
- Call plugins directly (FunctionChoiceBehavior.Auto enabled)
"""
```

#### Step 3: Invoke LLM with Plugins

```python
async def _execute_conversational(self):
    conversation = self.scratchpad.get_conversation_context()
    problem = self.read_scratchpad("PROBLEM_DESCRIPTION")
    
    # Build prompt with conversation context
    prompt = self._build_conversational_prompt(conversation, problem)
    
    # LLM extracts params and calls plugins automatically
    response = await self.invoke(prompt)
    
    # Write results to scratchpad
    self.write_scratchpad("DATA_COLLECTED", {"summary": response})
    
    # Append agent response to conversation
    self.scratchpad.append_conversation("agent", response)
```

#### Step 4: Handle Clarifications

```python
async def _execute_conversational(self):
    conversation = self.scratchpad.get_conversation_context()
    
    prompt = self._build_conversational_prompt(conversation, ...)
    response = await self.invoke(prompt)
    
    # Check if LLM needs clarification
    if "need to know" in response.lower() or "which" in response.lower():
        # LLM generated a clarifying question
        self.scratchpad.append_conversation("agent", response)
        return {"status": "awaiting_user_input", "question": response}
    
    # Otherwise, process results
    self.write_scratchpad("DATA_COLLECTED", ...)
```

### Why No Custom Extraction Logic?

#### Problems with Custom Extraction

**Brittleness**: Regex patterns break with variations
```python
pattern = r'pod:\s+([a-z0-9-]+)'  # Handles "pod: payments-svc"
# Breaks: "payments pod", "the payments service", "pod called payments-svc"
```

**Maintenance Burden**: Every variation requires code changes
```python
# Must handle: "2 hours ago", "since 2h", "from 8am", "last 2 hours"
# → Endless regex updates
```

**Context Blindness**: Can't correlate across messages
```python
# Message 1: "I'm checking the payments service"
# Message 2: "Use production namespace"
# → Custom parser can't link "it" to "payments"
```

#### Advantages of LLM-Delegation

**Natural Language Understanding**: Handles all variations
```python
prompt = f"Extract pod name from: {user_input}"

# Works with all of these:
# "payments pod" → "payments-svc"
# "the pod for payments" → "payments-svc"
# "check payments-svc" → "payments-svc"
```

**Context Awareness**: Considers full conversation
```python
# Conversation:
# User: "Check payments-svc"
# Agent: "Which namespace?"
# User: "production"

# LLM extracts BOTH: {pod: "payments-svc", namespace: "production"}
```

**Graceful Degradation**: Generates appropriate questions
```python
# User: "Check the logs"
# LLM: "Which service's logs would you like me to check?"
```

**Adaptability**: No code changes for new parameters
```python
# To add "container" parameter:
# ❌ Custom: Add regex, update parser (100+ LOC)
# ✅ LLM-First: Update prompt description (2 lines)
```

### When to Use Custom Logic

**Rule of Thumb**: If the LLM can do it based on conversation, delegate to LLM.

**Use Custom Logic For**:
1. **Performance-Critical**: Parsing megabytes of binary data
2. **Deterministic Validation**: File exists checks, UUID validation
3. **External Tool Execution**: Actual subprocess calls (in plugins)

```python
# ✅ Custom validation
if not os.path.exists(repo_path):
    raise ValueError(f"Repository not found: {repo_path}")

# ✅ Custom subprocess (in plugin)
@kernel_function
def fetch_logs(self, pod: str):
    return subprocess.run(["kubectl", "logs", pod]).stdout

# ❌ Custom extraction (delegate to LLM)
# Don't: pod_match = re.search(r'pod:\s+([a-z0-9-]+)', conversation)
```

### Conversational Implementation Checklist

When implementing conversational features:

- [ ] **Agent reads conversation context**: `scratchpad.get_conversation_context()`
- [ ] **Agent builds prompts with context**: Include conversation in LLM calls
- [ ] **No custom extraction code**: No regex, string parsing, or patterns
- [ ] **Plugins registered**: External tools via `@kernel_function`
- [ ] **FunctionChoiceBehavior.Auto()**: LLM calls plugins automatically
- [ ] **Natural language responses**: Append LLM responses to conversation
- [ ] **No hardcoded routing**: LLM decides next agent
- [ ] **LLM-generated clarifications**: No hardcoded question templates

### Testing Conversational Agents

```python
@pytest.mark.asyncio
async def test_conversational_execution(mock_kernel, mock_agent):
    """Test agent with conversational context."""
    scratchpad = Scratchpad(encryption_key=b"test" * 8)
    
    # Set up conversation history
    scratchpad.append_conversation("user", "Check payments-svc in production")
    
    agent = DataFetcherAgent(config, scratchpad)
    
    with patch.object(agent, '_kernel', mock_kernel), \
         patch.object(agent, '_agent', mock_agent):
        
        # Mock LLM response with extracted parameters
        mock_agent.invoke.return_value = "Fetched 200 logs from payments-svc..."
        
        result = await agent.execute()
        
        # Verify LLM received conversation context
        call_args = mock_agent.invoke.call_args[0][0]
        assert "Check payments-svc in production" in call_args
        
        # Verify agent wrote results
        assert scratchpad.has_section("DATA_COLLECTED")
        
        # Verify agent updated conversation
        conversation = scratchpad.get_conversation_context()
        assert "Fetched 200 logs" in conversation
```

### Reference Implementation

See `aletheia/agents/workflows/conversational.py` for complete examples of:
- Intent understanding prompts
- Parameter extraction prompts
- Agent routing prompts
- Clarification generation prompts
- Complete conversational flow walkthrough

**Documentation**:
- [SPECIFICATION.md Section 13](SPECIFICATION.md#13-conversational-mode-architecture): Complete architecture guide
- [README.md Conversational Mode](README.md#conversational-mode): User-facing documentation
- `aletheia/agents/workflows/conversational.py`: Reference implementation with examples



## Common Issues & Solutions

### Issue: uv command not found
**Solution:** Install uv using:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Issue: Worktree already exists
**Solution:** Remove existing worktree first:
```bash
git worktree remove worktrees/feat/<task-id>-<feat-name>
```

### Issue: Tests failing in worktree
**Solution:** Ensure dependencies are installed in the worktree:
```bash
cd worktrees/feat/<task-id>-<feat-name>
uv pip install -r requirements.txt -r requirements-dev.txt
```

## Session Checklist

- [ ] Asked user for feature name
- [ ] Created worktree: `worktrees/feat/<task-id>-<feat-name>`, example: `worktrees/feat/2.2-kubernetes-fetcher`
- [ ] Created branch: `feat/<task-id>-<feat-name>`
- [ ] Installed dependencies with uv
- [ ] Implemented feature/fix
- [ ] Written/updated tests
- [ ] Committed changes with clear messages
- [ ] Ran all unit tests successfully (skip the integration tests in `tests/integration` unless otherwise requested)
- [ ] All tests passing
- [ ] Provided session summary
- [ ] Updated TODO.md file

## Notes

- Always work in the worktree, never in the main working directory during feature development
- Keep commits atomic and well-described
- If a session is interrupted, note the worktree location for continuation
- Clean up worktrees after features are merged to main

---

**Remember:** The mandatory steps are:
1. **Start:** 
- Ask for feature name and create worktree with task id and feature name
- ALWAYS be sure to `cd` in the created worktree
- ALWAYS create and activate the python virtual environment
- ALWAYS keep the code simple and clean, DO NOT overengineer
2. **End:** 
- Run ALL tests and verify they pass
- update `worktrees/feat/<task-id>-<feat-name>/TODO.md` and `worktrees/feat/<task-id>-<feat-name>/.claude/memory/*.md`