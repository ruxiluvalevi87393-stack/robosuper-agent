"""inventory_mcp 真实后端：PG 备件**库存**维度（real-only，SQLAlchemy 直连）。

职责（对齐 plan.md §6.3）：库存 —— quantity/warehouse/location/safety_stock，
与 epc_parts_mcp（9103）按"目录 vs 库存"切分。包含跨库调拨（transfer_part，写操作）。

库存水位由本层派生（out/low/ok），避免 agent 自己拿 quantity 与 safety_stock 比较。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from common.db import engine


def _run(query: str, **params: Any) -> list[dict[str, Any]]:
    with engine().connect() as conn:
        return [dict(r) for r in conn.execute(text(query), params).mappings().all()]


def _stock_status(quantity: int, safety_stock: int) -> str:
    if quantity <= 0:
        return "out"
    if quantity < safety_stock:
        return "low"
    return "ok"


def real_check_stock(part_no: str, warehouse: str | None = None) -> dict[str, Any]:
    """跨仓库库存查询，附库存水位（out/low/ok）与总量。"""
    rows = _run(
        """
        SELECT p.part_no, p.name, p.warehouse, p.location, p.quantity, p.safety_stock,
               b.code AS brand_code
        FROM part_inventory p
        LEFT JOIN brand b ON b.id = p.brand_id
        WHERE p.part_no = :part_no
          AND (:warehouse IS NULL OR p.warehouse = :warehouse)
        ORDER BY p.warehouse
        """,
        part_no=part_no,
        warehouse=warehouse,
    )
    if not rows:
        return {"found": False, "part_no": part_no, "hint": "未找到该备件的库存记录"}
    warehouses = [
        {
            "warehouse": r["warehouse"],
            "location": r["location"],
            "quantity": r["quantity"],
            "safety_stock": r["safety_stock"],
            "status": _stock_status(r["quantity"] or 0, r["safety_stock"] or 0),
        }
        for r in rows
    ]
    total = sum(w["quantity"] for w in warehouses)
    return {
        "found": True,
        "part_no": part_no,
        "name": rows[0]["name"],
        "brand": rows[0]["brand_code"],
        "total_quantity": total,
        "low_stock": any(w["status"] == "low" for w in warehouses),
        "out_of_stock": any(w["status"] == "out" for w in warehouses),
        "warehouses": warehouses,
    }


def real_get_warehouse_list() -> dict[str, Any]:
    """仓库列表：每仓备件种类/总库存/低于安全库存的种类数。"""
    rows = _run(
        """
        SELECT warehouse,
               COUNT(DISTINCT part_no) AS part_kinds,
               SUM(quantity) AS total_qty,
               COUNT(*) FILTER (WHERE quantity < safety_stock) AS low_kinds
        FROM part_inventory
        GROUP BY warehouse
        ORDER BY warehouse
        """
    )
    return {
        "ok": True,
        "count": len(rows),
        "warehouses": [
            {
                "warehouse": r["warehouse"],
                "part_kinds": r["part_kinds"],
                "total_qty": int(r["total_qty"] or 0),
                "low_kinds": r["low_kinds"],
            }
            for r in rows
        ],
    }


def real_transfer_part(
    part_no: str,
    from_warehouse: str,
    to_warehouse: str,
    quantity: int,
    operator: str | None = None,
) -> dict[str, Any]:
    """跨库调拨：源仓减、目标仓加，单事务；目标仓无记录则新建（继承目录属性）。

    前置校验：quantity>0、源仓有货、不可自调。不校验 operator 是否存在（流水审计由上层负责）。
    """
    if quantity <= 0:
        return {"ok": False, "error": "quantity 必须为正整数", "part_no": part_no}
    if from_warehouse == to_warehouse:
        return {
            "ok": False,
            "error": "源仓与目标仓相同，无需调拨",
            "part_no": part_no,
        }

    try:
        with engine().begin() as conn:
            src = conn.execute(
                text(
                    """
                    SELECT part_no, quantity, name, category, price, lead_time_days,
                           compatible_brands, brand_id, safety_stock, location
                    FROM part_inventory
                    WHERE part_no = :part_no AND warehouse = :wh
                    FOR UPDATE
                    """
                ),
                {"part_no": part_no, "wh": from_warehouse},
            ).mappings().first()
            if src is None:
                return {
                    "ok": False,
                    "error": f"源仓 {from_warehouse} 无 {part_no} 库存记录",
                    "part_no": part_no,
                }
            if src["quantity"] < quantity:
                return {
                    "ok": False,
                    "error": f"源仓 {from_warehouse} 库存不足（现有 {src['quantity']}，需 {quantity}）",
                    "part_no": part_no,
                    "current_quantity": src["quantity"],
                }

            tgt = conn.execute(
                text(
                    """
                    SELECT quantity FROM part_inventory
                    WHERE part_no = :part_no AND warehouse = :wh
                    FOR UPDATE
                    """
                ),
                {"part_no": part_no, "wh": to_warehouse},
            ).mappings().first()
            if tgt is None:
                conn.execute(
                    text(
                        """
                        INSERT INTO part_inventory
                            (part_no, name, brand_id, category, price, lead_time_days,
                             compatible_brands, quantity, warehouse, location, safety_stock)
                        VALUES
                            (:part_no, :name, :brand_id, :category, :price, :lead_time_days,
                             :compatible_brands, :quantity, :warehouse, NULL, :safety_stock)
                        """
                    ),
                    {
                        "part_no": part_no,
                        "name": src["name"],
                        "brand_id": src["brand_id"],
                        "category": src["category"],
                        "price": src["price"],
                        "lead_time_days": src["lead_time_days"],
                        "compatible_brands": src["compatible_brands"],
                        "quantity": quantity,
                        "warehouse": to_warehouse,
                        "safety_stock": src["safety_stock"],
                    },
                )
                tgt_new_qty = quantity
            else:
                conn.execute(
                    text(
                        "UPDATE part_inventory SET quantity = quantity + :q "
                        "WHERE part_no = :part_no AND warehouse = :wh"
                    ),
                    {"q": quantity, "part_no": part_no, "wh": to_warehouse},
                )
                tgt_new_qty = tgt["quantity"] + quantity

            src_new_qty = src["quantity"] - quantity
            conn.execute(
                text(
                    "UPDATE part_inventory SET quantity = :q "
                    "WHERE part_no = :part_no AND warehouse = :wh"
                ),
                {"q": src_new_qty, "part_no": part_no, "wh": from_warehouse},
            )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"调拨失败: {exc}", "part_no": part_no}

    return {
        "ok": True,
        "part_no": part_no,
        "from_warehouse": from_warehouse,
        "to_warehouse": to_warehouse,
        "quantity": quantity,
        "result": {
            "from_quantity": src_new_qty,
            "to_quantity": tgt_new_qty,
        },
        "operator": operator,
    }
