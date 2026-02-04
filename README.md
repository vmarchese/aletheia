# Aletheia (ἀλήθεια)

> **Aletheia** (ἀλήθεια) — Ancient Greek for "truth" or "un-concealment": bringing what's hidden into the open.

Aletheia is a modular, AI-powered troubleshooting framework for SREs and system administrators. It orchestrates specialized LLM agents to collect and analyze observability data (logs, metrics, traces), inspect code, and generate actionable root cause hypotheses.

---

## Overview

Aletheia provides an interactive, agent-based workflow for troubleshooting distributed systems. It leverages Large Language Models (LLMs) and specialized plugins to automate data collection, pattern analysis, and root cause investigation across Kubernetes, Prometheus, log files, and more.

### Architecture

Aletheia uses a **daemon-based architecture** with a central gateway that manages sessions and coordinates communication between channels and agents:

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interfaces                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐      │
│  │   TUI    │    │  Web UI  │    │  Telegram Bot    │      │
│  └────┬─────┘    └────┬─────┘    └────────┬─────────┘      │
│       │               │                    │                │
│       └───────────────┴────────────────────┘                │
│                       │                                     │
│                WebSocket (ws://127.0.0.1:8765)             │
│                       │                                     │
│       ┌───────────────▼───────────────┐                    │
│       │    Aletheia Gateway Daemon    │                    │
│       │  - Session Management         │                    │
│       │  - Agent Orchestration        │                    │
│       │  - Chat History Logging       │                    │
│       │  - Response Streaming         │                    │
│       └───────────────┬───────────────┘                    │
│                       │                                     │
│       ┌───────────────▼───────────────┐                    │
│       │       Specialized Agents       │                    │
│       │  • Orchestrator                │                    │
│       │  • Kubernetes Data Fetcher     │                    │
│       │  • AWS Agent                   │                    │
│       │  • Azure Agent                 │                    │
│       │  • Code Analyzer               │                    │
│       │  • Network Agent               │                    │
│       │  • And more...                 │                    │
│       └────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

### Key Features

- **Multiple Interfaces**: TUI, Web UI, and Telegram bot - all connecting to the same gateway
- **Persistent Sessions**: Sessions managed centrally by the gateway daemon
- **Streaming Responses**: Real-time agent output streamed to all connected channels
- **Chat History**: All interactions logged in JSONL format per session
- **Extensible Channels**: Plugin-based channel system for easy integration of new interfaces

### Available Agents

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
uv pip install -e .
```

## Quick Start

### 1. Start the Gateway Daemon

The gateway daemon is the heart of Aletheia. Start it first:

```bash
aletheia start
```

This starts the gateway on `ws://127.0.0.1:8765` (configurable).

**Options:**
- `--host <host>` - Bind address (default: 127.0.0.1)
- `--port <port>` - Port number (default: 8765)
- `--enable-memory` / `--disable-memory` - Enable/disable Engram memory (default: enabled)

### 2. Check Gateway Status

```bash
aletheia status
```

### 3. Connect via a Channel

Choose your preferred interface:

#### Option A: Terminal UI (TUI)

```bash
python -m aletheia.channels.tui
```

The TUI provides an interactive terminal interface with:
- Rich markdown rendering
- Password prompts via prompt_toolkit
- Session management commands (`/new_session`, `/resume`, `/list_sessions`)

#### Option B: Web UI

```bash
python -m aletheia.channels.web
```

Then open http://localhost:8000 in your browser.

Features:
- Real-time streaming responses
- Session management
- Markdown rendering
- WebSocket-based communication

#### Option C: Telegram Bot

First, configure your Telegram bot (see [Telegram Bot Setup](#telegram-bot)):

```bash
python -m aletheia.channels.telegram
```

## Usage

### Gateway Daemon Commands

```bash
# Start the gateway daemon
aletheia start [--host HOST] [--port PORT] [--enable-memory/--disable-memory]

# Check gateway status
aletheia status
```

### Channel Connectors

All channels connect to the gateway via WebSocket and support the same core functionality:

#### TUI (Terminal UI)

```bash
python -m aletheia.channels.tui [GATEWAY_URL]
```

**Default:** `ws://127.0.0.1:8765`

**Commands:**
- `/new_session [name]` - Create new session
- `/resume <id>` - Resume existing session
- `/list_sessions` - List all sessions
- `/exit` - Disconnect

#### Web UI

```bash
python -m aletheia.channels.web [GATEWAY_URL] [HOST] [PORT]
```

**Defaults:**
- Gateway: `ws://127.0.0.1:8765`
- Host: `0.0.0.0`
- Port: `8000`

#### Telegram Bot

```bash
python -m aletheia.channels.telegram [GATEWAY_URL]
```

**Default:** `ws://127.0.0.1:8765`

See [Telegram Bot Setup](#telegram-bot) for configuration.

### Legacy Session Commands

For backward compatibility, direct session commands are still available but will be deprecated in favor of the daemon architecture:

```bash
# Open a new session (legacy mode - bypasses daemon)
aletheia session open [--name NAME] [--unsafe] [--verbose] [--enable-memory]

# Resume a session (legacy mode - bypasses daemon)
aletheia session resume <session_id> [--unsafe]

# List all sessions
aletheia session list

# View session details
aletheia session view <session_id>

# View session timeline
aletheia session timeline <session_id>

# Export session
aletheia session export <session_id> [--output FILE]

# Delete session
aletheia session delete <session_id>
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

### Daemon Configuration

```yaml
# Gateway Daemon Configuration
daemon_host: 127.0.0.1      # Gateway bind address
daemon_port: 8765            # Gateway WebSocket port
daemon_pid_file: null        # PID file location (optional)
daemon_log_file: null        # Log file location (optional)
```

**Environment variables:**
```bash
export ALETHEIA_DAEMON_HOST=127.0.0.1
export ALETHEIA_DAEMON_PORT=8765
```

### LLM Configuration

```yaml
# LLM Configuration
llm_default_model: gpt-4o
llm_temperature: 0.2
code_analyzer: claude

# Cost Configuration
cost_per_input_token: 0.0025
cost_per_output_token: 0.01
```

### Azure OpenAI

Aletheia needs three environment variables to be set to work with Azure OpenAI:

```bash
export AZURE_OPENAI_API_KEY=<azure openai api key>
export AZURE_OPENAI_ENDPOINT=<azure openai endpoint>
export AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=<azure deployment name>
```

### OpenAI (or Ollama)

To use Aletheia with OpenAI or Ollama:

```bash
export OPENAI_API_KEY=<openai api key>
export OPENAI_BASE_URL=<openai endpoint>
export OPENAI_MODEL=<openai model>
```

For Ollama on localhost:

```bash
export OPENAI_API_KEY=none
export OPENAI_BASE_URL=http://127.0.0.1:11434/v1
export OPENAI_MODEL=gpt-oss:20b
```

### Directory Configuration

```yaml
# Directory Configuration
skills_directory: ~/.config/aletheia/skills
commands_directory: ~/.config/aletheia/commands
custom_instructions_dir: ~/.config/aletheia/instructions
user_agents_directory: ~/.config/aletheia/agents
temp_folder: ./.aletheia
```

See the [Configuration](#configuration) section below for complete details.

## <a name="telegram-bot"></a>Telegram Bot Setup

### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Use the `/newbot` command and follow the prompts
3. Copy the bot token provided by BotFather

### 2. Get Your Telegram User ID

1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. The bot will reply with your user ID (a numeric value)

### 3. Configure Aletheia

```bash
# Bot token (required)
export ALETHEIA_TELEGRAM_BOT_TOKEN="your_bot_token_from_botfather"

# Allowed user IDs (comma-separated, recommended)
export ALETHEIA_TELEGRAM_ALLOWED_USERS="123456789,987654321"
```

Or in `config.yaml`:

```yaml
telegram_bot_token: "your_bot_token_from_botfather"
telegram_allowed_users:
  - 123456789
  - 987654321
telegram_session_timeout: 30  # minutes
```

### 4. Start the Gateway and Bot

```bash
# Terminal 1: Start gateway
aletheia start

# Terminal 2: Start Telegram bot
python -m aletheia.channels.telegram
```

### Available Bot Commands

- `/start` - Welcome message
- `/help` - Show help
- `/new` - Create new session
- `/resume <session_id>` - Resume session
- `/sessions` - List sessions

Regular text messages are sent to the active session for AI analysis.

### Security Note

⚠️ Telegram is not end-to-end encrypted. Messages can be read by Telegram server administrators. Always use the allowlist to restrict access.

## Memory (Engram)

Aletheia provides an optional multi-layered memory system called **Engram** that enables agents to persist knowledge across investigation sessions.

### Memory Layers

| Layer | File | Purpose | Persistence |
|-------|------|---------|-------------|
| **Long-term** | `MEMORY.md` | Important patterns, learned insights | Permanent |
| **Daily** | `memory/{YYYY-MM-DD}.md` | Session-specific findings | By date |

### Enabling/Disabling Memory

Memory is **enabled by default**. To disable:

```bash
# Gateway daemon
aletheia start --disable-memory

# Legacy session mode
aletheia session open --disable-memory
```

### Memory Storage

Memory files are stored in your config directory:
- **Linux**: `~/.config/aletheia/`
- **macOS**: `~/Library/Application Support/aletheia/`
- **Windows**: `%LOCALAPPDATA%\aletheia\`

## Knowledge Base

Aletheia provides a knowledge base management system using ChromaDB for storing troubleshooting documentation and runbooks.

### Commands

```bash
# Add a document
aletheia knowledge add <id> <path> [--metadata <json>]

# List documents
aletheia knowledge list

# Delete a document
aletheia knowledge delete <id>
```

## Skills (Experimental)

Skills are complex orchestrations of agent tools defined in external YAML files.

### Directory Structure

```
<skills_directory>/
  aws/
    ec2_route_tables/
      SKILL.md
  kubernetes_data_fetcher/
    examine_thread_dump/
      SKILL.md
```

Configure with:
```bash
export ALETHEIA_SKILLS_DIRECTORY=/path/to/skills
```

See existing skills in the repository for examples.

## User-Defined Agents

Create custom agents in `~/.config/aletheia/agents/`:

```
agents/
  my_agent/
    config.yaml          # Agent metadata
    agent.py             # Agent implementation
    instructions.yaml    # Agent instructions
```

A typical `agent.py` could be:

```python
from typing import Annotated
from aletheia.agents.base import BaseAgent
from aletheia.plugins.base import BasePlugin


class HelloWorldPlugin(BasePlugin):
    def say_hello(self, name: Annotated[str, "Name of the person to greet"]) -> str:
        return f"Hello, {name} from the HelloWorldAgent!"

    def get_tools(self):
        return [self.say_hello]

class HelloWorldAgent(BaseAgent):
    def __init__(self, name, config, description, session, scratchpad, **kwargs):
        hello = HelloWorldPlugin()
        plugins = [scratchpad, hello]  # Add your plugins here
        super().__init__(
            name=name, config=config, description=description,
            session=session, plugins=plugins, **kwargs
        )
```        

with  `config.yaml`: 

```yaml
agent:
  name: hello_world
  class: HelloWorldAgent
  description: "My Hello World Agent"
  enabled: true
```  

and `instructions.yaml`: 

```yaml
---
agent:
  name: hello_world
  identity: |-
        You are **HelloWorldAgent**, a specialized assistant responsible for **greeting users warmly and providing friendly interactions**.
  guidelines: |-
    - Be nice and friendly
    - Use the say_hello tool to greet people
    - Always add a joke about kittens after greeting
```    


## Advanced Configuration

### Complete Configuration Options

| Key | Description | Default |
|-----|-------------|---------|
| `daemon_host` | Gateway bind address | `127.0.0.1` |
| `daemon_port` | Gateway WebSocket port | `8765` |
| `llm_default_model` | Default LLM model | `gpt-4o` |
| `llm_temperature` | LLM temperature (0.0-1.0) | `0.2` |
| `code_analyzer` | Code analyzer (claude/copilot) | `""` |
| `skills_directory` | Skills directory path | `{config}/skills` |
| `commands_directory` | Custom commands path | `{config}/commands` |
| `custom_instructions_dir` | Agent instructions path | `{config}/instructions` |
| `user_agents_directory` | User agents path | `{config}/agents` |
| `telegram_bot_token` | Telegram bot token | `None` |
| `telegram_allowed_users` | Allowed Telegram user IDs | `[]` |

### Personality Customization (SOUL.md)

Customize Aletheia's personality by creating `SOUL.md` in your config directory:

```markdown
# Aletheia's Soul

You are a clever, witty assistant with great humor.

## Core Personality
- Clever and quick-witted
- Warmly sarcastic
- Self-aware

## How You Talk
- Greetings: "Well, well, well... look who needs help!"
- Success: "And THAT is how it's done. *mic drop*"
```

## Development

### Code Style

We use **Black** and **Ruff** for code formatting:

```bash
black .
ruff check --fix .
```

### Type Checking

```bash
mypy .
```

### Testing

```bash
pytest
```

## Architecture Details

### Protocol Messages

The gateway uses JSON-based WebSocket messages:

```json
{
  "type": "chat_message",
  "id": "uuid",
  "timestamp": "2026-02-02T10:00:00Z",
  "payload": {
    "message": "Why is my pod failing?"
  }
}
```

**Message Types:**
- `channel_register` - Channel registration
- `session_create` - Create new session
- `session_resume` - Resume session
- `chat_message` - User message
- `response_chunk` - Streaming response chunk
- `response_complete` - Response completion
- `error` - Error message

### Channel Capabilities

Channels declare capabilities via manifest:

```python
ChannelManifest(
    channel_type="tui",
    capabilities={
        ChannelCapability.STREAMING,
        ChannelCapability.RICH_TEXT,
        ChannelCapability.PERSISTENT,
    }
)
```

**Available Capabilities:**
- `STREAMING` - Supports streaming responses
- `RICH_TEXT` - Supports markdown/formatting
- `IMAGES` - Can display images
- `FILE_UPLOAD` - Can upload files
- `FILE_DOWNLOAD` - Can download files
- `INTERACTIVE` - Supports buttons/forms
- `MULTI_USER` - Multiple users per instance
- `PERSISTENT` - Maintains persistent connection
- `SECURE` - Provides E2E encryption
- `VOICE` - Supports voice I/O

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run code quality checks (`black`, `ruff`, `mypy`)
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
