# Aletheia (ἀλήθεια) 

> **Aletheia** (ἀλήθεια) - Ancient Greek for "truth" or "un-concealment": bringing what's hidden into the open.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Aletheia** is an AI-powered command-line tool that assists SREs and system administrators in troubleshooting production incidents through systematic, multi-agent analysis. By orchestrating specialized LLM agents, Aletheia collects observability data (logs, metrics, traces), analyzes patterns, inspects code, and generates root cause hypotheses with actionable recommendations.

## 🌟 Key Features

- **🔍 Systematic Investigation**: Structured workflow from problem description to root cause analysis
- **📊 Multi-Source Correlation**: Integrates logs (Kubernetes), metrics (Prometheus), and code (Git) in a unified investigation
- **🔐 Secure by Design**: Encrypted session data and credential management using AES-256
- **📝 Auditable Process**: Complete investigation trail preserved in encrypted scratchpad format
- **⏸️ Resume Capability**: Interrupted sessions can be resumed without data loss
- **🤖 AI-Powered Agents**: Microsoft Semantic Kernel-based agents with specialized skills
- **🎯 Guided Mode**: Menu-driven workflow for structured troubleshooting
- **🎨 Rich Terminal UI**: Beautiful, interactive output using Rich library

## 📋 Table of Contents

- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Usage](#-usage)
  - [Session Management](#session-management)
  - [Investigation Workflow](#investigation-workflow)
- [Data Sources](#-data-sources)
- [Agent Architecture](#-agent-architecture)
- [Configuration Guide](#-configuration-guide)
- [Examples](#-examples)
- [Troubleshooting](#-troubleshooting)
- [Development](#-development)
- [Contributing](#-contributing)
- [License](#-license)

## 🚀 Installation

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager (recommended) or pip
- Access to observability data sources (Kubernetes, Prometheus, etc.)
- OpenAI API key or compatible LLM provider

### Install via pip

```bash
# Clone the repository
git clone https://github.com/yourusername/aletheia.git
cd aletheia

# Install dependencies
pip install -e .

# Verify installation
aletheia version
```

### Install via uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/aletheia.git
cd aletheia

# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv pip install -e .

# Verify installation
aletheia version
```

### Install for Development

```bash
# Clone the repository
git clone https://github.com/yourusername/aletheia.git
cd aletheia

# Install with development dependencies
uv pip install -e ".[dev]"

# Run tests to verify
pytest
```

## ⚡ Quick Start

### 1. Set Up Your Environment

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="sk-..."

# Optional: Configure kubectl context for Kubernetes logs
kubectl config use-context your-cluster

# Optional: Set Prometheus endpoint
export PROMETHEUS_URL="http://prometheus.example.com:9090"
```

### 2. Create a Configuration File (Optional)

Create `.aletheia/config.yaml` in your project directory or `~/.aletheia/config.yaml` in your home directory:

```yaml
llm:
  default_model: "gpt-4o"
  api_key_env: "OPENAI_API_KEY"
  
data_sources:
  kubernetes:
    enabled: true
    context: "my-cluster"
    default_namespace: "default"
  
  prometheus:
    enabled: true
    url: "${PROMETHEUS_URL}"
    timeout: 30

repositories:
  - path: "/path/to/your/codebase"
    name: "main-app"
```

### 3. Start Your First Investigation

```bash
# Open a new troubleshooting session
aletheia session open --name "prod-incident-2025-10-17"

# Follow the guided workflow:
# 1. Describe the problem
# 2. Select time window
# 3. Choose data sources
# 4. Provide repository paths
# 5. Review diagnosis
```

### 4. Manage Sessions

```bash
# List all sessions
aletheia session list

# Resume a session
aletheia session resume <session-id>

# Export session for sharing
aletheia session export <session-id> --output incident-report.tar.gz.encrypted

# Delete a session
aletheia session delete <session-id>
```

## ⚙️ Configuration

Aletheia supports a multi-level configuration system with the following precedence (highest to lowest):

1. **Environment variables** (highest priority)
2. **Project config** (`./.aletheia/config.yaml`)
3. **User config** (`~/.aletheia/config.yaml`)
4. **System config** (`/etc/aletheia/config.yaml`)

### Configuration Schema

```yaml
# LLM Configuration
llm:
  default_model: "gpt-4o"              # Primary model for most agents
  api_key_env: "OPENAI_API_KEY"       # Environment variable for API key
  reasoning_model: "o1"                # Deep reasoning model for root cause analysis
  temperature: 0.2                     # LLM temperature (0.0-1.0)
  max_tokens: 4000                     # Maximum tokens per completion

# Agent Configuration
agents:
  use_sk_agents: true                  # Use Semantic Kernel agents (recommended)
  use_sk_orchestration: false          # Use SK HandoffOrchestration (experimental)
  data_fetcher:
    model: "gpt-4o"
    max_retries: 3
  pattern_analyzer:
    model: "gpt-4o"
    confidence_threshold: 0.7
  code_inspector:
    model: "gpt-4o"
    analysis_depth: "standard"         # minimal/standard/deep
    context_lines: 10
  root_cause_analyst:
    model: "o1"                        # Use reasoning model for synthesis
    min_confidence: 0.6

# Data Source Configuration
data_sources:
  kubernetes:
    enabled: true
    context: "production"              # kubectl context
    default_namespace: "default"
    kubeconfig: "~/.kube/config"
    timeout: 60
    log_sample_size: 200               # Target log count
    
  prometheus:
    enabled: true
    url: "http://prometheus:9090"
    timeout: 30
    step: "1m"                         # Default query step
    
  elasticsearch:
    enabled: false
    url: "http://elasticsearch:9200"
    index_pattern: "logs-*"
    username: "elastic"
    password_env: "ES_PASSWORD"

# Repository Configuration
repositories:
  - path: "/path/to/repo1"
    name: "backend-api"
  - path: "/path/to/repo2"
    name: "shared-lib"

# UI Configuration
ui:
  confirmation_level: "normal"         # verbose/normal/minimal
  show_progress: true
  show_agent_names: true
  output_format: "terminal"            # terminal/json
  
# Session Configuration
session:
  base_dir: "~/.aletheia/sessions"
  auto_cleanup_days: 90                # Auto-delete sessions older than 90 days
  encryption:
    algorithm: "AES256"
    iterations: 100000

# Sampling Configuration
sampling:
  max_logs: 200
  prioritize_errors: true              # Always include all ERROR/FATAL logs
  random_sample_others: true
```

### Environment Variables

Override any configuration with environment variables:

```bash
# LLM Configuration
export OPENAI_API_KEY="sk-..."
export ALETHEIA_LLM_MODEL="gpt-4o"

# Data Sources
export PROMETHEUS_URL="http://prometheus.example.com:9090"
export ES_ENDPOINT="http://elasticsearch:9200"
export ES_PASSWORD="secret"

# Session
export ALETHEIA_SESSION_DIR="~/custom/sessions"
```

## 📖 Usage

### Session Management

#### Create a New Session

```bash
# Create with automatic name
aletheia session open

# Create with custom name
aletheia session open --name "payment-failures-2025-10-17"

# Create in conversational mode (default is guided)
aletheia session open --mode conversational
```

When you create a session, you'll be prompted for:
- **Password**: Used to encrypt all session data (AES-256)
- **Password confirmation**: Ensures you remember the password

**⚠️ Important**: Store your password securely. Without it, you cannot resume or access the session data.

#### List Sessions

```bash
aletheia session list
```

Displays a table with:
- Session name
- Session ID (INC-XXXX format)
- Mode (guided/conversational)
- Created timestamp

#### Resume a Session

```bash
aletheia session resume INC-A3F2
```

You'll be prompted for the session password. The investigation continues from where it left off.

#### Delete a Session

```bash
# Delete with confirmation prompt
aletheia session delete INC-A3F2

# Delete without confirmation
aletheia session delete INC-A3F2 --yes
```

#### Export/Import Sessions

```bash
# Export session as encrypted archive
aletheia session export INC-A3F2 --output backup.tar.gz.encrypted

# Import session from archive
aletheia session import backup.tar.gz.encrypted
```

### Investigation Workflow

Aletheia follows a systematic workflow through specialized AI agents:

```
1. Data Fetcher Agent
   ↓ Collects logs, metrics, traces
   
2. Pattern Analyzer Agent
   ↓ Identifies anomalies, correlations
   
3. Code Inspector Agent (optional)
   ↓ Maps errors to source code
   
4. Root Cause Analyst Agent
   ↓ Synthesizes findings, generates diagnosis
```

#### Guided Mode (Default)

Menu-driven workflow with numbered choices:

```
1. What problem are you investigating?
   > Describe the issue (e.g., "Payment API returning 500 errors")

2. What time window?
   [1] Last 1 hour
   [2] Last 2 hours
   [3] Last 6 hours
   [4] Custom
   > Select: 2

3. Which data sources?
   [1] Kubernetes logs
   [2] Prometheus metrics
   [3] Both
   > Select: 3

4. Which services?
   > Enter service name: payments-svc

5. Repository paths (optional)?
   > Enter path: /path/to/payments-service
   > Add another? (y/N): n

[Agent Execution - Data Collection]
✅ Collected 200 logs from Kubernetes (47 errors)
✅ Fetched metrics from Prometheus (error rate spike detected)

[Agent Execution - Pattern Analysis]
✅ Identified 2 anomalies
✅ Found 3 error clusters
✅ Built incident timeline

[Agent Execution - Code Inspection]
✅ Mapped errors to 2 source files
✅ Analyzed suspect functions
✅ Retrieved git blame information

[Agent Execution - Root Cause Analysis]
✅ Synthesized findings
✅ Generated hypothesis (confidence: 0.86)

═══════════════════════════════════════════════════
🎯 ROOT CAUSE DIAGNOSIS
═══════════════════════════════════════════════════

Type: nil_pointer_dereference
Confidence: 0.86 (High)

Description:
The IsEnabled function in featurekit/features.go:57 dereferences
f.Enabled without checking if f is nil. A recent refactor changed
feature flag loading, allowing Get() to return nil. Callers in
payments-svc don't guard against this condition.

───────────────────────────────────────────────────
📊 EVIDENCE
───────────────────────────────────────────────────

• Error rate spike: 0.2 → 7.3 errors/sec at 08:05
• 45 panics with stack trace: charge.go:112 → features.go:57
• Temporal alignment: v1.19 rollout at 08:04, first error at 08:05:14
• Git blame: Refactor by john.doe on 2025-10-10 (commit a3f9c2d)

───────────────────────────────────────────────────
🔧 RECOMMENDED ACTIONS
───────────────────────────────────────────────────

[IMMEDIATE] Rollback payments-svc to v1.18
  → Stop ongoing customer impact

[HIGH] Apply nil-safe patch to IsEnabled
  → See proposed patch below

[MEDIUM] Add unit test for nil Feature handling
  → Prevent regression

[LOW] Review all callers of featurekit.Get() for nil checks
  → Ensure defensive programming

═══════════════════════════════════════════════════

What would you like to do?
[1] Show proposed patch
[2] Save diagnosis to file
[3] Open in editor
[4] End session
> Select:
```

## 🔌 Data Sources

### Kubernetes Logs

**Requirements**:
- `kubectl` installed and configured
- Access to target cluster (via kubeconfig)

**What it collects**:
- Pod logs from specified services
- Error-level logs (always included)
- Random sample of other logs to reach target count
- Timestamps and metadata

**Configuration**:
```yaml
data_sources:
  kubernetes:
    enabled: true
    context: "production"
    default_namespace: "default"
    log_sample_size: 200
```

### Prometheus Metrics

**Requirements**:
- Prometheus server accessible via HTTP
- Network connectivity to Prometheus endpoint

**What it collects**:
- Error rate metrics
- Latency percentiles (p50, p95, p99)
- Request rate trends
- Custom PromQL queries

**Built-in Templates**:
- `error_rate`: HTTP 5xx error rate
- `latency_p95`: 95th percentile latency
- `request_rate`: Request throughput
- `cpu_usage`, `memory_usage`, `disk_io`

**Configuration**:
```yaml
data_sources:
  prometheus:
    enabled: true
    url: "http://prometheus:9090"
    timeout: 30
```

### Git Repositories

**Requirements**:
- Git repository cloned locally
- Read access to repositories

**What it analyzes**:
- Source code at suspect lines
- Git blame information (author, commit, date)
- Caller relationships
- Function context

**Configuration**:
```yaml
repositories:
  - path: "/path/to/backend-api"
    name: "backend-api"
  - path: "/path/to/shared-lib"
    name: "shared-lib"
```

## 🤖 Agent Architecture

Aletheia uses **Microsoft Semantic Kernel** to orchestrate specialized AI agents:

### Data Fetcher Agent
- **Role**: Collects observability data
- **Plugins**: KubernetesPlugin, PrometheusPlugin
- **Capabilities**: Fetches logs, queries metrics, samples data intelligently
- **Model**: gpt-4o (function calling)

### Pattern Analyzer Agent
- **Role**: Identifies patterns and anomalies
- **Capabilities**: Error clustering, timeline generation, correlation analysis
- **Model**: gpt-4o (analysis)

### Code Inspector Agent
- **Role**: Maps errors to source code
- **Plugins**: GitPlugin
- **Capabilities**: File mapping, code extraction, git blame, caller analysis
- **Model**: gpt-4o (function calling)

### Root Cause Analyst Agent
- **Role**: Synthesizes findings into diagnosis
- **Capabilities**: Evidence synthesis, hypothesis generation, confidence scoring
- **Model**: o1 (deep reasoning)

### Scratchpad Architecture

All agents share state through an encrypted **scratchpad file**:

```
~/.aletheia/sessions/INC-XXXX/
├── metadata.encrypted       # Session metadata
├── scratchpad.encrypted     # Shared agent state
├── salt                     # Encryption salt
└── data/
    ├── logs/               # Raw log files
    ├── metrics/            # Metric query results
    └── traces/             # Trace data (future)
```

## 📚 Configuration Guide

### Minimal Configuration

Create `~/.aletheia/config.yaml`:

```yaml
llm:
  default_model: "gpt-4o"
  api_key_env: "OPENAI_API_KEY"

data_sources:
  kubernetes:
    enabled: true
  prometheus:
    enabled: true
    url: "http://localhost:9090"
```

Set environment variable:
```bash
export OPENAI_API_KEY="sk-..."
```

### Production Configuration

Create `.aletheia/config.yaml` in your project:

```yaml
llm:
  default_model: "gpt-4o"
  reasoning_model: "o1"
  api_key_env: "OPENAI_API_KEY"
  temperature: 0.2

agents:
  use_sk_agents: true
  code_inspector:
    analysis_depth: "deep"
    context_lines: 20

data_sources:
  kubernetes:
    enabled: true
    context: "production"
    default_namespace: "backend"
    log_sample_size: 300
    
  prometheus:
    enabled: true
    url: "${PROMETHEUS_URL}"
    timeout: 60

repositories:
  - path: "/workspace/backend-api"
    name: "backend-api"
  - path: "/workspace/platform/featurekit"
    name: "featurekit"
  - path: "/workspace/shared-services"
    name: "shared-services"

ui:
  confirmation_level: "minimal"
  show_progress: true
  show_agent_names: true

session:
  auto_cleanup_days: 30
  encryption:
    iterations: 200000  # Higher security
```

## 💡 Examples

### Example 1: API Error Investigation

```bash
# Start session
aletheia session open --name "api-500-errors"

# Guided workflow
> Problem: "User API returning 500 errors since deployment"
> Time window: Last 2 hours
> Data sources: Kubernetes + Prometheus
> Service: user-api
> Repository: /workspace/user-service

# Output shows:
# - Error spike at 14:23 (deployment time: 14:20)
# - Panic in handleUserProfile at profile.go:89
# - Nil pointer dereference when accessing user.Email
# - Recommendation: Add nil check before dereference
```

### Example 2: Performance Degradation

```bash
aletheia session open --name "slow-checkout"

> Problem: "Checkout API latency increased to 5 seconds"
> Time window: Last 6 hours
> Data sources: Prometheus
> Service: checkout-api

# Output shows:
# - p95 latency increased from 200ms to 5s at 09:15
# - Database connection pool exhaustion
# - Recommendation: Increase connection pool size
```

### Example 3: Resume After Interruption

```bash
# Start investigation
aletheia session open --name "payment-circuit-breaker"

# ... work in progress, Ctrl+C to interrupt ...

# Later, resume
aletheia session list
aletheia session resume INC-B7F3

# Investigation continues from last checkpoint
```

## 🔧 Troubleshooting

### "kubectl command not found"

**Problem**: Kubernetes fetcher fails with "kubectl not found"

**Solution**:
```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/darwin/arm64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Verify
kubectl version --client
```

### "Failed to connect to Prometheus"

**Problem**: Cannot reach Prometheus endpoint

**Solution**:
```bash
# Test connection
curl http://prometheus:9090/api/v1/status/config

# Update config with correct URL
export PROMETHEUS_URL="http://correct-host:9090"
```

### "Invalid API key"

**Problem**: OpenAI API authentication fails

**Solution**:
```bash
# Verify API key is set
echo $OPENAI_API_KEY

# Set if missing
export OPENAI_API_KEY="sk-..."

# Test with OpenAI CLI
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### "Session not found"

**Problem**: Cannot resume session

**Solution**:
```bash
# List all sessions
aletheia session list

# Check session directory exists
ls -la ~/.aletheia/sessions/

# If corrupted, delete and start fresh
aletheia session delete INC-XXXX --yes
```

### "Wrong password"

**Problem**: Cannot decrypt session

**Solution**:
- Password is case-sensitive and must match exactly
- No password recovery mechanism (by design for security)
- If password lost, session data cannot be recovered
- Create a new session

### Low Confidence Scores

**Problem**: Diagnosis shows confidence < 0.7

**Possible Causes**:
- Insufficient data collected (enable more sources)
- Contradictory evidence
- Missing repository access for code inspection
- Complex incident requiring manual investigation

**Solutions**:
- Re-run with longer time window
- Enable all data sources
- Provide repository paths
- Use diagnosis as starting point for manual investigation

## 🛠️ Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/yourusername/aletheia.git
cd aletheia

# Create worktree for feature development
git worktree add worktrees/feat/my-feature -b feat/my-feature
cd worktrees/feat/my-feature

# Setup environment
uv venv --python 3.12
source .venv/bin/activate
uv pip install --prerelease=allow -r requirements.txt -r requirements-dev.txt
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=aletheia --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_session.py

# Run integration tests (requires local K8s/Prometheus)
pytest tests/integration/

# Skip integration tests
SKIP_K8S_INTEGRATION=1 SKIP_PROMETHEUS_INTEGRATION=1 pytest
```

### Code Quality

```bash
# Format code
black aletheia/ tests/

# Lint code
ruff aletheia/ tests/

# Type checking
mypy aletheia/

# Run all checks
black . && ruff . && mypy aletheia/ && pytest
```

### Project Structure

```
aletheia/
├── aletheia/
│   ├── __init__.py
│   ├── cli.py              # CLI entry point
│   ├── config.py           # Configuration system
│   ├── encryption.py       # Encryption utilities
│   ├── scratchpad.py       # Scratchpad implementation
│   ├── session.py          # Session management
│   ├── agents/             # AI agents
│   │   ├── orchestrator.py
│   │   ├── data_fetcher.py
│   │   ├── pattern_analyzer.py
│   │   ├── code_inspector.py
│   │   └── root_cause_analyst.py
│   ├── fetchers/           # Data fetchers
│   │   ├── kubernetes.py
│   │   └── prometheus.py
│   ├── plugins/            # Semantic Kernel plugins
│   │   ├── kubernetes_plugin.py
│   │   ├── prometheus_plugin.py
│   │   └── git_plugin.py
│   └── ui/                 # User interface
│       ├── output.py
│       ├── input.py
│       └── menu.py
├── tests/
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
├── pyproject.toml          # Project metadata
├── requirements.txt        # Dependencies
└── README.md              # This file
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Quick Contribution Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make your changes with tests
4. Run tests and linting: `pytest && black . && ruff .`
5. Commit: `git commit -m "feat: add my feature"`
6. Push and create a Pull Request

### Commit Message Convention

Use conventional commits:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test changes
- `refactor:` - Code refactoring
- `chore:` - Build/tooling changes

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Microsoft Semantic Kernel** - AI orchestration framework
- **Rich** - Terminal formatting library
- **Typer** - CLI framework
- Inspired by SRE practices and incident response workflows

## 📞 Support

- **Documentation**: [docs.aletheia.dev](https://docs.aletheia.dev) (coming soon)
- **Issues**: [GitHub Issues](https://github.com/yourusername/aletheia/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/aletheia/discussions)

---

**Made with ❤️ by the Aletheia community**