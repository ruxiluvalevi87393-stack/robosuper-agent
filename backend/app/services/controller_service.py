"""控制器型号管理业务逻辑。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exception import AlreadyExistsException, ConflictException, NotFoundException
from app.models.brand import Brand
from app.models.controller import Controller
from app.models.robot_model import RobotModel
from app.schemas.controller import ControllerCreate, ControllerUpdate
from app.services.common import commit_or_conflict, get_or_404, paginate


class ControllerService:
    def __init__(self, db: Session):
        self.db = db

    def _validate(self, payload) -> None:
        if self.db.get(Brand, payload.brand_id) is None:
            raise NotFoundException(message=f"品牌 {payload.brand_id} 不存在")

    def create(self, payload: ControllerCreate) -> Controller:
        self._validate(payload)
        dup = select(Controller.id).where(
            Controller.brand_id == payload.brand_id, Controller.code == payload.code
        )
        if self.db.scalar(dup):
            raise AlreadyExistsException(
                message=f"该品牌下控制器代码 {payload.code} 已存在"
            )
        obj = Controller(**payload.model_dump())
        self.db.add(obj)
        commit_or_conflict(self.db)
        self.db.refresh(obj)
        return obj

    def get(self, controller_id: int) -> Controller:
        return get_or_404(self.db, Controller, controller_id, "控制器")

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        brand_id: int | None = None,
        keyword: str | None = None,
    ) -> tuple[int, list[Controller]]:
        stmt = select(Controller)
        count_stmt = select(func.count(Controller.id))
        if brand_id is not None:
            stmt = stmt.where(Controller.brand_id == brand_id)
            count_stmt = count_stmt.where(Controller.brand_id == brand_id)
        if keyword:
            like = f"%{keyword.strip()}%"
            cond = or_(Controller.code.ilike(like), Controller.name.ilike(like))
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        return paginate(self.db, stmt.order_by(Controller.id.desc()), count_stmt, page, page_size)

    def update(self, controller_id: int, payload: ControllerUpdate) -> Controller:
        obj = self.get(controller_id)
        data = payload.model_dump(exclude_unset=True)
        if "brand_id" in data:
            if self.db.get(Brand, data["brand_id"]) is None:
                raise NotFoundException(message=f"品牌 {data['brand_id']} 不存在")
        if "code" in data and data["code"] != obj.code:
            dup = select(Controller.id).where(
                Controller.brand_id == data.get("brand_id", obj.brand_id),
                Controller.code == data["code"],
                Controller.id != controller_id,
            )
            if self.db.scalar(dup):
                raise AlreadyExistsException(message=f"该品牌下控制器代码 {data['code']} 已存在")
        for field, value in data.items():
            setattr(obj, field, value)
        commit_or_conflict(self.db)
        self.db.refresh(obj)
        return obj

    def delete(self, controller_id: int) -> None:
        obj = self.get(controller_id)
        referenced = self.db.scalar(
            select(func.count(RobotModel.id)).where(RobotModel.controller_id == controller_id)
        )
        if referenced:
            raise ConflictException(message="该控制器被机器人型号引用，无法删除")
        self.db.delete(obj)
        commit_or_conflict(self.db)
