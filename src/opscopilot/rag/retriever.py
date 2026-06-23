"""混合检索 + 重排序（L2 核心深度点，面试最有故事的一层）。

三件事：
1. 混合检索：向量检索（语义）+ BM25（关键词），用 RRF 融合，
   补各自的短板——向量怕生僻关键词，BM25 怕同义改写。
2. 重排序：cross-encoder 对召回结果精排，相关性显著优于纯向量相似度。
3. 两阶段：先多召回(retrieve_top_k) 再精排取前(rerank_top_k)，
   兼顾召回率和喂给 LLM 的上下文质量/成本。

use_bm25 / use_rerank 可独立开关，便于做消融实验对比效果（面试讲：A/B 数据）。
"""
from __future__ import annotations

import logging
import re
from typing import Any

import numpy as np
from langchain_core.documents import Document

from ..config import settings

logger = logging.getLogger(__name__)

_CN_CHAR = re.compile(r"[一-龥]")


def _tokenize(text: str) -> list[str]:
    """简单分词：英文按词、中文按单字。生产中文建议换 jieba（精度更高）。"""
    return re.findall(r"[A-Za-z0-9_]+|[一-龥]", text.lower())


def reciprocal_rank_fusion(rank_lists: list[list[Document]], k: int = 60) -> list[Document]:
    """RRF：分数 = Σ 1/(k + rank)。k=60 是业界经验值，平滑头部优势。

    用 page_content 做去重键——向量召回和 BM25 召回同一 chunk 时是不同 Document
    对象，按 id 去重会导致同内容不被合并、RRF 退化为拼接；按内容合并才是真正融合。
    """
    scores: dict[str, float] = {}
    docs_by_key: dict[str, Document] = {}
    for doc_list in rank_lists:
        for rank, doc in enumerate(doc_list):
            key = doc.page_content
            docs_by_key[key] = doc
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [docs_by_key[key] for key, _ in ordered]


# -------------------------------------------------------------------- Reranker


class CrossEncoderReranker:
    """基于 sentence-transformers cross-encoder 的重排器。CPU 可跑。

    与双塔 embedding 不同：cross-encoder 把 (query, doc) 拼一起过一遍编码，
    能建模两者的交互，精度更高，但慢——所以只用来精排小批量召回结果。
    模型懒加载，避免 import 时就触发下载。
    """

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.reranker_model
        self._model: Any = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("加载 reranker 模型: %s", self.model_name)
            self._model = CrossEncoder(self.model_name)

    def rerank(self, query: str, docs: list[Document], top_k: int) -> list[Document]:
        if not docs:
            return []
        self._ensure_loaded()
        scores = self._model.predict([[query, d.page_content] for d in docs])
        order = np.argsort(scores)[::-1][:top_k]
        return [docs[i] for i in order]


class DashScopeReranker:
    """百炼 rerank（DashScope 原生接口，非 OpenAI 兼容）。

    百炼 rerank 不在 OpenAI 兼容协议里，需走专用 text-rerank 端点。
    请求: {"model","input":{"query","documents"},"parameters":{"return_documents":False,"top_n":N}}
    响应: {"output":{"results":[{"index","relevance_score"}]}}

    优点：免下载本地模型、按量计费便宜、多语言(gte-rerank-v2 / qwen3-rerank)。
    """

    def __init__(self, model: str | None = None, api_key: str | None = None, url: str | None = None) -> None:
        self.model = model or settings.dashscope_rerank_model
        self.api_key = api_key or settings.llm_api_key
        self.url = url or settings.dashscope_rerank_url

    def rerank(self, query: str, docs: list[Document], top_k: int) -> list[Document]:
        if not docs:
            return []
        import httpx

        body = {
            "model": self.model,
            "input": {"query": query, "documents": [d.page_content for d in docs]},
            "parameters": {"return_documents": False, "top_n": top_k},
        }
        r = httpx.post(
            self.url,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=30,
        )
        r.raise_for_status()
        results = r.json()["output"]["results"]  # [{index, relevance_score}]
        return [docs[item["index"]] for item in results]


def get_default_reranker():
    """按 settings.rerank_provider 返回默认 reranker（百炼 or 本地 cross-encoder）。"""
    if settings.rerank_provider == "dashscope":
        return DashScopeReranker()
    return CrossEncoderReranker()


# ------------------------------------------------------------- HybridRetriever


class HybridRetriever:
    """混合检索器：向量 + BM25 + 重排序，三路可独立开关。"""

    def __init__(
        self,
        vectorstore,
        use_bm25: bool = True,
        use_rerank: bool = True,
        reranker: CrossEncoderReranker | None = None,
    ) -> None:
        self.vectorstore = vectorstore
        self.use_bm25 = use_bm25
        self.use_rerank = use_rerank
        self.reranker = reranker or (get_default_reranker() if use_rerank else None)

        self._bm25: Any = None
        self._bm25_docs: list[Document] = []
        if use_bm25:
            self._build_bm25()

    # ---- BM25 索引 ----
    def _build_bm25(self) -> None:
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            logger.warning("rank-bm25 未安装，BM25 检索降级关闭")
            self.use_bm25 = False
            return

        data = self.vectorstore.get(include=["documents", "metadatas"])
        contents = data.get("documents", []) or []
        metas = data.get("metadatas", []) or []
        self._bm25_docs = [
            Document(page_content=t, metadata=m or {}) for t, m in zip(contents, metas)
        ]
        if not self._bm25_docs:
            logger.warning("向量库为空，BM25 无可索引内容（请先运行 ingest）")
            self._bm25 = None
            return
        tokenized = [_tokenize(d.page_content) for d in self._bm25_docs]
        self._bm25 = BM25Okapi(tokenized)

    # ---- 单路检索 ----
    def _vector_search(self, query: str, k: int) -> list[Document]:
        return self.vectorstore.similarity_search(query, k=k)

    def _bm25_search(self, query: str, k: int) -> list[Document]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        order = np.argsort(scores)[::-1][:k]
        return [self._bm25_docs[i] for i in order]

    # ---- 主入口 ----
    def retrieve(self, query: str, top_k: int | None = None) -> list[Document]:
        """检索：召回(各路 retrieve_top_k) → RRF 融合 → 精排(rerank_top_k)。"""
        target = top_k or settings.rerank_top_k
        recall_k = settings.retrieve_top_k

        rank_lists = [self._vector_search(query, recall_k)]
        if self.use_bm25:
            rank_lists.append(self._bm25_search(query, recall_k))

        fused = reciprocal_rank_fusion(rank_lists)

        if self.use_rerank and self.reranker and len(fused) > target:
            fused = self.reranker.rerank(query, fused, top_k=target)
        else:
            fused = fused[:target]
        return fused
