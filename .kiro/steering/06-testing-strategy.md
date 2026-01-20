---
inclusion: always
---

# Testing Strategy

## Testing Philosophy

Aletheia uses a comprehensive testing approach:
- **Unit Tests**: Test individual functions and classes
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows
- **Mock External Dependencies**: Avoid real API calls in tests

## Test Organization

```
tests/
├── agents/                    # Agent tests
│   ├── test_orchestrator.py
│   ├── test_kubernetes.py
│   └── test_aws.py
├── plugins/                   # Plugin tests
│   ├── test_kubernetes_plugin.py
│   └── test_aws_plugin.py
├── utils/                     # Utility tests
│   ├── test_encryption.py
│   └── test_validation.py
├── test_cli.py               # CLI tests
├── test_config.py            # Configuration tests
├── test_session.py           # Session management tests
└── conftest.py               # Shared fixtures
```

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_config.py

# Run specific test function
pytest tests/test_config.py::test_config_loading

# Run tests matching pattern
pytest -k "test_agent"
```

### Coverage Reports

```bash
# Run with coverage
pytest --cov=aletheia

# Generate HTML coverage report
pytest --cov=aletheia --cov-report=html

# View coverage report
open htmlcov/index.html

# Generate XML coverage (for CI)
pytest --cov=aletheia --cov-report=xml
```

### Test Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Run async tests
pytest -m asyncio
```

## Writing Unit Tests

### Basic Test Structure

```python
import pytest
from aletheia.config import Config

def test_config_default_values():
    """Test that config has correct default values."""
    config = Config()
    
    assert config.llm_default_model == "gpt-4o"
    assert config.llm_temperature == 0.2
    assert config.cost_per_input_token == 0.0

def test_config_from_env(monkeypatch):
    """Test config loading from environment variables."""
    monkeypatch.setenv("ALETHEIA_LLM_DEFAULT_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("ALETHEIA_LLM_TEMPERATURE", "0.5")
    
    config = Config()
    
    assert config.llm_default_model == "gpt-4o-mini"
    assert config.llm_temperature == 0.5
```

### Testing with Fixtures

```python
# conftest.py
import pytest
from aletheia.config import Config

@pytest.fixture
def test_config():
    """Provide test configuration."""
    return Config(
        llm_default_model="gpt-4o-mini",
        llm_temperature=0.2,
        temp_folder="/tmp/aletheia-test"
    )

@pytest.fixture
def temp_session_dir(tmp_path):
    """Provide temporary session directory."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    return session_dir

# test_session.py
def test_session_creation(test_config, temp_session_dir):
    """Test session creation."""
    from aletheia.session import Session
    
    session = Session(
        name="test-session",
        config=test_config,
        session_dir=temp_session_dir
    )
    
    assert session.name == "test-session"
    assert session.session_dir.exists()
```

### Mocking External Dependencies

```python
import pytest
from unittest.mock import Mock, patch, AsyncMock

@pytest.mark.asyncio
async def test_kubernetes_plugin_list_pods():
    """Test listing Kubernetes pods."""
    from aletheia.plugins.kubernetes import KubernetesPlugin
    
    plugin = KubernetesPlugin()
    
    # Mock kubectl command
    with patch('aletheia.utils.command.execute_command') as mock_exec:
        mock_exec.return_value = """
        NAME                    READY   STATUS
        pod-1                   1/1     Running
        pod-2                   0/1     Pending
        """
        
        result = await plugin.list_pods(namespace="default")
        
        assert "pod-1" in result
        assert "pod-2" in result
        mock_exec.assert_called_once()

@pytest.mark.asyncio
async def test_aws_plugin_with_boto3_mock():
    """Test AWS plugin with mocked boto3."""
    from aletheia.plugins.aws import AWSPlugin
    
    plugin = AWSPlugin()
    
    # Mock boto3 client
    with patch('boto3.client') as mock_boto3:
        mock_ec2 = Mock()
        mock_ec2.describe_instances.return_value = {
            'Reservations': [
                {
                    'Instances': [
                        {'InstanceId': 'i-123', 'State': {'Name': 'running'}}
                    ]
                }
            ]
        }
        mock_boto3.return_value = mock_ec2
        
        result = await plugin.list_instances()
        
        assert 'i-123' in result
        mock_ec2.describe_instances.assert_called_once()
```

## Testing Async Code

### Async Test Fixtures

```python
import pytest
import asyncio

@pytest.fixture
async def async_client():
    """Provide async HTTP client."""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        yield session

@pytest.mark.asyncio
async def test_async_operation(async_client):
    """Test async operation."""
    result = await some_async_function(async_client)
    assert result is not None
```

### Testing Concurrent Operations

```python
@pytest.mark.asyncio
async def test_concurrent_agent_execution():
    """Test multiple agents running concurrently."""
    from aletheia.agents import get_agent
    
    agent1 = get_agent("kubernetes_data_fetcher")
    agent2 = get_agent("aws")
    
    # Run agents concurrently
    results = await asyncio.gather(
        agent1.process_message("list pods"),
        agent2.process_message("list instances")
    )
    
    assert len(results) == 2
    assert all(r is not None for r in results)
```

## Integration Tests

### Testing Agent-Plugin Integration

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_with_real_plugin():
    """Test agent with actual plugin execution."""
    from aletheia.agents.kubernetes_data_fetcher import KubernetesAgent
    
    agent = KubernetesAgent()
    
    # Mock only external commands, not plugin logic
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="pod-1\npod-2\n"
        )
        
        response = await agent.process_message("list pods in default namespace")
        
        assert "pod-1" in response or "pod-2" in response
```

### Testing CLI Commands

```python
from typer.testing import CliRunner
from aletheia.cli import app

runner = CliRunner()

def test_cli_version():
    """Test version command."""
    result = runner.invoke(app, ["version"])
    
    assert result.exit_code == 0
    assert "Aletheia" in result.stdout

def test_cli_session_list():
    """Test session list command."""
    result = runner.invoke(app, ["session", "list"])
    
    assert result.exit_code == 0
```

## Test Data Management

### Using Test Fixtures

```python
# tests/fixtures/sample_logs.txt
2024-01-19 10:00:00 ERROR Failed to connect to database
2024-01-19 10:00:01 WARN Retrying connection
2024-01-19 10:00:02 INFO Connection established

# test_log_parser.py
import pytest
from pathlib import Path

@pytest.fixture
def sample_log_file():
    """Provide sample log file."""
    return Path(__file__).parent / "fixtures" / "sample_logs.txt"

def test_log_parsing(sample_log_file):
    """Test log file parsing."""
    from aletheia.plugins.log_file import LogFilePlugin
    
    plugin = LogFilePlugin()
    result = plugin.parse_log_file(str(sample_log_file))
    
    assert "ERROR" in result
    assert "database" in result
```

### Generating Test Data

```python
@pytest.fixture
def sample_kubernetes_pods():
    """Generate sample Kubernetes pod data."""
    return [
        {
            "name": "pod-1",
            "namespace": "default",
            "status": "Running",
            "containers": ["app"]
        },
        {
            "name": "pod-2",
            "namespace": "default",
            "status": "Pending",
            "containers": ["app", "sidecar"]
        }
    ]

def test_pod_filtering(sample_kubernetes_pods):
    """Test filtering pods by status."""
    from aletheia.utils.kubernetes import filter_pods_by_status
    
    running_pods = filter_pods_by_status(sample_kubernetes_pods, "Running")
    
    assert len(running_pods) == 1
    assert running_pods[0]["name"] == "pod-1"
```

## Testing Error Handling

### Testing Exceptions

```python
import pytest

def test_invalid_config_raises_error():
    """Test that invalid config raises ValueError."""
    from aletheia.config import Config
    
    with pytest.raises(ValueError, match="Invalid temperature"):
        Config(llm_temperature=2.0)  # Temperature must be 0.0-1.0

@pytest.mark.asyncio
async def test_plugin_handles_command_failure():
    """Test plugin handles command execution failure."""
    from aletheia.plugins.kubernetes import KubernetesPlugin
    
    plugin = KubernetesPlugin()
    
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "kubectl")
        
        with pytest.raises(RuntimeError, match="kubectl command failed"):
            await plugin.list_pods(namespace="default")
```

### Testing Error Recovery

```python
@pytest.mark.asyncio
async def test_agent_retries_on_failure():
    """Test agent retries failed operations."""
    from aletheia.agents.base import BaseAgent
    
    agent = BaseAgent()
    
    call_count = 0
    
    async def failing_operation():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Temporary failure")
        return "success"
    
    result = await agent.retry_operation(failing_operation, max_retries=3)
    
    assert result == "success"
    assert call_count == 3
```

## Performance Testing

### Testing Response Time

```python
import time
import pytest

@pytest.mark.slow
def test_config_loading_performance():
    """Test config loading is fast."""
    from aletheia.config import Config
    
    start = time.time()
    config = Config()
    duration = time.time() - start
    
    assert duration < 0.1  # Should load in < 100ms

@pytest.mark.asyncio
@pytest.mark.slow
async def test_agent_response_time():
    """Test agent responds within acceptable time."""
    from aletheia.agents import get_agent
    
    agent = get_agent("orchestrator")
    
    start = time.time()
    await agent.process_message("hello")
    duration = time.time() - start
    
    assert duration < 5.0  # Should respond in < 5 seconds
```

### Memory Usage Testing

```python
import pytest
import tracemalloc

@pytest.mark.slow
def test_session_memory_usage():
    """Test session doesn't leak memory."""
    from aletheia.session import Session
    
    tracemalloc.start()
    
    # Create and destroy sessions
    for _ in range(100):
        session = Session(name="test")
        del session
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # Peak memory should be reasonable
    assert peak < 100 * 1024 * 1024  # < 100MB
```

## Continuous Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install uv
      run: curl -LsSf https://astral.sh/uv/install.sh | sh
    
    - name: Install dependencies
      run: |
        uv venv
        source .venv/bin/activate
        uv pip install -r requirements.txt
        uv pip install -r requirements-dev.txt
    
    - name: Run tests
      run: |
        source .venv/bin/activate
        pytest --cov=aletheia --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

## Test Coverage Goals

- **Overall Coverage**: Minimum 80%
- **Critical Paths**: 100% (encryption, authentication, data handling)
- **New Code**: 90% coverage required
- **Plugins**: 85% coverage
- **Utilities**: 95% coverage

## Functional Testing

### Interactive Session Testing

For end-to-end functional testing of the interactive CLI, use the provided expect scripts:

```bash
# Run functional tests
./run_test.sh
```

This executes `test_aletheia_interactive.exp` which:
- Starts an Aletheia session with `--very-verbose --unsafe` flags
- Submits multiple queries sequentially
- Waits for each response to complete (by detecting the "Usage:" stats line)
- Captures all output to timestamped log files in `test_results/`

### Creating Custom Functional Tests

To create your own functional test script:

```bash
#!/usr/bin/expect -f

set timeout 300
log_user 1

# Start session
spawn bash -c "source .venv/bin/activate && uv run --env-file .env aletheia/cli.py session open --very-verbose --unsafe"

# Wait for session creation
expect {
    -re "Session ID:" {
        sleep 5
    }
    timeout {
        puts "Timeout waiting for session"
        exit 1
    }
}

# Send query
send "your query here\r"

# Wait for response completion (look for usage stats)
expect {
    -re "Usage:.*In:.*Out:" {
        sleep 5
    }
    timeout {
        puts "Timeout waiting for response"
    }
}

# Exit
send "exit\r"
expect eof
```

### Key Patterns for Expect Scripts

1. **Wait for "Session ID:"** - Indicates session is created
2. **Wait for "Usage:.*In:.*Out:"** - Indicates response is complete
3. **Use 5-second delays** - Allow prompt to fully render
4. **Set timeout 300** - Allow time for LLM responses
5. **Use `log_user 1`** - Show output in real-time

### Functional Test Output

Results are saved in `test_results/` with timestamps:
```
test_results/
├── test_run_20260119_092056.log
├── test_run_20260119_093145.log
└── ...
```

Each log contains:
- Full session output with ANSI color codes
- Agent responses and tool executions
- Token usage statistics
- Any errors or warnings

### Analyzing Test Results

```bash
# View latest test
ls -t test_results/*.log | head -1 | xargs less -R

# Search for errors
grep -i error test_results/test_run_*.log

# Extract token usage
grep "Usage:" test_results/test_run_*.log

# Count successful queries
grep -c "Response.*complete" test_results/test_run_*.log
```

## Best Practices

1. **Test One Thing**: Each test should verify one behavior
2. **Clear Names**: Test names should describe what they test
3. **Arrange-Act-Assert**: Structure tests clearly
4. **Mock External Calls**: Don't make real API calls
5. **Use Fixtures**: Share common setup code
6. **Test Edge Cases**: Test boundary conditions and errors
7. **Keep Tests Fast**: Unit tests should run in milliseconds
8. **Independent Tests**: Tests shouldn't depend on each other
9. **Clean Up**: Use fixtures and context managers for cleanup
10. **Document Complex Tests**: Add comments for non-obvious logic
