"""集中式配置：从环境变量 / .env 读取，全项目共享。

设计原则：所有"会变的值"(key、模型名、路径、检索参数)都集中在这里，
代码里只引用 settings.xxx，避免散落的硬编码。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---- 路径常量 ----
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RUNBOOK_DIR = DATA_DIR / "runbooks"
EVAL_DATASET_PATH = DATA_DIR / "eval" / "eval_dataset.json"
EVAL_RESULTS_DIR = DATA_DIR / "eval" / "results"

_chroma_default = str(PROJECT_ROOT / ".chroma")


@dataclass
class Settings:
    """全局配置单例（settings 在文件末尾实例化）。"""

    # ---- LLM（OpenAI 兼容接口）----
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))

    # ---- 文档解析（百炼 file-extract + qwen-long 提取全文）----
    file_extract_model: str = field(default_factory=lambda: os.getenv("FILE_EXTRACT_MODEL", "qwen-long"))
    # 图片 OCR 专用模型（qwen-vl-ocr，base64 直传，比 qwen-long 对图片准得多）
    ocr_model: str = field(default_factory=lambda: os.getenv("OCR_MODEL", "qwen-vl-ocr"))

    # ---- Embedding ----
    embedding_provider: str = field(default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "local"))
    embedding_model_local: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL_LOCAL", "BAAI/bge-small-zh-v1.5"))
    embedding_api_key: str = field(default_factory=lambda: os.getenv("EMBEDDING_API_KEY", ""))
    embedding_base_url: str = field(default_factory=lambda: os.getenv("EMBEDDING_BASE_URL", ""))
    embedding_model_openai: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))

    # ---- Rerank ----
    # provider: dashscope(百炼原生接口，免下载) | local(sentence-transformers cross-encoder)
    rerank_provider: str = field(default_factory=lambda: os.getenv("RERANK_PROVIDER", "dashscope"))
    reranker_model: str = field(default_factory=lambda: os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"))
    dashscope_rerank_model: str = field(default_factory=lambda: os.getenv("DASHSCOPE_RERANK_MODEL", "gte-rerank-v2"))
    dashscope_rerank_url: str = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"

    # ---- 向量库 ----
    chroma_persist_dir: str = field(default_factory=lambda: os.getenv("CHROMA_PERSIST_DIR", _chroma_default))
    chroma_collection: str = "opscopilot_runbooks"

    # ---- 检索参数（面试常被问：为什么这样设）----
    chunk_size: int = 500          # 字符级 chunk，运维文档单段语义密度适中
    chunk_overlap: int = 80        # 重叠防止切断排查步骤
    retrieve_top_k: int = 10       # 召回阶段多召回（向量 + BM25 各路）
    rerank_top_k: int = 4          # 精排后只留最相关，喂给 LLM 降成本/防噪声

    # ---- GitHub（L3 MCP Server）----
    github_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))

    # ---- 基础设施接入（工具适配器：配了查真，没配走 mock 兜底）----
    prometheus_url: str = field(default_factory=lambda: os.getenv("PROMETHEUS_URL", ""))
    loki_url: str = field(default_factory=lambda: os.getenv("LOKI_URL", ""))
    k8s_in_cluster: bool = field(default_factory=lambda: os.getenv("K8S_IN_CLUSTER", "").lower() == "true")

    # ---- IM 播报（配了推真，没配降级到 Web/日志）----
    feishu_webhook: str = field(default_factory=lambda: os.getenv("FEISHU_WEBHOOK", ""))
    dingtalk_webhook: str = field(default_factory=lambda: os.getenv("DINGTALK_WEBHOOK", ""))
    slack_webhook: str = field(default_factory=lambda: os.getenv("SLACK_WEBHOOK", ""))


settings = Settings()
