"""模拟 Alertmanager 告警，触发谛听 DiTing 排障闭环（无需真实 Prometheus）。

用法:
  python scripts/trigger_alert.py            # 默认：5xx 告警
  python scripts/trigger_alert.py oom         # OOM 告警
  python scripts/trigger_alert.py latency     # 延迟告警
  python scripts/trigger_alert.py dbpool      # 连接池耗尽

触发后访问 http://127.0.0.1:8000 切到「告警排障」Tab 查看，或 GET /api/incidents。
"""
from __future__ import annotations

import json
import sys
import urllib.request

URL = "http://127.0.0.1:8000/api/alerts"

ALERTS = {
    "5xx": {
        "alertname": "High5xxRate", "service": "order-service", "severity": "critical",
        "summary": "order-service 5xx 错误率飙升至 5.6%",
        "description": "订单服务 5xx 飙升，伴随 Pod CrashLoopBackOff 与 OOMKilled，疑似连接池耗尽",
    },
    "oom": {
        "alertname": "PodOOMKilled", "service": "order-service", "severity": "critical",
        "summary": "order-service Pod OOMKilled",
        "description": "容器反复 OOMKilled，Exit Code 137，疑似内存泄漏",
    },
    "latency": {
        "alertname": "HighLatency", "service": "payment-service", "severity": "warning",
        "summary": "payment-service P99 延迟飙升至 870ms",
        "description": "P99 突增但成功率未降，疑似慢 SQL 与热点行锁",
    },
    "dbpool": {
        "alertname": "DBConnPoolExhausted", "service": "order-service", "severity": "critical",
        "summary": "order-service 数据库连接池耗尽",
        "description": "Cannot get a connection，连接池 active 满，疑似连接泄漏",
    },
}


def main() -> None:
    kind = sys.argv[1] if len(sys.argv) > 1 else "5xx"
    a = ALERTS.get(kind, ALERTS["5xx"])
    payload = {
        "version": "4", "groupKey": "{}", "status": "firing",
        "alerts": [{
            "status": "firing",
            "labels": {"alertname": a["alertname"], "service": a["service"], "severity": a["severity"]},
            "annotations": {"summary": a["summary"], "description": a["description"]},
            "fingerprint": f"mock-{kind}",
        }],
    }
    req = urllib.request.Request(
        URL, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        r = urllib.request.urlopen(req, timeout=10)
        print(f"✅ 已触发 [{kind}] 告警 → {r.read().decode()}")
        print("谛听正在后台排障，约 30–60s 后：")
        print("  · 浏览器: http://127.0.0.1:8000 → 「告警排障」Tab")
        print("  · API:    curl http://127.0.0.1:8000/api/incidents")
    except Exception as e:  # noqa: BLE001
        print(f"❌ 触发失败（确认 FastAPI 在 8000 运行）: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
