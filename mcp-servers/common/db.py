"""共享 SQLAlchemy engine（惰性创建）。

servo_param / epc_parts / inventory / work_order 四个 server 复用同一 PG 连接；
只在首次查询时建 engine，不启动不连库。
"""
from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

_engine: Any | None = None
_session_factory: sessionmaker[Session] | None = None


def engine() -> Any:
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            future=True,
        )
    return _engine


def session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=engine(), autoflush=False, expire_on_commit=False
        )
    return _session_factory


def get_session() -> Generator[Session, None, None]:
    """依赖式会话：with/next 使用，保证用完即关。"""
    session = session_factory()()
    try:
        yield session
    finally:
        session.close()
