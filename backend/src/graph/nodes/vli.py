# Agent: VLI (VibeLink Interface) - The Central Nervous System
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
import os
import time
import asyncio
from typing import Any, Literal, cast

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from src.config.agents import AGENT_LLM_MAP
from src.config.analyst import get_analyst_keywords
from src.config.configuration import Configuration
from src.llms.llm import get_llm_by_type
from src.prompts.planner_model import Plan, Step, StepType
from src.prompts.template import apply_prompt_template
from src.tools.shared_storage import GLOBAL_CONTEXT, ORCHESTRATOR_CONTEXT
from src.services.macro_registry import macro_registry

from ..types import State

logger = logging.getLogger(__name__)

# 1. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = ORCHESTRATOR_CONTEXT

# 2. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

async def vli_node(state: State, config: RunnableConfig) -> Command[Literal["portfolio_manager", "smc_analyst", "analyst", "risk_manager", "journaler", "synthesizer", "coder", "imaging", "system", "reporter", "human_feedback", "session_monitor", "vision_specialist", "terminal_specialist", "__end__"]]:
    """
    Unified VLI Spine Node. 
    Handles: Vibe Checking, Fast-Path, Multi-step Planning, and Execution Coordination.
    """
    logger.info("VLI Spine is processing context.")
    
    # 0. Configuration & Model Selection
    configurable = Configuration.from_runnable_config(config)
    llm_type = "core" # [NEW] Default to Gemma 4 (core) as requested
    if hasattr(configurable, "vli_llm_type"):
        llm_type = getattr(configurable, "vli_llm_type")
    elif "vli_llm_type" in config.get("configurable", {}):
        llm_type = config["configurable"]["vli_llm_type"]
    else:
        # Fallback to the explicit registry if the override isn't present
        llm_type = AGENT_LLM_MAP.get("coordinator", "core")
        
    llm = get_llm_by_type(llm_type)
    
    # 1. Turn Awareness & Execution Tracking
    current_plan = state.get("current_plan")
    steps_completed = state.get("steps_completed", 0)
    raw_messages = state.get("messages", [])
    
    # [COORDINATION LOGIC] Check if returning from a specialist
    if raw_messages:
        last_msg = raw_messages[-1]
        msg_name = getattr(last_msg, "name", None)
        # If msg came from a specialist, increment completion
        if msg_name and msg_name not in ["vli", "vli_spine", "vli_parser", "vli_coordinator", "assistant", "Assistant"]:
            steps_completed += 1
            logger.info(f"[VLI_SPINE] Returning from specialist '{msg_name}'. Completion: {steps_completed}/{len(current_plan.steps if current_plan else [])}")
            
            # If plan is finished, route to reporter
            if current_plan and steps_completed >= len(current_plan.steps):
                logger.info("[VLI_SPINE] Plan complete. Routing to synthesis.")
                return Command(update={"steps_completed": steps_completed}, goto="reporter" if not state.get("raw_data_mode") else "__end__")

    # 2. Workspace & Metadata Synchronization
    analyst_keywords = ", ".join(get_analyst_keywords())
    macro_labels = ", ".join(list(macro_registry.get_macros().keys()))
    
    # Inject Daily Action Plan from Obsidian
    vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    if vault_path:
        plan_file = os.path.join(vault_path, "_cobalt", "Daily_Action_Plan.md")
        if os.path.exists(plan_file):
            try:
                with open(plan_file, encoding="utf-8") as f:
                    _GLOBAL_RESOURCE_CONTEXT["daily_action_plan"] = f.read()
            except Exception: pass

    # Prepare artifact directory scope
    artifacts_dir = os.path.join(os.getcwd(), "data", "artifacts")
    available_artifacts = ""
    if os.path.exists(artifacts_dir):
        available_artifacts = ", ".join(os.listdir(artifacts_dir))

    state_for_prompt = {
        **state,
        "ANALYST_KEYWORDS": analyst_keywords,
        "MACRO_INDICATORS": macro_labels,
        "DAILY_ACTION_PLAN": _GLOBAL_RESOURCE_CONTEXT.get("daily_action_plan", "No daily instructions."),
        "CACHED_TICKERS": ", ".join(sorted(list(_GLOBAL_RESOURCE_CONTEXT.get("cached_tickers", set())))) or "None",
        "SYMBOL_ARTIFACTS": available_artifacts or "None",
    }

    # 3. Context Horizon Management (TPM Mitigation)
    MAX_HISTORY = 12
    if len(raw_messages) > MAX_HISTORY:
        target_idx = len(raw_messages) - MAX_HISTORY
        while target_idx > 0 and not isinstance(raw_messages[target_idx], HumanMessage):
            target_idx -= 1
        
        # [NEW] Prune message content internally to avoid prompt saturation
        pruned_msgs = []
        for m in raw_messages[target_idx:]:
            content = str(getattr(m, "content", ""))
            if len(content) > 3000:
                # Truncate overly verbose tool results for the Planner's sanity
                content = content[:1500] + "\n... [TRUNCATED FOR PLANNING STABILITY] ...\n" + content[-500:]
            
            # Reconstruct message with pruned content
            if isinstance(m, HumanMessage): pruned_msgs.append(HumanMessage(content=content))
            elif isinstance(m, AIMessage): pruned_msgs.append(AIMessage(content=content, name=m.name))
            elif isinstance(m, ToolMessage): pruned_msgs.append(ToolMessage(content=content, name=m.name, tool_call_id=m.tool_call_id))
            else: pruned_msgs.append(m)

        state_for_prompt["messages"] = pruned_msgs
        logger.info(f"[VLI_SPINE] History pruned and truncated at index {target_idx}")

    # 4. Phase A: Fast-Path & Intent Classification
    from .common_vli import get_orchestrator_tools
    tools = get_orchestrator_tools(config)
    llm_with_tools = llm.bind_tools(tools)
    
    messages = apply_prompt_template("parser", state_for_prompt) # Use parser template for intent
    
    # Heuristic Rule Injection (Institutional Stability)
    core_logic_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "CORE_LOGIC.md")
    if os.path.exists(core_logic_path):
        try:
             with open(core_logic_path, "r", encoding="utf-8") as f:
                 rules = [l.strip() for l in f.readlines() if l.strip().startswith(("-", "*"))]
                 if rules:
                     messages.append(HumanMessage(content=f"[SYSTEM OVERRIDE]: Guardrail Heuristics:\n" + "\n".join(rules[:3])))
        except: pass

    # First Invoke to check for immediate tool calls
    response = await llm_with_tools.ainvoke(messages)
    
    # Fast-Path Check
    tech_keywords = ["analyze", "analysis", "smc", "sortino", "sharpe", "report"]
    user_query = str(raw_messages[-1].content).lower() if raw_messages else ""
    is_technical = any(kw in user_query for kw in tech_keywords)

    if response.tool_calls and not is_technical:
        logger.info("[VLI_SPINE] Fast-Path Bypass triggered.")
        name_to_tool = {t.name: t for t in tools}
        sem = asyncio.Semaphore(3)
        
        async def run_t(tc):
            async with sem:
                t = name_to_tool.get(tc["name"])
                if t:
                    res = await t.ainvoke(tc["args"], config)
                    return ToolMessage(content=str(res), tool_call_id=tc["id"], name=tc["name"])
                return ToolMessage(content="Tool not found", tool_call_id=tc["id"], name=tc["name"])
        
        t_msgs = list(await asyncio.gather(*[run_t(tc) for tc in response.tool_calls]))
        synth_messages = messages + [response] + t_msgs + [HumanMessage(content="Synthesize these results. If this is a system command (like cache invalidation/reset), respond ONLY with a 1-sentence execution status, warning, or error. No conversational filler or persona.")]
        final_synth = await llm.ainvoke(synth_messages)
        
        return Command(
            update={"final_report": str(final_synth.content), "messages": [response] + t_msgs + [AIMessage(content=str(final_synth.content), name="vli")]},
            goto="__end__"
        )

    # 5. Phase B: Planning & Coordination
    # If not fast-path, we need a Plan
    structured_llm = llm.with_structured_output(Plan)
    messages_coord = apply_prompt_template("coordinator", state_for_prompt)
    
    try:
        plan_obj = await structured_llm.ainvoke(messages_coord)
    except Exception as e:
        logger.error(f"[VLI_SPINE] Structural Parsing Failure: {e}. Falling back to default analyst plan.")
        # [RECOVERY] If JSON schema fails, force a safe default technical plan
        plan_obj = Plan(
            locale="en-US",
            has_enough_context=False,
            thought=f"Structural Failure Recovery: {str(e)[:100]}",
            title="Institutional Audit (Recovery)",
            steps=[Step(need_search=False, title="Technical Recovery Analysis", description=f"Perform core analysis for: {user_query}", step_type=StepType.ANALYST)]
        )
    
    # Guardrail: Force technical nodes if the model tries to answer deep questions directly
    if (not plan_obj.steps or plan_obj.has_enough_context) and is_technical:
        logger.warning("[VLI_SPINE] Guardrail: Forcing specialist step for technical query.")
        plan_obj.has_enough_context = False
        plan_obj.direct_response = ""
        plan_obj.steps = [Step(need_search=False, title="Institutional Audit", description=f"Extract metrics for {user_query}", step_type=StepType.ANALYST)]

    # Handle direct response from plan
    if plan_obj.has_enough_context or plan_obj.direct_response:
        resp = plan_obj.direct_response or f"Understood: {plan_obj.title}"
        return Command(
            update={"current_plan": plan_obj, "final_report": resp, "messages": [AIMessage(content=resp, name="vli")]},
            goto="__end__"
        )

    # 6. Dispatch to Router Logic
    logger.info(f"[VLI_SPINE] Dispatching Plan: {plan_obj.title} ({len(plan_obj.steps)} steps)")
    
    # We use the existing router_logic if possible, or just look at the first step
    # To maintain backward compatibility with the builder's conditional edges, we return the state
    # and let the builder's conditional router take over.
    next_agent = plan_obj.steps[0].step_type.value
    
    # If we need human feedback first
    if not state.get("is_test_mode", False) and not state.get("is_plan_approved", False):
        next_agent = "human_feedback"

    return Command(
        update={
            "current_plan": plan_obj, 
            "steps_completed": 0,
            "research_topic": plan_obj.title,
            "locale": plan_obj.locale
        },
        goto=next_agent
    )
