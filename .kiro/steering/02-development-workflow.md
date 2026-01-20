---
inclusion: always
---

# Development Workflow

## Environment Setup

### Prerequisites
- Python 3.12 (required)
- [uv](https://github.com/astral-sh/uv) for package management
- Docker (optional, for script execution feature)

### Initial Setup

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone <repository-url>
cd aletheia

# Create virtual environment
uv venv --python python3.12

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt

# Install in editable mode
uv pip install -e .
```

## Pre-Commit Checklist

Before committing code, run these commands in order:

```bash
# 1. Format code
black .

# 2. Lint and auto-fix
ruff check --fix .

# 3. Type check
mypy .

# 4. Run tests
pytest

# 5. Check coverage
pytest --cov=aletheia --cov-report=term-missing
```

## Code Quality Standards

### Formatting
- **Black**: Line length 88, targets py310/py311/py312
- Run `black .` before committing
- Configuration in `pyproject.toml`

### Linting
- **Ruff**: Fast Python linter
- Checks: pycodestyle, pyflakes, isort, flake8-comprehensions, flake8-bugbear, pyupgrade
- Run `ruff check --fix .` to auto-fix issues
- Configuration in `pyproject.toml`

### Type Checking
- **mypy**: Strict mode enabled
- All functions must have type annotations
- No untyped definitions allowed
- Run `mypy .` to check types
- Configuration in `pyproject.toml`

### Testing
- **pytest**: Test framework
- **pytest-asyncio**: For async tests
- **pytest-cov**: Coverage tracking
- Minimum coverage target: 80%
- Test files: `tests/test_*.py`
- Run `pytest` or `pytest -v` for verbose output

## Common Development Tasks

### Adding a New Agent

1. Create agent directory: `aletheia/agents/<agent_name>/`
2. Create agent class extending `BaseAgent`
3. Create corresponding plugin in `aletheia/plugins/<agent_name>/`
4. Add agent registration in `aletheia/agents/__init__.py`
5. Write tests in `tests/agents/test_<agent_name>.py`
6. Add documentation to agent's docstring

### Adding a New Plugin

1. Create plugin file: `aletheia/plugins/<plugin_name>/<plugin_name>_plugin.py`
2. Extend `BasePlugin` class
3. Implement tool methods with proper type hints
4. Add plugin to agent's plugin list
5. Write unit tests in `tests/plugins/test_<plugin_name>.py`
6. Document tool methods with clear docstrings

### Adding a New Skill

1. Create skill directory: `<skills_dir>/<agent_name>/<skill_name>/`
2. Create `SKILL.md` or `instructions.yaml` file
3. Define skill name, description, and instructions
4. Add any required scripts to `scripts/` subdirectory
5. Test skill execution with agent

### Modifying Configuration

1. Update `aletheia/config.py` with new config fields
2. Add corresponding environment variable support
3. Update `config.yaml.example` with new options
4. Document in README.md configuration section
5. Add validation if needed

## Testing Guidelines

### Unit Tests
- Test individual functions and methods
- Mock external dependencies
- Use fixtures for common setup
- Aim for 100% coverage of new code

### Integration Tests
- Test agent-plugin interactions
- Test CLI commands
- Test session management
- Use temporary directories for file operations

### Async Tests
- Mark with `@pytest.mark.asyncio`
- Use `pytest-asyncio` fixtures
- Test concurrent operations

### Test Organization
```
tests/
├── agents/          # Agent tests
├── plugins/         # Plugin tests
├── utils/           # Utility tests
├── test_cli.py      # CLI tests
├── test_config.py   # Configuration tests
└── conftest.py      # Shared fixtures
```

## Debugging

### Enable Verbose Logging
```bash
# Show all external commands
aletheia session open -v

# Show prompts and full details
aletheia session open -vv
```

### Python Debugging
```python
# Add breakpoints
import pdb; pdb.set_trace()

# Or use ipdb for better experience
import ipdb; ipdb.set_trace()
```

### Testing Individual Components
```bash
# Test specific file
pytest tests/test_config.py

# Test specific function
pytest tests/test_config.py::test_config_loading

# Run with print statements
pytest -s tests/test_config.py
```

## Git Workflow

### Branch Naming
- Feature: `feature/<description>`
- Bug fix: `fix/<description>`
- Documentation: `docs/<description>`
- Refactor: `refactor/<description>`

### Commit Messages
- Use conventional commits format
- Examples:
  - `feat: add Azure agent support`
  - `fix: resolve nil pointer in feature check`
  - `docs: update configuration guide`
  - `test: add tests for session encryption`
  - `refactor: simplify plugin loader`

### Pull Request Process
1. Create feature branch from `main`
2. Make changes with clear commits
3. Run pre-commit checklist
4. Push branch and create PR
5. Address review comments
6. Squash and merge when approved

## Performance Considerations

- Use async/await for I/O operations
- Cache expensive computations
- Limit LLM token usage where possible
- Use streaming for large responses
- Profile code with `cProfile` if needed

## Security Considerations

- Never commit credentials or API keys
- Use environment variables for secrets
- Encrypt sensitive session data
- Validate all user inputs
- Use secure credential storage (keychain, encrypted files)
