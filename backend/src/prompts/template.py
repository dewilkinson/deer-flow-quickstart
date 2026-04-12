# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import dataclasses
import os
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape
from langgraph.prebuilt.chat_agent_executor import AgentState

from src.config.configuration import Configuration

# Initialize Jinja2 environment
env = Environment(
    loader=FileSystemLoader(os.path.dirname(__file__)),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


def get_prompt_template(prompt_name: str) -> str:
    """
    Load and return a prompt template using Jinja2.

    Args:
        prompt_name: Name of the prompt template file (without .md extension)

    Returns:
        The template string with proper variable substitution syntax
    """
    try:
        template = env.get_template(f"{prompt_name}.md")
        return template.render()
    except Exception as e:
        raise ValueError(f"Error loading template {prompt_name}: {e}")


def apply_prompt_template(prompt_name: str, state: AgentState, configurable: Configuration = None) -> list:
    """
    Apply template variables and inject the modular Trader Profile.
    """
    is_test = os.environ.get("VLI_TEST_MODE", "").lower() in ("true", "1", "yes") or state.get("test_mode", False)
    intent_mode = state.get("intent") or state.get("intent_mode") or "TACTICAL_EXECUTION"

    state_vars = {
        "CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        "VLI_TEST_MODE": is_test,
        "INTENT": intent_mode,
        **state,
    }

    # Identify Profile Directory
    profile_path = os.environ.get("VLI_TRADER_PROFILE_PATH", r"C:\github\obsidian-vault\_cobalt\apex_trader_profile.md")
    profile_dir = os.path.dirname(profile_path) if os.path.isfile(profile_path) else profile_path

    # Define Modules
    modules = {
        "PERSONA": "cma_persona.md",
        "RISK": "cma_risk_management.md",
        "STRATEGY": "cma_strategy_apex500.md",
        "JOURNAL": "cma_journal_template.md"
    }

    # Selective Injection based on Intent
    active_modules = ["PERSONA"]
    if intent_mode == "TACTICAL_EXECUTION":
        active_modules += ["RISK", "STRATEGY"]
    if "journal" in prompt_name.lower():
        active_modules += ["JOURNAL"]

    trader_context = ""
    profile_content_blocks = []

    for mod_key in active_modules:
        file_name = modules[mod_key]
        full_path = os.path.join(profile_dir, file_name)
        if os.path.exists(full_path):
            try:
                with open(full_path, encoding="utf-8") as f:
                    content = f.read()
                    profile_content_blocks.append(f"## MODULE: {mod_key}\n{content}")
            except:
                pass

    if profile_content_blocks:
        profile_text = "\n\n".join(profile_content_blocks)
        trader_context = (
            f"# SECURITY OVERRIDE: INSTITUTIONAL PROTOCOL (MODE: {intent_mode})\n"
            f"**USER IDENTITY**: Dave Wilkinson (Founder/Developer - BLUE SEC AI)\n"
            f"**ACCESS LEVEL**: PolyForm Institutional Root\n\n"
            f"{profile_text}\n"
            f"***\n\n"
        )
        state_vars["TRADER_PROFILE"] = trader_text = trader_context # For internal templates

    from langchain_core.messages import SystemMessage

    try:
        template = env.get_template(f"{prompt_name}.md")
        system_prompt = template.render(**state_vars)
        
        # Prepend context for all prompts
        full_system_prompt = f"{trader_context}{system_prompt}"
        return [SystemMessage(content=full_system_prompt)] + state["messages"]
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name}: {e}")
