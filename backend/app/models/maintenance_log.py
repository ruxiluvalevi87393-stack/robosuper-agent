from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MaintenanceLog(Base):
    """维修历史：记录最终处理结果（故障、根因、所用 SOP/备件、停机时长）"""

    __tablename__ = "maintenance_log"
    __table_args__ = (
        Index("idx_maintenance_log_robot", "robot_instance_id"),
        Index("idx_maintenance_log_alarm", "alarm_code"),
        Index("idx_maintenance_log_work_no", "work_order_no"),
        Index("idx_maintenance_log_engineer", "engineer_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_no: Mapped[Optional[str]] = mapped_column(String(30))
    robot_instance_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("robot_instance.id"))
    alarm_code: Mapped[Optional[str]] = mapped_column(String(20))
    engineer_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("sys_user.id"))
    fault_description: Mapped[Optional[str]] = mapped_column(Text)
    root_cause: Mapped[Optional[str]] = mapped_column(Text)
    sop_used: Mapped[Optional[str]] = mapped_column(Text)
    parts_used: Mapped[Optional[dict]] = mapped_column(JSONB)
    downtime_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
