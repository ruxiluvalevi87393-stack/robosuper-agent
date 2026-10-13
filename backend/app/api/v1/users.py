"""用户管理路由：仅 admin 可操作。"""
from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, DBSession
from app.schemas.user import UserCreate, UserListOut, UserOut, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DBSession, _: AdminUser) -> SysUser:
    return UserService(db).create_user(payload)


@router.get("", response_model=UserListOut)
def list_users(
    db: DBSession,
    _: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, description="用户名/姓名模糊搜索"),
    role: str | None = Query(None, description="角色筛选"),
    is_active: bool | None = Query(None, description="启用状态筛选"),
) -> dict:
    total, items = UserService(db).list_users(
        page=page,
        page_size=page_size,
        keyword=keyword,
        role=role,
        is_active=is_active,
    )
    return {"total": total, "items": items}


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: DBSession, _: AdminUser) -> SysUser:
    return UserService(db).get_user(user_id)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: DBSession,
    operator: AdminUser,
) -> SysUser:
    return UserService(db).update_user(user_id, payload, operator=operator)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_user(user_id: int, db: DBSession, operator: AdminUser) -> None:
    UserService(db).soft_delete_user(user_id, operator=operator)
