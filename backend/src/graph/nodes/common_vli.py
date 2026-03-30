# Core: Common VLI - Shared node utilities and execution logic (V2 - Cache Buster).
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from src.agents import create_agent_from_registry
from src.config.configuration import Configuration
from src.tools import (
    get_stock_quote,
    get_web_search_tool,
    crawl_tool,
    snapper
)

logger = logging.getLogger(__name__)

async def _setup_and_execute_agent_step(state, config, agent_type, tools, agent_instructions: str = ""):
    """Executes the agent and captures the result for the reporter."""
    
    # 1. Diagnostic Trace: Emit a lifecycle log for the dashboard if in Test Mode
    if state.get("test_mode") or state.get("is_test_mode"):
        state["messages"].append(AIMessage(
            content=f"🚀 Node activated: {agent_type.upper()}. Preparing for high-fidelity execution...",
            name=agent_type
        ))

    agent = create_agent_from_registry(agent_type, tools)
    
    # Engagement with the actual agent context
    result = await agent.ainvoke(state, config)
    
    # Extract observations for the dashboard
    observations = []
    last_content = ""
    if isinstance(result, dict) and "messages" in result:
        last_msg = result["messages"][-1]
        if hasattr(last_msg, "content"):
            last_content = str(last_msg.content)
            observations.append(last_content)
    
    # Handle multi-step plan updates
    current_plan = state.get("current_plan")
    goto_node = "reporter"
    
    if current_plan:
        steps = []
        if hasattr(current_plan, "steps"):
            steps = current_plan.steps
        elif isinstance(current_plan, dict) and "steps" in current_plan:
            steps = current_plan["steps"]
            
        for step in steps:
            # Handle both object and dict steps
            if hasattr(step, "execution_res"):
                if getattr(step, "execution_res") is None:
                    setattr(step, "execution_res", last_content or "Executed.")
                    break
            elif isinstance(step, dict) and step.get("execution_res") is None:
                step["execution_res"] = last_content or "Executed."
                break

    # Ensure all messages from the agent are "Signed" so the coordinator can recognize them
    new_messages = result.get("messages", []) if isinstance(result, dict) else []
    if not new_messages:
        # Fallback: create a sentinel message if the agent didn't return any
        new_messages = [AIMessage(content=f"{agent_type.upper()} task completed successfully.", name=agent_type)]
    else:
        # Sign the last message from the agent to mark the turn as complete
        last_msg = new_messages[-1]
        
        # LangChain messages are often immutable, so we replace with a named copy for identity tracking
        if isinstance(last_msg, AIMessage):
            new_messages[-1] = AIMessage(content=last_msg.content, name=agent_type)
        elif hasattr(last_msg, "content"):
            new_messages[-1] = AIMessage(content=str(last_msg.content), name=agent_type)
        else:
            # Absolute fallback: append a sentinel
            new_messages.append(AIMessage(content="Step complete.", name=agent_type))

    # Hub-and-Spoke Routing Logic: Always return to the coordinator if a plan is in progress
    if current_plan:
        goto_node = "coordinator"
    elif state.get("is_test_mode", False) or state.get("test_mode", False):
        goto_node = "coordinator"

    return {
        "messages": new_messages,
        "observations": observations,
        "current_plan": current_plan
    }

# Orchestrator Fast Bypass Tools
def get_orchestrator_tools(config: RunnableConfig):
    """Returns a list of tools available to the Orchestrator for fast bypass."""
    configurable = Configuration.from_runnable_config(config)
    return [
        get_stock_quote,
        get_web_search_tool(configurable.max_search_results),
        crawl_tool,
        snapper
    ]
