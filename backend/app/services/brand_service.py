"""品牌管理业务逻辑。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exception import AlreadyExistsException, ConflictException
from app.models.brand import Brand
from app.models.controller import Controller
from app.models.part_inventory import PartInventory
from app.models.robot_model import RobotModel
from app.schemas.brand import BrandCreate, BrandUpdate
from app.services.common import commit_or_conflict, get_or_404, paginate


class BrandService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: BrandCreate) -> Brand:
        if self.db.scalar(select(Brand.id).where(Brand.code == payload.code)):
            raise AlreadyExistsException(message=f"品牌代码 {payload.code} 已存在")
        brand = Brand(**payload.model_dump())
        self.db.add(brand)
        commit_or_conflict(self.db)
        self.db.refresh(brand)
        return brand

    def get(self, brand_id: int) -> Brand:
        return get_or_404(self.db, Brand, brand_id, "品牌")

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> tuple[int, list[Brand]]:
        stmt = select(Brand)
        count_stmt = select(func.count(Brand.id))
        if keyword:
            like = f"%{keyword.strip()}%"
            cond = or_(Brand.code.ilike(like), Brand.name.ilike(like), Brand.country.ilike(like))
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        return paginate(self.db, stmt.order_by(Brand.id.desc()), count_stmt, page, page_size)

    def update(self, brand_id: int, payload: BrandUpdate) -> Brand:
        brand = self.get(brand_id)
        data = payload.model_dump(exclude_unset=True)
        if "code" in data and data["code"] != brand.code:
            dup = select(Brand.id).where(Brand.code == data["code"], Brand.id != brand_id)
            if self.db.scalar(dup):
                raise AlreadyExistsException(message=f"品牌代码 {data['code']} 已存在")
        for field, value in data.items():
            setattr(brand, field, value)
        commit_or_conflict(self.db)
        self.db.refresh(brand)
        return brand

    def delete(self, brand_id: int) -> None:
        brand = self.get(brand_id)
        referenced = (
            self.db.scalar(select(func.count(Controller.id)).where(Controller.brand_id == brand_id))
            + self.db.scalar(select(func.count(RobotModel.id)).where(RobotModel.brand_id == brand_id))
            + self.db.scalar(select(func.count(PartInventory.id)).where(PartInventory.brand_id == brand_id))
        )
        if referenced:
            raise ConflictException(message="该品牌被控制器/型号/备件引用，无法删除")
        self.db.delete(brand)
        commit_or_conflict(self.db)
