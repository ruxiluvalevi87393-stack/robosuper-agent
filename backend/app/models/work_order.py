from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WorkOrder(Base):
    """排障工单：报警→诊断→指派→处理→验收的运维闭环"""

    __tablename__ = "work_order"
    __table_args__ = (
        CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="work_order_priority_check"),
        CheckConstraint(
            "status IN ('created', 'assigned', 'in_progress', 'resolved', 'closed')",
            name="work_order_status_check",
        ),
        Index("idx_work_order_status", "status", "priority"),
        Index("idx_work_order_assignee", "assignee_id"),
        Index("idx_work_order_alarm", "alarm_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_order_no: Mapped[str] = mapped_column(String(30), unique=True)
    robot_instance_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("robot_instance.id"))
    alarm_code: Mapped[Optional[str]] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    status: Mapped[str] = mapped_column(String(20), default="created")
    assignee_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("sys_user.id"))
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("sys_user.id"))
    diagnosis_context: Mapped[Optional[dict]] = mapped_column(JSONB)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
