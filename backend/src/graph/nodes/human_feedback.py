# Core: Human Feedback - Node definition for user reviews and routing.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Literal, Dict, Any
from langchain_core.messages import HumanMessage
from langgraph.types import Command, interrupt
from src.prompts.planner_model import Plan
from src.tools.shared_storage import GLOBAL_CONTEXT
from ..types import State

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

def human_feedback_node(state: State) -> Command[Literal["parser", "reporter", "researcher", "coder", "scout", "journaler", "analyst", "imaging", "__end__"]]:
    """Human Feedback node implementation."""
    current_plan = state.get("current_plan")
    auto_accepted_plan = state.get("auto_accepted_plan", False)
    
    plan_obj = current_plan if isinstance(current_plan, Plan) else None
    
    # Auto-accept in Test or Debug mode
    import os
    from src.config.loader import get_bool_env
    vli_test = os.getenv("VLI_TEST_MODE", "").lower() in ("true", "1", "yes")
    vli_debug = os.getenv("VLI_DEBUG_MODE", "").lower() in ("true", "1", "yes")
    
    if vli_test or vli_debug or get_bool_env("VLI_TEST_MODE", False) or get_bool_env("VLI_DEBUG_MODE", False):
        logger.info("Test/Debug mode enabled: Automatically approving request.")
        auto_accepted_plan = True

    if not auto_accepted_plan:
        feedback = interrupt("Please Review the Plan.")
        if feedback and str(feedback).upper().startswith("[EDIT_PLAN]"):
            return Command(update={"messages": [HumanMessage(content=feedback, name="vli_feedback")]}, goto="parser")
        elif feedback and str(feedback).upper().startswith("[ACCEPTED]"):
            logger.info("Plan accepted.")
        else:
            raise TypeError(f"Unsupported feedback type: {feedback}")

    # Determine next routing
    if not plan_obj or not plan_obj.steps:
        return Command(goto="reporter")
    
    first_step = plan_obj.steps[0]
    st = first_step.step_type.lower()
    if st == "research": return Command(goto="researcher")
    if st == "processing": return Command(goto="coder")
    if st == "scout": return Command(goto="scout")
    if st == "journaler": return Command(goto="journaler")
    if st == "analyst": return Command(goto="analyst")
    if st == "imaging": return Command(goto="imaging")
    
    return Command(goto="reporter")
