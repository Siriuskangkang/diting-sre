"""修复动作执行子包（V2）：排障报告 → 提取可执行修复动作 → 人工审批 → 执行。

V2 的核心差异化：从"只给建议"升级到"能执行修复"（带人工审批）。
- 生产：用 LangGraph interrupt + checkpointer 实现真正的 human-in-the-loop（图暂停等审批）
- MVP：用"排障后生成动作→存 incident→前端审批→执行"的简化闭环，验证"从建议到行动"
"""

from .executor import execute_action  # noqa: F401
from .planner import plan_actions  # noqa: F401
