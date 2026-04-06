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
        return {}

    try:
        # Load synthesis LLMs
        llm = get_llm_by_type(AGENT_LLM_MAP.get("reporter", "basic"))
        
        # [NEW] Extract configuration for template rendering
        from src.config.configuration import Configuration
        configurable = Configuration.from_runnable_config(config)

        raw_messages = state.get("messages", [])
        
        # [RELIABILITY] Truncate context to prevent LLM payload rejection (Safety/Context blocks)
        MAX_HISTORY = 10
        if len(raw_messages) > MAX_HISTORY:
            target_idx = len(raw_messages) - MAX_HISTORY
            while target_idx > 0 and not isinstance(raw_messages[target_idx], HumanMessage):
                target_idx -= 1
            raw_messages = raw_messages[target_idx:]

        start_time = datetime.now()

        logger.info(f"Reporter: Compacting and sanitizing history ({len(raw_messages)} messages) for synthesis.")
        compacted = []

        for m in raw_messages:
            if isinstance(m, HumanMessage):
                compacted.append(HumanMessage(content=m.content))
            elif isinstance(m, AIMessage):
                if isinstance(m.content, list):
                    content = " ".join([item.get("text", "") if isinstance(item, dict) else str(item) for item in m.content])
                else:
                    content = str(m.content)
                
                if not content.strip() and hasattr(m, "tool_calls") and m.tool_calls:
                    content = f"[Agent invoked tool(s): {', '.join(tc.get('name', 'unknown') for tc in m.tool_calls)}]"
                
                logger.debug(f"[VLI_REPORTER] Compacting AIMessage of len {len(content)}: {content[:100]}...")
                if len(content) > 10000:
                    content = content[:10000] + "\n... [Content Truncated]"
                
                if content.strip():
                    compacted.append(AIMessage(content=content))
            elif isinstance(m, ToolMessage):
                content = str(m.content)
                if len(content) > 10000:
                    content = content[:10000] + "\n... [Large Dataset Pruned]"
                compacted.append(HumanMessage(content=f"[System: Tool '{m.name}' Returned]:\n{content}"))

        state_to_synthesize = {**state, "messages": compacted}

        # Invoke LLM for synthesis
        messages = apply_prompt_template("reporter", state_to_synthesize, configurable=configurable)
        response = await llm.ainvoke(messages)

        # Log performance metrics
        end_time = datetime.now()
        latency = (end_time - start_time).total_seconds()
        from src.utils.vli_metrics import log_vli_metric

        log_vli_metric("reporter", latency, True)

        final_report_text = str(response.content)
        if not final_report_text.strip():
            logger.error(f"[VLI_REPORTER] Empty string returned. Metadata: {getattr(response, 'response_metadata', 'None')}")
            final_report_text = "Analysis completed. (Synthesis pipeline returned an empty payload. Possible context/safety block)."
    except Exception as e:
        logger.error(f"Reporter Synthesis Error: {e}")
        final_report_text = "Analysis completed. (Synthesis failed, check logs)"

    return {"final_report": final_report_text}
