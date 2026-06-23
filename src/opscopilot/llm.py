"""LLM 工厂：统一封装，一个 get_llm() 切换厂商。

关键点（面试可讲）：通过 OpenAI 兼容接口 + base_url，DeepSeek / 智谱 / Qwen /
OpenAI 都能用同一套 ChatOpenAI 调用，业务代码零改动，只换配置。
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from .config import settings


def get_llm(temperature: float = 0.2, streaming: bool = False) -> ChatOpenAI:
    """返回共享配置的 ChatOpenAI 实例。

    Args:
        temperature: 事实型问答/排障用低温度(0~0.3)，创意任务可调高。
        streaming:   UI 流式输出时开。
    """
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=temperature,
        streaming=streaming,
    )
