from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.brands import router as brands_router
from app.api.v1.controllers import router as controllers_router
from app.api.v1.maintenance_logs import router as maintenance_logs_router
from app.api.v1.part_inventory import router as part_inventory_router
from app.api.v1.robot_instances import router as robot_instances_router
from app.api.v1.robot_models import router as robot_models_router
from app.api.v1.servo_param_histories import router as servo_param_histories_router
from app.api.v1.servo_params import router as servo_params_router
from app.api.v1.users import router as users_router
from app.api.v1.work_orders import router as work_orders_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(brands_router)
router.include_router(controllers_router)
router.include_router(robot_models_router)
router.include_router(robot_instances_router)
router.include_router(part_inventory_router)
router.include_router(servo_params_router)
router.include_router(work_orders_router)
router.include_router(maintenance_logs_router)
router.include_router(servo_param_histories_router)
