"""知识自进化子包：排障结论 → LLM 提炼成 runbook → 回写知识库。

这是谛听的核心壁垒——知识库随使用自增长（数据飞轮）：
  排障 Report → LLM 提炼 → 新 runbook → 入库 → 下次同类故障可检索复用
"""

from .ingestor import ingest_runbook  # noqa: F401
from .summarizer import summarize_to_runbook  # noqa: F401


def evolve(incident: dict, alert_labels: dict) -> tuple[str, str, int]:
    """编排：把一次排障结果提炼成 runbook 并入库。

    Returns: (runbook_markdown, source_name, chunks_added)
    """
    import time

    runbook = summarize_to_runbook(
        alert_info=incident.get("query", ""),
        triage=incident.get("triage", ""),
        evidence=incident.get("evidence", []),
        report=incident.get("report", ""),
    )
    source = f"auto:{alert_labels.get('alertname', 'incident')}:{int(time.time())}"
    n = ingest_runbook(runbook, source)

    # 回填到 incident，供前端展示「已沉淀为知识」
    incident["evolved_source"] = source
    incident["evolved_chunks"] = n
    return runbook, source, n
