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

#### 4.1.3 CLI Commands

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

#### 4.3.3 Gateway → Client Messages

| Type | Payload | Description |
|------|---------|-------------|
| `channel_registered` | `{channel_id: string, session?: SessionInfo}` | Confirm registration |
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
   ```

2. **Streaming Display**:
   - Use `rich.Live` for real-time updates
   - Buffer JSON chunks until parseable
   - Display structured sections incrementally

3. **Input Handling**:
   - Keep `prompt_toolkit` for command completion
   - Handle local commands (exit, quit) locally
   - Forward chat messages and slash commands to gateway

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
```

**Modified Endpoints**:

| Endpoint | Current | After Refactor |
|----------|---------|----------------|
| `POST /sessions` | Creates session directly | Forwards to gateway |
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
| `aletheia/daemon/session_manager.py` | Gateway session management |
| `aletheia/daemon/protocol.py` | WebSocket message protocol |
| `aletheia/daemon/history.py` | Chat history logger |
| `aletheia/daemon/plugins.py` | Plugin builder (moved from cli.py) |
| `aletheia/daemon/pid.py` | PID file management for daemon mode |

### 6.2 Channels Module

| File | Purpose |
|------|---------|
| `aletheia/channels/__init__.py` | Module exports |
| `aletheia/channels/base.py` | Abstract base connector |
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
│   ├── session_manager.py  # GatewaySessionManager class
│   ├── protocol.py         # Protocol messages and data classes
│   ├── history.py          # ChatHistoryLogger class
│   ├── plugins.py          # build_plugins() function
│   └── pid.py              # PID file management
├── channels/
│   ├── __init__.py
│   ├── base.py             # BaseChannelConnector ABC
│   ├── tui.py              # TUIChannelConnector
│   ├── web.py              # WebChannelConnector
│   └── telegram.py         # TelegramChannelConnector
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
| `daemon/session_manager.py` | `tests/daemon/test_session_manager.py` | Session CRUD, orchestrator management |
| `daemon/protocol.py` | `tests/daemon/test_protocol.py` | Message serialization |
| `daemon/history.py` | `tests/daemon/test_history.py` | History logging and retrieval |
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

*End of Specification Document*
