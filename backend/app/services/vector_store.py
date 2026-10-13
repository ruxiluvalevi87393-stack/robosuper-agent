"""MilvusDB 单例工厂。

服务层/Agent 工具统一通过 get_milvus() 拿实例，避免重复初始化
DashScope embedding 和 Milvus 连接。
"""
from functools import lru_cache

from app.config import settings
from app.core.milvusdb import MilvusDB


@lru_cache(maxsize=1)
def get_milvus() -> MilvusDB:
    """返回全局唯一的 MilvusDB 实例（线程安全，lru_cache 保证只创建一次）。"""
    return MilvusDB(
        collection_name=settings.MILVUS_COLLECTION_NAME,
        embedding_dim=1024,  # text-embedding-v4 输出维度
    )
