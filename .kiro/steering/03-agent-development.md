---
inclusion: always
---

# Agent Development Guide

## Agent Architecture

Agents in Aletheia are specialized LLM-powered components that handle specific troubleshooting domains. Each agent has:

- **Agent Class**: Core logic extending `BaseAgent`
- **Plugin(s)**: Tools the agent can use
- **Instructions**: System prompts and behavior guidelines
- **Skills**: Optional complex orchestrations

## Creating a New Agent

### 1. Agent Directory Structure

```
aletheia/agents/<agent_name>/
├── __init__.py
├── <agent_name>.py          # Agent class
└── instructions.md          # Agent instructions (optional)
```

### 2. Agent Class Template

```python
from typing import Any, Dict, List
from aletheia.agents.base import BaseAgent
from aletheia.plugins.<plugin_name> import <PluginClass>

class MyAgent(BaseAgent):
    """
    Brief description of what this agent does.
    
    Capabilities:
    - List key capabilities
    - What problems it solves
    - What data sources it accesses
    """
    
    def __init__(
        self,
        name: str = "my_agent",
        description: str = "Agent description",
        **kwargs: Any
    ) -> None:
        super().__init__(name=name, description=description, **kwargs)
        
        # Register plugins
        self.add_plugin(<PluginClass>())
    
    async def process_message(self, message: str) -> str:
        """
        Process user message and return response.
        
        Args:
            message: User input message
            
        Returns:
            Agent response
        """
        # Custom processing logic if needed
        return await super().process_message(message)
```

### 3. Register Agent

Add to `aletheia/agents/__init__.py`:

```python
from aletheia.agents.<agent_name>.<agent_name> import MyAgent

AVAILABLE_AGENTS = {
    # ... existing agents
    "my_agent": MyAgent,
}
```

## Agent Instructions

Instructions guide the agent's behavior and are loaded from:
1. Built-in instructions in the agent class
2. `instructions.md` file in agent directory
3. Custom instructions from config directory

### Instructions Template

```markdown
# Agent Name

## Role
You are a specialized agent for [domain]. Your purpose is to [primary goal].

## Capabilities
- Capability 1: Description
- Capability 2: Description
- Capability 3: Description

## Guidelines
1. Always [guideline 1]
2. When [condition], [action]
3. Prefer [approach] over [alternative]

## Output Format
Structure your responses with:
- **Findings**: What you discovered
- **Analysis**: Your interpretation
- **Recommendations**: Suggested next steps

## Examples
[Provide example interactions]
```

## Plugin Development

### Plugin Structure

```python
from typing import Any, Dict, List, Optional
from aletheia.plugins.base import BasePlugin

class MyPlugin(BasePlugin):
    """Plugin description."""
    
    def __init__(self) -> None:
        super().__init__(name="my_plugin")
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Return list of tools this plugin provides.
        
        Returns:
            List of tool definitions
        """
        return [
            {
                "name": "tool_name",
                "description": "What this tool does",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param1": {
                            "type": "string",
                            "description": "Parameter description"
                        }
                    },
                    "required": ["param1"]
                }
            }
        ]
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Any:
        """
        Execute a tool with given parameters.
        
        Args:
            tool_name: Name of tool to execute
            parameters: Tool parameters
            
        Returns:
            Tool execution result
        """
        if tool_name == "tool_name":
            return await self._tool_name(**parameters)
        
        raise ValueError(f"Unknown tool: {tool_name}")
    
    async def _tool_name(self, param1: str) -> Dict[str, Any]:
        """
        Tool implementation.
        
        Args:
            param1: Parameter description
            
        Returns:
            Result dictionary
        """
        # Implementation
        return {"result": "value"}
```

### Tool Design Best Practices

1. **Single Responsibility**: Each tool does one thing well
2. **Clear Naming**: Use descriptive, action-oriented names
3. **Type Safety**: Full type annotations on all parameters
4. **Error Handling**: Graceful failures with informative messages
5. **Documentation**: Clear docstrings for tools and parameters
6. **Validation**: Validate inputs before processing
7. **Async**: Use async/await for I/O operations

### Tool Parameter Schema

```python
{
    "name": "fetch_kubernetes_logs",
    "description": "Fetch logs from a Kubernetes pod",
    "parameters": {
        "type": "object",
        "properties": {
            "namespace": {
                "type": "string",
                "description": "Kubernetes namespace"
            },
            "pod_name": {
                "type": "string",
                "description": "Name of the pod"
            },
            "container": {
                "type": "string",
                "description": "Container name (optional)"
            },
            "tail_lines": {
                "type": "integer",
                "description": "Number of lines to fetch",
                "default": 100
            }
        },
        "required": ["namespace", "pod_name"]
    }
}
```

## Skills System

Skills are YAML-based orchestrations for complex multi-step operations.

### Skill Structure

```
<skills_dir>/<agent_name>/<skill_name>/
├── instructions.yaml    # Skill definition
└── scripts/            # Optional Python scripts
    └── script.py
```

### Skill Definition (instructions.yaml)

```yaml
---
name: Skill Name
description: Brief description of what this skill does
instructions: |-
  Detailed step-by-step instructions for the agent:
  
  1. First, use `tool_name(param)` to fetch data
  2. Then, analyze the results for [pattern]
  3. If [condition], call `another_tool(param)`
  4. Finally, summarize findings in [format]
  
  Important notes:
  - Always validate [something] before proceeding
  - Handle errors by [approach]
  - Return results as [format]
```

### Skills with Scripts

For complex operations, include Python scripts:

```python
# scripts/analyze_data.py
import os
import sys

# Access environment variables injected by Aletheia
input_data = os.environ.get("INPUT_DATA")
threshold = int(os.environ.get("THRESHOLD", "10"))

# Process data
result = process(input_data, threshold)

# Output to stdout (captured by Aletheia)
print(f"Analysis result: {result}")
```

Reference in skill instructions:

```yaml
instructions: |-
  1. Fetch data using `get_data()`
  2. Call script `analyze_data.py` with:
     - INPUT_DATA=<fetched data>
     - THRESHOLD=10
  3. Use script output in final response
```

## Agent Communication

### Agent-to-Agent Communication

Agents can delegate to other agents through the orchestrator:

```python
# In agent code
async def handle_complex_task(self, task: str) -> str:
    # Delegate to specialist agent
    result = await self.orchestrator.route_to_agent(
        agent_name="specialist_agent",
        message=task
    )
    return result
```

### Message Store

Agents maintain conversation history:

```python
# Access message history
messages = self.message_store.get_messages()

# Add custom message
self.message_store.add_message(
    role="assistant",
    content="Analysis complete"
)
```

## Testing Agents

### Unit Tests

```python
import pytest
from aletheia.agents.my_agent import MyAgent

@pytest.mark.asyncio
async def test_agent_initialization():
    agent = MyAgent()
    assert agent.name == "my_agent"
    assert len(agent.plugins) > 0

@pytest.mark.asyncio
async def test_agent_process_message():
    agent = MyAgent()
    response = await agent.process_message("test query")
    assert response is not None
    assert isinstance(response, str)
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_agent_with_plugin():
    agent = MyAgent()
    
    # Test tool execution
    result = await agent.execute_tool(
        "tool_name",
        {"param1": "value"}
    )
    
    assert result["status"] == "success"
```

## Agent Configuration

### Per-Agent LLM Configuration

```yaml
# config.yaml
agents:
  my_agent:
    model: gpt-4o
    temperature: 0.2
    max_tokens: 4000
```

### Custom Instructions

Place custom instructions in:
```
~/.config/aletheia/instructions/my_agent.txt
```

## Common Patterns

### Data Fetching Agent

- Focus on retrieving data from external sources
- Minimal analysis, return raw or lightly processed data
- Handle authentication and connection errors
- Support filtering and pagination

### Analysis Agent

- Receive data from other agents
- Apply domain-specific analysis
- Generate insights and recommendations
- Format results for human consumption

### Orchestration Agent

- Route requests to appropriate specialists
- Aggregate results from multiple agents
- Maintain conversation context
- Handle multi-step workflows

## Performance Tips

1. **Lazy Loading**: Load plugins only when needed
2. **Caching**: Cache expensive operations (API calls, computations)
3. **Streaming**: Use streaming for large responses
4. **Parallel Execution**: Run independent operations concurrently
5. **Token Optimization**: Minimize prompt size, use summarization

## Debugging Agents

```bash
# Enable trace logging
aletheia session open -vv

# View agent prompts and responses
# Check logs in session directory

# Test agent in isolation
python -m aletheia.agents.my_agent
```

## Agent Lifecycle

1. **Initialization**: Load plugins, instructions, skills
2. **Message Processing**: Receive user input
3. **Tool Execution**: Call plugin tools as needed
4. **LLM Reasoning**: Generate response using LLM
5. **Response Formatting**: Structure output
6. **State Persistence**: Save conversation history
