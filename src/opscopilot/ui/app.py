"""Gradio 界面：RAG 知识库问答 + Multi-Agent 排障 两个 Tab。

运行:
  python -m opscopilot.ui.app
  python src/opscopilot/ui/app.py

首次提问时才懒加载 chain / agent（启动快、无 key 时不报错）。
"""
from __future__ import annotations

import logging

import gradio as gr

from ..agents import run as run_agent
from ..rag.chain import build_rag_chain
from ..rag.embeddings import get_embeddings
from ..rag.retriever import HybridRetriever
from ..rag.vectorstore import get_vectorstore

logger = logging.getLogger(__name__)

_rag_chain = None
_retriever = None


def _get_rag():
    global _rag_chain
    if _rag_chain is None:
        _rag_chain = build_rag_chain()
    return _rag_chain


def _get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever(get_vectorstore(get_embeddings()))
    return _retriever


def rag_answer(question: str) -> tuple[str, str]:
    if not question.strip():
        return "请输入问题", ""
    res = _get_rag().ask(question)
    srcs = (
        "\n".join(f"- {s['source']}: {s['snippet']}..." for s in res["sources"])
        or "无"
    )
    return res["answer"], srcs


def agent_report(question: str) -> tuple[str, str, str]:
    if not question.strip():
        return "请输入故障描述", "", ""
    state = run_agent(question, retriever=_get_retriever())
    evidence = "\n---\n".join(state.get("evidence", [])) or "(无)"
    return state.get("triage", ""), evidence, state.get("report", "")


def kb_status() -> str:
    """返回当前知识库 chunk 数。"""
    try:
        vs = get_vectorstore(get_embeddings())
        return f"当前知识库共 **{vs._collection.count()}** 个 chunk"
    except Exception as e:  # noqa: BLE001
        return f"读取失败: {e}"


def _invalidate_caches() -> None:
    """入库/清空后，让下次问答重建检索器（否则新内容进不了 BM25 索引）。"""
    global _rag_chain, _retriever
    _rag_chain = None
    _retriever = None


def add_to_kb(files: list, text: str) -> str:
    """上传文件 + 粘贴文本 → 切分 → 入库。新增内容立即可被 RAG 检索到。"""
    from pathlib import Path

    from langchain_core.documents import Document

    from ..rag.chunker import chunk
    from ..rag.vectorstore import add_documents

    docs: list[Document] = []
    if files:
        for f in files:
            fpath = f if isinstance(f, str) else getattr(f, "name", str(f))
            try:
                content = Path(fpath).read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
            orig = getattr(f, "orig_name", None) or Path(fpath).name
            docs.append(Document(page_content=content, metadata={"source": Path(orig).name}))
    if text and text.strip():
        docs.append(Document(page_content=text.strip(), metadata={"source": "网页粘贴文本"}))
    if not docs:
        return "⚠️ 请上传 .md/.txt 文件或粘贴文本后再入库"

    chunks = chunk(docs, strategy="markdown")
    vs = get_vectorstore(get_embeddings())
    add_documents(vs, chunks)
    _invalidate_caches()
    return f"✅ 入库 {len(docs)} 篇 → {len(chunks)} 个 chunk\n\n" + kb_status()


def reset_kb() -> str:
    """清空知识库。"""
    from ..rag.vectorstore import reset_vectorstore

    vs = get_vectorstore(get_embeddings())
    reset_vectorstore(vs)
    get_vectorstore(get_embeddings())  # 重建空 collection
    _invalidate_caches()
    return "🗑 已清空知识库\n\n" + kb_status()


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="OpsCopilot") as demo:
        gr.Markdown("# 🛠 OpsCopilot — 多 Agent 智能运维助手\nRAG 深度优化 + Tool Calling + 自研 MCP + LangGraph 多 Agent 编排")

        with gr.Tab("📚 RAG 知识库问答"):
            q = gr.Textbox(label="问题", placeholder="例：线上服务 5xx 突然飙升怎么排查？")
            btn = gr.Button("提问", variant="primary")
            ans = gr.Textbox(label="回答", lines=10)
            src = gr.Textbox(label="引用来源", lines=6)
            btn.click(rag_answer, inputs=q, outputs=[ans, src])

        with gr.Tab("🤖 Multi-Agent 排障"):
            gr.Markdown("输入故障描述，Agent 自动 **分诊 → 调工具取证 → 生成报告**")
            q2 = gr.Textbox(label="故障描述", lines=3, placeholder="例：订单服务 5xx 错误率突然飙升")
            btn2 = gr.Button("开始排障", variant="primary")
            triage = gr.Textbox(label="① 分诊", lines=6)
            ev = gr.Textbox(label="② 证据", lines=8)
            rep = gr.Textbox(label="③ 排查报告", lines=12)
            btn2.click(agent_report, inputs=q2, outputs=[triage, ev, rep])

        with gr.Tab("🗂 知识库管理"):
            gr.Markdown(
                "上传 `.md`/`.txt` 文件或直接粘贴文本入库。**新增内容立即可在「RAG 问答」检索到。**\n"
                "切分策略：按 markdown 标题切（无标题则按段落切）。"
            )
            file_in = gr.File(
                label="上传文档(可多选)", file_count="multiple", file_types=[".md", ".txt"]
            )
            text_in = gr.Textbox(
                label="或直接粘贴文本", lines=6, placeholder="粘贴要入库的文本内容…"
            )
            with gr.Row():
                add_btn = gr.Button("➕ 入库", variant="primary")
                reset_btn = gr.Button("🗑 清空知识库")
            kb_out = gr.Markdown(kb_status())
            add_btn.click(add_to_kb, inputs=[file_in, text_in], outputs=kb_out)
            reset_btn.click(reset_kb, outputs=kb_out)

    return demo


def main() -> None:
    build_ui().launch()


if __name__ == "__main__":
    main()
