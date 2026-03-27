# Agent: Orchestrator - Main state machine and node definitions.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import json

import logging
import os
from typing import Annotated, Literal, Dict, Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.types import Command, interrupt

from src.agents import create_agent, create_agent_from_registry
from src.config.agents import AGENT_LLM_MAP
from src.config.configuration import Configuration
from src.llms.llm import get_llm_by_type
from src.prompts.planner_model import Plan
from src.prompts.template import apply_prompt_template
from src.tools import (
    crawl_tool,
    python_repl_tool,
    get_web_search_tool,
    snapper,
    get_retriever_tool,
    get_stock_quote,
    get_brokerage_accounts,
    get_brokerage_history,
    get_brokerage_balance,
    get_brokerage_statements,
    write_daily_journal,
    list_journal_entries,
    read_journal_entry,
    get_journal_folder,
    set_journal_folder,
    get_smc_analysis,
    get_ema_analysis,
    get_rsi_analysis,
    get_macd_analysis,
    get_volatility_atr,
    get_volume_profile,
    get_bollinger_bands,
    get_symbol_history_data
)
from src.tools.research import RULES as RESEARCH_RULES

from src.config.analyst import get_analyst_keywords
from src.utils.json_utils import repair_json_output
from .types import State
from src.tools.shared_storage import (
    SCOUT_CONTEXT, ANALYST_CONTEXT,
    JOURNALER_CONTEXT, CODER_CONTEXT, ORCHESTRATOR_CONTEXT,
    GENERAL_CONTEXT
)

logger = logging.getLogger(__name__)

# Node Private Contexts (Persistent across calls to the same node in this process)
_RESEARCHER_NODE_CONTEXT: Dict[str, Any] = {}
_ANALYST_NODE_CONTEXT: Dict[str, Any] = {}
_CODER_NODE_CONTEXT: Dict[str, Any] = {}
_SCOUT_NODE_CONTEXT: Dict[str, Any] = {}
_JOURNALER_NODE_CONTEXT: Dict[str, Any] = {}
_IMAGING_NODE_CONTEXT: Dict[str, Any] = {}
_PARSER_NODE_CONTEXT: Dict[str, Any] = {}
_COORDINATOR_NODE_CONTEXT: Dict[str, Any] = {}

def _clear_context(context: dict):
    """Effectively 'destroys' the context by clearing it, preparing for a new session."""
    context.clear()


async def parser_node(state: State, config: RunnableConfig) -> Command[Literal["coordinator", "reporter", "__end__"]]:
    """Parser node (VibeLink Interface) - Initial Input Processor."""
    logger.info("VLI Parser is processing user vibe.")
    
    # 1. Private to the Agent Code Itself
    _NODE_RESOURCE_CONTEXT = _PARSER_NODE_CONTEXT
    # 2. Shared context: Persistent, shared by agents of the SAME type
    _SHARED_RESOURCE_CONTEXT = ORCHESTRATOR_CONTEXT
    # 3. Global context: Shared across all agent types
    _GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

    configurable = Configuration.from_runnable_config(config)
    tools = get_orchestrator_tools(config)
    
    llm = get_llm_by_type(AGENT_LLM_MAP.get("parser", "basic"))
    # Bind tools for potential bypass
    llm_with_tools = llm.bind_tools(tools)
    structured_llm = llm_with_tools.with_structured_output(Plan)

    messages = apply_prompt_template("parser", state)
    
    response = structured_llm.invoke(messages)
    plan_obj = response
    
    if plan_obj.has_enough_context or plan_obj.direct_response:
        return Command(
            update={
                "current_plan": plan_obj,
                "locale": plan_obj.locale,
                "final_report": plan_obj.direct_response or "",
                "messages": [AIMessage(content=str(plan_obj), name="vli_parser")]
            },
            goto="reporter",
        )
    return Command(
        update={
            "current_plan": plan_obj,
            "locale": plan_obj.locale,
            "research_topic": plan_obj.title,
        },
        goto="coordinator",
    )

def coordinator_node(state: State, config: RunnableConfig) -> Command[Literal["human_feedback", "reporter", "__end__"]]:
    """Coordinator node - Detailed multi-step planning."""
    logger.info("VLI Coordinator is planning execution.")

    # 1. Private to the Agent Code Itself
    _NODE_RESOURCE_CONTEXT = _COORDINATOR_NODE_CONTEXT
    # 2. Shared context: Persistent, shared by agents of the SAME type
    _SHARED_RESOURCE_CONTEXT = ORCHESTRATOR_CONTEXT
    # 3. Global context: Shared across all agent types
    _GLOBAL_RESOURCE_CONTEXT = GENERAL_CONTEXT

    analyst_keywords = ", ".join(get_analyst_keywords())
    state_for_prompt = {**state, "ANALYST_KEYWORDS": analyst_keywords}
    
    messages = apply_prompt_template("coordinator", state_for_prompt)
    
    llm = get_llm_by_type(AGENT_LLM_MAP.get("coordinator", "reasoning"))
    tools = get_orchestrator_tools(config)
    llm_with_tools = llm.bind_tools(tools)
    structured_llm = llm_with_tools.with_structured_output(Plan)
    
    plan_obj = structured_llm.invoke(messages)
    return Command(
        update={
            "current_plan": plan_obj,
            "messages": [AIMessage(content=str(plan_obj), name="vli_coordinator")]
        },
        goto="human_feedback",
    )

def human_feedback_node(state: State) -> Command[Literal["parser", "reporter", "researcher", "coder", "scout", "journaler", "analyst", "imaging", "__end__"]]:

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

async def _setup_and_execute_agent_step(state, config, agent_type, tools):
    """Executes the agent and captures the result for the reporter."""
    agent = create_agent_from_registry(agent_type, tools)
    configurable = Configuration.from_runnable_config(config)
    
    # For simulation/test harness, we can mock the interaction if needed, 
    # but here we actually engage the agent.
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

async def researcher_node(state: State, config: RunnableConfig):
    # 1. Private to the Agent Code Itself
    _NODE_RESOURCE_CONTEXT = _RESEARCHER_NODE_CONTEXT
    # 2. Shared context: Persistent, shared by agents of the SAME type
    _SHARED_RESOURCE_CONTEXT = ANALYST_CONTEXT
    # 3. Global context: Shared across all agent types
    _GLOBAL_RESOURCE_CONTEXT = GENERAL_CONTEXT

    configurable = Configuration.from_runnable_config(config)
    
    # Initialize private data storage (macro_history) upon "spinup" if not already present.
    if not state.get("macro_history"):
        logger.info("Research Node: Initializing private macro history storage.")
        try:
            macro_data = await get_symbol_history_data.ainvoke({
                "symbols": RESEARCH_RULES["MACRO_SET"],
                "period": RESEARCH_RULES["DEFAULT_LOOKBACK"],
                "interval": RESEARCH_RULES["DEFAULT_INTERVAL"]
            })
            state["macro_history"] = macro_data
        except Exception as e:
            logger.error(f"Failed to initialize Research macro history: {e}")

    tools = [
        get_web_search_tool(configurable.max_search_results), 
        crawl_tool,
        snapper,
        get_stock_quote, 
        fetch_market_macros,
        get_smc_analysis, 
        get_ema_analysis, 
        get_rsi_analysis, 
        get_macd_analysis,
        get_volatility_atr, 
        get_volume_profile, 
        get_bollinger_bands
    ]

    return await _setup_and_execute_agent_step(state, config, "researcher", tools)


async def coder_node(state: State, config: RunnableConfig):
    # 1. Private to the Agent Code Itself
    _NODE_RESOURCE_CONTEXT = _CODER_NODE_CONTEXT
    # 2. Shared context: Persistent, shared by agents of the SAME type
    _SHARED_RESOURCE_CONTEXT = CODER_CONTEXT
    # 3. Global context: Shared across all agent types
    _GLOBAL_RESOURCE_CONTEXT = GENERAL_CONTEXT

    return await _setup_and_execute_agent_step(state, config, "coder", [python_repl_tool])


async def scout_node(state: State, config: RunnableConfig):
    # 1. Private to the Agent Code Itself
    _NODE_RESOURCE_CONTEXT = _SCOUT_NODE_CONTEXT
    # 2. Shared context: Persistent, shared by agents of the SAME type
    _SHARED_RESOURCE_CONTEXT = SCOUT_CONTEXT
    # 3. Global context: Shared across all agent types
    _GLOBAL_RESOURCE_CONTEXT = GENERAL_CONTEXT

    configurable = Configuration.from_runnable_config(config)
    tools = [
        get_brokerage_accounts, 
        get_brokerage_history, 
        get_brokerage_balance, 
        get_brokerage_statements, 
        get_stock_quote,
        get_web_search_tool(configurable.max_search_results),
        crawl_tool,
        snapper,
    ]

    return await _setup_and_execute_agent_step(state, config, "scout", tools)

# Orchestrator Fast Bypass Tools
def get_orchestrator_tools(config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    return [
        get_stock_quote,
        get_web_search_tool(configurable.max_search_results),
        crawl_tool,
        snapper
    ]

async def journaler_node(state: State, config: RunnableConfig):
    # 1. Private to the Agent Code Itself
    _NODE_RESOURCE_CONTEXT = _JOURNALER_NODE_CONTEXT
    # 2. Shared context: Persistent, shared by agents of the SAME type
    _SHARED_RESOURCE_CONTEXT = JOURNALER_CONTEXT
    # 3. Global context: Shared across all agent types
    _GLOBAL_RESOURCE_CONTEXT = GENERAL_CONTEXT

    # Journaler handles Obsidian note taking and trading logs
    tools = [write_daily_journal, list_journal_entries, read_journal_entry, get_journal_folder, set_journal_folder, get_brokerage_history, get_stock_quote]

    return await _setup_and_execute_agent_step(state, config, "journaler", tools)


async def analyst_node(state: State, config: RunnableConfig):
    # 1. Private to the Agent Code Itself
    _NODE_RESOURCE_CONTEXT = _ANALYST_NODE_CONTEXT
    # 2. Shared context: Persistent, shared by agents of the SAME type
    _SHARED_RESOURCE_CONTEXT = ANALYST_CONTEXT
    # 3. Global context: Shared across all agent types
    _GLOBAL_RESOURCE_CONTEXT = GENERAL_CONTEXT

    tools = [get_smc_analysis, get_ema_analysis, get_stock_quote, get_rsi_analysis, get_macd_analysis, get_volatility_atr, get_volume_profile, get_bollinger_bands]

    return await _setup_and_execute_agent_step(state, config, "analyst", tools)

async def imaging_node(state: State, config: RunnableConfig):
    # 1. Private to the Agent Code Itself
    _NODE_RESOURCE_CONTEXT = _IMAGING_NODE_CONTEXT
    # 2. Shared context: Persistent, shared by agents of the SAME type
    _SHARED_RESOURCE_CONTEXT = ANALYST_CONTEXT  # Imaging is part of Analyst flow
    # 3. Global context: Shared across all agent types
    _GLOBAL_RESOURCE_CONTEXT = GENERAL_CONTEXT

    configurable = Configuration.from_runnable_config(config)
    # Imaging handles charts and visual data
    tools = [get_stock_quote, get_smc_analysis, get_web_search_tool(configurable.max_search_results), python_repl_tool]

    return await _setup_and_execute_agent_step(state, config, "imaging", tools)

def reporter_node(state: State, config: RunnableConfig):
    return {"final_report": "Analysis synthesis completed."}

def background_investigation_node(state: State, config: RunnableConfig): pass
def planner_node(state: State, config: RunnableConfig): pass
def research_team_node(state: State): pass
