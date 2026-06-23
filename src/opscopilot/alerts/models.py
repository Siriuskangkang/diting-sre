"""Alertmanager webhook payload 模型（标准格式，兼容夜莺/Prometheus Alertmanager）。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Alert(BaseModel):
    """单条告警。"""

    status: str = "firing"  # firing / resolved
    labels: dict[str, str] = Field(default_factory=dict)  # alertname / service / severity ...
    annotations: dict[str, str] = Field(default_factory=dict)  # summary / description
    startsAt: str | None = None
    endsAt: str | None = None
    generatorURL: str | None = None
    fingerprint: str | None = None

    @property
    def key(self) -> str:
        """去重用的稳定 key：fingerprint 优先，否则 alertname+service。"""
        if self.fingerprint:
            return self.fingerprint
        return f"{self.labels.get('alertname', '')}:{self.labels.get('service', self.labels.get('job', ''))}"


class WebhookPayload(BaseModel):
    """Alertmanager webhook 整体 payload。"""

    version: str = "4"
    groupKey: str = ""
    status: str = "firing"
    receiver: str = ""
    groupLabels: dict[str, str] = Field(default_factory=dict)
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)
    externalURL: str = ""
    alerts: list[Alert] = Field(default_factory=list)
