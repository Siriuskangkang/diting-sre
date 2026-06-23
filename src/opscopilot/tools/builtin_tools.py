"""内置运维工具集（L3 Tool Calling 主力）。

每个工具用 @tool 装饰：LangChain 自动把 docstring + 类型注解转成 LLM 可见的
function schema，LLM 读 description 决定"何时调用、传什么参数"——这就是 Tool Calling。

工具返回字符串（给 LLM 的观测结果）。模拟工具返回确定性 mock，
注释里写明真实环境接哪个 API。
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import StructuredTool, tool

from .github_client import search_issues as _gh_search

logger = logging.getLogger(__name__)


@tool
def query_metrics(metric_name: str, service: str, lookback_minutes: int = 30) -> str:
    """查询 Prometheus 监控指标，用于诊断延迟/错误率/资源类故障。

    Args:
        metric_name: 指标名: http_5xx_rate / p99_latency / cpu_usage / memory_usage / db_connections
        service: 目标服务名
        lookback_minutes: 回看时间窗口(分钟)
    """
    from .adapters import prometheus

    return prometheus.query_metric(metric_name, service)


@tool
def query_logs(service: str, keyword: str, level: str = "ERROR") -> str:
    """查询服务日志(Loki/ELK)，抓异常堆栈定位根因。

    Args:
        service: 服务名
        keyword: 过滤关键词，如异常类名/错误信息
        level: 日志级别 ERROR/WARN/INFO
    """
    from .adapters import loki

    return loki.query_logs(service, keyword, level)


@tool
def get_pod_status(service: str) -> str:
    """查询 K8s Pod 状态，判断重启/OOM/探针问题。

    Args:
        service: 服务名
    """
    from .adapters import k8s

    return k8s.get_pods(service)


@tool
def search_github_issues(repo: str, keyword: str) -> str:
    """在 GitHub 仓库搜索已知 issue，看是否有相同故障的既有讨论/修复。

    Args:
        repo: 仓库 owner/name，如 kubernetes/kubernetes
        keyword: 搜索关键词
    """
    items = _gh_search(repo, keyword)
    if not items:
        return f"未在 {repo} 找到与 '{keyword}' 相关的 issue。"
    lines = [f"GitHub {repo} 命中 {len(items)} 条 issue:"]
    for it in items:
        lines.append(f"  #{it['number']} [{it['state']}] {it['title']}\n    {it['body']}")
    return "\n".join(lines)


def create_kb_tool(retriever) -> StructuredTool:
    """把 RAG 检索包装成一个 LangChain 工具，供 Agent 调用。

    这样 Agent 自主决定"何时查知识库"，而不是把检索写死在链里——
    这是 Agentic RAG 的核心思想（与传统 RAG 的关键区别，面试常问）。
    """

    def _kb(query: str) -> str:
        docs = retriever.retrieve(query)
        if not docs:
            return "知识库未检索到相关内容。"
        return "\n\n".join(
            f"[{d.metadata.get('source', '?')}]\n{d.page_content}" for d in docs
        )

    return StructuredTool.from_function(
        name="kb_search",
        description=(
            "检索运维排障知识库(runbook)。当需要已知故障的标准排查步骤、"
            "常见根因、修复方案、预防措施时调用。"
        ),
        func=_kb,
    )


# 默认工具集（不含 kb_search，后者需要 retriever 动态创建）
ALL_TOOLS = [query_metrics, query_logs, get_pod_status, search_github_issues]


def get_tools(retriever=None) -> list[Any]:
    """返回工具列表。传入 retriever 时额外挂上知识库检索工具。"""
    tools = list(ALL_TOOLS)
    if retriever is not None:
        tools.append(create_kb_tool(retriever))
    return tools
