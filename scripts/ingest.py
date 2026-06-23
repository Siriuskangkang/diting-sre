"""文档入库：加载 runbook → chunking → embedding → 存入 Chroma 向量库。

运行:
  python scripts/ingest.py                      # 增量入库（markdown 结构切分）
  python scripts/ingest.py --strategy recursive # 改用递归字符切分
  python scripts/ingest.py --reset              # 清空后全量重建

首次使用、修改文档、或换 embedding 模型后，都要重新 ingest。
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from opscopilot.config import settings  # noqa: E402
from opscopilot.rag.chunker import chunk  # noqa: E402
from opscopilot.rag.embeddings import get_embeddings  # noqa: E402
from opscopilot.rag.loader import load_documents  # noqa: E402
from opscopilot.rag.vectorstore import add_documents, get_vectorstore, reset_vectorstore  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ingest")


def main() -> None:
    ap = argparse.ArgumentParser(description="OpsCopilot 文档入库")
    ap.add_argument("--strategy", default="markdown", choices=["markdown", "recursive"])
    ap.add_argument("--reset", action="store_true", help="清空后全量重建")
    args = ap.parse_args()

    docs = load_documents()
    logger.info("加载 %d 篇文档", len(docs))
    if not docs:
        logger.warning("没有文档可入库，请检查 data/runbooks/ 目录")
        return

    chunks = chunk(docs, strategy=args.strategy)
    logger.info("切分成 %d 个 chunk (strategy=%s)", len(chunks), args.strategy)

    embeddings = get_embeddings()
    vectorstore = get_vectorstore(embeddings)
    if args.reset:
        reset_vectorstore(vectorstore)
        logger.info("已清空旧 collection")
        vectorstore = get_vectorstore(embeddings)  # 重新实例化，触发 get_or_create
    add_documents(vectorstore, chunks)
    logger.info("入库完成 ✓  向量库: %s", settings.chroma_persist_dir)


if __name__ == "__main__":
    main()
