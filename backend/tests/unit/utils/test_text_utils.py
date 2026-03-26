# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import pytest
from src.utils.text_utils import sanitize_content

def test_sanitize_content_html_stripping():
    raw_html = "<div>Hello <b>World</b></div>"
    expected = "Hello World"
    assert sanitize_content(raw_html) == expected

def test_sanitize_content_script_removal():
    raw_script = "Check this <script>alert('bad');</script> out!"
    expected = "Check this out!"
    assert sanitize_content(raw_script) == expected

def test_sanitize_content_style_removal():
    raw_style = "Text <style>body {color: red;}</style> content"
    expected = "Text content"
    assert sanitize_content(raw_style) == expected

def test_sanitize_content_malicious_attributes():
    raw_attr = '<img src="x" onload="alert(1)">'
    expected = "" # Because <img> is stripped entirely by the tag removal regex
    # Our regex for onload should also be tested if we kept some tags
    # Wait, our current regex removes all <[^>]+>
    assert sanitize_content(raw_attr) == expected

def test_sanitize_content_whitespace_normalization():
    messy_text = "   too    many    spaces   \n\n\n   "
    expected = "too many spaces"
    assert sanitize_content(messy_text) == expected

def test_sanitize_content_empty_input():
    assert sanitize_content("") == ""
    assert sanitize_content(None) == ""
