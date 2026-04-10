# Core: Common VLI - Shared node utilities and execution logic (V2 - Cache Buster).
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from datetime import datetime

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from src.agents import create_agent_from_registry
from src.config.configuration import Configuration
from src.tools import crawl_tool, get_stock_quote, get_web_search_tool, invalidate_market_cache, snapper
from src.tools.artifacts import read_session_artifact
from src.utils.vli_metrics import log_vli_metric

logger = logging.getLogger(__name__)


async def _setup_and_execute_agent_step(state, config, agent_type, tools, agent_instructions: str = ""):
    """Executes the agent and captures the result for the reporter."""

    # 1. Diagnostic Trace: Emit a lifecycle log for the terminal (but keep progress out of persistent history)
    logger.info(f"🚀 Specialist `{agent_type.upper()}` is now executing `{agent_instructions[:50]}...` (Fast-Path bypass enabled for efficiency).")

    agent = create_agent_from_registry(agent_type, tools)

    # [PERFORMANCE AUDIT] Track execution latency for the persistent store
    audit_start = datetime.now()
    try:
        # [RELIABILITY] Exponential Backoff for 429 Resource Exhausted errors
        # Gemini quotas can be tight; we wait between 4s and 60s for recovery.
        async for attempt in AsyncRetrying(wait=wait_exponential(multiplier=2, min=4, max=60), stop=stop_after_attempt(3), retry=retry_if_exception(lambda e: "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e)), reraise=True):
            with attempt:
                result = await agent.ainvoke(state, config)

        latency = (datetime.now() - audit_start).total_seconds()
        log_vli_metric(agent_type, latency, status="pass")
    except Exception as e:
        latency = (datetime.now() - audit_start).total_seconds()
        log_vli_metric(agent_type, latency, status="fail", metadata={"error": str(e)})
        logger.error(f"Agent `{agent_type}` failed after retries: {e}")
        raise e

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
        new_messages = [AIMessage(content=f"{agent_type.upper()} task completed successfully.", name=f"{agent_type}_finalize")]
    else:
        # Sign the last message from the agent to mark the turn as complete
        last_msg = new_messages[-1]

        # LangChain messages are often immutable, so we replace with a named copy for identity tracking
        if isinstance(last_msg, AIMessage):
            new_messages[-1] = AIMessage(content=last_msg.content, name=f"{agent_type}_finalize")
        elif hasattr(last_msg, "content"):
            content = last_msg.content
            if isinstance(content, list):
                new_messages[-1] = AIMessage(content=content, name=f"{agent_type}_finalize")
            else:
                new_messages[-1] = AIMessage(content=str(content), name=f"{agent_type}_finalize")
        else:
            # Absolute fallback: append a sentinel
            new_messages.append(AIMessage(content="Step complete.", name=f"{agent_type}_finalize"))

    # Hub-and-Spoke Routing Logic: Always return to the coordinator if a plan is in progress
    if current_plan:
        goto_node = "coordinator"
    elif state.get("is_test_mode", False) or state.get("test_mode", False):
        goto_node = "coordinator"

    return {"messages": new_messages, "observations": observations, "current_plan": current_plan}


# Orchestrator Fast Bypass Tools
def get_orchestrator_tools(config: RunnableConfig):
    """Returns a list of tools available to the Orchestrator for fast bypass."""
    from src.tools import get_brokerage_accounts, get_brokerage_balance, get_attribution_summary, get_daily_blotter, get_personal_risk_metrics, get_brokerage_statements, fetch_market_macros

    configurable = Configuration.from_runnable_config(config)
    return [
        get_stock_quote,
        invalidate_market_cache,
        get_web_search_tool(configurable.max_search_results),
        crawl_tool,
        snapper,
        get_brokerage_accounts,
        get_brokerage_balance,
        get_attribution_summary,
        get_daily_blotter,
        get_personal_risk_metrics,
        get_brokerage_statements,
        fetch_market_macros,
        read_session_artifact,
    ]
