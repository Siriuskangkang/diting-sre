"""把自进化生成的 runbook 入库（复用 RAG 的 chunk/embed/vectorstore 管道）。"""
from __future__ import annotations

from langchain_core.documents import Document

from ..rag.chunker import chunk
from ..rag.embeddings import get_embeddings
from ..rag.vectorstore import add_documents, get_vectorstore


def ingest_runbook(content: str, source: str) -> int:
    """把 runbook 文本切分 + 向量化 + 入库，返回 chunk 数。

    metadata 标记 auto_evolved=true，便于区分人工文档与自动沉淀的知识。
    """
    docs = [Document(page_content=content, metadata={"source": source, "auto_evolved": "true"})]
    chunks = chunk(docs, strategy="markdown")
    vectorstore = get_vectorstore(get_embeddings())
    add_documents(vectorstore, chunks)
    return len(chunks)
