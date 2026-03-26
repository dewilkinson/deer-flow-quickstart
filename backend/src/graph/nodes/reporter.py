# Agent: Reporter - Node definition for final synthesis reporting.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any
from src.tools.shared_storage import GLOBAL_CONTEXT
from ..types import State

logger = logging.getLogger(__name__)

# 1. Private to the Agent Code Itself
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type (None for Reporter)
_SHARED_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

def reporter_node(state: State):
    """Reporter node implementation."""
    logger.info("Reporter Node: Synthesis completed.")
    return {"final_report": "Analysis synthesis completed."}
