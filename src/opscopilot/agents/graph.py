"""LangGraph 主编排：把 Triage / Supervisor / Investigator / Reporter 串成状态机。

图结构:
    START → triage → supervisor ──(route)──→ investigate ──→ supervisor ... ──→ report → END
                         └───────────────────────(证据够了)──────────────────→ report

关键设计:
  - 用图/状态机建模 Agent：每一步是显式节点，可逐节点回放、调试、可观测。
  - 条件边实现"循环重查"：证据不足就回到 investigate，达到上限或证据够就 report。
  - MAX_ITER + 证据阈值双保险，防止失控循环和成本爆炸。
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph

from ..llm import get_llm
from ..tools import get_tools
from .nodes import (
    make_investigator_node,
    make_report_node,
    make_supervisor_node,
    make_triage_node,
    route,
)
from .state import OpsState

logger = logging.getLogger(__name__)


def build_graph(
    llm: BaseChatModel | None = None,
    retriever: Any = None,
    extra_tools: list[BaseTool] | None = None,
):
    """组装并编译 StateGraph。

    Args:
        llm:          主 LLM；None 则用默认配置。
        retriever:    RAG 检索器；传入后自动挂 kb_search 工具（Agentic RAG）。
        extra_tools:  额外工具（如 MCP 适配器加载的工具）。
    """
    llm = llm or get_llm()
    tools = get_tools(retriever=retriever)
    if extra_tools:
        tools = list(tools) + list(extra_tools)

    graph = StateGraph(OpsState)
    graph.add_node("triage", make_triage_node(llm))
    graph.add_node("supervisor", make_supervisor_node())
    graph.add_node("investigate", make_investigator_node(llm, tools))
    graph.add_node("report", make_report_node(llm))

    graph.add_edge(START, "triage")
    graph.add_edge("triage", "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route,
        {"investigate": "investigate", "report": "report"},
    )
    graph.add_edge("investigate", "supervisor")
    graph.add_edge("report", END)

    return graph.compile()


def run(
    query: str,
    llm: BaseChatModel | None = None,
    retriever: Any = None,
    extra_tools: list[BaseTool] | None = None,
) -> dict:
    """端到端运行排障：输入故障描述，返回完整 state（含 report）。"""
    app = build_graph(llm=llm, retriever=retriever, extra_tools=extra_tools)
    return app.invoke(
        {
            "query": query,
            "triage": "",
            "evidence": [],
            "messages": [],
            "iteration": 0,
            "report": "",
        },
        config={"recursion_limit": 50},
    )
