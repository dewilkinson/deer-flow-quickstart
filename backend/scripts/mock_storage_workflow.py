from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import asyncio
import json
import random
import logging

import sys
import os
from dotenv import load_dotenv

env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(dotenv_path=env_path)

# Inject dummy API keys completely bypassing Pydantic environment validation
os.environ["OPENAI_API_KEY"] = "mock-key-for-ui-test"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["ANTHROPIC_API_KEY"] = "mock-key"
os.environ["GEMINI_API_KEY"] = "mock-key"
if not os.environ.get("OBSIDIAN_VAULT_PATH"):
    os.environ["OBSIDIAN_VAULT_PATH"] = "c:\\github\\obsidian-vault"

# Append packages/harness to Python Path so deerflow resolves
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "packages", "harness")))

from deerflow.agents.memory.storage import FileMemoryStorage, ObsidianMemoryStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CMA Network Visualizer Mock Server")

# Allow Next.js requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def event_generator():
    """Generates server-sent events for the network visualization."""
    
    # Send structure defining the grid
    init_payload = {
        "type": "init",
        "nodes": [
            {"id": "agent-planner", "type": "agent", "label": "Lead Planner"},
            {"id": "agent-researcher", "type": "agent", "label": "Researcher"},
            {"id": "agent-writer", "type": "agent", "label": "Writer"},
            {"id": "storage-global", "type": "storage", "label": "Global Cache"},
            {"id": "storage-local", "type": "storage", "label": "Local Memory (JSON)"},
            {"id": "storage-obsidian", "type": "storage", "label": "Obsidian Vault (.md)"}
        ]
    }
    yield f"data: {json.dumps(init_payload)}\n\n"
    
    file_storage = FileMemoryStorage()
    obsidian_storage = ObsidianMemoryStorage()

    def transmit(action: str, source: str, target: str, message: str):
        payload = {
            "type": "event",
            "action": action, 
            "source": source,
            "target": target,
            "message": message
        }
        return f"data: {json.dumps(payload)}\n\n"

    try:
        # Phase 1: Planner spins up & writes global task
        await asyncio.sleep(1)
        yield transmit("spin-up", "agent-planner", "agent-planner", "Planner Agent Initialized")
        
        await asyncio.sleep(1.5)
        task_data = {"task": "Write comprehensive guide on quantum causality", "status": "pending"}
        # Execute actual storage update
        file_storage.save(task_data, None) 
        yield transmit("write", "agent-planner", "storage-global", "Wrote initial task to Global Memory")

        # Phase 2: Researcher spins up & reads global task
        await asyncio.sleep(2)
        yield transmit("spin-up", "agent-researcher", "agent-researcher", "Researcher Agent Initialized")
        
        await asyncio.sleep(1)
        file_storage.load(None) 
        yield transmit("read", "storage-global", "agent-researcher", "Read global task from Global Memory")

        # Phrase 3: Researcher writes to Obsidian memory
        await asyncio.sleep(2)
        research_data = {"findings": "Quantum entangled systems exhibit retroactive causality boundaries."}
        obsidian_storage.save(research_data, "researcher")
        yield transmit("write", "agent-researcher", "storage-obsidian", "Wrote findings to Obsidian Vault")

        # Phase 4: Writer spins up & reads from Obsidian memory
        await asyncio.sleep(1.5)
        yield transmit("spin-up", "agent-writer", "agent-writer", "Writer Agent Initialized")
        
        await asyncio.sleep(1)
        obsidian_storage.load("researcher")
        yield transmit("read", "storage-obsidian", "agent-writer", "Read researcher notes from Obsidian Vault")

        # Phase 5: Writer commits to Local File Memory
        await asyncio.sleep(2)
        final_doc = {"doc_id": "guide-101", "content": "The boundary of causality..."}
        file_storage.save(final_doc, "writer")
        yield transmit("write", "agent-writer", "storage-local", "Wrote final draft to Local Agent Memory")

        # Phase 6: Sync back to Global
        await asyncio.sleep(1.5)
        file_storage.save({"task": "Write comprehensive guide on quantum causality", "status": "completed"}, None) 
        yield transmit("write", "agent-writer", "storage-global", "Updated Global task status to completed")

        # End of stream flag
        await asyncio.sleep(2)
        yield f"data: {json.dumps({'type': 'complete'})}\n\n"

    except Exception as e:
        logger.error(f"Error in simulation: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@app.get("/api/simulate")
async def simulate_network():
    """Starts the network workflow visualization test."""
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    # Make sure we run on 8001 to not conflict with normal backend
    uvicorn.run("mock_storage_workflow:app", host="0.0.0.0", port=8001, reload=True)
