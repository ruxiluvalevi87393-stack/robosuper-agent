from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ServoParam(Base):
    """伺服参数定义（按机器人型号维护默认值/上下限）"""

    __tablename__ = "servo_param"
    __table_args__ = (
        UniqueConstraint("robot_model_id", "param_code", name="servo_param_robot_model_id_param_code_key"),
        Index("idx_servo_param_model", "robot_model_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    robot_model_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("robot_model.id"))
    param_code: Mapped[str] = mapped_column(String(50))
    param_name: Mapped[str] = mapped_column(String(100))
    default_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    min_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    max_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    unit: Mapped[Optional[str]] = mapped_column(String(20))
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
