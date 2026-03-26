# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Agent: Scout - Automated screenshot and visual capture tools.
# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates

# SPDX-License-Identifier: MIT

import base64
import logging
from typing import Annotated, Dict, Any

from langchain_core.tools import tool

from .decorators import log_io
from .shared_storage import SCOUT_CONTEXT

logger = logging.getLogger(__name__)

# Agent-specific resource context (Shared by all Scout sub-modules)
_NODE_RESOURCE_CONTEXT = SCOUT_CONTEXT



@tool
@log_io
def snapper(
    url: Annotated[str, "The URL of the webpage or chart to take a snapshot of. Must be a valid http or https URL."],
) -> str:
    """Use this to capture a full-resolution PNG image snapshot of a website or chart. This is the preferred tool when visual layout or graphical data (like TradingView) is required instead of raw HTML or text content."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return '{ "error": "playwright is not installed. Run `uv add playwright` and `uv run playwright install`." }'

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            # Set a standard desktop viewport for charts to render well
            page.set_viewport_size({"width": 1280, "height": 800})
            
            logger.info(f"Navigating to {url} for screenshot...")
            
            # Use networkidle to ensure JavaScript widgets (like TradingView) finish loading
            page.goto(url, wait_until="networkidle", timeout=20000)
            
            # Add an explicit wait time for heavy chart DOM elements to fully settle
            page.wait_for_timeout(4000)
            
            screenshot_bytes = page.screenshot(type="png")
            browser.close()
            
            # Encode to base64
            b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            return f'{{"images": ["data:image/png;base64,{b64}"]}}'
            
    except Exception as e:
        error_msg = f"Failed to take screenshot of {url}. Error: {repr(e)}"
        logger.error(error_msg)
        return f'{{"error": "{error_msg}"}}'
