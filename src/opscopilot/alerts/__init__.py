"""告警子包：接收 Alertmanager webhook → 去重分级 → 后台排障 → 播报 → 存历史。"""

from .gateway import process_alert, register_routes  # noqa: F401
from .models import Alert, WebhookPayload  # noqa: F401
from .store import list_incidents  # noqa: F401
