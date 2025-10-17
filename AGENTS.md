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
    agents=[data_fetcher, pattern_analyzer, code_inspector, root_cause_analyst],
    handoffs=handoffs,
    scratchpad=scratchpad,
    console=console
)

# Execute orchestration
await orchestration.execute(initial_agent=data_fetcher)
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
2. **End:** 
- Run ALL tests and verify they pass
- update `worktrees/feat/<task-id>-<feat-name>/TODO.md` and `worktrees/feat/<task-id>-<feat-name>/.claude/memory/*.md`