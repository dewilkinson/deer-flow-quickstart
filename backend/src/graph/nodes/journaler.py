# Agent: Journaler - Node definition for diary and trade logging.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

from src.tools import (
    write_daily_journal, list_journal_entries, read_journal_entry,
    get_journal_folder, set_journal_folder, get_brokerage_history, get_stock_quote
)
from src.tools.shared_storage import JOURNALER_CONTEXT, GLOBAL_CONTEXT
from ..types import State
from .common import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = JOURNALER_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

async def journaler_node(state: State, config: RunnableConfig):
    """Journaler node implementation."""
    logger.info("Journaler Node: Documenting vibes and trades.")
    tools = [
        write_daily_journal, list_journal_entries, read_journal_entry, 
        get_journal_folder, set_journal_folder, get_brokerage_history, get_stock_quote
    ]

    return await _setup_and_execute_agent_step(state, config, "journaler", tools)
