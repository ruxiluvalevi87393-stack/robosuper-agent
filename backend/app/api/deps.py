"""统一依赖注入：DB session、当前用户、角色检查。"""
from __future__ import annotations

from typing import Annotated, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.sys_user import SysUser

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

DBSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DBSession,
) -> SysUser:
    """解析 JWT 查 sys_user，账号禁用则 401。"""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id = payload.get("user_id")
        if user_id is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = db.get(SysUser, user_id)
    if user is None or not user.is_active:
        raise credentials_exc
    return user


CurrentUser = Annotated[SysUser, Depends(get_current_user)]


def require_role(*roles: str) -> Callable:
    """RBAC 检查：require_role("admin") / require_role("admin", "operator")。"""

    def checker(user: CurrentUser) -> SysUser:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return user

    return checker


# 常用角色别名：AdminUser 主数据可写；StaffUser 工单/维修流程可写（engineer+admin）
AdminUser = Annotated[SysUser, Depends(require_role("admin"))]
StaffUser = Annotated[SysUser, Depends(require_role("admin", "engineer"))]
