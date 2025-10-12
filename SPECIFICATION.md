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
- Routes between specialist agents
- Presents findings to user
- Handles error recovery and retry logic

#### Data Fetcher Agent
- Executes CLI tools (kubectl, curl, promtool, etc.)
- Constructs queries (Elasticsearch DSL, PromQL) using templates + LLM fallback
- Samples data intelligently (all errors + random sample of others)
- Writes summaries + file references to scratchpad
- 3 retries with exponential backoff on failures

#### Pattern Analyzer Agent
- Reads DATA_COLLECTED section from scratchpad
- Identifies anomalies (spikes, drops, outliers)
- Correlates across logs, metrics, traces
- Clusters error messages
- Builds incident timeline
- Writes PATTERN_ANALYSIS to scratchpad

#### Code Inspector Agent
- Reads PATTERN_ANALYSIS section
- Maps stack traces to source files in user-provided repositories
- Extracts suspect functions and context
- Runs `git blame` on suspect lines
- Analyzes caller relationships (configurable depth)
- Writes CODE_INSPECTION to scratchpad

#### Root Cause Analyst Agent
- Reads entire scratchpad + code files
- Synthesizes findings into root cause hypothesis
- Assigns confidence score
- Generates actionable recommendations
- Writes FINAL_DIAGNOSIS to scratchpad

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

**Custom Abstraction Layer**: Aletheia implements its own LLM provider abstraction for full control and minimal dependencies.

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

**Conversational Mode**: Natural language interaction with LLM-powered intent understanding.

**Session Key**: Encryption key derived from user password using PBKDF2, used to encrypt all session data.

**Template Query**: Pre-defined query structure (Elasticsearch DSL, PromQL) with placeholders for common use cases.

---

## 13. Appendix

### A. Example Session Transcript (Guided Mode)

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
