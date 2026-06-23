"""FastAPI 后端：暴露 RAG / Agent / 知识库 REST API，并托管前端静态文件。

把 Gradio 换成 REST + OD 设计的自定义前端。复用 rag/ (问答) 与 agents/ (排障) 核心。

运行:
  uvicorn opscopilot.api:app --port 8001 --reload
  或: python -m opscopilot.api
"""
from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from langchain_core.documents import Document
from langchain_core.messages import ToolMessage
from pydantic import BaseModel

from .agents import run as run_agent
from .alerts import register_routes as register_alert_routes
from .config import settings
from .rag.chain import build_rag_chain
from .rag.chunker import chunk
from .rag.file_parser import extract_text
from .rag.embeddings import get_embeddings
from .rag.retriever import HybridRetriever
from .rag.vectorstore import add_documents, get_vectorstore, reset_vectorstore

logger = logging.getLogger(__name__)
WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(title="OpsCopilot API")

# 懒加载单例（首次请求才初始化，启动快）
_rag_chain: Any = None
_retriever: Any = None


def get_rag():
    global _rag_chain
    if _rag_chain is None:
        _rag_chain = build_rag_chain()
    return _rag_chain


def get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever(get_vectorstore(get_embeddings()))
    return _retriever


def _invalidate():
    """入库/清空后让下次请求重建（新内容进 BM25 索引）。"""
    global _rag_chain, _retriever
    _rag_chain = None
    _retriever = None


# ---------------------------------------------------------------- models


class ChatReq(BaseModel):
    message: str
    mode: str = "hybrid"  # 前端检索模式 chip（视觉用）；后端默认混合+重排全开


class AgentReq(BaseModel):
    query: str


# ---------------------------------------------------------------- chat


@app.post("/api/chat")
def chat(req: ChatReq) -> dict[str, Any]:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message 不能为空")
    res = get_rag().ask(req.message)
    # rerank 后顺序即相关度，给前端一个递减分数画进度条
    sources = [
        {"file": s["source"] or "未知", "snippet": s["snippet"], "score": max(55, 96 - i * 9)}
        for i, s in enumerate(res["sources"])
    ]
    return {"answer": res["answer"], "sources": sources}


# ---------------------------------------------------------------- agent


@app.post("/api/agent")
def agent(req: AgentReq) -> dict[str, Any]:
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query 不能为空")
    state = run_agent(req.query, retriever=get_retriever())
    # 从 ReAct 消息里提取结构化证据：工具名 + 返回内容
    evidence: list[dict[str, str]] = []
    for m in state.get("messages", []):
        if isinstance(m, ToolMessage):
            content = m.content if isinstance(m.content, str) else str(m.content)
            evidence.append({"tool": m.name or "tool", "result": content[:500]})
    if not evidence:
        for e in state.get("evidence", []):
            evidence.append({"tool": "evidence", "result": str(e)[:500]})
    return {
        "triage": state.get("triage", ""),
        "evidence": evidence,
        "report": state.get("report", ""),
    }


# ---------------------------------------------------------------- kb


@app.get("/api/kb/status")
def kb_status() -> dict[str, Any]:
    vs = get_vectorstore(get_embeddings())
    return {"chunks": vs._collection.count()}


@app.get("/api/kb/documents")
def kb_documents() -> dict[str, Any]:
    vs = get_vectorstore(get_embeddings())
    data = vs.get(include=["metadatas"])
    files: Counter[str] = Counter()
    for m in data.get("metadatas", []) or []:
        files[(m or {}).get("source", "未知")] += 1
    docs = [{"file": f, "chunks": c} for f, c in files.most_common()]
    return {"documents": docs, "total": len(docs)}


@app.post("/api/kb/upload")
async def kb_upload(
    files: list[UploadFile] = File(default=[]),
    text: str = Form(default=""),
) -> dict[str, Any]:
    docs: list[Document] = []
    skipped: list[str] = []
    for f in files:
        raw = await f.read()
        try:
            content = extract_text(raw, f.filename or "upload")
        except Exception as e:  # noqa: BLE001
            logger.warning("解析失败 %s: %s", f.filename, e)
            skipped.append(f.filename or "未知")
            continue
        if content and content.strip():
            docs.append(Document(page_content=content, metadata={"source": f.filename or "上传文件"}))
        else:
            skipped.append(f.filename or "未知")
    if text.strip():
        docs.append(Document(page_content=text.strip(), metadata={"source": "网页粘贴文本"}))
    if not docs:
        raise HTTPException(status_code=400, detail="未提供有效文件或文本（或全部解析失败）")

    chunks = chunk(docs, strategy="markdown")
    vs = get_vectorstore(get_embeddings())
    add_documents(vs, chunks)
    _invalidate()
    return {"added": len(docs), "chunks": len(chunks), "total": vs._collection.count(), "skipped": skipped}


@app.delete("/api/kb/document")
def kb_delete_doc(file: str) -> dict[str, bool]:
    vs = get_vectorstore(get_embeddings())
    vs._collection.delete(where={"source": file})
    _invalidate()
    return {"ok": True}


@app.delete("/api/kb")
def kb_reset() -> dict[str, bool]:
    vs = get_vectorstore(get_embeddings())
    reset_vectorstore(vs)
    get_vectorstore(get_embeddings())  # 重建空 collection
    _invalidate()
    return {"ok": True}


# ---------------------------------------------------------------- alerts
register_alert_routes(app)  # 注册 POST /api/alerts + GET /api/incidents


# ---------------------------------------------------------------- static
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("opscopilot.api:app", host="0.0.0.0", port=8001, reload=False)
