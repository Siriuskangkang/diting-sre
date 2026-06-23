"""文档加载：把 runbook 知识库读成 LangChain Document。

面试点：加载阶段就要把"来源"写进 metadata，下游引用溯源和评估都依赖它。
不要等检索时再猜出处。
"""
from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from ..config import RUNBOOK_DIR


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_documents(directory: Path | None = None) -> list[Document]:
    """加载目录下所有 .md/.txt 文档为 Document 列表。

    每个文档 metadata 记录来源文件名（source）和路径（path），
    供后续引用溯源、评估、去重使用。
    """
    directory = directory or RUNBOOK_DIR
    if not directory.exists():
        return []

    docs: list[Document] = []
    for pattern in ("**/*.md", "**/*.txt"):
        for path in sorted(directory.glob(pattern)):
            docs.append(
                Document(
                    page_content=_read_text(path),
                    metadata={"source": path.name, "path": str(path)},
                )
            )
    return docs


def load_single_pdf(path: Path) -> list[Document]:
    """可选：加载 PDF（扩展知识库时用）。需要 pypdf。"""
    from langchain_community.document_loaders import PyPDFLoader

    return PyPDFLoader(str(path)).load()
