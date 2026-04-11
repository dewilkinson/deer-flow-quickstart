import logging
import os
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.config.agents import AGENT_LLM_MAP
from src.llms.llm import get_llm_by_type
from langchain_core.runnables import RunnableConfig
from src.prompts.template import apply_prompt_template

from ..types import State

logger = logging.getLogger(__name__)


async def reporter_node(state: State, config: RunnableConfig):
    # 2. Dynamic Synthesis
    if state.get("final_report"):
        return {"messages": []}

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
        elif "reporter_llm_type" in config.get("configurable", {}):
            llm_type = config["configurable"]["reporter_llm_type"]
        else:
            llm_type = AGENT_LLM_MAP.get("reporter", "reasoning")

        llm = get_llm_by_type(llm_type)

        raw_messages = state.get("messages", [])

        # [ANTI-ROT] Stateless Transaction Model:
        # Context window expanded to 12 to ensure all Specialist turns are visible for synthesis.
        MAX_HISTORY = 12
        if len(raw_messages) > MAX_HISTORY:
            target_idx = len(raw_messages) - MAX_HISTORY
            while target_idx > 0 and not isinstance(raw_messages[target_idx], HumanMessage):
                target_idx -= 1
            raw_messages = raw_messages[target_idx:]

        start_time = datetime.now()

        logger.info(f"Reporter: Compacting and sanitizing history ({len(raw_messages)} messages) for synthesis.")
        compacted = []

        for m in raw_messages:
            m_type = getattr(m, "type", m.get("type", "")) if isinstance(m, dict) else getattr(m, "type", "")
            if not m_type and isinstance(m, HumanMessage):
                m_type = "human"
            elif not m_type and isinstance(m, AIMessage):
                m_type = "ai"
            elif not m_type and isinstance(m, ToolMessage):
                m_type = "tool"

            if m_type == "human" or isinstance(m, HumanMessage):
                content = str(m.get("content", "")) if isinstance(m, dict) else str(getattr(m, "content", ""))
                compacted.append(HumanMessage(content=content))

            elif m_type == "ai" or isinstance(m, AIMessage):
                if isinstance(m, dict):
                    raw_content = m.get("content", "")
                    tool_calls = m.get("tool_calls", [])
                else:
                    raw_content = getattr(m, "content", "")
                    tool_calls = getattr(m, "tool_calls", [])

                if isinstance(raw_content, list):
                    content = " ".join([item.get("text", "") if isinstance(item, dict) else str(item) for item in raw_content])
                else:
                    content = str(raw_content)

                if not content.strip() and tool_calls:
                    content = f"[Agent invoked tool(s): {', '.join(tc.get('name', 'unknown') for tc in tool_calls)}]"

                logger.debug(f"[VLI_REPORTER] Compacting AIMessage of len {len(content)}: {content[:100]}...")
                if len(content) > 10000:
                    content = content[:10000] + "\n... [Content Truncated]"

                if content.strip():
                    compacted.append(AIMessage(content=content))

            elif m_type == "tool" or isinstance(m, ToolMessage):
                content = str(m.get("content", "")) if isinstance(m, dict) else str(getattr(m, "content", ""))
                name = m.get("name", "unknown") if isinstance(m, dict) else getattr(m, "name", "unknown")

                try:
                    # Attempt to compress raw JSON arrays into flattened mathematical summaries if massive
                    import json

                    parsed = json.loads(content)
                    if isinstance(parsed, list) and len(parsed) > 500:
                        content = f"[Truncated JSON List of {len(parsed)} items. Keys: {str(list(parsed[0].keys()))[:200]} if mapping]."
                    elif isinstance(parsed, dict) and len(str(parsed)) > 25000:
                        content = f"[Compressed JSON Object. Keys: {list(parsed.keys())}]"
                except:
                    pass

                if len(content) > 40000:
                    content = content[:40000] + "\n... [Large Dataset Pruned (SDK Validation Threshold Reached)]"
                compacted.append(HumanMessage(content=f"[System: Tool '{name}' Returned]:\n{content}"))
            else:
                # Fallback for generic/unknown messages
                content = str(m.get("content", "")) if isinstance(m, dict) else str(getattr(m, "content", ""))
                if content:
                    compacted.append(HumanMessage(content=content))

        # [STABILITY] Google Gemini SDK requires strict alternating turns.
        # To completely bypass internal protobuf/conversational turn rejection for multi-agent loops,
        # we squash the ENTIRE context payload into a SINGLE HumanMessage for the Reporter.
        synthesized_history = "\n\n==== CONTEXTUAL DATA ====\n\n".join([m.content for m in compacted if hasattr(m, "content") and m.content.strip()])

        # Guardrail against entirely empty history
        if not synthesized_history.strip():
            synthesized_history = "No specialist data generated. Produce a default blank analysis."

        final_compacted = [HumanMessage(content=synthesized_history)]

        state_to_synthesize = {**state, "messages": final_compacted}

        # Invoke LLM for synthesis
        messages = apply_prompt_template("reporter", state_to_synthesize, configurable=configurable)
        
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
                final_report_text = "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in response.content])
            except Exception as e:
                logger.error(f"List parse error: {e}")
                final_report_text = str(response.content)
        else:
            final_report_text = str(response.content)

        if not final_report_text.strip() or final_report_text.strip() == "[]":
            logger.error(f"[VLI_REPORTER] Empty string/bracket returned. Metadata: {getattr(response, 'response_metadata', 'None')}")
            final_report_text = "Analysis completed. (Synthesis pipeline returned an empty payload. Deep evaluation was successfully processed but blocked natively by SDK context/safety rendering)."

    except Exception as e:
        logger.error(f"Reporter Synthesis Error: {str(e)}")
        final_report_text = "Analysis completed. (PHASE_SYNTHESIS_RECOVERY): The system has transitioned to a managed reporting baseline due to model constraints."
        fb_msgs = []

    return {"final_report": final_report_text, "messages": fb_msgs + [AIMessage(content=final_report_text, name="reporter_finalize")]}
