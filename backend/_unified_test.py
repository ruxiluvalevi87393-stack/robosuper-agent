"""统一联调测试：登录 → SSE 流式排查（工具卡片/并行分支）→ interrupt 人工确认 → resume 续跑 → 建工单。"""
import json
import sys
import time

import requests

if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("gbk"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000"


def login() -> str:
    r = requests.post(
        f"{BASE}/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def stream_chat(session_id: str, query: str, token: str, resume_input: str | None = None) -> list[dict]:
    """POST /api/v1/agent/chat 流式读取 SSE 事件，返回事件列表。"""
    events: list[dict] = []
    body = {"session_id": session_id, "query": query, "resume_input": resume_input}
    with requests.post(
        f"{BASE}/api/v1/agent/chat",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        stream=True,
        timeout=300,
    ) as resp:
        print(f"  HTTP {resp.status_code}")
        resp.raise_for_status()
        buf = b""
        for chunk in resp.iter_content(chunk_size=256):
            buf += chunk
            while b"\n\n" in buf:
                block, buf = buf.split(b"\n\n", 1)
                for line in block.split(b"\n"):
                    if not line.startswith(b"data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload or payload in (b"[DONE]", b"data:[DONE]"):
                        continue
                    try:
                        events.append(json.loads(payload))
                    except json.JSONDecodeError:
                        pass
    return events


def summarize(events: list[dict], label: str) -> None:
    tools = [e for e in events if e["type"] == "tool"]
    branches = sorted({e.get("branch") for e in tools if e.get("branch")})
    parallel_nodes = sorted(
        {f"{e['node']}:{e['branch']}" for e in tools if e.get("branch") and e["status"] == "start"}
    )
    print(f"\n=== {label} ===")
    print(f"  事件总数: {len(events)} | 工具 start/end: {len(tools)}")
    print(f"  并行分支: {branches}")
    print(f"  带 branch 节点(start): {parallel_nodes}")
    for e in events:
        t = e["type"]
        if t == "tool":
            mark = "▶" if e["status"] == "start" else "■"
            br = f" [{e.get('branch')}]" if e.get("branch") else ""
            print(f"    {mark} tool {e['node']} ({e['name']}){br}")
        elif t == "confirm":
            print(f"    ✋ confirm node={e.get('node')} prompt={e.get('prompt')} options={e.get('options')}")
        elif t == "answer":
            print(
                f"    ✨ answer text={e.get('text','')[:60]!r} "
                f"sop={'Y' if e.get('sop') or e.get('sops') else 'N'} "
                f"graphs={len(e.get('graphs') or [])} "
                f"work_order={e.get('work_order')}"
            )
        elif t == "error":
            print(f"    ✗ error {e.get('message')}")
        elif t == "done":
            print(f"    ✓ done")


def main() -> int:
    token = login()
    print(f"登录成功，token 前缀 {token[:20]}…")

    session = f"unified_{int(time.time())}"

    # 1) 正常流程（碰撞报警 → 并行子代理 → 检查参数/备件 → 人工确认）
    q = "FANUC SRVO-050 碰撞报警怎么处理"
    print(f"\n>>> 发送: {q}")
    events = stream_chat(session, q, token)
    summarize(events, "第一轮（到人工确认）")

    confirm = next((e for e in events if e["type"] == "confirm"), None)
    if confirm is None:
        print("\n✗ 未收到 confirm 事件，测试终止")
        return 1
    answer_before = next((e for e in events if e["type"] == "answer"), None)

    # 2) resume 续跑：确认执行并建单
    decision = "确认执行并建单"
    print(f"\n>>> resume: {decision}")
    events2 = stream_chat(session, "", token, resume_input=decision)
    summarize(events2, "第二轮（resume 续跑 → 建工单）")

    answer = next((e for e in events2 if e["type"] == "answer"), None)
    if answer is None and answer_before is not None:
        # 若建单信息并入第一轮 answer，需要检查 work_order
        answer = None

    # 3) 断言
    checks = []
    g = lambda b, m: checks.append((b, m))

    tool_nodes = [e["node"] for e in events if e["type"] == "tool" and e["status"] == "start"]
    branches = sorted({e.get("branch") for e in events if e.get("branch")})
    for needed in ["intent_classifier", "brand_detector", "urgency_evaluator", "dispatcher",
                   "run_subagent", "query_graph", "retrieve_manual", "check_params", "match_part", "generate_sop"]:
        g(needed in tool_nodes, f"节点出现: {needed}")
    g(any("check_params" in n for n in tool_nodes), "check_params 已执行")
    g(any("match_part" in n for n in tool_nodes), "match_part 已执行")

    has_graphs = any((e.get("graphs") for e in [answer_before, answer] if e))
    g(bool(has_graphs), "answer 携带 graphs（GraphPanel 数据源）")

    wo = (answer or {}).get("work_order") or (answer_before or {}).get("work_order")
    g(bool(wo and wo.get("ok")), f"工单已创建: {wo}")
    if wo:
        print(f"\n  工单号: {wo.get('work_order_no')} 优先级: {wo.get('priority')}")

    print()
    failed = 0
    for b, m in checks:
        print(f"  [{'PASS' if b else 'FAIL'}] {m}")
        if not b:
            failed += 1

    # 4) 多意图并行场景：一次提问含两类报警 → 应出现 ≥2 个并行分支
    print("\n>>> 多意图: FANUC SRVO-050 碰撞报警，伺服轴也过载抖动")
    ev = stream_chat(f"{session}_p", "FANUC SRVO-050 碰撞报警，伺服轴也过载抖动", token)
    brs = sorted({e.get("branch") for e in ev if e.get("branch")})
    summarize(ev, "多意图（并行分支）")
    print(f"\n  多意图并行分支: {brs}")
    if len(brs) >= 2:
        print("  [PASS] 并行分支 ≥2（前端将渲染「并行」框）")
    else:
        print(f"  [INFO] 单意图/未识别多意图，分支={brs}（串行展示，符合设计）")
        failed += 1

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
