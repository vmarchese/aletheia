# Aletheia Refactoring Specification

> **Document Version**: 1.0
> **Target**: Transform Aletheia from CLI-centric to daemon-based architecture with channel connectors

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Architecture Analysis](#2-current-architecture-analysis)
3. [Target Architecture Overview](#3-target-architecture-overview)
4. [Component Specifications](#4-component-specifications)
   - 4.1 [Daemon (Gateway)](#41-daemon-gateway)
   - 4.2 [Session Manager](#42-session-manager)
   - 4.3 [WebSocket Protocol](#43-websocket-protocol)
   - 4.4 [Channel Connectors](#44-channel-connectors)
   - 4.5 [Chat History Logger](#45-chat-history-logger)
5. [File-by-File Changes](#5-file-by-file-changes)
6. [New Files to Create](#6-new-files-to-create)
7. [Data Models](#7-data-models)
8. [Migration Strategy](#8-migration-strategy)
9. [Configuration Changes](#9-configuration-changes)
10. [Testing Requirements](#10-testing-requirements)
11. [Channel Extensibility System](#11-channel-extensibility-system)

---

## 1. Executive Summary

### 1.1 Current State

Aletheia currently operates in three independent modes:
- **TUI Mode** (`aletheia session open`): Mono-session terminal interface
- **Web Mode** (`aletheia serve`): FastAPI server with SSE streaming
- **Telegram Mode** (`aletheia telegram serve`): Polling-based bot server

Each mode initializes its own orchestrator, manages sessions independently, and has no shared state between channels.

### 1.2 Target State

Transform Aletheia into a daemon-based architecture where:
- A **Gateway Daemon** runs continuously (`aletheia start`)
- All **channels** (TUI, Web, Telegram) connect to the gateway via **WebSocket**
- The gateway manages **one active session at a time** (with multi-session support planned)
- All **chat history** is logged to the session folder
- All existing features (skills, soul, slash commands, custom agents) remain fully functional

### 1.3 Key Benefits

- Unified session management across all channels
- Persistent daemon process with OS integration (systemd, launchctl)
- Real-time channel switching without losing context
- Centralized chat history for all interactions
- Foundation for future multi-session/multi-user support

---

## 2. Current Architecture Analysis

### 2.1 Entry Points

| File | Function | Purpose |
|------|----------|---------|
| `cli.py:784` | `session_open()` | Creates session, initializes orchestrator, runs `_start_investigation()` |
| `cli.py:1323` | `serve()` | Starts FastAPI/Uvicorn server |
| `cli.py:1446` | `telegram_serve()` | Runs Telegram bot via polling |

### 2.2 Session Management

**Current Location**: `aletheia/session.py`

- `Session.create()` - Creates new session with ID format `INC-XXXX`
- `Session.resume()` - Resumes existing session
- Sessions stored in `~/.aletheia/sessions/<session_id>/`
- Metadata stored as JSON, scratchpad encrypted or plaintext

### 2.3 Orchestrator Initialization

**Current Location**: `cli.py:321-371` (`init_orchestrator()`)

1. Creates `Loader` for prompt templates
2. Initializes `Scratchpad` with session directory and encryption key
3. Builds plugins via `_build_plugins()`
4. Creates `Orchestrator` with sub-agents
5. Initializes thread for conversation context

### 2.4 Channel-Specific State

| Channel | State Management | Location |
|---------|------------------|----------|
| TUI | Single session, single orchestrator | `cli.py` local variables |
| Web | `active_investigations` dict (session_id → Orchestrator) | `api.py:90` |
| Telegram | `TelegramSessionManager` (user_id → session_id, session_id → Orchestrator) | `telegram/session_manager.py` |

### 2.5 Streaming Mechanisms

| Channel | Mechanism | Details |
|---------|-----------|---------|
| TUI | `agent.run_stream()` + `rich.Live` | Direct async iteration |
| Web | SSE (`EventSourceResponse`) | Queue-based async push |
| Telegram | Accumulate + send | Buffer entire response, split on size limits |

---

## 3. Target Architecture Overview

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Aletheia Gateway Daemon                      │
│                        (aletheia start/stop)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │  Session Manager │    │  Chat History   │    │   Orchestrator  │ │
│  │                 │    │     Logger      │    │    + Agents     │ │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘ │
│           │                      │                      │          │
│           └──────────────────────┼──────────────────────┘          │
│                                  │                                  │
│  ┌───────────────────────────────┴───────────────────────────────┐ │
│  │                    WebSocket Server (:8765)                    │ │
│  └───────────────────────────────┬───────────────────────────────┘ │
│                                  │                                  │
└──────────────────────────────────┼──────────────────────────────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           │                       │                       │
    ┌──────┴──────┐         ┌──────┴──────┐         ┌──────┴──────┐
    │ TUI Channel │         │ Web Channel │         │  Telegram   │
    │  Connector  │         │  Connector  │         │  Connector  │
    └─────────────┘         └─────────────┘         └─────────────┘
```

### 3.2 Process Model

```
┌─────────────────────────────────────────────────────────┐
│                    Gateway Daemon Process                │
│                                                          │
│  - Runs as background service or foreground process     │
│  - Manages WebSocket server on localhost:8765           │
│  - Holds the active session and orchestrator            │
│  - Logs all interactions to session folder              │
│  - Handles graceful shutdown on SIGTERM/SIGINT          │
│                                                          │
└─────────────────────────────────────────────────────────┘

┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   TUI Process   │  │   Web Process   │  │ Telegram Process│
│                 │  │                 │  │                 │
│ WebSocket       │  │ WebSocket       │  │ WebSocket       │
│ Client          │  │ Client          │  │ Client          │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 3.3 Communication Flow

```
Channel → WebSocket → Gateway Daemon → Session Manager → Orchestrator
                                    ↓
                              Chat History Logger
                                    ↓
                              Session Folder
```

---

## 4. Component Specifications

### 4.1 Daemon (Gateway)

#### 4.1.1 New File: `aletheia/daemon/gateway.py`

**Purpose**: Main daemon process that manages the WebSocket server and session lifecycle.

**Class: `AletheiaGateway`**

```python
class AletheiaGateway:
    """
    Main gateway daemon managing sessions and channel connections.

    Attributes:
        config: Config - Aletheia configuration
        session_manager: GatewaySessionManager - Active session management
        websocket_server: WebSocketServer - WebSocket server instance
        chat_logger: ChatHistoryLogger - Logs all interactions
        engram: Engram | None - Memory system (if enabled)
        running: bool - Daemon running state
    """

    def __init__(self, config: Config, enable_memory: bool = True):
        """Initialize gateway with configuration."""

    async def start(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        """Start the gateway daemon and WebSocket server."""

    async def stop(self) -> None:
        """Gracefully stop the gateway daemon."""

    async def handle_connection(self, websocket: WebSocket, path: str) -> None:
        """Handle new WebSocket connection from a channel."""

    async def handle_message(self, websocket: WebSocket, message: dict) -> None:
        """Route incoming messages to appropriate handlers."""

    async def broadcast_to_channels(self, message: dict) -> None:
        """Broadcast message to all connected channels."""
```

**Methods Detail**:

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `start` | `host: str`, `port: int` | `None` | Initializes WebSocket server, sets up signal handlers |
| `stop` | None | `None` | Closes all connections, saves session, stops Engram watcher |
| `handle_connection` | `websocket`, `path` | `None` | Authenticates channel, adds to connection pool |
| `handle_message` | `websocket`, `message: dict` | `None` | Dispatches to message handlers based on `type` field |
| `broadcast_to_channels` | `message: dict` | `None` | Sends message to all connected channels except sender |

#### 4.1.2 New File: `aletheia/daemon/server.py`

**Purpose**: WebSocket server implementation.

**Class: `WebSocketServer`**

```python
class WebSocketServer:
    """
    Manages WebSocket connections from channel connectors.

    Attributes:
        host: str - Bind address
        port: int - Bind port
        connections: dict[str, WebSocket] - channel_id → connection
        server: websockets.WebSocketServer - Underlying server
    """

    async def start(self) -> None:
        """Start WebSocket server."""

    async def stop(self) -> None:
        """Stop WebSocket server and close all connections."""

    def register_connection(self, channel_id: str, websocket: WebSocket) -> None:
        """Register a new channel connection."""

    def unregister_connection(self, channel_id: str) -> None:
        """Remove a channel connection."""

    async def send_to_channel(self, channel_id: str, message: dict) -> None:
        """Send message to specific channel."""

    async def broadcast(self, message: dict, exclude: str | None = None) -> None:
        """Broadcast message to all channels."""
```

#### 4.1.3 New File: `aletheia/daemon/auth.py`

**Purpose**: Secure password entry endpoint for channels that cannot handle passwords securely (e.g., Telegram).

**Class: `AuthServer`**

```python
class AuthServer:
    """
    Lightweight HTTP server for secure password entry.

    Used by Telegram channel to allow users to enter passwords
    via a secure web form instead of through chat messages.

    Attributes:
        host: str - Bind address (default: 127.0.0.1)
        port: int - Bind port (default: 8766)
        tokens: dict[str, AuthToken] - Active authentication tokens
        gateway: AletheiaGateway - Reference to gateway for session creation
    """

    def __init__(self, gateway: "AletheiaGateway", host: str = "127.0.0.1", port: int = 8766):
        """Initialize auth server."""

    async def start(self) -> None:
        """Start HTTP server."""

    async def stop(self) -> None:
        """Stop HTTP server."""

    def generate_token(
        self,
        user_id: str,
        channel_id: str,
        action: str,  # "create" | "resume"
        session_id: str | None = None,
        verbose: bool = False,
        expires_in: int = 300  # 5 minutes
    ) -> str:
        """Generate a one-time authentication token."""

    async def handle_auth_page(self, request: Request) -> Response:
        """Serve the password entry form."""

    async def handle_auth_submit(self, request: Request) -> Response:
        """Handle password submission and create/resume session."""


@dataclass
class AuthToken:
    """One-time authentication token."""
    token: str
    user_id: str
    channel_id: str
    action: str  # "create" | "resume"
    session_id: str | None
    verbose: bool
    created_at: datetime
    expires_at: datetime
    used: bool = False
```

**Auth Flow**:

```
┌─────────────┐     /new_session safe     ┌─────────────┐
│   Telegram  │ ─────────────────────────→│   Gateway   │
│    User     │                           │             │
└─────────────┘                           └──────┬──────┘
      │                                          │
      │                                          │ Generate token
      │                                          ↓
      │                              ┌───────────────────────┐
      │   Auth URL                   │     AuthServer        │
      │←─────────────────────────────│  localhost:8766/auth  │
      │                              └───────────────────────┘
      │
      │ Open in browser
      ↓
┌─────────────┐                      ┌───────────────────────┐
│   Browser   │ ───────────────────→ │  GET /auth/<token>    │
│             │     Password form    │  Password entry form  │
└─────────────┘                      └───────────────────────┘
      │
      │ Submit password
      ↓
┌─────────────┐                      ┌───────────────────────┐
│   Browser   │ ───────────────────→ │  POST /auth/<token>   │
│             │                      │  Create session       │
└─────────────┘                      └──────────┬────────────┘
                                                │
                                                │ session_create
                                                ↓
                                     ┌───────────────────────┐
                                     │      Gateway          │
                                     │  Notify Telegram user │
                                     └───────────────────────┘
```

**Password Entry Form** (minimal HTML):

```html
<!DOCTYPE html>
<html>
<head><title>Aletheia - Secure Password Entry</title></head>
<body>
  <h1>🔐 Aletheia Session Setup</h1>
  <p>Enter your encryption password for the session.</p>
  <form method="POST">
    <label>Password: <input type="password" name="password" required></label><br>
    <label>Confirm: <input type="password" name="confirm" required></label><br>
    <button type="submit">Create Session</button>
  </form>
  <p><small>This password encrypts your session data locally.</small></p>
</body>
</html>
```

#### 4.1.4 CLI Commands

**New commands in `cli.py`**:

| Command | Description |
|---------|-------------|
| `aletheia start` | Start the gateway daemon in foreground |
| `aletheia start --daemon` | Start as background daemon |
| `aletheia stop` | Stop the running daemon |
| `aletheia status` | Check daemon status |
| `aletheia connect` | Connect TUI to running daemon |

---

### 4.2 Session Manager

#### 4.2.1 New File: `aletheia/daemon/session_manager.py`

**Purpose**: Centralized session management for the gateway.

**Class: `GatewaySessionManager`**

```python
class GatewaySessionManager:
    """
    Manages sessions for the gateway daemon.

    Currently supports single active session.
    Designed for future multi-session support.

    Attributes:
        active_session: Session | None - Currently active session
        orchestrator: Orchestrator | None - Active orchestrator
        config: Config - Aletheia configuration
        engram: Engram | None - Memory system
    """

    def __init__(self, config: Config, engram: Engram | None = None):
        """Initialize session manager."""

    async def create_session(
        self,
        name: str | None = None,
        password: str | None = None,
        unsafe: bool = False,
        verbose: bool = False
    ) -> Session:
        """Create and activate a new session."""

    async def resume_session(
        self,
        session_id: str,
        password: str | None = None,
        unsafe: bool = False
    ) -> Session:
        """Resume an existing session and make it active."""

    async def close_active_session(self) -> None:
        """Close the currently active session and cleanup orchestrator."""

    def get_active_session(self) -> Session | None:
        """Get the currently active session."""

    def get_orchestrator(self) -> Orchestrator | None:
        """Get the orchestrator for the active session."""

    async def send_message(self, message: str) -> AsyncIterator[dict]:
        """Send message to active session and yield streaming response."""

    def list_sessions(self) -> list[dict]:
        """List all available sessions."""
```

**Session Lifecycle**:

```
┌─────────────┐     create_session()      ┌─────────────┐
│   No        │ ─────────────────────────→│   Active    │
│   Session   │←─────────────────────────── │   Session   │
└─────────────┘   close_active_session()  └─────────────┘
                                                 │
                                                 │ resume_session()
                                                 ↓
                                          ┌─────────────┐
                                          │  Different  │
                                          │   Session   │
                                          └─────────────┘
```

#### 4.2.2 Future Multi-Session Support

Design considerations for future expansion:

```python
# Future structure (NOT for current implementation)
class MultiSessionManager:
    sessions: dict[str, Session]  # session_id → Session
    orchestrators: dict[str, Orchestrator]  # session_id → Orchestrator
    active_session_id: str | None  # Currently focused session

    async def switch_session(self, session_id: str) -> Session:
        """Switch the active session context."""
```

---

### 4.3 WebSocket Protocol

#### 4.3.1 New File: `aletheia/daemon/protocol.py`

**Purpose**: Define message protocol for WebSocket communication.

**Message Format**:

All messages are JSON objects with required `type` field:

```json
{
  "type": "message_type",
  "id": "unique_message_id",
  "timestamp": "2026-02-01T10:30:00Z",
  "payload": { ... }
}
```

#### 4.3.2 Client → Gateway Messages

| Type | Payload | Description |
|------|---------|-------------|
| `channel_register` | `{channel_type: "tui"|"web"|"telegram", channel_id: string}` | Register channel with gateway |
| `channel_unregister` | `{}` | Unregister channel before disconnect |
| `session_create` | `{name?: string, password?: string, unsafe?: bool, verbose?: bool}` | Create new session |
| `session_resume` | `{session_id: string, password?: string, unsafe?: bool}` | Resume existing session |
| `session_close` | `{}` | Close active session |
| `session_list` | `{}` | List available sessions |
| `chat_message` | `{message: string}` | Send message to orchestrator |
| `command` | `{command: string, args?: string[]}` | Execute slash command |
| `ping` | `{}` | Heartbeat ping |

**`session_create` Payload Details**:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `string?` | `null` | Optional session name (auto-generated if not provided) |
| `password` | `string?` | `null` | Password for encrypted sessions |
| `unsafe` | `bool` | `false` | If true, scratchpad stored as plaintext |
| `verbose` | `bool` | `false` | If true, enable verbose agent output |

**Session Initiation by Channel**:

| Channel | Method | Notes |
|---------|--------|-------|
| TUI | `/new_session` command | Supports `--verbose`, `--unsafe`, `--name` flags |
| Web | Modal dialog | Form with name, verbose checkbox, unsafe checkbox |
| Telegram | `/new_session` command | Supports `verbose` arg; always `unsafe=true` |

#### 4.3.3 Gateway → Client Messages

| Type | Payload | Description |
|------|---------|-------------|
| `channel_registered` | `{channel_id: string, session?: SessionInfo}` | Confirm registration |
| `session_required` | `{available_sessions: SessionInfo[]}` | No active session, client should prompt user |
| `session_created` | `{session: SessionMetadata}` | Session creation confirmed |
| `session_resumed` | `{session: SessionMetadata, history: ChatEntry[]}` | Session resumed with history |
| `session_closed` | `{}` | Session closed |
| `session_list` | `{sessions: SessionInfo[]}` | List of sessions |
| `chat_stream_start` | `{message_id: string}` | Response stream starting |
| `chat_stream_chunk` | `{message_id: string, chunk_type: string, content: any}` | Streaming chunk |
| `chat_stream_end` | `{message_id: string, usage: UsageInfo}` | Response stream complete |
| `command_result` | `{command: string, result: string}` | Command execution result |
| `error` | `{code: string, message: string}` | Error response |
| `pong` | `{}` | Heartbeat response |

**`session_required` Message**:

Sent when a channel attempts to send a `chat_message` but no active session exists:

```json
{
  "type": "session_required",
  "id": "msg-uuid",
  "timestamp": "2026-02-01T10:30:00Z",
  "payload": {
    "available_sessions": [
      {"id": "INC-0001", "name": "Database Issue", "created": "...", "updated": "..."},
      {"id": "INC-0002", "name": "Memory Leak", "created": "...", "updated": "..."}
    ]
  }
}
```

Channels should handle this by:
- **TUI**: Display message prompting user to run `/new_session` or `/resume <id>`
- **Web**: Show the "New Session" dialog or session picker
- **Telegram**: Reply with instructions to use `/new_session` or `/resume`

#### 4.3.4 Streaming Chunk Types

For `chat_stream_chunk`, the `chunk_type` field indicates content type:

| chunk_type | content | Description |
|------------|---------|-------------|
| `agent` | `string` | Agent name handling the request |
| `confidence` | `float` | Confidence level (0-1) |
| `findings` | `Findings` | Findings object |
| `decisions` | `Decisions` | Decisions object |
| `next_actions` | `NextActions` | Next actions object |
| `errors` | `string[]` | Error messages |
| `tool_call` | `{tool: string, args: dict}` | Tool being called |
| `tool_result` | `{tool: string, result: string}` | Tool result |

#### 4.3.5 Protocol Data Classes

```python
@dataclass
class ProtocolMessage:
    type: str
    id: str
    timestamp: str
    payload: dict

    @classmethod
    def create(cls, msg_type: str, payload: dict) -> "ProtocolMessage":
        """Create a new protocol message with generated ID and timestamp."""

    def to_json(self) -> str:
        """Serialize to JSON string."""

    @classmethod
    def from_json(cls, json_str: str) -> "ProtocolMessage":
        """Deserialize from JSON string."""


@dataclass
class SessionInfo:
    id: str
    name: str | None
    created: str
    updated: str
    status: str
    unsafe: bool


@dataclass
class ChatEntry:
    timestamp: str
    role: str  # "user" | "assistant"
    content: str
    agent: str | None
    channel: str  # "tui" | "web" | "telegram"


@dataclass
class UsageInfo:
    input_tokens: int
    output_tokens: int
    total_tokens: int
```

---

### 4.4 Channel Connectors

#### 4.4.1 New File: `aletheia/channels/base.py`

**Purpose**: Abstract base class for channel connectors.

```python
class BaseChannelConnector(ABC):
    """
    Abstract base class for channel connectors.

    A channel connector bridges a specific interface (TUI, Web, Telegram)
    with the Aletheia gateway via WebSocket.

    Attributes:
        channel_type: str - Type identifier ("tui", "web", "telegram")
        channel_id: str - Unique instance identifier
        gateway_url: str - WebSocket URL of gateway
        websocket: WebSocket | None - Active connection
        connected: bool - Connection state
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to gateway."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from gateway."""

    @abstractmethod
    async def send_message(self, message: str) -> None:
        """Send chat message to gateway."""

    @abstractmethod
    async def handle_gateway_message(self, message: dict) -> None:
        """Handle incoming message from gateway."""

    @abstractmethod
    async def render_response(self, response: dict) -> None:
        """Render response in channel-specific format."""
```

#### 4.4.2 New File: `aletheia/channels/tui.py`

**Purpose**: TUI channel connector replacing current `_start_investigation()`.

**Class: `TUIChannelConnector`**

```python
class TUIChannelConnector(BaseChannelConnector):
    """
    Terminal User Interface channel connector.

    Uses Rich for terminal rendering and prompt_toolkit for input.
    Connects to gateway via WebSocket.

    Attributes:
        console: Console - Rich console for output
        prompt_session: PromptSession - prompt_toolkit session
        completer: CommandCompleter - Command auto-completion
        live: Live | None - Rich Live display for streaming
    """

    def __init__(self, gateway_url: str = "ws://127.0.0.1:8765"):
        """Initialize TUI connector."""

    async def connect(self) -> None:
        """Connect to gateway and register as TUI channel."""

    async def run(self) -> None:
        """Main TUI event loop."""

    async def handle_gateway_message(self, message: dict) -> None:
        """Route gateway messages to appropriate handlers."""

    async def render_response(self, response: dict) -> None:
        """Render agent response using Rich."""

    async def render_stream_chunk(self, chunk: dict) -> None:
        """Update live display with streaming chunk."""

    def _format_agent_response(self, data: dict) -> str:
        """Format structured response as Markdown."""
```

**Key Implementation Notes**:

1. **Connection Flow**:
   ```python
   async def connect(self):
       self.websocket = await websockets.connect(self.gateway_url)
       await self.send(ProtocolMessage.create("channel_register", {
           "channel_type": "tui",
           "channel_id": str(uuid.uuid4())
       }))
       response = await self.receive()
       if response.type == "channel_registered":
           if response.payload.get("session"):
               self._display_session_info(response.payload["session"])
           else:
               self._prompt_new_session()
   ```

2. **Session Initiation**:
   - If no active session exists when TUI connects, prompt user to create or resume one
   - Session is created via `/new_session` command with options:
     - `/new_session` - Create session with defaults (will prompt for password)
     - `/new_session --verbose` or `/new_session -v` - Enable verbose mode
     - `/new_session --unsafe` or `/new_session -u` - Disable encryption (plaintext scratchpad, no password prompt)
     - `/new_session --verbose --unsafe` - Both options combined
     - `/new_session --name "My Investigation"` - Set custom session name
   - Session can be resumed via `/resume` command:
     - `/resume` - List available sessions and prompt for selection
     - `/resume INC-0001` - Resume specific session by ID (will prompt for password if encrypted)
     - `/resume --unsafe INC-0001` - Resume in unsafe mode (for encrypted sessions without password)
   - Commands are handled locally and sent to gateway as protocol messages

3. **Password Handling (Safe Sessions)**:
   - When creating a **safe session** (`unsafe=false`, the default):
     - TUI prompts user for password using `prompt_toolkit` with hidden input
     - Password is used to derive encryption key (not stored or transmitted)
     - Password confirmation is requested (enter twice)
   - When resuming an **encrypted session**:
     - TUI prompts for password to decrypt the scratchpad
     - On wrong password, gateway returns `SESSION_PASSWORD_INVALID` error
     - User can retry or use `--unsafe` to resume without decryption

   ```python
   async def handle_new_session_command(self, args: list[str]) -> None:
       """Parse /new_session command and create session via gateway."""
       parser = argparse.ArgumentParser(prog="/new_session")
       parser.add_argument("-v", "--verbose", action="store_true")
       parser.add_argument("-u", "--unsafe", action="store_true")
       parser.add_argument("--name", type=str, default=None)
       opts = parser.parse_args(args)

       password = None
       if not opts.unsafe:
           # Prompt for password with confirmation
           password = await self._prompt_password_with_confirmation()
           if password is None:
               self.console.print("[yellow]Session creation cancelled.[/yellow]")
               return

       await self.send(ProtocolMessage.create("session_create", {
           "name": opts.name,
           "verbose": opts.verbose,
           "unsafe": opts.unsafe,
           "password": password  # None if unsafe
       }))

   async def handle_resume_command(self, args: list[str]) -> None:
       """Parse /resume command and resume session via gateway."""
       if not args:
           # List available sessions
           await self.send(ProtocolMessage.create("session_list", {}))
           return

       parser = argparse.ArgumentParser(prog="/resume")
       parser.add_argument("-u", "--unsafe", action="store_true")
       parser.add_argument("session_id", type=str)
       opts = parser.parse_args(args)

       password = None
       if not opts.unsafe:
           # Check if session is encrypted (from cached session list)
           if self._is_session_encrypted(opts.session_id):
               password = await self._prompt_password()
               if password is None:
                   self.console.print("[yellow]Session resume cancelled.[/yellow]")
                   return

       await self.send(ProtocolMessage.create("session_resume", {
           "session_id": opts.session_id,
           "unsafe": opts.unsafe,
           "password": password
       }))

   async def _prompt_password_with_confirmation(self) -> str | None:
       """Prompt for password with confirmation. Returns None if cancelled."""
       password = await self.prompt_session.prompt_async(
           "Enter password for session encryption: ",
           is_password=True
       )
       if not password:
           return None

       confirm = await self.prompt_session.prompt_async(
           "Confirm password: ",
           is_password=True
       )
       if password != confirm:
           self.console.print("[red]Passwords do not match.[/red]")
           return None

       return password

   async def _prompt_password(self) -> str | None:
       """Prompt for password. Returns None if cancelled/empty."""
       return await self.prompt_session.prompt_async(
           "Enter session password: ",
           is_password=True
       )
   ```

3. **Streaming Display**:
   - Use `rich.Live` for real-time updates
   - Buffer JSON chunks until parseable
   - Display structured sections incrementally

4. **Input Handling**:
   - Keep `prompt_toolkit` for command completion
   - Handle local commands (exit, quit) locally
   - Handle session commands locally (parse args, send to gateway):
     - `/new_session` - Create new session
     - `/resume` - Resume existing session
     - `/sessions` - List available sessions
     - `/close` - Close current session
   - Forward chat messages and other slash commands to gateway

#### 4.4.3 Modified File: `aletheia/channels/web.py`

**Purpose**: Web channel connector replacing current `api.py` direct orchestrator usage.

**Changes to `api.py`**:

1. Remove `active_investigations` global dict
2. Remove `get_or_create_orchestrator()` function
3. Replace `run_agent_step()` with WebSocket forwarding
4. Add `WebChannelConnector` class

```python
class WebChannelConnector(BaseChannelConnector):
    """
    Web UI channel connector.

    Bridges FastAPI/SSE with gateway WebSocket.
    Each browser session gets a unique channel instance.

    Attributes:
        session_id: str - Browser session identifier
        event_queue: asyncio.Queue - Queue for SSE events
    """

    async def connect(self) -> None:
        """Connect to gateway for this browser session."""

    async def handle_gateway_message(self, message: dict) -> None:
        """Convert gateway messages to SSE events."""

    async def send_chat(self, user_message: str) -> None:
        """Forward chat message to gateway."""

    async def create_session(self, name: str | None, verbose: bool, unsafe: bool) -> None:
        """Create new session via gateway (called from dialog)."""
```

**Session Initiation (Web Dialog)**:

The Web UI uses a modal dialog for session creation:

1. When no active session exists, the frontend displays a "New Session" dialog
2. Dialog fields:
   - **Session Name** (optional text input)
   - **Verbose Mode** (checkbox, default: unchecked)
   - **Unsafe Mode** (checkbox, default: unchecked) - with warning about plaintext storage
   - **Password** (password input, shown only when Unsafe Mode is unchecked)
   - **Confirm Password** (password input, shown only when Unsafe Mode is unchecked)
3. On submit, frontend calls `POST /sessions` which forwards to gateway
4. Dialog is also accessible via a "New Session" button in the UI header

**Password Handling (Web)**:

- Password fields are displayed when "Unsafe Mode" is unchecked (default)
- Client-side validation ensures passwords match before submission
- Password is transmitted over HTTPS to the local gateway
- For resuming encrypted sessions, a password prompt dialog is shown

```typescript
// Frontend dialog component (React example)
interface NewSessionDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (options: SessionOptions) => void;
}

interface SessionOptions {
  name?: string;
  verbose: boolean;
  unsafe: boolean;
  password?: string;  // Required when unsafe=false
}

// Password prompt for resuming encrypted sessions
interface PasswordPromptDialogProps {
  open: boolean;
  sessionId: string;
  onClose: () => void;
  onSubmit: (password: string) => void;
  onUnsafeResume: () => void;  // Resume without decryption
  error?: string;  // Display password error
}
```

**Resume Session Dialog**:

When user selects an encrypted session to resume:
1. Display password prompt dialog
2. On submit, call `POST /sessions/{id}/resume` with password
3. If `SESSION_PASSWORD_INVALID` error, show error and allow retry
4. Offer "Resume without decryption" option (unsafe mode)

**Modified Endpoints**:

| Endpoint | Current | After Refactor |
|----------|---------|----------------|
| `POST /sessions` | Creates session directly | Forwards to gateway with `{name?, verbose, unsafe}` |
| `POST /sessions/{id}/chat` | Calls orchestrator directly | Forwards to gateway |
| `GET /sessions/{id}/stream` | Reads from local queue | Reads from gateway forwarded events |

#### 4.4.4 Modified File: `aletheia/channels/telegram.py`

**Purpose**: Telegram channel connector replacing current bot implementation.

**Changes to `telegram/bot.py` and `telegram/handlers.py`**:

1. Remove `TelegramSessionManager` (replaced by gateway)
2. Remove direct `init_orchestrator()` calls
3. Add `TelegramChannelConnector` class

```python
class TelegramChannelConnector(BaseChannelConnector):
    """
    Telegram Bot channel connector.

    Bridges python-telegram-bot with gateway WebSocket.
    Maps Telegram user_id to channel connection.

    Attributes:
        bot_token: str - Telegram bot API token
        application: Application - telegram-bot Application
        user_channels: dict[int, str] - user_id → channel_id mapping
    """

    async def connect(self) -> None:
        """Connect to gateway and start Telegram polling."""

    async def handle_telegram_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle Telegram message and forward to gateway."""

    async def handle_gateway_message(self, message: dict) -> None:
        """Handle gateway response and send to Telegram user."""

    async def render_response(self, response: dict) -> None:
        """Format and send response to Telegram."""

    async def handle_new_session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /new_session command from Telegram user."""
```

**Session Initiation (Telegram /new_session Command)**:

Telegram supports the `/new_session` command with options for both safe and unsafe sessions:

- `/new_session` - Create unsafe session (plaintext, default for convenience)
- `/new_session safe` - Create encrypted session (triggers secure password flow)
- `/new_session verbose` - Enable verbose mode
- `/new_session safe verbose` - Both options combined

**Password Handling for Telegram (Safe Sessions)**:

Since Telegram messages are not end-to-end encrypted by default, sending passwords directly via chat is insecure. Two methods are supported:

1. **Secure Web Link (Recommended)**:
   - When user requests a safe session, bot generates a one-time secure link
   - Link points to a local web page (e.g., `http://localhost:8080/auth/<token>`)
   - User opens link in browser and enters password in a secure form
   - Password is transmitted directly to gateway, never through Telegram
   - Token expires after 5 minutes or single use

2. **Direct Message (With Warning)**:
   - User can use `/password <password>` command in private chat
   - Bot immediately deletes the message containing the password
   - Warning is displayed about Telegram's lack of E2E encryption
   - Only allowed in private chats (not groups)

```python
async def handle_new_session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new_session command."""
    args = context.args or []
    verbose = "verbose" in args or "-v" in args
    safe = "safe" in args

    user_id = update.effective_user.id
    channel_id = self.get_channel_for_user(user_id)

    if safe:
        # Generate secure password entry link
        token = await self._generate_auth_token(user_id, channel_id)
        auth_url = f"http://localhost:{self.config.web_auth_port}/auth/{token}"

        await update.message.reply_text(
            "🔐 *Secure Session Setup*\n\n"
            f"To set your encryption password securely, open this link:\n"
            f"`{auth_url}`\n\n"
            "⚠️ Link expires in 5 minutes.\n\n"
            "_Alternatively, use `/password <your-password>` in this private chat "
            "(less secure - message will be deleted immediately)._",
            parse_mode="Markdown"
        )
        # Store pending session info
        self._pending_sessions[user_id] = {
            "token": token,
            "verbose": verbose,
            "channel_id": channel_id
        }
    else:
        # Create unsafe session directly
        await self.send(ProtocolMessage.create("session_create", {
            "verbose": verbose,
            "unsafe": True,
            "channel_id": channel_id
        }))
        await update.message.reply_text("Creating new session (unencrypted)...")

async def handle_password_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /password command for direct password entry."""
    # Only allow in private chats
    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "⚠️ Password commands are only allowed in private chats for security."
        )
        return

    # Immediately delete the message containing the password
    try:
        await update.message.delete()
    except Exception:
        pass  # May fail if bot lacks delete permission

    user_id = update.effective_user.id
    if user_id not in self._pending_sessions:
        await update.effective_chat.send_message(
            "No pending session. Use `/new_session safe` first."
        )
        return

    password = " ".join(context.args) if context.args else None
    if not password:
        await update.effective_chat.send_message(
            "Usage: `/password <your-password>`"
        )
        return

    pending = self._pending_sessions.pop(user_id)

    # Warn about security
    await update.effective_chat.send_message(
        "⚠️ *Security Notice*: Password was sent via Telegram, which is not "
        "end-to-end encrypted. For maximum security, use the web link method.\n\n"
        "Creating encrypted session...",
        parse_mode="Markdown"
    )

    await self.send(ProtocolMessage.create("session_create", {
        "verbose": pending["verbose"],
        "unsafe": False,
        "password": password,
        "channel_id": pending["channel_id"]
    }))

async def handle_resume_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /resume command."""
    args = context.args or []

    if not args:
        # List available sessions
        await self.send(ProtocolMessage.create("session_list", {}))
        return

    session_id = args[0]
    unsafe = "unsafe" in args

    user_id = update.effective_user.id
    channel_id = self.get_channel_for_user(user_id)

    # Check if session is encrypted
    if self._is_session_encrypted(session_id) and not unsafe:
        # Generate auth link for password entry
        token = await self._generate_auth_token(user_id, channel_id, session_id=session_id)
        auth_url = f"http://localhost:{self.config.web_auth_port}/auth/{token}"

        await update.message.reply_text(
            f"🔐 *Resume Encrypted Session {session_id}*\n\n"
            f"Enter your password securely:\n`{auth_url}`\n\n"
            "_Or use `/password <your-password>` in this private chat._",
            parse_mode="Markdown"
        )
        self._pending_resumes[user_id] = {
            "token": token,
            "session_id": session_id,
            "channel_id": channel_id
        }
    else:
        await self.send(ProtocolMessage.create("session_resume", {
            "session_id": session_id,
            "unsafe": unsafe,
            "channel_id": channel_id
        }))
```

**User-Channel Mapping**:

Since Telegram users interact via a single bot, we need to map users to channel connections:

```python
# Each Telegram user gets a unique channel_id
self.user_channels[user_id] = f"telegram-{user_id}-{uuid.uuid4()}"
```

---

### 4.5 Chat History Logger

#### 4.5.1 New File: `aletheia/daemon/history.py`

**Purpose**: Log all chat interactions to session folder.

**Class: `ChatHistoryLogger`**

```python
class ChatHistoryLogger:
    """
    Logs all chat interactions for a session.

    Writes to session folder for persistence and replay.

    Attributes:
        session: Session - Active session
        history_file: Path - Path to history log file
        entries: list[ChatEntry] - In-memory cache of entries
    """

    def __init__(self, session: Session):
        """Initialize logger for session."""

    def log_user_message(
        self,
        message: str,
        channel: str,
        timestamp: datetime | None = None
    ) -> ChatEntry:
        """Log a user message."""

    def log_assistant_response(
        self,
        response: AgentResponse,
        channel: str,
        timestamp: datetime | None = None
    ) -> ChatEntry:
        """Log an assistant response."""

    def get_history(self, limit: int | None = None) -> list[ChatEntry]:
        """Get chat history entries."""

    def _write_entry(self, entry: ChatEntry) -> None:
        """Write entry to history file."""

    def _load_history(self) -> list[ChatEntry]:
        """Load history from file."""
```

#### 4.5.2 History File Format

**Location**: `~/.aletheia/sessions/<session_id>/chat_history.jsonl`

**Format**: JSON Lines (one JSON object per line)

```json
{"timestamp": "2026-02-01T10:30:00Z", "role": "user", "content": "What pods are failing?", "agent": null, "channel": "tui"}
{"timestamp": "2026-02-01T10:30:05Z", "role": "assistant", "content": "{...}", "agent": "kubernetes_data_fetcher", "channel": "tui"}
```

#### 4.5.3 Integration Points

The `ChatHistoryLogger` is used by `GatewaySessionManager`:

```python
# In GatewaySessionManager.send_message()
async def send_message(self, message: str, channel: str) -> AsyncIterator[dict]:
    # Log user message
    self.chat_logger.log_user_message(message, channel)

    # Send to orchestrator
    full_response = ""
    async for chunk in self.orchestrator.agent.run_stream(...):
        full_response += chunk.text
        yield self._format_chunk(chunk)

    # Log complete response
    self.chat_logger.log_assistant_response(
        AgentResponse.parse(full_response),
        channel
    )
```

---

## 5. File-by-File Changes

### 5.1 Files to Modify

#### `aletheia/cli.py`

| Section | Lines | Change |
|---------|-------|--------|
| Imports | 1-67 | Add daemon imports, remove direct orchestrator imports |
| `_build_plugins()` | 144-309 | Move to `aletheia/daemon/plugins.py` |
| `init_orchestrator()` | 321-371 | Move to `aletheia/daemon/session_manager.py` |
| `_start_investigation()` | 374-768 | Replace with `TUIChannelConnector.run()` |
| `session_open()` | 783-874 | Modify to connect to gateway instead of direct session |
| `session_resume()` | 937-1017 | Modify to connect to gateway |
| `serve()` | 1323-1357 | Modify to use `WebChannelConnector` |
| `telegram_serve()` | 1446-1513 | Modify to use `TelegramChannelConnector` |
| New commands | N/A | Add `start`, `stop`, `status`, `connect` commands |

**New CLI Commands**:

```python
@app.command("start")
def start_daemon(
    host: str = typer.Option("127.0.0.1", help="Host to bind"),
    port: int = typer.Option(8765, help="Port to bind"),
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Run as background daemon"),
    enable_memory: bool = typer.Option(True, "--enable-memory/--disable-memory"),
) -> None:
    """Start the Aletheia gateway daemon."""

@app.command("stop")
def stop_daemon() -> None:
    """Stop the running Aletheia gateway daemon."""

@app.command("status")
def daemon_status() -> None:
    """Check the status of the Aletheia gateway daemon."""

@app.command("connect")
def connect_tui(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Connect TUI to the running gateway daemon."""
```

#### `aletheia/session.py`

| Section | Lines | Change |
|---------|-------|--------|
| `SessionMetadata` | 55-89 | Add `chat_history_file` property |
| `Session` | 92-767 | Add `get_chat_history_path()` method |

**New Method**:

```python
@property
def chat_history_file(self) -> Path:
    """Path to chat history file."""
    return self.session_path / "chat_history.jsonl"
```

#### `aletheia/api.py`

| Section | Lines | Change |
|---------|-------|--------|
| Globals | 29-31, 88-91 | Remove `_engram_instance`, `active_investigations`, `investigation_queues` |
| `get_or_create_orchestrator()` | 397-464 | Remove - gateway handles this |
| `run_agent_step()` | 467-599 | Remove - replaced by WebSocket forwarding |
| `chat_session()` | 684-737 | Rewrite to forward to gateway |
| `stream_session()` | 740-770 | Rewrite to stream from gateway |
| New | N/A | Add `WebChannelConnector` instance management |

#### `aletheia/telegram/bot.py`

| Section | Lines | Change |
|---------|-------|--------|
| `run_telegram_bot()` | 108-201 | Replace with `TelegramChannelConnector` initialization |
| Remove | Various | Remove direct session/orchestrator management |

#### `aletheia/telegram/handlers.py`

| Section | Lines | Change |
|---------|-------|--------|
| All handlers | All | Rewrite to forward messages to gateway via WebSocket |
| `TelegramSessionManager` usage | Various | Remove - gateway manages sessions |

#### `aletheia/telegram/session_manager.py`

**Action**: Delete this file (functionality moved to `GatewaySessionManager`)

#### `aletheia/config.py`

| Section | Lines | Change |
|---------|-------|--------|
| `Config` class | Various | Add daemon configuration options |

**New Configuration Options**:

```python
# Daemon configuration
daemon_host: str = "127.0.0.1"
daemon_port: int = 8765
daemon_pid_file: str | None = None  # Default: ~/.aletheia/aletheia.pid
daemon_log_file: str | None = None  # Default: ~/.aletheia/daemon.log

# Auth server configuration (for secure password entry via Telegram)
auth_server_enabled: bool = True
auth_server_host: str = "127.0.0.1"
auth_server_port: int = 8766
auth_token_expiry: int = 300  # seconds (5 minutes)
```

### 5.2 Files to Keep Unchanged

| File | Reason |
|------|--------|
| `aletheia/agents/*.py` | Agent implementation unchanged |
| `aletheia/plugins/*.py` | Plugin implementation unchanged |
| `aletheia/encryption.py` | Encryption logic unchanged |
| `aletheia/engram/*.py` | Memory system unchanged |
| `aletheia/knowledge/*.py` | Knowledge base unchanged |
| `aletheia/mcp/*.py` | MCP support unchanged |
| `aletheia/commands.py` | Commands system unchanged |

---

## 6. New Files to Create

### 6.1 Daemon Module

| File | Purpose |
|------|---------|
| `aletheia/daemon/__init__.py` | Module exports |
| `aletheia/daemon/gateway.py` | Main gateway class |
| `aletheia/daemon/server.py` | WebSocket server |
| `aletheia/daemon/auth.py` | Secure password entry HTTP server for Telegram |
| `aletheia/daemon/session_manager.py` | Gateway session management |
| `aletheia/daemon/protocol.py` | WebSocket message protocol |
| `aletheia/daemon/history.py` | Chat history logger |
| `aletheia/daemon/plugins.py` | Plugin builder (moved from cli.py) |
| `aletheia/daemon/pid.py` | PID file management for daemon mode |

### 6.2 Channels Module

| File | Purpose |
|------|---------|
| `aletheia/channels/__init__.py` | Module exports |
| `aletheia/channels/base.py` | Abstract base connector with lifecycle hooks |
| `aletheia/channels/registry.py` | Channel plugin registry and discovery |
| `aletheia/channels/manifest.py` | Channel manifest and capabilities definitions |
| `aletheia/channels/config.py` | Per-channel configuration schema and validation |
| `aletheia/channels/exceptions.py` | Channel-specific exceptions |
| `aletheia/channels/tui.py` | TUI channel connector |
| `aletheia/channels/web.py` | Web channel connector |
| `aletheia/channels/telegram.py` | Telegram channel connector |

### 6.3 Directory Structure

```
aletheia/
├── daemon/
│   ├── __init__.py
│   ├── gateway.py          # AletheiaGateway class
│   ├── server.py           # WebSocketServer class
│   ├── auth.py             # AuthServer for secure password entry
│   ├── session_manager.py  # GatewaySessionManager class
│   ├── protocol.py         # Protocol messages and data classes
│   ├── history.py          # ChatHistoryLogger class
│   ├── plugins.py          # build_plugins() function
│   └── pid.py              # PID file management
├── channels/
│   ├── __init__.py
│   ├── base.py             # BaseChannelConnector ABC with lifecycle hooks
│   ├── registry.py         # ChannelRegistry for plugin discovery
│   ├── manifest.py         # ChannelManifest and ChannelCapability
│   ├── config.py           # Channel configuration validation
│   ├── exceptions.py       # ChannelError, ConnectionError, etc.
│   ├── tui.py              # TUIChannelConnector (built-in)
│   ├── web.py              # WebChannelConnector (built-in)
│   └── telegram.py         # TelegramChannelConnector (built-in)
├── ...existing modules...
```

---

## 7. Data Models

### 7.1 New Data Classes

#### `aletheia/daemon/protocol.py`

```python
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any
import json
import uuid


@dataclass
class ProtocolMessage:
    """Base WebSocket protocol message."""
    type: str
    id: str
    timestamp: str
    payload: dict[str, Any]

    @classmethod
    def create(cls, msg_type: str, payload: dict[str, Any] | None = None) -> "ProtocolMessage":
        return cls(
            type=msg_type,
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            payload=payload or {}
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "ProtocolMessage":
        obj = json.loads(data)
        return cls(**obj)


@dataclass
class SessionInfo:
    """Session information for protocol messages."""
    id: str
    name: str | None
    created: str
    updated: str
    status: str
    unsafe: bool
    total_input_tokens: int = 0
    total_output_tokens: int = 0


@dataclass
class ChatEntry:
    """Single chat history entry."""
    timestamp: str
    role: str  # "user" | "assistant"
    content: str
    agent: str | None
    channel: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ChatEntry":
        return cls(**data)


@dataclass
class ChannelInfo:
    """Connected channel information."""
    channel_id: str
    channel_type: str  # "tui" | "web" | "telegram"
    connected_at: str
    user_id: str | None = None  # For Telegram


@dataclass
class UsageInfo:
    """Token usage information."""
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass
class StreamChunk:
    """Streaming response chunk."""
    message_id: str
    chunk_type: str
    content: Any
```

### 7.2 Updated Session Directory Structure

```
~/.aletheia/sessions/<session_id>/
├── metadata.json           # Session metadata (existing)
├── scratchpad.md           # Plaintext scratchpad (existing, if unsafe)
├── scratchpad.encrypted    # Encrypted scratchpad (existing, if safe)
├── chat_history.jsonl      # NEW: Chat history log
├── salt                    # Encryption salt (existing, if safe)
├── .canary                 # Password validation (existing, if safe)
└── data/
    ├── logs/               # Collected logs (existing)
    ├── metrics/            # Collected metrics (existing)
    └── traces/             # Collected traces (existing)
```

---

## 8. Migration Strategy

### 8.1 Phase 1: Foundation (Non-Breaking)

**Goal**: Create daemon infrastructure without breaking existing functionality.

**Steps**:

1. Create `aletheia/daemon/` module with all new classes
2. Create `aletheia/channels/` module with base class
3. Add new CLI commands (`start`, `stop`, `status`)
4. Add daemon configuration options
5. Write unit tests for new modules

**Verification**:
- All existing commands still work unchanged
- New daemon can start/stop independently
- Unit tests pass

### 8.2 Phase 2: TUI Channel (First Integration)

**Goal**: Make TUI work via gateway while keeping legacy mode.

**Steps**:

1. Implement `TUIChannelConnector`
2. Add `connect` CLI command
3. Modify `session open` to optionally use gateway
4. Add `--legacy` flag to preserve old behavior

**Verification**:
- `aletheia start` + `aletheia connect` works
- `aletheia session open --legacy` uses old direct mode
- Chat history is logged

### 8.3 Phase 3: Web Channel

**Goal**: Make Web UI work via gateway.

**Steps**:

1. Implement `WebChannelConnector`
2. Modify `api.py` to use connector
3. Update frontend if needed for new SSE format
4. Test session sharing between TUI and Web

**Verification**:
- Web UI connects to running gateway
- TUI and Web can share same session
- History visible from both channels

### 8.4 Phase 4: Telegram Channel

**Goal**: Make Telegram work via gateway.

**Steps**:

1. Implement `TelegramChannelConnector`
2. Modify `telegram/bot.py` to use connector
3. Remove `TelegramSessionManager`
4. Test multi-channel session access

**Verification**:
- Telegram bot connects to gateway
- Users can interact via any channel
- Session state is shared

### 8.5 Phase 5: Cleanup

**Goal**: Remove legacy code and finalize.

**Steps**:

1. Remove `--legacy` flags
2. Delete obsolete code paths
3. Update documentation
4. Final integration tests

---

## 9. Configuration Changes

### 9.1 New Configuration Options

Add to `aletheia/config.py`:

```python
class Config(BaseSettings):
    # ... existing fields ...

    # Daemon Configuration
    daemon_host: str = "127.0.0.1"
    daemon_port: int = 8765
    daemon_pid_file: str | None = None
    daemon_log_file: str | None = None
    daemon_socket_timeout: int = 30  # seconds
    daemon_heartbeat_interval: int = 15  # seconds
```

### 9.2 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALETHEIA_DAEMON_HOST` | `127.0.0.1` | Gateway bind address |
| `ALETHEIA_DAEMON_PORT` | `8765` | Gateway WebSocket port |
| `ALETHEIA_DAEMON_PID_FILE` | `~/.aletheia/aletheia.pid` | PID file location |
| `ALETHEIA_DAEMON_LOG_FILE` | `~/.aletheia/daemon.log` | Daemon log location |
| `ALETHEIA_AUTH_SERVER_ENABLED` | `true` | Enable auth server for secure password entry |
| `ALETHEIA_AUTH_SERVER_HOST` | `127.0.0.1` | Auth server bind address |
| `ALETHEIA_AUTH_SERVER_PORT` | `8766` | Auth server HTTP port |
| `ALETHEIA_AUTH_TOKEN_EXPIRY` | `300` | Auth token expiry in seconds |

### 9.3 OS Daemon Integration

#### 9.3.1 Linux (systemd)

Create `/etc/systemd/system/aletheia.service`:

```ini
[Unit]
Description=Aletheia AI Troubleshooting Gateway
After=network.target

[Service]
Type=simple
User=<username>
ExecStart=/path/to/aletheia start
ExecStop=/path/to/aletheia stop
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### 9.3.2 macOS (launchctl)

Create `~/Library/LaunchAgents/com.aletheia.gateway.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.aletheia.gateway</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/aletheia</string>
        <string>start</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

---

## 10. Testing Requirements

### 10.1 Unit Tests

| Module | Test File | Coverage |
|--------|-----------|----------|
| `daemon/gateway.py` | `tests/daemon/test_gateway.py` | Start/stop, connection handling |
| `daemon/server.py` | `tests/daemon/test_server.py` | WebSocket server operations |
| `daemon/auth.py` | `tests/daemon/test_auth.py` | Token generation, expiry, password form |
| `daemon/session_manager.py` | `tests/daemon/test_session_manager.py` | Session CRUD, orchestrator management |
| `daemon/protocol.py` | `tests/daemon/test_protocol.py` | Message serialization |
| `daemon/history.py` | `tests/daemon/test_history.py` | History logging and retrieval |
| `channels/registry.py` | `tests/channels/test_registry.py` | Plugin discovery, registration, lifecycle |
| `channels/manifest.py` | `tests/channels/test_manifest.py` | Manifest validation, capability checks |
| `channels/base.py` | `tests/channels/test_base.py` | Base connector, lifecycle hooks, reconnection |
| `channels/tui.py` | `tests/channels/test_tui.py` | TUI connector operations |
| `channels/web.py` | `tests/channels/test_web.py` | Web connector operations |
| `channels/telegram.py` | `tests/channels/test_telegram.py` | Telegram connector operations |

### 10.2 Integration Tests

| Test | Description |
|------|-------------|
| `test_gateway_lifecycle` | Start daemon, connect TUI, send messages, stop |
| `test_session_persistence` | Create session, close, resume, verify history |
| `test_multi_channel_session` | TUI and Web sharing same session |
| `test_channel_disconnect_reconnect` | Disconnect TUI, reconnect, verify state |
| `test_session_switching` | Switch between sessions, verify context |
| `test_history_logging` | Verify all messages logged correctly |
| `test_channel_plugin_discovery` | Install plugin, verify auto-discovery on restart |
| `test_channel_capability_adaptation` | Verify responses adapted based on capabilities |
| `test_custom_channel_lifecycle` | Custom channel connect, message, disconnect |
| `test_channel_config_validation` | Invalid config rejected, valid config accepted |
| `test_tui_password_prompt` | TUI prompts for password on safe session create/resume |
| `test_web_password_dialog` | Web dialog collects password for safe sessions |
| `test_telegram_auth_flow` | Telegram secure auth via web link |
| `test_telegram_direct_password` | Telegram /password command with message deletion |
| `test_session_password_invalid` | Wrong password returns error, allows retry |
| `test_auth_token_expiry` | Expired tokens rejected |

### 10.3 E2E Tests

| Test | Description |
|------|-------------|
| `test_full_investigation_tui` | Complete investigation via TUI |
| `test_full_investigation_web` | Complete investigation via Web |
| `test_full_investigation_telegram` | Complete investigation via Telegram |
| `test_cross_channel_investigation` | Start in TUI, continue in Web |

### 10.4 Performance Tests

| Test | Metric |
|------|--------|
| Connection establishment | < 100ms |
| Message round-trip | < 50ms overhead |
| Concurrent connections | Support 10+ channels |
| Memory usage | < 100MB idle daemon |

---

## 11. Channel Extensibility System

### 11.1 Overview

The channel architecture is designed to be extensible, allowing developers to add new communication channels (e.g., Slack, Discord, Matrix, SMS, Voice) without modifying core gateway code. This is achieved through:

1. **Channel Plugin Registry** - Dynamic registration and discovery of channel connectors
2. **Channel Manifest** - Declarative channel metadata and capabilities
3. **Channel Lifecycle Hooks** - Standard hooks for initialization, connection, and cleanup
4. **Channel Configuration Schema** - Per-channel configuration with validation

### 11.2 Channel Plugin Architecture

#### 11.2.1 New File: `aletheia/channels/registry.py`

**Purpose**: Central registry for channel plugins with discovery and loading.

```python
from typing import Type
from importlib import import_module
from importlib.metadata import entry_points


class ChannelRegistry:
    """
    Central registry for channel connectors.

    Supports both built-in channels and external plugins.
    External plugins are discovered via Python entry points.

    Attributes:
        channels: dict[str, Type[BaseChannelConnector]] - Registered channel types
        manifests: dict[str, ChannelManifest] - Channel metadata
    """

    _instance: "ChannelRegistry | None" = None

    def __init__(self):
        self.channels: dict[str, Type[BaseChannelConnector]] = {}
        self.manifests: dict[str, ChannelManifest] = {}

    @classmethod
    def get_instance(cls) -> "ChannelRegistry":
        """Get or create the singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load_builtin_channels()
            cls._instance._discover_plugins()
        return cls._instance

    def register(
        self,
        channel_type: str,
        connector_class: Type[BaseChannelConnector],
        manifest: "ChannelManifest"
    ) -> None:
        """Register a channel connector class."""
        if channel_type in self.channels:
            raise ValueError(f"Channel type '{channel_type}' already registered")
        self.channels[channel_type] = connector_class
        self.manifests[channel_type] = manifest

    def unregister(self, channel_type: str) -> None:
        """Unregister a channel connector."""
        self.channels.pop(channel_type, None)
        self.manifests.pop(channel_type, None)

    def get_connector_class(self, channel_type: str) -> Type[BaseChannelConnector]:
        """Get a connector class by type."""
        if channel_type not in self.channels:
            raise ValueError(f"Unknown channel type: {channel_type}")
        return self.channels[channel_type]

    def create_connector(
        self,
        channel_type: str,
        config: dict | None = None
    ) -> BaseChannelConnector:
        """Create a new connector instance."""
        cls = self.get_connector_class(channel_type)
        return cls(**(config or {}))

    def list_channels(self) -> list[ChannelManifest]:
        """List all registered channels with their manifests."""
        return list(self.manifests.values())

    def _load_builtin_channels(self) -> None:
        """Load built-in channel connectors."""
        from aletheia.channels.tui import TUIChannelConnector
        from aletheia.channels.web import WebChannelConnector
        from aletheia.channels.telegram import TelegramChannelConnector

        self.register("tui", TUIChannelConnector, TUIChannelConnector.manifest())
        self.register("web", WebChannelConnector, WebChannelConnector.manifest())
        self.register("telegram", TelegramChannelConnector, TelegramChannelConnector.manifest())

    def _discover_plugins(self) -> None:
        """Discover and load channel plugins from entry points."""
        discovered = entry_points(group="aletheia.channels")
        for ep in discovered:
            try:
                connector_class = ep.load()
                manifest = connector_class.manifest()
                self.register(manifest.channel_type, connector_class, manifest)
            except Exception as e:
                # Log warning but don't fail - plugin errors shouldn't break core
                import logging
                logging.warning(f"Failed to load channel plugin '{ep.name}': {e}")
```

#### 11.2.2 New File: `aletheia/channels/manifest.py`

**Purpose**: Declarative channel metadata and capabilities.

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChannelCapability(Enum):
    """Channel capabilities that affect gateway behavior."""
    STREAMING = "streaming"           # Supports streaming responses
    RICH_TEXT = "rich_text"          # Supports markdown/formatting
    IMAGES = "images"                 # Can display images
    FILE_UPLOAD = "file_upload"       # Can upload files
    FILE_DOWNLOAD = "file_download"   # Can download files
    INTERACTIVE = "interactive"       # Supports interactive elements (buttons, etc.)
    MULTI_USER = "multi_user"         # Supports multiple users per channel instance
    PERSISTENT = "persistent"         # Maintains persistent connection
    SECURE = "secure"                 # Provides E2E encryption
    VOICE = "voice"                   # Supports voice input/output


@dataclass
class ChannelManifest:
    """
    Declarative metadata for a channel connector.

    Attributes:
        channel_type: str - Unique identifier (e.g., "slack", "discord")
        display_name: str - Human-readable name
        description: str - Channel description
        version: str - Connector version (semver)
        author: str - Author or maintainer
        capabilities: set[ChannelCapability] - Supported capabilities
        config_schema: dict - JSON Schema for channel configuration
        requires_daemon: bool - Whether channel requires gateway daemon
        max_message_length: int | None - Maximum message length (None = unlimited)
        supports_threading: bool - Supports threaded conversations
        documentation_url: str | None - Link to documentation
    """
    channel_type: str
    display_name: str
    description: str
    version: str = "1.0.0"
    author: str = "Aletheia Team"
    capabilities: set[ChannelCapability] = field(default_factory=set)
    config_schema: dict[str, Any] = field(default_factory=dict)
    requires_daemon: bool = True
    max_message_length: int | None = None
    supports_threading: bool = False
    documentation_url: str | None = None

    def has_capability(self, capability: ChannelCapability) -> bool:
        """Check if channel has a specific capability."""
        return capability in self.capabilities

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "channel_type": self.channel_type,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "capabilities": [c.value for c in self.capabilities],
            "config_schema": self.config_schema,
            "requires_daemon": self.requires_daemon,
            "max_message_length": self.max_message_length,
            "supports_threading": self.supports_threading,
            "documentation_url": self.documentation_url,
        }
```

### 11.3 Extended Base Channel Connector

Update `aletheia/channels/base.py` with plugin support:

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, Any
import asyncio
import logging

from aletheia.channels.manifest import ChannelManifest, ChannelCapability


class BaseChannelConnector(ABC):
    """
    Abstract base class for channel connectors.

    To implement a new channel:
    1. Subclass BaseChannelConnector
    2. Implement all abstract methods
    3. Override manifest() class method with channel metadata
    4. Optionally override lifecycle hooks

    Attributes:
        channel_type: str - Type identifier from manifest
        channel_id: str - Unique instance identifier
        gateway_url: str - WebSocket URL of gateway
        websocket: WebSocket | None - Active connection
        connected: bool - Connection state
        config: dict - Channel-specific configuration
        logger: Logger - Channel-specific logger
    """

    def __init__(
        self,
        gateway_url: str = "ws://127.0.0.1:8765",
        config: dict[str, Any] | None = None
    ):
        self.gateway_url = gateway_url
        self.config = config or {}
        self.websocket = None
        self.connected = False
        self.channel_id: str | None = None
        self.logger = logging.getLogger(f"aletheia.channel.{self.manifest().channel_type}")
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 1.0

    @classmethod
    @abstractmethod
    def manifest(cls) -> ChannelManifest:
        """
        Return the channel manifest with metadata and capabilities.

        Must be implemented by all channel connectors.

        Example:
            @classmethod
            def manifest(cls) -> ChannelManifest:
                return ChannelManifest(
                    channel_type="slack",
                    display_name="Slack",
                    description="Slack workspace integration",
                    capabilities={
                        ChannelCapability.STREAMING,
                        ChannelCapability.RICH_TEXT,
                        ChannelCapability.MULTI_USER,
                    },
                    max_message_length=4000,
                )
        """
        pass

    # === Connection Lifecycle ===

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to gateway."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from gateway."""
        pass

    async def reconnect(self) -> bool:
        """
        Attempt to reconnect with exponential backoff.

        Returns True if reconnection successful, False otherwise.
        """
        while self._reconnect_attempts < self._max_reconnect_attempts:
            self._reconnect_attempts += 1
            delay = self._reconnect_delay * (2 ** (self._reconnect_attempts - 1))
            self.logger.info(f"Reconnecting in {delay}s (attempt {self._reconnect_attempts})")

            await asyncio.sleep(delay)

            try:
                await self.connect()
                self._reconnect_attempts = 0
                return True
            except Exception as e:
                self.logger.warning(f"Reconnection failed: {e}")

        self.logger.error("Max reconnection attempts reached")
        return False

    # === Message Handling ===

    @abstractmethod
    async def send_message(self, message: str) -> None:
        """Send chat message to gateway."""
        pass

    @abstractmethod
    async def handle_gateway_message(self, message: dict) -> None:
        """Handle incoming message from gateway."""
        pass

    @abstractmethod
    async def render_response(self, response: dict) -> None:
        """Render response in channel-specific format."""
        pass

    # === Lifecycle Hooks (Optional Overrides) ===

    async def on_connect(self) -> None:
        """
        Called after successful connection to gateway.

        Override to perform channel-specific initialization.
        """
        pass

    async def on_disconnect(self) -> None:
        """
        Called before disconnection from gateway.

        Override to perform channel-specific cleanup.
        """
        pass

    async def on_session_created(self, session_info: dict) -> None:
        """
        Called when a new session is created.

        Override to handle session creation events.
        """
        pass

    async def on_session_resumed(self, session_info: dict, history: list) -> None:
        """
        Called when a session is resumed.

        Override to handle session resumption and history display.
        """
        pass

    async def on_error(self, error: dict) -> None:
        """
        Called when an error is received from gateway.

        Override to handle errors in channel-specific way.
        """
        self.logger.error(f"Gateway error: {error.get('message', 'Unknown error')}")

    # === Utility Methods ===

    def validate_config(self) -> list[str]:
        """
        Validate channel configuration against schema.

        Returns list of validation error messages (empty if valid).
        """
        errors = []
        schema = self.manifest().config_schema

        # Check required fields
        for field, spec in schema.get("properties", {}).items():
            if field in schema.get("required", []) and field not in self.config:
                errors.append(f"Missing required config: {field}")

        return errors

    def has_capability(self, capability: ChannelCapability) -> bool:
        """Check if this channel has a specific capability."""
        return self.manifest().has_capability(capability)

    def truncate_message(self, message: str) -> str:
        """Truncate message to channel's max length if needed."""
        max_len = self.manifest().max_message_length
        if max_len and len(message) > max_len:
            return message[:max_len - 3] + "..."
        return message
```

### 11.4 Channel Plugin Development Guide

#### 11.4.1 Creating a New Channel Plugin

To create a new channel (e.g., Slack), follow these steps:

**Step 1: Create the connector class**

```python
# aletheia_slack/connector.py

from aletheia.channels.base import BaseChannelConnector
from aletheia.channels.manifest import ChannelManifest, ChannelCapability
from aletheia.daemon.protocol import ProtocolMessage
import websockets


class SlackChannelConnector(BaseChannelConnector):
    """
    Slack channel connector for Aletheia.

    Bridges Slack Bot API with Aletheia gateway via WebSocket.
    """

    @classmethod
    def manifest(cls) -> ChannelManifest:
        return ChannelManifest(
            channel_type="slack",
            display_name="Slack",
            description="Integrate Aletheia with Slack workspaces",
            version="1.0.0",
            author="Your Name",
            capabilities={
                ChannelCapability.STREAMING,
                ChannelCapability.RICH_TEXT,
                ChannelCapability.IMAGES,
                ChannelCapability.FILE_UPLOAD,
                ChannelCapability.MULTI_USER,
                ChannelCapability.INTERACTIVE,
            },
            config_schema={
                "type": "object",
                "required": ["bot_token", "app_token"],
                "properties": {
                    "bot_token": {
                        "type": "string",
                        "description": "Slack Bot OAuth token (xoxb-...)"
                    },
                    "app_token": {
                        "type": "string",
                        "description": "Slack App-level token (xapp-...)"
                    },
                    "allowed_channels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of allowed Slack channel IDs"
                    }
                }
            },
            max_message_length=4000,
            supports_threading=True,
            documentation_url="https://github.com/your/aletheia-slack"
        )

    def __init__(self, gateway_url: str = "ws://127.0.0.1:8765", config: dict = None):
        super().__init__(gateway_url, config)
        self.bot_token = self.config.get("bot_token")
        self.app_token = self.config.get("app_token")
        self.slack_client = None
        self.user_channels: dict[str, str] = {}  # slack_user_id → channel_id

    async def connect(self) -> None:
        """Connect to gateway and initialize Slack client."""
        # Validate configuration
        errors = self.validate_config()
        if errors:
            raise ValueError(f"Invalid config: {', '.join(errors)}")

        # Connect to Aletheia gateway
        self.websocket = await websockets.connect(self.gateway_url)

        # Register with gateway
        await self._send(ProtocolMessage.create("channel_register", {
            "channel_type": "slack",
            "channel_id": f"slack-{self.config.get('workspace_id', 'default')}"
        }))

        response = await self._receive()
        if response.type == "channel_registered":
            self.connected = True
            self.channel_id = response.payload.get("channel_id")
            await self.on_connect()

        # Initialize Slack client
        await self._init_slack_client()

    async def disconnect(self) -> None:
        """Disconnect from gateway and Slack."""
        await self.on_disconnect()
        if self.websocket:
            await self._send(ProtocolMessage.create("channel_unregister", {}))
            await self.websocket.close()
        self.connected = False

    async def send_message(self, message: str) -> None:
        """Send message to gateway."""
        await self._send(ProtocolMessage.create("chat_message", {
            "message": message
        }))

    async def handle_gateway_message(self, message: dict) -> None:
        """Route gateway messages to appropriate handlers."""
        msg_type = message.get("type")

        if msg_type == "chat_stream_start":
            await self._handle_stream_start(message)
        elif msg_type == "chat_stream_chunk":
            await self._handle_stream_chunk(message)
        elif msg_type == "chat_stream_end":
            await self._handle_stream_end(message)
        elif msg_type == "error":
            await self.on_error(message.get("payload", {}))

    async def render_response(self, response: dict) -> None:
        """Format and send response to Slack."""
        # Convert to Slack Block Kit format
        blocks = self._format_as_blocks(response)

        # Send to Slack
        await self.slack_client.chat_postMessage(
            channel=response.get("slack_channel"),
            blocks=blocks,
            thread_ts=response.get("thread_ts")
        )

    # === Slack-specific methods ===

    async def _init_slack_client(self) -> None:
        """Initialize Slack Bolt app."""
        from slack_bolt.async_app import AsyncApp

        self.slack_app = AsyncApp(
            token=self.bot_token,
            signing_secret=self.config.get("signing_secret")
        )

        # Register Slack event handlers
        @self.slack_app.message("")
        async def handle_message(message, say):
            await self._on_slack_message(message, say)

    async def _on_slack_message(self, message: dict, say) -> None:
        """Handle incoming Slack message."""
        user_id = message.get("user")
        text = message.get("text", "")
        channel = message.get("channel")

        # Forward to gateway
        await self.send_message(text)

    def _format_as_blocks(self, response: dict) -> list:
        """Convert response to Slack Block Kit format."""
        # Implementation specific to Slack formatting
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": response.get("content", "")
                }
            }
        ]

    async def _send(self, message: ProtocolMessage) -> None:
        """Send protocol message to gateway."""
        await self.websocket.send(message.to_json())

    async def _receive(self) -> ProtocolMessage:
        """Receive protocol message from gateway."""
        data = await self.websocket.recv()
        return ProtocolMessage.from_json(data)
```

**Step 2: Create package entry point**

```python
# aletheia_slack/__init__.py

from aletheia_slack.connector import SlackChannelConnector

__all__ = ["SlackChannelConnector"]
```

**Step 3: Configure entry point in pyproject.toml**

```toml
# pyproject.toml

[project]
name = "aletheia-slack"
version = "1.0.0"
dependencies = [
    "aletheia>=1.0.0",
    "slack-bolt>=1.18.0",
]

[project.entry-points."aletheia.channels"]
slack = "aletheia_slack:SlackChannelConnector"
```

**Step 4: Install the plugin**

```bash
pip install aletheia-slack
# or for development
pip install -e ./aletheia-slack
```

The channel will be automatically discovered and registered on gateway startup.

#### 11.4.2 Channel Configuration

Channels are configured via the main Aletheia config file or environment variables:

```yaml
# ~/.aletheia/config.yaml

channels:
  slack:
    enabled: true
    bot_token: "${SLACK_BOT_TOKEN}"
    app_token: "${SLACK_APP_TOKEN}"
    allowed_channels:
      - "C0123456789"
      - "C9876543210"

  discord:
    enabled: true
    bot_token: "${DISCORD_BOT_TOKEN}"
    guild_ids:
      - "123456789"
```

#### 11.4.3 CLI Commands for Channel Management

Add new commands to manage channels:

```python
@channel_app.command("list")
def list_channels() -> None:
    """List all registered channel connectors."""

@channel_app.command("info")
def channel_info(channel_type: str) -> None:
    """Show detailed information about a channel."""

@channel_app.command("enable")
def enable_channel(channel_type: str) -> None:
    """Enable a channel connector."""

@channel_app.command("disable")
def disable_channel(channel_type: str) -> None:
    """Disable a channel connector."""

@channel_app.command("test")
def test_channel(channel_type: str) -> None:
    """Test channel connectivity and configuration."""
```

### 11.5 New Files for Channel Extensibility

| File | Purpose |
|------|---------|
| `aletheia/channels/registry.py` | Channel plugin registry with discovery |
| `aletheia/channels/manifest.py` | Channel manifest and capabilities |
| `aletheia/channels/config.py` | Per-channel configuration schema and validation |
| `aletheia/channels/exceptions.py` | Channel-specific exceptions |

### 11.6 Gateway Integration

Update `AletheiaGateway` to use the channel registry:

```python
# In aletheia/daemon/gateway.py

from aletheia.channels.registry import ChannelRegistry

class AletheiaGateway:
    def __init__(self, config: Config, enable_memory: bool = True):
        # ... existing init ...
        self.channel_registry = ChannelRegistry.get_instance()
        self.active_channels: dict[str, BaseChannelConnector] = {}

    async def handle_connection(self, websocket: WebSocket, path: str) -> None:
        """Handle new WebSocket connection."""
        try:
            # Wait for channel registration message
            raw_message = await websocket.recv()
            message = ProtocolMessage.from_json(raw_message)

            if message.type != "channel_register":
                await websocket.close(1002, "Expected channel_register")
                return

            channel_type = message.payload.get("channel_type")
            channel_id = message.payload.get("channel_id")

            # Validate channel type is registered
            if channel_type not in self.channel_registry.channels:
                await self._send_error(websocket, "UNKNOWN_CHANNEL_TYPE",
                    f"Channel type '{channel_type}' not registered")
                return

            # Register the connection
            self.websocket_server.register_connection(channel_id, websocket)
            self.active_channels[channel_id] = {
                "type": channel_type,
                "manifest": self.channel_registry.manifests[channel_type],
                "connected_at": datetime.now().isoformat()
            }

            # Send confirmation with session info if available
            await self._send(websocket, ProtocolMessage.create("channel_registered", {
                "channel_id": channel_id,
                "session": self._get_session_info() if self.session_manager.active_session else None
            }))

            # Start message handling loop
            await self._handle_channel_messages(websocket, channel_id, channel_type)

        except websockets.ConnectionClosed:
            pass
        finally:
            if channel_id:
                self.websocket_server.unregister_connection(channel_id)
                self.active_channels.pop(channel_id, None)

    def get_channel_capabilities(self, channel_id: str) -> set[ChannelCapability]:
        """Get capabilities of a connected channel."""
        channel_info = self.active_channels.get(channel_id)
        if channel_info:
            return channel_info["manifest"].capabilities
        return set()
```

### 11.7 Response Adaptation Based on Capabilities

The gateway adapts responses based on channel capabilities:

```python
# In aletheia/daemon/session_manager.py

async def send_message(
    self,
    message: str,
    channel_id: str,
    channel_capabilities: set[ChannelCapability]
) -> AsyncIterator[dict]:
    """Send message and yield adapted response chunks."""

    async for chunk in self.orchestrator.agent.run_stream(...):
        adapted_chunk = self._adapt_chunk(chunk, channel_capabilities)
        yield adapted_chunk

def _adapt_chunk(
    self,
    chunk: dict,
    capabilities: set[ChannelCapability]
) -> dict:
    """Adapt response chunk based on channel capabilities."""

    # Remove images if channel doesn't support them
    if ChannelCapability.IMAGES not in capabilities:
        chunk = self._strip_images(chunk)

    # Convert rich text to plain if not supported
    if ChannelCapability.RICH_TEXT not in capabilities:
        chunk = self._to_plain_text(chunk)

    # Remove interactive elements if not supported
    if ChannelCapability.INTERACTIVE not in capabilities:
        chunk = self._strip_interactive(chunk)

    return chunk
```

### 11.8 Example Channel Implementations

The following channels could be implemented as plugins:

| Channel | Priority | Complexity | Notes |
|---------|----------|------------|-------|
| Slack | High | Medium | Popular enterprise chat, rich API |
| Discord | Medium | Medium | Gaming/community focused |
| Matrix | Medium | Medium | Open protocol, federated |
| Microsoft Teams | High | High | Enterprise, complex auth |
| SMS (Twilio) | Low | Low | Text-only, simple |
| Voice (Whisper+TTS) | Low | High | Requires audio processing |
| Mattermost | Low | Low | Similar to Slack API |
| IRC | Low | Low | Legacy, text-only |

---

## Appendix A: Backward Compatibility

### A.1 Preserved Behaviors

| Feature | Status |
|---------|--------|
| Session encryption | Unchanged |
| Skills loading | Unchanged |
| Custom agents | Unchanged |
| Soul personality | Unchanged |
| Slash commands | Unchanged |
| Knowledge base | Unchanged |
| Engram memory | Unchanged |
| MCP servers | Unchanged |

### A.2 Changed Behaviors

| Feature | Before | After |
|---------|--------|-------|
| Session management | Per-channel | Centralized in gateway |
| Orchestrator lifecycle | Created per mode | Managed by gateway |
| Chat history | Only scratchpad | Full history log |
| Channel communication | Direct | Via WebSocket |

---

## Appendix B: Error Handling

### B.1 Gateway Errors

| Error Code | Description | Recovery |
|------------|-------------|----------|
| `GATEWAY_UNAVAILABLE` | Cannot connect to gateway | Start daemon or check config |
| `SESSION_NOT_FOUND` | Session ID doesn't exist | List sessions and use valid ID |
| `SESSION_PASSWORD_REQUIRED` | Encrypted session needs password | Provide password |
| `SESSION_PASSWORD_INVALID` | Wrong password | Retry with correct password |
| `ORCHESTRATOR_ERROR` | Agent execution failed | Check agent logs |
| `WEBSOCKET_TIMEOUT` | Connection timed out | Reconnect |

### B.2 Channel Errors

| Error Code | Description | Recovery |
|------------|-------------|----------|
| `CHANNEL_DISCONNECTED` | Lost connection to gateway | Auto-reconnect with backoff |
| `CHANNEL_UNAUTHORIZED` | Telegram user not allowed | Contact admin |
| `MESSAGE_TOO_LARGE` | Message exceeds limit | Split message |

---

## Appendix C: Security Considerations

### C.1 WebSocket Security

- Gateway binds to `127.0.0.1` by default (localhost only)
- No authentication required for local connections
- For remote access: implement token-based auth (future feature)

### C.2 Session Security

- Session encryption unchanged
- Passwords never transmitted over WebSocket (derived key only)
- Chat history encrypted if session is encrypted

### C.3 Telegram Security

- Existing user allowlist preserved
- Session always uses unsafe mode (Telegram limitation)
- Warning displayed about Telegram's lack of E2E encryption

---

## Appendix D: Channel Developer Reference

### D.1 Channel Development Checklist

When implementing a new channel connector:

- [ ] Create connector class extending `BaseChannelConnector`
- [ ] Implement `manifest()` class method with accurate capabilities
- [ ] Implement all abstract methods: `connect()`, `disconnect()`, `send_message()`, `handle_gateway_message()`, `render_response()`
- [ ] Override lifecycle hooks as needed: `on_connect()`, `on_disconnect()`, `on_session_created()`, `on_session_resumed()`, `on_error()`
- [ ] Define configuration schema in manifest
- [ ] Handle reconnection gracefully (use built-in `reconnect()` or override)
- [ ] Implement message truncation for channels with length limits
- [ ] Add comprehensive unit tests
- [ ] Add integration tests with mock gateway
- [ ] Document configuration options
- [ ] Register via entry point in `pyproject.toml`

### D.2 Capability Guidelines

| Capability | When to Use |
|------------|-------------|
| `STREAMING` | Channel can display partial responses as they arrive |
| `RICH_TEXT` | Channel renders Markdown or similar formatting |
| `IMAGES` | Channel can display inline images |
| `FILE_UPLOAD` | Users can upload files through the channel |
| `FILE_DOWNLOAD` | Users can download files through the channel |
| `INTERACTIVE` | Channel supports buttons, menus, or forms |
| `MULTI_USER` | Single channel instance serves multiple users |
| `PERSISTENT` | Channel maintains long-lived connections |
| `SECURE` | Channel provides end-to-end encryption |
| `VOICE` | Channel supports voice input/output |

### D.3 Common Patterns

**User-to-Channel Mapping (Multi-User Channels)**:
```python
class MultiUserConnector(BaseChannelConnector):
    def __init__(self, ...):
        super().__init__(...)
        self.user_channels: dict[str, str] = {}  # user_id → channel_id

    def get_channel_for_user(self, user_id: str) -> str:
        if user_id not in self.user_channels:
            self.user_channels[user_id] = f"{self.manifest().channel_type}-{user_id}-{uuid.uuid4()}"
        return self.user_channels[user_id]
```

**Response Buffering (Non-Streaming Channels)**:
```python
class BufferedConnector(BaseChannelConnector):
    async def handle_gateway_message(self, message: dict) -> None:
        if message["type"] == "chat_stream_start":
            self._buffer = ""
        elif message["type"] == "chat_stream_chunk":
            self._buffer += message["payload"].get("content", "")
        elif message["type"] == "chat_stream_end":
            await self.render_response({"content": self._buffer})
            self._buffer = ""
```

**Rate Limiting**:
```python
from asyncio import Semaphore

class RateLimitedConnector(BaseChannelConnector):
    def __init__(self, ...):
        super().__init__(...)
        self._rate_limiter = Semaphore(10)  # max 10 concurrent

    async def send_to_platform(self, message: str) -> None:
        async with self._rate_limiter:
            await self._platform_send(message)
            await asyncio.sleep(0.1)  # rate limit delay
```

### D.4 Error Handling Best Practices

1. **Never crash the gateway**: Catch all exceptions in channel code
2. **Log errors with context**: Include channel_id, user_id, message_id
3. **Use typed exceptions**: Define channel-specific exceptions
4. **Graceful degradation**: Fall back to simpler responses if rendering fails
5. **Notify users of issues**: Don't silently drop messages

```python
# aletheia/channels/exceptions.py

class ChannelError(Exception):
    """Base exception for channel errors."""
    pass

class ChannelConnectionError(ChannelError):
    """Failed to connect to gateway or platform."""
    pass

class ChannelConfigurationError(ChannelError):
    """Invalid channel configuration."""
    pass

class ChannelRateLimitError(ChannelError):
    """Platform rate limit exceeded."""
    pass

class ChannelMessageError(ChannelError):
    """Failed to send/receive message."""
    pass
```

---

*End of Specification Document*
