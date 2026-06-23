"""Prometheus 适配器：配了 PROMETHEUS_URL 走真 PromQL 查询，没配 mock 兜底。"""
from __future__ import annotations

import logging

import httpx

from ...config import settings

logger = logging.getLogger(__name__)

# 语义指标名 → PromQL 模板（{s} = service）
_METRIC_TO_PROMQL = {
    "http_5xx_rate": 'sum(rate(http_requests_total{{service="{s}",status=~"5.."}}[5m])) by (service)',
    "p99_latency": 'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{service="{s}"}}[5m])) by (le))',
    "cpu_usage": 'avg(rate(container_cpu_usage_seconds_total{{pod=~"{s}.*"}}[5m])) by (pod)',
    "memory_usage": 'avg(container_memory_usage_bytes{{pod=~"{s}.*"}}) by (pod)',
    "db_connections": 'avg(db_connection_pool_active{{service="{s}"}}) by (service)',
}

_MOCK = {
    "http_5xx_rate": "{s} 近30min 5xx 率: 0.1% -> 5.6% (15:03 突增)",
    "p99_latency": "{s} 近30min P99: 82ms -> 870ms (持续走高)",
    "cpu_usage": "{s} 近30min CPU: 均值 88%, 峰值 97%",
    "memory_usage": "{s} 近30min 内存: 1.6G/2G limit (80%+), OOMKilled 3 次",
    "db_connections": "{s} 近30min DB连接: active=50/50(满), 等待线程 12",
}


def query_metric(metric_name: str, service: str) -> str:
    """查指标。配了 PROMETHEUS_URL 走真查询；否则 mock。"""
    if not settings.prometheus_url:
        logger.info("[mock] Prometheus 未配置 PROMETHEUS_URL")
        return _MOCK.get(metric_name, f"{service} {metric_name}: [mock] 暂无数据").format(s=service)

    promql = _METRIC_TO_PROMQL.get(metric_name, f'{metric_name}{{service="{service}"}}').format(s=service)
    try:
        r = httpx.get(
            f"{settings.prometheus_url}/api/v1/query",
            params={"query": promql},
            timeout=15,
        )
        r.raise_for_status()
        results = r.json().get("data", {}).get("result", [])
        if not results:
            return f"PromQL `{promql}` 无数据"
        lines = []
        for item in results[:10]:
            metric = item.get("metric", {})
            val = item.get("value", [None, "N/A"])[1]
            labels = ",".join(f"{k}={v}" for k, v in metric.items() if k != "__name__")
            name = metric.get("__name__", metric_name)
            lines.append(f"{name}{{{labels}}} = {val}")
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001  查询失败降级 mock，不阻断排障
        logger.warning("Prometheus 查询失败，降级 mock: %s", e)
        return f"[Prometheus 查询失败: {e}] " + _MOCK.get(metric_name, "").format(s=service)
