# Aletheia (ἀλήθεια)

> **Aletheia** (ἀλήθεια) — Ancient Greek for "truth" or "un-concealment": bringing what's hidden into the open.

Aletheia is a modular, AI-powered troubleshooting framework for SREs and system administrators. It orchestrates specialized LLM agents to collect and analyze observability data (logs, metrics, traces), inspect code, and generate actionable root cause hypotheses.

---

## Overview

Aletheia provides an interactive, agent-based workflow for troubleshooting distributed systems. It leverages Large Language Models (LLMs) and specialized plugins to automate data collection, pattern analysis, and root cause investigation across Kubernetes, Prometheus, log files, and more. The CLI offers a conversational interface for managing troubleshooting sessions, running investigations, and exploring demo scenarios.

### Available agents

- **Orchestrator** - Routes requests to appropriate specialist agents and relays their output
- **Kubernetes Data Fetcher** - Collects Kubernetes logs, pod information, and cluster health data
- **AWS Agent** - Manages AWS resources, logs, and AWS-specific investigations
- **AWS Managed Prometheus** - Handles AWS Managed Prometheus metrics, CPU/memory data, and PromQL queries
- **Azure Agent** - Manages Azure resources and performs Azure-specific queries and investigations
- **Code Analyzer** - Analyzes code repositories using Claude or GitHub Copilot for code review and inspection
- **Log File Data Fetcher** - Reads and analyzes local log files
- **PCAP File Data Fetcher** - Analyzes packet capture (PCAP) files for network troubleshooting
- **Network Agent** - Handles DNS queries, IP connectivity, port scanning, and general network tools
- **Security Agent** - Performs security testing and analysis using tools like httpx and sslscan
- **SysDiag Agent** - Provides system diagnostics and troubleshooting capabilities

## Installation

Aletheia requires Python 3.12 and uses [uv](https://github.com/astral-sh/uv) for dependency management.

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone the repository

```bash
git clone https://github.com/your-org/aletheia.git
cd aletheia
```

### 3. Create venv and install dependencies

```bash
uv venv --python python3.12
source ./.venv/bin/activate
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt  # for development
```

### 4. (Optional) Install in editable mode

```bash
uv pip install -e .
```

## Usage

Aletheia provides multiple interfaces for managing troubleshooting sessions and running investigations:

- **TUI (Terminal)**: Interactive command-line interface with `aletheia session open`
- **Web UI**: Browser-based interface with `aletheia serve`
- **Telegram Bot**: Messaging interface with `aletheia telegram serve`

### Command Line Interface

Run the CLI:

```bash
aletheia --help
```

#### Session Management

- **Open a new session:**

  ```bash
  aletheia session open
  ```

  Options:
  - `--name, -n`: Session name
  - `--verbose, -v`: Show all external commands and their output
  - `--very-verbose, -vv`: Enable trace logging with prompts, commands, and full details
  - `--unsafe`: Use plaintext storage (not recommended)

- **List sessions:**

  ```bash
  aletheia session list
  ```


- **Delete a session:**

  ```bash
  aletheia session delete <session_id>
  ```

- **Export a session:**


  ```bash
  aletheia session export <session_id> --output <file>
  ```

- **View session:**

  ```bash
  aletheia session view <session_id> 
  ```

- **View session timeline:**

  ```bash
  aletheia session timeline <session_id> 
  ```  


#### Version

```bash
aletheia version
```


## Configuration

Aletheia uses a simple, prioritized configuration system with platformdirs for standard config locations.

### Configuration Hierarchy

Configuration is loaded in the following order (highest to lowest priority):

1. **Explicit values** - Passed directly to the Config class
2. **Environment variables** - Prefixed with `ALETHEIA_`
3. **YAML config file** - Located at:
   - Linux: `~/.config/aletheia/config.yaml`
   - macOS: `~/Library/Application Support/aletheia/config.yaml`
   - Windows: `%LOCALAPPDATA%\aletheia\config.yaml`
4. **Default values** - Built-in defaults

### Configuration Directory Structure

```
{user_config_path}/aletheia/
├── config.yaml              # Main configuration file
├── skills/                  # Skills directory
│   ├── aws/                # Agent-specific skills
│   │   └── ec2_route_tables/
│   │       └── SKILL.md
│   └── kubernetes_data_fetcher/
│       └── examine_thread_dump/
│           └── SKILL.md
└── instructions/           # Custom agent instructions
    ├── agent1.txt
    └── agent2.txt
```

### Environment Variables

All configuration can be set via environment variables with the `ALETHEIA_` prefix:

```bash
# LLM Configuration
export ALETHEIA_LLM_DEFAULT_MODEL=gpt-4o
export ALETHEIA_LLM_TEMPERATURE=0.2
export ALETHEIA_CODE_ANALYZER=claude

# Cost Configuration
export ALETHEIA_COST_PER_INPUT_TOKEN=0.0025
export ALETHEIA_COST_PER_OUTPUT_TOKEN=0.01

# Prometheus Configuration
export ALETHEIA_PROMETHEUS_ENDPOINT=https://prometheus.example.com
export ALETHEIA_PROMETHEUS_TIMEOUT_SECONDS=30
export ALETHEIA_PROMETHEUS_CREDENTIALS_TYPE=env

# Directory Configuration
export ALETHEIA_SKILLS_DIRECTORY=/custom/path/to/skills
export ALETHEIA_CUSTOM_INSTRUCTIONS_DIR=/custom/path/to/instructions
export ALETHEIA_MCP_SERVERS_YAML=/path/to/mcp-servers.yaml

# Telegram Bot Configuration
export ALETHEIA_TELEGRAM_BOT_TOKEN=your_bot_token_here
export ALETHEIA_TELEGRAM_ALLOWED_USERS=123456789,987654321
export ALETHEIA_TELEGRAM_SESSION_TIMEOUT=30
```

### YAML Configuration

Create a `config.yaml` file in your config directory. You can use the provided example as a starting point:

```bash
# Copy the example config to your config directory
cp config.yaml.example ~/.config/aletheia/config.yaml
# (or ~/Library/Application Support/aletheia/config.yaml on macOS)
```

Example configuration:

```yaml
# LLM Configuration
llm_default_model: gpt-4o
llm_temperature: 0.2
code_analyzer: claude

# Cost Configuration
cost_per_input_token: 0.0025
cost_per_output_token: 0.01

# Prometheus Configuration
prometheus_endpoint: https://prometheus.example.com
prometheus_timeout_seconds: 30
prometheus_credentials_type: env

# Directory Configuration (optional, defaults shown)
# skills_directory: /path/to/skills
# custom_instructions_dir: /path/to/instructions
# mcp_servers_yaml: /path/to/mcp-servers.yaml

# Telegram Bot Configuration (optional)
# telegram_bot_token: your_bot_token_here
# telegram_allowed_users: [123456789, 987654321]
# telegram_session_timeout: 30
```

See [config.yaml.example](config.yaml.example) for a complete configuration template with detailed comments.

### Active Configuration Options

| Configuration Key | Description | Default Value |
|------------------|-------------|---------------|
| `llm_default_model` | Default LLM model for agents | `gpt-4o` |
| `llm_temperature` | Temperature for LLM responses (0.0-1.0) | `0.2` |
| `code_analyzer` | Code analyzer to use (claude, copilot) | `""` |
| `cost_per_input_token` | Cost per input token | `0.0` |
| `cost_per_output_token` | Cost per output token | `0.0` |
| `prometheus_endpoint` | Prometheus server URL | `None` |
| `prometheus_timeout_seconds` | Request timeout for Prometheus | `10` |
| `prometheus_credentials_type` | Credential type (env, keychain, encrypted_file) | `env` |
| `skills_directory` | Path to skills directory | `{config_dir}/skills` |
| `custom_instructions_dir` | Path to custom instructions | `{config_dir}/instructions` |
| `mcp_servers_yaml` | Path to MCP servers config | `None` |
| `temp_folder` | Temporary file storage | `/tmp/aletheia` |
| `telegram_bot_token` | Telegram bot API token | `None` |
| `telegram_allowed_users` | List of allowed Telegram user IDs | `[]` |
| `telegram_session_timeout` | Session timeout in minutes | `30` |

### Custom Agent Instructions

Custom instructions for specific agents can be added to the `instructions/` directory:

```bash
# Example: Create custom instructions for the AWS agent
echo "Always use us-west-2 region" > ~/.config/aletheia/instructions/aws.txt
```

### Skills Configuration

Skills are organized by agent name in subdirectories. Each skill is a folder containing a `SKILL.md` file:

```
skills/
├── aws/
│   └── ec2_route_tables/
│       └── SKILL.md
└── kubernetes_data_fetcher/
    └── examine_thread_dump/
        └── SKILL.md
```

See `aletheia/config.py` for the complete configuration schema and advanced usage.

### Azure OpenAI
Aletheia needs three environment variables to be set to work with Azure OpenAI:

```bash
AZURE_OPENAI_API_KEY=<azure openai api key >
AZURE_OPENAI_ENDPOINT=<azure openai endpoint >
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=<azure deployment name>
```

### OpenAI (or Ollama)
To use Aletheia with Ollama the following environment variables must be set:

```bash
ALETHEIA_OPENAI_API_KEY=<openai api key>
ALETHEIA_OPENAI_ENDPOINT=<openai endpoint>
ALETHEIA_OPENAI_MODEL=<openai model>
```

For instance, to use Ollama on the local machine:

```bash
ALETHEIA_OPENAI_API_KEY=none
ALETHEIA_OPENAI_ENDPOINT=http://127.0.0.1:11434/v1
ALETHEIA_OPENAI_MODEL=gpt-oss:20b
```
          

in which `instructions.md` could be:

```markdown
- ALWAYS answer in rhymes
- ALWAYS add a funny kubernetes joke at the end
```

## Knowledge

Aletheia provides a knowledge base management system using ChromaDB for storing and retrieving troubleshooting documentation, runbooks, and other reference materials. The knowledge base uses vector embeddings for semantic search, allowing agents to find relevant information during investigations.

### Knowledge Base Commands

The `aletheia knowledge` command group provides tools to manage the knowledge base:

#### Add a Document

Add a Markdown document to the knowledge base:

```bash
aletheia knowledge add <document_id> <path_to_markdown_file> [--metadata <json>]
```

**Arguments:**
- `document_id`: Unique identifier for the document
- `path_to_markdown_file`: Path to the Markdown file to add

**Options:**
- `--metadata, -m`: Metadata as JSON string (e.g., `'{"category": "kubernetes", "priority": "high"}'`)

**Example:**
```bash
aletheia knowledge add k8s-troubleshooting /path/to/k8s-guide.md --metadata '{"category":"kubernetes"}'
```

#### Delete a Document

Remove a document from the knowledge base:

```bash
aletheia knowledge delete <document_id>
```

**Arguments:**
- `document_id`: ID of the document to delete

**Example:**
```bash
aletheia knowledge delete k8s-troubleshooting
```

#### List Documents

View all documents stored in the knowledge base:

```bash
aletheia knowledge list
```

This displays a table with:
- Document ID
- Content preview (first 75 characters)

**Example output:**
```
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Document ID          ┃ Content Preview                      ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ k8s-troubleshooting  │ # Kubernetes Troubleshooting Guide... │
└──────────────────────┴──────────────────────────────────────┘
```

### How Agents Use Knowledge

During investigations, agents can query the knowledge base to:
1. Find relevant troubleshooting procedures
2. Retrieve reference documentation
3. Look up best practices and common solutions
4. Access runbooks and playbooks

The knowledge base uses semantic search, so agents can find relevant documents even when exact keywords don't match.

## Memory (Engram)

Aletheia provides an optional multi-layered memory system called **Engram** that enables agents to persist knowledge across investigation sessions. The memory system uses hybrid vector + full-text search for semantic retrieval.

### Memory Layers

Memory is organized into two layers:

| Layer | File | Purpose | Persistence |
|-------|------|---------|-------------|
| **Long-term** | `MEMORY.md` | Important patterns, learned insights, persistent knowledge | Permanent |
| **Daily** | `memory/{YYYY-MM-DD}.md` | Session-specific findings, daily observations | Organized by date |

### Enabling/Disabling Memory

Memory is **enabled by default**. To disable it, use the `--disable-memory` flag:

```bash
# Disable memory for interactive sessions
aletheia session open --disable-memory

# Disable memory for API server
aletheia serve --disable-memory

# Disable memory for Telegram bot
aletheia telegram serve --disable-memory
```

To explicitly enable (if previously disabled):

```bash
aletheia session open --enable-memory
```

### How It Works

When memory is enabled:

1. **Orchestrator reads memory first** - On every request, the orchestrator reads both long-term and daily memories before routing to agents
2. **Agents can search memory** - Hybrid search combines semantic similarity (70%) with keyword matching (30%)
3. **Agents write discoveries** - Important findings are persisted to appropriate memory layer
4. **Background indexing** - A file watcher automatically re-indexes memories when files change

### Memory Storage Location

Memory files are stored in your config directory:

- **Linux**: `~/.config/aletheia/`
- **macOS**: `~/Library/Application Support/aletheia/`
- **Windows**: `%LOCALAPPDATA%\aletheia\`

```
{config_dir}/
├── MEMORY.md              # Long-term memory
├── memory/                # Daily memories folder
│   ├── 2026-01-28.md     # Today's memories
│   └── 2026-01-27.md     # Yesterday's memories
└── .engram/
    └── index.db          # SQLite index (vector + FTS)
```

### Memory Tools Available to Agents

When memory is enabled, agents have access to these tools:

| Tool | Description |
|------|-------------|
| `long_term_memory_write(memory)` | Write to persistent long-term memory |
| `daily_memory_write(memory)` | Write to today's daily memory |
| `read_long_term_memory()` | Read full long-term memory contents |
| `read_daily_memories(n_of_days)` | Read memories from last N days |
| `memory_search(query, max_results, min_score)` | Hybrid semantic + keyword search |
| `memory_get(path, from_line, lines)` | Retrieve specific memory file lines |

### Embedding Configuration

Memory search uses OpenAI embeddings by default (`text-embedding-3-small`). For Azure OpenAI:

```bash
export OPENAI_BASE_URL=https://YOUR-RESOURCE.openai.azure.com/openai/v1/
export OPENAI_API_KEY=your_azure_openai_key
```

## In-Session Commands

While in an active troubleshooting session, you can use these slash commands:

#### /help
Display all available in-session commands:
```
/help
```

#### /version
Show the current version of Aletheia:
```
/version
```

#### /info
Display information about the current Aletheia configuration, including:
- LLM provider being used
- LLM model being used
```
/info
```

#### /agents
List all loaded agents with their descriptions:
```
/agents
```

#### /cost
Display token usage and cost information for the current session:
```
/cost
```

This shows a detailed breakdown of:
- Total tokens used (input and output)
- Cost per token type (based on configuration)
- Total estimated cost

## Skills (experimental)
Aletheia's skills are complex orchestration of the Aletheia's agents' tools that can be defined in external yaml files.
The skills must be in `<skill_folder>/<agent_name>/<skill_name>` 

Where `<skill_folder>` can be set with the environment variable `ALETHEIA_USER_SKILLS_DIRS`

An example could be:
```
<skill_folder>
  |--aws
      <skill name>
        |-- instructions.yaml
        |--scripts
              |-- myscript.py
```      
in which `instructions.yaml` is: 

```yaml
---
name: Check IP in ELBV2 Security Groups
description: checks if a specific IP address is allowed by the security groups associated with ELBV2 load balancers in AWS.
instructions: |-
  Use this skill to check if a specific IP address is allowed by the security groups associated with ELBV2 load balancers in AWS.
  1. Use `aws_profiles()` to find the list of profiles
  2. If the user has specified a profile check against the results returned
  3. If the user has not specified a profile, ask him which one to use
  4. If the profile is there call `aws_elbv2_security_groups(profile)` to get the security groups associated with ELBV2 load balancers
  5. for each security group get the inbound rules using `aws_ec2_describe_security_group_inbound_rules(profile, group_id)`
  6. for each security group get the outbound rules using `aws_ec2_describe_security_group_outbound_rules(profile, group_id)`
  7. For each security group rule retrieved check if the specified IP address is allowed by the rule
  8. you MUST return the full results as a poem with rhymes in shakespearean style
```

If Aletheia is asked to  check if an IP address is allowed by the security group of and ELBV2 load balancer in AWS, it should recognize that it can't do it by simply invoking the given plugins and should load the skill to orchestrate the calls. 

When writing a skill try to avoid name overlapping with the Aletheia's plugins tool names

### Python scripts execution

You can add some python scripts to the skills and ask Aletheia to execute them if the skill is loaded. The scripts are executed in a docker container. 

1. **Build the docker image**

Build the aletheia-script-executor image from `aletheia-script-executor/Dockerfile`
```
cd aletheia-script-executor
docker build -t aletheia:latest .
```

2. **Add your scripts to the `<skill_folder>/<your skill>/scripts` folder**

e.g.:
```
<skills folder>
  |-- kubernetes_data_fetcher
        |--awesome_skill
              |-- instructions.yaml
              |-- scripts
                     |-- myscript.py
```

where `myscript.py` is

```python
import os

my_variable = os.environ.get("MY_VARIABLE")
print("Here's the pod in pending state:", my_variable)
```

3. **Reference your script from the skill instructions and ask Aletheia to inject variables**

```yaml
---
name: My Awesome Kubernetes skill
description: An awesome Kubernetes skill 
instructions: |-
  Use this awesome skill to find a pending pod in the kubernetes cluster:
  1. list the pods in the namespace with `list_kubernetes_pods()`
  2. Find the name of the pod that is in a `Pending` state
  3. call the script `myscript.py` passing as a parameter my_variable=<name of the pending pod>
```

4. **Run Aletheia**

```
> aletheia session open --unsafe -vv
[INC-25E3] 👤 YOU: execute my awesome skill for kubernetes in namespace aletheia-test

[INC-25E3] 🤖 Aletheia
────────────────────────────────────────────────────────────────────────────────
Loading skill from: [...]/test_skills/kubernetes_data_fetcher/awesome_skill
AGENT: kubernetes_data_fetcher

─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Section Findings:

 • Listed all pods in namespace aletheia-test using list_kubernetes_pods(). Found the following pods:
    • golang-test-service-6c6787f8dc-jmmfr (Running)
    • golang-test-service-6c6787f8dc-wnf5b (Running)
    • java-test-service-5cdf59696b-8bzr2 (Running)
    • java-test-service-5cdf59696b-t4lkc (Running)
    • ms-call-6579c46bdf-5gmb9 (Running)
    • ms-call-6579c46bdf-vl5zm (Running)
    • ms-called-b8f45d8c7-9xdz6 (Running)
    • ms-called-b8f45d8c7-ftmpc (Running)
    • pod-with-missing-secret (Pending)
 • Found the pod in Pending state: pod-with-missing-secret.
 • Executed the script myscript.py from the skill, passing my_variable=pod-with-missing-secret.
 • Script output: "Here's the pod in pending state: pod-with-missing-secret"

Section Decisions:

 • Loaded the skill "My Awesome Kubernetes skill" as requested, following the instructions exactly.
 • Used list_kubernetes_pods() to get all pods in the namespace, identified the pending pod, and executed the required script with the pod name as parameter.
 • Did not use direct tool calls beyond those required by the skill instructions.

Section Suggested actions:

 • If you need further investigation on why the pod is pending, consider describing the pod or checking events for pod-with-missing-secret.

─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
You can ask questions about the investigation or type 'exit' to end the session.
```

## WEB UI (Alpha)
Aletheia has a very rudimental WEB UI. To access it start Aletheia with `aletheia serve` and open `http://localhost:8000` in your browser.

## Telegram Bot

Aletheia provides a Telegram bot interface for remote troubleshooting via messaging. The bot supports all core functionality including session management, agent interactions, and command execution through a conversational interface.

### Features

- **Session Management**: Create, resume, list, and view investigation sessions
- **AI-Powered Chat**: Send messages to investigate issues with full agent orchestration
- **Command Support**: All built-in commands (`/help`, `/info`, `/agents`, `/cost`, `/version`) and custom commands
- **User Authorization**: Allowlist-based access control for security
- **Persistent Sessions**: Sessions stored in unsafe mode (plaintext) for easy access

### Setup

#### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Use the `/newbot` command and follow the prompts
3. Copy the bot token provided by BotFather

#### 2. Get Your Telegram User ID

1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. The bot will reply with your user ID (a numeric value)

#### 3. Configure Aletheia

Set the bot token and allowed users via environment variables:

```bash
# Bot token (required)
export ALETHEIA_TELEGRAM_BOT_TOKEN="your_bot_token_from_botfather"

# Allowed user IDs (comma-separated, recommended)
export ALETHEIA_TELEGRAM_ALLOWED_USERS="123456789,987654321"
```

Or add to your `config.yaml`:

```yaml
# Telegram Bot Configuration
telegram_bot_token: "your_bot_token_from_botfather"
telegram_allowed_users:
  - 123456789
  - 987654321
```

#### 4. Start the Bot

```bash
aletheia telegram serve
```

Options:
- `--token`: Override configured bot token
- `--verbose, -v`: Enable verbose logging

The bot will start polling for messages. You'll see a security disclaimer about Telegram's encryption.

### Available Commands

#### Session Commands

- `/start` - Welcome message and introduction
- `/new_session` - Create a new investigation session (always in unsafe mode)
- `/session list` - List all available sessions
- `/session resume <session-id>` - Resume an existing session
- `/session timeline <session-id>` - View session timeline
- `/session show <session-id>` - View session scratchpad

#### Built-in Commands

- `/help` - Show available commands
- `/info` - Display Aletheia configuration
- `/agents` - List all loaded agents
- `/cost` - Show token usage and costs
- `/version` - Display Aletheia version

#### Custom Commands

All custom commands defined in `~/.config/aletheia/commands/` are automatically available.

#### Regular Messages

Any non-command text is sent to the active session's AI orchestrator for investigation.

### Usage Example

```
You: /start
Bot: 👋 Welcome to Aletheia!
     Start with /new_session or resume with /session resume <id>

You: /new_session
Bot: ✅ New session created: INC-0042
     You can now send messages to investigate issues.

You: Why is my Kubernetes pod failing?
Bot: [AI-generated analysis with findings, decisions, and next actions]

You: /session list
Bot: Available Sessions:
     • INC-0042 - Telegram-123456789
       Created: 2026-01-26T14:30:00
       Status: active
```

### Security Considerations

⚠️ **Important Security Notes:**

1. **No End-to-End Encryption**: Telegram is not end-to-end encrypted. Messages can be read by Telegram server administrators. Avoid sharing sensitive data.

2. **User Allowlist**: Always configure `telegram_allowed_users` to restrict access. An empty allowlist allows ALL users.

3. **Plaintext Storage**: All Telegram sessions use unsafe mode (plaintext, no password encryption) for ease of access.

4. **Bot Token**: Keep your bot token secret. Anyone with the token can control your bot.

### Managing Allowed Users

View configured allowed users:

```bash
aletheia telegram allowed-users
```

This displays a table of authorized user IDs. To add or remove users, update your configuration and restart the bot.

### Troubleshooting

**Bot not responding:**
- Verify bot token is correct
- Check that your user ID is in the allowlist
- Review bot logs with `--verbose` flag

**Authorization errors:**
- Ensure your Telegram user ID is in `telegram_allowed_users`
- Check that the configuration is loaded correctly

**Session errors:**
- Sessions are stored in `~/.aletheia/sessions/`
- Use `/session list` to verify session exists
- Resume sessions with `/session resume <id>`

## User-Defined Agents

Aletheia supports loading custom agents at runtime without modifying the core codebase. User-defined agents are discovered from a configurable directory and loaded alongside built-in agents.

### Directory Structure

Create your agents in the user agents directory:

- **Linux**: `~/.config/aletheia/agents/`
- **macOS**: `~/Library/Application Support/aletheia/agents/`
- **Windows**: `%LOCALAPPDATA%\aletheia\agents\`

Each agent is a subdirectory containing:

```
agents/
  my_agent/
    config.yaml        # Agent metadata (required)
    agent.py           # Agent class definition (required)
    instructions.yaml  # Agent instructions (required)
```

### Configuration (config.yaml)

The `config.yaml` file contains basic agent metadata:

```yaml
agent:
  name: hello_world
  class: HelloWorldAgent
  description: "A friendly agent that greets people"
  enabled: true
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique agent identifier |
| `class` | Yes | Python class name in agent.py |
| `description` | Yes | Description shown to the orchestrator |
| `enabled` | No | Enable/disable the agent (default: true) |

### Instructions (instructions.yaml)

The `instructions.yaml` file defines the agent's identity and behavioral guidelines, following the same structure as internal agents:

```yaml
agent:
  name: hello_world
  identity: |
    You are HelloWorldAgent, a friendly agent that says hello to the world.
  guidelines: |
    - Be nice and helpful
    - Always greet people warmly
    - Use the say_hello tool when appropriate
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Agent name (should match config.yaml) |
| `identity` | Yes | Agent identity and role description |
| `guidelines` | Yes | Behavioral guidelines and instructions |

### Agent Implementation (agent.py)

```python
from typing import Annotated, List
from agent_framework import ToolProtocol
from aletheia.agents.base import BaseAgent
from aletheia.plugins.base import BasePlugin


class HelloWorldPlugin(BasePlugin):
    """Custom plugin providing tools for the agent."""

    def __init__(self):
        self.name = "HelloWorldPlugin"
        self.instructions = "Use say_hello to greet someone."

    def say_hello(self, name: Annotated[str, "Name of the person to greet"]) -> str:
        """Greet a person by name."""
        return f"Hello, {name}!"

    def get_tools(self) -> List[ToolProtocol]:
        """Return the list of tools provided by this plugin."""
        return [self.say_hello]


class HelloWorldAgent(BaseAgent):
    """Custom agent that greets people."""

    def __init__(self, name, config, description, session, scratchpad, **kwargs):
        # Create plugin instances
        hello_plugin = HelloWorldPlugin()
        plugins = [scratchpad, hello_plugin]

        # Instructions are loaded from instructions.yaml via BaseAgent
        super().__init__(
            name=name,
            config=config,
            description=description,
            session=session,
            plugins=plugins,
            **kwargs
        )
```

### Configuration Options

Control user agent loading via environment variables or config.yaml:

| Variable | Description | Default |
|----------|-------------|---------|
| `ALETHEIA_USER_AGENTS_DIRECTORY` | Path to user agents directory | `{config_dir}/agents` |
| `ALETHEIA_USER_AGENTS_ENABLED` | Enable/disable user agent loading | `true` |
| `ALETHEIA_DISABLED_AGENTS` | Comma-separated list of agents to disable | `""` |

Example in config.yaml:

```yaml
user_agents_directory: /path/to/my/agents
user_agents_enabled: true
disabled_agents:
  - aws  # Disable built-in AWS agent
```

### Plugin Requirements

Custom plugins must:
1. Inherit from `BasePlugin`
2. Implement `get_tools()` returning a list of callable methods
3. Use `Annotated` type hints for tool parameters

```python
def my_tool(self, param: Annotated[str, "Parameter description"]) -> str:
    """Tool docstring becomes the tool description."""
    return "result"

def get_tools(self) -> List[ToolProtocol]:
    return [self.my_tool]
```

## MCP Support (Highly experimental)
You can add MCP Server to each agent by setting a `ALETHEIA_MCP_SERVERS_YAML` env variable pointing to a yaml configuration which must have the following format:

```yaml
mcp_servers:
  # STDIO Transport
  - name: # MCP Server Name
    type: stdio # if stdio 
    agents: # comma separated names of the agents that are allowed to access the server
    description: # mcp server description
    command: # mcp servert command. e.g.: uvx
    args:  # array of arguments
    env: # dictionary ov environment variables
    ...
  # HTTP Streamable Transport
  - name: # MCP Server Name
    type: streamable_http # if stdio 
    agents: # comma separated names of the agents that are allowed to access the server
    description: # mcp server description
    url: # uri of the server
    bearer:  # bearer token
    ...
```


 

