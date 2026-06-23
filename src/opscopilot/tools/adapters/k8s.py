"""k8s 适配器：配了 K8S_IN_CLUSTER=true 走真查询，没配 mock 兜底。

生产用 kubernetes client；为避免重依赖，仅 in-cluster 时才 import。无配置时 mock。
"""
from __future__ import annotations

import logging

from ...config import settings

logger = logging.getLogger(__name__)


def get_pods(service: str, namespace: str = "default") -> str:
    """查 Pod 状态。in-cluster 走真查询；否则 mock。"""
    if not settings.k8s_in_cluster:
        logger.info("[mock] k8s 未配置 K8S_IN_CLUSTER")
        return (
            f"{service} Pod 状态:\n"
            f"  READY 1/1  STATUS CrashLoopBackOff  RESTARTS 9\n"
            f"  Last State: Terminated (Reason=OOMKilled, Exit Code=137)\n"
            f"  Liveness probe failed: HTTP 500 (initialDelaySeconds=10s 过短)"
        )

    try:
        from kubernetes import client, config  # type: ignore

        config.load_incluster_config()
        v1 = client.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace, label_selector=f"app={service}")
        if not pods.items:
            return f"namespace {namespace} 下无 app={service} 的 Pod"
        lines = ["NAME\tREADY\tSTATUS\tRESTARTS"]
        for p in pods.items:
            ready = f"{sum(1 for c in (p.status.container_statuses or []) if c.ready)}/{len(p.spec.containers)}"
            lines.append(f"{p.metadata.name}\t{ready}\t{p.status.phase}\t{p.status.container_statuses[0].restart_count if p.status.container_statuses else 0}")
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        logger.warning("k8s 查询失败，降级 mock: %s", e)
        return f"[k8s 查询失败: {e}] {service} Pod 状态暂不可用"
