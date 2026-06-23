"""GitHub API 客户端：搜索 issues / 获取 issue 详情。

有 GITHUB_TOKEN 时走真实 API；无 token 时返回确定性 mock 数据，
保证 demo 在任何环境都能跑通（面试演示不翻车）。被 builtin_tools 与
自研 MCP Server 共用——同一份能力，两种暴露方式（普通函数 vs MCP 协议）。
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger(__name__)
GITHUB_API = "https://api.github.com"


def _mock_search_issues(repo: str, keyword: str, state: str) -> list[dict[str, Any]]:
    """无 token 时的确定性 mock，内容围绕 keyword 组织，便于演示检索流程。"""
    return [
        {
            "number": 142,
            "title": f"[{repo}] {keyword} 导致偶发连接超时",
            "state": "open",
            "url": f"https://github.com/{repo}/issues/142",
            "body": f"复现：高并发下 {keyword} 时连接超时，疑似连接池耗尽，未归还连接。",
        },
        {
            "number": 88,
            "title": f"[{repo}] {keyword} 排查手册补充",
            "state": "closed",
            "url": f"https://github.com/{repo}/issues/88",
            "body": f"补充 {keyword} 的标准排查路径，已合并到 runbook。",
        },
    ]


def search_issues(repo: str, keyword: str, state: str = "open") -> list[dict[str, Any]]:
    """搜索仓库 issue。repo 格式: owner/name。"""
    if not settings.github_token:
        logger.info("无 GITHUB_TOKEN，返回 mock 数据（demo 模式）")
        return _mock_search_issues(repo, keyword, state)

    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
    }
    q = f"repo:{repo} {keyword} type:issue state:{state}"
    r = httpx.get(
        f"{GITHUB_API}/search/issues",
        headers=headers,
        params={"q": q, "per_page": 5},
        timeout=20,
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    return [
        {
            "number": it["number"],
            "title": it["title"],
            "state": it["state"],
            "url": it["html_url"],
            "body": (it.get("body") or "")[:300],
        }
        for it in items
    ]


def get_issue(repo: str, issue_number: int) -> dict[str, Any]:
    """获取单个 issue 详情。"""
    if not settings.github_token:
        return {
            "number": issue_number,
            "title": f"[{repo}] mock issue #{issue_number}",
            "state": "open",
            "url": f"https://github.com/{repo}/issues/{issue_number}",
            "body": "无 token 时的 mock issue 详情：连接池耗尽导致 5xx，已通过归还连接修复。",
        }

    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
    }
    r = httpx.get(
        f"{GITHUB_API}/repos/{repo}/issues/{issue_number}", headers=headers, timeout=20
    )
    r.raise_for_status()
    it = r.json()
    return {
        "number": it["number"],
        "title": it["title"],
        "state": it["state"],
        "url": it.get("html_url"),
        "body": (it.get("body") or "")[:500],
    }
