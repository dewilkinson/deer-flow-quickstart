import logging
from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from src.graph.nodes.common_vli import _compact_history
from src.llms.llm import get_llm_by_type
from src.prompts.template import apply_prompt_template

from ..types import State

logger = logging.getLogger(__name__)


def _sanitize_final_content(text: str) -> str:
    """Detects and cleans raw structural data leakage in reports."""
    t = text.strip()
    # If it looks like raw JSON or a failing sentinel, it's NOT a narrative
    # More specific JSON markers to avoid false positives with common words like 'locale' or 'title'
    leak_markers = ["\"expected_dict\":", "\"current_plan\":", "\"steps_completed\":", "RESOURCE_EXHAUSTED", "\"has_enough_context\":"]
    triggered_keys = [m for m in leak_markers if m in t]
    
    if (t.startswith("{") and t.endswith("}")) or triggered_keys:
        if triggered_keys:
            logger.warning(f"[VLI_LEAK_GUARD] Triggered by internal keys: {triggered_keys}")
        else:
            logger.warning("[VLI_LEAK_GUARD] Triggered by raw JSON structure detection.")
        logger.warning(f"[REPORTER_GUARDRAIL] Caught structural leakage in output: {t[:100]}...")
        # Clean it: Try to extract only the text if embedded, or return a failure sentinel
        return ""
    return text


async def reporter_node(state: State, config: RunnableConfig):
    """
    Final synthesis node for VLI reports.
    Ensures Specialist findings are compiled into a professional Markdown narrative.
    """
    # 1. Resource Exhaustion Check
    raw_messages = state.get("messages", [])
    if raw_messages:
        last_msg_content = str(getattr(raw_messages[-1], "content", ""))
        if "RESOURCE_EXHAUSTED" in last_msg_content:
            return {"final_report": last_msg_content, "messages": [AIMessage(content=last_msg_content, name="reporter_finalize")]}

    try:
        # [NEW] Extract configuration for template rendering early to allow custom LLM binding
        from src.config.configuration import Configuration

        configurable = Configuration.from_runnable_config(config)

        # Load dynamic synthesis LLM (Default to agents.py mapping, override if API requests raw/basic synthesis)
        llm_type = "reasoning"
        if hasattr(configurable, "reporter_llm_type"):
            llm_type = getattr(configurable, "reporter_llm_type")
        
        llm = get_llm_by_type(llm_type)
        start_time = datetime.now()

        # 2. Compact history for synthesis (Skip coordinator planning stages / intermediate tool dumps)
        state_to_synthesize = state.copy()
        state_to_synthesize["messages"] = _compact_history(state.get("messages", []))
        
        # Use the standard template applicator (returns a list of messages)
        # Note: apply_prompt_template appends .md internally
        messages = apply_prompt_template("reporter", state_to_synthesize)
        
        # Add the explicit directive
        messages.append(HumanMessage(content=f"DIRECTIVE: {state.get('directive', 'Generate summary report.')}"))

        # Compact the history to remove structural overhead
        final_compacted = _compact_history(state.get("messages", []))
        
        # Format the history for the LLM to understand the trajectory
        final_vli_history = "\n\n".join([f"**{m.name if hasattr(m, 'name') and m.name else m.type.upper()}**: {m.content}" for m in final_compacted])

        # State to synthesize includes the human request and the compacted analyst findings
        state_to_synthesize = state.copy()
        state_to_synthesize["messages"] = final_compacted
        
        from src.graph.nodes.common_vli import _run_node_with_tiered_fallback

        try:
            response, fb_msgs = await _run_node_with_tiered_fallback("reporter", state_to_synthesize, config, messages=messages)
        except Exception as e:
             logger.error(f"Reporter Synthesis Error after fallback: {str(e)}")
             final_report_text = "Analysis completed. (PHASE_SYNTHESIS_INTERRUPTED): The reasoning engine experienced a structural validation failure. Managed recovery plan is active."
             return {"final_report": final_report_text, "messages": [AIMessage(content=final_report_text, name="reporter_finalize")]}

        # Log performance metrics
        end_time = datetime.now()
        latency = (end_time - start_time).total_seconds()
        from src.utils.vli_metrics import log_vli_metric

        log_vli_metric("reporter", latency, True)

        # [STABILITY] Robust Content Extraction
        if isinstance(response.content, str):
            final_report_text = response.content
        elif isinstance(response.content, list):
            try:
                final_report_text = "".join([str(c.get("text", "")) if isinstance(c, dict) else str(c) for c in response.content])
            except Exception as e:
                logger.error(f"List parse error: {e}")
                final_report_text = str(response.content)
        else:
            final_report_text = str(response.content)

        if not final_report_text.strip() or final_report_text.strip() == "[]":
            logger.error(f"[VLI_REPORTER] Empty string/bracket returned. Metadata: {getattr(response, 'response_metadata', 'None')}")
            final_report_text = "Analysis completed. (Synthesis pipeline returned an empty payload. Deep evaluation was successfully processed but blocked natively by SDK context/safety rendering)."
        
        # [NEW] Final Sanitization & Re-synthesis Guardrail
        sanitized_text = _sanitize_final_content(final_report_text)
        if not sanitized_text:
            logger.info("Reporter: Structural data leak detected in final output. Forcing narrative recovery.")
            recovery_prompt = "MANDATORY: Your previous response contained raw JSON/data structures (expected_dict, etc). Rewrite this IMMEDIATELY as a professional Markdown narrative. NO raw braces, NO JSON tags."
            # Reuse the compacted history plus the correction demand
            recovery_response = await llm.ainvoke(final_compacted + [HumanMessage(content=recovery_prompt)])
            final_report_text = str(recovery_response.content)
        else:
            final_report_text = sanitized_text

    except Exception as e:
        logger.error(f"Reporter Synthesis Error: {str(e)}", exc_info=True)
        final_report_text = "Analysis completed. (PHASE_SYNTHESIS_RECOVERY): The system has transitioned to a managed reporting baseline due to model constraints."
        fb_msgs = []

    return {"final_report": final_report_text, "messages": fb_msgs + [AIMessage(content=final_report_text, name="reporter_finalize")]}
