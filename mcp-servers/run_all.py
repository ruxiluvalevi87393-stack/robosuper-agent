"""一键启动 5 个 MCP 服务端（每服务独立进程，streamable HTTP，real-only）。

用法（在 mcp-servers/ 目录下）：
    python run_all.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from common.config import settings

SERVERS = [
    "alarm_graph_mcp",
    "servo_param_mcp",
    "epc_parts_mcp",
    "inventory_mcp",
    "work_order_mcp",
]


def main() -> None:
    root = Path(__file__).resolve().parent
    procs: list[subprocess.Popen] = []
    try:
        for name in SERVERS:
            port = settings.server_ports[name]
            print(f"[run_all] 启动 {name} @ {settings.MCP_HOST}:{port}")
            procs.append(
                subprocess.Popen(
                    [sys.executable, "-m", f"{name}.server"],
                    cwd=root,
                )
            )
        print(f"[run_all] 全部 {len(procs)} 个服务已启动，Ctrl+C 退出")
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\n[run_all] 停止全部服务")
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
