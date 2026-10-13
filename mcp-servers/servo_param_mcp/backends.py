"""servo_param_mcp 真实后端：PG 伺服参数（real-only，SQLAlchemy 直连）。

职责（对齐 plan.md §6.3）：query_params / compare_params / get_param_history /
check_param_in_range。update_param 属 phase-2 写操作，且"实例当前参数值"无落点表
（servo_param 存型号基线，变更走 history 快照），故本阶段不实现写参数。

型号解析：接受型号 code 或名称，精确优先、模糊兜底；品牌过滤可消歧。
数值统一转 float，避免 Decimal 序列化问题。
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


def _resolve_models(
    model_query: str, brand: str | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """返回 (exact_matches, fuzzy_matches)。brand 过滤后按 code 排序。"""
    all_models = _run(
        """
        SELECT rm.id, rm.code AS model_code, rm.name AS model_name, b.code AS brand_code
        FROM robot_model rm
        JOIN brand b ON b.id = rm.brand_id
        WHERE (:brand IS NULL OR b.code = :brand OR b.name = :brand)
        ORDER BY rm.code
        """,
        brand=brand,
    )
    mq = (model_query or "").strip().lower()
    exact = [
        m for m in all_models
        if (m["model_code"] or "").lower() == mq or (m["model_name"] or "").lower() == mq
    ]
    fuzzy = [
        m for m in all_models
        if mq in (m["model_code"] or "").lower() or mq in (m["model_name"] or "").lower()
    ]
    return exact, [m for m in fuzzy if m not in exact]


def _params_for_model(model_id: int) -> list[dict[str, Any]]:
    rows = _run(
        """
        SELECT param_code, param_name, default_value, min_value, max_value, unit, description
        FROM servo_param
        WHERE robot_model_id = :mid
        ORDER BY param_code
        """,
        mid=model_id,
    )
    return [
        {
            "param_code": r["param_code"],
            "param_name": r["param_name"],
            "default_value": _num(r["default_value"]),
            "min_value": _num(r["min_value"]),
            "max_value": _num(r["max_value"]),
            "unit": r["unit"],
            "description": r["description"],
        }
        for r in rows
    ]


def _available_models() -> list[dict[str, Any]]:
    return _run(
        """
        SELECT rm.code AS model_code, rm.name AS model_name, b.code AS brand_code
        FROM robot_model rm
        JOIN brand b ON b.id = rm.brand_id
        ORDER BY rm.code
        """
    )


def real_query_params(
    robot_model: str, brand: str | None = None, keyword: str | None = None
) -> dict[str, Any]:
    """按机器人型号查伺服参数（型号 code/名称精确或模糊，品牌可消歧）。"""
    exact, fuzzy = _resolve_models(robot_model, brand)
    matched = exact or fuzzy
    if not matched:
        return {
            "found": False,
            "robot_model": robot_model,
            "hint": "未找到该机器人型号",
            "available_models": _available_models(),
        }
    target = matched[0]
    kw = f"%{keyword}%" if keyword else "%"
    params = _params_for_model(target["id"])
    if kw != "%":
        params = [
            p for p in params
            if keyword.lower() in p["param_code"].lower()
            or keyword.lower() in (p["param_name"] or "").lower()
        ]
    return {
        "found": True,
        "robot_model": robot_model,
        "model": {
            "code": target["model_code"],
            "name": target["model_name"],
            "brand": target["brand_code"],
        },
        "matched_count": len(matched),
        "count": len(params),
        "params": params,
    }


def real_compare_params(model_a: str, model_b: str) -> dict[str, Any]:
    """对比两型号同参数码的默认值差异。"""
    ea, fa = _resolve_models(model_a)
    eb, fb = _resolve_models(model_b)
    a = (ea or fa)[0] if (ea or fa) else None
    b = (eb or fb)[0] if (eb or fb) else None
    if a is None or b is None:
        return {
            "found": False,
            "model_a": model_a,
            "model_b": model_b,
            "hint": "一个或多个型号未找到",
            "available_models": _available_models(),
        }
    pa = _params_for_model(a["id"])
    pb = _params_for_model(b["id"])
    pb_map = {p["param_code"]: p for p in pb}
    common, only_a, only_b = [], [], []
    for p in pa:
        q = pb_map.get(p["param_code"])
        if q is None:
            only_a.append(p["param_code"])
            continue
        va, vb = p["default_value"], q["default_value"]
        diff = (vb - va) if (va is not None and vb is not None) else None
        common.append(
            {
                "param_code": p["param_code"],
                "param_name": p["param_name"],
                "unit": p["unit"],
                f"{a['model_code']}_default": va,
                f"{b['model_code']}_default": vb,
                "diff": diff,
            }
        )
    only_b = [p["param_code"] for p in pb if p["param_code"] not in {x["param_code"] for x in pa}]
    return {
        "found": True,
        "models": {
            "a": {"code": a["model_code"], "name": a["model_name"], "brand": a["brand_code"]},
            "b": {"code": b["model_code"], "name": b["model_name"], "brand": b["brand_code"]},
        },
        "common_count": len(common),
        "common_params": common,
        "only_in_a": only_a,
        "only_in_b": only_b,
    }


def real_get_param_history(
    robot_instance: str | None = None,
    robot_model: str | None = None,
    param_code: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """参数变更历史：谁在何时把哪台设备的哪个参数改成什么（可追溯）。"""
    rows = _run(
        """
        SELECT h.param_code, h.old_value, h.new_value, h.reason, h.changed_at,
               ri.asset_no, rm.code AS model_code, u.username AS changed_by
        FROM servo_param_history h
        LEFT JOIN robot_instance ri ON ri.id = h.robot_instance_id
        LEFT JOIN robot_model rm ON rm.id = COALESCE(h.robot_model_id, ri.robot_model_id)
        LEFT JOIN sys_user u ON u.id = h.changed_by
        WHERE (:asset IS NULL OR ri.asset_no = :asset)
          AND (:model IS NULL OR rm.code ILIKE :model OR rm.name ILIKE :model)
          AND (:code IS NULL OR h.param_code = :code)
        ORDER BY h.changed_at DESC
        LIMIT :limit
        """,
        asset=robot_instance,
        model=f"%{robot_model}%" if robot_model else None,
        code=param_code,
        limit=limit,
    )
    return {
        "ok": True,
        "count": len(rows),
        "items": [
            {
                "asset_no": r["asset_no"],
                "model_code": r["model_code"],
                "param_code": r["param_code"],
                "old_value": _num(r["old_value"]),
                "new_value": _num(r["new_value"]),
                "changed_by": r["changed_by"],
                "reason": r["reason"],
                "changed_at": r["changed_at"].isoformat() if r["changed_at"] else None,
            }
            for r in rows
        ],
    }


def real_check_param_in_range(
    robot_model: str, param_code: str, value: float
) -> dict[str, Any]:
    """校验参数值是否在型号基线 [min, max] 内（无上下限时仅比对默认值提示）。"""
    exact, fuzzy = _resolve_models(robot_model)
    matched = exact or fuzzy
    if not matched:
        return {
            "found": False,
            "robot_model": robot_model,
            "hint": "未找到该机器人型号",
            "available_models": _available_models(),
        }
    target = matched[0]
    params = _params_for_model(target["id"])
    p = next((x for x in params if x["param_code"].lower() == param_code.lower()), None)
    if p is None:
        return {
            "found": False,
            "robot_model": robot_model,
            "param_code": param_code,
            "hint": f"型号 {robot_model} 无参数 {param_code}",
            "available_params": [x["param_code"] for x in params],
        }
    v = float(value)
    lo, hi = p["min_value"], p["max_value"]
    if lo is not None and hi is not None:
        in_range = lo <= v <= hi
        verdict = "ok" if in_range else ("below_min" if v < lo else "above_max")
    else:
        in_range, verdict = True, "no_bounds"
    return {
        "found": True,
        "robot_model": robot_model,
        "model": {
            "code": target["model_code"],
            "name": target["model_name"],
            "brand": target["brand_code"],
        },
        "param": {"param_code": p["param_code"], "param_name": p["param_name"], "unit": p["unit"]},
        "value": v,
        "in_range": in_range,
        "verdict": verdict,
        "bounds": {"min": lo, "max": hi, "default": p["default_value"]},
    }
