---
inclusion: always
---

# Troubleshooting Guide

## Common Issues and Solutions

### Environment and Setup Issues

#### Virtual Environment Not Activated

**Symptom**: Commands fail with "module not found" errors

**Solution**:
```bash
# Activate virtual environment
source .venv/bin/activate

# Verify activation (should show .venv path)
which python
```

#### uv Not Found

**Symptom**: `bash: uv: command not found`

**Solution**:
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Reload shell
source ~/.bashrc  # or ~/.zshrc

# Verify installation
uv --version
```

#### Dependency Installation Fails

**Symptom**: `uv pip install` fails with version conflicts

**Solution**:
```bash
# Clear cache and reinstall
rm -rf .venv
uv venv --python python3.12
source .venv/bin/activate
uv pip install -r requirements.txt --no-cache
```

### Configuration Issues

#### Config File Not Found

**Symptom**: Aletheia uses default values instead of config file

**Solution**:
```bash
# Check config file location
python -c "from platformdirs import user_config_dir; print(user_config_dir('aletheia'))"

# Create config directory if missing
mkdir -p ~/.config/aletheia

# Copy example config
cp config.yaml.example ~/.config/aletheia/config.yaml
```

#### Environment Variables Not Working

**Symptom**: Config values not loaded from environment

**Solution**:
```bash
# Ensure ALETHEIA_ prefix
export ALETHEIA_LLM_DEFAULT_MODEL=gpt-4o  # Correct
export LLM_DEFAULT_MODEL=gpt-4o           # Wrong

# Verify environment variable
echo $ALETHEIA_LLM_DEFAULT_MODEL

# Debug config loading
python -c "from aletheia.config import Config; c = Config(); print(c.llm_default_model)"
```

#### Invalid Configuration Values

**Symptom**: `ValueError: Invalid temperature` or similar

**Solution**:
```bash
# Check valid ranges
# Temperature: 0.0 - 1.0
# Timeout: > 0
# Tokens: > 0

# Fix in config.yaml
llm_temperature: 0.2  # Not 2.0
prometheus_timeout_seconds: 30  # Not -1
```

### LLM Provider Issues

#### OpenAI API Key Not Set

**Symptom**: `AuthenticationError: No API key provided`

**Solution**:
```bash
# Set API key
export ALETHEIA_OPENAI_API_KEY=sk-...

# Or in .env file
echo "ALETHEIA_OPENAI_API_KEY=sk-..." >> .env

# Verify
python -c "import os; print('Key set' if os.getenv('ALETHEIA_OPENAI_API_KEY') else 'Key missing')"
```

#### Azure OpenAI Connection Fails

**Symptom**: `Connection error` or `Invalid endpoint`

**Solution**:
```bash
# Verify all three required variables
export AZURE_OPENAI_API_KEY=your-key
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
export AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4o

# Test connection
python -c "
from openai import AzureOpenAI
import os
client = AzureOpenAI(
    api_key=os.getenv('AZURE_OPENAI_API_KEY'),
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
    api_version='2024-02-01'
)
print('Connection successful')
"
```

#### Ollama Not Responding

**Symptom**: `Connection refused` to localhost:11434

**Solution**:
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve

# Pull model if needed
ollama pull llama3:70b

# Configure Aletheia
export ALETHEIA_OPENAI_API_KEY=none
export ALETHEIA_OPENAI_ENDPOINT=http://127.0.0.1:11434/v1
export ALETHEIA_OPENAI_MODEL=llama3:70b
```

### Session Issues

#### Session Creation Fails

**Symptom**: `PermissionError` or `FileNotFoundError`

**Solution**:
```bash
# Check session directory permissions
ls -la ~/.local/share/aletheia/sessions/

# Create directory if missing
mkdir -p ~/.local/share/aletheia/sessions

# Fix permissions
chmod 700 ~/.local/share/aletheia/sessions
```

#### Encryption Password Forgotten

**Symptom**: Cannot decrypt session data

**Solution**:
```bash
# Unfortunately, encrypted sessions cannot be recovered without password
# Prevention: Use --unsafe for development sessions
aletheia session open --unsafe

# Or use keychain for production
aletheia config set prometheus_credentials_type keychain
```

#### Session List Empty

**Symptom**: `aletheia session list` shows no sessions

**Solution**:
```bash
# Check session directory
ls ~/.local/share/aletheia/sessions/

# Verify data directory setting
python -c "from platformdirs import user_data_dir; print(user_data_dir('aletheia'))"

# Check for custom data directory
echo $ALETHEIA_DATA_DIR
```

### Agent Issues

#### Agent Not Found

**Symptom**: `Agent 'xyz' not found`

**Solution**:
```bash
# List available agents
aletheia session open
/agents

# Check agent registration
python -c "from aletheia.agents import AVAILABLE_AGENTS; print(list(AVAILABLE_AGENTS.keys()))"

# Verify agent import
python -c "from aletheia.agents.kubernetes_data_fetcher import KubernetesAgent; print('OK')"
```

#### Agent Timeout

**Symptom**: Agent takes too long to respond

**Solution**:
```bash
# Increase timeout in config
llm_timeout_seconds: 120

# Or use faster model
llm_default_model: gpt-4o-mini

# Check for network issues
curl -I https://api.openai.com

# Enable verbose logging to see where it hangs
aletheia session open -vv
```

#### Tool Execution Fails

**Symptom**: `Tool 'xyz' failed to execute`

**Solution**:
```bash
# Check if required CLI tools are installed
which kubectl  # For Kubernetes agent
which aws      # For AWS agent
which az       # For Azure agent

# Verify credentials
kubectl get pods  # Test kubectl access
aws sts get-caller-identity  # Test AWS access

# Check tool permissions
ls -la $(which kubectl)
```

### Plugin Issues

#### Plugin Import Error

**Symptom**: `ModuleNotFoundError: No module named 'aletheia.plugins.xyz'`

**Solution**:
```bash
# Verify plugin exists
ls aletheia/plugins/xyz/

# Check __init__.py exists
ls aletheia/plugins/xyz/__init__.py

# Reinstall in editable mode
uv pip install -e .

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
```

#### Plugin Tool Not Available

**Symptom**: Agent says tool is not available

**Solution**:
```python
# Debug plugin registration
from aletheia.agents.kubernetes_data_fetcher import KubernetesAgent
agent = KubernetesAgent()
print([p.name for p in agent.plugins])
print([t['name'] for p in agent.plugins for t in p.get_tools()])
```

### Skills Issues

#### Skill Not Loading

**Symptom**: Skill not found or not executed

**Solution**:
```bash
# Check skills directory
echo $ALETHEIA_SKILLS_DIRECTORY
ls -la $ALETHEIA_SKILLS_DIRECTORY

# Verify skill structure
ls $ALETHEIA_SKILLS_DIRECTORY/agent_name/skill_name/instructions.yaml

# Check YAML syntax
python -c "
import yaml
with open('path/to/instructions.yaml') as f:
    print(yaml.safe_load(f))
"
```

#### Script Execution Fails

**Symptom**: Skill script doesn't run

**Solution**:
```bash
# Check Docker is running (required for script execution)
docker ps

# Build script executor image
cd aletheia-script-executor
docker build -t aletheia:latest .

# Test script manually
docker run --rm -e MY_VAR=test aletheia:latest python /scripts/myscript.py
```

### Knowledge Base Issues

#### ChromaDB Connection Error

**Symptom**: `Connection refused` or ChromaDB errors

**Solution**:
```bash
# Check ChromaDB directory
ls -la .chroma/

# Remove corrupted database
rm -rf .chroma/
# Database will be recreated on next use

# Verify ChromaDB installation
python -c "import chromadb; print(chromadb.__version__)"
```

#### Document Not Found

**Symptom**: Added document not appearing in searches

**Solution**:
```bash
# List all documents
aletheia knowledge list

# Re-add document
aletheia knowledge delete doc-id
aletheia knowledge add doc-id /path/to/doc.md

# Check document content
python -c "
from aletheia.knowledge import KnowledgeBase
kb = KnowledgeBase()
docs = kb.list_documents()
print(docs)
"
```

### Testing Issues

#### Tests Fail with Import Errors

**Symptom**: `ModuleNotFoundError` during test execution

**Solution**:
```bash
# Install in editable mode
uv pip install -e .

# Install test dependencies
uv pip install -r requirements-dev.txt

# Run from project root
cd /path/to/aletheia
pytest
```

#### Async Tests Fail

**Symptom**: `RuntimeError: Event loop is closed`

**Solution**:
```python
# Ensure pytest-asyncio is installed
# pip install pytest-asyncio

# Mark async tests properly
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
    assert result is not None
```

#### Coverage Report Not Generated

**Symptom**: No coverage data after running tests

**Solution**:
```bash
# Install coverage plugin
uv pip install pytest-cov

# Run with coverage
pytest --cov=aletheia --cov-report=html

# Check coverage file
ls .coverage htmlcov/
```

### Type Checking Issues

#### mypy Errors on Third-Party Libraries

**Symptom**: `error: Skipping analyzing 'module': module not installed`

**Solution**:
```bash
# Install type stubs
uv pip install types-pyyaml types-requests

# Or ignore missing imports in pyproject.toml
[[tool.mypy.overrides]]
module = ["problematic_module.*"]
ignore_missing_imports = true
```

#### Strict Type Checking Failures

**Symptom**: Many type errors in existing code

**Solution**:
```python
# Add type annotations gradually
def function(param: str) -> str:  # Add types
    return param

# Use type: ignore for complex cases (sparingly)
result = complex_operation()  # type: ignore[misc]

# Use cast for type narrowing
from typing import cast
value = cast(str, maybe_string)
```

### Performance Issues

#### Slow Agent Response

**Symptom**: Agent takes minutes to respond

**Solution**:
```bash
# Use faster model
export ALETHEIA_LLM_DEFAULT_MODEL=gpt-4o-mini

# Reduce max tokens
export ALETHEIA_LLM_MAX_TOKENS=2000

# Enable streaming (if supported)
export ALETHEIA_ENABLE_STREAMING=true

# Check network latency
ping api.openai.com
```

#### High Memory Usage

**Symptom**: Python process uses excessive memory

**Solution**:
```bash
# Profile memory usage
python -m memory_profiler aletheia/cli.py

# Limit conversation history
export ALETHEIA_MAX_HISTORY_MESSAGES=50

# Clear old sessions
aletheia session delete <old-session-id>
```

## Debugging Techniques

### Enable Verbose Logging

```bash
# Show external commands
aletheia session open -v

# Show everything (prompts, responses, traces)
aletheia session open -vv
```

### Python Debugging

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use ipdb for better experience
import ipdb; ipdb.set_trace()

# Print debug info
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Component Status

```bash
# Test configuration
python -c "from aletheia.config import Config; print(Config())"

# Test agent loading
python -c "from aletheia.agents import get_agent; print(get_agent('orchestrator'))"

# Test plugin loading
python -c "from aletheia.plugins.kubernetes import KubernetesPlugin; print(KubernetesPlugin().get_tools())"
```

### Network Debugging

```bash
# Test API connectivity
curl -I https://api.openai.com

# Test with proxy
export HTTPS_PROXY=http://proxy:8080
curl -I https://api.openai.com

# Check DNS resolution
nslookup api.openai.com
```

## Getting Help

### Check Logs

```bash
# Session logs
cat ~/.local/share/aletheia/sessions/<session-id>/session.log

# System logs (if configured)
tail -f /var/log/aletheia/aletheia.log
```

### Collect Debug Information

```bash
# System info
python --version
uv --version
which python

# Aletheia version
aletheia version

# Configuration
aletheia config show

# Environment
env | grep ALETHEIA
```

### Report Issues

When reporting issues, include:
1. Aletheia version (`aletheia version`)
2. Python version (`python --version`)
3. Operating system
4. Error message and stack trace
5. Steps to reproduce
6. Configuration (sanitized, no secrets)
7. Relevant logs

### Community Resources

- GitHub Issues: Report bugs and feature requests
- Documentation: Check README.md and steering docs
- Examples: Review examples/ directory
- Tests: Look at tests/ for usage examples
