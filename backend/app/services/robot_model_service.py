"""机器人型号管理业务逻辑。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exception import AlreadyExistsException, ConflictException, NotFoundException
from app.models.brand import Brand
from app.models.controller import Controller
from app.models.robot_instance import RobotInstance
from app.models.robot_model import RobotModel
from app.models.servo_param import ServoParam
from app.schemas.robot_model import RobotModelCreate, RobotModelUpdate
from app.services.common import commit_or_conflict, get_or_404, paginate


class RobotModelService:
    def __init__(self, db: Session):
        self.db = db

    def _validate(self, payload) -> None:
        if self.db.get(Brand, payload.brand_id) is None:
            raise NotFoundException(message=f"品牌 {payload.brand_id} 不存在")
        if payload.controller_id is not None and self.db.get(Controller, payload.controller_id) is None:
            raise NotFoundException(message=f"控制器 {payload.controller_id} 不存在")

    def create(self, payload: RobotModelCreate) -> RobotModel:
        self._validate(payload)
        dup = select(RobotModel.id).where(
            RobotModel.brand_id == payload.brand_id, RobotModel.code == payload.code
        )
        if self.db.scalar(dup):
            raise AlreadyExistsException(message=f"该品牌下型号代码 {payload.code} 已存在")
        obj = RobotModel(**payload.model_dump())
        self.db.add(obj)
        commit_or_conflict(self.db)
        self.db.refresh(obj)
        return obj

    def get(self, model_id: int) -> RobotModel:
        return get_or_404(self.db, RobotModel, model_id, "机器人型号")

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        brand_id: int | None = None,
        controller_id: int | None = None,
        keyword: str | None = None,
    ) -> tuple[int, list[RobotModel]]:
        stmt = select(RobotModel)
        count_stmt = select(func.count(RobotModel.id))
        if brand_id is not None:
            stmt = stmt.where(RobotModel.brand_id == brand_id)
            count_stmt = count_stmt.where(RobotModel.brand_id == brand_id)
        if controller_id is not None:
            stmt = stmt.where(RobotModel.controller_id == controller_id)
            count_stmt = count_stmt.where(RobotModel.controller_id == controller_id)
        if keyword:
            like = f"%{keyword.strip()}%"
            cond = or_(RobotModel.code.ilike(like), RobotModel.name.ilike(like))
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        return paginate(self.db, stmt.order_by(RobotModel.id.desc()), count_stmt, page, page_size)

    def update(self, model_id: int, payload: RobotModelUpdate) -> RobotModel:
        obj = self.get(model_id)
        data = payload.model_dump(exclude_unset=True)
        if "brand_id" in data and self.db.get(Brand, data["brand_id"]) is None:
            raise NotFoundException(message=f"品牌 {data['brand_id']} 不存在")
        if "controller_id" in data and data["controller_id"] is not None:
            if self.db.get(Controller, data["controller_id"]) is None:
                raise NotFoundException(message=f"控制器 {data['controller_id']} 不存在")
        if "code" in data and data["code"] != obj.code:
            dup = select(RobotModel.id).where(
                RobotModel.brand_id == data.get("brand_id", obj.brand_id),
                RobotModel.code == data["code"],
                RobotModel.id != model_id,
            )
            if self.db.scalar(dup):
                raise AlreadyExistsException(message=f"该品牌下型号代码 {data['code']} 已存在")
        for field, value in data.items():
            setattr(obj, field, value)
        commit_or_conflict(self.db)
        self.db.refresh(obj)
        return obj

    def delete(self, model_id: int) -> None:
        obj = self.get(model_id)
        referenced = (
            self.db.scalar(
                select(func.count(RobotInstance.id)).where(RobotInstance.robot_model_id == model_id)
            )
            + self.db.scalar(
                select(func.count(ServoParam.id)).where(ServoParam.robot_model_id == model_id)
            )
        )
        if referenced:
            raise ConflictException(message="该型号被机器人实例/伺服参数引用，无法删除")
        self.db.delete(obj)
        commit_or_conflict(self.db)
