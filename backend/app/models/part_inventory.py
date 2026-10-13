from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PartInventory(Base):
    """备件库存（按 EPC 图号 + 仓库）"""

    __tablename__ = "part_inventory"
    __table_args__ = (
        UniqueConstraint("part_no", "warehouse", name="part_inventory_part_no_warehouse_key"),
        Index("idx_part_inventory_brand", "brand_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    part_no: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    brand_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("brand.id"))
    category: Mapped[Optional[str]] = mapped_column(String(50))
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    lead_time_days: Mapped[Optional[int]] = mapped_column(SmallInteger)
    compatible_brands: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    warehouse: Mapped[str] = mapped_column(String(50))
    location: Mapped[Optional[str]] = mapped_column(String(50))
    safety_stock: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
