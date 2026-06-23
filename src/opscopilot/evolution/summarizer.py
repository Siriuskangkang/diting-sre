"""把一次排障结果（分诊+证据+报告）LLM 提炼成可复用的运维 runbook。"""
from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ..llm import get_llm

_SUMMARY_PROMPT = ChatPromptTemplate.from_template(
    """你是运维知识工程师。把下面这次故障的排障过程与结论，提炼成一篇可复用的运维排查手册(runbook)，
供未来遇到同类故障时检索使用。

要求：
1. 用 Markdown，结构严格为：# 故障标题 / ## 现象 / ## 常见根因 / ## 排查步骤 / ## 修复方案 / ## 预防措施
2. 只写被证据验证过的结论，不要编造；存疑处标注「待确认」
3. 语言简洁、可操作，像写给未来 SRE 的手册

告警/故障信息：
{alert}

分诊结论：
{triage}

调查证据：
{evidence}

排查报告：
{report}

请输出 runbook（Markdown）："""
)


def summarize_to_runbook(alert_info: str, triage: str, evidence: list[str], report: str) -> str:
    """把排障结果提炼成 runbook Markdown。"""
    chain = _SUMMARY_PROMPT | get_llm(temperature=0.2) | StrOutputParser()
    return chain.invoke(
        {
            "alert": alert_info,
            "triage": triage,
            "evidence": "\n---\n".join(str(e) for e in evidence)[:2000],
            "report": report[:3000],
        }
    ).strip()
