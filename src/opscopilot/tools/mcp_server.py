"""自研 MCP Server (L3 杀手锏)：把 GitHub Issues 能力封装成标准 MCP 协议。

为什么 MCP（面试必答）：传统每个工具各自定义 schema，N 个 Agent × M 个工具 = N×M
集成工作。MCP 把工具标准化为"Server 暴露 tools/resources/prompts"，任何支持 MCP 的
客户端（Claude Desktop / IDE / 其他 Agent）都能即插即用，治 N×M 集成爆炸。
这就是为什么 Anthropic 推 MCP——它是工具层的"USB-C 接口"。

本 server 暴露:
  - tools:     search_github_issues / get_github_issue（可被调用执行）
  - resource:  github://repos/{repo}（只读数据源）

运行:
  python -m opscopilot.tools.mcp_server            # stdio，供 MCP client 连接
  mcp dev src/opscopilot/tools/mcp_server.py        # 用 MCP Inspector 可视化调试
  mcp install src/opscopilot/tools/mcp_server.py    # 装进 Claude Desktop
"""
from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from .github_client import get_issue, search_issues

logger = logging.getLogger(__name__)

mcp = FastMCP("github-ops-mcp")


@mcp.tool()
def search_github_issues(repo: str, keyword: str, state: str = "open") -> str:
    """在 GitHub 仓库搜索 issue，用于查既有故障讨论/修复方案。

    Args:
        repo: owner/name，如 kubernetes/kubernetes
        keyword: 搜索关键词
        state: open / closed / all
    """
    items = search_issues(repo, keyword, state)
    if not items:
        return f"未在 {repo} 找到 '{keyword}' 相关 issue。"
    lines = [f"命中 {len(items)} 条:"]
    for it in items:
        lines.append(f"#{it['number']} [{it['state']}] {it['title']}\n{it['body']}")
    return "\n".join(lines)


@mcp.tool()
def get_github_issue(repo: str, issue_number: int) -> str:
    """获取单个 GitHub issue 详情。

    Args:
        repo: owner/name
        issue_number: issue 编号
    """
    it = get_issue(repo, issue_number)
    return f"#{it['number']} [{it.get('state', '?')}] {it['title']}\n{it.get('body', '')}"


@mcp.resource("github://repos/{repo}")
def repo_issue_overview(repo: str) -> str:
    """MCP resource 示例：暴露某仓库的 open issue 概览（resource = 只读数据源）。"""
    items = search_issues(repo, "is:issue", "open")
    if not items:
        return f"{repo} 暂无 open issue。"
    return "\n".join(f"#{i['number']} {i['title']}" for i in items)


def main() -> None:
    """以 stdio transport 启动 MCP server。"""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
