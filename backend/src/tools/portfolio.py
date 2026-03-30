# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Agent: Portfolio Manager - Watchlist and Ledger management tools.

import os
import logging
from typing import List, Dict, Any
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from src.config.configuration import Configuration
from .shared_storage import PORTFOLIO_MANAGER_CONTEXT

logger = logging.getLogger(__name__)

def _get_obsidian_config(config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    settings = configurable.obsidian_settings if configurable.obsidian_settings else {}
    vault_path = settings.get("OBSIDIAN_VAULT_PATH") or os.getenv("OBSIDIAN_VAULT_PATH")
    return vault_path

@tool
def update_watchlist(tickers: List[str], action: str = "add", config: RunnableConfig = None):
    """
    Manages the 'Watchlist.md' file in the Obsidian vault (_cobalt directory).
    Actions: 'add' (adds tickers if not present), 'remove' (removes tickers), 'list' (returns content).
    """
    vault_path = _get_obsidian_config(config)
    if not vault_path:
        return "[ERROR]: Obsidian vault path is not configured."
    
    cobalt_dir = os.path.join(vault_path, "_cobalt")
    if not os.path.exists(cobalt_dir):
        os.makedirs(cobalt_dir, exist_ok=True)
    
    watchlist_path = os.path.join(cobalt_dir, "Watchlist.md")
    
    # Read existing
    current_watchlist = []
    if os.path.exists(watchlist_path):
        with open(watchlist_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            current_watchlist = [line.strip().replace("- ", "") for line in lines if line.startswith("- ")]

    if action == "list":
        return f"Current Watchlist: {', '.join(current_watchlist)}" if current_watchlist else "Watchlist is empty."

    # Normalize tickers
    tickers = [t.upper().strip() for t in tickers]
    
    if action == "add":
        new_tickers = [t for t in tickers if t not in current_watchlist]
        current_watchlist.extend(new_tickers)
        msg = f"Added: {', '.join(new_tickers)}" if new_tickers else "No new tickers to add."
    elif action == "remove":
        current_watchlist = [t for t in current_watchlist if t not in tickers]
        msg = f"Removed: {', '.join(tickers)}"
    else:
        return "[ERROR]: Invalid action. Use 'add', 'remove', or 'list'."

    # Sort and Write back
    current_watchlist.sort()
    with open(watchlist_path, "w", encoding="utf-8") as f:
        f.write("# Cobalt Watchlist\n\n")
        for ticker in current_watchlist:
            f.write(f"- {ticker}\n")
            
    return f"{msg} | Watchlist updated at {watchlist_path}"

@tool
def update_portfolio_ledger(position_data: str, config: RunnableConfig = None):
    """
    Updates the 'Portfolio_Ledger.md' in the Obsidian vault (_cobalt directory).
    Use this to persist the current state of active 'Sword' and 'Shield' positions.
    """
    vault_path = _get_obsidian_config(config)
    if not vault_path:
        return "[ERROR]: Obsidian vault path is not configured."
    
    cobalt_dir = os.path.join(vault_path, "_cobalt")
    if not os.path.exists(cobalt_dir):
        os.makedirs(cobalt_dir, exist_ok=True)
        
    ledger_path = os.path.join(cobalt_dir, "Portfolio_Ledger.md")
    
    try:
        with open(ledger_path, "w", encoding="utf-8") as f:
            f.write(f"# Portfolio Ledger\n\n{position_data}")
        return f"Portfolio ledger successfully updated at {ledger_path}"
    except Exception as e:
        return f"[ERROR]: Failed to update ledger: {e}"

@tool
def get_portfolio_balance_report(config: RunnableConfig = None):
    """
    Reads both the Watchlist and Portfolio Ledger to provide a summary of the current tactical state.
    """
    vault_path = _get_obsidian_config(config)
    if not vault_path:
        return "[ERROR]: Obsidian vault path is not configured."
    
    cobalt_dir = os.path.join(vault_path, "_cobalt")
    reports = []
    
    for filename in ["Portfolio_Ledger.md", "Watchlist.md"]:
        path = os.path.join(cobalt_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                reports.append(f"--- {filename} ---\n{f.read()}")
        else:
            reports.append(f"--- {filename} ---\n(File Not Found)")
            
    return "\n\n".join(reports)
