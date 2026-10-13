"""实测：agent 回答是否真逐 token 流式（answer_delta 事件逐字出现）。

验证点：
1. 诊断查询（confirm→resume 路径）下 answer_delta 数量 > 若干，拼接后 == answer 事件 text。
2. answer 事件仍携带 graphs / manual_images / sops（流式只替换文本下发方式）。
3. 未流式路径（direct_answer，如「机器人怎么保养」）整段 text 出现、无重复。
"""
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


def summarize(session_id: str, label: str, ev: list[dict]) -> None:
    types = [e["type"] for e in ev]
    deltas = [e["text"] for e in ev if e["type"] == "answer_delta"]
    ans = next((e for e in ev if e["type"] == "answer"), None)
    err = next((e.get("message") for e in ev if e["type"] == "error"), None)

    streamed = "".join(deltas)
    print(f"  [{label}] 事件序列: {', '.join(t for t in types if t in ('tool','answer_delta','answer','confirm','done','error'))}")
    print(f"  answer_delta 条数: {len(deltas)}  拼接长度: {len(streamed)}")
    if ans:
        text = ans.get("text") or ""
        print(f"  answer.text 长度: {len(text)}  与流式拼接一致: {streamed == text}")
        print(f"  answer 结构化: graphs={len(ans.get('graphs') or [])} "
              f"manual_images={len(ans.get('manual_images') or [])} "
              f"manual_chunks={len(ans.get('manual_chunks') or [])} "
              f"sops={len(ans.get('sops') or [])} "
              f"work_order={bool(ans.get('work_order'))}")
        if streamed and streamed != text:
            print("    !!! 流式文本与 answer.text 不一致，请检查")
        if not streamed:
            print(f"  （未流式，整段 text 前 80 字）: {text[:80]!r}")
    if err:
        print(f"  ✗ error: {err}")


def main() -> int:
    token = login()
    print(f"登录成功\n")
    ts = int(time.time())

    # 诊断查询（走 confirm → resume，最终由 narrate 流式叙述）
    q = "FANUC 伺服轴抖动是什么原因"
    sid = f"stream_{ts}_1"
    print(f"========== [1] 诊断: {q}")
    ev1 = stream_chat(sid, q, token)
    types1 = [e["type"] for e in ev1]
    confirm = next((e for e in ev1 if e["type"] == "confirm"), None)
    print(f"  第一轮: answer={'Y' if 'answer' in types1 else 'N'} confirm={'Y' if confirm else 'N'} done={'Y' if 'done' in types1 else 'N'}")
    if confirm:
        decision = confirm.get("options") or ["确认执行并建单"]
        print(f"  → resume: {decision[0]!r}")
        ev2 = stream_chat(sid, "", token, resume_input=decision[0])
        summarize(sid, "resume", ev2)
    else:
        summarize(sid, "第一轮", ev1)

    # 直接回答（others 意图，未流式整段 text）
    q2 = "机器人日常维护多久做一次润滑"
    sid2 = f"stream_{ts}_2"
    print(f"\n========== [2] direct_answer: {q2}")
    ev3 = stream_chat(sid2, q2, token)
    summarize(sid2, "direct", ev3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
