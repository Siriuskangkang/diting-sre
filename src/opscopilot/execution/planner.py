"""修复动作规划器：从排障报告用 LLM 提取可执行的修复动作（供人工审批后执行）。"""
from __future__ import annotations

import json
import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ..llm import get_llm

_PROMPT = ChatPromptTemplate.from_template(
    """从下面的运维排障报告中，提取出"可执行的修复动作"。

只要确定、可立即操作的动作（如扩容副本、回滚版本、重启 Pod、kill 慢查询、调参数），
不要模糊的建议性内容。最多 3 个。

输出严格的 JSON 数组，每个元素：
{{"description":"动作的简短描述","action_type":"scale_up|rollback|restart|kill|config_change|other","target":"操作目标(服务/Pod等)","risk":"low|medium|high"}}

若没有可执行动作，返回 []。只输出 JSON 数组，不要解释。

排障报告：
{report}
"""
)


def plan_actions(report: str) -> list[dict]:
    """从报告提取可执行动作列表。"""
    if not report or not report.strip():
        return []
    chain = _PROMPT | get_llm(temperature=0.1) | StrOutputParser()
    raw = chain.invoke({"report": report[:3000]}).strip()
    # 去掉可能的 markdown 代码围栏
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw).strip()
    try:
        actions = json.loads(raw)
    except Exception:  # noqa: BLE001  LLM 输出不稳定，兜底用正则提取
        m = re.search(r"\[.*\]", raw, re.S)
        try:
            actions = json.loads(m.group()) if m else []
        except Exception:  # noqa: BLE001
            actions = []
    if not isinstance(actions, list):
        actions = []
    return [a for a in actions if isinstance(a, dict)][:3]
