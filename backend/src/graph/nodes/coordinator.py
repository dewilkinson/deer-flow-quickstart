# Agent: Coordinator - Node definition for multi-step graph orchestration.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any, Literal
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from src.config.agents import AGENT_LLM_MAP
from src.llms.llm import get_llm_by_type
from src.prompts.planner_model import Plan
from src.prompts.template import apply_prompt_template
from src.config.analyst import get_analyst_keywords
from src.tools.shared_storage import ORCHESTRATOR_CONTEXT, GLOBAL_CONTEXT
from ..types import State

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = ORCHESTRATOR_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

def coordinator_node(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """Coordinator node - Detailed multi-step planning."""
    logger.info("VLI Coordinator is planning execution.")
    analyst_keywords = ", ".join(get_analyst_keywords())
    
    # 1. Setup LLM and Tools
    llm = get_llm_by_type(AGENT_LLM_MAP.get("coordinator", "reasoning"))
    from .common_vli import get_orchestrator_tools
    tools = get_orchestrator_tools(config)
    llm_with_tools = llm.bind_tools(tools)
    structured_llm = llm_with_tools.with_structured_output(Plan)
    
    # 2. Check if we are returning from an agent
    current_plan = state.get("current_plan")
    steps_completed = state.get("steps_completed", 0)
    
    # Defensive: Check the recent messages - if one is from an agent, we finished a step
    known_agents = list(AGENT_LLM_MAP.keys()) + ["scout", "analyst", "portfolio_manager", "risk_manager", "journaler"]
    
    last_msgs = state["messages"][-5:] if state.get("messages") else []
    from_agent = False
    last_agent_name = None
    for msg in reversed(last_msgs):
        msg_name = getattr(msg, "name", None)
        if msg_name in known_agents and msg_name not in ["coordinator", "vli_coordinator"]:
            from_agent = True
            last_agent_name = msg_name
            break
    
    # Check if we are in autonomous research/simulation mode
    is_autonomous = state.get("is_test_mode", False) or state.get("test_mode", False)
    
    if from_agent and current_plan:
        steps_completed += 1
        logger.info(f"[COORD] Step {steps_completed}/{len(current_plan.steps)} finished by {last_agent_name}")
        if steps_completed >= len(current_plan.steps):
            return {
                "steps_completed": steps_completed,
                "messages": [AIMessage(content="Finalizing plan execution.", name="coordinator")]
            }
        return {"steps_completed": steps_completed}

    # 3. Apply Multi-Step Planning Template
    cached_tickers_set = set()
    try:
        global_tickers = GLOBAL_CONTEXT.get("cached_tickers", set())
        cached_tickers_set.update(global_tickers)
    except Exception as e:
        logger.debug(f"Could not read global ticker cache for coordinator: {e}")
        
    from src.config.configuration import Configuration
    configurable = Configuration.from_runnable_config(config)
    dev_mode = getattr(configurable, 'developer_mode', False)
    
    state_for_prompt = {
        **state, 
        "DEVELOPER_MODE": str(dev_mode).lower(),
        "ANALYST_KEYWORDS": analyst_keywords,
        "CACHED_TICKERS": ", ".join(sorted(list(cached_tickers_set))) if cached_tickers_set else "None (Data Store Empty)"
    }
    
    messages = apply_prompt_template("coordinator", state_for_prompt)
    plan_obj = structured_llm.invoke(messages)
    
    return {
        "current_plan": plan_obj,
        "steps_completed": steps_completed,
        "messages": [AIMessage(content=str(plan_obj), name="coordinator")]
    }
