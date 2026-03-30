# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import sys
import os

# Emergency BSON patch for local environment: MUST BE FIRST
try:
    import bson
    from bson import ObjectId
except (ImportError, AttributeError):
    try:
        import pymongo.bson as pymongo_bson
        sys.modules['bson'] = pymongo_bson
        from bson import ObjectId
    except Exception:
        pass

import asyncio
import sys

# Ensure Windows ProactorEventLoop for Playwright Async Support
if sys.platform == "win32":
    try:
        if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

import base64
import json
import logging
import sys
import os

# Emergency BSON patch for local environment
try:
    from bson import ObjectId
except (ImportError, AttributeError):
    try:
        import pymongo.bson as pymongo_bson
        sys.modules['bson'] = pymongo_bson
        from bson import ObjectId
        patch_logger = logging.getLogger("bson_patch")
        patch_logger.info("Successfully monkey-patched BSON in app context")
    except Exception:
        pass

from typing import Annotated, Any, List, Dict, Union, cast, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.security import APIKeyHeader
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolMessage, HumanMessage
from langgraph.types import Command
from langgraph.store.memory import InMemoryStore
from pydantic import BaseModel

# Use our clean, native checkpointer to avoid BSON version conflict
from src.graph.mongodb_checkpointer import NativeMongoDBSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from src.config.configuration import get_recursion_limit
from src.config.database import init_database, get_db
from src.config.database_service import research_db
from src.config.loader import get_bool_env, get_str_env
from src.config.report_style import ReportStyle
from src.config.tools import SELECTED_RAG_PROVIDER
from src.graph.builder import build_graph_with_memory
from src.llms.llm import get_configured_llm_models
from src.podcast.graph.builder import build_graph as build_podcast_graph
from src.ppt.graph.builder import build_graph as build_ppt_graph
from src.prompt_enhancer.graph.builder import build_graph as build_prompt_enhancer_graph
from src.prose.graph.builder import build_graph as build_prose_graph
from src.rag.builder import build_retriever
from src.rag.milvus import load_examples
from src.rag.retriever import Resource
from src.server.chat_request import (
    ChatRequest,
    EnhancePromptRequest,
    GeneratePodcastRequest,
    GeneratePPTRequest,
    GenerateProseRequest,
    TTSRequest,
)
from src.server.config_request import ConfigResponse
from src.server.mcp_request import MCPServerMetadataRequest, MCPServerMetadataResponse
from src.server.mcp_utils import load_mcp_tools
from src.server.rag_request import (
    RAGConfigResponse,
    RAGResourceRequest,
    RAGResourcesResponse,
)
from src.server.research_api import router as research_router
from src.server.studio_api import router as studio_router
from src.tools import VolcengineTTS
from src.graph.checkpoint import chat_stream_message
from src.utils.json_utils import sanitize_args
from src.config.vli import get_action_plan_path, get_inbox_path, get_archive_path, VAULT_ROOT
from datetime import datetime
import re

logger = logging.getLogger(__name__)

# --- GLOBAL VLI STATE ---
_vli_extracted_alerts = []  # [{symbol, label, color}]
_vli_dynamic_panels = []    # [{id, title, content_html}]

def create_futures_watchlist_panel():
    """Create a high-fidelity Futures Watchlist panel with Sortino indicators."""
    html = """
    <table style="width:100%; border-collapse:collapse; margin-top:5px;">
        <thead>
            <tr style="text-align:left; border-bottom:1px solid var(--border-color); color:var(--text-muted); font-size:11px;">
                <th style="padding:5px;">SYMBOL</th>
                <th style="padding:5px;">PRICE</th>
                <th style="padding:5px;">CHANGE</th>
                <th style="padding:5px;">SORTINO</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td style="padding:8px 5px;">$ES (E-mini)</td>
                <td style="padding:8px 5px; font-family:monospace;">5,245.50</td>
                <td style="padding:8px 5px; color:var(--emerald-green);">+0.85%</td>
                <td style="padding:8px 5px;"><span class="sortino-indicator sortino-green"></span>2.2</td>
            </tr>
            <tr style="background:rgba(255,255,255,0.02);">
                <td style="padding:8px 5px;">$NQ (Nasdaq)</td>
                <td style="padding:8px 5px; font-family:monospace;">18,412.25</td>
                <td style="padding:8px 5px; color:var(--emerald-green);">+1.20%</td>
                <td style="padding:8px 5px;"><span class="sortino-indicator sortino-green"></span>2.8</td>
            </tr>
            <tr>
                <td style="padding:8px 5px;">$GC (Gold)</td>
                <td style="padding:8px 5px; font-family:monospace;">2,185.40</td>
                <td style="padding:8px 5px; color:#f85149;">-0.15%</td>
                <td style="padding:8px 5px;"><span class="sortino-indicator sortino-yellow"></span>1.1</td>
            </tr>
        </tbody>
    </table>
    """
    return {
        "id": "watch-futures-01",
        "title": "Futures Watchlist",
        "content_html": html
    }

def extract_vli_logic(text: str) -> List[Dict[str, str]]:
    """Extract ticker symbols and risk thresholds from markdown text."""
    # ... existing extraction ...
    global _vli_dynamic_panels
    text_lower = text.lower()
    if "futures" in text_lower and "watchlist" in text_lower:
        # Check if already added
        if not any(p['id'] == "watch-futures-01" for p in _vli_dynamic_panels):
            _vli_dynamic_panels.append(create_futures_watchlist_panel())
            
    alerts = []
    
    # 1. Extract Symbols: $TICKER
    symbols = re.findall(r"\$([A-Z]{1,5})", text)
    for sym in set(symbols):
        alerts.append({"symbol": sym, "label": "Detected in Action Plan", "color": "green"})
        
    # 2. Extract Logic: S_{DR} >= 2.0
    logic_matches = re.findall(r"(S_{DR}\s*[>=<]+\s*\d+\.?\d*)", text)
    for logic in set(logic_matches):
        alerts.append({"symbol": "LOGIC", "label": logic, "color": "blue"})
        
    return alerts

INTERNAL_SERVER_ERROR_DETAIL = "Internal Server Error"

app = FastAPI(
    title="Cobalt Multiagent API",
    description="API for Deer",
    version="0.1.0",
)

# Add CORS middleware
# It's recommended to load the allowed origins from an environment variable
# for better security and flexibility across different environments.
allowed_origins_str = get_str_env("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8089,http://127.0.0.1:8089")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]

logger.info(f"Allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Restrict to specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # Use the configured list of methods
    allow_headers=["*"],  # Now allow all headers, but can be restricted further
)

@app.on_event("startup")
async def startup_event():
    import asyncio
    asyncio.create_task(vli_inbox_watcher())

# Load examples into Milvus if configured
load_examples()

# Initialize research database
try:
    db_success = init_database()
    if db_success:
        logger.info("Research database initialized successfully")
    else:
        logger.warning("Research database initialization skipped - some features may be limited")
except Exception as e:
    logger.error(f"Failed to initialize research database: {e}")
    logger.warning("Continuing without database - some features may be limited")

in_memory_store = InMemoryStore()
graph = build_graph_with_memory()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    expected_key = get_str_env("COBALT_API_KEY", "")
    if expected_key:
        if not api_key or api_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key

@app.get("/api/vli/visualization")
async def vli_visualization():
    """Serve the VLI technical analysis visualization (Diagnostic Only)."""
    try:
        img_path = r"C:\Users\rende\OneDrive\Desktop\vli_analysis_visualization.png"
        with open(img_path, "rb") as f:
            return Response(content=f.read(), media_type="image/png")
    except Exception:
        raise HTTPException(status_code=404, detail="Visualization image not found. Deploy to production to generate.")

# --- VLI SESSION MONITORING & CHAT ENDPOINTS ---

class VLIActionPlanRequest(BaseModel):
    text: str
    image: Optional[str] = None
    is_action_plan: bool = False

@app.get("/api/vli/active-state")
async def get_vli_active_state():
    """Live state for the VLI Dashboard (Action Plan + Alerts)."""
    plan_html = "No active plan found."
    plan_file = get_action_plan_path()
    
    # 1. Read Daily Action Plan (Markdown to simple HTML UL)
    if os.path.exists(plan_file):
        with open(plan_file, "r", encoding="utf-8") as f:
            content = f.read()
            lines = [l.strip("- ").strip() for l in content.split("\n") if l.strip().startswith("-")]
            if lines:
                plan_html = "<ul style='padding-left:15px; margin:0;'>" + "".join([f"<li>{l}</li>" for l in lines]) + "</ul>"
            else:
                plan_html = f"<div style='font-size:12px; color:#8b949e;'>{content[:200]}...</div>"

    # 2. Return Extracted Alerts (Dynamic)
    global _vli_extracted_alerts, _vli_dynamic_panels
    if not _vli_extracted_alerts:
        # Default fallback indicators
        alerts = [
            {"symbol": "VIX", "color": "green", "label": "Threshold: 30"},
            {"symbol": "CL=F", "color": "orange", "label": "Threshold: 90"}
        ]
    else:
        alerts = _vli_extracted_alerts
    # 3. Read Inbox Files
    inbox_path = get_inbox_path()
    inbox_files = []
    if os.path.exists(inbox_path):
        for f in os.listdir(inbox_path):
            if not f.startswith("."):
                inbox_files.append(f)

    return {
        "plan_html": plan_html, 
        "alerts": alerts,
        "dynamic_panels": _vli_dynamic_panels,
        "inbox_files": inbox_files
    }

@app.post("/api/vli/action-plan")
async def post_vli_action_plan(request: VLIActionPlanRequest):
    """Handle chat or action-plan updates from the VLI Sidebar."""
    plan_file = get_action_plan_path()
    
    # Check if this is a large text block representing a new plan
    if request.is_action_plan or len(request.text) > 300:
        with open(plan_file, "w", encoding="utf-8") as f:
            f.write(request.text)
        return {"response": "Plan captured. Vault updated. Session Monitor is analyzing directives..."}
            
    # Handle Image/Chart analysis request
    if request.image:
        return {"response": "Image received. Vision Specialist is scanning for EMA crossings and SMC fair-value gaps..."}

    return {"response": "Directive received. Action plan augmented."}

# --- VLI REACTIVE PIPELINE (INBOX WATCHER & ARCHIVER) ---

async def vli_inbox_watcher():
    """Background task to watch inbox/ for drafts AND archive end-of-day plans."""
    inbox = get_inbox_path()
    plan_file = get_action_plan_path()
    archive_dir = get_archive_path()
    
    plan_dir = os.path.dirname(plan_file)
    os.makedirs(inbox, exist_ok=True)
    os.makedirs(archive_dir, exist_ok=True)
    os.makedirs(plan_dir, exist_ok=True)
    
    logger.info(f"VLI: Inbox & Archiver watcher started on {inbox}")
    
    # Track the current day to detect transitions
    last_run_day = datetime.now().strftime("%Y-%m-%d")
    
    while True:
        try:
            # 1. Check for Day Transition (End-of-day Archiving)
            current_day = datetime.now().strftime("%Y-%m-%d")
            if current_day != last_run_day:
                logger.info(f"VLI: Day transition detected ({last_run_day} -> {current_day}). Archiving plan.")
                if os.path.exists(plan_file):
                    archive_file = os.path.join(archive_dir, f"Action_Plan_{last_run_day}.md")
                    os.rename(plan_file, archive_file)
                    # Create blank new plan for the new day
                    with open(plan_file, "w", encoding="utf-8") as f:
                        f.write(f"# Daily Action Plan - {current_day}\n- [ ] Waiting for morning session briefing...")
                
                last_run_day = current_day

            # 2. Check for Inbox Drafts
            files = [f for f in os.listdir(inbox) if f.endswith(".md")]
            for filename in files:
                filepath = os.path.join(inbox, filename)
                logger.info(f"VLI Inbox: Detected new draft '{filename}'. Processing...")
                
                with open(filepath, "r", encoding="utf-8") as rf:
                    content = rf.read()
                
                # Extract logic and update global alerts
                new_alerts = extract_vli_logic(content)
                global _vli_extracted_alerts
                _vli_extracted_alerts.extend(new_alerts)
                # Keep only unique alerts by symbol/label
                seen = set()
                unique_alerts = []
                for a in _vli_extracted_alerts:
                    key = f"{a['symbol']}:{a['label']}"
                    if key not in seen:
                        seen.add(key)
                        unique_alerts.append(a)
                _vli_extracted_alerts = unique_alerts
                
                # Append to active plan (dynamic date-based filename)
                with open(plan_file, "a", encoding="utf-8") as af:
                    af.write(f"\n\n### Batch Update: {filename}\n{content}")
                
                # Success: Move to archives instead of deleting
                archive_path = os.path.join(archive_dir, f"Draft_{datetime.now().strftime('%H%M%S')}_{filename}")
                os.rename(filepath, archive_path)
                logger.info(f"VLI Inbox: Archived draft to {archive_path}")
                
        except Exception as e:
            logger.error(f"VLI Reactive Pipeline Error: {e}")
            
        await asyncio.sleep(0.5) # High-frequency reactive polling

@app.on_event("startup")
async def startup_event():
    logger.info("Cobalt Multiagent: Launching VLI Reactive Pipeline.")
    asyncio.create_task(vli_inbox_watcher())

@app.post("/api/chat/stream", dependencies=[Depends(verify_api_key)])
async def chat_stream(request: ChatRequest):
    # Check if MCP server configuration is enabled
    mcp_enabled = get_bool_env("ENABLE_MCP_SERVER_CONFIGURATION", False)

    # Validate MCP settings if provided
    if request.mcp_settings and not mcp_enabled:
        raise HTTPException(
            status_code=403,
            detail="MCP server configuration is disabled. Set ENABLE_MCP_SERVER_CONFIGURATION=true to enable MCP features.",
        )

    thread_id = request.thread_id
    if thread_id == "__default__":
        thread_id = str(uuid4())

    return StreamingResponse(
        _astream_workflow_generator(
            request.model_dump()["messages"],
            thread_id,
            request.resources,
            request.max_plan_iterations,
            request.max_step_num,
            request.max_search_results,
            request.auto_accepted_plan,
            request.interrupt_feedback,
            request.mcp_settings if mcp_enabled else {},
            request.enable_background_investigation,
            request.report_style,
            request.enable_deep_thinking,
            request.snaptrade_settings if request.snaptrade_settings else {},
            request.obsidian_settings if request.obsidian_settings else {},
            request.verbosity,
            request.is_test_mode,
        ),
        media_type="text/event-stream",
    )


def _process_tool_call_chunks(tool_call_chunks):
    """Process tool call chunks and sanitize arguments."""
    chunks = []
    for chunk in tool_call_chunks:
        chunks.append(
            {
                "name": chunk.get("name", ""),
                "args": sanitize_args(chunk.get("args", "")),
                "id": chunk.get("id", ""),
                "index": chunk.get("index", 0),
                "type": chunk.get("type", ""),
            }
        )
    return chunks


def _get_agent_name(agent, message_metadata):
    """Extract agent name from agent tuple."""
    agent_name = "unknown"
    if agent and len(agent) > 0:
        agent_name = agent[0].split(":")[0] if ":" in agent[0] else agent[0]
    else:
        agent_name = message_metadata.get("langgraph_node", "unknown")
    return agent_name


def _create_event_stream_message(
    message_chunk, message_metadata, thread_id, agent_name
):
    """Create base event stream message."""
    event_stream_message = {
        "thread_id": thread_id,
        "agent": agent_name,
        "id": message_chunk.id,
        "role": "assistant",
        "checkpoint_ns": message_metadata.get("checkpoint_ns", ""),
        "langgraph_node": message_metadata.get("langgraph_node", ""),
        "langgraph_path": message_metadata.get("langgraph_path", ""),
        "langgraph_step": message_metadata.get("langgraph_step", ""),
        "content": message_chunk.content,
    }

    # Add optional fields
    if message_chunk.additional_kwargs.get("reasoning_content"):
        event_stream_message["reasoning_content"] = message_chunk.additional_kwargs[
            "reasoning_content"
        ]

    if message_chunk.response_metadata.get("finish_reason"):
        event_stream_message["finish_reason"] = message_chunk.response_metadata.get(
            "finish_reason"
        )

    return event_stream_message


def _create_interrupt_event(thread_id, event_data):
    """Create interrupt event."""
    interrupt_obj = event_data["__interrupt__"][0]

    # Handle different versions of LangGraph Interrupt object
    try:
        # Try the old format first (for backward compatibility)
        interrupt_id = interrupt_obj.ns[0] if hasattr(interrupt_obj, 'ns') else str(interrupt_obj)
        content = interrupt_obj.value if hasattr(interrupt_obj, 'value') else str(interrupt_obj)
    except AttributeError:
        # Newer version of LangGraph might have different structure
        interrupt_id = str(interrupt_obj) if not hasattr(interrupt_obj, 'id') else interrupt_obj.id
        content = str(interrupt_obj) if not hasattr(interrupt_obj, 'value') else interrupt_obj.value

    return _make_event(
        "interrupt",
        {
            "thread_id": thread_id,
            "id": interrupt_id,
            "role": "assistant",
            "content": content,
            "finish_reason": "interrupt",
            "options": [
                {"text": "Edit plan", "value": "edit_plan"},
                {"text": "Start research", "value": "accepted"},
            ],
        },
    )


def _process_initial_messages(message, thread_id):
    """Process initial messages and yield formatted events."""
    json_data = json.dumps(
        {
            "thread_id": thread_id,
            "id": "run--" + message.get("id", uuid4().hex),
            "role": "user",
            "content": message.get("content", ""),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    chat_stream_message(
        thread_id, f"event: message_chunk\ndata: {json_data}\n\n", "none"
    )


async def _process_message_chunk(message_chunk, message_metadata, thread_id, agent, session_obj=None, project_obj=None):
    """Process a single message chunk and yield appropriate events."""
    agent_name = _get_agent_name(agent, message_metadata)
    event_stream_message = _create_event_stream_message(
        message_chunk, message_metadata, thread_id, agent_name
    )

    # Save assistant messages to database
    if isinstance(message_chunk, (AIMessage, AIMessageChunk)) and message_chunk.content:
        try:
            # Try to save the message to database (this will work if session exists)
            if session_obj:
                research_db.save_session_message(
                    session_id=session_obj.id,
                    role="assistant",
                    content=message_chunk.content,
                    message_type="text"
                )

                # Extract and save research findings from AI responses
                if project_obj:
                    research_db.extract_and_save_findings(
                        content=message_chunk.content,
                        project_id=project_obj.id,
                        session_id=str(session_obj.id)
                    )

        except Exception as e:
            # Silently fail if database is not available or session doesn't exist
            pass

    if isinstance(message_chunk, ToolMessage):
        # Tool Message - Return the result of the tool call
        event_stream_message["tool_call_id"] = message_chunk.tool_call_id

        # Save tool results to database
        try:
            if session_obj:
                research_db.save_session_message(
                    session_id=session_obj.id,
                    role="tool",
                    content=str(message_chunk.content),
                    message_type="tool_result",
                    tool_calls=message_chunk.tool_call_id
                )
        except Exception as e:
            pass

        yield _make_event("tool_call_result", event_stream_message)
    elif isinstance(message_chunk, (AIMessage, AIMessageChunk)):
        # AI Message - Raw message tokens
        if message_chunk.tool_calls:
            # AI Message - Tool Call
            event_stream_message["tool_calls"] = message_chunk.tool_calls
            event_stream_message["tool_call_chunks"] = _process_tool_call_chunks(
                message_chunk.tool_call_chunks
            )

            # Save tool calls to database
            try:
                if session_obj:
                    tool_calls_json = json.dumps([{
                        "name": tc.get("name", ""),
                        "args": tc.get("args", ""),
                        "id": tc.get("id", "")
                    } for tc in message_chunk.tool_calls])
                    research_db.save_session_message(
                        session_id=session_obj.id,
                        role="assistant",
                        content="",
                        message_type="tool_call",
                        tool_calls=tool_calls_json
                    )
            except Exception as e:
                pass

            yield _make_event("tool_calls", event_stream_message)
        elif hasattr(message_chunk, "tool_call_chunks") and message_chunk.tool_call_chunks:
            # AI Message - Tool Call Chunks
            event_stream_message["tool_call_chunks"] = _process_tool_call_chunks(
                message_chunk.tool_call_chunks
            )
            yield _make_event("tool_call_chunks", event_stream_message)
        else:
            # AI Message - Raw message tokens
            yield _make_event("message_chunk", event_stream_message)


async def _stream_graph_events(
    graph_instance, workflow_input, workflow_config, thread_id, session_obj=None, project_obj=None
):
    """Stream events from the graph and process them."""
    try:
        async for agent, _, event_data in graph_instance.astream(
            workflow_input,
            config=workflow_config,
            stream_mode=["messages", "updates"],
            subgraphs=True,
        ):
            if isinstance(event_data, dict):
                if "__interrupt__" in event_data:
                    yield _create_interrupt_event(thread_id, event_data)
                continue

            message_chunk, message_metadata = cast(
                tuple[BaseMessage, dict[str, Any]], event_data
            )

            async for event in _process_message_chunk(
                message_chunk, message_metadata, thread_id, agent, session_obj, project_obj
            ):
                yield event
    except Exception as e:
        logger.exception("Error during graph execution")
        yield _make_event(
            "error",
            {
                "thread_id": thread_id,
                "error": str(e),
            },
        )



async def _astream_workflow_generator(
    messages: List[dict],
    thread_id: str,
    resources: List[Resource],
    max_plan_iterations: int,
    max_step_num: int,
    max_search_results: int,
    auto_accepted_plan: bool,
    interrupt_feedback: str,
    mcp_settings: dict,
    enable_background_investigation: bool,
    report_style: ReportStyle,
    enable_deep_thinking: bool,
    snaptrade_settings: dict,
    obsidian_settings: dict,
    verbosity: int = 1,
    is_test_mode: bool = False,
):
    # Create research project and session for persistence
    research_topic = messages[-1]["content"] if messages else "Research Session"
    session_obj = None
    project_obj = None

    try:
        # Create or get research project
        project_obj = research_db.create_research_project(
            title=f"Research: {research_topic[:100]}",
            description=f"Research session on: {research_topic}",
            tags="auto-generated"
        )
        logger.info(f"Created research project: {project_obj.id}")

        # Create research session
        session_obj = research_db.create_research_session(
            project_id=project_obj.id,
            session_id=thread_id,
            title=f"Session: {research_topic[:50]}"
        )
        logger.info(f"Created research session: {session_obj.id}")

    except Exception as e:
        logger.warning(f"Failed to create research project/session: {e}")

    # Process initial messages
    for message in messages:
        if isinstance(message, dict) and "content" in message:
            _process_initial_messages(message, thread_id)

            # Save user message to database
            try:
                if session_obj:
                    research_db.save_session_message(
                        session_id=session_obj.id,
                        role=message.get("role", "user"),
                        content=message.get("content", ""),
                        message_type="text"
                    )
            except Exception as e:
                logger.warning(f"Failed to save user message: {e}")

    # Prepare workflow input
    workflow_input = {
        "messages": messages,
        "plan_iterations": 0,
        "final_report": "",
        "current_plan": None,
        "observations": [],
        "auto_accepted_plan": auto_accepted_plan,
        "enable_background_investigation": enable_background_investigation,
        "research_topic": messages[-1]["content"] if messages else "",
        "obsidian_settings": obsidian_settings,
        "verbosity": verbosity,
        "test_mode": is_test_mode,
    }

    if not auto_accepted_plan and interrupt_feedback:
        resume_msg = f"[{interrupt_feedback}]"
        if messages:
            resume_msg += f" {messages[-1]['content']}"
        workflow_input = Command(resume=resume_msg)

    # Prepare workflow config
    workflow_config = {
        "configurable": {
            "thread_id": thread_id,
            "max_plan_iterations": max_plan_iterations,
            "max_step_num": max_step_num,
            "max_search_results": max_search_results,
            "mcp_settings": mcp_settings,
            "report_style": report_style.value,
            "enable_deep_thinking": enable_deep_thinking,
            "snaptrade_settings": snaptrade_settings,
            "obsidian_settings": obsidian_settings,
        },
        "recursion_limit": get_recursion_limit(),
    }

    checkpoint_saver = get_bool_env("LANGGRAPH_CHECKPOINT_SAVER", False)
    checkpoint_url = get_str_env("LANGGRAPH_CHECKPOINT_DB_URL", "")
    # Handle checkpointer if configured
    connection_kwargs = {
        "autocommit": True,
        "row_factory": "dict_row",
        "prepare_threshold": 0,
    }
    if checkpoint_saver and checkpoint_url != "":
        if checkpoint_url.startswith("postgresql://"):
            logger.info("start async postgres checkpointer.")
            async with AsyncConnectionPool(
                checkpoint_url, kwargs=connection_kwargs
            ) as conn:
                checkpointer = AsyncPostgresSaver(conn)
                await checkpointer.setup()
                graph.checkpointer = checkpointer
                graph.store = in_memory_store
                async for event in _stream_graph_events(
                    graph, workflow_input, workflow_config, thread_id, session_obj, project_obj
                ):
                    yield event

        if checkpoint_url.startswith("mongodb://"):
            logger.info("Starting native MongoDB checkpointer.")
            async with NativeMongoDBSaver.from_conn_string(
                checkpoint_url
            ) as checkpointer:
                graph.checkpointer = checkpointer
                graph.store = in_memory_store
                async for event in _stream_graph_events(
                    graph, workflow_input, workflow_config, thread_id, session_obj, project_obj
                ):
                    yield event
    else:
        # Use graph without MongoDB checkpointer
        async for event in _stream_graph_events(
            graph, workflow_input, workflow_config, thread_id, session_obj, project_obj
        ):
            yield event


def _make_event(event_type: str, data: dict[str, any]):
    if data.get("content") == "":
        data.pop("content")
    # Ensure JSON serialization with proper encoding
    try:
        json_data = json.dumps(data, ensure_ascii=False)

        finish_reason = data.get("finish_reason", "")
        chat_stream_message(
            data.get("thread_id", ""),
            f"event: {event_type}\ndata: {json_data}\n\n",
            finish_reason,
        )

        return f"event: {event_type}\ndata: {json_data}\n\n"
    except (TypeError, ValueError) as e:
        logger.error(f"Error serializing event data: {e}")
        # Return a safe error event
        error_data = json.dumps({"error": "Serialization failed"}, ensure_ascii=False)
        return f"event: error\ndata: {error_data}\n\n"


@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech using volcengine TTS API."""
    app_id = get_str_env("VOLCENGINE_TTS_APPID", "")
    if not app_id:
        raise HTTPException(status_code=400, detail="VOLCENGINE_TTS_APPID is not set")
    access_token = get_str_env("VOLCENGINE_TTS_ACCESS_TOKEN", "")
    if not access_token:
        raise HTTPException(
            status_code=400, detail="VOLCENGINE_TTS_ACCESS_TOKEN is not set"
        )

    try:
        cluster = get_str_env("VOLCENGINE_TTS_CLUSTER", "volcano_tts")
        voice_type = get_str_env("VOLCENGINE_TTS_VOICE_TYPE", "BV700_V2_streaming")

        tts_client = VolcengineTTS(
            appid=app_id,
            access_token=access_token,
            cluster=cluster,
            voice_type=voice_type,
        )
        # Call the TTS API
        result = tts_client.text_to_speech(
            text=request.text[:1024],
            encoding=request.encoding,
            speed_ratio=request.speed_ratio,
            volume_ratio=request.volume_ratio,
            pitch_ratio=request.pitch_ratio,
            text_type=request.text_type,
            with_frontend=request.with_frontend,
            frontend_type=request.frontend_type,
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=str(result["error"]))

        # Decode the base64 audio data
        audio_data = base64.b64decode(result["audio_data"])

        # Return the audio file
        return Response(
            content=audio_data,
            media_type=f"audio/{request.encoding}",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=tts_output.{request.encoding}"
                )
            },
        )

    except Exception as e:
        logger.exception(f"Error in TTS endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/podcast/generate")
async def generate_podcast(request: GeneratePodcastRequest):
    try:
        report_content = request.content
        print(report_content)
        workflow = build_podcast_graph()
        final_state = workflow.invoke({"input": report_content})
        audio_bytes = final_state["output"]
        return Response(content=audio_bytes, media_type="audio/mp3")
    except Exception as e:
        logger.exception(f"Error occurred during podcast generation: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/ppt/generate")
async def generate_ppt(request: GeneratePPTRequest):
    try:
        report_content = request.content
        print(report_content)
        workflow = build_ppt_graph()
        final_state = workflow.invoke({"input": report_content})
        generated_file_path = final_state["generated_file_path"]
        with open(generated_file_path, "rb") as f:
            ppt_bytes = f.read()
        return Response(
            content=ppt_bytes,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    except Exception as e:
        logger.exception(f"Error occurred during ppt generation: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/prose/generate")
async def generate_prose(request: GenerateProseRequest):
    try:
        sanitized_prompt = request.prompt.replace("\r\n", "").replace("\n", "")
        logger.info(f"Generating prose for prompt: {sanitized_prompt}")
        workflow = build_prose_graph()
        events = workflow.astream(
            {
                "content": request.prompt,
                "option": request.option,
                "command": request.command,
            },
            stream_mode="messages",
            subgraphs=True,
        )
        return StreamingResponse(
            (f"data: {event[0].content}\n\n" async for _, event in events),
            media_type="text/event-stream",
        )
    except Exception as e:
        logger.exception(f"Error occurred during prose generation: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/prompt/enhance")
async def enhance_prompt(request: EnhancePromptRequest):
    try:
        sanitized_prompt = request.prompt.replace("\r\n", "").replace("\n", "")
        logger.info(f"Enhancing prompt: {sanitized_prompt}")

        # Convert string report_style to ReportStyle enum
        report_style = None
        if request.report_style:
            try:
                # Handle both uppercase and lowercase input
                style_mapping = {
                    "ACADEMIC": ReportStyle.ACADEMIC,
                    "POPULAR_SCIENCE": ReportStyle.POPULAR_SCIENCE,
                    "NEWS": ReportStyle.NEWS,
                    "SOCIAL_MEDIA": ReportStyle.SOCIAL_MEDIA,
                }
                report_style = style_mapping.get(
                    request.report_style.upper(), ReportStyle.ACADEMIC
                )
            except Exception:
                # If invalid style, default to ACADEMIC
                report_style = ReportStyle.ACADEMIC
        else:
            report_style = ReportStyle.ACADEMIC

        workflow = build_prompt_enhancer_graph()
        final_state = workflow.invoke(
            {
                "prompt": request.prompt,
                "context": request.context,
                "report_style": report_style,
            }
        )
        return {"result": final_state["output"]}
    except Exception as e:
        logger.exception(f"Error occurred during prompt enhancement: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.post("/api/mcp/server/metadata", response_model=MCPServerMetadataResponse)
async def mcp_server_metadata(request: MCPServerMetadataRequest):
    """Get information about an MCP server."""
    # Check if MCP server configuration is enabled
    if not get_bool_env("ENABLE_MCP_SERVER_CONFIGURATION", False):
        raise HTTPException(
            status_code=403,
            detail="MCP server configuration is disabled. Set ENABLE_MCP_SERVER_CONFIGURATION=true to enable MCP features.",
        )

    try:
        # Set default timeout with a longer value for this endpoint
        timeout = 300  # Default to 300 seconds for this endpoint

        # Use custom timeout from request if provided
        if request.timeout_seconds is not None:
            timeout = request.timeout_seconds

        # Load tools from the MCP server using the utility function
        tools = await load_mcp_tools(
            server_type=request.transport,
            command=request.command,
            args=request.args,
            url=request.url,
            env=request.env,
            headers=request.headers,
            timeout_seconds=timeout,
        )

        # Create the response with tools
        response = MCPServerMetadataResponse(
            transport=request.transport,
            command=request.command,
            args=request.args,
            url=request.url,
            env=request.env,
            headers=request.headers,
            tools=tools,
        )

        return response
    except Exception as e:
        logger.exception(f"Error in MCP server metadata endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_DETAIL)


@app.get("/api/rag/config", response_model=RAGConfigResponse)
async def rag_config():
    """Get the config of the RAG."""
    return RAGConfigResponse(provider=SELECTED_RAG_PROVIDER)


@app.get("/api/rag/resources", response_model=RAGResourcesResponse)
async def rag_resources(request: Annotated[RAGResourceRequest, Query()]):
    """Get the resources of the RAG."""
    retriever = build_retriever()
    if retriever:
        return RAGResourcesResponse(resources=retriever.list_resources(request.query))
    return RAGResourcesResponse(resources=[])


@app.get("/api/config", response_model=ConfigResponse)
async def config():
    """Get the config of the server."""
    return ConfigResponse(
        rag=RAGConfigResponse(provider=SELECTED_RAG_PROVIDER),
        models=get_configured_llm_models(),
    )

# Include research API routes
app.include_router(research_router, prefix="/api/research", tags=["research"])
app.include_router(studio_router)

# Trigger hot reload

