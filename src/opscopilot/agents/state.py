"""LangGraph 全局状态：StateGraph 节点间共享的数据结构。

TypedDict + Annotated[..., reducer] 是 LangGraph 的标准写法。
messages 用 add_messages reducer：多节点追加消息时自动合并/去重。
"""
from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class OpsState(TypedDict):
    """运维排障 Agent 的全局状态。"""

    query: str  # 原始故障描述
    triage: str  # 分诊结论：故障类型 + 假设根因 + 待查项
    evidence: list[str]  # 调查收集的证据（工具返回 + agent 总结）
    messages: Annotated[list, add_messages]  # investigator 的 ReAct 对话历史
    iteration: int  # 调查轮次（防失控循环 / 成本爆炸）
    report: str  # 最终排查报告
