# Cobalt Multiagent - VLI Configuration
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>

import os

# --- Vault Mount Points ---
VAULT_ROOT = os.environ.get("OBSIDIAN_VAULT_PATH", r"C:\github\obsidian-vault")
COBALT_DIR = "_cobalt"
INBOX_DIR = "inbox"
ARCHIVE_DIR = "archives"

# --- Filenames ---
ACTION_PLAN_DIR = "action_plans"
SPECIALIZATION_FILE = "Vision_Analyst_Specialization.md"

def get_vli_path(subpath: str = "") -> str:
    """Get the full path to a Cobalt-related file or directory."""
    base = os.path.join(VAULT_ROOT, COBALT_DIR)
    if subpath:
        return os.path.join(base, subpath)
    return base

def get_action_plan_path() -> str:
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{today} Action Plan.md"
    return os.path.join(get_vli_path(ACTION_PLAN_DIR), filename)

def get_inbox_path() -> str:
    return get_vli_path(INBOX_DIR)

def get_archive_path() -> str:
    return get_vli_path(ARCHIVE_DIR)
