"""RAG 问答链：检索 → Prompt → LLM，输出带引用溯源的答案。

引用溯源（citation）是生产级 RAG 的基本要求：答案要能指出来自哪份文档，
既增强可信度，也便于人工核查幻觉。
"""
from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ..llm import get_llm

PROMPT = ChatPromptTemplate.from_template(
    """你是一名资深 SRE / 运维专家，请严格基于下面的排查手册片段回答问题。

规则：
1. 只用提供的资料作答，禁止编造；资料不足时明确说"现有手册未覆盖该问题"。
2. 在关键结论后用 [来源n] 标注引用，n 对应资料编号。
3. 回答结构化、可直接用于排障操作。

资料：
{context}

问题：{question}

回答："""
)


def _format_context(docs: list[Any]) -> str:
    """把检索到的 chunk 拼成带编号的 context，编号即引用标号。"""
    blocks = []
    for i, d in enumerate(docs, 1):
        src = d.metadata.get("source", "?")
        blocks.append(f"[来源{i}] ({src})\n{d.page_content}")
    return "\n\n".join(blocks)


class RAGChain:
    """单轮 RAG 问答。ask() 同时返回 answer / sources / contexts。"""

    def __init__(self, retriever, llm: BaseChatModel | None = None) -> None:
        self.retriever = retriever
        self.llm = llm or get_llm(temperature=0.1)
        self._chain = PROMPT | self.llm | StrOutputParser()

    def ask(self, question: str) -> dict[str, Any]:
        docs = self.retriever.retrieve(question)
        context = _format_context(docs)
        answer = self._chain.invoke({"context": context, "question": question})
        return {
            "answer": answer,
            "question": question,
            "sources": [
                {"source": d.metadata.get("source"), "snippet": d.page_content[:120]}
                for d in docs
            ],
            "contexts": [d.page_content for d in docs],  # 供 RAGAS 评估
        }


def build_rag_chain(
    use_bm25: bool = True,
    use_rerank: bool = True,
    llm: BaseChatModel | None = None,
) -> RAGChain:
    """工厂：装配 embeddings → vectorstore → retriever → chain。

    关掉 use_bm25 / use_rerank 可得到消融对照组（用于评估脚本对比）。
    """
    from .embeddings import get_embeddings
    from .retriever import HybridRetriever, get_default_reranker
    from .vectorstore import get_vectorstore

    embeddings = get_embeddings()
    vectorstore = get_vectorstore(embeddings)
    retriever = HybridRetriever(
        vectorstore,
        use_bm25=use_bm25,
        use_rerank=use_rerank,
        reranker=get_default_reranker() if use_rerank else None,
    )
    return RAGChain(retriever, llm=llm)
