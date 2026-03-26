# Agent: Coordinator - Node definition for multi-step graph orchestration.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any, Literal
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

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

def coordinator_node(state: State, config: RunnableConfig) -> Command[Literal["human_feedback", "reporter", "__end__"]]:
    """Coordinator node - Detailed multi-step planning."""
    logger.info("VLI Coordinator is planning execution.")
    analyst_keywords = ", ".join(get_analyst_keywords())
    state_for_prompt = {**state, "ANALYST_KEYWORDS": analyst_keywords}
    
    messages = apply_prompt_template("coordinator", state_for_prompt)
    llm = get_llm_by_type(AGENT_LLM_MAP.get("coordinator", "reasoning"))
    structured_llm = llm.with_structured_output(Plan)
    
    plan_obj = structured_llm.invoke(messages)
    return Command(
        update={
            "current_plan": plan_obj,
            "messages": [AIMessage(content=str(plan_obj), name="vli_coordinator")]
        },
        goto="human_feedback",
    )
