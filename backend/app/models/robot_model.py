from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RobotModel(Base):
    """机器人型号（品牌 + 控制器确定一台的规格基线）"""

    __tablename__ = "robot_model"
    __table_args__ = (
        UniqueConstraint("brand_id", "code", name="robot_model_brand_id_code_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    brand_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("brand.id"))
    controller_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("controller.id"))
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(100))
    payload_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    reach_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    axes: Mapped[Optional[int]] = mapped_column(SmallInteger)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
