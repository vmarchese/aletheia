# Aletheia - Product Requirements Document

**Version**: 1.0
**Status**: Requirements Complete
**Date**: 2025-10-11

---

## 1. Executive Summary

**Aletheia** is a command-line tool designed to assist SREs and system administrators in troubleshooting production incidents through AI-powered analysis. By orchestrating multiple specialized LLM agents, Aletheia systematically collects observability data (logs, metrics, traces), analyzes patterns, inspects code, and generates root cause hypotheses with actionable recommendations.

### Key Value Propositions
- **Systematic Investigation**: Structured workflow from problem description to root cause analysis
- **Multi-Source Correlation**: Integrates logs, metrics, traces, and code in a unified investigation
- **Secure by Design**: Encrypted session data and credential management
- **Auditable Process**: Complete investigation trail preserved in scratchpad format
- **Resume Capability**: Interrupted sessions can be resumed without data loss

---

## 2. Architecture Overview

### 2.1 Agent System Architecture

Aletheia uses an **Orchestrator + Specialist** pattern with scratchpad-based handoff.

```
User ←→ Orchestrator Agent (manages session, UX, coordination)
         ↓
         [Scratchpad File] (encrypted, shared state)
         ↓
Handoff to Agent:
1. Data Fetcher Agent       → Collects observability data
2. Pattern Analyzer Agent   → Identifies anomalies and correlations
3. Code Inspector Agent     → Maps errors to source code
4. Root Cause Analyst       → Synthesizes findings and generates diagnosis
```

### 2.2 Scratchpad Design

The scratchpad is an encrypted file that serves as the shared context for all agents.

**Location**: `~/.aletheia/sessions/{session-id}/scratchpad.encrypted`

**Structure**:
```yaml
PROBLEM_DESCRIPTION:
  description: "User-provided problem statement"
  time_window: "2h"
  affected_services: ["payments-svc"]
  interaction_mode: "guided" | "conversational"

DATA_COLLECTED:
  logs:
    - source: "kubernetes"
      path: "~/.aletheia/sessions/{id}/data/logs/payments-svc.json"
      summary: "200 logs, 47 errors, top error: 'nil pointer dereference'"
      count: 200
      time_range: "08:03-08:07"
      error_clusters:
        "nil pointer dereference": 45
        "circuit open": 2
  metrics:
    - source: "prometheus"
      path: "~/.aletheia/sessions/{id}/data/metrics/error_rate.json"
      summary: "Error rate spike: 0.2 → 7.3 at 08:05"
      queries:
        - "rate(http_requests_total{status=~'5..'}[5m])"
  traces:
    - source: "jaeger"
      path: "~/.aletheia/sessions/{id}/data/traces/error_spans.json"
      summary: "15 error traces, representative span: chargeHandler → applyPromoIfEligible"
      error_count: 15

PATTERN_ANALYSIS:
  anomalies:
    - type: "error_rate_spike"
      timestamp: "08:05:00"
      severity: "critical"
      description: "500 error rate increased 36x"
  correlations:
    - type: "temporal_alignment"
      description: "Error spike coincides with payments-svc v1.19 rollout"
      confidence: 0.92
  error_clusters:
    - pattern: "nil pointer dereference at charge.go:112"
      count: 45
      stack_trace: "charge.go:112 → features.go:57 → promo.go:88"
  timeline:
    - time: "08:05:14"
      event: "First panic in chargeHandler"
    - time: "08:05:15"
      event: "Circuit breaker opens to promo-svc"

CODE_INSPECTION:
  suspect_files:
    - file: "featurekit/features.go"
      line: 57
      function: "IsEnabled"
      repository: "git@company:platform/featurekit.git"
      snippet: |
        func IsEnabled(f *Feature) bool {
            return *f.Enabled // <-- nil pointer dereference
        }
      analysis: "No nil check before dereferencing f.Enabled"
      git_blame:
        author: "john.doe"
        commit: "a3f9c2d"
        date: "2025-10-10"
        message: "Refactor feature flag loading"
  related_code:
    - file: "payments-svc/internal/discounts/promo.go"
      line: 88
      function: "applyPromoIfEligible"
      snippet: |
        f := featurekit.Get("new_promo_engine") // may return nil
        if featurekit.IsEnabled(f) { ... }      // nil can reach here
      analysis: "Caller doesn't guard against nil return from Get()"

FINAL_DIAGNOSIS:
  root_cause:
    type: "nil_pointer_dereference"
    confidence: 0.86
    description: |
      The IsEnabled function in featurekit/features.go:57 dereferences
      f.Enabled without checking if f is nil. A recent refactor changed
      feature flag loading, allowing Get() to return nil. Callers in
      payments-svc don't guard against this condition.
  timeline_correlation:
    deployment: "payments-svc v1.19 rollout at 08:04"
    first_error: "08:05:14 (70 seconds after deployment)"
    alignment: "Temporal alignment supports hypothesis"
  recommended_actions:
    - priority: "immediate"
      action: "Rollback payments-svc to v1.18"
      rationale: "Stop ongoing customer impact"
    - priority: "high"
      action: "Apply nil-safe patch to IsEnabled"
      patch: |
        func IsEnabled(f *Feature) bool {
            return f != nil && f.Enabled != nil && *f.Enabled
        }
    - priority: "medium"
      action: "Add unit test for nil Feature handling"
    - priority: "low"
      action: "Review all callers of featurekit.Get() for nil checks"
```

### 2.3 Agent Responsibilities

#### Orchestrator Agent
- Manages user interaction (guided or conversational mode)
- Creates and initializes scratchpad
- Routes between specialist agents (custom or SK HandoffOrchestration)
- Presents findings to user
- Handles error recovery and retry logic
- **SK Integration**: Optionally uses HandoffOrchestration for agent coordination

#### Data Fetcher Agent (SK ChatCompletionAgent)
- **Plugins**: KubernetesPlugin, PrometheusPlugin
- **Capabilities via Function Calling**:
  - Fetches logs via `fetch_kubernetes_logs(pod, namespace, ...)`
  - Queries metrics via `fetch_prometheus_metrics(query, start, end, ...)`
  - Constructs PromQL queries via `build_promql_from_template(template, params)`
- Samples data intelligently (all errors + random sample of others)
- Writes summaries + file references to scratchpad
- 3 retries with exponential backoff on failures (via SK + custom retry)
- **LLM Model**: Uses FunctionChoiceBehavior.Auto() to automatically invoke plugins

#### Pattern Analyzer Agent (SK ChatCompletionAgent)
- Reads DATA_COLLECTED section from scratchpad
- Identifies anomalies (spikes, drops, outliers) using LLM analysis
- Correlates across logs, metrics, traces
- Clusters error messages using normalization algorithms
- Builds incident timeline
- Writes PATTERN_ANALYSIS to scratchpad
- **LLM Model**: Direct analysis methods (no plugins required)

#### Code Inspector Agent (SK ChatCompletionAgent)
- **Plugins**: GitPlugin
- **Capabilities via Function Calling**:
  - Maps stack traces to files via `find_file_in_repo(filename, repo)`
  - Extracts code context via `extract_code_context(file_path, line, context_lines)`
  - Runs git blame via `git_blame(file_path, line_number, repo)`
- Analyzes caller relationships (configurable depth)
- Writes CODE_INSPECTION to scratchpad
- **LLM Model**: Uses FunctionChoiceBehavior.Auto() to automatically invoke Git operations

#### Root Cause Analyst Agent (SK ChatCompletionAgent)
- Reads entire scratchpad + code files
- Synthesizes findings into root cause hypothesis using LLM reasoning
- Assigns confidence score based on evidence strength
- Generates actionable recommendations with priorities
- Writes FINAL_DIAGNOSIS to scratchpad
- **LLM Model**: Deep reasoning model (e.g., o1) for comprehensive synthesis

### 2.4 Agent Execution Model

**Synchronous Pipeline** (MVP):
- Orchestrator runs agents according to the user's choice
- User sees progress through each stage
- Each agent completes before next begins
- Estimated session time: 2-5 minutes

**Future Optimization**: Parallel data fetching from multiple sources

### 2.5 LLM Configuration

Each agent can use a different LLM model optimized for its task:

```yaml
llm:
  default_model: "gpt-4o"
  api_key_env: "OPENAI_API_KEY"

  agents:
    orchestrator:
      model: "gpt-4o"           # Conversational, fast
    data_fetcher:
      model: "gpt-4o-mini"      # Structured output, cost-effective
    pattern_analyzer:
      model: "gpt-4o"           # Pattern recognition
    code_inspector:
      model: "gpt-4o"           # Code understanding
    root_cause_analyst:
      model: "o1"               # Deep reasoning
```

**LLM Integration**: Aletheia uses **Semantic Kernel** for LLM integration, providing:
- Unified interface across multiple LLM providers
- Automatic function calling via plugins
- Built-in retry and error handling
- Multi-agent orchestration support

**Migration Note**: The custom `LLMProvider` abstraction is deprecated in favor of Semantic Kernel's `OpenAIChatCompletion` service. Both patterns are currently supported via feature flags for backward compatibility during the transition.

### 2.6 Semantic Kernel Architecture

Aletheia leverages **Microsoft Semantic Kernel** as its AI orchestration framework, providing a robust foundation for multi-agent systems with automatic function calling and orchestration.

#### 2.6.1 Agent Framework

All specialist agents inherit from `SKBaseAgent`, which wraps Semantic Kernel's `ChatCompletionAgent`:

```python
from aletheia.agents.sk_base import SKBaseAgent

class DataFetcherAgent(SKBaseAgent):
    """Data fetching agent using SK ChatCompletionAgent."""
    
    def __init__(self, config, scratchpad):
        super().__init__(config, scratchpad, agent_name="data_fetcher")
        # Register plugins with kernel
        self.kernel.add_plugin(KubernetesPlugin(config), plugin_name="kubernetes")
        self.kernel.add_plugin(PrometheusPlugin(config), plugin_name="prometheus")
```

**Key Features**:
- **Lazy Initialization**: Kernel and agent created on-demand
- **Plugin Support**: Automatic registration of kernel function plugins
- **Scratchpad Integration**: Built-in read/write methods for shared state
- **Configurable Models**: Per-agent model selection via config

#### 2.6.2 Plugin Architecture

External tool integrations are implemented as **Semantic Kernel plugins** with `@kernel_function` decorators:

```python
from semantic_kernel.functions import kernel_function
from typing import Annotated

class KubernetesPlugin:
    @kernel_function(
        name="fetch_kubernetes_logs",
        description="Fetch logs from a Kubernetes pod with sampling"
    )
    def fetch_logs(
        self,
        pod: Annotated[str, "The name of the pod to fetch logs from"],
        namespace: Annotated[str, "The Kubernetes namespace"] = "default",
        sample_size: Annotated[int, "Target number of log entries"] = 200
    ) -> Annotated[str, "JSON string containing logs and metadata"]:
        # Implementation calls KubernetesFetcher
        ...
```

**Available Plugins**:
- **KubernetesPlugin**: Pod logs, pod listing, status checks
- **PrometheusPlugin**: Metric queries, PromQL execution, template-based queries
- **GitPlugin**: git blame, file search, code context extraction

**Plugin Benefits**:
- **Automatic Invocation**: LLM automatically calls functions as needed via `FunctionChoiceBehavior.Auto()`
- **Type Safety**: Annotated type hints provide parameter descriptions to the LLM
- **Composability**: Agents can register multiple plugins for complex capabilities
- **Testability**: Plugins can be mocked independently in unit tests

#### 2.6.3 Function Calling Pattern

Semantic Kernel's `FunctionChoiceBehavior.Auto()` enables automatic function calling:

1. Agent receives a task (e.g., "Fetch logs from payments-svc pod")
2. LLM determines which kernel function to call based on descriptions
3. SK automatically invokes the function with appropriate parameters
4. Function result is returned to LLM for further processing
5. LLM synthesizes results and updates scratchpad

**Configuration Example**:
```python
execution_settings = OpenAIChatPromptExecutionSettings(
    function_choice_behavior=FunctionChoiceBehavior.Auto()
)
```

#### 2.6.4 Orchestration Pattern

Agent coordination uses **HandoffOrchestration** from Semantic Kernel:

```python
from semantic_kernel.agents import HandoffOrchestration, OrchestrationHandoffs

# Define handoff rules (routing topology)
handoffs = OrchestrationHandoffs(
    # data_fetcher → pattern_analyzer (after data collection)
    # pattern_analyzer → code_inspector (after analysis)
    # code_inspector → root_cause_analyst (after code inspection)
)

# Create orchestration
orchestration = HandoffOrchestration(
    members=[data_fetcher_agent, pattern_analyzer_agent, ...],
    handoffs=handoffs,
    agent_response_callback=update_scratchpad,
    human_response_function=prompt_user
)
```

**Handoff Rules**:
- **data_fetcher** → **pattern_analyzer**: After data collection completes
- **pattern_analyzer** → **code_inspector**: After pattern analysis completes
- **code_inspector** → **root_cause_analyst**: After code inspection completes
- **pattern_analyzer** → **root_cause_analyst**: Skip code inspection option

**Orchestration Features**:
- **Callback Support**: `agent_response_callback` for scratchpad updates
- **Human-in-the-Loop**: `human_response_function` for guided mode interaction
- **Termination Conditions**: Each agent signals completion/failure/skip
- **Runtime Management**: `InProcessRuntime` for local multi-agent execution

#### 2.6.5 Feature Flag Configuration

Semantic Kernel integration is opt-in via configuration:

```yaml
agents:
  use_sk_orchestration: false  # Default: false (use custom orchestration)
```

**Precedence** (highest to lowest):
1. Environment variable: `ALETHEIA_USE_SK_ORCHESTRATION=true`
2. Config file: `agents.use_sk_orchestration: true`
3. Default: `false`

**Backward Compatibility**: Both custom and SK orchestration patterns are maintained during the transition period. Custom implementations will be deprecated in a future release.

#### 2.6.6 SK Service Configuration

Semantic Kernel services are configured per-agent:

```python
# Create OpenAI chat completion service
service = OpenAIChatCompletion(
    service_id="openai-chat",
    ai_model_id=model,
    api_key=api_key
)

# Add service to kernel
kernel.add_service(service)

# Configure execution settings
settings = kernel.get_prompt_execution_settings_from_service_id("openai-chat")
settings.function_choice_behavior = FunctionChoiceBehavior.Auto()
```

**Service Benefits**:
- **Consistent Interface**: Same pattern across all LLM providers
- **Built-in Retry**: Automatic retry logic for transient failures
- **Token Management**: Automatic token counting and limits
- **Streaming Support**: Optional streaming responses (future enhancement)

---

## 3. Data Collection Strategy

### 3.1 Supported Data Sources (MVP)

1. **Kubernetes**
  1.1 **Context**
   - Tool: `kubectl config set-context`
   - Auth: Delegates to `~/.kube/config`
   - Sampling: n/a
  1.2 **Namespace**
   - Tool: `kubectl config set-context --namespace=<namespace>`
   - Auth: Delegates to `~/.kube/config`
   - Sampling: n/a
  1.3 **Logs**
   - Tool: `kubectl logs`
   - Auth: Delegates to `~/.kube/config`
   - Sampling: Smart sampling (all errors + random sample)

2. **Elasticsearch Logs**
   - Tool: `curl` with Elasticsearch REST API
   - Auth: Multi-source (encrypted config, keychain, env vars)
   - Query: Template-based + LLM fallback

3. **Prometheus Metrics**
   - Tool: `curl` with Prometheus HTTP API
   - Auth: Multi-source (encrypted config, keychain, env vars)
   - Query: Template-based PromQL + LLM fallback

**Deferred to Post-MVP**: Jaeger traces, local file logs

### 3.2 Query Construction

**Hybrid Approach**: Templates for common patterns, LLM for complex cases

**Example Elasticsearch Template**:
```python
ES_ERROR_QUERY_TEMPLATE = {
    "query": {
        "bool": {
            "must": [
                {"match": {"service": "{service}"}},
                {"match": {"level": "ERROR"}},
                {"range": {"@timestamp": {"gte": "{start}", "lte": "{end}"}}}
            ]
        }
    },
    "size": "{sample_size}"
}
```

**Example PromQL Template**:
```python
PROMQL_ERROR_RATE = 'rate(http_requests_total{{service="{service}",status=~"5.."}}[{window}])'
```

### 3.3 Credential Management

**Multi-Source Precedence** (highest to lowest):
1. Environment variables (`ES_ENDPOINT`, `ES_PASSWORD`)
2. Project-specific config (`./.aletheia/config.yaml`)
3. User config (`~/.aletheia/config.yaml`)
4. System config (`/etc/aletheia/config.yaml`)

**Encryption**: All credentials encrypted with session key

**Kubernetes Exception**: Delegates to existing `kubectl` authentication

### 3.4 Sampling Strategy

**Logs**:
- Capture all ERROR and FATAL level logs by default, override if requested by user
- Random sample of other levels to reach target count (e.g., 200 total)
- Time-window based (e.g., last 2 hours by default)  selectable by user

**Metrics**:
- 1-minute resolution (adaptive based on time window)
- Pre-aggregated when possible (min/max/avg)

**Traces** (post-MVP):
- All error traces in time window
- P95+ latency traces
- Representative success samples

### 3.5 Error Handling

**CLI Tool Failures**:
- 3 retries with exponential backoff (1s, 2s, 4s)
- After retries, prompt user with options:
  - Retry with different parameters
  - Skip this data source
  - Provide data manually (upload file)

**Partial Success**:
- Continue analysis with available data
- Note missing data sources in diagnosis
- Include data limitations in confidence scoring

---

## 4. Code Analysis Integration

### 4.1 Repository Access

**Discovery Strategy**: Hybrid approach
- Orchestrator extracts service names from logs/traces
- Suggests repositories based on naming patterns
- User confirms or provides additional repos

**Access Method**: User provides paths to git repositories and tag
- Aletheia clones the repository locally in the session folder

**Validation**:
- Verify path is a git repository
- Warn if current branch doesn't match expected deployment branch
- Confirm user wants to proceed with current branch

### 4.2 Branch/Commit Selection

**Strategy**: Parse deployment logs if available, otherwise ask user

**Example**:
```
> [Aletheia] Detected deployment: payments-svc v1.19 at 08:04
> Git commit from deployment log: a3f9c2d
> Confirm using commit a3f9c2d? [Y/n]
```

**Fallback**: If no deployment metadata, ask user to specify branch/commit

### 4.3 Symbol Search & Code Extraction

**File Mapping**:
- Use full import paths from stack traces when available
- Search all provided repositories for file name
- Ask user if ambiguous (file exists in multiple repos)

**Code Extraction**:
- Extract entire function containing suspect line
- Include type definitions if referenced
- Configurable depth for analyzing callers and dependencies

**Analysis Depth** (configurable based on problem type):
- Minimal: Just suspect function
- Standard: Function + immediate callers
- Deep: Function + callers + type definitions + related functions

### 4.4 Git History Analysis

**Basic `git blame`**:
```bash
git blame -L {line},{line} {file}
```

Output includes:
- Author
- Commit hash
- Date
- Commit message

**Future Enhancement**: Full commit diff and PR metadata via GitHub/GitLab API

### 4.5 Code Analysis Method

**Deferred Decision**: AST-based vs LLM-based analysis

**Options for Implementation**:
1. **LLM-only**: Feed code to LLM or LLM-based tool on command line for all analysis (MVP approach)
2. **tree-sitter**: Universal AST parser for symbol extraction
3. **Hybrid**: tree-sitter for navigation, LLM for understanding

**Recommendation**: Start with LLM-only for MVP, add tree-sitter optimization post-MVP

---

## 5. User Experience Design

### 5.1 Interaction Modes

User selects mode at session start:

**Guided Mode** (default):
```
> [Aletheia] Choose a time window:
1. Last 30m
2. Last 2h
3. Custom…

> [User] → 2
```
- Menu-driven workflow
- Numbered choices
- Clear next steps
- Confirmation prompts (configurable)

**Conversational Mode**:
```
> [Aletheia] What would you like to investigate?
> [User] Show me errors from payments service in the last 2 hours
> [Aletheia] I'll fetch Kubernetes logs for payments-svc from 08:05-10:05...
```
- Natural language interaction
- LLM-powered intent understanding
- More flexible but potentially slower

### 5.2 Session Management

**Commands**:
```bash
# Start new session
aletheia session open --name incident-2025-10-11 [--mode guided|conversational]

# List all sessions
aletheia session list

# Resume interrupted session
aletheia session resume INC-8F2A

# Export session for sharing
aletheia session export INC-8F2A [--output incident.tar.gz.enc]

# Import shared session
aletheia session import incident.tar.gz.enc

# Delete session
aletheia session delete INC-8F2A
```

**Session Directory Structure**:
```
~/.aletheia/sessions/INC-8F2A/
├── metadata.json          # Session info (created, updated, status)
├── scratchpad.encrypted   # Shared agent state
├── data/                  # Raw collected data
│   ├── logs/
│   │   └── payments-svc.json.encrypted
│   ├── metrics/
│   │   └── error_rate.json.encrypted
│   └── traces/
│       └── error_spans.json.encrypted
└── diagnosis.md           # Final output (plaintext or encrypted based on config)
```

### 5.3 Confirmation Levels

Configurable via `~/.aletheia/config.yaml`:

```yaml
ui:
  confirmation_level: "normal"  # verbose | normal | minimal
```

**Verbose**:
- Confirm every external command
- Show full command before execution
- Confirm each agent transition

**Normal** (default):
- Confirm before fetching data
- Confirm before accessing repositories
- No confirmation for analysis steps

**Minimal**:
- Only confirm destructive operations
- No confirmation for read-only operations

### 5.4 Progress Feedback

**Long-running Operations**:
```
> [Aletheia] Fetching Kubernetes logs... ⏳ (elapsed: 5s)
```

**Agent Visibility** (verbose mode only):
```
> [Aletheia] [Data Fetcher Agent] Executing: kubectl logs...
> [Aletheia] [Pattern Analyzer Agent] Analyzing 200 log entries...
```

**Default Mode**: Hide agent architecture from user, show operation progress

### 5.5 Error Handling UI

**Failure After Retries**:
```
> [Aletheia] ❌ Failed to connect to Elasticsearch after 3 attempts.
> Error: Connection timeout
> What would you like to do?
1. Retry with different parameters
2. Skip Elasticsearch and continue with available data
3. Provide Elasticsearch data manually (upload JSON file)
4. End session
```

**Partial Success**:
```
> [Aletheia] ⚠️  Successfully fetched logs and metrics.
> Note: Jaeger traces unavailable (connection failed).
> Continue analysis with available data? [Y/n]
```

### 5.6 Output Format

**Terminal Output**:
```
> [Aletheia]
================================================================================
ROOT CAUSE ANALYSIS (Confidence: 0.86)
================================================================================

PROBABLE CAUSE:
Nil pointer dereference in featurekit/features.go:57

DESCRIPTION:
The IsEnabled function dereferences f.Enabled without checking if f is nil.
Recent refactor (commit a3f9c2d) changed feature flag loading, allowing
Get() to return nil. Callers don't guard against this condition.

EVIDENCE:
• 45 panics with stack trace: charge.go:112 → features.go:57 → promo.go:88
• Error spike at 08:05 (70s after payments-svc v1.19 deployment)
• Git blame shows recent change by john.doe on 2025-10-10

RECOMMENDED ACTIONS:
[IMMEDIATE] Rollback payments-svc to v1.18
[HIGH]      Apply nil-safe patch to IsEnabled function
[MEDIUM]    Add unit test for nil Feature handling
[LOW]       Review all callers of featurekit.Get() for nil checks

Choose an action:
1. Show proposed patch
2. Open in $EDITOR (features.go:57)
3. Save diagnosis to file
4. End session
```

**File Output**: `~/.aletheia/sessions/{id}/diagnosis.md`
- Markdown format
- Full diagnosis text
- Code snippets with syntax highlighting
- Timeline visualization (ASCII art)

### 5.7 Deferred Features (Post-MVP)

- Shortcuts and quick commands
- Configuration profiles
- Session replay with new data
- External integrations (GitHub issues, Slack notifications)

---

## 6. Technical Implementation

### 6.1 Technology Stack

**Language**: Python 3.10+, uv as package manager

**Core Dependencies**:
```toml
[dependencies]
typer = "^0.9.0"          # CLI framework
pyyaml = "^6.0"           # Config parsing
pycryptodome = "^3.19"    # Encryption
rich = "^13.7"            # Terminal output
requests = "^2.31"        # HTTP APIs
gitpython = "^3.1"        # Git operations (optional for MVP)
semantic-kernel = "^1.37.0"
```

**Optional Dependencies**:
```toml
[optional-dependencies]
tree-sitter = "^0.20"     # AST parsing (post-MVP)
```

### 6.2 Project Structure

```
aletheia/
├── aletheia/
│   ├── __init__.py
│   ├── cli.py                    # Typer CLI entry point
│   ├── config.py                 # Multi-level config management
│   ├── session.py                # Session lifecycle management
│   ├── scratchpad.py             # Scratchpad read/write operations
│   ├── encryption.py             # PBKDF2 + Fernet encryption
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py               # Base agent class
│   │   ├── orchestrator.py
│   │   ├── data_fetcher.py
│   │   ├── pattern_analyzer.py
│   │   ├── code_inspector.py
│   │   └── root_cause_analyst.py
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── base.py               # Base fetcher interface
│   │   ├── kubernetes.py
│   │   ├── elasticsearch.py
│   │   └── prometheus.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── provider.py           # Custom LLM abstraction
│   │   └── prompts.py            # Agent prompt templates
│   └── utils/
│       ├── __init__.py
│       ├── retry.py              # Exponential backoff
│       └── validation.py         # Input validation
├── tests/
│   ├── unit/
│   │   ├── test_agents.py
│   │   ├── test_fetchers.py
│   │   ├── test_encryption.py
│   │   └── test_scratchpad.py
│   └── integration/
│       └── test_session_flow.py
├── pyproject.toml
├── README.md
└── SPECIFICATION.md              # This document
```

### 6.3 Configuration System

**Multi-Level Precedence** (highest to lowest):
1. Environment variables
2. Project-specific: `./.aletheia/config.yaml`
3. User-specific: `~/.aletheia/config.yaml`
4. System-wide: `/etc/aletheia/config.yaml`

**Example Configuration**:
```yaml
# ~/.aletheia/config.yaml

llm:
  default_model: "gpt-4o"
  api_key_env: "OPENAI_API_KEY"

  agents:
    orchestrator:
      model: "gpt-4o"
    data_fetcher:
      model: "gpt-4o-mini"
    pattern_analyzer:
      model: "gpt-4o"
    code_inspector:
      model: "gpt-4o"
    root_cause_analyst:
      model: "o1"

data_sources:
  kubernetes:
    context: "prod-eu"
    namespace: "default"

  elasticsearch:
    endpoint: "https://es.company.com"
    credentials:
      type: "env"  # env | keychain | encrypted_file
      username_env: "ES_USERNAME"
      password_env: "ES_PASSWORD"

  prometheus:
    endpoint: "https://prometheus.company.com"
    credentials:
      type: "env"

ui:
  confirmation_level: "normal"  # verbose | normal | minimal
  default_mode: "guided"        # guided | conversational
  agent_visibility: false       # Show agent names in output

session:
  auto_save_interval: 300       # Seconds (0 to disable)
  default_time_window: "2h"

encryption:
  algorithm: "Fernet"            # Fernet (AES-128-CBC + HMAC)
  pbkdf2_iterations: 100000
  salt_size: 32

sampling:
  logs:
    default_sample_size: 200
    always_include_levels: ["ERROR", "FATAL", "CRITICAL"]

  metrics:
    default_resolution: "1m"
    auto_adjust: true
```

### 6.4 Encryption Implementation

**Algorithm**: Fernet (symmetric encryption with AES-128-CBC + HMAC)

**Key Derivation**:
```python
import secrets
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Cipher import AES

def derive_session_key(password: str, salt: bytes) -> bytes:
    """Derive session key from user password using PBKDF2."""
    return PBKDF2(
        password=password.encode('utf-8'),
        salt=salt,
        dkLen=32,  # 256-bit key
        count=100000  # iterations
    )

def create_session_encryption(password: str) -> tuple[bytes, bytes]:
    """Create encryption key and salt for new session."""
    salt = secrets.token_bytes(32)
    key = derive_session_key(password, salt)
    return key, salt

def encrypt_file(filepath: str, key: bytes) -> None:
    """Encrypt file in place with Fernet."""
    from cryptography.fernet import Fernet
    import base64

    fernet_key = base64.urlsafe_b64encode(key)
    cipher = Fernet(fernet_key)

    with open(filepath, 'rb') as f:
        plaintext = f.read()

    encrypted = cipher.encrypt(plaintext)

    with open(filepath, 'wb') as f:
        f.write(encrypted)
```

**Session Initialization**:
```python
# User starts session
password = getpass("Enter session password: ")
key, salt = create_session_encryption(password)

# Store salt with session metadata
session_metadata = {
    "id": "INC-8F2A",
    "salt": base64.b64encode(salt).decode('utf-8'),
    "created": "2025-10-11T08:05:00Z"
}

# Encrypt all session files with session key
encrypt_file("scratchpad.txt", key)  # → scratchpad.encrypted
encrypt_file("data/logs/payments-svc.json", key)  # → payments-svc.json.encrypted
```

**Security Properties**:
- Unique salt per session (prevents rainbow table attacks)
- Strong PBKDF2 iteration count (100K iterations)
- Authenticated encryption (HMAC prevents tampering)
- Session-scoped keys (breach of one session doesn't compromise others)

### 6.5 LLM Provider Abstraction

**Custom Implementation** (no LangChain dependency):

```python
# aletheia/llm/provider.py

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def complete(self,
                 prompt: str,
                 system_prompt: Optional[str] = None,
                 temperature: float = 0.7,
                 max_tokens: Optional[int] = None) -> str:
        """Generate completion from prompt."""
        pass

class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def complete(self, prompt: str, **kwargs) -> str:
        import openai
        openai.api_key = self.api_key

        messages = []
        if kwargs.get('system_prompt'):
            messages.append({"role": "system", "content": kwargs['system_prompt']})
        messages.append({"role": "user", "content": prompt})

        response = openai.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get('temperature', 0.7),
            max_tokens=kwargs.get('max_tokens')
        )

        return response.choices[0].message.content

class LLMFactory:
    """Factory for creating LLM providers based on configuration."""

    @staticmethod
    def create_provider(config: Dict[str, Any]) -> LLMProvider:
        model = config.get('model', 'gpt-4o')

        if model.startswith('gpt-') or model.startswith('o1'):
            api_key = os.getenv(config.get('api_key_env', 'OPENAI_API_KEY'))
            return OpenAIProvider(api_key, model)
        else:
            raise ValueError(f"Unsupported model: {model}")
```

**Usage in Agents**:
```python
# aletheia/agents/data_fetcher.py

class DataFetcherAgent:
    def __init__(self, config: Dict[str, Any]):
        self.llm = LLMFactory.create_provider(config['llm']['agents']['data_fetcher'])

    def generate_elasticsearch_query(self, user_intent: str) -> Dict[str, Any]:
        prompt = f"""Generate an Elasticsearch query for: {user_intent}

        Output valid JSON following Elasticsearch Query DSL format."""

        query_json = self.llm.complete(prompt, temperature=0.0)
        return json.loads(query_json)
```

### 6.6 Testing Strategy

**Unit Tests** (mocked LLM responses):
```python
# tests/unit/test_agents.py

def test_data_fetcher_kubernetes():
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(
            stdout='{"log": "ERROR: something failed"}\n',
            returncode=0
        )

        fetcher = KubernetesFetcher()
        result = fetcher.fetch_logs(namespace="default", pod="payments-svc")

        assert "ERROR" in result
        mock_run.assert_called_once()
```

**Integration Tests** (end-to-end):
```python
# tests/integration/test_session_flow.py

def test_full_session_flow():
    # Start session
    session = Session.create("test-incident")
    session.set_password("test-password-123")

    # Initialize scratchpad
    scratchpad = Scratchpad(session)
    scratchpad.write_problem_description("Payments API 500 errors")

    # Simulate data fetching
    data_fetcher = DataFetcherAgent(config)
    data_fetcher.fetch(source="kubernetes", scratchpad=scratchpad)

    # Verify scratchpad updated
    assert scratchpad.has_section("DATA_COLLECTED")

    # Simulate pattern analysis
    pattern_analyzer = PatternAnalyzerAgent(config)
    pattern_analyzer.analyze(scratchpad)

    assert scratchpad.has_section("PATTERN_ANALYSIS")

    # Cleanup
    session.delete()
```

**Test Coverage Target**: >80% for core modules

---

## 7. Risk Assessment & Mitigation

### 7.1 Technical Risks

#### Risk: LLM Token Usage Costs
**Severity**: Medium
**Probability**: High

**Description**: Root Cause Analyst reading full scratchpad + multiple code files can consume 10-20K tokens per session. With o1 model, costs can escalate.

**Mitigation**:
1. Earlier agents write summaries, not raw data dumps
2. Implement token budget awareness (warn user at 75% of budget)
3. Add configuration option for maximum tokens per session
4. Provide cost estimation before expensive operations

#### Risk: Code Analysis Complexity
**Severity**: Medium
**Probability**: Medium

**Description**: LLM-only code analysis may miss subtle bugs or struggle with complex codebases.

**Mitigation**:
1. Start with LLM-only for MVP (acceptable for most cases)
2. Post-MVP: Add tree-sitter for precise symbol extraction
3. Allow configurable analysis depth (minimal/standard/deep)
4. Provide "confidence: low" warnings when code analysis is uncertain

#### Risk: Repository Synchronization
**Severity**: Medium
**Probability**: High

**Description**: User-provided local repos may not match deployed code version.

**Mitigation**:
1. Validate repository branch/commit matches deployment metadata
2. Warn user prominently if mismatch detected
3. Show git commit hash in diagnosis output
4. Add documentation on maintaining repo sync

#### Risk: Credential Security
**Severity**: High
**Probability**: Low

**Description**: Storing encrypted credentials creates attack surface.

**Mitigation**:
1. Strong encryption (Fernet with PBKDF2, 100K iterations)
2. Session-scoped keys (breach of one session doesn't compromise others)
3. Support for system keychain integration (post-MVP)
4. Clear documentation on security model

### 7.2 Usability Risks

#### Risk: Overwhelming User with Choices
**Severity**: Low
**Probability**: Medium

**Description**: Too many prompts and confirmations slow down investigation.

**Mitigation**:
1. Configurable confirmation levels (verbose/normal/minimal)
2. Sensible defaults based on user role
3. "Quick mode" command for power users (post-MVP)
4. Learn from user patterns (future enhancement)

#### Risk: Unclear Diagnosis Output
**Severity**: Medium
**Probability**: Medium

**Description**: LLM-generated diagnosis may be verbose or unclear.

**Mitigation**:
1. Structured output format (root cause, evidence, actions)
2. Confidence scoring to set expectations
3. Highlight actionable recommendations
4. Save full context to file for detailed review

---

## 8. Success Criteria

### 8.1 MVP Success Metrics

**Functional Requirements**:
- ✅ Successfully complete end-to-end session (problem → diagnosis)
- ✅ Support 2+ data sources (Kubernetes + Elasticsearch/Prometheus)
- ✅ Generate root cause hypothesis with ≥0.7 confidence
- ✅ Produce actionable recommendations
- ✅ Session resume after interruption
- ✅ Encrypted session data and credentials

**Quality Requirements**:
- ✅ Test coverage ≥80% for core modules
- ✅ Session completion time <5 minutes (typical case)
- ✅ Zero credential leaks in logs or temporary files

**Usability Requirements**:
- ✅ User can complete investigation without reading documentation (guided mode)
- ✅ Clear error messages with recovery options
- ✅ Diagnosis output understandable to SREs

### 8.2 Post-MVP Success Metrics

**Adoption**:
- Active users (daily active incidents investigated)
- Session completion rate (% of started sessions that finish)
- Time-to-diagnosis vs manual investigation

**Accuracy**:
- Root cause accuracy (% of diagnoses that identify real issue)
- False positive rate (% of diagnoses that are incorrect)
- User confidence in recommendations (survey)

**Efficiency**:
- Average time saved per incident
- Reduction in mean time to resolution (MTTR)
- Cost per investigation (LLM tokens)

---

## 9. MVP Scope Definition

### 9.1 Included in MVP

**Core Features**:
- ✅ Orchestrator + 4 specialist agents
- ✅ Scratchpad-based agent handoff
- ✅ Kubernetes logs fetching
- ✅ Elasticsearch OR Prometheus (choose one for MVP)
- ✅ LLM-based code analysis
- ✅ Git blame integration
- ✅ Guided mode (menu-driven UX)
- ✅ Session management (create, resume, list, delete, export, import)
- ✅ Encryption (credentials, scratchpad, data files)
- ✅ Configurable confirmation levels
- ✅ Unit + integration tests

**Data Sources**:
- ✅ Kubernetes logs (kubectl)
- ✅ Elasticsearch logs OR Prometheus metrics (choose one)

**Code Analysis**:
- ✅ LLM-based code understanding
- ✅ Git blame for suspect lines
- ✅ Function extraction with context

**UX**:
- ✅ Guided mode only
- ✅ Terminal output with Rich formatting
- ✅ Markdown diagnosis file

### 9.2 Deferred to Post-MVP

**Features**:
- ❌ Conversational mode (natural language interaction)
- ❌ Async/parallel data fetching
- ❌ AST-based code analysis (tree-sitter)
- ❌ Jaeger traces integration
- ❌ External integrations (GitHub issues, Slack)
- ❌ Shortcuts and quick commands
- ❌ Configuration profiles
- ❌ Session replay with new data
- ❌ Learning from user patterns

**Data Sources**:
- ❌ Jaeger traces
- ❌ Local log files
- ❌ Additional metrics systems (Datadog, New Relic, etc.)

**Code Analysis**:
- ❌ Full PR/commit metadata from GitHub/GitLab
- ❌ Automated code patching
- ❌ Multi-repository dependency analysis

**UX**:
- ❌ Web UI
- ❌ VSCode extension
- ❌ Team collaboration features

---

## 10. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
- Project setup (Python, dependencies, structure)
- Configuration system (multi-level precedence)
- Encryption module (PBKDF2 + Fernet)
- Session management (create, resume, delete)
- Scratchpad read/write operations
- Unit tests for core utilities

### Phase 2: Data Collection (Weeks 3-4)
- Kubernetes fetcher (kubectl integration)
- Elasticsearch OR Prometheus fetcher (choose one)
- Query template system
- Retry logic with exponential backoff
- Data sampling and summarization
- Unit tests for fetchers

### Phase 3: Agent System (Weeks 5-7)
- LLM provider abstraction
- Orchestrator agent (UX flow)
- Data Fetcher agent (query construction)
- Pattern Analyzer agent (correlation, clustering)
- Code Inspector agent (symbol search, git blame)
- Root Cause Analyst agent (synthesis)
- Agent unit tests with mocked LLM

### Phase 4: User Experience (Week 8)
- Typer CLI interface
- Guided mode implementation
- Rich terminal output formatting
- Progress indicators and spinners
- Error handling UI
- Confirmation prompt system

### Phase 5: Integration & Testing (Week 9)
- End-to-end integration tests
- Session flow testing
- Error recovery testing
- Performance optimization
- Documentation (README, user guide)

### Phase 6: MVP Hardening (Week 10)
- Security review (credential handling, encryption)
- Edge case testing
- User acceptance testing
- Bug fixes and polish
- Release preparation

**Total Estimated Time**: 10 weeks for MVP

---

## 11. Open Questions & Deferred Decisions

### 11.1 To Be Resolved During Implementation

**Code Analysis Method**:
- Decision deferred: AST-based vs LLM-based vs hybrid
- Start with LLM-only, evaluate performance and accuracy
- Add tree-sitter if LLM struggles with large codebases

**Multi-Language Support**:
- Decision deferred: Per-language parsers vs universal approach
- Start with LLM-only (language-agnostic)
- Prioritize languages based on user feedback

**Token Optimization**:
- Determine actual token usage in practice
- Tune summarization strategies based on real sessions
- Implement budget warnings if costs become issue

### 11.2 Post-MVP Enhancements (Prioritized)

**High Priority**:
1. Conversational mode (natural language interaction)
2. Jaeger traces integration
3. Async/parallel data fetching
4. AST-based code analysis optimization

**Medium Priority**:
5. Configuration profiles and shortcuts
6. Session replay with new data
7. GitHub/GitLab API integration for PR metadata
8. Additional data source integrations

**Low Priority**:
9. Web UI for session viewing
10. Team collaboration features
11. Learning from user patterns
12. Automated patch generation

---

## 12. Glossary

**Agent**: Specialized LLM-powered component responsible for one aspect of the investigation (e.g., data fetching, pattern analysis, code inspection).

**Orchestrator**: The main agent that manages user interaction and coordinates specialist agents.

**Scratchpad**: Encrypted file containing shared state for all agents, structured in sections (problem description, data collected, pattern analysis, code inspection, final diagnosis).

**Session**: A single troubleshooting investigation with unique ID, stored in `~/.aletheia/sessions/{id}/`.

**Data Fetcher**: Agent responsible for collecting logs, metrics, and traces from external systems.

**Pattern Analyzer**: Agent that identifies anomalies, correlations, and error clusters in collected data.

**Code Inspector**: Agent that maps errors to source code, extracts suspect functions, and runs git blame.

**Root Cause Analyst**: Agent that synthesizes all findings into a root cause hypothesis with recommendations.

**Guided Mode**: Menu-driven interaction where user selects from numbered choices.

**Conversational Mode**: Natural language interaction with LLM-powered intent understanding (see Section 2.7).

**Session Key**: Encryption key derived from user password using PBKDF2, used to encrypt all session data.

**Template Query**: Pre-defined query structure (Elasticsearch DSL, PromQL) with placeholders for common use cases.

**LLM-First Pattern**: Architecture pattern where agents delegate ALL decision logic (parameter extraction, intent classification, routing) to the LLM via prompts, avoiding custom parsing code.

**Plugin**: Semantic Kernel function decorated with `@kernel_function` that exposes external tool operations (kubectl, git, HTTP APIs) to the LLM for automatic invocation.

---

## 13. Conversational Mode Architecture

###  13.1 Overview

**Conversational Mode** enables natural language interaction with Aletheia, allowing users to describe problems and ask questions without navigating menus. This mode leverages the **LLM-First pattern**, where ALL parameter extraction, intent understanding, and routing decisions are delegated to the LLM through carefully crafted prompts.

**Key Principle**: Agents build prompts and invoke the LLM; the LLM does all the reasoning, extraction, and decision-making. Agents do NOT implement custom parsing, extraction, or classification logic.

### 13.2 LLM-First Pattern

#### 13.2.1 Design Philosophy

Traditional agent systems often implement custom logic for tasks like:
- ❌ Regex patterns to extract pod names from user input
- ❌ Hardcoded intent-to-agent mapping dictionaries
- ❌ Custom parsers for stack traces or error messages
- ❌ Rule-based decision trees for routing

The **LLM-First Pattern** eliminates this custom logic by asking the LLM to do the work:

```python
# ❌ OLD WAY (Custom Extraction Logic)
def extract_pod_name(user_input: str) -> str:
    match = re.search(r'pod[:\s]+([a-z0-9-]+)', user_input)
    return match.group(1) if match else "default"

# ✅ NEW WAY (LLM-First Pattern)
async def execute(self):
    conversation = self.scratchpad.get_conversation_context()
    prompt = f"""
    Based on this conversation:
    {conversation}
    
    Extract the pod name the user wants to investigate.
    Use kubernetes.fetch_kubernetes_logs() to collect logs.
    """
    response = await self.invoke(prompt)  # LLM extracts pod name and calls plugin
```

**Benefits**:
1. **Flexibility**: LLM handles variations ("payments pod", "pod: payments-svc", "the payments service")
2. **Maintainability**: No regex patterns or parsers to maintain
3. **Context Awareness**: LLM considers full conversation history
4. **Natural Handling**: Works with ambiguous or incomplete information
5. **Extensibility**: Adding new parameters doesn't require code changes

#### 13.2.2 Core Principles

**1. Agents Build Prompts, LLMs Extract Parameters**

```python
# Agent responsibility: Build prompt with conversation context
prompt = f"""
You are a data fetcher agent.

Conversation history:
{self.scratchpad.get_conversation_context()}

Problem description:
{self.read_scratchpad("PROBLEM_DESCRIPTION")}

Available plugins:
- kubernetes.fetch_kubernetes_logs(pod, namespace, since, tail_lines)
- prometheus.fetch_prometheus_metrics(query, start, end, step)

Task: Extract parameters from the conversation and use plugins to collect data.
"""

# LLM responsibility: Extract pod="payments-svc", namespace="default", etc.
response = await self.invoke(prompt)
```

**2. Plugins for ALL External Operations**

```python
# ✅ CORRECT: Register plugins, let LLM call them
self.kernel.add_plugin(KubernetesPlugin(config), plugin_name="kubernetes")
self.kernel.add_plugin(PrometheusPlugin(config), plugin_name="prometheus")

# LLM automatically calls:
# kubernetes.fetch_kubernetes_logs(pod="payments-svc", namespace="production")
```

```python
# ❌ WRONG: Direct subprocess calls in agent code
logs = subprocess.run(["kubectl", "logs", pod_name], capture_output=True)
```

**3. No Hardcoded Routing Logic**

```python
# ❌ WRONG: Hardcoded intent-to-agent mapping
intent_to_agent = {
    "collect_data": data_fetcher,
    "analyze_patterns": pattern_analyzer,
    "inspect_code": code_inspector
}
next_agent = intent_to_agent[classified_intent]
```

```python
# ✅ CORRECT: LLM decides routing based on conversation
prompt = f"""
Based on this conversation and investigation state:
{conversation_history}
{investigation_state}

Which agent should run next and why?
Available agents: data_fetcher, pattern_analyzer, code_inspector, root_cause_analyst
"""
decision = await self.invoke(prompt)
# LLM response: "route to data_fetcher because no data collected yet"
```

**4. Conversation History is the Context**

```python
# Agent reads conversation from scratchpad
conversation = self.scratchpad.get_conversation_context()

# Agent includes conversation in prompt
prompt = f"Based on this conversation:\n{conversation}\n\nYour task: ..."

# LLM has full context to make informed decisions
response = await self.invoke(prompt)
```

**5. LLM Generates Clarifying Questions**

```python
# ❌ WRONG: Hardcoded question templates
if missing_namespace:
    question = "Which namespace is the pod in? (default, production, staging)"
```

```python
# ✅ CORRECT: LLM generates contextual questions
prompt = f"""
Conversation: {conversation}
Missing information: namespace

Generate a natural, helpful question to ask the user.
"""
question = await self.invoke(prompt)
# LLM: "I see you're investigating payments-svc. Which namespace is it in?"
```

### 13.3 Conversational Flow

#### 13.3.1 Session Start

```
User: "Why is payments-svc returning 500 errors in production?"
  ↓
Orchestrator:
  1. Appends user message to CONVERSATION_HISTORY section in scratchpad
  2. Reads full conversation context
  3. Invokes LLM with intent understanding prompt
  ↓
LLM Response:
  {
    "intent": "investigate_errors",
    "confidence": 0.95,
    "parameters": {
      "service": "payments-svc",
      "namespace": "production",
      "error_type": "500 errors"
    },
    "next_action": "collect_data"
  }
  ↓
Orchestrator:
  1. Invokes LLM with routing decision prompt
  2. LLM decides to route to data_fetcher
  3. Appends agent's response to conversation
```

#### 13.3.2 Data Collection

```
Data Fetcher Agent:
  1. Reads CONVERSATION_HISTORY from scratchpad
  2. Reads PROBLEM_DESCRIPTION from scratchpad
  3. Registers KubernetesPlugin and PrometheusPlugin with kernel
  4. Builds prompt with conversation context
  5. Invokes LLM
  ↓
LLM Processing (via FunctionChoiceBehavior.Auto()):
  1. Extracts parameters: pod="payments-svc", namespace="production", since="1h"
  2. Calls kubernetes.fetch_kubernetes_logs(pod="payments-svc", namespace="production", since="1h")
  3. Receives log data from plugin
  4. Synthesizes summary in natural language
  ↓
LLM Response:
  "I collected 200 log lines from payments-svc pod in production namespace.
   Found 47 ERROR messages, mostly 'nil pointer dereference at features.go:57'.
   Circuit breaker opened to promo-svc at 08:05:15."
  ↓
Data Fetcher Agent:
  1. Writes DATA_COLLECTED section to scratchpad
  2. Appends agent response to CONVERSATION_HISTORY
  3. Returns control to orchestrator
```

#### 13.3.3 Pattern Analysis

```
Orchestrator:
  1. Reads updated conversation
  2. Invokes LLM with routing decision prompt
  3. LLM decides to route to pattern_analyzer
  ↓
Pattern Analyzer Agent:
  1. Reads CONVERSATION_HISTORY
  2. Reads DATA_COLLECTED section
  3. Invokes LLM with pattern analysis prompt
  ↓
LLM Analysis:
  "Based on collected data:
   - Error rate spike at 08:05 (36x increase)
   - Deployment of payments-svc v1.19 at 08:04
   - 45 panics with same stack trace: features.go:57
   
   Pattern: Nil pointer dereference introduced in recent deployment"
  ↓
Pattern Analyzer Agent:
  1. Writes PATTERN_ANALYSIS section
  2. Appends findings to conversation
  3. Returns to orchestrator
```

#### 13.3.4 User Clarification

```
Code Inspector Agent:
  1. Reads conversation and pattern analysis
  2. LLM needs repository path to run git blame
  ↓
LLM Response:
  "I need access to the source code repository to analyze the error at features.go:57.
   What's the path to the git repository for payments-svc?"
  ↓
Agent:
  1. Appends clarifying question to conversation
  2. Returns to orchestrator
  ↓
Orchestrator:
  1. Displays question to user
  2. Waits for user response
  ↓
User: "/Users/alice/repos/payments-svc"
  ↓
Orchestrator:
  1. Appends user response to conversation
  2. Routes back to code_inspector
  ↓
Code Inspector:
  1. Reads updated conversation
  2. LLM extracts repository path: "/Users/alice/repos/payments-svc"
  3. LLM calls git.git_blame() plugin
  4. Continues analysis
```

#### 13.3.5 Final Diagnosis

```
Root Cause Analyst Agent:
  1. Reads ALL scratchpad sections:
     - CONVERSATION_HISTORY
     - PROBLEM_DESCRIPTION
     - DATA_COLLECTED
     - PATTERN_ANALYSIS
     - CODE_INSPECTION
  2. Builds synthesis prompt with full context
  3. Invokes LLM
  ↓
LLM Synthesis:
  "Root Cause: Nil pointer dereference in features.go:57
   
   Evidence:
   - 45 panics with identical stack trace
   - Recent refactor (commit a3f9c2d) by john.doe removed nil check
   - Temporal correlation: errors started 70s after v1.19 deployment
   
   Confidence: 0.92
   
   Recommendations:
   [IMMEDIATE] Rollback to v1.18
   [HIGH] Add nil check in IsEnabled()
   [MEDIUM] Add unit tests for nil Feature handling"
  ↓
Root Cause Analyst:
  1. Writes FINAL_DIAGNOSIS section
  2. Appends diagnosis to conversation
  ↓
Orchestrator:
  1. Formats diagnosis for display
  2. Presents to user with action menu
```

### 13.4 Prompt Engineering Patterns

#### 13.4.1 Intent Understanding Prompt

```
You are an orchestrator agent for the Aletheia troubleshooting system.

**Conversation History**:
{conversation_history}

**Current Investigation State**:
{investigation_state}

**Your Task**: Understand the user's intent and extract relevant parameters.

**Output** (JSON format):
{
  "intent": "investigate_errors|collect_data|analyze_patterns|inspect_code|diagnose|clarify",
  "confidence": 0.0-1.0,
  "parameters": {
    // Extract ANY relevant parameters from natural language
    // Examples: service_name, pod_name, namespace, time_window, error_type
  },
  "reasoning": "Why you classified this intent",
  "clarification_needed": "Optional: what to ask user if unclear"
}

**Guidelines**:
- Extract parameters from natural language variations
- Consider conversation context, not just the last message
- If ambiguous, set intent="clarify" and provide clarification_needed
- Be specific with extracted parameters
```

#### 13.4.2 Parameter Extraction Prompt

```
You are a data fetcher agent.

**Conversation**:
{conversation_history}

**Problem**:
{problem_description}

**Available Plugins**:
- kubernetes.fetch_kubernetes_logs(pod: str, namespace: str, since: str, tail_lines: int)
- prometheus.fetch_prometheus_metrics(query: str, start: str, end: str, step: str)

**Task**: 
1. Extract parameters from the conversation (pod name, namespace, time window)
2. Use the appropriate plugin to collect data
3. Summarize what you collected

**Examples**:
- "payments service" → pod="payments-svc"
- "in production" → namespace="production"
- "last 2 hours" → since="2h"
- "since 8am" → calculate time difference

**Important**: 
- Call plugins directly (FunctionChoiceBehavior.Auto enabled)
- If parameters missing, ask for clarification
- Provide natural language summary of results
```

#### 13.4.3 Agent Routing Prompt

```
You are deciding which specialist agent to invoke next.

**Conversation**:
{conversation_history}

**Investigation State**:
- Data collected: {data_collected}
- Pattern analysis done: {pattern_analysis_done}
- Code inspected: {code_inspected}
- Agents run: {agents_run}

**Available Agents**:
1. data_fetcher: Collects logs/metrics/traces
   Prerequisites: Service or pod name identified
   
2. pattern_analyzer: Finds anomalies and correlations
   Prerequisites: DATA_COLLECTED section exists
   
3. code_inspector: Maps errors to code, runs git blame
   Prerequisites: PATTERN_ANALYSIS exists, repository paths known
   
4. root_cause_analyst: Synthesizes all findings
   Prerequisites: PATTERN_ANALYSIS exists (CODE_INSPECTION optional)

**Output** (JSON):
{
  "action": "route_to_agent|ask_clarification|complete",
  "agent": "data_fetcher|pattern_analyzer|code_inspector|root_cause_analyst|null",
  "reasoning": "Why this agent is appropriate",
  "prerequisites_met": true|false,
  "suggested_response": "What to tell the user"
}

**Rules**:
- Check prerequisites before routing
- Follow natural flow: data → patterns → code → diagnosis
- If prerequisites not met, set action="ask_clarification"
- If investigation complete, set action="complete"
```

#### 13.4.4 Clarification Question Prompt

```
You are an agent in the Aletheia troubleshooting system.

**Conversation**:
{conversation_history}

**Missing Information**: {missing_info}

**Task**: Generate a natural, helpful clarifying question.

**Guidelines**:
- Be specific about what you need
- Explain why you need it
- Provide examples if helpful
- Keep it conversational

**Example**:
Missing: namespace
Output: "I see you're investigating payments-svc. Which Kubernetes namespace 
is it running in? (Common examples: default, production, staging)"
```

### 13.5 Why No Custom Extraction Logic?

#### 13.5.1 Problems with Custom Extraction

**Brittleness**: Regex patterns break with variations
```python
# Handles: "pod: payments-svc"
pattern = r'pod:\s+([a-z0-9-]+)'

# Breaks with: "payments pod", "the payments service", "pod called payments-svc"
```

**Maintenance Burden**: Every new variation requires code changes
```python
# Need to handle:
# "in the last 2 hours"
# "since 2 hours ago"
# "2h ago"
# "from 8am to 10am"
# → Endless regex updates
```

**Context Blindness**: Custom logic can't consider conversation history
```python
# First message: "I'm looking at the payments service"
# Second message: "Check the production namespace"
# → Hardcoded parser can't correlate "it" with "payments service"
```

**Lack of Flexibility**: Can't handle ambiguity or missing information gracefully
```python
# User: "Check the pod"
# → Which pod? Custom logic must hardcode every clarification case
```

#### 13.5.2 Advantages of LLM-Delegation

**Natural Language Understanding**: LLM handles variations effortlessly
```python
prompt = f"Extract the pod name from: {user_input}"

# Works with:
# "payments pod" → "payments-svc"
# "the pod for payments" → "payments-svc"
# "check payments-svc" → "payments-svc"
# "payment service pod" → "payments-svc"
```

**Context Awareness**: LLM considers full conversation
```python
# Conversation:
# User: "I'm investigating payments-svc"
# Agent: "What namespace?"
# User: "production"

# LLM extracts BOTH from conversation:
# {pod: "payments-svc", namespace: "production"}
```

**Graceful Degradation**: LLM generates appropriate clarifying questions
```python
# User: "Check the logs"
# LLM: "Which service's logs would you like me to check?"
```

**Adaptability**: Adding new parameters doesn't require code changes
```python
# To support "container" parameter:
# ❌ Custom: Add regex, update parser, handle edge cases (100+ LOC)
# ✅ LLM-First: Update prompt description (2 lines)
```

#### 13.5.3 When to Use Custom Logic

**Rule of Thumb**: If the LLM can do it based on conversation context, delegate it to the LLM.

**Exceptions** (use custom logic):
1. **Performance-Critical Operations**: Parsing megabytes of binary data
2. **Deterministic Validation**: Checking if file exists, validating UUID format
3. **External Tool Interfaces**: Actual subprocess execution (but expose via plugins)

**Example**:
```python
# ✅ Custom logic for validation
if not os.path.exists(repository_path):
    raise ValueError(f"Repository not found: {repository_path}")

# ✅ Custom logic for subprocess execution (in plugin)
@kernel_function
def fetch_logs(self, pod: str, namespace: str):
    result = subprocess.run(["kubectl", "logs", pod, "-n", namespace])
    return result.stdout

# ❌ Custom logic for extraction (delegate to LLM)
# Don't: pod_match = re.search(r'pod:\s+([a-z0-9-]+)', conversation)
```

### 13.6 Implementation Checklist

When implementing conversational features, ensure:

- [ ] **Agent reads conversation context**: Use `scratchpad.get_conversation_context()`
- [ ] **Agent builds prompts with context**: Include conversation in all LLM calls
- [ ] **No custom extraction code**: No regex, string parsing, or hardcoded patterns
- [ ] **Plugins registered**: All external tools exposed via `@kernel_function`
- [ ] **FunctionChoiceBehavior.Auto()**: LLM can call plugins automatically
- [ ] **Natural language responses**: Agent appends LLM responses to conversation
- [ ] **No hardcoded routing**: LLM decides next agent based on investigation state
- [ ] **Clarifying questions via LLM**: No hardcoded question templates

**Verification Tests**:
1. Mock LLM invocation and verify conversation context in prompt
2. Verify NO custom extraction methods in agent code
3. Verify plugins registered in agent `__init__`
4. Verify agent appends to CONVERSATION_HISTORY section
5. Integration test with real LLM (mocked plugins)

---

## 14. Appendix

### A. Example Session Transcript (Conversational Mode)

```bash
$ aletheia session open --name incident-2025-10-11

> [Aletheia] Enter session password: ********
> [Aletheia] Session INC-8F2A created.

> [Aletheia] How can I help you troubleshoot today?

> [User]: Why is payments-svc returning 500 errors in production?

> [Aletheia] I'll investigate that for you. Let me collect logs from payments-svc in production namespace...

⏳ Collecting data... (elapsed: 3s)

> [Aletheia] ✅ I found 200 log entries from payments-svc in the last hour. Here's what I discovered:
  • 47 ERROR level messages
  • Top error: "nil pointer dereference" (45 occurrences)
  • Circuit breaker opened to promo-svc at 08:05:15
  
The errors started around 08:05. Would you like me to fetch metrics to see if there was a traffic spike?

> [User]: Yes, check error rate and latency

> [Aletheia] Fetching Prometheus metrics for error rate and P95 latency...

⏳ Analyzing patterns... (elapsed: 2s)

> [Aletheia] ✅ Pattern analysis complete:
  • Error rate spiked from 0.2% to 7.3% at 08:05 (36x increase)
  • Temporal correlation: payments-svc v1.19 deployed at 08:04
  • 45 panics with identical stack trace: charge.go:112 → features.go:57
  
This looks like a nil pointer dereference introduced in v1.19. Do you have access to the source code repository?

> [User]: Yes, it's at /Users/alice/repos/payments-svc

> [Aletheia] Thanks! Let me analyze the code...

⏳ Inspecting code... (elapsed: 4s)

> [Aletheia] ✅ Code analysis complete:
  • Error at features.go:57 in IsEnabled() function
  • Git blame shows recent change by john.doe (commit a3f9c2d, 2025-10-10)
  • Change: "Refactor feature flag loading" - removed nil check
  • Caller at promo.go:88 doesn't guard against nil

Let me synthesize the diagnosis...

⏳ Generating diagnosis... (elapsed: 2s)

> [Aletheia] ✅ Diagnosis complete. Here's what I found:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ROOT CAUSE ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROBABLE CAUSE:
Nil pointer dereference in featurekit/features.go:57

DESCRIPTION:
The IsEnabled function dereferences f.Enabled without checking if f is nil.
A recent refactor (commit a3f9c2d on 2025-10-10 by john.doe) changed feature
flag loading, allowing Get() to return nil. Callers in payments-svc don't
guard against this condition.

EVIDENCE:
• 45 panics with stack trace: charge.go:112 → features.go:57 → promo.go:88
• Error spike at 08:05 (70 seconds after v1.19 deployment)
• Git blame: Recent change "Refactor feature flag loading"
• No nil checks in caller at promo.go:88

CONFIDENCE: 0.92

RECOMMENDED ACTIONS:
[IMMEDIATE] Rollback payments-svc to v1.18 to stop customer impact
[HIGH]      Apply nil-safe patch to IsEnabled function
[MEDIUM]    Add unit test for nil Feature handling
[LOW]       Review all callers of featurekit.Get() for nil checks

> [Aletheia] What would you like to do?

> [User]: Show me the proposed patch

> [Aletheia] Here's the proposed patch for features.go:

--- features.go.original
+++ features.go.patched
@@ -54,7 +54,10 @@
 type Feature struct { Name string; Enabled *bool }

 func IsEnabled(f *Feature) bool {
-    return *f.Enabled
+    if f == nil || f.Enabled == nil {
+        return false
+    }
+    return *f.Enabled
 }

> [User]: Perfect, thanks! Save the diagnosis

> [Aletheia] ✅ Diagnosis saved to:
  ~/.aletheia/sessions/INC-8F2A/diagnosis.md

You can resume this session anytime with:
  aletheia session resume INC-8F2A

> [User]: End session

> [Aletheia] Session ended. Investigation complete.
```

### B. Example Session Transcript (Guided Mode)

```bash
$ aletheia session open --name incident-2025-10-11

> [Aletheia] Enter session password: ********
> [Aletheia] Session INC-8F2A created.
> [Aletheia] Select interaction mode:
1. Guided (menu-driven)
2. Conversational (natural language)

> [User] → 1

> [Aletheia] Describe the problem:
> [User]: Checkout API 500s since ~08:05 CEST after payments-svc v1.19 rollout

> [Aletheia] Choose a time window:
1. Last 30m
2. Last 2h
3. Custom…

> [User] → 2

> [Aletheia] Select system/cluster:
1. Kubernetes (prod-eu)
2. Elasticsearch (centralized logs)
3. Both

> [User] → 1

> [Aletheia] What data to fetch first?
1. Logs: Kubernetes pods
2. Metrics: Prometheus
3. Both in parallel (experimental)

> [User] → 1

> [Aletheia] Kubernetes configuration:
• Context: prod-eu
• Namespace: commerce
• Pod selector: app=payments-svc
• Container: app
Confirm? [Y/n]

> [User] → Y

> [Aletheia] Fetching logs... ⏳ (elapsed: 3s)
> [Aletheia] ✅ Collected 200 logs (47 errors found)
> [Aletheia] Top error clusters:
  • "nil pointer dereference" (45 occurrences)
  • "circuit open to promo-svc" (2 occurrences)

> [Aletheia] Fetch additional data?
1. Metrics: Prometheus (error rate, latency)
2. Skip to code analysis

> [User] → 1

> [Aletheia] Prometheus metrics:
  [x] Error rate (5xx)
  [x] P95 latency
  [ ] CPU/Memory saturation
  [ ] Custom query

> [User] → (press Enter to accept)

> [Aletheia] Fetching metrics... ⏳ (elapsed: 2s)
> [Aletheia] ✅ Metrics collected
> [Aletheia] Findings:
  • Error rate: 0.2/s → 7.3/s at 08:05
  • P95 latency: 180ms → 2.4s at 08:05

> [Aletheia] [Pattern Analyzer] Analyzing data... ⏳ (elapsed: 8s)
> [Aletheia] ✅ Pattern analysis complete
> [Aletheia] Key findings:
  • Error spike correlates with v1.19 deployment (08:04)
  • Stack trace pattern: charge.go:112 → features.go:57 → promo.go:88

> [Aletheia] Map stack traces to code repositories?
> [Aletheia] Detected services: payments-svc, featurekit
> [Aletheia] Suggested repositories:
1. git@company:commerce/payments-svc.git
2. git@company:platform/featurekit.git
3. Add another repository
4. Skip code analysis

> [User] → 1,2

> [Aletheia] Provide local repository paths:
> [User] payments-svc: /home/user/src/payments-svc
> [User] featurekit: /home/user/src/featurekit

> [Aletheia] Validating repositories... ✅
> [Aletheia] ⚠️  Warning: payments-svc is on branch 'main' (commit 89a2b3f)
> Expected commit from deployment: a3f9c2d
> Continue anyway? [y/N]

> [User] → y

> [Aletheia] [Code Inspector] Analyzing source code... ⏳ (elapsed: 10s)
> [Aletheia] ✅ Code inspection complete
> [Aletheia] Suspect code locations:
  • featurekit/features.go:57 (IsEnabled function)
  • payments-svc/internal/discounts/promo.go:88 (applyPromoIfEligible)

> [Aletheia] [Root Cause Analyst] Synthesizing findings... ⏳ (elapsed: 15s)

> [Aletheia]
================================================================================
ROOT CAUSE ANALYSIS (Confidence: 0.86)
================================================================================

PROBABLE CAUSE:
Nil pointer dereference in featurekit/features.go:57

DESCRIPTION:
The IsEnabled function dereferences f.Enabled without checking if f is nil.
A recent refactor (commit a3f9c2d on 2025-10-10 by john.doe) changed feature
flag loading, allowing Get() to return nil. Callers in payments-svc don't
guard against this condition.

EVIDENCE:
• 45 panics with stack trace: charge.go:112 → features.go:57 → promo.go:88
• Error spike at 08:05 (70 seconds after v1.19 deployment at 08:04)
• Git blame: Recent change by john.doe "Refactor feature flag loading"
• No nil checks in caller at promo.go:88

RECOMMENDED ACTIONS:
[IMMEDIATE] Rollback payments-svc to v1.18 to stop customer impact
[HIGH]      Apply nil-safe patch to IsEnabled function (see below)
[MEDIUM]    Add unit test for nil Feature handling
[LOW]       Review all callers of featurekit.Get() for nil checks

Choose an action:
1. Show proposed patch
2. Open features.go:57 in $EDITOR
3. Save full diagnosis to file
4. Export session for sharing
5. End session

> [User] → 1

> [Aletheia] Proposed patch for featurekit/features.go:

--- features.go.original
+++ features.go.patched
@@ -54,7 +54,10 @@
 type Feature struct { Name string; Enabled *bool }

 func IsEnabled(f *Feature) bool {
-    return *f.Enabled
+    if f == nil || f.Enabled == nil {
+        return false
+    }
+    return *f.Enabled
 }

Apply this patch? [y/N]

> [User] → N

> [Aletheia] Diagnosis saved to:
  ~/.aletheia/sessions/INC-8F2A/diagnosis.md

> [Aletheia] Session INC-8F2A saved. You can resume with:
  aletheia session resume INC-8F2A

> [Aletheia] End session? [Y/n]

> [User] → Y

> [Aletheia] Session ended. Investigation complete.
```

---

**End of Specification Document**
