"""MCP → LangChain 工具适配器（L3 进阶）。

把自研 MCP Server 暴露的工具加载为 LangChain tool，让 LangGraph Agent 能像调用
普通工具一样调用 MCP 工具——这就是"工具层标准化"带来的复用价值。

需要: pip install langchain-mcp-adapters
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# 默认启动自研 GitHub MCP server 的命令（stdio 子进程）
DEFAULT_SERVER_CMD = ["python", "-m", "opscopilot.tools.mcp_server"]


def load_mcp_tools(server_command: list[str] | None = None) -> list[Any]:
    """启动 MCP server 子进程(stdio)，把它的工具加载为 LangChain tool。

    Example:
        tools = load_mcp_tools()                 # 连自研 GitHub MCP server
        graph = build_graph(extra_tools=tools)   # 接入 LangGraph Agent
    """
    from langchain_mcp_adapters.client import MultiServerMCPClient

    cmd = server_command or DEFAULT_SERVER_CMD
    client = MultiServerMCPClient(
        {"github-ops": {"command": cmd[0], "args": cmd[1:], "transport": "stdio"}}
    )
    return asyncio.run(client.get_tools())
