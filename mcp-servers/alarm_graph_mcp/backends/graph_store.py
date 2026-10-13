"""alarm_graph_mcp 接地索引向量检索：对接 Milvus graph_entities 集合。

镜像 backend/app/core/milvusdb.py 的 LangChain Milvus 用法（同一集合、同一嵌入模型），
保证查询侧 schema 与灌数侧（scripts/load/build_graph_entities.py）一致：
    primary_field="id" / text_field="text" / vector_field="vector"，
    entity_type / brand / code 等为显式列，过滤用裸列名。

纯 real：数据库为真实 Milvus。所有异常记日志返回空/False，调用方降级，绝不 raise。
"""
from __future__ import annotations

from typing import Any

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.documents import Document
from langchain_milvus import Milvus
from loguru import logger
from pymilvus import MilvusClient

from common.config import settings


class GraphEntityStore:
    """graph_entities 集合的向量检索（惰性连接）。"""

    def __init__(self) -> None:
        self._store: Milvus | None = None

    # ------------------------------------------------------------------
    # 连接
    # ------------------------------------------------------------------

    @property
    def _uri(self) -> str:
        return f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"

    @property
    def _token(self) -> str | None:
        if settings.MILVUS_TOKEN:
            return settings.MILVUS_TOKEN
        if settings.MILVUS_USER:
            return f"{settings.MILVUS_USER}:{settings.MILVUS_PASSWORD}"
        return None

    def _connect(self) -> Milvus:
        if self._store is None:
            connection_args: dict[str, str] = {"uri": self._uri}
            token = self._token
            if token:
                connection_args["token"] = token
            self._store = Milvus(
                embedding_function=DashScopeEmbeddings(
                    dashscope_api_key=settings.DASHSCOPE_API_KEY,
                    model=settings.EMBEDDING_MODEL,
                ),
                collection_name=settings.MILVUS_GRAPH_ENTITIES_COLLECTION,
                connection_args=connection_args,
                primary_field="id",
                text_field="text",
                vector_field="vector",
            )
        return self._store

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------

    def collection_exists(self) -> bool:
        """graph_entities 集合是否存在（异常视为不存在）。"""
        try:
            client = MilvusClient(uri=self._uri)
            try:
                return client.has_collection(settings.MILVUS_GRAPH_ENTITIES_COLLECTION)
            finally:
                client.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Milvus 集合检查失败: {exc}")
            return False

    def search(
        self,
        query: str,
        top_k: int = 5,
        brand: str | None = None,
    ) -> list[tuple[Document, float]]:
        """向量检索 AlarmCode 实体，返回 (Document, L2距离)。异常/集合缺失返回空。"""
        if not self.collection_exists():
            logger.warning("graph_entities 集合不存在，跳过向量锚点")
            return []
        try:
            expr = 'entity_type == "AlarmCode"'
            if brand:
                lit = str(brand).replace("\\", "\\\\").replace('"', '\\"')
                expr += f' and brand == "{lit}"'
            return self._connect().similarity_search_with_score(query, k=top_k, expr=expr)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"向量检索失败: {exc}")
            return []
