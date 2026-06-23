"""告警网关：接收 Alertmanager webhook → 去重分级 → 后台排障 → 播报 → 存历史。

核心流程：
  POST /api/alerts (Alertmanager payload)
    → 过滤 firing 告警 → BackgroundTasks 异步处理（webhook 立即返回 202）
    → process_alert: 去重 → 构造查询 → run_agent 排障 → 回填 → notify 播报
"""
from __future__ import annotations

import logging
import traceback

from fastapi import BackgroundTasks, FastAPI, HTTPException

from ..agents import run as run_agent
from ..notify import notify
from ..rag.embeddings import get_embeddings
from ..rag.retriever import HybridRetriever
from ..rag.vectorstore import get_vectorstore
from .models import Alert, WebhookPayload
from .store import add_incident, compute_stats, is_duplicate, list_incidents, mark_completed

logger = logging.getLogger(__name__)

_retriever = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever(get_vectorstore(get_embeddings()))
    return _retriever


def _alert_to_query(alert: Alert) -> str:
    """把告警 labels/annotations 拼成自然语言查询，喂给排障 Agent。"""
    sev = alert.labels.get("severity", "")
    name = alert.labels.get("alertname", "")
    service = alert.labels.get("service") or alert.labels.get("job", "")
    summary = alert.annotations.get("summary", "")
    desc = alert.annotations.get("description", "")
    parts = [p for p in (f"[{sev}]" if sev else "", name, service, summary, desc) if p]
    return " ".join(parts).strip() or "未命名告警"


def process_alert(alert: Alert) -> None:
    """处理单条告警（后台执行）：去重 → 排障 → 回填 → 播报。"""
    key = alert.key
    if is_duplicate(key):
        logger.info("告警去重（5分钟内重复）: %s", key)
        return

    query = _alert_to_query(alert)
    incident = add_incident(
        {
            "alertname": alert.labels.get("alertname", ""),
            "severity": alert.labels.get("severity", ""),
            "service": alert.labels.get("service") or alert.labels.get("job", ""),
            "summary": alert.annotations.get("summary", ""),
        },
        query,
    )
    logger.info("🔔 开始排障: %s", query[:80])

    try:
        state = run_agent(query, retriever=_get_retriever())
        incident["triage"] = state.get("triage", "")
        incident["evidence"] = [str(e)[:300] for e in state.get("evidence", [])]
        incident["report"] = state.get("report", "")
        incident["status"] = "resolved"
        mark_completed(incident)
    except Exception as e:  # noqa: BLE001
        incident["status"] = "error"
        incident["report"] = f"排障失败: {e}"
        logger.error("排障失败: %s\n%s", e, traceback.format_exc())

    # 知识自进化（V1 核心）：排障成功后，把结论提炼成 runbook 回写知识库
    if incident["status"] == "resolved":
        try:
            from ..evolution import evolve

            _runbook, src, n = evolve(incident, alert.labels)
            global _retriever
            _retriever = None  # 下次检索重建，让新 runbook 进入 BM25 索引
            incident["evolved"] = True
            logger.info("🧬 知识自进化: %s 入库 %d chunks", src, n)
        except Exception as e:  # noqa: BLE001  自进化失败不影响排障结果
            logger.warning("自进化失败（不影响排障结果）: %s", e)

        # V2：规划可执行修复动作（待人工审批）
        try:
            from ..execution import plan_actions

            actions = plan_actions(incident["report"])
            if actions:
                incident["pending_actions"] = actions
                incident["actions_status"] = "pending_approval"
                logger.info("🔧 规划 %d 个修复动作，待审批", len(actions))
        except Exception as e:  # noqa: BLE001
            logger.warning("动作规划失败（不影响排障结果）: %s", e)

    # 播报（配了 IM 推 IM，没配降级日志）
    title = f"告警 {alert.labels.get('alertname', '?')} 排障完成"
    body = (
        f"故障: {query}\n\n"
        f"分诊:\n{incident['triage'][:300]}\n\n"
        f"排查报告:\n{incident['report'][:800]}"
    )
    notify(title, body)
    logger.info("✅ 排障+播报完成: %s", incident["id"])


def register_routes(app: FastAPI) -> None:
    """把告警路由注册到 FastAPI app。"""

    @app.post("/api/alerts")
    async def receive_alerts(payload: WebhookPayload, bg: BackgroundTasks):
        firing = [a for a in payload.alerts if a.status == "firing"]
        for a in firing:
            bg.add_task(process_alert, a)
        return {
            "accepted": len(firing),
            "ignored_resolved": len(payload.alerts) - len(firing),
        }

    @app.get("/api/incidents")
    def get_incidents(limit: int = 50):
        return {"incidents": list_incidents(limit)}

    @app.get("/api/stats")
    def get_stats():
        from ..rag.embeddings import get_embeddings
        from ..rag.vectorstore import get_vectorstore

        s = compute_stats()
        # 知识库自增长指标
        vs = get_vectorstore(get_embeddings())
        data = vs.get(include=["metadatas"])
        auto = sum(
            1
            for m in (data.get("metadatas") or [])
            if (m or {}).get("auto_evolved") == "true"
        )
        s["total_chunks"] = vs._collection.count()
        s["auto_evolved_chunks"] = auto
        return s

    @app.post("/api/incidents/{inc_id}/approve")
    def approve_actions(inc_id: str):
        """人工审批并执行某 incident 的待执行修复动作（V2 human-in-the-loop）。"""
        from ..execution import execute_action

        inc = next((i for i in list_incidents(200) if i["id"] == inc_id), None)
        if inc is None:
            raise HTTPException(status_code=404, detail="incident 不存在")
        pending = inc.get("pending_actions") or []
        if not pending:
            raise HTTPException(status_code=400, detail="该事件无待审批的修复动作")
        results = [execute_action(a) for a in pending]
        inc["actions_results"] = results
        inc["actions_status"] = "executed"
        logger.info("✅ 已审批执行 incident %s 的 %d 个动作", inc_id, len(results))
        return {"id": inc_id, "executed": len(results), "results": results}
