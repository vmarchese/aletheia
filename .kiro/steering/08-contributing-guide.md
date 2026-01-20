---
inclusion: always
---

# Contributing Guide

## Getting Started

### Fork and Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/YOUR_USERNAME/aletheia.git
cd aletheia

# Add upstream remote
git remote add upstream https://github.com/ORIGINAL_OWNER/aletheia.git
```

### Setup Development Environment

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv --python python3.12
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt

# Install in editable mode
uv pip install -e .

# Verify installation
aletheia version
```

## Development Workflow

### Create Feature Branch

```bash
# Update main branch
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/bug-description
```

### Make Changes

1. **Write Code**: Implement your feature or fix
2. **Add Tests**: Write tests for new functionality
3. **Update Documentation**: Update README.md or add docs
4. **Follow Style Guide**: Use Black and Ruff for formatting

### Pre-Commit Checks

Run these commands before committing:

```bash
# 1. Format code
black .

# 2. Lint and fix issues
ruff check --fix .

# 3. Type check
mypy .

# 4. Run tests
pytest

# 5. Check coverage
pytest --cov=aletheia --cov-report=term-missing
```

### Commit Changes

```bash
# Stage changes
git add .

# Commit with conventional commit message
git commit -m "feat: add new agent for X"
git commit -m "fix: resolve issue with Y"
git commit -m "docs: update configuration guide"
git commit -m "test: add tests for Z"
git commit -m "refactor: simplify plugin loader"
```

### Conventional Commit Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements

**Examples**:
```bash
feat(agents): add timeline agent for incident tracking
fix(encryption): resolve key derivation issue
docs(readme): update installation instructions
test(plugins): add unit tests for AWS plugin
refactor(config): simplify configuration loading
```

### Push Changes

```bash
# Push to your fork
git push origin feature/your-feature-name
```

### Create Pull Request

1. Go to GitHub and create a Pull Request
2. Fill in the PR template
3. Link related issues
4. Request review from maintainers

## Pull Request Guidelines

### PR Title

Use conventional commit format:
```
feat: add support for GCP monitoring
fix: resolve session encryption bug
docs: improve agent development guide
```

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to change)
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally
- [ ] Coverage maintained or improved

## Related Issues
Closes #123
Related to #456
```

### Review Process

1. **Automated Checks**: CI/CD runs tests and linting
2. **Code Review**: Maintainers review code
3. **Address Feedback**: Make requested changes
4. **Approval**: Get approval from maintainers
5. **Merge**: Maintainer merges PR

## Code Review Guidelines

### As a Reviewer

**What to Look For**:
- Code correctness and logic
- Test coverage
- Security issues
- Performance concerns
- Code style and readability
- Documentation completeness

**How to Review**:
- Be constructive and respectful
- Explain reasoning for suggestions
- Approve when satisfied
- Request changes if needed

**Review Checklist**:
- [ ] Code is correct and handles edge cases
- [ ] Tests are comprehensive
- [ ] No security vulnerabilities
- [ ] Performance is acceptable
- [ ] Code is readable and maintainable
- [ ] Documentation is clear
- [ ] No breaking changes (or properly documented)

### As a Contributor

**Responding to Feedback**:
- Address all comments
- Ask questions if unclear
- Make requested changes
- Mark conversations as resolved
- Thank reviewers

**Updating PR**:
```bash
# Make changes based on feedback
git add .
git commit -m "address review feedback"
git push origin feature/your-feature-name
```

## Contribution Types

### Bug Fixes

1. **Identify Bug**: Reproduce the issue
2. **Create Issue**: Document the bug (if not exists)
3. **Write Test**: Add failing test demonstrating bug
4. **Fix Bug**: Implement fix
5. **Verify**: Ensure test passes
6. **Submit PR**: Reference issue in PR

### New Features

1. **Discuss**: Open issue to discuss feature
2. **Design**: Plan implementation approach
3. **Implement**: Write code with tests
4. **Document**: Update docs and examples
5. **Submit PR**: Include comprehensive description

### Documentation

1. **Identify Gap**: Find missing or unclear docs
2. **Write/Update**: Improve documentation
3. **Review**: Check for accuracy and clarity
4. **Submit PR**: Documentation-only PRs welcome

### Tests

1. **Find Coverage Gap**: Identify untested code
2. **Write Tests**: Add unit/integration tests
3. **Verify**: Ensure tests pass
4. **Submit PR**: Test-only PRs welcome

## Adding New Components

### Adding a New Agent

1. **Create Agent Directory**:
   ```bash
   mkdir -p aletheia/agents/my_agent
   touch aletheia/agents/my_agent/__init__.py
   touch aletheia/agents/my_agent/my_agent.py
   ```

2. **Implement Agent**:
   ```python
   from aletheia.agents.base import BaseAgent
   
   class MyAgent(BaseAgent):
       def __init__(self, **kwargs):
           super().__init__(
               name="my_agent",
               description="Agent description",
               **kwargs
           )
   ```

3. **Register Agent**:
   ```python
   # In aletheia/agents/__init__.py
   from aletheia.agents.my_agent.my_agent import MyAgent
   
   AVAILABLE_AGENTS = {
       # ...
       "my_agent": MyAgent,
   }
   ```

4. **Add Tests**:
   ```bash
   touch tests/agents/test_my_agent.py
   ```

5. **Update Documentation**:
   - Add to README.md agent list
   - Create agent documentation

### Adding a New Plugin

1. **Create Plugin Directory**:
   ```bash
   mkdir -p aletheia/plugins/my_plugin
   touch aletheia/plugins/my_plugin/__init__.py
   touch aletheia/plugins/my_plugin/my_plugin.py
   ```

2. **Implement Plugin**:
   ```python
   from aletheia.plugins.base import BasePlugin
   
   class MyPlugin(BasePlugin):
       def __init__(self):
           super().__init__(name="my_plugin")
       
       def get_tools(self):
           return [...]
       
       async def execute_tool(self, tool_name, parameters):
           ...
   ```

3. **Add Tests**:
   ```bash
   touch tests/plugins/test_my_plugin.py
   ```

4. **Document Tools**: Add clear docstrings

## Code Style Guidelines

### Python Style

```python
# Good: Clear, typed, documented
async def fetch_logs(
    namespace: str,
    pod_name: str,
    tail_lines: int = 100
) -> str:
    """
    Fetch logs from a Kubernetes pod.
    
    Args:
        namespace: Kubernetes namespace
        pod_name: Name of the pod
        tail_lines: Number of lines to fetch
        
    Returns:
        Pod logs as string
        
    Raises:
        RuntimeError: If kubectl command fails
    """
    validate_input(namespace, pattern=r'^[a-z0-9-]+$')
    validate_input(pod_name, pattern=r'^[a-z0-9-]+$')
    
    cmd = ["kubectl", "logs", "-n", namespace, pod_name, f"--tail={tail_lines}"]
    return await execute_command(cmd)

# Bad: No types, no docs, unsafe
def fetch_logs(namespace, pod_name, tail_lines=100):
    cmd = f"kubectl logs -n {namespace} {pod_name} --tail={tail_lines}"
    return os.popen(cmd).read()
```

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `KubernetesAgent`)
- **Functions**: `snake_case` (e.g., `fetch_logs`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)
- **Private**: `_leading_underscore` (e.g., `_internal_method`)

### Import Organization

```python
# Standard library
import os
import sys
from typing import Any, Dict, List

# Third-party
import yaml
from rich.console import Console

# Local
from aletheia.agents.base import BaseAgent
from aletheia.config import Config
```

## Testing Guidelines

### Test Coverage Requirements

- **New Code**: 90% coverage minimum
- **Bug Fixes**: Add test demonstrating bug
- **Features**: Comprehensive test suite
- **Critical Code**: 100% coverage (encryption, auth)

### Writing Good Tests

```python
# Good: Clear, focused, well-named
@pytest.mark.asyncio
async def test_kubernetes_plugin_lists_pods_in_namespace():
    """Test that plugin correctly lists pods in specified namespace."""
    plugin = KubernetesPlugin()
    
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="pod-1\npod-2\n"
        )
        
        result = await plugin.list_pods(namespace="default")
        
        assert "pod-1" in result
        assert "pod-2" in result
        mock_run.assert_called_once()

# Bad: Unclear, tests multiple things
def test_plugin():
    plugin = KubernetesPlugin()
    result = plugin.list_pods("default")
    assert result
```

## Documentation Guidelines

### Code Documentation

```python
class MyAgent(BaseAgent):
    """
    Brief one-line description.
    
    Longer description explaining what this agent does,
    when to use it, and any important considerations.
    
    Attributes:
        name: Agent name
        description: Agent description
        
    Example:
        >>> agent = MyAgent()
        >>> result = await agent.process_message("query")
    """
```

### README Updates

When adding features, update:
- Feature list
- Usage examples
- Configuration options
- Installation requirements

### Steering Documents

For significant features, consider adding:
- Usage guide
- Best practices
- Common patterns
- Troubleshooting tips

## Release Process

### Version Numbering

Follow Semantic Versioning (SemVer):
- **Major**: Breaking changes (1.0.0 → 2.0.0)
- **Minor**: New features (1.0.0 → 1.1.0)
- **Patch**: Bug fixes (1.0.0 → 1.0.1)

### Changelog

Update CHANGELOG.md with:
- Version number and date
- Added features
- Changed behavior
- Deprecated features
- Removed features
- Fixed bugs
- Security updates

## Community Guidelines

### Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Provide constructive feedback
- Focus on the code, not the person
- Assume good intentions

### Communication

- **Issues**: Bug reports and feature requests
- **Discussions**: Questions and ideas
- **Pull Requests**: Code contributions
- **Reviews**: Constructive feedback

### Getting Help

- Check documentation first
- Search existing issues
- Ask in discussions
- Provide context and details
- Be patient and respectful

## Recognition

Contributors are recognized through:
- Git commit history
- CONTRIBUTORS.md file
- Release notes
- Project documentation

Thank you for contributing to Aletheia!
