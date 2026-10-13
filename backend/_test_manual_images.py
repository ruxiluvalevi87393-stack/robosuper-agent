"""实测：哪些 agent 查询能让 answer 事件的 manual_images 非空（含 resume 路径）。"""
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
    events: list[dict] = []
    body = {"session_id": session_id, "query": query, "resume_input": resume_input}
    with requests.post(
        f"{BASE}/api/v1/agent/chat",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        stream=True,
        timeout=300,
    ) as resp:
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


QUERIES = [
    "FANUC SRVO-050 碰撞报警怎么处理",
    "FANUC SRVO-001 过载报警怎么处理",
    "FANUC 伺服轴抖动是什么原因",
    "FANUC 程序中断如何排查",
    "FANUC IO 信号异常怎么处理",
]


def main() -> int:
    token = login()
    print(f"登录成功，token 前缀 {token[:20]}…\n")

    ts = int(time.time())
    for i, q in enumerate(QUERIES, 1):
        print(f"========== [{i}/{len(QUERIES)}] {q}")
        try:
            ev = stream_chat(f"imgs_{ts}_{i}", q, token)
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ 请求失败: {exc}\n")
            continue

        confirm = next((e for e in ev if e["type"] == "confirm"), None)
        ans = next((e for e in ev if e["type"] == "answer"), None)
        err = next((e.get("message") for e in ev if e["type"] == "error"), None)
        tools = [e["node"] for e in ev if e["type"] == "tool" and e["status"] == "start"]
        has_rm = any("retrieve_manual" in n for n in tools)

        imgs = (ans or {}).get("manual_images") or []
        graphs = len((ans or {}).get("graphs") or [])
        print(f"  [第一轮] answer={'Y' if ans else 'N'} confirm={'Y' if confirm else 'N'} "
              f"retrieve_manual={has_rm} graphs={graphs} manual_images={len(imgs)} error={err}")

        if confirm is not None:
            decision = confirm.get("options") or ["确认执行并建单"]
            ev2 = stream_chat(f"imgs_{ts}_{i}", "", token, resume_input=decision[0])
            ans2 = next((e for e in ev2 if e["type"] == "answer"), None)
            imgs2 = (ans2 or {}).get("manual_images") or []
            graphs2 = len((ans2 or {}).get("graphs") or [])
            err2 = next((e.get("message") for e in ev2 if e["type"] == "error"), None)
            wo = (ans2 or {}).get("work_order") or {}
            print(f"  [resume: {decision[0]!r}] answer={'Y' if ans2 else 'N'} "
                  f"graphs={graphs2} manual_images={len(imgs2)} work_order={wo.get('work_order_no')} error={err2}")
            for img in imgs2[:6]:
                print(f"    - page={img.get('page')} content={(img.get('content') or '')[:40]!r} url={str(img.get('asset_url'))[:70]}")
            if not imgs2 and ans2:
                print(f"  （无图）text 前 100 字: {(ans2.get('text') or '')[:100]!r}")
        else:
            for img in imgs[:6]:
                print(f"    - page={img.get('page')} content={(img.get('content') or '')[:40]!r} url={str(img.get('asset_url'))[:70]}")
            if ans and not imgs:
                print(f"  （无图）text 前 100 字: {(ans.get('text') or '')[:100]!r}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
