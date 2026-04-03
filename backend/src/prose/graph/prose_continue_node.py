# Agent: Prose Writer - Node definition for text continuation.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.config.agents import AGENT_LLM_MAP
from src.llms.llm import get_llm_by_type
from src.prompts.template import get_prompt_template
from src.prose.graph.state import ProseState
from src.tools.shared_storage import GLOBAL_CONTEXT, PROSE_CONTEXT

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS node.
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context: Persistent, shared across all Prose Writer nodes
_SHARED_RESOURCE_CONTEXT = PROSE_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


def prose_continue_node(state: ProseState):
    """Prose continue node implementation."""
    logger.info("Generating prose continue content.")
    model = get_llm_by_type(AGENT_LLM_MAP.get("prose_writer", "basic"))
    prose_content = model.invoke(
        [
            SystemMessage(content=get_prompt_template("prose/prose_continue")),
            HumanMessage(content=state["content"]),
        ],
    )
    return {"output": prose_content.content}
