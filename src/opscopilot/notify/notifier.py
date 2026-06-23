"""统一播报器：把排障结果推到飞书 / 钉钉 / Slack。

设计：配置驱动 + 优雅降级——哪个 webhook 配了就推哪个；都没配则只写日志
（保证 MVP 在无 IM 配置时也能跑通闭环，结果在 Web 控制台/日志查看）。
"""
from __future__ import annotations

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


def _send_feishu(text: str) -> bool:
    if not settings.feishu_webhook:
        return False
    httpx.post(
        settings.feishu_webhook,
        json={"msg_type": "text", "content": {"text": text}},
        timeout=10,
    )
    return True


def _send_dingtalk(text: str) -> bool:
    if not settings.dingtalk_webhook:
        return False
    httpx.post(
        settings.dingtalk_webhook,
        json={"msgtype": "text", "text": {"content": text}},
        timeout=10,
    )
    return True


def _send_slack(text: str) -> bool:
    if not settings.slack_webhook:
        return False
    httpx.post(settings.slack_webhook, json={"text": text}, timeout=10)
    return True


_CHANNELS = [("feishu", _send_feishu), ("dingtalk", _send_dingtalk), ("slack", _send_slack)]


def notify(title: str, body: str) -> list[str]:
    """推送到所有已配置的渠道，返回成功推送的渠道名列表。

    全都没配置时降级写日志（MVP 仍可运行）。
    """
    text = f"【谛听 DiTing · {title}】\n{body}"
    sent: list[str] = []
    for name, fn in _CHANNELS:
        try:
            if fn(text):
                sent.append(name)
        except Exception as e:  # noqa: BLE001  推送失败不影响主流程
            logger.warning("%s 推送失败: %s", name, e)
    if not sent:
        logger.info("[播报降级 · 仅日志]\n%s", text)
    return sent
