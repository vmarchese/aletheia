# Semantic Kernel Migration Guide

**Version**: 1.0  
**Date**: 2025-10-17  
**Status**: Active Migration

---

## Overview

This guide documents the migration from custom LLM abstractions to **Semantic Kernel (SK)** as Aletheia's AI orchestration framework. The migration provides:

- **Automatic Function Calling**: LLMs automatically invoke tools via plugins
- **Multi-Agent Orchestration**: Built-in handoff patterns for agent coordination
- **Consistent Interface**: Unified API across multiple LLM providers
- **Improved Testing**: Better mocking and isolation patterns

## Migration Status

### Completed
✅ **Phase 1**: SK Foundation
- SKBaseAgent implementation
- Plugin architecture (Kubernetes, Prometheus, Git)
- Dual-mode support (SK + custom patterns)

✅ **Phase 2**: Agent Migration
- Data Fetcher Agent → SK ChatCompletionAgent
- Pattern Analyzer Agent → SK ChatCompletionAgent
- Code Inspector Agent → SK ChatCompletionAgent
- Root Cause Analyst Agent → SK ChatCompletionAgent

✅ **Phase 3**: Testing Updates
- All agent tests updated for SK patterns
- Plugin unit tests (100% coverage)
- Integration tests with mocked SK components

### In Progress
🔄 **Phase 4**: Orchestration Migration
- AletheiaHandoffOrchestration wrapper implemented
- Custom orchestration still default (feature flag: `use_sk_orchestration: false`)
- Gradual rollout of SK orchestration patterns

### Planned
📋 **Phase 5**: Deprecation
- Mark custom `BaseAgent` as deprecated (after SK migration complete)
- Mark custom `LLMProvider` as deprecated (keeping as backup)
- Remove custom patterns in v2.0

---

## Feature Flags

Aletheia supports both custom and SK patterns during migration via feature flags.

### Configuration

```yaml
# .aletheia/config.yaml or ~/.aletheia/config.yaml
agents:
  use_sk_agents: true           # Use SK-based agents (default: true)
  use_sk_orchestration: false   # Use SK HandoffOrchestration (default: false)

llm:
  use_sk_services: true         # Use SK OpenAIChatCompletion (default: true)
```

### Environment Variables

```bash
# Override config with environment variables
export ALETHEIA_USE_SK_AGENTS=true
export ALETHEIA_USE_SK_ORCHESTRATION=false
export ALETHEIA_USE_SK_SERVICES=true
```

### Precedence

1. **Environment variables** (highest)
2. **Project config** (`./.aletheia/config.yaml`)
3. **User config** (`~/.aletheia/config.yaml`)
4. **Default values** (lowest)

---

## Migration Path: Agents

### Before: Custom BaseAgent

```python
from aletheia.agents.base import BaseAgent
from aletheia.llm.provider import LLMFactory

class MyAgent(BaseAgent):
    def __init__(self, config, scratchpad):
        super().__init__(config, scratchpad)
        self.llm = LLMFactory.create_provider(config["llm"])
        self.fetcher = MyFetcher(config)
    
    def execute(self):
        # Read scratchpad
        problem = self.scratchpad.read_section("PROBLEM_DESCRIPTION")
        
        # Direct tool invocation
        data = self.fetcher.fetch_data(problem["service"])
        
        # Direct LLM call
        response = self.llm.complete([
            {"role": "system", "content": "You are an agent..."},
            {"role": "user", "content": f"Analyze: {data}"}
        ])
        
        # Write to scratchpad
        self.scratchpad.write_section("MY_SECTION", {
            "analysis": response.content
        })
```

### After: SK ChatCompletionAgent

```python
from aletheia.agents.sk_base import SKBaseAgent
from aletheia.plugins.my_plugin import MyPlugin

class MyAgent(SKBaseAgent):
    def __init__(self, config, scratchpad):
        # Agent name for config lookup
        super().__init__(config, scratchpad, agent_name="my_agent")
        
        # Register plugin (replaces direct tool invocation)
        self.kernel.add_plugin(MyPlugin(config), plugin_name="my_tool")
    
    async def execute(self):
        # Read scratchpad (same as before)
        problem = self.read_scratchpad("PROBLEM_DESCRIPTION")
        
        # LLM automatically calls plugin functions
        task = f"Fetch and analyze data for service: {problem['service']}"
        response = await self.invoke(task)
        
        # Write to scratchpad (same as before)
        self.write_scratchpad("MY_SECTION", {
            "analysis": response
        })
```

### Key Changes

1. **Inherit from `SKBaseAgent`** instead of `BaseAgent`
2. **Create plugins** for external tool operations
3. **Register plugins** in `__init__` via `self.kernel.add_plugin()`
4. **Use `await self.invoke()`** instead of direct LLM calls
5. **LLM automatically calls** plugin functions (FunctionChoiceBehavior.Auto)
6. **Async execution** required for SK agent methods

---

## Migration Path: Plugins

### Before: Direct Tool Invocation

```python
# In agent code
from aletheia.fetchers.kubernetes import KubernetesFetcher

class DataFetcherAgent(BaseAgent):
    def execute(self):
        fetcher = KubernetesFetcher(self.config)
        
        # Direct method call
        logs = fetcher.fetch_logs(
            pod="payments-svc",
            namespace="production",
            sample_size=200
        )
```

### After: Plugin with @kernel_function

```python
# In aletheia/plugins/kubernetes_plugin.py
from semantic_kernel.functions import kernel_function
from typing import Annotated
from aletheia.fetchers.kubernetes import KubernetesFetcher

class KubernetesPlugin:
    def __init__(self, config):
        self.fetcher = KubernetesFetcher(config)
    
    @kernel_function(
        name="fetch_kubernetes_logs",
        description="Fetch logs from a Kubernetes pod with optional filtering and sampling"
    )
    def fetch_logs(
        self,
        pod: Annotated[str, "The name of the pod to fetch logs from"],
        namespace: Annotated[str, "The Kubernetes namespace"] = "default",
        sample_size: Annotated[int, "Target number of log entries"] = 200,
    ) -> Annotated[str, "JSON string containing logs, summary, and metadata"]:
        """Fetch logs from Kubernetes pod.
        
        The LLM uses the @kernel_function description and Annotated
        type hints to understand how to call this function.
        """
        result = self.fetcher.fetch_logs(pod, namespace, sample_size)
        
        # Return as JSON string
        import json
        return json.dumps({
            "success": True,
            "logs": result["logs"],
            "summary": result["summary"]
        })

# In agent code
class DataFetcherAgent(SKBaseAgent):
    def __init__(self, config, scratchpad):
        super().__init__(config, scratchpad, agent_name="data_fetcher")
        
        # Register plugin - LLM can now call functions automatically
        self.kernel.add_plugin(
            KubernetesPlugin(config),
            plugin_name="kubernetes"
        )
    
    async def execute(self):
        # LLM automatically calls fetch_kubernetes_logs
        task = "Fetch logs from pod payments-svc in namespace production"
        response = await self.invoke(task)
```

### Key Changes

1. **Create plugin class** wrapping your tool/fetcher
2. **Add `@kernel_function` decorator** to each operation
3. **Use `Annotated[type, "description"]`** for all parameters
4. **Return JSON strings** for complex results
5. **Register plugin** in agent's `__init__`
6. **LLM automatically calls** appropriate functions

---

## Migration Path: LLM Services

### Before: Custom LLMProvider

```python
from aletheia.llm.provider import LLMFactory, OpenAIProvider

llm = LLMFactory.create_provider(config["llm"])
response = llm.complete([
    {"role": "system", "content": "You are..."},
    {"role": "user", "content": "Analyze..."}
])
print(response.content)
```

### After: SK OpenAIChatCompletion

```python
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior

# Create kernel
kernel = Kernel()

# Add OpenAI service
service = OpenAIChatCompletion(
    service_id="openai-chat",
    ai_model_id="gpt-4o",
    api_key=os.getenv("OPENAI_API_KEY")
)
kernel.add_service(service)

# Configure execution settings
settings = kernel.get_prompt_execution_settings_from_service_id("openai-chat")
settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

# Invoke (plugins registered with kernel can be called automatically)
result = await kernel.invoke_prompt(
    "Analyze this data...",
    settings=settings
)
print(result)
```

### Key Changes

1. **Create `Kernel` instance** instead of LLMProvider
2. **Add `OpenAIChatCompletion` service** to kernel
3. **Configure `FunctionChoiceBehavior.Auto()`** for plugin support
4. **Use `await kernel.invoke_prompt()`** instead of `llm.complete()`
5. **All calls are async** in SK

---

## Migration Path: Orchestration

### Before: Custom Agent Registry

```python
class OrchestratorAgent:
    def __init__(self, config, scratchpad):
        self.agent_registry = {
            "data_fetcher": DataFetcherAgent(config, scratchpad),
            "pattern_analyzer": PatternAnalyzerAgent(config, scratchpad),
            "code_inspector": CodeInspectorAgent(config, scratchpad),
            "root_cause_analyst": RootCauseAnalystAgent(config, scratchpad),
        }
    
    def execute_guided_mode(self):
        # Manual routing
        data_result = self.agent_registry["data_fetcher"].execute()
        patterns = self.agent_registry["pattern_analyzer"].execute()
        code = self.agent_registry["code_inspector"].execute()
        diagnosis = self.agent_registry["root_cause_analyst"].execute()
```

### After: SK HandoffOrchestration

```python
from aletheia.agents.orchestration_sk import AletheiaHandoffOrchestration
from semantic_kernel.agents import OrchestrationHandoffs

class OrchestratorAgent:
    def __init__(self, config, scratchpad, console):
        # Create agents
        self.agents = [
            DataFetcherAgent(config, scratchpad),
            PatternAnalyzerAgent(config, scratchpad),
            CodeInspectorAgent(config, scratchpad),
            RootCauseAnalystAgent(config, scratchpad),
        ]
        
        # Define handoff rules (routing topology)
        handoffs = OrchestrationHandoffs(
            # data_fetcher -> pattern_analyzer (after data collection)
            # pattern_analyzer -> code_inspector (after analysis)
            # code_inspector -> root_cause_analyst (after code inspection)
        )
        
        # Create SK orchestration
        self.orchestration = AletheiaHandoffOrchestration(
            agents=self.agents,
            handoffs=handoffs,
            scratchpad=scratchpad,
            console=console
        )
    
    async def execute_guided_mode(self):
        # SK automatically routes between agents based on handoff rules
        await self.orchestration.execute(initial_agent=self.agents[0])
```

### Key Changes

1. **Define `OrchestrationHandoffs`** with routing rules
2. **Create `AletheiaHandoffOrchestration`** wrapper
3. **SK automatically routes** between agents based on handoffs
4. **Callbacks update scratchpad** automatically
5. **Human-in-the-loop** via `human_response_function`

---

## Testing Migration

### Before: Custom Mocking

```python
def test_agent():
    mock_llm = Mock()
    mock_llm.complete.return_value = Mock(content="Analysis result")
    
    agent = MyAgent(config, scratchpad)
    agent.llm = mock_llm
    
    result = agent.execute()
    assert result["status"] == "success"
```

### After: SK Mocking

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch

@pytest.mark.asyncio
async def test_agent():
    # Mock SK agent
    mock_agent = AsyncMock()
    mock_agent.invoke = AsyncMock(return_value="Analysis result")
    
    # Mock kernel
    mock_kernel = Mock()
    mock_kernel.add_plugin = Mock()
    
    agent = MyAgent(config, scratchpad)
    
    with patch.object(agent, '_agent', mock_agent), \
         patch.object(agent, '_kernel', mock_kernel):
        
        result = await agent.execute()
        
        assert result["status"] == "success"
        mock_agent.invoke.assert_called_once()
```

### Key Changes

1. **Use `pytest-asyncio`** for async tests
2. **Mock `_agent` and `_kernel`** attributes
3. **Use `AsyncMock`** for async methods
4. **Verify plugin registration** in tests
5. **Test plugins separately** with their own mocks

---

## Common Migration Issues

### Issue 1: Async/Await Required

**Problem**: SK methods are async, but custom code is synchronous

```python
# ❌ Won't work - missing await
result = self.invoke(task)
```

**Solution**: Make methods async and use await

```python
# ✅ Correct
async def execute(self):
    result = await self.invoke(task)
```

### Issue 2: Plugin Not Registered

**Problem**: LLM doesn't call plugin functions

**Solution**: Verify plugin registration in `__init__`

```python
def __init__(self, config, scratchpad):
    super().__init__(config, scratchpad, agent_name="my_agent")
    
    # Must register BEFORE using the agent
    self.kernel.add_plugin(MyPlugin(config), plugin_name="my_tool")
```

### Issue 3: Missing Type Annotations

**Problem**: LLM doesn't understand function parameters

```python
# ❌ Missing descriptions
def my_function(self, param1: str, param2: int):
    ...
```

**Solution**: Use `Annotated` with descriptions

```python
# ✅ Correct
from typing import Annotated

def my_function(
    self,
    param1: Annotated[str, "Description for LLM"],
    param2: Annotated[int, "Another description"]
):
    ...
```

### Issue 4: Agent Name Mismatch

**Problem**: Agent configuration not found

```python
# ❌ Agent name doesn't match config
super().__init__(config, scratchpad, agent_name="wrong_name")

# Config has:
# llm:
#   agents:
#     data_fetcher:  # <-- actual name
#       model: "gpt-4o"
```

**Solution**: Use correct agent name

```python
# ✅ Correct
super().__init__(config, scratchpad, agent_name="data_fetcher")
```

---

## Rollback Plan

If issues arise during migration:

### 1. Disable SK via Feature Flags

```yaml
# Rollback to custom patterns
agents:
  use_sk_agents: false
  use_sk_orchestration: false
llm:
  use_sk_services: false
```

### 2. Environment Variable Override

```bash
# Quick rollback without config changes
export ALETHEIA_USE_SK_AGENTS=false
export ALETHEIA_USE_SK_ORCHESTRATION=false
export ALETHEIA_USE_SK_SERVICES=false
```

### 3. Dual-Mode Execution

Agents support both patterns during migration:

```python
async def execute(self, use_sk: bool = True):
    if use_sk:
        # SK-based execution
        result = await self.invoke(task)
    else:
        # Legacy execution
        result = self._legacy_execute()
```

---

## Timeline

### Completed (2025-10-15)
- ✅ SK foundation and plugins (tasks 3.4.5, 3.4.6, 3.4.7)
- ✅ All agents migrated to SK (tasks 3.4.8, 3.5.6, 3.6.7, 3.7.6)
- ✅ Integration tests updated (task 3.8.3, 3.8.4)

### Current (2025-10-17)
- 🔄 Documentation updates (task 3.9.1, 3.9.2)
- 🔄 SK orchestration opt-in via feature flags

### Future (v1.1)
- 📋 SK orchestration as default (change feature flag default)
- 📋 Remove custom BaseAgent and LLMProvider

### Future (v2.0)
- 📋 Complete removal of custom patterns
- 📋 SK-only codebase

---

## Resources

- **Semantic Kernel Documentation**: https://learn.microsoft.com/en-us/semantic-kernel/
- **SK Python Samples**: https://github.com/microsoft/semantic-kernel/tree/main/python
- **Aletheia SPECIFICATION.md**: Section 2.6 - Semantic Kernel Architecture
- **Aletheia AGENTS.md**: Semantic Kernel Development Patterns section

---

## Support

For migration questions or issues:
1. Check this guide first
2. Review `SPECIFICATION.md` section 2.6
3. Review `AGENTS.md` SK patterns section
4. Check existing SK-based agent implementations (DataFetcherAgent, etc.)
5. Review plugin implementations (kubernetes_plugin.py, git_plugin.py, prometheus_plugin.py)

---

**Last Updated**: 2025-10-17  
**Migration Status**: Phase 4 (Orchestration Migration)  
**Next Milestone**: SK orchestration rollout
