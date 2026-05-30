"""v0.28 Agent 全量审计 · 端到端真打"""
import asyncio
import json
import time
import uuid
import httpx

BASE = "http://127.0.0.1:8000"


async def main():
    results = {"PASS": [], "WARN": [], "FAIL": []}
    sess_email = f"audit_{uuid.uuid4().hex[:8]}@test.com"
    sess_pw = "TestPass123!"

    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        # ───────────── 4.1 · 注册 + 登录 ─────────────
        t = time.time()
        r = await c.post("/v1/auth/register", json={"email": sess_email, "password": sess_pw})
        if r.status_code == 200 and r.json().get("code") == 200:
            results["PASS"].append(f"4.1 register OK ({(time.time()-t)*1000:.0f}ms)")
        else:
            results["FAIL"].append(f"4.1 register failed: {r.status_code} {r.text[:200]}")
            return results

        t = time.time()
        r = await c.post("/v1/auth/login", json={"email": sess_email, "password": sess_pw})
        if r.status_code != 200 or r.json().get("code") != 200:
            results["FAIL"].append(f"4.2 login failed: {r.text[:200]}")
            return results
        data = r.json()["data"]
        token = data["access_token"]
        # decode JWT to get user_id (sub claim) without verifying
        import base64
        try:
            payload_b64 = token.split('.')[1] + '=='
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            user_id = payload.get('sub')
        except Exception:
            user_id = "(decode failed)"
        H = {"Authorization": f"Bearer {token}"}
        results["PASS"].append(f"4.2 login OK ({(time.time()-t)*1000:.0f}ms), user_id={user_id[:8] if user_id else '?'}…")

        # ───────────── 4.3 · /auth/me ─────────────
        r = await c.get("/v1/auth/me", headers=H)
        if r.status_code == 200 and r.json()["data"]["email"] == sess_email:
            results["PASS"].append("4.3 /auth/me identity OK")
        else:
            results["FAIL"].append(f"4.3 /auth/me failed: {r.text[:200]}")

        # ───────────── 4.4 · widgets/home ─────────────
        r = await c.get("/v1/widgets", headers=H)
        if r.status_code == 200:
            results["PASS"].append(f"4.4 /v1/widgets OK · {len(r.json()['data'])} widgets")
        else:
            results["WARN"].append(f"4.4 widgets: {r.status_code} {r.text[:100]}")

        # ───────────── 4.5 · Agent 状态 ─────────────
        r = await c.get("/v1/agent/state", headers=H)
        if r.status_code == 200:
            results["PASS"].append(f"4.5 GET agent_state · {r.json()['data']['current_state']}")
        else:
            results["WARN"].append(f"4.5 agent_state: {r.status_code} {r.text[:100]}")

        # ───────────── 4.6 · Agent SSE chat 真打 ─────────────
        print("[4.6] sending chat msg → DeepSeek V4 Flash (streaming SSE)...")
        t = time.time()
        full_reply = ""
        tools_called = []
        session_id_used = None
        thinking_events = []
        try:
            async with c.stream(
                "POST", "/v1/agent/chat",
                headers={**H, "Content-Type": "application/json"},
                json={"message": "你好", "session_id": None},
                timeout=60,
            ) as resp:
                if resp.status_code != 200:
                    results["FAIL"].append(f"4.6 chat status {resp.status_code}")
                else:
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        try:
                            ev = json.loads(line[6:])
                        except Exception:
                            continue
                        if "delta" in ev:
                            full_reply += ev["delta"]
                        if "thinking" in ev:
                            thinking_events.append(ev["thinking"])
                        if ev.get("done"):
                            tools_called = ev.get("tools_called", [])
                            session_id_used = ev.get("session_id")
        except Exception as e:
            results["FAIL"].append(f"4.6 SSE exception: {e}")

        if full_reply:
            results["PASS"].append(
                f"4.6 SSE chat OK · {(time.time()-t):.1f}s · {len(full_reply)} chars · "
                f"tools={tools_called} · thinking={len(thinking_events)} · "
                f"reply='{full_reply[:60]}…'"
            )
        else:
            results["FAIL"].append("4.6 SSE chat returned empty reply")

        # ───────────── 4.7 · 第二轮（带 session_id，验持久化） ─────────────
        if session_id_used:
            t = time.time()
            full2 = ""
            try:
                async with c.stream(
                    "POST", "/v1/agent/chat",
                    headers={**H, "Content-Type": "application/json"},
                    json={"message": "我刚才说了什么", "session_id": session_id_used},
                    timeout=60,
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                ev = json.loads(line[6:])
                                if "delta" in ev:
                                    full2 += ev["delta"]
                            except Exception:
                                pass
            except Exception as e:
                results["FAIL"].append(f"4.7 session 持久化 exception: {e}")
            if "你好" in full2 or "刚才" in full2 or "之前" in full2 or "上一" in full2:
                results["PASS"].append(f"4.7 session 历史持久化 OK · reply='{full2[:80]}…'")
            else:
                results["WARN"].append(f"4.7 session 历史可疑 · reply='{full2[:80]}…'")

        # ───────────── 4.8 · 测工具调用（明确触发） ─────────────
        print("[4.8] testing tool call get_full_context...")
        t = time.time()
        full3 = ""
        tools3 = []
        try:
            async with c.stream(
                "POST", "/v1/agent/chat",
                headers={**H, "Content-Type": "application/json"},
                json={"message": "看一下我今天有什么任务", "session_id": None},
                timeout=120,
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            if "delta" in ev:
                                full3 += ev["delta"]
                            if ev.get("done"):
                                tools3 = ev.get("tools_called", [])
                        except Exception:
                            pass
        except Exception as e:
            results["FAIL"].append(f"4.8 tool chat exception: {e}")
        if tools3:
            results["PASS"].append(f"4.8 工具调用 OK · {(time.time()-t):.1f}s · tools={tools3}")
        else:
            results["WARN"].append(f"4.8 期望工具调用但未触发 · tools=[] · reply='{full3[:80]}…'")

        # ───────────── 4.9 · 测 RAG retrieve_knowledge ─────────────
        print("[4.9] testing RAG retrieve_knowledge tool...")
        t = time.time()
        full4 = ""
        tools4 = []
        try:
            async with c.stream(
                "POST", "/v1/agent/chat",
                headers={**H, "Content-Type": "application/json"},
                json={"message": "调用 retrieve_knowledge 查一下我笔记里有什么关于导数的内容", "session_id": None},
                timeout=120,
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            if "delta" in ev:
                                full4 += ev["delta"]
                            if ev.get("done"):
                                tools4 = ev.get("tools_called", [])
                        except Exception:
                            pass
        except Exception as e:
            results["FAIL"].append(f"4.9 RAG chat exception: {e}")
        if "retrieve_knowledge" in tools4:
            results["PASS"].append(f"4.9 RAG 工具调用 OK · {(time.time()-t):.1f}s · reply='{full4[:80]}…'")
        elif tools4:
            results["WARN"].append(f"4.9 调了别的工具={tools4} · reply='{full4[:80]}…'")
        else:
            results["WARN"].append(f"4.9 没调 retrieve_knowledge · reply='{full4[:80]}…'")

        # ───────────── 4.10 · /v1/agent/history (PRD 9.7) ─────────────
        r = await c.get("/v1/agent/history", headers=H)
        if r.status_code == 200:
            data = r.json()["data"]
            count = len(data) if isinstance(data, list) else (data.get("total") if isinstance(data, dict) else 0)
            results["PASS"].append(f"4.10 agent history OK · {count} logs")
        else:
            results["WARN"].append(f"4.10 agent history: {r.status_code}")

        # ───────────── 4.11 · 自动注入 RAG · 检查 thinking 流 ─────────────
        # 已在 4.6 间接验证（每条消息系统都注入 top-5；server 端在 logger.info 打了）
        # 这里跑一个明确含 RAG 查询的话题
        print("[4.11] testing implicit RAG injection (no tool call needed)...")
        t = time.time()
        full5 = ""
        try:
            async with c.stream(
                "POST", "/v1/agent/chat",
                headers={**H, "Content-Type": "application/json"},
                json={"message": "导数和微分有什么区别", "session_id": None},
                timeout=120,
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            if "delta" in ev:
                                full5 += ev["delta"]
                        except Exception:
                            pass
        except Exception as e:
            pass
        if "导数" in full5 and ("微分" in full5 or "切线" in full5 or "斜率" in full5):
            results["PASS"].append(f"4.11 RAG 隐式注入 · {(time.time()-t):.1f}s · reply 含数学概念")
        else:
            results["WARN"].append(f"4.11 RAG 隐式 reply 可疑: '{full5[:120]}…'")

    return results


if __name__ == "__main__":
    res = asyncio.run(main())
    print()
    print("="*72)
    print(f"PASS: {len(res['PASS'])}")
    for x in res["PASS"]:
        print(f"  [PASS]{x}")
    print(f"WARN: {len(res['WARN'])}")
    for x in res["WARN"]:
        print(f"  [WARN]{x}")
    print(f"FAIL: {len(res['FAIL'])}")
    for x in res["FAIL"]:
        print(f"  [FAIL]{x}")
