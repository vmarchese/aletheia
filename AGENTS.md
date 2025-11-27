# Aletheia (ἀλήθεια)

> **Aletheia** (ἀλήθεια) — Ancient Greek for "truth" or "un-concealment": bringing what's hidden into the open.

Aletheia is a modular, AI-powered troubleshooting framework for SREs and system administrators. It orchestrates specialized LLM agents to collect and analyze observability data (logs, metrics, traces), inspect code, and generate actionable root cause hypotheses.

---

# Python Project Guidelines

When developing agents or contributing to Aletheia, please adhere to the following guidelines to ensure code quality and consistency.

## 1. Environment Management

Aletheia uses **[uv](https://github.com/astral-sh/uv)** for fast Python package management.

*   **Create Virtual Environment**: `uv venv --python python3.12`
*   **Install Dependencies**: `uv pip install -r requirements.txt`
*   **Install Dev Dependencies**: `uv pip install -r requirements-dev.txt`

## 2. Code Style & Formatting

We enforce a consistent code style using **Black** and **Ruff**.

*   **Formatter**: [Black](https://github.com/psf/black)
    *   Line length: 88 characters
    *   Target versions: py310, py311, py312
*   **Linter**: [Ruff](https://github.com/astral-sh/ruff)
    *   Used for import sorting (isort), pyflakes, pycodestyle, and more.
    *   Configuration is in `pyproject.toml`.

**Command to format code:**
```bash
black .
ruff check --fix .
```

## 3. Type Safety

All new code must be fully typed. We use **mypy** for static type checking.

*   **Strict Mode**: Enabled.
*   **Disallow Untyped Defs**: Enabled.

**Command to check types:**
```bash
mypy .
```

## 4. Testing

We use **pytest** for testing.

*   **Async Support**: `pytest-asyncio` is used for async tests.
*   **Coverage**: `pytest-cov` is configured to track coverage.

**Command to run tests:**
```bash
pytest
```

## 5. Development Workflow

Before submitting a Pull Request, ensure you have run the following:

1.  Format code: `black .`
2.  Lint code: `ruff check .`
3.  Check types: `mypy .`
4.  Run tests: `pytest`

# How to Add a New Agent to Aletheia

This guide outlines the process for implementing and registering a new agent in the Aletheia system.

## 1. Create Agent Directory

Create a new directory for your agent in `aletheia/agents/`. For example, if your agent is named `MyNewAgent`, create `aletheia/agents/my_new_agent/`.

```bash
mkdir aletheia/agents/my_new_agent
touch aletheia/agents/my_new_agent/__init__.py
```

## 2. Implement Agent Class

Create a python file for your agent (e.g., `aletheia/agents/my_new_agent/my_new_agent.py`).
Your agent class must inherit from `BaseAgent` defined in `aletheia/agents/base.py`.

```python
from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.config import Config

class MyNewAgent(BaseAgent):
    """Description of what MyNewAgent does."""

    def __init__(self,
                 name: str,
                 config: Config,
                 description: str,
                 session: Session,
                 scratchpad: Scratchpad):
        
        # Initialize any specific plugins or tools your agent needs
        plugins = [scratchpad] 
        # Add other plugins if needed

        # Load instructions (see step 3)
        # You can pass instructions directly or let BaseAgent load them
        # If passing directly, load them here. 
        # If using BaseAgent's loading mechanism, ensure instructions.yaml exists.
        
        instructions = "You are a helpful agent..." # Or load from file

        super().__init__(name=name,
                         description=description,
                         instructions=instructions,
                         session=session,
                         plugins=plugins)
```

## 3. Define Agent Instructions

Create an instruction file (YAML or Markdown) in your agent's directory.
If using `BaseAgent`'s default loading, create `instructions.yaml`.

Example `instructions.yaml`:
```yaml
agent:
  name: MyNewAgent
  identity: "You are an expert in ..."
  guidelines: "Always follow these rules..."
```

Or you can use a Markdown file and load it manually in `__init__` using `Loader`.

## 4. Register the Agent

To make the agent available to the system, you need to register it in `aletheia/cli.py`.

1.  Import your agent class in `aletheia/cli.py`.
    ```python
    from aletheia.agents.my_new_agent.my_new_agent import MyNewAgent
    ```

2.  Instantiate and add your agent to the `plugins` list in the `_build_plugins` function in `aletheia/cli.py`.

    ```python
    def _build_plugins(...):
        # ... existing agents ...

        my_new_agent = MyNewAgent(name="my_new_agent",
                                  config=config,
                                  description="Description for the Orchestrator to understand when to use this agent.",
                                  session=session,
                                  scratchpad=scratchpad)
        plugins.append(my_new_agent.agent.as_tool())

        return plugins
    ```

## 5. (Optional) Configuration

If your agent requires configuration settings, add them to `aletheia/config.py` and update `Config` class.

## Summary

1.  **Create Directory**: `aletheia/agents/<agent_name>/`
2.  **Implement Class**: Inherit from `BaseAgent`.
3.  **Add Instructions**: `instructions.yaml` or `.md`.
4.  **Register**: Add to `_build_plugins` in `aletheia/cli.py`.

