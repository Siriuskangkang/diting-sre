"""Embedding 工厂：百炼(OpenAI 兼容) 或 本地(sentence-transformers)。

百炼坑：langchain 官方 OpenAIEmbeddings 会用 tiktoken 分块，传给百炼会触发
"input.contents is neither str nor list" 错误。这里自写一个 Embeddings 子类，
直接用 openai SDK 调兼容端点，绕过 tiktoken 分块，稳定可靠。
"""
from __future__ import annotations

from langchain_core.embeddings import Embeddings

from ..config import settings


class DashScopeCompatibleEmbeddings(Embeddings):
    """直接调百炼 OpenAI 兼容 embedding 端点（绕过 langchain tiktoken 分块）。

    百炼 text-embedding-v3 默认 1024 维，单次最多 10 条 input。
    """

    def __init__(self, model: str, api_key: str, base_url: str, batch_size: int = 10) -> None:
        from openai import OpenAI

        self.model = model
        self.batch_size = batch_size
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            resp = self.client.embeddings.create(model=self.model, input=batch)
            out.extend(d.embedding for d in resp.data)
        return out

    def embed_query(self, text: str) -> list[float]:
        resp = self.client.embeddings.create(model=self.model, input=text)
        return resp.data[0].embedding


def get_embeddings() -> Embeddings:
    """按 EMBEDDING_PROVIDER 返回 embedding 实例。"""
    if settings.embedding_provider == "openai":
        return DashScopeCompatibleEmbeddings(
            model=settings.embedding_model_openai,
            api_key=settings.embedding_api_key or settings.llm_api_key,
            base_url=settings.embedding_base_url or settings.llm_base_url,
        )
    # 默认本地，免 key、可离线
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model_local,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
