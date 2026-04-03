# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT


from pydantic import BaseModel, Field


class MCPServerMetadataRequest(BaseModel):
    """Request model for MCP server metadata."""

    transport: str = Field(
        ...,
        description=("The type of MCP server connection (stdio or sse or streamable_http)"),
    )
    command: str | None = Field(None, description="The command to execute (for stdio type)")
    args: list[str] | None = Field(None, description="Command arguments (for stdio type)")
    url: str | None = Field(None, description="The URL of the SSE server (for sse type)")
    env: dict[str, str] | None = Field(None, description="Environment variables (for stdio type)")
    headers: dict[str, str] | None = Field(None, description="HTTP headers (for sse/streamable_http type)")
    timeout_seconds: int | None = Field(None, description="Optional custom timeout in seconds for the operation")


class MCPServerMetadataResponse(BaseModel):
    """Response model for MCP server metadata."""

    transport: str = Field(
        ...,
        description=("The type of MCP server connection (stdio or sse or streamable_http)"),
    )
    command: str | None = Field(None, description="The command to execute (for stdio type)")
    args: list[str] | None = Field(None, description="Command arguments (for stdio type)")
    url: str | None = Field(None, description="The URL of the SSE server (for sse type)")
    env: dict[str, str] | None = Field(None, description="Environment variables (for stdio type)")
    headers: dict[str, str] | None = Field(None, description="HTTP headers (for sse/streamable_http type)")
    tools: list = Field(default_factory=list, description="Available tools from the MCP server")
