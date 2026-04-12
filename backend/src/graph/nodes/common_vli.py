# Core: Common VLI - Shared node utilities and execution logic (V2 - Cache Buster).
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import asyncio
import logging
import time
import traceback
from datetime import datetime

from langchain_core.messages import AIMessage, SystemMessage
from src.llms.llm import get_llm_by_type
from langchain_core.runnables import RunnableConfig
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from src.agents import create_agent_from_registry
from src.config.configuration import Configuration
from src.tools import crawl_tool, get_stock_quote, get_web_search_tool, invalidate_market_cache, snapper
from src.tools.artifacts import read_session_artifact
from src.config.vli import get_vli_path
from src.utils.vli_metrics import log_vli_metric
from src.config.agents import AGENT_LLM_MAP

logger = logging.getLogger(__name__)

# [TIER_CONSTANTS] Global list of Gemini tiers for execution
TIERS = ["reasoning", "basic", "legacy"]


async def _run_node_with_tiered_fallback(agent_type, state, config, tools=None, is_structured=False, structured_schema=None, messages=None):
    """Universal tiered fallback executor for all VLI nodes."""
    current_tier = AGENT_LLM_MAP.get(agent_type, "basic")
    
    try:
        start_idx = TIERS.index(current_tier)
    except ValueError:
        start_idx = 1
        
    fallback_messages = []
    result = None

    for i in range(start_idx, len(TIERS)):
        tier = TIERS[i]
        AGENT_LLM_MAP[agent_type] = tier
        
        # Re-initialize based on tier
        is_graph = False
        if tools:
            if is_structured and structured_schema:
                llm = get_llm_by_type(tier)
                runnable = llm.bind_tools(tools).with_structured_output(structured_schema)
            else:
                runnable = create_agent_from_registry(agent_type, tools)
                is_graph = True
        else:
            runnable = get_llm_by_type(tier)

        # Execution
        t0 = time.time()
        
        # [DYNAMIC BUDGET] Calculate remaining global time relative to 115s server limit
        configurable = config.get("configurable", {})
        execution_start_time = configurable.get("execution_start_time", t0)
        elapsed_global = time.time() - execution_start_time
        remaining_global = 110.0 - elapsed_global # Use 110s to leave buffer
        
        tier_timeouts = {
            "reasoning": 40.0,
            "basic": 35.0,
            "legacy": 30.0
        }
        
        # [ADAPTIVE SKIP] If reasoning is requested but we have < 30s left, skip to basic
        if tier == "reasoning" and remaining_global < 30.0:
            logger.warning(f"[BUDGET_ENFORCEMENT] Skipping Reasoning tier (Remaining: {remaining_global:.1f}s < 30s).")
            # Inject Adaptive Verbosity logic into the prompt history for the fallback model
            if messages is not None:
                if is_structured:
                    # For structured output (like Phase B Coordinator), avoid narrative instructions which break JSON parsing
                    messages.append(SystemMessage(content="[BUDGET_CONSTRAINED]: Maintain valid JSON Plan output, but ensure the 'thought' and 'description' fields are highly detailed."))
                else:
                    # For text/graph nodes (Synthesizer, Reporter), go full depth
                    messages.append(SystemMessage(content="[BUDGET_RECOVERY_MODE]: You have been promoted to the immediate execution tier due to time constraints. You MUST provide a full, high-fidelity institutional answer immediately. Do NOT sacrifice depth for brevity."))
            continue
            
        # Hard-cap the tier timeout by the remaining global budget
        static_timeout = tier_timeouts.get(tier, 110.0)
        tier_timeout = min(static_timeout, max(5.0, remaining_global))
        
        # [TRACE] High-fidelity diagnostic probe
        state_size = len(str(state))
        msgs_size = len(str(messages)) if messages is not None else 0
        logger.info(f"[TRACE_START] Tier: {tier} | Agent: {agent_type} | State: {state_size} | Msgs: {msgs_size} | Timeout: {tier_timeout:.1f}s (Global Remaining: {remaining_global:.1f}s)")
        
        try:
            if messages is not None:
                if is_graph:
                    # Agent graph needs dict payload
                    result = await asyncio.wait_for(runnable.ainvoke({"messages": messages}), timeout=tier_timeout)
                    if isinstance(result, dict) and "messages" in result and result["messages"]:
                        result = result["messages"][-1]
                else:
                    result = await asyncio.wait_for(runnable.ainvoke(messages), timeout=tier_timeout)
            else:
                if is_structured:
                    st_llm = runnable.with_structured_output(structured_schema)
                    result = await asyncio.wait_for(st_llm.ainvoke(state), timeout=tier_timeout)
                else:
                    result = await asyncio.wait_for(runnable.ainvoke(state), timeout=tier_timeout)
                    if isinstance(result, dict) and "messages" in result and result["messages"]:
                        result = result["messages"][-1]
            
            # [PROMPT LEAKAGE GUARD] Detect if the model is echoing its own instructions/security protocol
            res_str = str(result).upper()
            if hasattr(result, "content") and result.content:
                res_str += " " + str(result.content).upper()
            leak_keywords = ["# SECURITY OVERRIDE", "[APEX 500 SYSTEM]", "[SYSTEM INSTRUCTION]", "[USER OVERRIDE DIRECTIVE]", "[OPERATIONAL MANDATE]"]
            is_leak = False
            for x in leak_keywords:
                if x in res_str:
                    logger.warning(f"[LEAK_DEBUG] Detected keyword '{x}' in response context.")
                    is_leak = True
                    break
            
            # Deep check for list of messages
            if not is_leak and isinstance(result, list):
                for item in result:
                    for x in leak_keywords:
                        if x in str(item).upper():
                            logger.warning(f"[LEAK_DEBUG] Detected keyword '{x}' in message item.")
                            is_leak = True
                            break
                    if is_leak:
                        break
            
            duration = time.time() - t0
            logger.info(f"[TRACE_END] Tier: {tier} | Status: {'LEAK' if is_leak else 'OK'} | Duration: {duration:.2f}s")
            
            if (is_structured and isinstance(result, list)) or is_leak:
                if i < len(TIERS) - 1:
                    next_tier = TIERS[i+1]
                    msg = f"STRUCTURAL_EXCEPTION: Integrity check failed on {tier} (Instruction Leak). Falling back to {next_tier}..."
                    fallback_messages.append(AIMessage(content=msg, name="system_fallback"))
                    continue
                else:
                    raise TypeError(f"Agent Intelligence Failure: Structural validation failed on all tiers.")
                
            logger.info(f"[TIMING] Tier {tier} ({agent_type}) finished in {time.time() - t0:.2f}s.")
            if hasattr(result, "additional_kwargs"):
                result.additional_kwargs["duration_secs"] = time.time() - t0
            return result, fallback_messages
        except Exception as e:
            if isinstance(e, asyncio.TimeoutError):
                logger.error(f"[VLI_TIER_FAIL] Tier {tier} timed out after {tier_timeout:.2f}s")
                fallback_messages.append(SystemMessage(content=f"[TIER_{tier.upper()}_TIMEOUT] Try a fallback reasoning strategy."))
                
                # [NEW] Telemetry Injection for Visibility
                try:
                    telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
                    timestamp = datetime.now().strftime("[%H:%M:%S]")
                    with open(telemetry_file, "a", encoding="utf-8") as tf:
                        tf.write(f"\n{timestamp} **TIER_STALL:** Tier `{tier.upper()}` timed out ({tier_timeout}s). Rotating to next availability.\n")
                        tf.flush()
                except:
                    pass
            else:
                logger.error(f"[VLI_TIER_FAIL] Tier {tier} failed after {time.time() - t0:.2f}s: {e}")
                logger.error("".join(traceback.format_tb(e.__traceback__)))
                fallback_messages.append(SystemMessage(content=f"[TIER_{tier.upper()}_FAILURE] Error: {e}. Adjust approach and try fallback tier."))
            
            e_str = (str(e) + " " + e.__class__.__name__).upper()
            is_quota = any(x in e_str for x in ["RESOURCE_EXHAUSTED", "429", "QUOTA_EXHAUSTED", "RATE_LIMIT"])
            
            if is_quota:
                try:
                    tmp_llm = get_llm_by_type(tier)
                    actual_model = getattr(tmp_llm, 'model_name', getattr(tmp_llm, 'model', f"Gemini {tier}"))
                except Exception:
                    actual_model = getattr(runnable, 'model_name', getattr(runnable, 'model', f"Gemini {tier}"))
                
                model_str = str(actual_model).lower()
                
                # [UI] Prettify the model name for the dashboard warning
                if "gemini-3" in model_str:
                    actual_model = "Gemini 3 Pro" if "pro" in model_str else "Gemini 3 Flash"
                elif "3" in model_str and "flash" in model_str:
                    actual_model = "Gemini 3 Flash"
                elif "3.1" in model_str or "pro" in model_str:
                    actual_model = "Gemini 3 Pro"
                elif "flash" in model_str or tier in ["basic", "core", "reporter"]:
                    actual_model = "Gemini Flash"
                    
                fail_msg = f"QUOTA_EXHAUSTED: Quota limit reached for {actual_model}."
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
 
                if is_structured and structured_schema:
                    try:
                        error_res = structured_schema(
                            locale="en-US",
                            thought=fail_msg,
                            has_enough_context=True,
                            direct_response=fail_msg,
                            title="Quota Failure",
                            steps=[]
                        )
                    except Exception:
                        error_res = {"thought": fail_msg, "has_enough_context": True, "direct_response": fail_msg, "title": "Quota Failure", "steps": []}
                else:
                    error_res = AIMessage(content=fail_msg, name="system_fallback_error")
                
                return error_res, fallback_messages
            else:
                # [RELIABILITY] Final tier failure sentinel
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
            if (isinstance(content, (dict, list))) and not isinstance(content, list):
                 import json
                 content_str = f"```json\n{json.dumps(content, indent=2)}\n```"
            elif isinstance(content, list):
                 # Flatten list of content blocks if needed
                 content_parts = []
                 for item in content:
                     if isinstance(item, dict) and "text" in item:
                         content_parts.append(str(item["text"]))
                     else:
                         content_parts.append(str(item))
                 content_str = "\n".join(content_parts)
            else:
                 content_str = str(content)
            
            new_messages[-1] = AIMessage(content=content_str, name=f"{agent_type}_finalize")
        else:
            new_messages.append(AIMessage(content="Step complete.", name=f"{agent_type}_finalize"))

    return {"messages": fallback_messages + new_messages, "observations": observations, "current_plan": current_plan}


def _compact_history(messages: list) -> list:
    """
    Compacts message history for synthesis.
    Filters out structural planning messages to provide a clean context for the reporter.
    """
    compacted = []
    # Nodes whose messages should be ignored in final narrative synthesis EXCEPT when they hold result logic
    structural_nodes = ["vli_spine", "system", "vli_parser", "parser"]
    
    # [HARDENING] We keep 'coordinator' and 'vli_coordinator' if they were the final node or contain _finalize suffix
    # because they often hold the entire analytical payload in Fast-Path scenarios.
    
    for m in messages:
        name = getattr(m, "name", "") or ""
        
        # 1. Skip strictly structural nodes
        if name in structural_nodes:
            continue
            
        # 2. Skip 'coordinator' if it's just a planning stage and NOT a finalization
        if name in ["coordinator", "vli_coordinator"]:
            content = str(getattr(m, "content", ""))
            # If it's the very last message in the set, we must keep it (it's the answer)
            if m == messages[-1]:
                 pass # Keep
            # If it looks like a planning object (contains internal braces or keys), skip it
            elif "{" in content and "steps" in content:
                 continue
            
        compacted.append(m)
    return compacted


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
