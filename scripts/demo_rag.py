"""RAG 单轮问答 demo (L1/L2)。

运行: python scripts/demo_rag.py
交互式问答，返回带引用溯源的答案。默认开启 混合检索 + 重排序（L2 完整版）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402

from opscopilot.rag.chain import build_rag_chain  # noqa: E402

console = Console()
EXAMPLES = [
    "线上服务 5xx 突然飙到 5%，怎么排查？",
    "Pod 一直 CrashLoopBackOff 不停重启怎么办？",
    "Redis 内存满了 evicted_keys 狂涨，怎么处理？",
    "接口 P99 从 80ms 涨到 800ms 但成功率没掉，什么原因？",
]


def main() -> None:
    console.print("[bold green]OpsCopilot · RAG 知识库问答[/]  (输入 quit 退出)")
    console.print(f"[dim]示例: {EXAMPLES}[/]\n")
    chain = build_rag_chain()  # 默认全开：BM25 + Rerank
    while True:
        q = console.input("[bold cyan]问题> [/]").strip()
        if q.lower() in {"quit", "exit", "q"}:
            break
        if not q:
            continue
        with console.status("[cyan]检索 + 生成中...[/]"):
            res = chain.ask(q)
        console.print(Panel(res["answer"], title="回答", border_style="green"))
        if res["sources"]:
            srcs = ", ".join(s["source"] for s in res["sources"])
            console.print(f"[dim]引用来源: {srcs}[/]")
        console.print()


if __name__ == "__main__":
    main()
