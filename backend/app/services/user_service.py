"""用户管理业务逻辑。

约定：
- 所有方法接收业务层 schema（schemas/user.py 的请求模型），返回 ORM 对象或数据。
- 异常统一抛 app.core.exception 中的业务异常，由全局处理器转 HTTP。
- 敏感业务规则集中在 service，API 层只做路由与参数绑定。
"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exception import (
    AlreadyExistsException,
    ConflictException,
    NotFoundException,
)
from app.core.security import hash_password
from app.models.sys_user import SysUser
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    """用户管理：创建 / 查询 / 列表 / 更新 / 软删禁用。"""

    def __init__(self, db: Session):
        self.db = db

    # ---------- 创建 ----------

    def create_user(self, payload: UserCreate) -> SysUser:
        username = payload.username.strip()
        exists = self.db.scalar(select(SysUser.id).where(SysUser.username == username))
        if exists:
            raise AlreadyExistsException(message=f"用户名 {username} 已存在")

        user = SysUser(
            username=username,
            password_hash=hash_password(payload.password),
            role=payload.role,
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            is_active=payload.is_active,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    # ---------- 查询 ----------

    def get_user(self, user_id: int) -> SysUser:
        user = self.db.get(SysUser, user_id)
        if user is None:
            raise NotFoundException(message=f"用户 {user_id} 不存在")
        return user

    def list_users(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[int, list[SysUser]]:
        """分页 + 关键词（用户名/姓名）+ 角色 + 启停状态筛选。"""
        stmt = select(SysUser)
        count_stmt = select(func.count(SysUser.id))

        conditions = []
        if keyword:
            like = f"%{keyword.strip()}%"
            conditions.append(or_(SysUser.username.ilike(like), SysUser.name.ilike(like)))
        if role:
            conditions.append(SysUser.role == role)
        if is_active is not None:
            conditions.append(SysUser.is_active == is_active)

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        total = self.db.scalar(count_stmt) or 0
        items = self.db.scalars(
            stmt.order_by(SysUser.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return total, items

    # ---------- 更新 ----------

    def update_user(
        self,
        user_id: int,
        payload: UserUpdate,
        *,
        operator: SysUser,
    ) -> SysUser:
        """更新用户。

        - exclude_unset 实现「传哪个改哪个」，password 单独走哈希。
        - 自我保护：不能停用自己、不能把自己的角色移出 admin。
        - 兜底：不能把最后一个启用中的 admin 停用/降级。
        """
        user = self.get_user(user_id)
        data = payload.model_dump(exclude_unset=True)

        # 自我保护
        if user.id == operator.id:
            if data.get("is_active") is False:
                raise ConflictException(message="不能停用当前登录账号")
            if data.get("role") is not None and data["role"] != "admin":
                raise ConflictException(message="不能修改当前登录账号的 admin 角色")

        new_role = data.get("role", user.role)
        new_active = data.get("is_active", user.is_active)
        self._ensure_other_active_admin(
            user, is_active=new_active, role=new_role,
            reason="至少需要保留一个启用的 admin 账号",
        )

        for field, value in data.items():
            setattr(user, field, value)
        if "password" in data:
            user.password_hash = hash_password(data["password"])

        self.db.commit()
        self.db.refresh(user)
        return user

    # ---------- 软删（禁用） ----------

    def soft_delete_user(self, user_id: int, *, operator: SysUser) -> None:
        """软删除 = 置 is_active=False（保留数据，前端不可登录/不可操作）。"""
        user = self.get_user(user_id)
        if user.id == operator.id:
            raise ConflictException(message="不能禁用当前登录账号")
        if not user.is_active:
            raise ConflictException(message="该用户已处于禁用状态")
        self._ensure_other_active_admin(
            user, is_active=False, role=user.role,
            reason="至少需要保留一个启用的 admin 账号",
        )
        user.is_active = False
        self.db.commit()

    # ---------- 内部校验 ----------

    def _ensure_other_active_admin(
        self,
        target: SysUser,
        *,
        is_active: bool,
        role: str,
        reason: str,
    ) -> None:
        """目标用户若即将失去「启用 admin」身份，则必须有其他启用 admin 兜底。"""
        if target.is_active and target.role == "admin" and (not is_active or role != "admin"):
            other_active_admins = self.db.scalar(
                select(func.count(SysUser.id)).where(
                    SysUser.id != target.id,
                    SysUser.is_active.is_(True),
                    SysUser.role == "admin",
                )
            )
            if not other_active_admins:
                raise ConflictException(message=reason)
