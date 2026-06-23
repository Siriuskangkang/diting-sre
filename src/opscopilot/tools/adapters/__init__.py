"""工具适配器：配置驱动——有基础设施 URL 就查真，没配置则 mock 兜底。

这是 MVP 可运行的关键设计：用户没有真实 Prometheus/Loki/k8s 时也能跑通闭环（mock），
配上 URL 就自动切到真实查询。面试讲点：适配器模式 + 优雅降级。
"""

from . import k8s, loki, prometheus  # noqa: F401
