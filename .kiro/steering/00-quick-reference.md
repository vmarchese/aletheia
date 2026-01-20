---
inclusion: always
---

# Quick Reference Guide

## Essential Commands

### Environment Setup

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create and activate virtual environment
uv venv --python python3.12
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt

# Install in editable mode
uv pip install -e .
```

### Code Quality

```bash
# Format code
black .

# Lint code
ruff check --fix .

# Type check
mypy .

# Run tests
pytest

# Run tests with coverage
pytest --cov=aletheia --cov-report=html

# Run functional tests
./run_test.sh
```

### Aletheia CLI

```bash
# Start session
aletheia session open
aletheia session open --name incident-123
aletheia session open -v          # Verbose
aletheia session open -vv         # Very verbose
aletheia session open --unsafe    # Plaintext (dev only)

# Manage sessions
aletheia session list
aletheia session view <session-id>
aletheia session timeline <session-id>
aletheia session delete <session-id>
aletheia session export <session-id> --output file.enc

# Knowledge base
aletheia knowledge add <doc-id> <file.md>
aletheia knowledge list
aletheia knowledge delete <doc-id>

# Version
aletheia version
```

### In-Session Commands

```bash
/help       # Show available commands
/version    # Show version
/info       # Show configuration
/agents     # List available agents
/cost       # Show token usage and cost
```

## Project Structure

```
aletheia/
├── agents/              # Agent implementations
│   ├── base.py         # Base agent class
│   ├── orchestrator/   # Orchestrator agent
│   ├── kubernetes_data_fetcher/
│   ├── aws/
│   └── ...
├── plugins/            # Plugin implementations
│   ├── base.py        # Base plugin class
│   ├── kubernetes/
│   ├── aws/
│   └── ...
├── llm/               # LLM integration
├── knowledge/         # Knowledge base
├── mcp/              # MCP support
├── utils/            # Utilities
├── config.py         # Configuration
├── session.py        # Session management
├── cli.py            # CLI interface
└── api.py            # Web API

tests/                # Test suite
├── agents/
├── plugins/
└── ...

.kiro/steering/       # Development guides
```

## Configuration

### Environment Variables

```bash
# LLM Configuration
export ALETHEIA_LLM_DEFAULT_MODEL=gpt-4o
export ALETHEIA_LLM_TEMPERATURE=0.2
export ALETHEIA_CODE_ANALYZER=claude

# OpenAI
export ALETHEIA_OPENAI_API_KEY=sk-...

# Azure OpenAI
export AZURE_OPENAI_API_KEY=key
export AZURE_OPENAI_ENDPOINT=https://...
export AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4o

# Ollama
export ALETHEIA_OPENAI_API_KEY=none
export ALETHEIA_OPENAI_ENDPOINT=http://127.0.0.1:11434/v1
export ALETHEIA_OPENAI_MODEL=llama3:70b

# AWS Bedrock
export AWS_PROFILE=default
export AWS_REGION=us-east-1

# Directories
export ALETHEIA_SKILLS_DIRECTORY=/path/to/skills
export ALETHEIA_CUSTOM_INSTRUCTIONS_DIR=/path/to/instructions
```

### Config File Locations

- **Linux**: `~/.config/aletheia/config.yaml`
- **macOS**: `~/Library/Application Support/aletheia/config.yaml`
- **Windows**: `%LOCALAPPDATA%\aletheia\config.yaml`

## Common Patterns

### Creating a New Agent

```python
from typing import Any
from aletheia.agents.base import BaseAgent
from aletheia.plugins.my_plugin import MyPlugin

class MyAgent(BaseAgent):
    """Agent description."""
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            name="my_agent",
            description="What this agent does",
            **kwargs
        )
        self.add_plugin(MyPlugin())
```

### Creating a New Plugin

```python
from typing import Any, Dict, List
from aletheia.plugins.base import BasePlugin

class MyPlugin(BasePlugin):
    """Plugin description."""
    
    def __init__(self) -> None:
        super().__init__(name="my_plugin")
    
    def get_tools(self) -> List[Dict[str, Any]]:
        return [{
            "name": "tool_name",
            "description": "What this tool does",
            "parameters": {
                "type": "object",
                "properties": {
                    "param": {
                        "type": "string",
                        "description": "Parameter description"
                    }
                },
                "required": ["param"]
            }
        }]
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Any:
        if tool_name == "tool_name":
            return await self._tool_name(**parameters)
        raise ValueError(f"Unknown tool: {tool_name}")
    
    async def _tool_name(self, param: str) -> Dict[str, Any]:
        """Tool implementation."""
        return {"result": "value"}
```

### Writing Tests

```python
import pytest
from unittest.mock import Mock, patch

@pytest.mark.asyncio
async def test_agent_functionality():
    """Test agent does what it should."""
    from aletheia.agents.my_agent import MyAgent
    
    agent = MyAgent()
    
    with patch('external.dependency') as mock_dep:
        mock_dep.return_value = "expected"
        
        result = await agent.process_message("test")
        
        assert "expected" in result
        mock_dep.assert_called_once()
```

## Troubleshooting Quick Fixes

### Module Not Found
```bash
source .venv/bin/activate
uv pip install -e .
```

### Config Not Loading
```bash
mkdir -p ~/.config/aletheia
cp config.yaml.example ~/.config/aletheia/config.yaml
```

### API Key Issues
```bash
export ALETHEIA_OPENAI_API_KEY=sk-...
# Verify
echo $ALETHEIA_OPENAI_API_KEY
```

### Tests Failing
```bash
uv pip install -r requirements-dev.txt
pytest -v
```

### Type Errors
```bash
mypy .
# Fix type annotations or add type: ignore
```

### Import Errors
```bash
find . -type d -name __pycache__ -exec rm -rf {} +
uv pip install -e .
```

## Git Workflow

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes and commit
git add .
git commit -m "feat: add new feature"

# Run checks
black .
ruff check --fix .
mypy .
pytest

# Push and create PR
git push origin feature/my-feature
```

## Conventional Commits

```bash
feat: new feature
fix: bug fix
docs: documentation
test: tests
refactor: code refactoring
style: formatting
chore: maintenance
perf: performance
```

## Key Files

- `pyproject.toml` - Project configuration
- `requirements.txt` - Production dependencies
- `requirements-dev.txt` - Development dependencies
- `config.yaml.example` - Example configuration
- `.gitignore` - Git ignore rules
- `README.md` - Project documentation
- `AGENTS.md` - Agent development guide

## Important Directories

- `.venv/` - Virtual environment
- `.kiro/steering/` - Development guides
- `aletheia/` - Source code
- `tests/` - Test suite
- `htmlcov/` - Coverage reports
- `~/.config/aletheia/` - User configuration
- `~/.local/share/aletheia/` - User data

## Security Reminders

- Never commit API keys or credentials
- Use encrypted sessions in production
- Validate all user inputs
- Use parameterized commands
- Keep dependencies updated
- Use `--unsafe` only for development

## Performance Tips

- Use `gpt-4o-mini` for faster responses
- Reduce `llm_max_tokens` for speed
- Enable streaming when available
- Cache expensive operations
- Use async/await for I/O

## Documentation Links

- **Architecture**: `01-architecture.md`
- **Development**: `02-development-workflow.md`
- **Agents**: `03-agent-development.md`
- **Configuration**: `04-configuration-management.md`
- **Security**: `05-security-and-encryption.md`
- **Testing**: `06-testing-strategy.md`
- **Troubleshooting**: `07-troubleshooting-guide.md`
- **Contributing**: `08-contributing-guide.md`

## Getting Help

1. Check steering documents in `.kiro/steering/`
2. Review README.md
3. Search existing issues on GitHub
4. Check test files for examples
5. Enable verbose logging: `aletheia session open -vv`

## Quick Debugging

```bash
# Check configuration
python -c "from aletheia.config import Config; print(Config())"

# List agents
python -c "from aletheia.agents import AVAILABLE_AGENTS; print(list(AVAILABLE_AGENTS.keys()))"

# Test plugin
python -c "from aletheia.plugins.kubernetes import KubernetesPlugin; print(KubernetesPlugin().get_tools())"

# Check environment
env | grep ALETHEIA
```

## Coverage Goals

- Overall: 80% minimum
- New code: 90% minimum
- Critical paths: 100% (encryption, auth)
- Plugins: 85% minimum
- Utilities: 95% minimum

## Code Review Checklist

- [ ] Code is correct and handles edge cases
- [ ] Tests are comprehensive (90%+ coverage)
- [ ] No security vulnerabilities
- [ ] Type annotations complete
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
- [ ] Follows code style (Black, Ruff)
- [ ] Passes all checks (mypy, pytest)

## Release Checklist

- [ ] Version bumped (SemVer)
- [ ] CHANGELOG.md updated
- [ ] Tests passing
- [ ] Documentation updated
- [ ] No security issues
- [ ] Dependencies updated
- [ ] Migration guide (if breaking)

## Useful Python Snippets

```python
# Debug configuration
from aletheia.config import Config
config = Config()
print(config.model_dump_json(indent=2))

# Test agent
from aletheia.agents import get_agent
agent = get_agent("orchestrator")
print(agent.name, agent.description)

# List plugins
from aletheia.agents.kubernetes_data_fetcher import KubernetesAgent
agent = KubernetesAgent()
for plugin in agent.plugins:
    print(f"{plugin.name}: {[t['name'] for t in plugin.get_tools()]}")

# Test encryption
from aletheia.encryption import encrypt_data, decrypt_data, derive_key
import os
key = derive_key("password", os.urandom(32))
encrypted = encrypt_data("secret", key)
decrypted = decrypt_data(encrypted, key)
assert decrypted == "secret"
```

## Remember

- **Always activate virtual environment**: `source .venv/bin/activate`
- **Run pre-commit checks**: `black . && ruff check --fix . && mypy . && pytest`
- **Use type annotations**: All functions must be typed
- **Write tests**: 90% coverage for new code
- **Document code**: Clear docstrings for all public APIs
- **Security first**: Never commit secrets, validate inputs
- **Be respectful**: Follow code of conduct in all interactions
