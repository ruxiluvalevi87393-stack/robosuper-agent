"""MCP 服务端公共配置。

env_file 按序加载两个文件，后者优先：
1. mcp-servers/.env —— 仅 MCP 专属配置（模式/监听地址/端口），**不含任何密钥**；
2. backend/.env —— PG/Neo4j 凭据复用，两个文件无重叠键，故无覆盖冲突。

安全约定：本模块只读键名，绝不打印/提交凭据值（见 mcp_development_plan.md §2）。
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

MCP_DIR = Path(__file__).resolve().parent.parent  # mcp-servers/
CANONICAL_DIR = MCP_DIR.parent / "backend" / "data" / "canonical"

_env_files = (
    str(MCP_DIR / ".env"),                 # MCP 专属配置（无密钥）
    str(MCP_DIR.parent / "backend" / ".env"),  # PG/Neo4j 凭据（复用）
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_files, case_sensitive=True, extra="ignore"
    )

    # streamable HTTP 监听地址与各服务端口（9101–9103, 9105–9106，避开 Docker 占用的 9001）
    MCP_HOST: str = "127.0.0.1"
    ALARM_GRAPH_MCP_PORT: int = 9101
    SERVO_PARAM_MCP_PORT: int = 9102
    EPC_PARTS_MCP_PORT: int = 9103
    INVENTORY_MCP_PORT: int = 9105
    WORK_ORDER_MCP_PORT: int = 9106

    # 接地索引向量检索（alarm_reasoning 用；凭据复用 backend/.env，extra="ignore" 只放行已定义键）
    DASHSCOPE_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-v4"
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_USER: str = ""
    MILVUS_PASSWORD: str = ""
    MILVUS_TOKEN: str = ""
    MILVUS_GRAPH_ENTITIES_COLLECTION: str = "graph_entities"
    # 向量锚点最低相似度（1/(1+L2)）；低于阈值视为离域噪声，不构成锚点
    VECTOR_ANCHOR_MIN_SCORE: float = 0.5

    # PostgreSQL（凭据复用 backend/.env）
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "123456"
    POSTGRES_DB: str = "sentinel_ai"

    # Neo4j 知识图谱（alarm_graph 用；凭据复用 backend/.env）
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""

    @property
    def server_ports(self) -> dict[str, int]:
        """服务名 -> 端口，供 run_all.py 一键启动。"""
        return {
            "alarm_graph_mcp": self.ALARM_GRAPH_MCP_PORT,
            "servo_param_mcp": self.SERVO_PARAM_MCP_PORT,
            "epc_parts_mcp": self.EPC_PARTS_MCP_PORT,
            "inventory_mcp": self.INVENTORY_MCP_PORT,
            "work_order_mcp": self.WORK_ORDER_MCP_PORT,
        }

    @property
    def database_url(self) -> str:
        # 与 backend/app/config.py 对齐：连接级 timezone=Asia/Shanghai
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            f"?options=-c%20timezone%3DAsia%2FShanghai"
        )


settings = Settings()
