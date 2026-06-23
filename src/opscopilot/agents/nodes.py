"""Agent 节点实现：Triage / Supervisor / Investigator(ReAct) / Reporter。

架构（Supervisor 模式）:
  START → triage → supervisor ⇄ investigate → report → END
                           (条件边路由：证据够了吗？够了→report，不够→再调查)

- triage:        LLM 分析故障，输出类型/假设/待查项
- supervisor:    更新轮次，由条件边决定路由（轻量，核心逻辑在 route()）
- investigate:   ReAct 工具调用 Agent，自主调用 metrics/logs/pod/github/kb 收集证据
- report:        LLM 综合证据生成结构化排障报告

为什么这样分（面试点）：单一职责 + 可观测。每个节点是一个独立 step，
LangGraph 能逐节点回放/调试/插桩；Supervisor 把"何时停"显式化，避免无限循环。
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from .state import OpsState

logger = logging.getLogger(__name__)

# 调查最大轮次：防止失控循环 + 控制成本（面试讲点）
MAX_ITER = 2

TRIAGE_PROMPT = """你是运维分诊专家。分析下面故障描述，简明输出:
1. 故障类型 (5xx飙升 / 延迟突增 / Pod崩溃 / 连接池耗尽 / OOM / 磁盘 / Redis / 证书 等)
2. 最可能的 2-3 个根因假设
3. 建议调查时查的项 (指标 / 日志 / Pod状态 / GitHub issue / 知识库)
只输出结论，不要寒暄。"""

INVESTIGATOR_PROMPT = """你是故障调查 Agent。基于"故障描述"和"分诊结论"，调用可用工具收集证据：
可查监控指标、查日志、查 Pod 状态、搜 GitHub issue、检索知识库。
目标：找到根因的实锤证据。最后用一段话总结你的关键发现和最可能的根因。"""

REPORT_PROMPT = """你是资深 SRE。基于故障描述、分诊结论和调查证据，生成结构化排查报告：

## 故障概述
## 根因分析（必须标注证据来源）
## 修复方案（按优先级排序）
## 预防措施

要求：结论必须有证据支撑；证据不足或存疑处必须明确标注"待进一步确认"，禁止编造。"""


# ---------------------------------------------------------------- triage


def make_triage_node(llm: BaseChatModel) -> Callable[[OpsState], dict]:
    def triage(state: OpsState) -> dict:
        logger.info("[triage] 分诊: %s", state["query"][:50])
        resp = llm.invoke(
            [SystemMessage(content=TRIAGE_PROMPT), HumanMessage(content=state["query"])]
        )
        return {"triage": resp.content}

    return triage


# ----------------------------------------------------------- supervisor


def make_supervisor_node() -> Callable[[OpsState], dict]:
    """Supervisor：累加调查轮次。真正路由逻辑在 route() 条件边里。"""

    def supervisor(state: OpsState) -> dict:
        it = state.get("iteration", 0) + 1
        logger.info("[supervisor] 进入第 %d 轮决策", it)
        return {"iteration": it}

    return supervisor


def route(state: OpsState) -> str:
    """条件边路由函数：决定 supervisor 之后去 investigate 还是 report。

    停止条件（任一满足即生成报告）:
      - 调查轮次达到 MAX_ITER（硬上限，防失控）
      - 已收集足够证据（>=3 条，证据够就不浪费成本）
    """
    it = state.get("iteration", 0)
    evidence = state.get("evidence", [])
    if it >= MAX_ITER:
        return "report"
    if it > 1 and len(evidence) >= 3:
        return "report"
    return "investigate"


# ---------------------------------------------------------- investigator


def make_investigator_node(
    llm: BaseChatModel, tools: list[BaseTool]
) -> Callable[[OpsState], dict]:
    """ReAct 工具调用 Agent：自主决定调哪些工具、调几次。"""
    react = create_react_agent(llm, tools)

    def investigate(state: OpsState) -> dict:
        logger.info("[investigate] 第 %d 轮调查", state.get("iteration", 1))
        human = HumanMessage(
            content=f"故障描述: {state['query']}\n\n分诊结论:\n{state.get('triage', '')}"
        )
        result = react.invoke({"messages": [SystemMessage(content=INVESTIGATOR_PROMPT), human]})
        msgs = result.get("messages", [])

        # 提取工具观测结果作为证据 + agent 最终总结
        evidence: list[str] = [m.content for m in msgs if isinstance(m, ToolMessage)]
        ai_summaries = [m for m in msgs if isinstance(m, AIMessage) and m.content]
        if ai_summaries:
            evidence.append("[本轮调查总结] " + str(ai_summaries[-1].content))

        logger.info("[investigate] 收集到 %d 条证据", len(evidence))
        return {"messages": msgs, "evidence": evidence}

    return investigate


# -------------------------------------------------------------- reporter


def make_report_node(llm: BaseChatModel) -> Callable[[OpsState], dict]:
    def report(state: OpsState) -> dict:
        logger.info("[report] 生成最终报告")
        evidence_text = "\n---\n".join(state.get("evidence", [])) or "（无证据）"
        ctx = (
            f"故障描述: {state['query']}\n\n"
            f"分诊结论:\n{state.get('triage', '')}\n\n"
            f"调查证据:\n{evidence_text}"
        )
        resp = llm.invoke(
            [SystemMessage(content=REPORT_PROMPT), HumanMessage(content=ctx)]
        )
        return {"report": resp.content}

    return report
