"""FastAPI 入口。"""
from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager

# psycopg 异步要求 SelectorEventLoop（Proactor 不兼容）。uvicorn 0.52 会通过
# asyncio.Runner(loop_factory=...) 显式传 Proactor 覆盖此 policy，故 __main__ 块还需
# 传 loop factory；此处 policy 兜底给 uvicorn 之外的 asyncio.new_event_loop() 调用。
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.v1.agent import router as agent_router
from app.api.v1.auth import router as auth_router
from app.api.v1.brands import router as brands_router
from app.api.v1.controllers import router as controllers_router
from app.api.v1.knowledge_base import router as knowledge_base_router
from app.api.v1.knowledge_base import extra_router as knowledge_extra_router
from app.api.v1.maintenance_logs import router as maintenance_logs_router
from app.api.v1.part_inventory import router as part_inventory_router
from app.api.v1.robot_instances import router as robot_instances_router
from app.api.v1.robot_models import router as robot_models_router
from app.api.v1.servo_param_histories import router as servo_param_histories_router
from app.api.v1.servo_params import router as servo_params_router
from app.api.v1.users import router as users_router
from app.api.v1.work_orders import router as work_orders_router
from app.core.database import init_db, SessionLocal
from app.core.exception import register_exception_handlers
from app.core.security import hash_password
from app.models import SysUser


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config import settings
    from sqlalchemy import select

    logger.info(f"PostgreSQL: {settings.POSTGRES_USER}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    init_db()
    logger.info("数据库初始化完成")

    # 初始化 LangGraph PG Checkpointer（异步 context manager，保持连接）
    from app.memory.checkpoint import init_checkpointer
    await init_checkpointer()

    # 确保默认管理员存在（按 username 查，而非判断表是否为空）
    with SessionLocal() as db:
        admin = db.execute(
            select(SysUser).where(SysUser.username == "admin")
        ).scalar_one_or_none()
        if admin is None:
            db.add(SysUser(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin",
            ))
            db.commit()
            logger.info("默认管理员已创建: admin / admin123")
        else:
            logger.debug("管理员账号已存在，跳过初始化")

    # 尽力初始化 Milvus 集合，失败不阻塞启动
    try:
        from app.services.vector_store import get_milvus
        get_milvus()  # 触发单例创建 + Milvus 连接（集合在首次 add_documents 时自动创建）
        logger.info("Milvus 连接就绪")
    except Exception as exc:
        logger.warning(f"Milvus 初始化跳过（向量功能暂不可用）: {exc}")

    # 尽力初始化 Redis，失败不阻塞启动
    try:
        from app.core.redis_client import get_redis
        if get_redis().ping():
            logger.info("Redis 连接就绪")
        else:
            logger.warning("Redis ping 失败（会话缓存/限流不可用）")
    except Exception as exc:
        logger.warning(f"Redis 初始化跳过（会话缓存/限流不可用）: {exc}")

    # 尽力连接 MCP 工具服务端，失败不阻塞启动（工具降级为暂不可用）
    try:
        from app.services.mcp.mcp_client import pool
        await pool.connect_all()
        logger.info(
            f"MCP 工具服务端就绪：{len(pool.tool_index)} 个工具 / 在线 {pool.available_servers}"
        )
    except Exception as exc:
        logger.warning(f"MCP 工具服务端初始化跳过: {exc}")

    # Langfuse 可观测性：注册全局客户端供 @observe 使用（未配置 secret key 自动跳过）
    try:
        from app.core.tracing import get_langfuse
        if get_langfuse() is not None:
            logger.info(
                f"Langfuse 可观测性就绪：{settings.LANGFUSE_HOST}（tracing_enabled）"
            )
    except Exception as exc:
        logger.warning(f"Langfuse 初始化跳过: {exc}")
    yield

    # LangGraph PG Checkpointer 连接关闭
    try:
        from app.memory.checkpoint import close_checkpointer
        await close_checkpointer()
    except Exception:
        pass

    # MCP 客户端关闭（长连接，进程退出前释放）
    try:
        from app.services.mcp.mcp_client import pool
        await pool.close()
    except Exception:
        pass

app = FastAPI(
    title="工业机器人运维智能体系统",
    description="工业机器人运维智能体系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# 各业务模块路由统一挂载，前缀 /api/v1
for _router in (
    agent_router,
    auth_router,
    users_router,
    brands_router,
    controllers_router,
    robot_models_router,
    robot_instances_router,
    part_inventory_router,
    servo_params_router,
    work_orders_router,
    maintenance_logs_router,
    servo_param_histories_router,
    knowledge_base_router,
    knowledge_extra_router,
):
    app.include_router(_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "service": "sentinel_ai",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn

    def _loop_factory() -> asyncio.AbstractEventLoop:
        # uvicorn 0.52 在 win32 默认 asyncio_loop_factory 返回 ProactorEventLoop，
        # 经 asyncio.Runner(loop_factory=...) 显式传入后无视上方 event_loop_policy；
        # psycopg 异步（AsyncPostgresSaver）只兼容 Selector，故显式提供 loop factory。
        return asyncio.SelectorEventLoop()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        loop=_loop_factory if sys.platform == "win32" else "auto",
    )