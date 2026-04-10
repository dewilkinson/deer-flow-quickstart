# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

from collections import defaultdict
from typing import Literal

# Define available LLM types
LLMType = Literal["basic", "reasoning", "vision", "code", "core"]

# 1. Base dictionary for explicit mappings
_BASE_AGENT_LLM_MAP: dict[str, LLMType] = {
    "coordinator": "reasoning",
    "parser": "reasoning",
    "planner": "reasoning",
    "synthesizer": "basic",
    "coder": "basic",
    # [BUGFIX: ANTI-ROT]
    # The reporter was previously 'reasoning' to handle massive SMC payloads, but Gemini 3.1 Pro
    # frequently fails to export text outside of <think> blocks on complex state. As payloads
    # are now aggressively pruned to 10k max length, 'basic' (Flash) handles synthesis flawlessly.
    "reporter": "basic",
    "podcast_script_writer": "basic",
    "ppt_composer": "basic",
    "prose_writer": "basic",
    "prompt_enhancer": "basic",
    "scout": "basic",
    "journaler": "basic",
    "portfolio_manager": "reasoning",
    "risk_manager": "reasoning",
    "analyst": "reasoning",
    "smc_analyst": "reasoning",
    "imaging": "vision",
    "vision_specialist": "vision",
    "system": "basic",
}

# 2. Resilient Registry: Never throws KeyError, defaults to "basic"
AGENT_LLM_MAP = defaultdict(lambda: "basic", _BASE_AGENT_LLM_MAP)
