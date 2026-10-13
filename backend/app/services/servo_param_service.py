"""伺服参数定义管理业务逻辑。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exception import AlreadyExistsException, NotFoundException
from app.models.robot_model import RobotModel
from app.models.servo_param import ServoParam
from app.schemas.servo_param import ServoParamCreate, ServoParamUpdate
from app.services.common import commit_or_conflict, get_or_404, paginate


class ServoParamService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: ServoParamCreate) -> ServoParam:
        if self.db.get(RobotModel, payload.robot_model_id) is None:
            raise NotFoundException(message=f"机器人型号 {payload.robot_model_id} 不存在")
        dup = select(ServoParam.id).where(
            ServoParam.robot_model_id == payload.robot_model_id,
            ServoParam.param_code == payload.param_code,
        )
        if self.db.scalar(dup):
            raise AlreadyExistsException(
                message=f"该型号下参数 {payload.param_code} 已存在"
            )
        obj = ServoParam(**payload.model_dump())
        self.db.add(obj)
        commit_or_conflict(self.db)
        self.db.refresh(obj)
        return obj

    def get(self, param_id: int) -> ServoParam:
        return get_or_404(self.db, ServoParam, param_id, "伺服参数")

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        robot_model_id: int | None = None,
        keyword: str | None = None,
    ) -> tuple[int, list[ServoParam]]:
        stmt = select(ServoParam)
        count_stmt = select(func.count(ServoParam.id))
        if robot_model_id is not None:
            stmt = stmt.where(ServoParam.robot_model_id == robot_model_id)
            count_stmt = count_stmt.where(ServoParam.robot_model_id == robot_model_id)
        if keyword:
            like = f"%{keyword.strip()}%"
            cond = or_(ServoParam.param_code.ilike(like), ServoParam.param_name.ilike(like))
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        return paginate(self.db, stmt.order_by(ServoParam.id.desc()), count_stmt, page, page_size)

    def update(self, param_id: int, payload: ServoParamUpdate) -> ServoParam:
        obj = self.get(param_id)
        data = payload.model_dump(exclude_unset=True)
        if "robot_model_id" in data and self.db.get(RobotModel, data["robot_model_id"]) is None:
            raise NotFoundException(message=f"机器人型号 {data['robot_model_id']} 不存在")
        if "param_code" in data and data["param_code"] != obj.param_code:
            dup = select(ServoParam.id).where(
                ServoParam.robot_model_id == data.get("robot_model_id", obj.robot_model_id),
                ServoParam.param_code == data["param_code"],
                ServoParam.id != param_id,
            )
            if self.db.scalar(dup):
                raise AlreadyExistsException(message=f"该型号下参数 {data['param_code']} 已存在")
        for field, value in data.items():
            setattr(obj, field, value)
        commit_or_conflict(self.db)
        self.db.refresh(obj)
        return obj

    def delete(self, param_id: int) -> None:
        obj = self.get(param_id)
        self.db.delete(obj)
        commit_or_conflict(self.db)
