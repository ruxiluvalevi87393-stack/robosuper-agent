"""认证路由：登录/登出/me/改密。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.core.exception import UnauthorizedException
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.sys_user import SysUser
from app.schemas.auth import (
    ChangePasswordRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=TokenResponse)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DBSession,
) -> TokenResponse:
    user = db.execute(
        select(SysUser).where(SysUser.username == form.username)
    ).scalar_one_or_none()

    if user is None or not verify_password(form.password, user.password_hash):
        raise UnauthorizedException("用户名或密码错误")

    if not user.is_active:
        raise UnauthorizedException("账号已禁用")

    token = create_access_token(
        {"user_id": user.id, "username": user.username, "role": user.role}
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )


@router.post("/logout")
def logout(user: CurrentUser) -> dict:
    # JWT 无状态，前端清 token 即可
    return {"message": "已登出"}


@router.get("/me", response_model=UserOut)
def get_me(user: CurrentUser) -> UserOut:
    return user


@router.put("/password")
def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, db: DBSession
) -> dict:
    if not verify_password(payload.old_password, user.password_hash):
        raise UnauthorizedException("原密码错误")

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"message": "密码修改成功"}
