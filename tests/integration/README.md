# Integration Tests for Data Collection

This directory contains integration tests for the Kubernetes and Prometheus fetchers. These tests validate the fetchers against real data sources.

## Overview

- **Kubernetes Integration Tests** (`test_kubernetes_integration.py`): 17 tests validating kubectl integration
- **Prometheus Integration Tests** (`test_prometheus_integration.py`): 28 tests validating HTTP API integration

Total: **45 integration tests**

## Running the Tests

### Option 1: Skip All Integration Tests (Default for CI)

```bash
export SKIP_K8S_INTEGRATION=1
export SKIP_PROMETHEUS_INTEGRATION=1
pytest tests/integration/ -v
```

All tests will be skipped:
```
45 skipped in 4.09s
```

### Option 2: Run Kubernetes Tests Only

**Prerequisites:**
- kubectl installed and in PATH
- Access to a Kubernetes cluster (local or remote)
- Current kubectl context configured (`kubectl config current-context`)

```bash
# Don't set SKIP_K8S_INTEGRATION or set it to 0
export SKIP_PROMETHEUS_INTEGRATION=1
pytest tests/integration/test_kubernetes_integration.py -v
```

The tests will use:
- Current kubectl context
- `kube-system` namespace (should always exist)
- Existing pods for testing

### Option 3: Run Prometheus Tests Only

**Prerequisites:**
- Prometheus server accessible via HTTP
- Default: `http://localhost:9090` or set `PROMETHEUS_ENDPOINT`

**Starting a local Prometheus instance:**

```bash
# Using Docker
docker run -d -p 9090:9090 prom/prometheus
```

**Running the tests:**

```bash
export SKIP_K8S_INTEGRATION=1
# Don't set SKIP_PROMETHEUS_INTEGRATION or set it to 0
pytest tests/integration/test_prometheus_integration.py -v
```

**With custom endpoint:**

```bash
export PROMETHEUS_ENDPOINT=https://prometheus.example.com
export SKIP_K8S_INTEGRATION=1
pytest tests/integration/test_prometheus_integration.py -v
```

### Option 4: Run All Integration Tests

**Prerequisites:**
- Both Kubernetes and Prometheus accessible
- See prerequisites from Options 2 and 3 above

```bash
# Don't set skip flags or set them to 0
export SKIP_K8S_INTEGRATION=0
export SKIP_PROMETHEUS_INTEGRATION=0
pytest tests/integration/ -v
```

## Test Coverage

### Kubernetes Integration Tests (17 tests)

**TestKubernetesConnection** (3 tests):
- ✅ Connection to cluster succeeds
- ✅ Invalid context fails gracefully
- ✅ Capabilities reporting

**TestKubernetesPodOperations** (3 tests):
- ✅ List pods in namespace
- ✅ List pods with label selector
- ✅ Get pod status

**TestKubernetesLogFetching** (4 tests):
- ✅ Fetch logs without specifying pod
- ✅ Fetch logs with time window
- ✅ Fetch logs from specific pod
- ✅ Fetch logs with small sample size

**TestKubernetesErrorScenarios** (3 tests):
- ✅ Handle non-existent pod
- ✅ Handle non-existent namespace
- ✅ Handle invalid time window

**TestKubernetesDataQuality** (4 tests):
- ✅ Log format consistency
- ✅ Summary generation
- ✅ Time range in result
- ✅ Metadata completeness

### Prometheus Integration Tests (28 tests)

**TestPrometheusConnection** (4 tests):
- ✅ Connection succeeds
- ✅ Invalid endpoint fails
- ✅ Malformed endpoint validation
- ✅ Capabilities reporting

**TestPrometheusQueryExecution** (4 tests):
- ✅ Query 'up' metric (always exists)
- ✅ Query with time window
- ✅ Query with custom step
- ✅ Query with rate function

**TestPrometheusTemplates** (3 tests):
- ✅ Request rate template
- ✅ Missing template parameters
- ✅ Invalid template name

**TestPrometheusErrorScenarios** (4 tests):
- ✅ Invalid PromQL syntax
- ✅ Non-existent metric
- ✅ Timeout handling
- ✅ Missing query/template

**TestPrometheusDataQuality** (5 tests):
- ✅ Data format consistency
- ✅ Summary generation
- ✅ Time range accuracy
- ✅ Metadata includes query
- ✅ Count matches data length

**TestPrometheusAdaptiveResolution** (3 tests):
- ✅ Short time window (< 1 hour)
- ✅ Medium time window (1-6 hours)
- ✅ Long time window (> 7 days)

**TestPrometheusAuthentication** (3 tests):
- ✅ Basic authentication
- ✅ Bearer token authentication
- ✅ Invalid credentials handling

**TestPrometheusPerformance** (2 tests):
- ✅ Large time window (7 days)
- ✅ Complex PromQL queries

## Authentication Configuration

### Kubernetes

Kubernetes tests use the current kubectl context and delegate all authentication to `~/.kube/config`. No additional configuration is needed.

### Prometheus

**Environment Variables Authentication:**
```bash
export PROMETHEUS_USERNAME=myuser
export PROMETHEUS_PASSWORD=mypassword
pytest tests/integration/test_prometheus_integration.py -v
```

**Bearer Token Authentication:**
```bash
export PROMETHEUS_TOKEN=my-bearer-token
pytest tests/integration/test_prometheus_integration.py -v
```

**No Authentication:**
If your Prometheus instance doesn't require authentication, the tests will work without any credentials.

## CI/CD Integration

For continuous integration pipelines, always skip integration tests by default:

```yaml
# Example GitHub Actions
- name: Run tests
  env:
    SKIP_K8S_INTEGRATION: 1
    SKIP_PROMETHEUS_INTEGRATION: 1
  run: pytest tests/ -v
```

To enable integration tests in CI:
1. Set up test infrastructure (k3d for Kubernetes, Docker for Prometheus)
2. Configure environment variables
3. Remove or set skip flags to 0

## Troubleshooting

### Kubernetes Tests

**Error: `kubectl: command not found`**
- Install kubectl: `brew install kubectl` (macOS) or follow [official docs](https://kubernetes.io/docs/tasks/tools/)

**Error: `No Kubernetes context configured`**
- Configure kubectl context: `kubectl config use-context <context-name>`
- Check current context: `kubectl config current-context`

**Error: `No pods found in test namespace`**
- Tests use `kube-system` namespace which should have system pods
- If using a different cluster, ensure pods exist in the namespace

### Prometheus Tests

**Error: `Prometheus not accessible`**
- Verify Prometheus is running: `curl http://localhost:9090/api/v1/status/config`
- Check endpoint configuration: `echo $PROMETHEUS_ENDPOINT`
- Ensure firewall allows connections

**Error: `Connection timeout`**
- Increase timeout in fetcher configuration
- Check network connectivity
- Verify Prometheus is not overloaded

## Development Guidelines

### Adding New Integration Tests

1. **Use appropriate fixtures**: `kubernetes_fetcher`, `prometheus_fetcher`, etc.
2. **Handle missing resources gracefully**: Use `pytest.skip()` when resources aren't available
3. **Test real-world scenarios**: Focus on end-to-end workflows
4. **Avoid hardcoded values**: Use dynamic discovery (e.g., list pods before fetching)
5. **Clean up resources**: Integration tests should not leave artifacts

### Example Test Structure

```python
def test_new_feature(kubernetes_fetcher):
    """Test description."""
    # Arrange: Set up test conditions
    pods = kubernetes_fetcher.list_pods()
    if not pods:
        pytest.skip("No pods found")
    
    # Act: Execute the feature
    result = kubernetes_fetcher.fetch(pod=pods[0])
    
    # Assert: Verify expected behavior
    assert result.source == "kubernetes"
    assert result.count > 0
```

## Test Execution Times

- **Unit tests**: ~90 seconds (356 tests)
- **Integration tests (skipped)**: ~4 seconds (45 tests)
- **Integration tests (Kubernetes only)**: ~10-30 seconds
- **Integration tests (Prometheus only)**: ~5-15 seconds
- **All tests**: Varies based on cluster/server response times

## Notes

- Integration tests are **not mocked** - they interact with real services
- Tests are **idempotent** - can be run multiple times without side effects
- Tests use **read-only operations** - no modifications to clusters/servers
- Tests are **environment-aware** - gracefully handle missing services
