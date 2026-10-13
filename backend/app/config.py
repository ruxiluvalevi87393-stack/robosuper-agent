from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
_env_file = str(BASE_DIR / ".env")  # .env 在 backend/ 目录


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_file, case_sensitive=True, extra="ignore")

    # 通义千问
    DASHSCOPE_API_KEY: str = ""
    LLM_MODEL: str = "qwen-plus"
    EMBEDDING_MODEL: str = "text-embedding-v4"

    # 七牛云 S3 兼容 OSS
    QINIU_S3_ENDPOINT: str = "https://s3.cn-east-1.qiniucs.com"
    QINIU_ACCESS_KEY: str = ""
    QINIU_SECRET_KEY: str = ""
    QINIU_BUCKET: str = ""
    QINIU_REGION: str = "cn-east-1"

    # Milvus
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_USER: str = ""
    MILVUS_PASSWORD: str = ""
    MILVUS_COLLECTION_NAME: str = ""
    MILVUS_GRAPH_ENTITIES_COLLECTION: str = "graph_entities"
    MILVUS_TOKEN: str = ""

    # PostgreSQL
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "123456"
    POSTGRES_DB: str = "sentinel_ai"

    # Neo4j 知识图谱（灌数/维护脚本直连；运行时查询走 alarm_graph_mcp）
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    NEO4J_DATABASE: str = "neo4j"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # MinerU 在线文档解析
    MINERU_BASE_URL: str = "https://mineru.net/api/v4"
    MINERU_TOKEN: str = ""
    MINERU_WORK_DIR: str = "storage/mineru"  # 解析包本地工作目录（相对 backend/）
    MINERU_BATCH_PAGES: int = 150  # 超长 PDF 分批解析的每批页数（MinerU 在线单任务约 200 页上限，留余量）

    # JWT
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 1440  # 24h

    LANGFUSE_PUBLIC_KEY: str = "pk-lf-60ff3714-6cb1-4f1a-9ed5-38d26bb2c63a"
    LANGFUSE_SECRET_KEY: str = "sk-lf-2d1ba616-acdf-4657-bb88-498a8df390cd"
    LANGFUSE_HOST: str = "http://localhost:3000"  # 自托管离线；SDK 默认指向云服务，必须改为本地

    @property
    def database_url(self) -> str:
        # ?options=-c timezone=Asia/Shanghai：每个连接 session 自动 SET timezone，
        # 让 NOW() / CURRENT_TIMESTAMP 返回北京时间。
        # 不动 PG 服务器配置，不影响同实例其他业务。
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            f"?options=-c%20timezone%3DAsia%2FShanghai"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def mineru_work_dir(self) -> Path:
        """MinerU 解析包本地工作目录（backend/storage/mineru）。"""
        return BASE_DIR / self.MINERU_WORK_DIR


settings = Settings()
