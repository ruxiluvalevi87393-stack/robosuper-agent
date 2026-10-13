"""work_order_mcp 真实后端：PG 工单闭环（real-only，SQLAlchemy 直连，写为主）。

职责（对齐 plan.md §6.3）：报警→诊断→建工单→指派→处理→关单+维修历史 的运维闭环。
- 事务边界在服务内：建单单条写；关单 = 更新工单 + 写维修历史 单事务。
- 状态流转用**转移表**约束（created→assigned→in_progress→resolved→closed），
  杜绝跳级（如 created 直接 closed）。
- 工单号自动生成：WO-YYYY-NNNN（与种子数据格式一致，递增）。
- created_by / engineer / assignee 以 **username 自然键**传入，服务内解析为 id。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text

from common.db import engine

_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "created": {"assigned"},
    "assigned": {"in_progress"},
    "in_progress": {"resolved"},
    "resolved": {"closed"},
}
_VALID_STATUSES = set(_STATUS_TRANSITIONS) | {"closed"}
_VALID_PRIORITIES = {"low", "normal", "high", "urgent"}


def _run(query: str, **params: Any) -> list[dict[str, Any]]:
    with engine().connect() as conn:
        return [dict(r) for r in conn.execute(text(query), params).mappings().all()]


def _resolve_robot(asset_no: str | None) -> dict[str, Any] | None:
    if not asset_no:
        return None
    rows = _run(
        """
        SELECT ri.id, ri.asset_no, ri.status AS instance_status,
               rm.code AS model_code, b.code AS brand_code
        FROM robot_instance ri
        LEFT JOIN robot_model rm ON rm.id = ri.robot_model_id
        LEFT JOIN brand b ON b.id = rm.brand_id
        WHERE ri.asset_no = :asset
        """,
        asset=asset_no,
    )
    return rows[0] if rows else None


def _resolve_user(username: str | None) -> dict[str, Any] | None:
    if not username:
        return None
    rows = _run(
        "SELECT id, username, role FROM sys_user WHERE username = :u",
        u=username,
    )
    return rows[0] if rows else None


def _next_work_order_no() -> str:
    year = datetime.now().strftime("%Y")
    prefix = f"WO-{year}-"
    rows = _run(
        """
        SELECT COALESCE(MAX(SUBSTRING(work_order_no FROM '[0-9]+$')::int), 0) + 1 AS next_seq
        FROM work_order WHERE work_order_no LIKE :prefix
        """,
        prefix=f"{prefix}%",
    )
    return f"{prefix}{rows[0]['next_seq']:04d}"


def _get_wo(work_order_no: str) -> dict[str, Any] | None:
    rows = _run(
        """
        SELECT wo.*, ri.asset_no, rm.code AS model_code, b.code AS brand_code,
               a.username AS assignee_name, c.username AS creator_name
        FROM work_order wo
        LEFT JOIN robot_instance ri ON ri.id = wo.robot_instance_id
        LEFT JOIN robot_model rm ON rm.id = ri.robot_model_id
        LEFT JOIN brand b ON b.id = rm.brand_id
        LEFT JOIN sys_user a ON a.id = wo.assignee_id
        LEFT JOIN sys_user c ON c.id = wo.created_by
        WHERE wo.work_order_no = :no
        """,
        no=work_order_no,
    )
    return rows[0] if rows else None


def _wo_summary(wo: dict[str, Any]) -> dict[str, Any]:
    return {
        "work_order_no": wo["work_order_no"],
        "title": wo["title"],
        "priority": wo["priority"],
        "status": wo["status"],
        "alarm_code": wo["alarm_code"],
        "asset_no": wo["asset_no"],
        "model_code": wo["model_code"],
        "brand": wo["brand_code"],
        "assignee": wo["assignee_name"],
        "created_by": wo["creator_name"],
        "created_at": wo["created_at"].isoformat() if wo["created_at"] else None,
        "assigned_at": wo["assigned_at"].isoformat() if wo["assigned_at"] else None,
        "resolved_at": wo["resolved_at"].isoformat() if wo["resolved_at"] else None,
        "closed_at": wo["closed_at"].isoformat() if wo["closed_at"] else None,
    }


def real_create_work_order(
    asset_no: str | None,
    alarm_code: str | None,
    title: str,
    priority: str = "normal",
    description: str | None = None,
    created_by: str | None = None,
    diagnosis_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """建工单：由诊断结论（可选）生成 created 状态工单。"""
    if not title or not title.strip():
        return {"ok": False, "error": "title 不能为空"}
    if priority not in _VALID_PRIORITIES:
        return {
            "ok": False,
            "error": f"priority 非法（可选: {sorted(_VALID_PRIORITIES)}）",
            "priority": priority,
        }
    robot = _resolve_robot(asset_no) if asset_no else None
    if asset_no and robot is None:
        return {"ok": False, "error": f"资产号 {asset_no} 不存在（robot_instance 未找到）", "asset_no": asset_no}
    creator = _resolve_user(created_by) if created_by else None
    if created_by and creator is None:
        return {"ok": False, "error": f"创建人 {created_by} 不存在（sys_user 未找到）", "created_by": created_by}

    wo_no = _next_work_order_no()
    with engine().begin() as conn:
        res = conn.execute(
            text(
                """
                INSERT INTO work_order
                    (work_order_no, robot_instance_id, alarm_code, title, description,
                     priority, status, created_by, diagnosis_context)
                VALUES
                    (:no, :rid, :alarm, :title, :desc, :priority, 'created', :created_by,
                     CAST(:ctx AS jsonb))
                RETURNING id
                """
            ),
            {
                "no": wo_no,
                "rid": robot["id"] if robot else None,
                "alarm": alarm_code,
                "title": title.strip(),
                "desc": description,
                "priority": priority,
                "created_by": creator["id"] if creator else None,
                "ctx": json.dumps(diagnosis_context, ensure_ascii=False) if diagnosis_context else None,
            },
        ).mappings().first()
        new_id = res["id"]
    return {
        "ok": True,
        "work_order_no": wo_no,
        "id": new_id,
        "status": "created",
        "robot_instance_id": robot["id"] if robot else None,
    }


def real_assign_engineer(work_order_no: str, engineer: str) -> dict[str, Any]:
    """指派工程师：created→assigned；已指派/处理中可改派（状态不变）。"""
    wo = _get_wo(work_order_no)
    if wo is None:
        return {"ok": False, "error": f"工单 {work_order_no} 不存在"}
    eng = _resolve_user(engineer)
    if eng is None:
        return {"ok": False, "error": f"工程师 {engineer} 不存在（sys_user 未找到）", "engineer": engineer}
    if eng["role"] not in ("engineer", "admin"):
        return {"ok": False, "error": f"用户 {engineer} 角色为 {eng['role']}，不可指派为处理人"}

    cur = wo["status"]
    if cur not in ("created", "assigned", "in_progress"):
        return {"ok": False, "error": f"工单当前状态 {cur} 不可指派", "status": cur}
    new_status = "assigned" if cur == "created" else cur
    with engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE work_order SET assignee_id = :uid, "
                "assigned_at = COALESCE(assigned_at, now()), status = :st "
                "WHERE work_order_no = :no"
            ),
            {"uid": eng["id"], "st": new_status, "no": work_order_no},
        )
    return {
        "ok": True,
        "work_order_no": work_order_no,
        "assignee": engineer,
        "status": new_status,
        "prev_status": cur,
    }


def real_update_work_order_status(work_order_no: str, status: str) -> dict[str, Any]:
    """状态流转（转移表约束，禁止跳级）。"""
    if status not in _VALID_STATUSES:
        return {"ok": False, "error": f"status 非法（可选: {sorted(_VALID_STATUSES)}）", "status": status}
    wo = _get_wo(work_order_no)
    if wo is None:
        return {"ok": False, "error": f"工单 {work_order_no} 不存在"}
    cur = wo["status"]
    if cur == status:
        return {"ok": True, "work_order_no": work_order_no, "from": cur, "to": status, "noop": True}
    allowed = _STATUS_TRANSITIONS.get(cur, set())
    if status not in allowed:
        return {
            "ok": False,
            "work_order_no": work_order_no,
            "error": f"非法流转 {cur} → {status}",
            "from": cur,
            "allowed": sorted(allowed),
        }
    with engine().begin() as conn:
        conn.execute(
            text(
                """
                UPDATE work_order
                SET status = :st,
                    resolved_at = CASE WHEN :st = 'resolved' THEN now() ELSE resolved_at END,
                    closed_at = CASE WHEN :st = 'closed' THEN now() ELSE closed_at END
                WHERE work_order_no = :no
                """
            ),
            {"st": status, "no": work_order_no},
        )
    return {"ok": True, "work_order_no": work_order_no, "from": cur, "to": status}


def real_list_work_orders(
    status: str | None = None,
    priority: str | None = None,
    engineer: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """工单列表：按状态/优先级/处理人过滤，倒序。"""
    if status and status not in _VALID_STATUSES:
        return {"ok": False, "error": f"status 非法（可选: {sorted(_VALID_STATUSES)}）", "status": status}
    rows = _run(
        """
        SELECT wo.*, ri.asset_no, rm.code AS model_code, b.code AS brand_code,
               a.username AS assignee_name, c.username AS creator_name
        FROM work_order wo
        LEFT JOIN robot_instance ri ON ri.id = wo.robot_instance_id
        LEFT JOIN robot_model rm ON rm.id = ri.robot_model_id
        LEFT JOIN brand b ON b.id = rm.brand_id
        LEFT JOIN sys_user a ON a.id = wo.assignee_id
        LEFT JOIN sys_user c ON c.id = wo.created_by
        WHERE (:status IS NULL OR wo.status = :status)
          AND (:priority IS NULL OR wo.priority = :priority)
          AND (:eng IS NULL OR a.username = :eng)
        ORDER BY wo.created_at DESC
        LIMIT :limit
        """,
        status=status,
        priority=priority,
        eng=engineer,
        limit=limit,
    )
    items = [_wo_summary(r) for r in rows]
    return {"ok": True, "count": len(items), "items": items}


def real_get_work_order_detail(work_order_no: str) -> dict[str, Any]:
    """工单详情：全部字段 + 诊断上下文快照 + 机器人信息。"""
    wo = _get_wo(work_order_no)
    if wo is None:
        return {"found": False, "work_order_no": work_order_no, "hint": "工单不存在"}
    return {
        "found": True,
        **_wo_summary(wo),
        "description": wo["description"],
        "diagnosis_context": wo["diagnosis_context"],
        "robot_instance_id": wo["robot_instance_id"],
        "assignee_id": wo["assignee_id"],
        "created_by_id": wo["created_by"],
    }


def real_close_work_order(
    work_order_no: str,
    root_cause: str | None = None,
    sop_used: str | None = None,
    parts_used: dict[str, Any] | None = None,
    downtime_minutes: int | None = None,
    fault_description: str | None = None,
    engineer: str | None = None,
) -> dict[str, Any]:
    """关单：仅 resolved 可关；单事务 = 置 closed + 写维修历史（maintenance_log）。"""
    wo = _get_wo(work_order_no)
    if wo is None:
        return {"ok": False, "error": f"工单 {work_order_no} 不存在"}
    if wo["status"] != "resolved":
        return {
            "ok": False,
            "error": f"仅 resolved 状态的工单可关单（当前 {wo['status']}）",
            "status": wo["status"],
            "hint": "先用 update_work_order_status 流转到 resolved",
        }
    eng = _resolve_user(engineer) if engineer else None
    if engineer and eng is None:
        return {"ok": False, "error": f"工程师 {engineer} 不存在（sys_user 未找到）", "engineer": engineer}

    with engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE work_order SET status = 'closed', closed_at = now() "
                "WHERE work_order_no = :no"
            ),
            {"no": work_order_no},
        )
        res = conn.execute(
            text(
                """
                INSERT INTO maintenance_log
                    (work_order_no, robot_instance_id, alarm_code, engineer_id,
                     fault_description, root_cause, sop_used, parts_used,
                     downtime_minutes, occurred_at)
                VALUES
                    (:no, :rid, :alarm, :eng,
                     :fault, :root, :sop, CAST(:parts AS jsonb),
                     :downtime, now())
                RETURNING id
                """
            ),
            {
                "no": work_order_no,
                "rid": wo["robot_instance_id"],
                "alarm": wo["alarm_code"],
                "eng": eng["id"] if eng else None,
                "fault": fault_description,
                "root": root_cause,
                "sop": sop_used,
                "parts": json.dumps(parts_used, ensure_ascii=False) if parts_used else None,
                "downtime": downtime_minutes,
            },
        ).mappings().first()
        log_id = res["id"]
    return {
        "ok": True,
        "work_order_no": work_order_no,
        "status": "closed",
        "maintenance_log_id": log_id,
    }
