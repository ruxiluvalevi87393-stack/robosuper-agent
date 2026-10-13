"""epc_parts_mcp 真实后端：PG 备件**目录**查询（real-only，SQLAlchemy 直连）。

职责（对齐 plan.md §6.3）：备件目录维度 —— part_no/name/brand/category/price/lead_time/
compatible_brands；**不含库存**（库存归 inventory_mcp，两者按"目录 vs 库存"切分）。

注意 part_inventory 表唯一键是 (part_no, warehouse)，同一 part_no 可跨多仓库 →
目录维度按 part_no 聚合（SUM quantity / COUNT DISTINCT warehouse）。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from common.db import engine


def _run(query: str, **params: Any) -> list[dict[str, Any]]:
    with engine().connect() as conn:
        return [dict(r) for r in conn.execute(text(query), params).mappings().all()]


def _num(v: Any) -> float | None:
    return float(v) if v is not None else None


def real_search_part(
    keyword: str | None = None,
    brand: str | None = None,
    category: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """按关键词/图号/分类搜备件目录（跨仓库聚合）。brand 接受 code 或 name。"""
    rows = _run(
        """
        SELECT p.part_no,
               MAX(p.name) AS name,
               MAX(p.category) AS category,
               MAX(p.price) AS price,
               MAX(p.lead_time_days) AS lead_time_days,
               MAX(p.compatible_brands) AS compatible_brands,
               MAX(b.code) AS brand_code,
               MAX(b.name) AS brand_name,
               SUM(p.quantity) AS total_qty,
               COUNT(DISTINCT p.warehouse) AS warehouse_count
        FROM part_inventory p
        LEFT JOIN brand b ON b.id = p.brand_id
        WHERE (:kw IS NULL OR p.part_no ILIKE '%'||:kw||'%'
               OR p.name ILIKE '%'||:kw||'%'
               OR p.category ILIKE '%'||:kw||'%')
          AND (:brand IS NULL OR b.code = :brand OR b.name = :brand)
          AND (:category IS NULL OR p.category = :category)
        GROUP BY p.part_no
        ORDER BY p.part_no
        LIMIT :limit
        """,
        kw=keyword,
        brand=brand,
        category=category,
        limit=limit,
    )
    return {
        "ok": True,
        "query": {"keyword": keyword, "brand": brand, "category": category},
        "count": len(rows),
        "items": [
            {
                "part_no": r["part_no"],
                "name": r["name"],
                "category": r["category"],
                "brand": r["brand_code"] or r["brand_name"],
                "price": _num(r["price"]),
                "lead_time_days": r["lead_time_days"],
                "compatible_brands": r["compatible_brands"] or [],
                "total_qty": int(r["total_qty"] or 0),
                "warehouse_count": int(r["warehouse_count"] or 0),
            }
            for r in rows
        ],
    }


def real_get_part_detail(part_no: str) -> dict[str, Any]:
    """备件详情：目录属性 + 各仓库库存快照（目录与库存两个维度一并呈现，省一次调用）。"""
    rows = _run(
        """
        SELECT p.part_no, p.name, p.category, p.price, p.lead_time_days,
               p.compatible_brands, p.warehouse, p.location, p.quantity, p.safety_stock,
               b.code AS brand_code, b.name AS brand_name
        FROM part_inventory p
        LEFT JOIN brand b ON b.id = p.brand_id
        WHERE p.part_no = :part_no
        ORDER BY p.warehouse
        """,
        part_no=part_no,
    )
    if not rows:
        return {"found": False, "part_no": part_no, "hint": "未在备件目录中找到该图号"}
    first = rows[0]
    return {
        "found": True,
        "part_no": first["part_no"],
        "name": first["name"],
        "category": first["category"],
        "brand": first["brand_code"] or first["brand_name"],
        "price": _num(first["price"]),
        "lead_time_days": first["lead_time_days"],
        "compatible_brands": first["compatible_brands"] or [],
        "total_quantity": int(sum(r["quantity"] or 0 for r in rows)),
        "warehouses": [
            {
                "warehouse": r["warehouse"],
                "location": r["location"],
                "quantity": r["quantity"],
                "safety_stock": r["safety_stock"],
            }
            for r in rows
        ],
    }


def real_get_part_compatibility(part_no: str) -> dict[str, Any]:
    """备件兼容品牌（跨品牌可互换性）。"""
    rows = _run(
        """
        SELECT p.part_no, p.name, p.compatible_brands, b.code AS brand_code
        FROM part_inventory p
        LEFT JOIN brand b ON b.id = p.brand_id
        WHERE p.part_no = :part_no
        """,
        part_no=part_no,
    )
    if not rows:
        return {"found": False, "part_no": part_no, "hint": "未在备件目录中找到该图号"}
    first = rows[0]
    return {
        "found": True,
        "part_no": part_no,
        "name": first["name"],
        "own_brand": first["brand_code"],
        "compatible_brands": first["compatible_brands"] or [],
    }


def real_find_alternative(
    part_no: str, brand: str | None = None, limit: int = 10
) -> dict[str, Any]:
    """替代件：同分类 + 兼容品牌有交集（或显式限定品牌）的备件，排除自身。

    说明：plan.md 原设计为"图嵌入匹配"，但备件主数据权威在 PG、图内仅有报警 mock 备件，
    故用**分类 + 品牌域交集**做近似替代匹配（足够覆盖"这备件缺货，用什么顶"的问答）。
    """
    tgt = _run(
        """
        SELECT p.part_no, p.name, p.category, p.compatible_brands, b.code AS brand_code
        FROM part_inventory p
        LEFT JOIN brand b ON b.id = p.brand_id
        WHERE p.part_no = :part_no
        """,
        part_no=part_no,
    )
    if not tgt:
        return {"found": False, "part_no": part_no, "hint": "未在备件目录中找到该图号"}
    tt = tgt[0]
    category = tt["category"]
    target_brands = set(tt["compatible_brands"] or [])
    if tt["brand_code"]:
        target_brands.add(tt["brand_code"])

    rows = _run(
        """
        SELECT p.part_no, MAX(p.name) AS name, MAX(p.category) AS category,
               MAX(p.price) AS price, MAX(p.compatible_brands) AS compatible_brands,
               MAX(b.code) AS brand_code, SUM(p.quantity) AS total_qty
        FROM part_inventory p
        LEFT JOIN brand b ON b.id = p.brand_id
        WHERE p.part_no <> :part_no
          AND (:category IS NULL OR p.category = :category)
          AND (:brand IS NULL OR b.code = :brand OR b.name = :brand)
        GROUP BY p.part_no
        ORDER BY p.part_no
        LIMIT :limit
        """,
        part_no=part_no,
        category=category,
        brand=brand,
        limit=limit,
    )
    items: list[dict[str, Any]] = []
    for r in rows:
        other_brands = set(r["compatible_brands"] or [])
        if r["brand_code"]:
            other_brands.add(r["brand_code"])
        overlap = sorted(other_brands & target_brands)
        if not overlap:
            continue
        items.append(
            {
                "part_no": r["part_no"],
                "name": r["name"],
                "category": r["category"],
                "brand": r["brand_code"],
                "price": _num(r["price"]),
                "compatible_brands": r["compatible_brands"] or [],
                "total_qty": int(r["total_qty"] or 0),
                "overlap_brands": overlap,
            }
        )
    return {
        "found": True,
        "part_no": part_no,
        "method": "same_category_brand_overlap",
        "count": len(items),
        "items": items,
    }
