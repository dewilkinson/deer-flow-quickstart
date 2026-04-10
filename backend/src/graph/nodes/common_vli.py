# Core: Common VLI - Shared node utilities and execution logic (V2 - Cache Buster).
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import asyncio
import logging
import time
from datetime import datetime

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from src.agents import create_agent_from_registry
from src.config.configuration import Configuration
from src.tools import crawl_tool, get_stock_quote, get_web_search_tool, invalidate_market_cache, snapper
from src.tools.artifacts import read_session_artifact
from src.config.vli import get_vli_path
from src.utils.vli_metrics import log_vli_metric

logger = logging.getLogger(__name__)


async def _run_node_with_tiered_fallback(agent_type, state, config, tools=None, is_structured=False, structured_schema=None, messages=None):
    """Universal tiered fallback executor for all VLI nodes."""
    from src.config.agents import AGENT_LLM_MAP
    from src.llms.llm import get_llm_by_type

    tiers = ["reasoning", "basic", "legacy"]
    current_tier = AGENT_LLM_MAP.get(agent_type, "basic")
    
    try:
        start_idx = tiers.index(current_tier)
    except ValueError:
        start_idx = 1
        
    fallback_messages = []
    result = None

    for i in range(start_idx, len(tiers)):
        tier = tiers[i]
        AGENT_LLM_MAP[agent_type] = tier
        
        # Re-initialize based on tier
        if tools:
            if is_structured and structured_schema:
                llm = get_llm_by_type(tier)
                runnable = llm.bind_tools(tools).with_structured_output(structured_schema)
            else:
                runnable = create_agent_from_registry(agent_type, tools)
        else:
            runnable = get_llm_by_type(tier)

        # Execution
        t0 = time.time()
        # [PERFORMANCE] Set aggressive timeouts to survive reasoning stalls and force basic/legacy rotation
        tier_timeouts = {
            "reasoning": 4.0,
            "basic": 40.0,
            "legacy": 40.0
        }
        tier_timeout = tier_timeouts.get(tier, 45)
        logger.info(f"[TIMING] Tier {tier} ({agent_type}) started (Internal Timeout: {tier_timeout}s).")
        
        try:
            if messages is not None:
                result = await asyncio.wait_for(asyncio.to_thread(runnable.invoke, messages), timeout=tier_timeout)
            else:
                if is_structured:
                    st_llm = runnable.with_structured_output(structured_schema)
                    result = await asyncio.wait_for(asyncio.to_thread(st_llm.invoke, state), timeout=tier_timeout)
                else:
                    result = await asyncio.wait_for(asyncio.to_thread(runnable.invoke, state), timeout=tier_timeout)
            
            # [PROMPT LEAKAGE GUARD] Detect if the model is echoing its own instructions/security protocol
            res_str = str(result).upper()
            leak_keywords = ["# SECURITY OVERRIDE", "APEX 500 SYSTEM", "SYSTEM INSTRUCTION", "USER OVERRIDE DIRECTIVE", "OPERATIONAL MANDATE"]
            is_leak = any(x in res_str for x in leak_keywords)
            
            # Deep check for list of messages
            if not is_leak and isinstance(result, list):
                for item in result:
                    if any(x in str(item).upper() for x in leak_keywords):
                        is_leak = True
                        break
            
            if (is_structured and isinstance(result, list)) or is_leak:
                logger.error(f"[VLI_INTEGRITY_FAIL] Tier {tier} for {agent_type} returned malformed output or prompt leakage. Forcing rotation.")
                if i < len(tiers) - 1:
                    next_tier = tiers[i+1]
                    msg = f"[SYSTEM]: Integrity check failed on {tier} (Instruction Leak). Falling back to {next_tier}..."
                    fallback_messages.append(AIMessage(content=msg, name="system_fallback"))
                    continue
                else:
                    raise TypeError(f"Agent Intelligence Failure: Structural validation failed on all tiers.")
                
            logger.info(f"[TIMING] Tier {tier} ({agent_type}) finished in {time.time() - t0:.2f}s.")
            return result, fallback_messages
        except Exception as e:
            logger.error(f"[VLI_TIER_FAIL] Tier {tier} failed after {time.time() - t0:.2f}s: {e}")
            e_str = str(e).upper()
            is_quota = any(x in e_str for x in ["RESOURCE_EXHAUSTED", "429", "QUOTA", "LIMIT", "EXHAUSTED", "RATE_LIMIT", "TIMEOUT", "CANCELLED"])
            
            if is_quota:
                try:
                    actual_model = getattr(runnable, 'model_name', getattr(runnable, 'model', f"Gemini {tier}"))
                except:
                    actual_model = f"Gemini {tier}"
                
                # Prettify the model name
                if "3.1" in actual_model.lower() or "pro" in actual_model.lower() or tier == "reasoning":
                    actual_model = "Gemini 3 Pro"
                elif "flash" in actual_model.lower() or tier in ["basic", "core", "reporter"]:
                    actual_model = "Gemini Flash"
                    
                fail_msg = f"RESOURCE_EXHAUSTED: Quota limit reached for {actual_model}."
                logger.warning(fail_msg)
                
                # [AUDIT] Log explicit failure to active telemetry file
                try:
                    from src.config.vli import get_vli_path
                    telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
                    timestamp = datetime.now().strftime("[%H:%M:%S]")
                    with open(telemetry_file, "a", encoding="utf-8") as tf:
                        tf.write(f"\n{timestamp} **QUOTA EXHAUSTED:** Agent `{agent_type}` (Tier: `{tier}`). Fallback loop specifically disabled by user.\n")
                        tf.flush()
                except:
                    pass

                if is_structured:
                    error_res = {"thought": fail_msg, "has_enough_context": True, "direct_response": fail_msg, "title": "Quota Failure", "steps": []}
                else:
                    error_res = AIMessage(content=fail_msg, name="system_fallback_error")
                
                return error_res, fallback_messages
            else:
                # [RELIABILITY] Final tier failure sentinel
                if is_quota:
                     fail_msg = f"CRITICAL: All available Gemini tiers are currently exhausted (Reasoning, Basic, and Legacy). Please verify your Google Cloud Quota or wait for the reset period."
                     fallback_messages.append(AIMessage(content=f"[SYSTEM]: Full Pipeline Quota Exhausted.", name="system_fallback"))
                     
                     if is_structured and structured_schema:
                         # Return a dummy object that satisfies basic schema expectations if possible
                         try:
                             # Try to instantiate the Pydantic model with fallback values
                             error_res = structured_schema(
                                 locale="en-US",
                                 thought=fail_msg,
                                 has_enough_context=True,
                                 direct_response=fail_msg,
                                 title="Quota Failure",
                                 steps=[]
                             )
                         except Exception:
                             # Fallback to dict if Pydantic instantiation fails (e.g. schema mismatch)
                             error_res = {"thought": fail_msg, "has_enough_context": True, "direct_response": fail_msg, "title": "Quota Failure", "steps": []}
                     else:
                         error_res = AIMessage(content=fail_msg, name="system_fallback_error")
                     
                     return error_res, fallback_messages
                raise e
    return result, fallback_messages


async def _setup_and_execute_agent_step(state, config, agent_type, tools, agent_instructions: str = ""):
    """Executes the agent and captures the result for the reporter with multi-tier fallback."""
    logger.info(f"🚀 Specialist `{agent_type.upper()}` is now executing `{agent_instructions[:50]}...` (Tiered Fallback Active).")

    audit_start = datetime.now()
    try:
        result, fallback_messages = await _run_node_with_tiered_fallback(agent_type, state, config, tools=tools)
        latency = (datetime.now() - audit_start).total_seconds()
        from src.config.agents import AGENT_LLM_MAP
        log_vli_metric(agent_type, latency, status="pass", metadata={"tier": AGENT_LLM_MAP[agent_type]})
    except Exception as e:
        latency = (datetime.now() - audit_start).total_seconds()
        log_vli_metric(agent_type, latency, status="fail", metadata={"error": str(e)})
        logger.error(f"Agent `{agent_type}` failed after tiered fallback: {e}")
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
    
    if current_plan:
        steps = []
        if hasattr(current_plan, "steps"):
            steps = current_plan.steps
        elif isinstance(current_plan, dict) and "steps" in current_plan:
            steps = current_plan["steps"]

        for step in steps:
            if hasattr(step, "execution_res"):
                if getattr(step, "execution_res") is None:
                    setattr(step, "execution_res", last_content or "Executed.")
                    break
            elif isinstance(step, dict) and step.get("execution_res") is None:
                step["execution_res"] = last_content or "Executed."
                break

    # Ensure all messages from the agent are "Signed"
    new_messages = result.get("messages", []) if isinstance(result, dict) else []
    if not new_messages:
        new_messages = [AIMessage(content=f"{agent_type.upper()} task completed successfully.", name=f"{agent_type}_finalize")]
    else:
        last_msg = new_messages[-1]
        if isinstance(last_msg, AIMessage):
            new_messages[-1] = AIMessage(content=last_msg.content, name=f"{agent_type}_finalize")
        elif hasattr(last_msg, "content"):
            content = last_msg.content
            new_messages[-1] = AIMessage(content=content if isinstance(content, list) else str(content), name=f"{agent_type}_finalize")
        else:
            new_messages.append(AIMessage(content="Step complete.", name=f"{agent_type}_finalize"))

    return {"messages": fallback_messages + new_messages, "observations": observations, "current_plan": current_plan}


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
