"""备件库存管理业务逻辑。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exception import AlreadyExistsException, NotFoundException
from app.models.brand import Brand
from app.models.part_inventory import PartInventory
from app.schemas.part_inventory import PartInventoryCreate, PartInventoryUpdate
from app.services.common import commit_or_conflict, get_or_404, paginate


class PartInventoryService:
    def __init__(self, db: Session):
        self.db = db

    def _validate(self, payload) -> None:
        if payload.brand_id is not None and self.db.get(Brand, payload.brand_id) is None:
            raise NotFoundException(message=f"品牌 {payload.brand_id} 不存在")

    def create(self, payload: PartInventoryCreate) -> PartInventory:
        self._validate(payload)
        dup = select(PartInventory.id).where(
            PartInventory.part_no == payload.part_no, PartInventory.warehouse == payload.warehouse
        )
        if self.db.scalar(dup):
            raise AlreadyExistsException(
                message=f"备件 {payload.part_no} 在仓库 {payload.warehouse} 已存在"
            )
        obj = PartInventory(**payload.model_dump())
        self.db.add(obj)
        commit_or_conflict(self.db)
        self.db.refresh(obj)
        return obj

    def get(self, record_id: int) -> PartInventory:
        return get_or_404(self.db, PartInventory, record_id, "库存记录")

    def list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        brand_id: int | None = None,
        category: str | None = None,
        warehouse: str | None = None,
        low_stock: bool | None = None,
    ) -> tuple[int, list[PartInventory]]:
        stmt = select(PartInventory)
        count_stmt = select(func.count(PartInventory.id))
        if keyword:
            like = f"%{keyword.strip()}%"
            cond = or_(PartInventory.part_no.ilike(like), PartInventory.name.ilike(like))
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        if brand_id is not None:
            stmt = stmt.where(PartInventory.brand_id == brand_id)
            count_stmt = count_stmt.where(PartInventory.brand_id == brand_id)
        if category:
            stmt = stmt.where(PartInventory.category == category)
            count_stmt = count_stmt.where(PartInventory.category == category)
        if warehouse:
            stmt = stmt.where(PartInventory.warehouse == warehouse)
            count_stmt = count_stmt.where(PartInventory.warehouse == warehouse)
        if low_stock is True:
            cond = PartInventory.quantity <= PartInventory.safety_stock
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        return paginate(self.db, stmt.order_by(PartInventory.id.desc()), count_stmt, page, page_size)

    def update(self, record_id: int, payload: PartInventoryUpdate) -> PartInventory:
        obj = self.get(record_id)
        data = payload.model_dump(exclude_unset=True)
        if "brand_id" in data and data["brand_id"] is not None:
            if self.db.get(Brand, data["brand_id"]) is None:
                raise NotFoundException(message=f"品牌 {data['brand_id']} 不存在")
        if ("part_no" in data or "warehouse" in data) and (
            data.get("part_no", obj.part_no) != obj.part_no
            or data.get("warehouse", obj.warehouse) != obj.warehouse
        ):
            dup = select(PartInventory.id).where(
                PartInventory.part_no == data.get("part_no", obj.part_no),
                PartInventory.warehouse == data.get("warehouse", obj.warehouse),
                PartInventory.id != record_id,
            )
            if self.db.scalar(dup):
                raise AlreadyExistsException(message="该图号在目标仓库已存在")
        for field, value in data.items():
            setattr(obj, field, value)
        commit_or_conflict(self.db)
        self.db.refresh(obj)
        return obj

    def delete(self, record_id: int) -> None:
        obj = self.get(record_id)
        self.db.delete(obj)
        commit_or_conflict(self.db)
