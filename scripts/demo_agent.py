"""Multi-Agent 排障 demo (L4)。

运行:
  python scripts/demo_agent.py                                # 交互式
  python scripts/demo_agent.py "订单服务 5xx 错误率飙升"        # 单次

流程: Triage → Investigate(自主调工具) → Report，全自动输出排查报告。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402

from opscopilot.agents import run as run_agent  # noqa: E402
from opscopilot.rag.embeddings import get_embeddings  # noqa: E402
from opscopilot.rag.retriever import HybridRetriever  # noqa: E402
from opscopilot.rag.vectorstore import get_vectorstore  # noqa: E402

console = Console()


def build_retriever() -> HybridRetriever:
    return HybridRetriever(get_vectorstore(get_embeddings()))


def handle(question: str, retriever: HybridRetriever) -> None:
    console.rule(f"[bold cyan]故障: {question}")
    with console.status("[cyan]Agent 排障中 (triage → investigate → report)...[/]"):
        state = run_agent(question, retriever=retriever)

    console.print(Panel(state.get("triage", ""), title="① 分诊", border_style="yellow"))
    evidence = state.get("evidence", [])
    console.print(
        Panel(
            "\n---\n".join(evidence) or "(无)",
            title=f"② 证据 ({len(evidence)} 条)",
            border_style="blue",
        )
    )
    console.print(Panel(state.get("report", ""), title="③ 排查报告", border_style="green"))
    console.print()


def main() -> None:
    console.print("[bold green]OpsCopilot · Multi-Agent 排障[/]  (输入 quit 退出)\n")
    retriever = build_retriever()

    # 支持命令行直传一次性查询
    inline = " ".join(sys.argv[1:]).strip()
    if inline:
        handle(inline, retriever)
        return

    while True:
        q = console.input("[bold cyan]故障描述> [/]").strip()
        if q.lower() in {"quit", "exit", "q"}:
            break
        if not q:
            continue
        handle(q, retriever)


if __name__ == "__main__":
    main()
