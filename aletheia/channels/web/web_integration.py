"""Web UI integration for the gateway daemon.

This module creates a FastAPI app that uses the gateway's session manager
instead of maintaining its own session state.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from agent_framework import ChatMessage, Role, TextContent, UsageContent, UsageDetails
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from aletheia.agents.entrypoint import Orchestrator
from aletheia.agents.instructions_loader import Loader
from aletheia.agents.model import AgentResponse, Timeline
from aletheia.cli import _build_plugins
from aletheia.commands import COMMANDS, expand_custom_command, get_custom_commands
from aletheia.config import load_config
from aletheia.daemon.session_manager import GatewaySessionManager
from aletheia.engram.tools import Engram
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session, SessionExistsError, SessionNotFoundError


async def run_command_step(
    command_name: str,
    args: list,
    queue: asyncio.Queue,
    session_id: str,
    session_manager: GatewaySessionManager,
):
    """Execute a built-in command and send output to queue."""
    import io
    import re

    from rich.console import Console
    from rich.markdown import Markdown

    try:
        command = COMMANDS.get(command_name)
        if not command:
            await queue.put(
                {"type": "error", "content": f"Unknown command: /{command_name}"}
            )
            await queue.put({"type": "done"})
            return

        # Create mock console to capture command output
        class MockConsole:
            def __init__(self):
                self.file = io.StringIO()
                self.console = Console(
                    file=self.file,
                    force_terminal=False,
                    width=80,
                    legacy_windows=False,
                    no_color=True,
                    markup=False,
                )

            def print(self, *args, **kwargs):
                for arg in args:
                    if isinstance(arg, Markdown):
                        self.file.write(arg.markup + "\n")
                    else:
                        self.console.print(arg, **kwargs)

            def get_output(self):
                output = self.file.getvalue()
                # Strip Rich markup tags
                output = re.sub(r"\[/?[a-z_]+[^\]]*\]", "", output)
                return output

        mock_console = MockConsole()

        # Prepare kwargs for command execution
        kwargs = {}
        config = load_config()
        kwargs["config"] = config

        # Some commands need completion_usage
        if command_name == "cost":
            orchestrator = session_manager.get_orchestrator()
            if orchestrator and hasattr(orchestrator, "completion_usage"):
                kwargs["completion_usage"] = orchestrator.completion_usage

        # Execute command
        command.execute(console=mock_console, *args, **kwargs)

        # Send output to queue
        output = mock_console.get_output()
        await queue.put({"type": "text", "content": output})
        await queue.put({"type": "done"})

    except Exception as e:
        await queue.put({"type": "error", "content": str(e)})
        await queue.put({"type": "done"})


def create_web_app(
    session_manager: GatewaySessionManager, engram: Engram | None
) -> FastAPI:
    """Create FastAPI app integrated with gateway's session manager.

    Args:
        session_manager: Gateway's session manager instance
        engram: Gateway's engram instance (if memory enabled)

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="Aletheia Web UI",
        description="Web interface for Aletheia - integrated with gateway daemon",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files
    static_dir = Path(__file__).parent.parent / "ui" / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Store gateway components in app state
    app.state.session_manager = session_manager
    app.state.engram = engram

    # Queue for SSE streaming (per-session)
    app.state.investigation_queues: dict[str, asyncio.Queue] = {}

    # Models
    class SessionCreateRequest(BaseModel):
        name: str | None = None
        password: str | None = None
        unsafe: bool = False
        verbose: bool = True

    class ChatRequest(BaseModel):
        message: str
        password: str | None = None

    # Routes
    @app.get("/")
    async def read_root():
        return FileResponse(static_dir / "index.html")

    @app.get("/sessions", response_model=list[dict[str, Any]])
    async def list_sessions():
        """List all available sessions."""
        return Session.list_sessions()

    @app.get("/commands", response_model=list[dict[str, str]])
    async def list_commands():
        """List all available commands (built-in and custom)."""
        config = load_config()
        commands_list = []

        # Built-in commands
        for name, cmd_obj in COMMANDS.items():
            commands_list.append(
                {"name": name, "description": cmd_obj.description, "type": "built-in"}
            )

        # Custom commands
        try:
            custom_cmds = get_custom_commands(config)
            for command_name, custom_cmd in custom_cmds.items():
                commands_list.append(
                    {
                        "name": command_name,
                        "description": f"{custom_cmd.name}: {custom_cmd.description}",
                        "type": "custom",
                    }
                )
        except Exception:
            pass

        commands_list.sort(key=lambda x: x["name"])
        return commands_list

    @app.post("/sessions", response_model=dict[str, Any])
    async def create_session(request: SessionCreateRequest):
        """Create a new session via gateway's session manager."""
        try:
            session = await session_manager.create_session(
                name=request.name,
                password=request.password,
                unsafe=request.unsafe,
                verbose=request.verbose,
            )
            return session.get_metadata().to_dict()
        except SessionExistsError:
            raise HTTPException(status_code=409, detail="Session already exists")
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/sessions/{session_id}", response_model=dict[str, Any])
    async def get_session_metadata(
        session_id: str, password: str | None = None, unsafe: bool = False
    ):
        """Get session metadata."""
        # Check if this is the active session
        active_session = session_manager.get_active_session()
        if active_session and active_session.session_id == session_id:
            metadata = active_session.get_metadata().to_dict()

            # Calculate cost
            config = load_config()
            input_tokens = metadata.get("total_input_tokens", 0)
            output_tokens = metadata.get("total_output_tokens", 0)
            metadata["total_cost"] = (input_tokens * config.cost_per_input_token) + (
                output_tokens * config.cost_per_output_token
            )
            return metadata

        # Not active session, load from disk
        sessions = Session.list_sessions()
        target_session = None
        for s in sessions:
            if s["id"] == session_id:
                target_session = s
                break

        if not target_session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Try to load full metadata
        try:
            is_unsafe = target_session.get("unsafe") is True
            use_unsafe = unsafe or is_unsafe
            session = Session.resume(
                session_id=session_id, password=password, unsafe=use_unsafe
            )
            data = session.get_metadata().to_dict()

            config = load_config()
            input_tokens = data.get("total_input_tokens", 0)
            output_tokens = data.get("total_output_tokens", 0)
            data["total_cost"] = (input_tokens * config.cost_per_input_token) + (
                output_tokens * config.cost_per_output_token
            )
            return data
        except Exception:
            if password:
                raise HTTPException(
                    status_code=400, detail="Invalid password or session data"
                )
            return target_session

    @app.post("/sessions/{session_id}/chat")
    async def chat_session(
        session_id: str,
        request: ChatRequest,
        background_tasks: BackgroundTasks,
        unsafe: bool = False,
    ):
        """Send a message to the active session via gateway."""
        # Create queue for streaming if not exists
        if session_id not in app.state.investigation_queues:
            app.state.investigation_queues[session_id] = asyncio.Queue()

        queue = app.state.investigation_queues[session_id]

        # Set up WebUIFunctionMiddleware BEFORE creating/resuming session
        from aletheia.agents.middleware import WebUIFunctionMiddleware

        # Ensure this session is active in gateway
        active_session = session_manager.get_active_session()
        if not active_session or active_session.session_id != session_id:
            # Need to resume this session first - check if session is unsafe from metadata
            sessions = Session.list_sessions()
            is_session_unsafe = False
            for s in sessions:
                if s["id"] == session_id:
                    is_session_unsafe = s.get("unsafe") is True
                    break

            # Use unsafe flag from session metadata OR from query param
            use_unsafe = unsafe or is_session_unsafe

            # Set middleware before resuming
            session_manager.additional_middleware = [
                WebUIFunctionMiddleware(event_queue=queue)
            ]
            try:
                await session_manager.resume_session(
                    session_id=session_id,
                    password=request.password,
                    unsafe=use_unsafe,
                )
            except Exception as e:
                raise HTTPException(
                    status_code=400, detail=f"Failed to resume session: {e}"
                )
        else:
            # Session is already active - update middleware queue reference
            orchestrator = session_manager.get_orchestrator()
            if orchestrator:
                # Update WebUIFunctionMiddleware queue in orchestrator
                updated = False
                if hasattr(orchestrator.agent, "middlewares"):
                    for middleware in orchestrator.agent.middlewares:
                        if isinstance(middleware, WebUIFunctionMiddleware):
                            middleware.event_queue = queue
                            updated = True
                            break

                # If no middleware found, add it now
                if not updated:
                    if not hasattr(orchestrator.agent, "middlewares"):
                        orchestrator.agent.middlewares = []
                    orchestrator.agent.middlewares.append(
                        WebUIFunctionMiddleware(event_queue=queue)
                    )

                # Also update in sub-agents
                for agent_instance in getattr(orchestrator, "sub_agent_instances", []):
                    if hasattr(agent_instance, "agent") and hasattr(
                        agent_instance.agent, "middlewares"
                    ):
                        for middleware in agent_instance.agent.middlewares:
                            if isinstance(middleware, WebUIFunctionMiddleware):
                                middleware.event_queue = queue
                                break

        # Check for slash commands
        if request.message.strip().startswith("/"):
            from aletheia.commands import expand_custom_command

            config = load_config()

            # Try to expand custom command first
            expanded_message, was_expanded = expand_custom_command(
                request.message, config
            )

            if was_expanded:
                # Custom command was expanded, use the expanded message for chat
                request.message = expanded_message
            else:
                # Not a custom command, check if it's a built-in command
                command_parts = request.message.strip()[1:].split()
                command_name = command_parts[0]
                args = command_parts[1:]

                # Run built-in command
                background_tasks.add_task(
                    run_command_step,
                    command_name,
                    args,
                    queue,
                    session_id,
                    session_manager,
                )
                return {"status": "processing_command"}

        # Stream message using session manager (receives JSON chunks)
        async def stream_response():
            import json as json_module

            last_sent_data = {}
            parsed_successfully = False

            try:
                # Stream from session manager (all channels now receive JSON)
                async for chunk in session_manager.send_message(request.message, "web"):
                    chunk_type = chunk.get("type")

                    if chunk_type == "json_chunk":
                        # Incremental JSON chunk (not yet parseable)
                        # For web UI, we wait for json_complete to send structured events
                        pass

                    elif chunk_type == "json_complete":
                        # Complete, parseable JSON response
                        parsed = chunk.get("parsed", {})
                        parsed_successfully = True

                        # Helper to serialize for comparison (handles nested objects)
                        def serialize_for_comparison(obj):
                            return (
                                json_module.dumps(obj, sort_keys=True) if obj else None
                            )

                        # Send incremental structured events ONLY for changed fields
                        if "confidence" in parsed:
                            new_val = serialize_for_comparison(parsed.get("confidence"))
                            old_val = serialize_for_comparison(
                                last_sent_data.get("confidence")
                            )
                            if new_val != old_val:
                                await queue.put(
                                    {
                                        "type": "confidence",
                                        "content": parsed["confidence"],
                                    }
                                )
                                last_sent_data["confidence"] = parsed["confidence"]

                        if "agent" in parsed:
                            new_val = serialize_for_comparison(parsed.get("agent"))
                            old_val = serialize_for_comparison(
                                last_sent_data.get("agent")
                            )
                            if new_val != old_val:
                                await queue.put(
                                    {"type": "agent", "content": parsed["agent"]}
                                )
                                last_sent_data["agent"] = parsed["agent"]

                        # Check if orchestrator response (simplified rendering)
                        agent_name = parsed.get("agent", "").lower()
                        is_orchestrator = agent_name in ("orchestrator", "aletheia")

                        if "findings" in parsed:
                            new_val = serialize_for_comparison(parsed.get("findings"))
                            old_val = serialize_for_comparison(
                                last_sent_data.get("findings")
                            )
                            if new_val != old_val:
                                # Clean up findings data - remove section headers from details
                                findings = (
                                    parsed["findings"].copy()
                                    if isinstance(parsed["findings"], dict)
                                    else parsed["findings"]
                                )
                                if isinstance(findings, dict) and "details" in findings:
                                    # Remove markdown section headers from details field
                                    details_text = findings["details"]
                                    if isinstance(details_text, str):
                                        # Remove lines starting with ## (markdown headers)
                                        lines = details_text.split("\n")
                                        cleaned_lines = [
                                            line
                                            for line in lines
                                            if not line.strip().startswith("##")
                                        ]
                                        findings["details"] = "\n".join(
                                            cleaned_lines
                                        ).strip()

                                await queue.put(
                                    {"type": "findings", "content": findings}
                                )
                                last_sent_data["findings"] = parsed["findings"]

                        # Skip decisions/next_actions for orchestrator direct responses
                        if not is_orchestrator:
                            if "decisions" in parsed:
                                new_val = serialize_for_comparison(
                                    parsed.get("decisions")
                                )
                                old_val = serialize_for_comparison(
                                    last_sent_data.get("decisions")
                                )
                                if new_val != old_val:
                                    await queue.put(
                                        {
                                            "type": "decisions",
                                            "content": parsed["decisions"],
                                        }
                                    )
                                    last_sent_data["decisions"] = parsed["decisions"]

                            if "next_actions" in parsed:
                                new_val = serialize_for_comparison(
                                    parsed.get("next_actions")
                                )
                                old_val = serialize_for_comparison(
                                    last_sent_data.get("next_actions")
                                )
                                if new_val != old_val:
                                    await queue.put(
                                        {
                                            "type": "next_actions",
                                            "content": parsed["next_actions"],
                                        }
                                    )
                                    last_sent_data["next_actions"] = parsed[
                                        "next_actions"
                                    ]

                        if "errors" in parsed and parsed.get("errors"):
                            new_val = serialize_for_comparison(parsed.get("errors"))
                            old_val = serialize_for_comparison(
                                last_sent_data.get("errors")
                            )
                            if new_val != old_val:
                                await queue.put(
                                    {"type": "errors", "content": parsed["errors"]}
                                )
                                last_sent_data["errors"] = parsed["errors"]

                    elif chunk_type == "json_error":
                        # JSON parsing failed, send as text fallback
                        await queue.put(
                            {
                                "type": "text_fallback",
                                "content": chunk.get("content", ""),
                            }
                        )

                    elif chunk_type == "usage":
                        # Usage information
                        await queue.put(
                            {
                                "type": "usage",
                                "content": chunk.get("usage", {}),
                            }
                        )

                # If parsing succeeded, send completion signal
                if parsed_successfully:
                    await queue.put({"type": "response_complete"})

                await queue.put({"type": "done"})
            except Exception as e:
                await queue.put({"type": "error", "content": str(e)})

        background_tasks.add_task(stream_response)
        return {"status": "processing"}

    @app.get("/sessions/{session_id}/stream")
    async def stream_session(session_id: str):
        """SSE endpoint for session updates."""
        if session_id not in app.state.investigation_queues:
            app.state.investigation_queues[session_id] = asyncio.Queue()

        queue = app.state.investigation_queues[session_id]

        async def event_generator():
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
                    continue

                if data["type"] == "done":
                    yield {"data": json.dumps(data)}
                    continue

                if data["type"] == "error":
                    yield {"event": "error", "data": data["content"]}
                    break

                yield {"data": json.dumps(data)}

        return EventSourceResponse(event_generator())

    @app.delete("/sessions/{session_id}")
    async def delete_session(session_id: str):
        """Delete a session."""
        try:
            # If it's the active session, close it first
            active_session = session_manager.get_active_session()
            if active_session and active_session.session_id == session_id:
                await session_manager.close_active_session()

            # Delete from disk
            session = Session(session_id=session_id)
            session.delete()

            # Clear queue
            if session_id in app.state.investigation_queues:
                del app.state.investigation_queues[session_id]

            return {"status": "success", "message": f"Session {session_id} deleted"}
        except SessionNotFoundError:
            raise HTTPException(status_code=404, detail="Session not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/sessions/{session_id}/scratchpad")
    async def get_session_scratchpad(
        session_id: str, password: str | None = None, unsafe: bool = False
    ):
        """Get session scratchpad content."""
        try:
            # Check if active session
            active_session = session_manager.get_active_session()
            if active_session and active_session.session_id == session_id:
                session = active_session
            else:
                # Load session
                sessions = Session.list_sessions()
                is_unsafe = False
                for s in sessions:
                    if s["id"] == session_id:
                        is_unsafe = s.get("unsafe") is True
                        break
                use_unsafe = unsafe or is_unsafe
                session = Session.resume(
                    session_id=session_id, password=password, unsafe=use_unsafe
                )

            scratchpad = Scratchpad(
                session_dir=session.session_path, encryption_key=session.get_key()
            )
            content = scratchpad.read_scratchpad()
            return {"content": content}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/sessions/{session_id}/timeline")
    async def get_session_timeline(
        session_id: str, password: str | None = None, unsafe: bool = False
    ):
        """Get session timeline."""
        try:
            # Check if active session
            active_session = session_manager.get_active_session()
            if active_session and active_session.session_id == session_id:
                session = active_session
            else:
                # Load session
                sessions = Session.list_sessions()
                is_unsafe = False
                for s in sessions:
                    if s["id"] == session_id:
                        is_unsafe = s.get("unsafe") is True
                        break
                use_unsafe = unsafe or is_unsafe
                session = Session.resume(
                    session_id=session_id, password=password, unsafe=use_unsafe
                )

            # Load scratchpad
            scratchpad_file = session.scratchpad_file
            if not scratchpad_file.exists():
                return {"timeline": []}

            scratchpad = Scratchpad(
                session_dir=session.session_path, encryption_key=session.get_key()
            )

            # Get scratchpad content
            journal_content = scratchpad.read_scratchpad()
            if not journal_content or not journal_content.strip():
                return {"timeline": []}

            # Use timeline agent to generate timeline
            from aletheia.agents.timeline.timeline_agent import TimelineAgent

            prompt_loader = Loader()

            timeline_agent = TimelineAgent(
                name="timeline_agent",
                instructions=prompt_loader.load("timeline", "json_instructions"),
                description="Timeline Agent for generating session timeline",
            )

            message = ChatMessage(
                role=Role.USER,
                contents=[
                    TextContent(
                        text=f"""
Generate a timeline of the following troubleshooting session scratchpad data:

{journal_content}
"""
                    )
                ],
            )

            response = await timeline_agent.agent.run(message, response_format=Timeline)

            if response and response.text:
                try:
                    timeline_data = json.loads(str(response.text))

                    # Handle both Timeline model format and legacy format
                    entries = (
                        timeline_data.get("entries", timeline_data)
                        if isinstance(timeline_data, dict)
                        else timeline_data
                    )

                    # Normalize entries to consistent format
                    normalized_entries = []
                    for event in entries:
                        normalized_entries.append(
                            {
                                "timestamp": event.get("timestamp", ""),
                                "type": event.get(
                                    "entry_type", event.get("type", "INFO")
                                ),
                                "content": event.get(
                                    "content", event.get("description", "")
                                ),
                            }
                        )

                    return {"timeline": normalized_entries}
                except json.JSONDecodeError:
                    # Fallback: return raw text
                    return {"timeline": [], "raw_text": str(response.text)}
            else:
                return {"timeline": []}

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    return app
