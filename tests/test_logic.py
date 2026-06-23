"""纯逻辑单元测试（不依赖 LLM / 向量库 / 网络），装好依赖即可 pytest 直接跑。"""
from __future__ import annotations

from langchain_core.documents import Document

from opscopilot.rag import chunker
from opscopilot.rag.retriever import _tokenize, reciprocal_rank_fusion


def _doc(text: str) -> Document:
    return Document(page_content=text, metadata={"source": "t.md"})


# ---------------- RRF ----------------


def test_rrf_prefers_doc_early_in_multiple_lists():
    a = [_doc("x"), _doc("y"), _doc("z")]
    b = [_doc("y"), _doc("w"), _doc("x")]
    fused = reciprocal_rank_fusion([a, b])
    # "y" 在两路都靠前，融合后应排第一
    assert fused[0].page_content == "y"


def test_rrf_single_list_preserves_order():
    a = [_doc("a"), _doc("b"), _doc("c")]
    fused = reciprocal_rank_fusion([a])
    assert [d.page_content for d in fused] == ["a", "b", "c"]


def test_rrf_empty_input():
    assert reciprocal_rank_fusion([]) == []


# ---------------- tokenize ----------------


def test_tokenize_mixed_cn_en():
    assert _tokenize("OOM Killed 异常") == ["oom", "killed", "异", "常"]


def test_tokenize_lowercase_and_digits():
    assert _tokenize("HTTP 5xx 503") == ["http", "5xx", "503"]


# ---------------- chunker ----------------


def test_chunk_recursive_splits_long_text():
    long = "正文章节。\n\n" * 50
    docs = [Document(page_content=long, metadata={"source": "x.md"})]
    chunks = chunker.chunk_recursive(docs, chunk_size=100, chunk_overlap=10)
    assert len(chunks) > 1
    # metadata 应透传到每个 chunk
    assert all(c.metadata.get("source") == "x.md" for c in chunks)


def test_chunk_unknown_strategy_raises():
    try:
        chunker.chunk([_doc("a")], strategy="nope")
        assert False, "应抛 ValueError"
    except ValueError:
        pass
