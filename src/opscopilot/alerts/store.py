"""incidents 内存存储 + 去重（MVP 用内存；生产换 DB）。"""
from __future__ import annotations

import time

_DEDUP_WINDOW = 300  # 5 分钟内相同告警去重
_seen: dict[str, float] = {}
_incidents: list[dict] = []


def is_duplicate(key: str) -> bool:
    now = time.time()
    last = _seen.get(key)
    if last is not None and now - last < _DEDUP_WINDOW:
        return True
    _seen[key] = now
    return False


def add_incident(alert_dict: dict, query: str) -> dict:
    incident = {
        "id": f"inc-{int(time.time() * 1000)}",
        "alertname": alert_dict.get("alertname", ""),
        "severity": alert_dict.get("severity", ""),
        "service": alert_dict.get("service", ""),
        "summary": alert_dict.get("summary", ""),
        "query": query,
        "status": "investigating",
        "created_at": time.time(),
        "completed_at": None,
        "triage": "",
        "evidence": [],
        "report": "",
    }
    _incidents.insert(0, incident)  # 最新的在前
    if len(_incidents) > 200:  # 防止无限增长
        _incidents[:] = _incidents[:200]
    return incident


def update_incident(incident: dict) -> None:
    """原地更新（gateway 排障完成后回填）。"""
    # incident 是 add_incident 返回的同一引用，已在列表中，无需额外操作
    pass


def list_incidents(limit: int = 50) -> list[dict]:
    return _incidents[:limit]


def mark_completed(incident: dict) -> None:
    """排障完成时调用，记录完成时间用于算 MTTR。"""
    incident["completed_at"] = time.time()


def compute_stats() -> dict:
    """评估看板数据：告警总量/成功率/平均MTTR/自进化篇数。"""
    total = len(_incidents)
    resolved = [i for i in _incidents if i.get("status") == "resolved"]
    mttrs = [
        i["completed_at"] - i["created_at"]
        for i in resolved
        if i.get("completed_at")
    ]
    avg_mttr = sum(mttrs) / len(mttrs) if mttrs else 0.0
    evolved = sum(1 for i in _incidents if i.get("evolved"))
    return {
        "total_incidents": total,
        "resolved": len(resolved),
        "failed": sum(1 for i in _incidents if i.get("status") == "error"),
        "success_rate": round(len(resolved) / total, 3) if total else 0.0,
        "avg_mttr_seconds": round(avg_mttr, 1),
        "evolved_runbooks": evolved,
    }
