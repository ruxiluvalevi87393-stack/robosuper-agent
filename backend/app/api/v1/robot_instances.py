"""机器人实例路由：读=任意登录用户，写=admin。"""
from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, CurrentUser, DBSession
from app.schemas.common import PageOut
from app.schemas.robot_instance import RobotInstanceCreate, RobotInstanceOut, RobotInstanceUpdate
from app.services.robot_instance_service import RobotInstanceService

router = APIRouter(prefix="/robot-instances", tags=["机器人实例"])


@router.post("", response_model=RobotInstanceOut, status_code=status.HTTP_201_CREATED)
def create_instance(payload: RobotInstanceCreate, db: DBSession, _: AdminUser) -> RobotInstanceOut:
    return RobotInstanceService(db).create(payload)


@router.get("", response_model=PageOut[RobotInstanceOut])
def list_instances(
    db: DBSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    robot_model_id: int | None = Query(None, description="按型号筛选"),
    status: str | None = Query(None, description="按运行状态筛选"),
    line_id: str | None = Query(None, description="按产线筛选"),
    keyword: str | None = Query(None, description="资产编号/名称模糊搜索"),
) -> dict:
    total, items = RobotInstanceService(db).list(
        page=page,
        page_size=page_size,
        robot_model_id=robot_model_id,
        status=status,
        line_id=line_id,
        keyword=keyword,
    )
    return {"total": total, "items": items}


@router.get("/{instance_id}", response_model=RobotInstanceOut)
def get_instance(instance_id: int, db: DBSession, _: CurrentUser) -> RobotInstanceOut:
    return RobotInstanceService(db).get(instance_id)


@router.put("/{instance_id}", response_model=RobotInstanceOut)
def update_instance(
    instance_id: int, payload: RobotInstanceUpdate, db: DBSession, _: AdminUser
) -> RobotInstanceOut:
    return RobotInstanceService(db).update(instance_id, payload)


@router.delete("/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_instance(instance_id: int, db: DBSession, _: AdminUser) -> None:
    RobotInstanceService(db).delete(instance_id)
