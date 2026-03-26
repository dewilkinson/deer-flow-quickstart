# Agent: Coder - Node definition for Python REPL execution.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

from src.tools import python_repl_tool
from src.tools.shared_storage import CODER_CONTEXT, GLOBAL_CONTEXT
from ..types import State
from .common import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = CODER_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

async def coder_node(state: State, config: RunnableConfig):
    """Coder node implementation."""
    logger.info("Coder Node: Preparing Python execution.")
    return await _setup_and_execute_agent_step(state, config, "coder", [python_repl_tool])
