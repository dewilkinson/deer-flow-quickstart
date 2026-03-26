# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import re
import html

def sanitize_content(text: str) -> str:
    """
    Sanity check and clean text content from web search results.
    Removes executable code, malicious script tags, and excessive HTML.
    """
    if not text:
        return ""
        
    # Remove script and style tags and their contents
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove all other HTML tags but keep content
    text = re.sub(r'<[^>]+>', '', text)
    
    # Unescape HTML entities
    text = html.unescape(text)
    
    # Remove potentially malicious patterns (basic protection)
    # e.g., javascript: protocols in what would be links
    text = re.sub(r'javascript:[^\s]*', '[REMOVED]', text, flags=re.IGNORECASE)
    
    # Remove malicious links/patterns like common XSS or auto-exec
    text = re.sub(r'onload\s*=\s*"[^"]*"', '', text, flags=re.IGNORECASE)
    
    # Normalize whitespaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text
