"""CLI：读 canonical 品牌/型号主数据 UPSERT 进 PG（幂等，可重复跑）。

用法（backend/ 目录下）：
    python -m scripts.load.load_postgres

对齐设计稿「业务主数据权威在 PG」：brand/controller/robot_model 以自然键
（brand.code / brand_id+controller.code / brand_id+model.code）UPSERT。
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database import SessionLocal
from app.models.brand import Brand
from app.models.controller import Controller
from app.models.robot_model import RobotModel

CANONICAL = Path(__file__).resolve().parent.parent.parent / "data" / "canonical"


def _load_json(name: str) -> list:
    return json.loads((CANONICAL / name).read_text(encoding="utf-8"))


def upsert_brands(db) -> int:
    count = 0
    for b in _load_json("brands.json"):
        stmt = pg_insert(Brand).values(
            code=b["code"], name=b["name"],
            country=b.get("country"), description=b.get("description"),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Brand.code],
            set_={"name": stmt.excluded.name, "country": stmt.excluded.country,
                  "description": stmt.excluded.description},
        )
        db.execute(stmt)
        count += 1
    return count


def upsert_controllers_and_models(db) -> tuple[int, int]:
    rows = _load_json("robot_models.json")
    brand_ids = {code: i for code, i in db.execute(select(Brand.code, Brand.id)).all()}
    controller_ids: dict[tuple[str, str], int] = {}
    controller_count = model_count = 0

    for m in rows:
        brand_id = brand_ids.get(m["brand"])
        if brand_id is None:
            print(f"  !! 跳过型号 {m['code']}: 品牌 {m['brand']} 未在 brands.json")
            continue

        ctrl = m.get("controller") or {}
        ctrl_code = ctrl.get("code")
        ctrl_id = None
        if ctrl_code:
            key = (m["brand"], ctrl_code)
            if key not in controller_ids:
                stmt = pg_insert(Controller).values(
                    brand_id=brand_id, code=ctrl_code,
                    name=ctrl.get("name", ctrl_code),
                    series=ctrl.get("series"), description=ctrl.get("description"),
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[Controller.brand_id, Controller.code],
                    set_={"name": stmt.excluded.name, "series": stmt.excluded.series,
                          "description": stmt.excluded.description},
                )
                controller_ids[key] = db.execute(
                    stmt.returning(Controller.id)
                ).scalar_one()
                controller_count += 1
            ctrl_id = controller_ids[key]

        stmt = pg_insert(RobotModel).values(
            brand_id=brand_id, controller_id=ctrl_id,
            code=m["code"], name=m["name"],
            payload_kg=m.get("payload_kg"), reach_mm=m.get("reach_mm"),
            axes=m.get("axes"), description=m.get("description"),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[RobotModel.brand_id, RobotModel.code],
            set_={"name": stmt.excluded.name, "controller_id": stmt.excluded.controller_id,
                  "payload_kg": stmt.excluded.payload_kg, "reach_mm": stmt.excluded.reach_mm,
                  "axes": stmt.excluded.axes, "description": stmt.excluded.description},
        )
        db.execute(stmt)
        model_count += 1
    return controller_count, model_count


def main() -> None:
    db = SessionLocal()
    try:
        nb = upsert_brands(db)
        nc, nm = upsert_controllers_and_models(db)
        db.commit()
        print(f"UPSERT 完成: brands={nb} controllers={nc} robot_models={nm}（幂等，重跑不重复）")
        brands = db.execute(select(Brand.code, Brand.name)).all()
        models = db.execute(
            select(Brand.code, RobotModel.code).join(Brand, Brand.id == RobotModel.brand_id)
        ).all()
        print("PG 现有品牌:", [f"{c}:{n}" for c, n in brands])
        print("PG 现有型号:", [f"{c} {m}" for c, m in models])
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
