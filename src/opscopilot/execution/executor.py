"""修复动作执行器：mock 执行审批通过的修复动作。

生产环境接真 kubectl / 云 API（带 RBAC + 审计 + 回滚预案）；
MVP 用 mock 模拟执行结果，验证"审批→执行"闭环。
"""
from __future__ import annotations

_MOCK_RESULT = {
    "scale_up": "✓ 已扩容：副本 3 → 5，新 Pod 已 Ready，负载下降",
    "rollback": "✓ 已回滚：部署到上一稳定版本，5xx 错误率恢复至 0.1%",
    "restart": "✓ 已重启：Pod 重新拉起，状态 Running",
    "kill": "✓ 已终止：慢查询/长事务已 kill，连接池释放",
    "config_change": "✓ 已调整配置：参数已生效，指标改善",
}


def execute_action(action: dict) -> dict:
    """执行单个修复动作（mock），返回执行结果。"""
    action_type = action.get("action_type", "other")
    desc = action.get("description", "")
    result = _MOCK_RESULT.get(action_type, f"✓ 已执行：{desc}")
    return {
        "action_type": action_type,
        "description": desc,
        "target": action.get("target", ""),
        "risk": action.get("risk", "unknown"),
        "result": result,
        "status": "done",
    }
