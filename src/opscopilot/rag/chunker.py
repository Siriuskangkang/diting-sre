"""文档切分：多种 chunking 策略对比（面试高频考点）。

为什么 chunking 重要：切太大 → 一个 chunk 混入多个主题，检索噪声大、token 贵；
切太小 → 语义被切断，召回不到完整上下文。运维文档天然有标题结构，按结构切最合理。
"""
from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from ..config import settings


def chunk_recursive(
    docs: list[Document],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Document]:
    """策略 A：递归字符切分。

    按 ["\\n\\n", "\\n", "。", ".", " ", ""] 优先级递归切，
    尽量在自然边界断开，是工业默认。适合通用场景。
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.chunk_size,
        chunk_overlap=chunk_overlap or settings.chunk_overlap,
        separators=["\n\n", "\n", "。", ".", "；", " ", ""],
    )
    return splitter.split_documents(docs)


def chunk_by_markdown_headers(docs: list[Document]) -> list[Document]:
    """策略 B：按 markdown 标题切分（推荐用于 runbook）。

    "现象/常见根因/排查步骤/修复方案" 各自成块，语义边界清晰。
    切完再用递归切分兜底，防止单个章节过大。
    """
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
        strip_headers=False,
    )
    out: list[Document] = []
    for d in docs:
        try:
            parts = splitter.split_text(d.page_content)
        except ValueError:
            # 文档没有任何已知标题时，split_text 可能抛错，退化为原块
            out.append(d)
            continue
        # MarkdownHeaderTextSplitter 只保留 header metadata，需补回来源 source（引用溯源依赖它）
        for p in parts:
            p.metadata = {**d.metadata, **p.metadata}
        out.extend(parts)
    # 合并标题 metadata 到后续 chunk（chunk_recursive 会自动透传 metadata）
    return chunk_recursive(out, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)


def chunk(docs: list[Document], strategy: str = "markdown") -> list[Document]:
    """统一入口：strategy ∈ {"recursive", "markdown"}."""
    if strategy == "recursive":
        return chunk_recursive(docs)
    if strategy == "markdown":
        return chunk_by_markdown_headers(docs)
    raise ValueError(f"未知 chunking 策略: {strategy}")
