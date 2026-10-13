"""DashScope LLM 客户端（openai SDK 版）：三档模型 + tenacity 重试 + Redis 缓存。

对齐 backend/agent_build_plan.md §4.1。plan.md §6.2 原设计用 langchain_openai，
本环境未安装该包，改用 openai 官方 SDK 直连 DashScope compatible-mode（单供应商）。
"""
from __future__ import annotations

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.core.redis_client import get_redis
from app.core.tracing import observed


class LLMClient:
    """DashScope 单供应商：按 tier 选档，tenacity 重试 + Redis 缓存兜底。"""

    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    TIER_MODELS = {
        "default": "qwen-plus",  # 意图分类、品牌判别、NER
        "strong": "qwen-max",  # SOP 生成、复杂推理
        "fast": "qwen-turbo",  # 简单关键词提取、状态判断
    }

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            base_url=self.BASE_URL,
            api_key=settings.DASHSCOPE_API_KEY,
            timeout=30,
        )

    @observed(as_type="generation")
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=3),
        reraise=True,
    )
    async def invoke(
        self,
        prompt: str,
        tier: str = "default",
        cache_key: str | None = None,
        temperature: float = 0.3,
        response_format: dict | None = None,
    ) -> str:
        """调 DashScope 返回文本；cache_key 命中直接返回（TTL 1h）。"""
        if cache_key:
            cached = get_redis().get(cache_key)
            if cached:
                return cached
        kwargs: dict = {
            "model": self.TIER_MODELS[tier],
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if response_format:
            kwargs["response_format"] = response_format
        resp = await self._client.chat.completions.create(**kwargs)
        text = (resp.choices[0].message.content or "").strip()
        if cache_key and text:
            get_redis().set(cache_key, text, ttl=3600)
        return text

    @observed(as_type="generation")
    async def stream(
        self,
        prompt: str,
        tier: str = "default",
        temperature: float = 0.3,
        response_format: dict | None = None,
    ):
        """DashScope 流式：async generator 逐 token 产出文本（供 agent 回答逐字下发）。"""
        kwargs: dict = {
            "model": self.TIER_MODELS[tier],
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }
        if response_format:
            kwargs["response_format"] = response_format
        resp = await self._client.chat.completions.create(**kwargs)
        async for chunk in resp:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


llm_client = LLMClient()
