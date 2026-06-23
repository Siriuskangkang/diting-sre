"""RAG 子包：文档加载 → 切分 → 向量化 → 检索(混合+重排) → 引用溯源问答。"""

from .chain import RAGChain, build_rag_chain  # noqa: F401
from .retriever import HybridRetriever  # noqa: F401
