"""TUI (Terminal User Interface) channel connector for Aletheia."""

import asyncio
import os
import random
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from aletheia.channels.base import BaseChannelConnector
from aletheia.channels.formatter import format_response_to_markdown
from aletheia.channels.manifest import ChannelCapability, ChannelManifest
from aletheia.daemon.protocol import ProtocolMessage

# Thinking messages from CLI
THINKING_MESSAGES = [
    "🕺 Galavanting...",
    "🧠 Confabulating...",
    "🫣 Unhiding...",
    "🧶 Byte-braiding...",
    "😌 Panic-taming...",
    "🚶‍♂️ Perambulating...",
    "🔮 Divining...",
    "🕵️‍♀️ Unconcealing...",
    "📏 Metric-massaging...",
    "🦘 Log-leaping...",
    "📡 Packet-probing...",
    "⛏️ Metric-mining...",
    "🤠 Log-lassoing...",
    "🧭 Trace-traversing...",
    "⚓ Data-dredging...",
    "🚀 Warming up the stream...",
    "🤔 Thinking deep thoughts...",
    "✨ Summoning Markdown magic...",
    "🧠 Crunching ideas...",
    "📡 Connecting to the source...",
    "🧵 Weaving words together...",
    "🔮 Consulting the language spirits...",
    "⚙️ Calibrating cleverness...",
    "📖 Turning pages of possibility...",
    "💫 Spinning semantic silk...",
    "🪄 Casting formatting spells...",
    "🔍 Inspecting thought packets...",
    "🧩 Reassembling syntax fragments...",
    "🌩️ Charging the neural flux...",
    "🎭 Rehearsing replies...",
    "💡 Illuminating markdown mysteries...",
    "📈 Optimizing verbosity coefficients...",
    "🛰️ Aligning thought satellites...",
]


class TUICommandCompleter(Completer):
    """Command completer for TUI slash commands."""

    def _get_all_commands(self) -> dict[str, str]:
        """Get all available commands with descriptions (always fresh from disk)."""
        all_commands: dict[str, str] = {}

        # TUI-specific commands
        all_commands["new_session"] = "Create a new session"
        all_commands["session"] = "Session management (list/show/timeline/resume)"
        all_commands["reload"] = "Reload skills and custom commands"
        all_commands["exit"] = "Disconnect and exit"

        # Built-in commands from aletheia.commands
        try:
            from aletheia.commands import COMMANDS, get_custom_commands
            from aletheia.config import load_config

            for name, cmd_obj in COMMANDS.items():
                all_commands[name] = cmd_obj.description

            # Add custom commands (always fresh from disk)
            try:
                config = load_config()
                custom_cmds = get_custom_commands(config)
                for command_name, custom_cmd in custom_cmds.items():
                    all_commands[command_name] = (
                        f"{custom_cmd.name}: {custom_cmd.description}"
                    )
            except Exception:
                pass  # Ignore if custom commands can't be loaded

        except Exception:
            pass  # Ignore if built-in commands can't be loaded

        return all_commands

    def get_completions(self, document: Document, complete_event):
        """Generate completion suggestions."""
        text = document.text_before_cursor

        # Only provide completions if text starts with /
        if not text.startswith("/"):
            return

        # Extract the command part (everything after the /)
        command_part = text[1:].lower()

        # Get all available commands
        all_commands = self._get_all_commands()

        # Filter and yield matching commands
        for cmd_name, description in sorted(all_commands.items()):
            if cmd_name.lower().startswith(command_part):
                yield Completion(
                    text=cmd_name,
                    start_position=-len(command_part),
                    display=cmd_name,
                    display_meta=description,
                )


class TUIChannelConnector(BaseChannelConnector):
    """Terminal User Interface channel connector."""

    def __init__(
        self,
        gateway_url: str = "ws://127.0.0.1:8765",
        config: dict[str, Any] | None = None,
    ):
        """Initialize TUI connector."""
        super().__init__(gateway_url, config)
        self.console = Console()

        # Initialize prompt session with command completion
        completer = TUICommandCompleter()
        self.prompt_session: PromptSession = PromptSession(
            completer=completer,
            complete_while_typing=True,
        )

        self._live: Live | None = None
        self._current_response = ""
        self._current_thinking = ""
        self._last_usage: dict[str, Any] | None = None
        self._stop_event = asyncio.Event()
        self._processing = False  # Track if agent is processing
        self._thinking_task: asyncio.Task | None = None  # Thinking animation task
        self._active_session_id: str | None = None  # Track active session

    @classmethod
    def manifest(cls) -> ChannelManifest:
        """Return TUI channel manifest."""
        return ChannelManifest(
            channel_type="tui",
            display_name="Terminal UI",
            description="Interactive terminal interface using Rich and prompt_toolkit",
            version="1.0.0",
            capabilities={
                ChannelCapability.STREAMING,
                ChannelCapability.RICH_TEXT,
                ChannelCapability.PERSISTENT,
            },
            requires_daemon=True,
            supports_threading=False,
        )

    async def on_connected(self, payload: dict[str, Any]) -> None:
        """Display welcome message on connection."""
        # Show Aletheia banner
        banner_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "banner.txt"
        )
        try:
            with open(banner_path, encoding="utf-8") as f:
                self.console.print(f.read())
        except OSError:
            pass

        # Check if there's already an active session
        session_info = payload.get("session")
        if session_info:
            self._active_session_id = session_info.get("id")
            self.console.print(
                f"\n[bold green]✓[/bold green] Active session: "
                f"[cyan]{self._active_session_id}[/cyan]"
            )
            if session_info.get("name"):
                self.console.print(f"  Name: {session_info['name']}")
            self.console.print()

        self.console.print(
            Panel(
                "[bold green]Connected to Aletheia Gateway[/bold green]\n\n"
                "Session Commands:\n"
                "  /new_session [name] [--unsafe] [--verbose] - Create new session\n"
                "  /session resume <id> [--unsafe] - Resume existing session\n"
                "  /session list - List all sessions\n"
                "  /session show - Show current session metadata\n"
                "  /session timeline - Show session timeline\n\n"
                "Built-in Commands:\n"
                "  /help - Show available commands\n"
                "  /info - Show session information\n"
                "  /agents - Show loaded agents\n"
                "  /version - Show Aletheia version\n\n"
                "  /exit - Disconnect and exit",
                title="Aletheia TUI",
                border_style="green",
            )
        )

    async def handle_gateway_message(self, message: ProtocolMessage) -> None:
        """Handle incoming message from gateway."""
        try:
            if message.type == "session_created":
                await self._handle_session_created(message.payload)
            elif message.type == "session_resumed":
                await self._handle_session_resumed(message.payload)
            elif message.type == "session_list":
                await self._handle_session_list(message.payload)
            elif message.type == "chat_stream_start":
                await self._handle_stream_start(message.payload)
            elif message.type == "chat_stream_chunk":
                await self._handle_stream_chunk(message.payload)
            elif message.type == "chat_stream_end":
                await self._handle_stream_end(message.payload)
            elif message.type == "session_metadata":
                await self._handle_session_metadata(message.payload)
            elif message.type == "timeline_data":
                await self._handle_timeline_data(message.payload)
            elif message.type == "commands_updated":
                # Tab completion always loads fresh from disk, no action needed
                self.logger.debug("Commands updated on disk")
            elif message.type == "error":
                await self._handle_error(message.payload)
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            self.console.print(f"[bold red]Error:[/bold red] {e}")

    async def _handle_session_created(self, payload: dict[str, Any]) -> None:
        """Handle session creation confirmation."""
        session = payload.get("session", {})
        self._active_session_id = session.get("id", "unknown")
        self.console.print(
            f"\n[bold green]✓[/bold green] Session created: "
            f"[cyan]{self._active_session_id}[/cyan]"
        )
        if session.get("name"):
            self.console.print(f"  Name: {session['name']}")
        self.console.print()
        self._processing = False

    async def _handle_session_resumed(self, payload: dict[str, Any]) -> None:
        """Handle session resume confirmation."""
        session = payload.get("session", {})
        self._active_session_id = session.get("id", "unknown")
        self.console.print(
            f"\n[bold green]✓[/bold green] Session resumed: "
            f"[cyan]{self._active_session_id}[/cyan]"
        )
        if session.get("name"):
            self.console.print(f"  Name: {session['name']}")
        self.console.print()
        self._processing = False

    async def _handle_session_list(self, payload: dict[str, Any]) -> None:
        """Handle session list response."""
        sessions = payload.get("sessions", [])
        if not sessions:
            self.console.print("\n[yellow]No sessions found[/yellow]\n")
            self._processing = False
            return

        self.console.print("\n[bold]Available Sessions:[/bold]")
        for session in sessions:
            # Session list doesn't include status, just show basic info
            self.console.print(
                f"  [green]•[/green] "
                f"[cyan]{session['id']}[/cyan] "
                f"({session.get('name', 'unnamed')}) "
                f"- Created: {session.get('created', 'unknown')}"
            )
        self.console.print()
        self._processing = False

    async def _handle_session_metadata(self, payload: dict[str, Any]) -> None:
        """Handle session metadata response."""
        metadata = payload.get("metadata", {})
        if not metadata:
            self.console.print("\n[yellow]No metadata available[/yellow]\n")
            self._processing = False
            return

        self.console.print("\n[bold]Session Info:[/bold]")
        self.console.print(f"  [cyan]ID:[/cyan]       {metadata.get('id', 'unknown')}")
        if metadata.get("name"):
            self.console.print(f"  [cyan]Name:[/cyan]     {metadata['name']}")
        self.console.print(
            f"  [cyan]Status:[/cyan]   {metadata.get('status', 'unknown')}"
        )
        self.console.print(
            f"  [cyan]Created:[/cyan]  {metadata.get('created', 'unknown')}"
        )
        self.console.print(
            f"  [cyan]Updated:[/cyan]  {metadata.get('updated', 'unknown')}"
        )

        input_tokens = metadata.get("total_input_tokens", 0)
        output_tokens = metadata.get("total_output_tokens", 0)
        total_cost = metadata.get("total_cost", 0)

        if input_tokens or output_tokens:
            self.console.print(
                f"  [cyan]Tokens:[/cyan]   {input_tokens} in / {output_tokens} out"
            )
        if total_cost:
            self.console.print(f"  [cyan]Cost:[/cyan]     ${total_cost:.4f}")

        self.console.print()
        self._processing = False

    async def _handle_timeline_data(self, payload: dict[str, Any]) -> None:
        """Handle timeline data response."""
        timeline = payload.get("timeline", [])
        if not timeline:
            self.console.print("\n[yellow]No timeline entries found[/yellow]\n")
            self._processing = False
            return

        type_styles = {
            "ACTION": ("bold green", "ACTION"),
            "OBSERVATION": ("bold blue", "OBSERVATION"),
            "DECISION": ("bold red", "DECISION"),
            "INFO": ("bold cyan", "INFO"),
        }

        self.console.print("\n[bold]Session Timeline:[/bold]")
        self.console.print("[dim]" + "-" * 80 + "[/dim]")

        for entry in timeline:
            entry_type = entry.get("type", "INFO").upper()
            timestamp = entry.get("timestamp", "")
            content = entry.get("content", "")
            style, label = type_styles.get(entry_type, ("bold white", entry_type))

            self.console.print(
                f"  [{style}][{label}][/{style}] " f"[dim]{timestamp}[/dim]"
            )
            self.console.print(f"    {content}")
            self.console.print()

        self.console.print("[dim]" + "-" * 80 + "[/dim]\n")
        self._processing = False

    async def _show_thinking_animation(self) -> None:
        """Show thinking animation until first content arrives."""
        while self._processing and not self._current_response:
            msg = random.choice(THINKING_MESSAGES)
            if self._live:
                self._live.update(f"[grey82 i]{msg}[/grey82 i]")
            await asyncio.sleep(1)

    async def _handle_stream_start(self, payload: dict[str, Any]) -> None:
        """Handle stream start."""
        # Reset current response and start processing
        self._current_response = ""
        self._current_thinking = ""
        self._processing = True

        # Print header with session ID
        if self._active_session_id:
            self.console.print(
                f"\n[[bold yellow]{self._active_session_id}[/bold yellow]] [bold cyan]🤖 Aletheia[/bold cyan]"
            )
            self.console.print("[cyan]" + "─" * 80 + "[/cyan]")

        # Start live display for thinking animation
        if self._live is None:
            self._live = Live(
                "", console=self.console, auto_refresh=True, refresh_per_second=4
            )
            self._live.start()

        # Start thinking animation
        self._thinking_task = asyncio.create_task(self._show_thinking_animation())

    async def _handle_stream_chunk(self, payload: dict[str, Any]) -> None:
        """Handle streaming response chunk."""
        chunk_type = payload.get("chunk_type", "text")

        # Handle JSON chunks - parse and format to markdown
        if chunk_type == "json_complete":
            # Complete JSON received - parse and format
            parsed = payload.get("parsed")
            if parsed:
                # Stop thinking animation on first real content
                if self._thinking_task and not self._thinking_task.done():
                    self._thinking_task.cancel()
                    try:
                        await self._thinking_task
                    except asyncio.CancelledError:
                        pass

                # Format JSON to markdown
                formatted_markdown = format_response_to_markdown(parsed)

                # Ensure live display is running
                if self._live is None:
                    self._live = Live(
                        "",
                        console=self.console,
                        auto_refresh=True,
                        refresh_per_second=5,
                    )
                    self._live.start()

                # Store usage for display at stream end
                usage = payload.get("usage")
                if usage:
                    self._last_usage = usage

                # Update display with formatted markdown
                self._current_response = formatted_markdown
                self._live.update(Markdown(self._current_response))

        elif chunk_type == "json_error":
            # JSON parsing failed - show raw content
            content = payload.get("content", "")
            if content:
                # Stop thinking animation
                if self._thinking_task and not self._thinking_task.done():
                    self._thinking_task.cancel()
                    try:
                        await self._thinking_task
                    except asyncio.CancelledError:
                        pass

                if self._live is None:
                    self._live = Live(
                        "",
                        console=self.console,
                        auto_refresh=True,
                        refresh_per_second=5,
                    )
                    self._live.start()

                self._current_response = content
                self._live.update(self._current_response)

        elif chunk_type == "text":
            # Plain text content (e.g. from command_execute responses)
            content = payload.get("content", "")
            if content:
                # Stop thinking animation on first real content
                if self._thinking_task and not self._thinking_task.done():
                    self._thinking_task.cancel()
                    try:
                        await self._thinking_task
                    except asyncio.CancelledError:
                        pass

                if self._live is None:
                    self._live = Live(
                        "",
                        console=self.console,
                        auto_refresh=True,
                        refresh_per_second=5,
                    )
                    self._live.start()

                self._current_response += content
                self._live.update(Markdown(self._current_response))

        elif chunk_type == "function_call":
            # Show function call events from the gateway middleware
            content = payload.get("content", {})
            agent_name = content.get("agent_name", "orchestrator")
            func_name = content.get("function_name", "unknown")
            arguments = content.get("arguments", {})

            # Format arguments as a compact string
            args_parts = [f"{k}={v}" for k, v in arguments.items()]
            args_str = ", ".join(args_parts) if args_parts else ""

            # Print as a persistent line above the live animated line
            func_display = f"[dim]⚙ {agent_name}::{func_name}({args_str})[/dim]"
            if self._live:
                # console.print inside a Live context prints above the
                # animated line, keeping the thinking animation in place
                self._live.console.print(func_display)
            else:
                self.console.print(func_display)

        # json_chunk doesn't need handling for TUI - we wait for json_complete

    async def _handle_stream_end(self, payload: dict[str, Any]) -> None:
        """Handle stream end."""
        # Cancel thinking animation if still running
        if self._thinking_task and not self._thinking_task.done():
            self._thinking_task.cancel()
            try:
                await self._thinking_task
            except asyncio.CancelledError:
                pass

        # Stop live display (it already showed the content)
        if self._live:
            self._live.stop()
            self._live = None

        # Show compact context usage if available
        if self._last_usage:
            usage = self._last_usage
            util = usage.get("context_utilization", 0)
            input_tk = usage.get("input_tokens", 0)
            output_tk = usage.get("output_tokens", 0)
            usage_line = (
                f"[dim]tokens: {input_tk:,} in / {output_tk:,} out"
                f" | context: {util:.0f}%[/dim]"
            )
            if util > 80:
                usage_line = (
                    f"[bold yellow]tokens: {input_tk:,} in / {output_tk:,} out"
                    f" | context: {util:.0f}% ⚠[/bold yellow]"
                )
            self.console.print(usage_line)
            self._last_usage = None

        # Print final newline for spacing
        self.console.print()

        # Reset state
        self._current_response = ""
        self._current_thinking = ""
        self._processing = False
        self._thinking_task = None

    async def _handle_error(self, payload: dict[str, Any]) -> None:
        """Handle error message."""
        # Cancel thinking animation if running
        if self._thinking_task and not self._thinking_task.done():
            self._thinking_task.cancel()
            try:
                await self._thinking_task
            except asyncio.CancelledError:
                pass

        # Stop live display if active
        if self._live:
            self._live.stop()
            self._live = None

        error_msg = payload.get("message", payload.get("error", "Unknown error"))
        self.console.print(f"\n[bold red]Error:[/bold red] {error_msg}\n")

        # Reset processing state
        self._processing = False
        self._current_response = ""
        self._current_thinking = ""
        self._thinking_task = None

    async def render_response(self, response: dict[str, Any]) -> None:
        """Render response (used for non-streaming responses)."""
        content = response.get("content", "")
        self.console.print(Markdown(content))
        self.console.print()

    async def run_interactive(self) -> None:
        """Run interactive TUI loop."""
        try:
            # Connect to gateway
            await self.connect()

            # Main input loop
            while self.connected and not self._stop_event.is_set():
                try:
                    # Wait while processing
                    while self._processing:
                        await asyncio.sleep(0.1)
                        if not self.connected or self._stop_event.is_set():
                            break

                    if not self.connected or self._stop_event.is_set():
                        break

                    # Build prompt with session ID if available
                    # Use prompt_toolkit's HTML formatting (not Rich markup)
                    if self._active_session_id:
                        prompt_text = HTML(
                            f"[<b><ansiyellow>{self._active_session_id}</ansiyellow></b>] "
                            "<b>You:</b> "
                        )
                    else:
                        prompt_text = HTML("<b>You:</b> ")

                    # Get user input using prompt_toolkit (without patch_stdout for better Rich rendering)
                    # Explicitly set is_password=False to reset after any password prompts
                    user_input = await self.prompt_session.prompt_async(
                        prompt_text, is_password=False
                    )

                    if not user_input.strip():
                        continue

                    # Handle commands
                    if user_input.startswith("/"):
                        await self._handle_command(user_input)
                    else:
                        # Set processing BEFORE sending message to prevent prompt from appearing
                        self._processing = True
                        # Send regular chat message
                        await self.send_message(user_input)

                except (EOFError, KeyboardInterrupt):
                    break
                except Exception as e:
                    self.logger.error(f"Input loop error: {e}")
                    self.console.print(f"[bold red]Error:[/bold red] {e}")
                    # Reset processing on error
                    self._processing = False

        finally:
            await self.disconnect()

    async def _handle_command(self, command: str) -> None:
        """Handle TUI commands."""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()

        # TUI-specific commands
        if cmd == "/exit":
            self._stop_event.set()
            self.console.print("[yellow]Disconnecting...[/yellow]")

        elif cmd == "/new_session":
            # Parse arguments: /new_session [name] [--unsafe] [--verbose]
            args = parts[1].split() if len(parts) > 1 else []
            name = None
            unsafe = False
            verbose = False

            # Parse name and flags
            for arg in args:
                if arg == "--unsafe":
                    unsafe = True
                elif arg == "--verbose":
                    verbose = True
                elif not name:
                    name = arg

            password = None

            # Prompt for password if not in unsafe mode
            if not unsafe:
                while True:
                    password = await self.prompt_session.prompt_async(
                        "Password (press Enter to skip): ",
                        is_password=True,
                    )
                    if not password.strip():
                        password = None
                        break

                    confirm = await self.prompt_session.prompt_async(
                        "Confirm password: ",
                        is_password=True,
                    )
                    if password == confirm:
                        break
                    self.console.print(
                        "[bold red]Passwords do not match. "
                        "Please try again.[/bold red]"
                    )

            self._processing = True
            await self.create_session(
                name=name, password=password, unsafe=unsafe, verbose=verbose
            )

        elif cmd == "/list_sessions":
            # Legacy alias — redirect to /session list
            self._processing = True
            await self.list_sessions()

        elif cmd == "/session":
            args = parts[1].split() if len(parts) > 1 else []
            if not args:
                self.console.print(
                    "[bold red]Usage:[/bold red]\n"
                    "  /session resume <id> [--unsafe] - Resume existing session\n"
                    "  /session list     - List all sessions\n"
                    "  /session show     - Show current session metadata\n"
                    "  /session timeline - Show session timeline"
                )
                return

            action = args[0].lower()

            if action == "resume":
                # Parse: /session resume <id> [--unsafe]
                remaining = args[1:]
                session_id = None
                unsafe = False

                for arg in remaining:
                    if arg == "--unsafe":
                        unsafe = True
                    elif not session_id:
                        session_id = arg

                if not session_id:
                    self.console.print(
                        "[bold red]Usage:[/bold red] "
                        "/session resume <session_id> [--unsafe]"
                    )
                    return

                password = None

                if not unsafe:
                    password = await self.prompt_session.prompt_async(
                        "Password: ",
                        is_password=True,
                    )
                    if not password.strip():
                        password = None

                self._processing = True
                await self.resume_session(
                    session_id=session_id, password=password, unsafe=unsafe
                )

            elif action == "list":
                self._processing = True
                await self.list_sessions()

            elif action == "show":
                if not self._active_session_id:
                    self.console.print(
                        "[bold red]No active session.[/bold red] "
                        "Use /new_session or /session resume first."
                    )
                    return
                self.console.print("[yellow]Fetching session metadata...[/yellow]")
                self._processing = True
                await self.request_session_metadata(
                    session_id=self._active_session_id, unsafe=True
                )

            elif action == "timeline":
                if not self._active_session_id:
                    self.console.print(
                        "[bold red]No active session.[/bold red] "
                        "Use /new_session or /session resume first."
                    )
                    return
                self.console.print(
                    "[yellow]Generating timeline (this may take a moment)...[/yellow]"
                )
                self._processing = True
                await self.request_timeline(
                    session_id=self._active_session_id, unsafe=True
                )

            else:
                self.console.print(
                    "[bold red]Unknown subcommand:[/bold red] "
                    f"{action}\n"
                    "  /session resume <id> [--unsafe] - Resume existing session\n"
                    "  /session list     - List all sessions\n"
                    "  /session show     - Show current session metadata\n"
                    "  /session timeline - Show session timeline"
                )

        else:
            # Try built-in commands (help, version, info, agents, cost)
            from aletheia.commands import COMMANDS, expand_custom_command
            from aletheia.config import load_config

            cmd_name = cmd[1:]  # Remove leading /

            # Try to expand custom command first
            config = load_config()
            expanded_message, was_expanded = expand_custom_command(command, config)

            if was_expanded:
                # Custom command was expanded, send as chat message
                self._processing = True
                await self.send_message(expanded_message)
            elif cmd_name in COMMANDS:
                # Execute built-in command
                # Note: These commands expect console and other parameters
                # For now, we'll show a simple message
                if cmd_name == "help":
                    COMMANDS[cmd_name].execute(self.console)
                elif cmd_name in ["version", "info"]:
                    COMMANDS[cmd_name].execute(self.console)
                elif cmd_name == "agents":
                    COMMANDS[cmd_name].execute(self.console)
                elif cmd_name in ("cost", "reload", "context"):
                    if not self._active_session_id:
                        self.console.print(
                            "[bold red]No active session.[/bold red] "
                            "Use /new_session or /session resume first."
                        )
                    elif self.websocket:
                        # Delegate to gateway which has access to session/orchestrator
                        self._processing = True
                        msg = ProtocolMessage.create(
                            "command_execute",
                            {"message": f"/{cmd_name}", "channel": "tui"},
                        )
                        await self.websocket.send(msg.to_json())
                else:
                    COMMANDS[cmd_name].execute(self.console)
            else:
                self.console.print(
                    f"[bold red]Unknown command:[/bold red] {cmd}\n"
                    "Available commands:\n"
                    "  /new_session [name] [--unsafe] [--verbose]\n"
                    "  /session resume <id> [--unsafe]\n"
                    "  /session list | show | timeline\n"
                    "  /help - Show built-in commands\n"
                    "  /exit"
                )


async def main() -> None:
    """Main entry point for TUI connector."""
    import sys

    # Setup logging
    from aletheia.utils.logging import setup_logging

    setup_logging()

    # Parse gateway URL from args
    gateway_url = "ws://127.0.0.1:8765"
    if len(sys.argv) > 1:
        gateway_url = sys.argv[1]

    # Create and run TUI
    tui = TUIChannelConnector(gateway_url=gateway_url)
    await tui.run_interactive()


if __name__ == "__main__":
    asyncio.run(main())
