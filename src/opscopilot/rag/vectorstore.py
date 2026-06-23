"""向量库：Chroma 本地持久化。

为什么 Chroma 起步：零运维、本地文件持久化、API 简单，适合学习和中小项目。
生产可平滑切换 Qdrant / Milvus / pgvector，只需换 get_vectorstore 实现。
"""
from __future__ import annotations

from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from ..config import settings


def get_vectorstore(embeddings) -> Chroma:
    """返回一个 Chroma 实例（同一个 collection 名 = 同一个知识库）。"""
    Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=settings.chroma_collection,
        embedding_function=embeddings,
        persist_directory=settings.chroma_persist_dir,
    )


def add_documents(vectorstore: Chroma, docs: list[Document]) -> None:
    """入库（去重：相同内容重复入库会产生重复 chunk，ingest 脚本会先清空）。"""
    if docs:
        vectorstore.add_documents(docs)


def reset_vectorstore(vectorstore: Chroma) -> None:
    """清空 collection（ingest 全量重建时用）。"""
    try:
        vectorstore.delete_collection()
    except Exception:  # noqa: BLE001  首次运行时 collection 还不存在
        pass
