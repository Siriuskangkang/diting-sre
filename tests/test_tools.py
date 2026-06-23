"""内置工具单元测试（确定性 mock 返回，不依赖网络 / token）。"""
from __future__ import annotations

from opscopilot.tools.builtin_tools import (
    ALL_TOOLS,
    get_pod_status,
    get_tools,
    query_logs,
    query_metrics,
    search_github_issues,
)


def test_query_metrics_known_metric():
    r = query_metrics.invoke(
        {"metric_name": "http_5xx_rate", "service": "order", "lookback_minutes": 30}
    )
    assert "5.6%" in r
    assert "order" in r


def test_query_metrics_unknown_metric_fallback():
    r = query_metrics.invoke(
        {"metric_name": "unknown_metric", "service": "order", "lookback_minutes": 30}
    )
    assert "暂无数据" in r


def test_query_logs_echoes_keyword():
    r = query_logs.invoke({"service": "order", "keyword": "DbPool", "level": "ERROR"})
    assert "DbPool" in r
    assert "ERROR" in r


def test_get_pod_status_has_oom_signal():
    r = get_pod_status.invoke({"service": "order"})
    assert "OOMKilled" in r or "CrashLoopBackOff" in r


def test_search_github_issues_returns_text():
    r = search_github_issues.invoke({"repo": "foo/bar", "keyword": "OOM"})
    assert isinstance(r, str) and len(r) > 0


def test_all_tools_have_names_and_descriptions():
    for t in ALL_TOOLS:
        assert t.name
        assert t.description


def test_get_tools_without_retriever_equals_all_tools():
    tools = get_tools()
    assert len(tools) == len(ALL_TOOLS)
