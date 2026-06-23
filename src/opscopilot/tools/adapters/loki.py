"""Loki 适配器：配了 LOKI_URL 走真 LogQL 查询，没配 mock 兜底。"""
from __future__ import annotations

import logging
import time

import httpx

from ...config import settings

logger = logging.getLogger(__name__)


def query_logs(service: str, keyword: str, level: str = "ERROR", limit: int = 20) -> str:
    """查日志。配了 LOKI_URL 走真查询；否则 mock。"""
    if not settings.loki_url:
        logger.info("[mock] Loki 未配置 LOKI_URL")
        return (
            f"[{level}] {service} 日志命中 '{keyword}':\n"
            f"  15:03:12 NullPointerException at DbPool.acquire(DbPool.java:88)\n"
            f"  15:03:13 '{keyword}' 累计出现 1247 次\n"
            f"  15:03:15 Connection wait timeout after 30000ms"
        )

    logql = f'{{service="{service}"}}|~"{keyword}"'
    now = int(time.time())
    start = now - 1800  # 近 30 分钟
    try:
        r = httpx.get(
            f"{settings.loki_url}/loki/api/v1/query_range",
            params={"query": logql, "start": str(start), "end": str(now), "limit": limit},
            timeout=15,
        )
        r.raise_for_status()
        results = r.json().get("data", {}).get("result", [])
        if not results:
            return f"LogQL `{logql}` 无数据"
        lines = []
        for stream in results[:5]:
            for ts, line in stream.get("values", [])[:limit]:
                lines.append(f"{line}")
        return "\n".join(lines[:limit]) or "无日志"
    except Exception as e:  # noqa: BLE001
        logger.warning("Loki 查询失败，降级 mock: %s", e)
        return f"[Loki 查询失败: {e}] {service} '{keyword}' 日志暂不可用"
