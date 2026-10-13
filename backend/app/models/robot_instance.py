from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RobotInstance(Base):
    """机器人实例：客户现场的每一台具体设备（资产维度）"""

    __tablename__ = "robot_instance"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'idle', 'alarm', 'maintenance', 'offline')",
            name="robot_instance_status_check",
        ),
        Index("idx_robot_instance_model", "robot_model_id"),
        Index("idx_robot_instance_line", "line_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    robot_model_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("robot_model.id"))
    asset_no: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[Optional[str]] = mapped_column(String(100))
    serial_no: Mapped[Optional[str]] = mapped_column(String(50))
    line_id: Mapped[Optional[str]] = mapped_column(String(50))
    install_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="running")
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
