import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from agent_framework import AgentSession, Content, Message, UsageDetails, add_usage_details
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
from aletheia.config import get_config_dir, load_config
from aletheia.engram.tools import Engram
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import (
    Session,
    SessionExistsError,
    SessionNotFoundError,
)

_engram_instance: Engram | None = None
MEMORY_ENABLED: bool = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engram_instance
    if MEMORY_ENABLED:
        _engram_instance = Engram(identity=str(get_config_dir()))
        _engram_instance.start_watcher()
    yield
    if _engram_instance is not None:
        _engram_instance.stop_watcher()
        _engram_instance = None


app = FastAPI(
    title="Aletheia API",
    description="REST API for Aletheia Troubleshooting Tool",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).parent / "ui" / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def read_root():
    return FileResponse(static_dir / "index.html")


# --- Models ---


class SessionCreateRequest(BaseModel):
    name: str | None = None
    password: str | None = None
    unsafe: bool = False
    verbose: bool = True


class SessionResumeRequest(BaseModel):
    password: str | None = None


class ChatRequest(BaseModel):
    message: str
    password: str | None = None  # Password might be needed if session not cached/loaded


# --- Global State (Simple in-memory cache for active agents) ---
# In a production app, this might need more robust state management
active_investigations: dict[str, Orchestrator] = {}
investigation_queues: dict[str, asyncio.Queue] = {}

# --- Dependencies ---


def get_session(
    session_id: str, password: str | None = None, unsafe: bool = False
) -> Session:
    try:
        if unsafe:
            return Session.resume(session_id=session_id, password=None, unsafe=True)
        return Session.resume(session_id=session_id, password=password, unsafe=False)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def get_session_auto(
    session_id: str, password: str | None = None, unsafe: bool = False
) -> Session:
    """
    Helper to get session with auto-detection of unsafe status.
    Prioritizes explicit 'unsafe' param, then checks list_sessions metadata.
    """
    if unsafe:
        return Session.resume(session_id=session_id, password=None, unsafe=True)

    # Check metadata
    sessions = Session.list_sessions()
    is_unsafe = False
    for s in sessions:
        if s["id"] == session_id:
            is_unsafe = s.get("unsafe") is True
            break

    # Resume with detected unsafe status if password not provided or if it's strictly unsafe
    # If is_unsafe is True, we MUST enable unsafe mode.
    use_unsafe = unsafe or is_unsafe
    return Session.resume(session_id=session_id, password=password, unsafe=use_unsafe)


# --- Endpoints ---


@app.get("/sessions", response_model=list[dict[str, Any]])
async def list_sessions():
    """List all available sessions."""
    return Session.list_sessions()


@app.get("/commands", response_model=list[dict[str, str]])
async def list_commands():
    """
    List all available commands (built-in and custom).

    Returns:
        List of command objects with name and description
    """
    config = load_config()
    commands_list = []

    # Add built-in commands
    for name, cmd_obj in COMMANDS.items():
        commands_list.append(
            {"name": name, "description": cmd_obj.description, "type": "built-in"}
        )

    # Add custom commands
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
        # If custom commands fail to load, just return built-in ones
        pass

    # Sort alphabetically by name
    commands_list.sort(key=lambda x: x["name"])

    return commands_list


@app.post("/sessions", response_model=dict[str, Any])
async def create_session(request: SessionCreateRequest):
    """Create a new troubleshooting session."""
    try:
        session = Session.create(
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
    # Check if session exists and get its unsafe status from list_sessions
    sessions = Session.list_sessions()
    target_session = None
    for s in sessions:
        if s["id"] == session_id:
            target_session = s
            break

    if not target_session:
        raise HTTPException(status_code=404, detail="Session not found")

    is_unsafe = target_session.get("unsafe") is True

    # If user passed unsafe=True, we respect it.
    # If user passed False (default) but session IS unsafe, we must use unsafe=True to resume it.
    use_unsafe = unsafe or is_unsafe

    try:
        session = Session.resume(
            session_id=session_id, password=password, unsafe=use_unsafe
        )
        data = session.get_metadata().to_dict()

        # Attach runtime info if available

        if session_id in active_investigations:
            orchestrator = active_investigations[session_id]
            if hasattr(orchestrator, "completion_usage"):
                usage = orchestrator.completion_usage
                # Sync to be sure (though run_agent_step should have saved it)
                if usage.get("input_token_count", 0) > 0:
                    session.update_usage(
                        usage.get("input_token_count", 0), usage.get("output_token_count", 0)
                    )

        # Load fresh metadata (or use what we have)
        data = session.get_metadata().to_dict()

        # Calculate cost
        config = load_config()
        input_tokens = data.get("total_input_tokens", 0)
        output_tokens = data.get("total_output_tokens", 0)

        data["total_cost"] = (input_tokens * config.cost_per_input_token) + (
            output_tokens * config.cost_per_output_token
        )

        return data
    except Exception:
        # If we can't load metadata (e.g. password needed for encrypted session),
        # fall back to list info which has limited data.
        if password:
            # If password was provided but validation failed, raise error
            raise HTTPException(
                status_code=400, detail="Invalid password or session data"
            )
        return target_session


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    try:
        # Clear from active investigations cache
        if session_id in active_investigations:
            del active_investigations[session_id]
        if session_id in investigation_queues:
            del investigation_queues[session_id]

        # We don't need password to delete the folder?
        # Session.delete() just removes the folder.
        # But we should probably verify it exists.
        session = Session(
            session_id=session_id
        )  # Don't need resume/password to delete path
        session.delete()
        return {"status": "success", "message": f"Session {session_id} deleted"}
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sessions/{session_id}/reset")
async def reset_session_cache(session_id: str):
    """Reset the cached orchestrator for a session (for testing)."""
    try:
        if session_id in active_investigations:
            del active_investigations[session_id]
            print(f"[DEBUG API] Cleared cached orchestrator for session {session_id}")
        return {"status": "success", "message": f"Session {session_id} cache cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}/export")
async def export_session(
    session_id: str, password: str | None = None, unsafe: bool = False
):
    """Export session as zip/tar."""
    try:
        session = get_session_auto(session_id, password, unsafe)
        export_path = session.export()
        return FileResponse(
            export_path, filename=export_path.name, media_type="application/gzip"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/sessions/{session_id}/timeline")
async def get_session_timeline(
    session_id: str, password: str | None = None, unsafe: bool = False
):
    """Get session timeline."""
    try:
        session = get_session_auto(session_id, password, unsafe)
        scratchpad = Scratchpad(
            session_dir=session.session_path, encryption_key=session.get_key()
        )
        journal_content = scratchpad.read_scratchpad()

        # We could use the LLM here to parse it like in CLI, but for API maybe raw or simple parsing is better/faster?
        # The user asked to implement commands as REST APIs. The CLI command uses LLM.
        # We should probably replicate that logic or reuse it.
        # Reusing it requires async execution.

        from aletheia.agents.timeline.timeline_agent import TimelineAgent

        prompt_loader = Loader()
        timeline_agent = TimelineAgent(
            name="timeline_agent",
            instructions=prompt_loader.load("timeline", "json_instructions"),
            description="Timeline Agent",
        )

        message = Message(
            role="user",
            contents=[Content.from_text(f"""
                                       Generate a timeline of the following troubleshooting session scratchpad data:\n\n{journal_content}\n\n
                                       """)],
        )
        response = await timeline_agent.agent.run(
            message, options={"response_format": Timeline}
        )

        # Parse JSON from response
        try:
            timeline_data = json.loads(str(response.text))
            # If response is Timeline model format with 'entries' key, return that
            # Otherwise assume it's a list of entries and wrap it
            if isinstance(timeline_data, dict) and "entries" in timeline_data:
                return {"timeline": timeline_data}
            else:
                return {"timeline": {"entries": timeline_data}}
        except json.JSONDecodeError:
            # Fallback if LLM returns text/markdown
            return {
                "timeline": {
                    "entries": [
                        {
                            "timestamp": "",
                            "entry_type": "INFO",
                            "content": str(response.text),
                        }
                    ]
                }
            }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/sessions/{session_id}/scratchpad")
async def get_session_scratchpad(
    session_id: str, password: str | None = None, unsafe: bool = False
):
    """Get session scratchpad content."""
    try:
        session = get_session_auto(session_id, password, unsafe)
        # We need the key to decrypt if strictly necessary, but Scratchpad handles it.
        # Actually Scratchpad needs the key.
        scratchpad = Scratchpad(
            session_dir=session.session_path, encryption_key=session.get_key()
        )
        content = scratchpad.read_scratchpad()
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Investigation / Chat ---


async def get_or_create_orchestrator(
    session_id: str,
    password: str | None,
    unsafe: bool,
    event_queue: asyncio.Queue | None = None,
) -> Orchestrator:
    if session_id in active_investigations:
        print(f"[DEBUG API] Returning cached orchestrator for session {session_id}")
        return active_investigations[session_id]

    print(f"[DEBUG API] Creating new orchestrator for session {session_id}")
    session = get_session_auto(session_id, password, unsafe)
    config = load_config()
    prompt_loader = Loader()
    scratchpad = Scratchpad(
        session_dir=session.session_path, encryption_key=session.get_key()
    )
    session.scratchpad = scratchpad

    # Create WebUI middleware if queue provided
    webui_middlewares = []
    if event_queue is not None:
        from aletheia.agents.middleware import WebUIFunctionMiddleware

        print(
            f"[DEBUG API] Creating WebUIFunctionMiddleware with event_queue: {event_queue}"
        )
        webui_middlewares.append(WebUIFunctionMiddleware(event_queue=event_queue))
        print(f"[DEBUG API] WebUI middleware list: {webui_middlewares}")

    # Build plugins with middleware so all sub-agents get it too
    tools, agent_instances = _build_plugins(
        config=config,
        prompt_loader=prompt_loader,
        session=session,
        scratchpad=scratchpad,
        additional_middleware=webui_middlewares if webui_middlewares else None,
        engram=_engram_instance,
    )

    orchestrator = Orchestrator(
        name="orchestrator",
        description="Orchestrator agent",
        instructions=prompt_loader.load("orchestrator", "instructions"),
        session=session,
        sub_agents=tools,
        scratchpad=scratchpad,
        config=config,
        additional_middleware=webui_middlewares if webui_middlewares else None,
        engram=_engram_instance,
    )
    print(
        f"[DEBUG API] Orchestrator created with additional_middleware: {webui_middlewares if webui_middlewares else None}"
    )
    # Store agent instances to cleanup later?
    # For now we attach them to orchestrator or keep global ref if needed.
    # The CLI keeps them to call cleanup().
    orchestrator.sub_agent_instances = agent_instances

    if not hasattr(orchestrator, "completion_usage"):
        meta = session.get_metadata()
        orchestrator.completion_usage: UsageDetails = {
            "input_token_count": meta.total_input_tokens,
            "output_token_count": meta.total_output_tokens,
        }

    active_investigations[session_id] = orchestrator
    return orchestrator


async def run_agent_step(
    orchestrator: Orchestrator, message: str, queue: asyncio.Queue
):
    try:
        # Maintain a single AgentSession per orchestrator for conversation state
        if not hasattr(orchestrator, "agent_session"):
            orchestrator.agent_session = AgentSession()

        # Buffer for accumulating JSON text
        json_buffer = ""
        last_sent_data = {}
        parsed_successfully = False  # Track if JSON parsing ever succeeded

        async for response in orchestrator.agent.run(
            messages=[Message(role="user", contents=[Content.from_text(message)])],
            stream=True,
            session=orchestrator.agent_session,
            options={"response_format": AgentResponse},
        ):
            if response and str(response.text) != "":
                json_buffer += str(response.text)

                # Try to parse complete or partial JSON object and send incremental structured events
                try:
                    # Attempt to parse the accumulated buffer as JSON
                    parsed = json.loads(json_buffer)
                    parsed_successfully = True  # Mark successful parse

                    # Send incremental structured events only for fields that changed
                    if "confidence" in parsed and parsed.get(
                        "confidence"
                    ) != last_sent_data.get("confidence"):
                        await queue.put(
                            {"type": "confidence", "content": parsed["confidence"]}
                        )
                        last_sent_data["confidence"] = parsed["confidence"]

                    if "agent" in parsed and parsed.get("agent") != last_sent_data.get(
                        "agent"
                    ):
                        await queue.put({"type": "agent", "content": parsed["agent"]})
                        last_sent_data["agent"] = parsed["agent"]

                    # Check if this is a direct orchestrator response (case-insensitive)
                    agent_name = parsed.get("agent", "").lower()
                    is_orchestrator = agent_name in ("orchestrator", "aletheia")

                    if "findings" in parsed and parsed.get(
                        "findings"
                    ) != last_sent_data.get("findings"):
                        # Ensure tool_outputs is properly serialized as a list of dicts
                        findings_data = parsed["findings"]
                        if (
                            isinstance(findings_data, dict)
                            and "tool_outputs" in findings_data
                        ):
                            # Already a dict from JSON parsing, should be fine
                            pass
                        await queue.put({"type": "findings", "content": findings_data})
                        last_sent_data["findings"] = findings_data

                    # Skip decisions and next_actions for orchestrator direct responses
                    if not is_orchestrator:
                        if "decisions" in parsed and parsed.get(
                            "decisions"
                        ) != last_sent_data.get("decisions"):
                            await queue.put(
                                {"type": "decisions", "content": parsed["decisions"]}
                            )
                            last_sent_data["decisions"] = parsed["decisions"]

                        if "next_actions" in parsed and parsed.get(
                            "next_actions"
                        ) != last_sent_data.get("next_actions"):
                            await queue.put(
                                {
                                    "type": "next_actions",
                                    "content": parsed["next_actions"],
                                }
                            )
                            last_sent_data["next_actions"] = parsed["next_actions"]

                    if (
                        "errors" in parsed
                        and parsed.get("errors")
                        and parsed.get("errors") != last_sent_data.get("errors")
                    ):
                        await queue.put({"type": "errors", "content": parsed["errors"]})
                        last_sent_data["errors"] = parsed["errors"]

                except json.JSONDecodeError:
                    # Not yet a complete JSON object, continue accumulating silently
                    # Don't send text events to avoid showing raw JSON chunks
                    pass

            if response and response.contents:
                for content in response.contents:
                    if isinstance(content, Content) and content.type == "usage":
                        orchestrator.completion_usage = add_usage_details(
                            orchestrator.completion_usage, content.usage_details
                        )
                        # Persist usage to session metadata
                        orchestrator.session.update_usage(
                            input_tokens=orchestrator.completion_usage.get("input_token_count", 0),
                            output_tokens=orchestrator.completion_usage.get("output_token_count", 0),
                        )

        # Fallback: If JSON parsing never succeeded, send raw buffer as text_fallback
        if not parsed_successfully and json_buffer and json_buffer.strip():
            # Try to extract text content from partial JSON
            fallback_text = json_buffer
            if json_buffer.strip().startswith("{"):
                try:
                    import re

                    # Extract text from string fields
                    text_matches = re.findall(
                        r'"(?:summary|details|approach|rationale)":\s*"([^"]*)"',
                        json_buffer,
                    )
                    if text_matches:
                        fallback_text = "\n\n".join(text_matches)
                except Exception:
                    pass  # Use raw buffer if extraction fails

            await queue.put({"type": "text_fallback", "content": fallback_text})

        # Send final usage stats
        await queue.put(
            {
                "type": "usage",
                "content": {
                    "input_tokens": orchestrator.completion_usage.get("input_token_count", 0),
                    "output_tokens": orchestrator.completion_usage.get("output_token_count", 0),
                    "total_tokens": orchestrator.completion_usage.get("input_token_count", 0) + orchestrator.completion_usage.get("output_token_count", 0),
                },
            }
        )
        await queue.put({"type": "done"})
    except Exception as e:
        await queue.put({"type": "error", "content": str(e)})


# --- Helpers for Commands ---

import io

from rich.console import Console
from rich.markdown import Markdown


class MockConsole:
    def __init__(self):
        self.file = io.StringIO()
        # Use legacy_windows=False and no_color=True to get clean text output
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
        """Get the console output with Rich markup stripped."""
        output = self.file.getvalue()
        # Strip Rich markup tags like [bold], [cyan], etc.
        import re

        # Remove Rich markup: [tag], [/tag], [tag attribute]
        output = re.sub(r"\[/?[a-z_]+[^\]]*\]", "", output)
        return output


async def run_command_step(
    command_name: str, args: list, queue: asyncio.Queue, session_id: str
):
    try:
        command = COMMANDS.get(command_name)
        if not command:
            await queue.put(
                {"type": "error", "content": f"Unknown command: /{command_name}"}
            )
            return

        mock_console = MockConsole()

        # Prepare kwargs - some commands might need config or other contexts
        # replicating what CLI typically passes
        kwargs = {}

        # Load config for commands that need it (help, cost)
        config = load_config()
        kwargs["config"] = config

        if command_name == "cost":
            # retrieving completion usage might be tricky without active context
            # For now we'll pass empty or dummy if strictly required,
            # but CostInfo expects it.
            # Let's try to get it from the orchestrator if it exists
            if session_id in active_investigations:
                orchestrator = active_investigations[session_id]
                if hasattr(orchestrator, "completion_usage"):
                    kwargs["completion_usage"] = orchestrator.completion_usage

        command.execute(console=mock_console, *args, **kwargs)

        output = mock_console.get_output()
        await queue.put({"type": "text", "content": output})
        await queue.put({"type": "done"})

    except Exception as e:
        await queue.put({"type": "error", "content": str(e)})


@app.post("/sessions/{session_id}/chat")
async def chat_session(
    session_id: str,
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    unsafe: bool = False,
):
    """Send a message to the investigation session."""
    try:
        # Load config for custom command expansion
        config = load_config()

        # Check for Slash Command
        if request.message.strip().startswith("/"):
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

                if session_id not in investigation_queues:
                    investigation_queues[session_id] = asyncio.Queue()
                queue = investigation_queues[session_id]

                background_tasks.add_task(
                    run_command_step, command_name, args, queue, session_id
                )
                return {"status": "processing_command"}

        # We need a way to stream results back.
        # We'll use a queue for this session.
        if session_id not in investigation_queues:
            investigation_queues[session_id] = asyncio.Queue()

        queue = investigation_queues[session_id]

        orchestrator = await get_or_create_orchestrator(
            session_id, request.password, unsafe, event_queue=queue
        )

        # Run the agent in background and push updates to queue
        background_tasks.add_task(run_agent_step, orchestrator, request.message, queue)

        return {"status": "processing"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/sessions/{session_id}/stream")
async def stream_session(session_id: str):
    """SSE endpoint for session updates."""
    if session_id not in investigation_queues:
        # If no queue, maybe create one or wait?
        # Or maybe the user hasn't sent a message yet.
        investigation_queues[session_id] = asyncio.Queue()

    queue = investigation_queues[session_id]

    async def event_generator():
        while True:
            try:
                # Wait for data with timeout for heartbeat
                data = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                # Send heartbeat comment to keep connection alive
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
