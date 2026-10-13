"""CLI：演示数据 mock —— 填充运行时操作表。

用法（backend/ 目录下）：
    python -m scripts.load.seed_operational            # 幂等：按自然键只补缺失行，已存在则跳过
    python -m scripts.load.seed_operational --reset    # 先清空 6 张操作表 + 非 admin 用户，再全量重建

对齐设计稿 §3.3 seed_operational.py，引用全部解析到真实数据：
- alarm_code 采样自 canonical alarms（真实码，含 title/cause/remedy），避免孤儿引用；
- robot_model / brand 引用 robot_models.json / brands.json 对应主数据；
- part_no 来自 canonical parts.json 备件目录（与图谱 Part 节点共用自然键），
  maintenance_log.parts_used 与其一致。
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select, text

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.brand import Brand
from app.models.maintenance_log import MaintenanceLog
from app.models.part_inventory import PartInventory
from app.models.robot_instance import RobotInstance
from app.models.robot_model import RobotModel
from app.models.servo_param import ServoParam
from app.models.servo_param_history import ServoParamHistory
from app.models.sys_user import SysUser
from app.models.work_order import WorkOrder

CANONICAL = Path(__file__).resolve().parent.parent.parent / "data" / "canonical"
_DEMO_PASSWORD = "123456"

_ENGINEERS = [
    dict(username="zhangwei", name="张伟", role="engineer"),
    dict(username="liqiang", name="李强", role="engineer"),
    dict(username="wangfang", name="王芳", role="engineer"),
    dict(username="chenjing", name="陈静", role="viewer"),
]

_INSTANCES = [
    dict(asset_no="RB-FAN-001", model_code="M-20iA", name="焊接工位1号机", serial="FNM20-201103",
         line_id="W1", install="2021-03-15", status="running", note="日常点检正常"),
    dict(asset_no="RB-FAN-002", model_code="M-20iA", name="码垛工位机器人", serial="FNM20-210708",
         line_id="P1", install="2021-09-20", status="maintenance", note="编码器电池更换中"),
    dict(asset_no="RB-FAN-003", model_code="M-20iA", name="上下料工位2号机", serial="FNM20-220514",
         line_id="W2", install="2022-06-11", status="alarm", note="碰撞报警待处理"),
    dict(asset_no="RB-KUK-001", model_code="KR 16", name="装配线A机器人", serial="K16-190822",
         line_id="A1", install="2020-05-08", status="running", note=""),
    dict(asset_no="RB-KUK-002", model_code="KR 16", name="打磨工位机器人", serial="K16-211025",
         line_id="P2", install="2021-12-02", status="idle", note=""),
    dict(asset_no="RB-KUK-003", model_code="KR 16", name="焊接工位2号机", serial="K16-230119",
         line_id="W2", install="2023-02-27", status="offline", note="计划停机保养"),
]

def _load_parts_from_canonical() -> list[dict]:
    """从 canonical parts.json 读取备件目录，展开为 part_inventory 行（每 part × 每仓库一行）。

    与图谱 Part 节点共用 part_no 自然键，保证"诊断→备件→库存"链路可解析。
    """
    data = json.loads((CANONICAL / "parts.json").read_text(encoding="utf-8"))
    parts = data["parts"] if isinstance(data, dict) else data
    rows: list[dict] = []
    for p in parts:
        for w in p.get("warehouses") or []:
            rows.append(dict(
                part_no=p["part_no"], name=p["name"], brand=p["brand"],
                category=p.get("category"), price=p["price"], lead=p["lead_time_days"],
                compatible=p["compatible_brands"], qty=w["quantity"],
                warehouse=w["warehouse"], location=w.get("location"),
                safety=p.get("safety_stock", 0),
            ))
    return rows


_PARTS = _load_parts_from_canonical()

# param_code -> (param_name, default, min, max, unit, description)
_SERVO_PARAMS = {
    "M-20iA": [
        ("SV_POS_GAIN", "位置环增益", "5000", "100", "8000", "1/1000s", "位置环增益系数，提高响应速度"),
        ("SV_VEL_GAIN", "速度环增益", "120", "10", "300", "%", "速度环增益，过大易振荡"),
        ("SV_INERTIA", "惯量比", "100", "1", "2000", "%", "负载惯量与电机惯量比"),
        ("SV_ACC_FEED", "加速度前馈", "50", "0", "100", "%", "加速度前馈量，改善轨迹精度"),
        ("SV_TORQUE_LIMIT", "扭矩限制", "80", "0", "100", "%", "各轴最大扭矩百分比限制"),
        ("SV_LOAD_RATE", "伺服负载率", "60", "0", "200", "%", "实时负载率（只读参考）"),
    ],
    "KR 16": [
        ("SV_POS_GAIN", "位置环增益", "4800", "100", "8000", "1/1000s", "位置环增益系数，提高响应速度"),
        ("SV_VEL_GAIN", "速度环增益", "115", "10", "300", "%", "速度环增益，过大易振荡"),
        ("SV_INERTIA", "惯量比", "90", "1", "2000", "%", "负载惯量与电机惯量比"),
        ("SV_ACC_FEED", "加速度前馈", "45", "0", "100", "%", "加速度前馈量，改善轨迹精度"),
        ("SV_TORQUE_LIMIT", "扭矩限制", "75", "0", "100", "%", "各轴最大扭矩百分比限制"),
        ("SV_LOAD_RATE", "伺服负载率", "55", "0", "200", "%", "实时负载率（只读参考）"),
    ],
}

# (no, asset_no, brand, alarm_code, title, priority, status, assignee, desc, created)
_WORK_ORDERS = [
    dict(no="WO-2026-0001", asset_no="RB-FAN-003", brand="FANUC", code="PNT2-114",
         title="FANUC 上下料工位碰撞报警", priority="urgent", status="in_progress", assignee="zhangwei",
         desc="机器人在下料动作中出现碰撞报警，PLC 中断，需排查轨迹干涉与夹具干涉。",
         created=datetime(2026, 8, 10, 9, 30)),
    dict(no="WO-2025-0002", asset_no="RB-FAN-001", brand="FANUC", code="SRVO-001",
         title="FANUC 焊接工位操作面盘急停", priority="high", status="resolved", assignee="liqiang",
         desc="操作人员误按急停导致停机，需复位并确认安全回路。",
         created=datetime(2025, 12, 2, 14, 5)),
    dict(no="WO-2025-0003", asset_no="RB-FAN-002", brand="FANUC", code="SRVO-062",
         title="FANUC 码垛工位编码器电池报警", priority="normal", status="closed", assignee="wangfang",
         desc="编码器绝对位置电池电压低，需更换电池并脉冲复位。",
         created=datetime(2025, 10, 18, 11, 20)),
    dict(no="WO-2026-0004", asset_no="RB-KUK-003", brand="KUKA", code="2912",
         title="KUKA 焊接工位2号机碰撞预警", priority="urgent", status="assigned", assignee="liqiang",
         desc="KUKA 系统检测到即将与夹具碰撞，已触发限位，需检查焊枪姿态。",
         created=datetime(2026, 8, 11, 15, 0)),
    dict(no="WO-2025-0005", asset_no="RB-KUK-001", brand="KUKA", code="0001",
         title="KUKA 装配线A急停恢复", priority="normal", status="resolved", assignee="liqiang",
         desc="产线急停按钮被按下，复位后恢复运行。",
         created=datetime(2025, 6, 20, 8, 40)),
    dict(no="WO-2025-0006", asset_no="RB-KUK-002", brand="KUKA", code="0102",
         title="KUKA 打磨工位编码器缆线故障", priority="high", status="closed", assignee="zhangwei",
         desc="打磨工位 J3 轴编码器缆线信号丢失，需检查连接。",
         created=datetime(2025, 11, 5, 16, 10)),
    dict(no="WO-2026-0007", asset_no="RB-FAN-003", brand="FANUC", code="PNT1-072",
         title="FANUC 上下料工位追踪编码器断线", priority="normal", status="created", assignee=None,
         desc="追踪编码器缆线异常，待安排工程师现场排查。",
         created=datetime(2026, 8, 12, 10, 0)),
    dict(no="WO-2026-0008", asset_no="RB-KUK-003", brand="KUKA", code="2817",
         title="KUKA 焊接工位2号机编码器电池告警", priority="low", status="created", assignee=None,
         desc="编码器电池故障待确认，计划随保养窗口处理。",
         created=datetime(2026, 8, 12, 11, 30)),
]

# (work_order_no, asset_no, brand, alarm_code, engineer, fault, downtime_min, occurred, parts_used)
_MAINTENANCE_LOGS = [
    dict(no="WO-2026-0001", asset_no="RB-FAN-003", brand="FANUC", code="PNT2-114", engineer="zhangwei",
         fault="上下料时机械臂与物料托盘发生干涉碰撞，触发碰撞检测报警。",
         downtime=180, occurred=datetime(2026, 8, 10, 9, 30), parts_used={}),
    dict(no="WO-2025-0002", asset_no="RB-FAN-001", brand="FANUC", code="SRVO-001", engineer="liqiang",
         fault="操作面板急停按钮被按下导致停机，安全回路触发。",
         downtime=45, occurred=datetime(2025, 12, 2, 14, 5), parts_used={}),
    dict(no="WO-2025-0003", asset_no="RB-FAN-002", brand="FANUC", code="SRVO-062", engineer="wangfang",
         fault="编码器绝对位置备份电池电压低，掉电后位置丢失风险。",
         downtime=120, occurred=datetime(2025, 10, 18, 11, 20), parts_used={"A97L-0001-0176": 1}),
    dict(no="WO-2025-0005", asset_no="RB-KUK-001", brand="KUKA", code="0001", engineer="liqiang",
         fault="产线急停按钮被误触，EMERGENCY STOP 电路触发。",
         downtime=30, occurred=datetime(2025, 6, 20, 8, 40), parts_used={}),
    dict(no="WO-2025-0006", asset_no="RB-KUK-002", brand="KUKA", code="0102", engineer="zhangwei",
         fault="打磨工位 J3 轴编码器缆线信号丢失，连接松动导致反馈中断。",
         downtime=240, occurred=datetime(2025, 11, 5, 16, 10), parts_used={}),
]

# (asset_no, model_code, param_code, old, new, changed_by, reason, changed_at)
_PARAM_HISTORY = [
    dict(asset_no="RB-FAN-002", model_code="M-20iA", param_code="SV_LOAD_RATE", old="55", new="70",
         changed_by="liqiang", reason="负载增加后负载率报警，调整参数", changed_at=datetime(2026, 2, 10, 9, 0)),
    dict(asset_no="RB-FAN-003", model_code="M-20iA", param_code="SV_INERTIA", old="80", new="120",
         changed_by="zhangwei", reason="更换夹具后惯量比调整", changed_at=datetime(2026, 1, 28, 14, 30)),
    dict(asset_no="RB-KUK-001", model_code="KR 16", param_code="SV_POS_GAIN", old="5000", new="5600",
         changed_by="liqiang", reason="跟踪误差偏大，提高位置环增益", changed_at=datetime(2026, 2, 18, 10, 15)),
    dict(asset_no="RB-KUK-002", model_code="KR 16", param_code="SV_TORQUE_LIMIT", old="80", new="70",
         changed_by="wangfang", reason="降低扭矩限制误报", changed_at=datetime(2026, 3, 2, 16, 45)),
]


def _load_alarms() -> dict[str, dict[str, dict]]:
    """brand -> {code: alarm}，从 canonical alarms 提取真实报警（引用必可解析）。"""
    alarms: dict[str, dict[str, dict]] = {}
    for fp in sorted((CANONICAL / "alarms").glob("*_alarms.json")):
        brand = fp.stem.split("_")[0].upper()
        data = json.loads(fp.read_text(encoding="utf-8"))
        alarms[brand] = {a["code"]: a for a in data if a.get("code")}
    return alarms


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def _reset(db) -> None:
    db.execute(text(
        "TRUNCATE servo_param_history, maintenance_log, work_order, servo_param, "
        "part_inventory, robot_instance RESTART IDENTITY CASCADE"
    ))
    db.execute(text("DELETE FROM sys_user WHERE username != 'admin'"))


def seed_users(db) -> dict[str, int]:
    created = {}
    for u in _ENGINEERS:
        row = db.scalar(select(SysUser).where(SysUser.username == u["username"]))
        if row is None:
            row = SysUser(username=u["username"], name=u["name"], role=u["role"],
                          password_hash=hash_password(_DEMO_PASSWORD))
            db.add(row)
            db.flush()
        created[u["username"]] = row.id
    return created


def seed_instances(db) -> dict[str, int]:
    model_by_code = dict(db.execute(select(RobotModel.code, RobotModel.id)).all())
    ids: dict[str, int] = {}
    for it in _INSTANCES:
        row = db.scalar(select(RobotInstance).where(RobotInstance.asset_no == it["asset_no"]))
        if row is None:
            row = RobotInstance(
                robot_model_id=model_by_code[it["model_code"]],
                asset_no=it["asset_no"], name=it["name"], serial_no=it["serial"],
                line_id=it["line_id"], install_date=date.fromisoformat(it["install"]),
                status=it["status"], note=it["note"],
            )
            db.add(row)
            db.flush()
        ids[row.asset_no] = row.id
    return ids


def seed_parts(db) -> None:
    brand_by_code = dict(db.execute(select(Brand.code, Brand.id)).all())
    for p in _PARTS:
        row = db.scalar(select(PartInventory).where(
            PartInventory.part_no == p["part_no"], PartInventory.warehouse == p["warehouse"]))
        if row is None:
            db.add(PartInventory(
                part_no=p["part_no"], name=p["name"], brand_id=brand_by_code.get(p["brand"]),
                category=p["category"], price=Decimal(p["price"]), lead_time_days=p["lead"],
                compatible_brands=p["compatible"], quantity=p["qty"], warehouse=p["warehouse"],
                location=p["location"], safety_stock=p["safety"],
            ))


def seed_servo_params(db) -> None:
    model_by_code = dict(db.execute(select(RobotModel.code, RobotModel.id)).all())
    for model_code, params in _SERVO_PARAMS.items():
        model_id = model_by_code[model_code]
        for code, name, default, lo, hi, unit, desc in params:
            row = db.scalar(select(ServoParam).where(
                ServoParam.robot_model_id == model_id, ServoParam.param_code == code))
            if row is None:
                db.add(ServoParam(
                    robot_model_id=model_id, param_code=code, param_name=name,
                    default_value=Decimal(default), min_value=Decimal(lo), max_value=Decimal(hi),
                    unit=unit, description=desc,
                ))


def seed_work_orders(db, user_ids: dict[str, int], instance_ids: dict[str, int],
                    alarms: dict[str, dict[str, dict]]) -> None:
    admin_id = db.scalar(select(SysUser.id).where(SysUser.username == "admin"))
    for wo in _WORK_ORDERS:
        row = db.scalar(select(WorkOrder).where(WorkOrder.work_order_no == wo["no"]))
        if row is not None:
            continue
        alarm = alarms[wo["brand"]][wo["code"]]
        diag = {
            "graph_anchor": {"entity_type": "AlarmCode", "entity_key": f"{wo['brand']}|{wo['code']}"},
            "matched_alarm_title": alarm.get("title", ""),
            "suggested_remedy": (alarm.get("remedy") or "")[:400],
        }
        db.add(WorkOrder(
            work_order_no=wo["no"], robot_instance_id=instance_ids[wo["asset_no"]],
            alarm_code=wo["code"], title=wo["title"], description=wo["desc"],
            priority=wo["priority"], status=wo["status"],
            assignee_id=user_ids.get(wo["assignee"]) if wo["assignee"] else None,
            created_by=admin_id, diagnosis_context=diag,
            assigned_at=wo["created"] if wo["status"] != "created" else None,
            resolved_at=wo["created"].replace(hour=16, minute=30) if wo["status"] in ("resolved", "closed") else None,
            closed_at=wo["created"].replace(hour=17, minute=0) if wo["status"] == "closed" else None,
            created_at=wo["created"],
        ))


def seed_maintenance_logs(db, user_ids: dict[str, int], instance_ids: dict[str, int],
                          alarms: dict[str, dict[str, dict]]) -> None:
    if _count(db, MaintenanceLog) > 0:
        return
    for lg in _MAINTENANCE_LOGS:
        alarm = alarms[lg["brand"]][lg["code"]]
        db.add(MaintenanceLog(
            work_order_no=lg["no"], robot_instance_id=instance_ids[lg["asset_no"]],
            alarm_code=lg["code"], engineer_id=user_ids[lg["engineer"]],
            fault_description=lg["fault"], root_cause=alarm.get("cause") or "",
            sop_used=alarm.get("remedy") or "", parts_used=lg["parts_used"],
            downtime_minutes=lg["downtime"], occurred_at=lg["occurred"],
        ))


def seed_param_history(db, user_ids: dict[str, int], instance_ids: dict[str, int]) -> None:
    if _count(db, ServoParamHistory) > 0:
        return
    model_by_code = dict(db.execute(select(RobotModel.code, RobotModel.id)).all())
    for h in _PARAM_HISTORY:
        db.add(ServoParamHistory(
            robot_instance_id=instance_ids[h["asset_no"]],
            robot_model_id=model_by_code[h["model_code"]], param_code=h["param_code"],
            old_value=Decimal(h["old"]), new_value=Decimal(h["new"]),
            changed_by=user_ids[h["changed_by"]], reason=h["reason"], changed_at=h["changed_at"],
        ))


def _verify(db) -> None:
    tables = {
        "sys_user": SysUser, "robot_instance": RobotInstance, "part_inventory": PartInventory,
        "servo_param": ServoParam, "work_order": WorkOrder, "maintenance_log": MaintenanceLog,
        "servo_param_history": ServoParamHistory,
    }
    for name, model in tables.items():
        print(f"  {name:<20} {_count(db, model):>4}")
    assert db.scalar(select(func.count()).select_from(WorkOrder)) == len(_WORK_ORDERS), "work_order 数量不符"
    assert db.scalar(select(func.count()).select_from(MaintenanceLog)) == len(_MAINTENANCE_LOGS), "maintenance_log 数量不符"
    assert db.scalar(select(func.count()).select_from(PartInventory)) == len(_PARTS), "part_inventory 数量与 parts.json 不符"


def main() -> None:
    parser = argparse.ArgumentParser(description="演示数据 mock：填充运行时操作表")
    parser.add_argument("--reset", action="store_true", help="先清空操作表 + 非 admin 用户再重建")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            _reset(db)
            print("已清空操作表 + 非 admin 用户", flush=True)

        alarms = _load_alarms()
        user_ids = seed_users(db)
        instance_ids = seed_instances(db)
        seed_parts(db)
        seed_servo_params(db)
        seed_work_orders(db, user_ids, instance_ids, alarms)
        seed_maintenance_logs(db, user_ids, instance_ids, alarms)
        seed_param_history(db, user_ids, instance_ids)
        db.commit()

        print(f"填充完成（演示密码统一 {_DEMO_PASSWORD!r}）：")
        _verify(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
