# Agent: Journaler - Node definition for diary and trade logging.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.tools import get_brokerage_history, get_journal_folder, get_stock_quote, list_journal_entries, read_journal_entry, set_journal_folder, write_daily_journal
from src.tools.shared_storage import GLOBAL_CONTEXT, JOURNALER_CONTEXT

from ..types import State
from .common_vli import _setup_and_execute_agent_step

logger = logging.getLogger(__name__)

# 1. Private context: Truly private to THIS module.
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context: Persistent, shared by agents of the SAME type
_SHARED_RESOURCE_CONTEXT = JOURNALER_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


async def journaler_node(state: State, config: RunnableConfig):
    """Journaler node implementation."""
    logger.info("Journaler Node: Documenting vibes and trades.")
    tools = [write_daily_journal, list_journal_entries, read_journal_entry, get_journal_folder, set_journal_folder, get_brokerage_history, get_stock_quote]

    return await _setup_and_execute_agent_step(state, config, "journaler", tools)
