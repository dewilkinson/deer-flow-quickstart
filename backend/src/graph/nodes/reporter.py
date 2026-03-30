# Agent: Reporter - Node definition for final synthesis reporting.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any
from src.tools.shared_storage import GLOBAL_CONTEXT
from ..types import State

logger = logging.getLogger(__name__)

# 1. Private to the Agent Code Itself
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type (None for Reporter)
_SHARED_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

import os
import json
from datetime import datetime
from langchain_core.messages import AIMessage, HumanMessage

def reporter_node(state: State):
    """Reporter node implementation."""
    logger.info("Reporter Node: Synthesis completed.")
    
    # 1. Telemetry Logging: Silently push atomic step summaries to the backlog
    vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    if vault_path:
        cobalt_dir = os.path.join(vault_path, "_cobalt")
        os.makedirs(cobalt_dir, exist_ok=True)
        telemetry_file = os.path.join(cobalt_dir, "VLI_Raw_Telemetry.md")
        
        # Extract atomic metrics
        messages = state.get("messages", [])
        initial_command = "Unknown"
        agent_sequence = []
        final_response = "Unknown"
        
        for msg in messages:
            if isinstance(msg, HumanMessage) and initial_command == "Unknown":
                initial_command = str(msg.content)
            elif isinstance(msg, AIMessage) and getattr(msg, "name", None):
                if msg.name != "reporter" and msg.name not in ["coordinator", "router"]:
                    agent_sequence.append(msg.name)
            
        if messages and isinstance(messages[-1], AIMessage):
            final_response = str(messages[-1].content)
        elif len(messages) > 0:
            final_response = str(messages[-1].content)
            
        timestamp = datetime.now().isoformat()
        
        log_entry = (
            f"### [{timestamp}] VLI Transaction\n"
            f"- **Command**: `{initial_command}`\n"
            f"- **Agents Spun Up**: `{len(agent_sequence)}` -> `{json.dumps(agent_sequence)}`\n"
            f"- **System Response**: {final_response}\n\n"
            "---\n"
        )
        
        try:
            with open(telemetry_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"Failed to write telemetry: {e}")
            
    return {"final_report": "Analysis synthesis completed."}

