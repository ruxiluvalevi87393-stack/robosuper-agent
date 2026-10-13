from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ServoParamHistory(Base):
    """伺服参数变更历史：可追溯谁在何时改了哪台设备的参数"""

    __tablename__ = "servo_param_history"
    __table_args__ = (
        Index(
            "idx_servo_param_history_param",
            "robot_instance_id",
            "param_code",
            text("changed_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    robot_instance_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("robot_instance.id"))
    robot_model_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("robot_model.id"))
    param_code: Mapped[str] = mapped_column(String(50))
    old_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    new_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    changed_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("sys_user.id"))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
