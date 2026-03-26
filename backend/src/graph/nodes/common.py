# Core: Common - Shared node utilities and execution logic.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any
from langchain_core.messages import AIMessage
from langgraph.types import Command
from src.agents import create_agent_from_registry
from src.config.configuration import Configuration

logger = logging.getLogger(__name__)

async def _setup_and_execute_agent_step(state, config, agent_type, tools):
    """Executes the agent and captures the result for the reporter."""
    agent = create_agent_from_registry(agent_type, tools)
    
    # Engagement with the actual agent context
    result = await agent.ainvoke(state, config)
    
    # Extract observations for the dashboard
    observations = []
    if isinstance(result, dict) and "messages" in result:
        last_msg = result["messages"][-1]
        if hasattr(last_msg, "content"):
            observations.append(last_msg.content)
            
    return Command(
        update={
            "messages": result.get("messages", []),
            "observations": observations
        },
        goto="reporter"
    )
