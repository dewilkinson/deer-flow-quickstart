# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from typing import Optional

from langgraph.graph import MessagesState

from ..types import Script


class PodcastState(MessagesState):
    """State for the podcast generation."""

    # Input
    input: str = ""

    # Output
    output: Optional[bytes] = None

    # Assets
    script: Optional[Script] = None
    audio_chunks: list[bytes] = []
