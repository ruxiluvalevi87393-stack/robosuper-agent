"""检索手册（RAG）：向量+BM25 混合检索 → manual_chunks。"""
from __future__ import annotations

from typing import Any

from app.events import emit_start
from app.services.graph_service import graph_service

NAME = "retrieve_manual"


async def run(state: dict[str, Any]) -> dict[str, Any]:
    emit_start(NAME)
    query = state.get("user_query") or ""
    brand = state.get("brand")
    chunks = await graph_service.search_manual(query, brand=brand, top_k=10)
    return {"manual_chunks": chunks}
