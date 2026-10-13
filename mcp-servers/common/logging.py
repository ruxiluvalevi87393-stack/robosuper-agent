"""统一日志（loguru，对齐后端）：格式含服务名，便于区分多进程输出。"""
import sys

from loguru import logger


def setup_logging(service_name: str) -> None:
    """配置全局 logger；幂等，服务进程启动时调用一次。"""
    logger.remove()
    logger.configure(extra={"service": service_name})
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[service]}</cyan> | {message}"
        ),
        level="INFO",
        enqueue=True,
    )
