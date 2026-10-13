from typing import Optional

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_milvus import Milvus
from pymilvus import MilvusClient
from app.config import settings


class MilvusDB:
    """基于 LangChain 的 Milvus 向量数据库封装类
    提供集合管理、文档写入、向量查询、元数据过滤等操作，
    内部维护一个 Milvus VectorStore 实例，所有操作均通过
    LangChain 的 VectorStore 接口完成。
    """

    def __init__(
        self,
        collection_name: str = "default",
        embedding_dim: int = 1024,
        uri: Optional[str] = None,
    ):
        """初始化 MilvusDB 实例
        Args:
            collection_name: Milvus 集合名称，默认 "default"。
            embedding_dim: 向量维度，需与所用 Embedding 模型一致，默认 1024。
            uri: Milvus 连接地址，默认使用 config 中的配置。
        """
        self._collection_name = collection_name
        self._embedding_dim = embedding_dim
        self._uri = uri or f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
        self._connection_args = {
            "uri": self._uri,
        }
        if settings.MILVUS_USER:
            self._connection_args["token"] = (
                f"{settings.MILVUS_USER}:{settings.MILVUS_PASSWORD}"
            )

        # 初始化 Embedding 模型
        self._embeddings: Embeddings = DashScopeEmbeddings(
            dashscope_api_key=settings.DASHSCOPE_API_KEY,
            model=settings.EMBEDDING_MODEL,
        )

        self._llm: BaseChatModel = ChatTongyi(
            dashscope_api_key=settings.DASHSCOPE_API_KEY,
            model=settings.LLM_MODEL
        )


        self._vector_store = Milvus(
            embedding_function=self._embeddings,
            collection_name=self._collection_name,
            connection_args=self._connection_args,
            primary_field="id",
            text_field="text",
            vector_field="vector",
        )

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------

    @property
    def collection_name(self) -> str:
        return self._collection_name

    @property
    def embeddings(self) -> Embeddings:
        return self._embeddings

    @property
    def llm(self) -> BaseChatModel:
        return self._llm

    @property
    def vector_store(self) -> Milvus:
        return self._vector_store

    # ------------------------------------------------------------------
    # 文档操作
    # ------------------------------------------------------------------

    def add_documents(
        self, documents: list[Document], ids: Optional[list[str]] = None
    ) -> list[str]:
        """将文档写入 Milvus 向量数据库
        Args:
            documents: LangChain Document 列表。
            ids: 可选的 ID 列表，与 documents 一一对应。
        Returns:
            写入成功的文档 ID 列表。
        """
        kwargs = {}
        if ids:
            kwargs["ids"] = ids
        return self._vector_store.add_documents(documents, **kwargs)

    def update_document(self, doc_id: str, document: Document) -> str:
        """根据 ID 更新单个文档的向量（先删后增）。
        Args:
            doc_id: 文档 ID。
            document: 新的 Document 对象。
        Returns:
            写入成功的文档 ID。
        """
        self._vector_store.delete([doc_id])
        return self._vector_store.add_documents([document], ids=[doc_id])[0]

    def add_texts(
        self,
        texts: list[str],
        metadatas: Optional[list[dict]] = None,
    ) -> list[str]:
        """便捷方法：直接从文本列表创建文档并写入。
        Args:
            texts: 文本内容列表。
            metadatas: 与文本一一对应的元数据字典列表。
        Returns:
            写入成功的文档 ID 列表。
        """
        return self._vector_store.add_texts(texts, metadatas=metadatas)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def query(
        self,
        question: str,
        top_k: int = 5,
        filter_expr: Optional[str] = None,
    ) -> str:
        """使用自然语言查询向量数据库
        Args:
            question: 查询问题。
            top_k: 返回最相似的文档数量。
            filter_expr: 可选的 Milvus 过滤表达式（如 'metadata["key"] == "value"'）。
        Returns:
            查询结果的文本
        """
        docs = self.retrieve(question, top_k=top_k, filter_expr=filter_expr)
        if not docs:
            return "未找到相关文档。"
        return "\n\n---\n\n".join(doc.page_content for doc in docs)

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        filter_expr: Optional[str] = None,
    ) -> list[Document]:
        """检索与问题最相似的文档列表。
        Args:
            question: 查询文本。
            top_k: 返回数量。
            filter_expr: 可选的 Milvus 过滤表达式。
        Returns:
            Document 列表。
        """
        kwargs = {}
        if filter_expr:
            kwargs["expr"] = filter_expr
        return self._vector_store.similarity_search(
            question, k=top_k, **kwargs
        )

    def retrieve_with_score(
        self,
        question: str,
        top_k: int = 5,
        filter_expr: Optional[str] = None,
    ) -> list[tuple[Document, float]]:
        """检索与问题最相似的文档列表，附带相似度分数。
        Args:
            question: 查询文本。
            top_k: 返回数量。
            filter_expr: 可选的 Milvus 过滤表达式。
        Returns:
            (Document, score) 元组列表。
        """
        kwargs = {}
        if filter_expr:
            kwargs["expr"] = filter_expr
        return self._vector_store.similarity_search_with_score(
            question, k=top_k, **kwargs
        )

    def hybrid_search(
        self,
        query: str,
        all_docs: list[Document],
        top_k: int = 5,
        vector_weight: float = 0.7,
        searcher_weight: float = 0.3,
        filter_meta: Optional[dict] = None,
    ) -> list[dict]:
        """混合检索：向量相似度 + BM25 关键词，加权合并排序。
        Args:
            query: 查询文本。
            all_docs: 用于构建 BM25 索引的全量 Document 列表（从数据库加载）。
            top_k: 最终返回数量。
            vector_weight: 向量相似度权重。
            searcher_weight: BM25 关键词权重。
            filter_meta: 结构化过滤条件（如 {"document_id": 5, "brand": "FANUC"}），
                同时作用于向量检索与 BM25 预过滤，保证两侧过滤口径一致。
        Returns:
            dict 列表，每项包含 content、metadata、vector_score、bm25_score、score。
        """
        k = max(top_k * 3, 20)  # 多取一些候选，合并后再截断

        # 由 filter_meta 生成 Milvus 过滤表达式（与 BM25 预过滤共用同一份条件）。
        # 集合为显式列 schema，过滤必须用裸列名（如 brand == "FANUC"），不能用
        # metadata["brand"]——那需要集合有名为 metadata 的 JSON 动态字段。
        expr = None
        if filter_meta:
            parts = []
            for key, value in filter_meta.items():
                if isinstance(value, int):
                    parts.append(f"{key} == {value}")
                else:
                    lit = str(value).replace("\\", "\\\\").replace('"', '\\"')
                    parts.append(f'{key} == "{lit}"')
            expr = " and ".join(parts)

        def _match(doc: Document) -> bool:
            md = doc.metadata
            return all(md.get(key) == value for key, value in filter_meta.items())

        # ── 向量检索 ──
        vector_results = {}  # doc_id → normalized_score
        try:
            kwargs = {}
            if expr:
                kwargs["expr"] = expr
            vs_hits = self._vector_store.similarity_search_with_score(
                query, k=k, **kwargs
            )
            for doc, score in vs_hits:
                doc_id = doc.metadata.get("chunk_id") or doc.metadata.get("id") or doc.page_content[:100]
                # Milvus L2 距离转为 0~1 相似度（越小越相似）
                norm_score = 1.0 / (1.0 + score)
                vector_results[doc_id] = max(vector_results.get(doc_id, 0), norm_score)
        except Exception:
            pass

        # ── BM25 关键词检索（先按 filter_meta 预过滤文档集，保证与向量侧口径一致）──
        bm25_results = {}  # doc_id → normalized_score
        bm25_docs = [d for d in all_docs if _match(d)] if filter_meta else all_docs
        if bm25_docs and searcher_weight > 0:
            try:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"BM25: 构建索引，文档数={len(bm25_docs)}, k={k}")
                import jieba

                def _tokenize(text: str) -> list[str]:
                    return list(jieba.cut(text))

                bm25 = BM25Retriever.from_documents(bm25_docs, preprocess_func=_tokenize, k=k)
                bm25_hits = bm25.invoke(query)
                logger.info(f"BM25: 查询='{query}', 命中数={len(bm25_hits)}")
                for rank, doc in enumerate(bm25_hits):
                    doc_id = doc.metadata.get("chunk_id") or doc.metadata.get("id") or doc.page_content[:100]
                    norm_score = max(0, 1.0 - rank / max(len(bm25_hits), 1))
                    bm25_results[doc_id] = max(bm25_results.get(doc_id, 0), norm_score)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"BM25 检索异常: {e}", exc_info=True)

        # ── 合并分数 ──
        all_doc_ids = set(vector_results.keys()) | set(bm25_results.keys())
        merged = []
        for doc_id in all_doc_ids:
            v_score = vector_results.get(doc_id, 0)
            b_score = bm25_results.get(doc_id, 0)
            combined = v_score * vector_weight + b_score * searcher_weight
            merged.append((doc_id, combined, v_score, b_score))

        merged.sort(key=lambda x: x[1], reverse=True)

        # ── 构建结果 ──
        # 从 all_docs 中查找完整内容和元数据
        doc_map = {}
        for doc in all_docs:
            did = doc.metadata.get("chunk_id") or doc.metadata.get("id") or doc.page_content[:100]
            doc_map[did] = doc

        results = []
        for doc_id, combined, v_score, b_score in merged[:top_k]:
            doc = doc_map.get(doc_id)
            if doc:
                results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "vector_score": round(v_score, 4),
                    "bm25_score": round(b_score, 4),
                    "score": round(combined, 4),
                })
        return results

    # ------------------------------------------------------------------
    # 删除
    # ------------------------------------------------------------------

    def delete_by_ids(self, ids: list[str]) -> None:
        """根据文档 ID 列表删除文档。"""
        if not self.collection_exists():
            return
        client = MilvusClient(uri=self._uri)
        try:
            client.delete(self._collection_name, ids=ids)
        finally:
            client.close()

    def delete_by_filter(self, filter_expr: str) -> None:
        """根据过滤表达式删除文档。
        Args:
            filter_expr: Milvus 过滤表达式。
        """
        if not self.collection_exists():
            return
        client = MilvusClient(uri=self._uri)
        try:
            client.delete(self._collection_name, filter=filter_expr)
        finally:
            client.close()

    # ------------------------------------------------------------------
    # 集合管理
    # ------------------------------------------------------------------

    def drop_collection(self) -> None:
        """删除当前集合（谨慎使用）。"""
        client = MilvusClient(uri=self._uri)
        client.drop_collection(self._collection_name)
        client.close()

    def collection_exists(self) -> bool:
        """检查当前集合是否存在。"""
        client = MilvusClient(uri=self._uri)
        exists = client.has_collection(self._collection_name)
        client.close()
        return exists

    def existing_ids(self) -> set[str]:
        """返回当前集合已存在的全部主键（实体 key），用于增量/断点续跑。"""
        if not self.collection_exists():
            return set()
        client = MilvusClient(uri=self._uri)
        try:
            ids: set[str] = set()
            offset = 0
            while True:
                rows = client.query(
                    self._collection_name,
                    filter="id != ''",
                    output_fields=["id"],
                    limit=16384,
                    offset=offset,
                )
                ids.update(r["id"] for r in rows)
                if len(rows) < 16384:
                    break
                offset += len(rows)
            return ids
        finally:
            client.close()

    # ------------------------------------------------------------------
    # 魔术方法
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"MilvusDB(collection='{self._collection_name}', "
            f"uri='{self._uri}', dim={self._embedding_dim})"
        )


if __name__ == "__main__":
    print("=" * 60)
    print("MilvusDB 测试")
    print("=" * 60)

    # 初始化
    print("\n[1] 初始化 MilvusDB...")
    db = MilvusDB(collection_name=settings.MILVUS_COLLECTION_NAME, embedding_dim=1024)
    print(f"    实例: {db}")

    # 检查集合
    print("\n[2] 检查集合是否存在...")
    exists = db.collection_exists()
    print(f"    集合存在: {exists}")

    # # 添加文本
    # print("\n[3] 添加测试文档...")
    # texts = [
    #     "LangChain 是一个用于开发 LLM 应用的框架",
    #     "Milvus 是一个开源的向量数据库",
    #     "Python 是一种流行的编程语言",
    #     "FastAPI 是一个现代的 Web 框架",
    # ]
    # metadatas = [
    #     {"source": "langchain", "category": "framework"},
    #     {"source": "milvus", "category": "database"},
    #     {"source": "python", "category": "language"},
    #     {"source": "fastapi", "category": "framework"},
    # ]
    # ids = db.add_texts(texts, metadatas=metadatas)
    # print(f"    写入成功，IDs: {ids}")
    #
    # # 查询
    # print("\n[4] 向量查询测试...")
    # question = "什么是向量数据库？"
    # print(f"    查询: {question}")
    # result = db.query(question, top_k=3)
    # print(f"    结果:\n{result}")
    #
    # # 带分数查询
    # print("\n[5] 带相似度分数的查询...")
    # results_with_score = db.retrieve_with_score(question, top_k=2)
    # for doc, score in results_with_score:
    #     print(f"    [分数: {score:.4f}] {doc.page_content}")
    #
    # # 过滤查询
    # print("\n[6] 带元数据过滤的查询...")
    # filter_expr = 'category == "framework"'
    # filtered = db.retrieve("框架", top_k=3, filter_expr=filter_expr)
    # print(f"    过滤条件: {filter_expr}")
    # for doc in filtered:
    #     print(f"    - {doc.page_content}")
    #
    # print("\n" + "=" * 60)
    # print("测试完成!")
    # print("=" * 60)
