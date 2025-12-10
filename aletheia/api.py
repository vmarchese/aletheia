import asyncio
import base64
import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Depends
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from aletheia.session import Session, SessionNotFoundError, SessionExistsError, SessionMetadata, SessionError
from aletheia.config import load_config
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.agents.instructions_loader import Loader
from aletheia.agents.entrypoint import Orchestrator
from aletheia.cli import _build_plugins
from agent_framework import ChatMessage, TextContent, Role, UsageDetails, UsageContent

from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Aletheia API", description="REST API for Aletheia Troubleshooting Tool")

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
    name: Optional[str] = None
    password: Optional[str] = None
    unsafe: bool = False
    verbose: bool = True

class SessionResumeRequest(BaseModel):
    password: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    password: Optional[str] = None # Password might be needed if session not cached/loaded

# --- Global State (Simple in-memory cache for active agents) ---
# In a production app, this might need more robust state management
active_investigations: Dict[str, Orchestrator] = {}
investigation_queues: Dict[str, asyncio.Queue] = {}

# --- Dependencies ---

def get_session(session_id: str, password: Optional[str] = None, unsafe: bool = False) -> Session:
    try:
        if unsafe:
             return Session.resume(session_id=session_id, password=None, unsafe=True)
        return Session.resume(session_id=session_id, password=password, unsafe=False)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Endpoints ---

@app.get("/sessions", response_model=List[Dict[str, Any]])
async def list_sessions():
    """List all available sessions."""
    return Session.list_sessions()

@app.post("/sessions", response_model=Dict[str, Any])
async def create_session(request: SessionCreateRequest):
    """Create a new troubleshooting session."""
    try:
        session = Session.create(
            name=request.name,
            password=request.password,
            unsafe=request.unsafe,
            verbose=request.verbose
        )
        return session.get_metadata().to_dict()
    except SessionExistsError:
        raise HTTPException(status_code=409, detail="Session already exists")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/sessions/{session_id}", response_model=Dict[str, Any])
async def get_session_metadata(session_id: str, unsafe: bool = False):
    # Check if session exists and get its unsafe status from list_sessions
    sessions = Session.list_sessions()
    target_session = None
    for s in sessions:
        if s['id'] == session_id:
            target_session = s
            break
    
    if not target_session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    is_unsafe = target_session.get("unsafe") == "True"
    
    # If user passed unsafe=True, we respect it.
    # If user passed False (default) but session IS unsafe, we must use unsafe=True to resume it.
    use_unsafe = unsafe or is_unsafe
    
    try:
        session = Session.resume(session_id=session_id, password=None, unsafe=use_unsafe)
        data = session.get_metadata().to_dict()
        
        # Attach runtime info if available
        
        if session_id in active_investigations:
            orchestrator = active_investigations[session_id]
            if hasattr(orchestrator, 'completion_usage'):
                 usage = orchestrator.completion_usage
                 # Sync to be sure (though run_agent_step should have saved it)
                 if usage.input_token_count > 0:
                     session.update_usage(usage.input_token_count, usage.output_token_count)

        # Load fresh metadata (or use what we have)
        data = session.get_metadata().to_dict()
        
        # Calculate cost
        config = load_config()
        input_tokens = data.get("total_input_tokens", 0)
        output_tokens = data.get("total_output_tokens", 0)
        
        data["total_cost"] = (input_tokens * config.cost_per_input_token) + (output_tokens * config.cost_per_output_token)
        
        return data
    except Exception:
        # If we can't load metadata (e.g. password needed for encrypted session), 
        # fall back to list info which has limited data.
        return target_session

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    try:
        # We don't need password to delete the folder? 
        # Session.delete() just removes the folder.
        # But we should probably verify it exists.
        session = Session(session_id=session_id) # Don't need resume/password to delete path
        session.delete()
        return {"status": "success", "message": f"Session {session_id} deleted"}
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}/export")
async def export_session(session_id: str, password: Optional[str] = None, unsafe: bool = False):
    """Export session as zip/tar."""
    try:
        session = get_session(session_id, password, unsafe)
        export_path = session.export()
        return FileResponse(export_path, filename=export_path.name, media_type='application/gzip')
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/sessions/{session_id}/timeline")
async def get_session_timeline(session_id: str, password: Optional[str] = None, unsafe: bool = False):
    """Get session timeline."""
    try:
        session = get_session(session_id, password, unsafe)
        scratchpad = Scratchpad(session_dir=session.session_path, encryption_key=session.get_key())
        journal_content = scratchpad.read_scratchpad()
        
        # We could use the LLM here to parse it like in CLI, but for API maybe raw or simple parsing is better/faster?
        # The user asked to implement commands as REST APIs. The CLI command uses LLM.
        # We should probably replicate that logic or reuse it.
        # Reusing it requires async execution.
        
        from aletheia.agents.timeline.timeline_agent import TimelineAgent
        prompt_loader = Loader()
        timeline_agent = TimelineAgent(name="timeline_agent",
                                       instructions=prompt_loader.load("timeline", "json_instructions"),
                                       description="Timeline Agent")
        
        message = ChatMessage(role=Role.USER, contents=[TextContent(text=f"""
                                       Generate a timeline of the following troubleshooting session scratchpad data:\n\n{journal_content}\n\n
                                       """)])
        response = await timeline_agent.agent.run(message)
        
        # Parse JSON from response
        try:
            timeline_data = json.loads(str(response.text))
        except json.JSONDecodeError:
            # Fallback if LLM returns text/markdown
             timeline_data = [{"timestamp": "", "type": "INFO", "description": str(response.text)}]

        return {"timeline": timeline_data}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Investigation / Chat ---

async def get_or_create_orchestrator(session_id: str, password: Optional[str], unsafe: bool) -> Orchestrator:
    if session_id in active_investigations:
        return active_investigations[session_id]
    
    session = get_session(session_id, password, unsafe)
    config = load_config()
    prompt_loader = Loader()
    scratchpad = Scratchpad(session_dir=session.session_path, encryption_key=session.get_key())
    session.scratchpad = scratchpad
    
    tools, agent_instances = _build_plugins(config=config, prompt_loader=prompt_loader, session=session, scratchpad=scratchpad)
    
    orchestrator = Orchestrator(
        name="orchestrator",
        description="Orchestrator agent",
        instructions=prompt_loader.load("orchestrator", "instructions"),
        session=session,
        sub_agents=tools,
        scratchpad=scratchpad,
        config=config
    )
    # Store agent instances to cleanup later? 
    # For now we attach them to orchestrator or keep global ref if needed.
    # The CLI keeps them to call cleanup().
    orchestrator.sub_agent_instances = agent_instances 
    
    if not hasattr(orchestrator, 'completion_usage'):
        meta = session.get_metadata()
        orchestrator.completion_usage = UsageDetails(
            input_token_count=meta.total_input_tokens,
            output_token_count=meta.total_output_tokens
        )

    active_investigations[session_id] = orchestrator
    return orchestrator

async def run_agent_step(orchestrator: Orchestrator, message: str, queue: asyncio.Queue):
    try:
        thread = orchestrator.agent.get_new_thread() # Or maintain thread state?
        # In CLI it maintains thread. We should probably cache thread too or use same thread.
        # For simplicity, let's assume single thread per session for now or store it on orchestrator.
        if not hasattr(orchestrator, 'current_thread'):
            orchestrator.current_thread = orchestrator.agent.get_new_thread()
        
        async for response in orchestrator.agent.run_stream(
            messages=[ChatMessage(role="user", contents=[TextContent(text=message)])],
            thread=orchestrator.current_thread,
        ):
            if response and str(response.text) != "":
                await queue.put({"type": "text", "content": str(response.text)})
            
            if response and response.contents:
                for content in response.contents:
                    if isinstance(content, UsageContent):
                        orchestrator.completion_usage += content.details
                        # Persist usage to session metadata
                        orchestrator.session.update_usage(
                            input_tokens=orchestrator.completion_usage.input_token_count,
                            output_tokens=orchestrator.completion_usage.output_token_count
                        )
            
        await queue.put({"type": "done"})
    except Exception as e:
        await queue.put({"type": "error", "content": str(e)})


# --- Helpers for Commands ---

from aletheia.commands import COMMANDS
from rich.console import Console
from rich.markdown import Markdown
import io

class MockConsole:
    def __init__(self):
        self.file = io.StringIO()
        self.console = Console(file=self.file, force_terminal=False, width=80)
        
    def print(self, *args, **kwargs):
        for arg in args:
            if isinstance(arg, Markdown):
               self.file.write(arg.markup + "\n")
            else:
               self.console.print(arg, **kwargs)

    def get_output(self):
        return self.file.getvalue()

async def run_command_step(command_name: str, args: list, queue: asyncio.Queue, session_id: str):
    try:
        command = COMMANDS.get(command_name)
        if not command:
            await queue.put({"type": "error", "content": f"Unknown command: /{command_name}"})
            return

        mock_console = MockConsole()
        
        # Prepare kwargs - some commands might need config or other contexts
        # replicating what CLI typically passes
        kwargs = {}
        if command_name == "cost":
             config = load_config()
             kwargs["config"] = config
             # retrieving completion usage might be tricky without active context
             # For now we'll pass empty or dummy if strictly required, 
             # but CostInfo expects it. 
             # Let's try to get it from the orchestrator if it exists
             # Let's try to get it from the orchestrator if it exists
             if session_id in active_investigations:
                 orchestrator = active_investigations[session_id]
                 if hasattr(orchestrator, 'completion_usage'):
                    kwargs["completion_usage"] = orchestrator.completion_usage

        command.execute(console=mock_console, *args, **kwargs)
        
        output = mock_console.get_output()
        await queue.put({"type": "text", "content": output})
        await queue.put({"type": "done"})
        
    except Exception as e:
        await queue.put({"type": "error", "content": str(e)})


@app.post("/sessions/{session_id}/chat")
async def chat_session(session_id: str, request: ChatRequest, background_tasks: BackgroundTasks, unsafe: bool = False):
    """Send a message to the investigation session."""
    try:
        # Check for Slash Command
        if request.message.strip().startswith("/"):
            command_parts = request.message.strip()[1:].split()
            command_name = command_parts[0]
            args = command_parts[1:]
            
            if session_id not in investigation_queues:
                investigation_queues[session_id] = asyncio.Queue()
            queue = investigation_queues[session_id]
            
            background_tasks.add_task(run_command_step, command_name, args, queue, session_id)
            return {"status": "processing_command"}

        orchestrator = await get_or_create_orchestrator(session_id, request.password, unsafe)
        
        # We need a way to stream results back. 
        # We'll use a queue for this session.
        if session_id not in investigation_queues:
            investigation_queues[session_id] = asyncio.Queue()
            
        queue = investigation_queues[session_id]
        
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
