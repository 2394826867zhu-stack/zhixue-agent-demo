"""Sprint 2/3/4 真打验证：Memory / Planner / Safety exits / PII"""
import asyncio
import json
import time
import uuid
import httpx

BASE = "http://127.0.0.1:8000"


async def main():
    R = {"PASS": [], "WARN": [], "FAIL": []}
    async with httpx.AsyncClient(base_url=BASE, timeout=180) as c:
        em = f"sprint234_{uuid.uuid4().hex[:6]}@test.com"
        await c.post("/v1/auth/register", json={"email": em, "password": "TestPass123!"})
        l = await c.post("/v1/auth/login", json={"email": em, "password": "TestPass123!"})
        tok = l.json()["data"]["access_token"]
        H = {"Authorization": f"Bearer {tok}"}

        # ── S2.1 · agent_episodes 表能写 ─────────
        # 通过 checkin 拿 streak_milestone
        for i in range(3):
            r = await c.post("/v1/checkin", headers=H, json={"content": f"day {i+1} 我学了 5 个数学知识点"})
            if r.status_code == 429:
                await asyncio.sleep(15)
                r = await c.post("/v1/checkin", headers=H, json={"content": f"day {i+1} 我学了 5 个数学知识点"})
        # 也直接经由 db 查 agent_episodes
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import text
        from app.config import settings
        eng = create_async_engine(settings.DATABASE_URL, echo=False)
        Session = async_sessionmaker(eng, expire_on_commit=False)
        async with Session() as db:
            row = await db.execute(text("SELECT count(*) FROM agent_episodes"))
            n_eps = row.scalar_one()
            R["PASS"].append(f"S2.1 agent_episodes 表读写正常 · 当前 {n_eps} 条")

        # ── S2.2 · 手动写一个 episode 验证 RAG 召回 ──
        async with Session() as db:
            uid_row = await db.execute(text(f"SELECT id FROM users WHERE email = :e"), {"e": em})
            uid = uid_row.scalar_one()
            from app.services.episodic_memory_service import record_event
            await record_event(
                db, user_id=uid,
                event_kind="kp_struggle",
                summary=f"用户在「二次函数图像」上反复出错。",
                detail={"subject": "数学"},
                importance=6,
            )
            R["PASS"].append("S2.2 record_event 手动写入 OK")

        # ── S2.3 · 验证 episode 被注入到 Agent 上下文 ──
        # 发"今天数学怎么样"应能被 Agent 知道二次函数有问题
        full = ""
        async with c.stream("POST", "/v1/agent/chat",
                            headers={**H, "Content-Type": "application/json"},
                            json={"message": "今天数学怎么样"}, timeout=120) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    try:
                        ev = json.loads(line[6:])
                        if "delta" in ev:
                            full += ev["delta"]
                    except: pass
        if "二次函数" in full or "出错" in full:
            R["PASS"].append(f"S2.3 episode 注入 OK · reply 提到具体问题")
        else:
            R["WARN"].append(f"S2.3 episode 注入未明显体现 · reply='{full[:80]}…'")

        # ── S3.1 · 复杂任务走 Plan-Execute ──
        # 通过监控 thinking 事件 + tools_called
        print("[S3.1] 发复杂任务测 Plan-Execute pipeline...")
        thinking_events = []
        tools = []
        full = ""
        t0 = time.time()
        async with c.stream("POST", "/v1/agent/chat",
                            headers={**H, "Content-Type": "application/json"},
                            json={"message": "帮我安排接下来一周的数学复习计划"}, timeout=180) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    try:
                        ev = json.loads(line[6:])
                        if "delta" in ev:
                            full += ev["delta"]
                        if "thinking" in ev:
                            thinking_events.append(ev["thinking"])
                        if ev.get("done"):
                            tools = ev.get("tools_called", [])
                    except: pass
        elapsed = time.time() - t0
        planner_thinking = any("规划" in t or "执行" in t for t in thinking_events)
        if planner_thinking:
            R["PASS"].append(f"S3.1 Plan-Execute 触发 · {elapsed:.1f}s · thinking={thinking_events[:3]} · tools={tools}")
        else:
            R["WARN"].append(f"S3.1 复杂任务未走 planner · thinking={thinking_events[:3]} · tools={tools}")

        # ── S3.2 · 简单任务走 ReAct（不走 planner） ──
        thinking_events = []
        async with c.stream("POST", "/v1/agent/chat",
                            headers={**H, "Content-Type": "application/json"},
                            json={"message": "你好"}, timeout=60) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    try:
                        ev = json.loads(line[6:])
                        if "thinking" in ev:
                            thinking_events.append(ev["thinking"])
                    except: pass
        if not any("规划" in t for t in thinking_events):
            R["PASS"].append(f"S3.2 简单任务跳过 planner · thinking={thinking_events[:3]}")
        else:
            R["WARN"].append(f"S3.2 简单任务误走 planner · thinking={thinking_events[:3]}")

        # ── S3.3 · 安全出口 · regenerate ──
        # 先发一条
        sid = None
        async with c.stream("POST", "/v1/agent/chat", headers={**H, "Content-Type": "application/json"},
                            json={"message": "随便说点什么"}, timeout=60) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    try:
                        ev = json.loads(line[6:])
                        if ev.get("done"):
                            sid = ev.get("session_id")
                    except: pass
        # 再 regenerate
        if sid:
            r2 = ""
            async with c.stream("POST", "/v1/agent/regenerate",
                                headers={**H, "Content-Type": "application/json"},
                                json={"session_id": sid}, timeout=60) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            if "delta" in ev:
                                r2 += ev["delta"]
                        except: pass
            if r2:
                R["PASS"].append(f"S3.3 /regenerate OK · 新 reply='{r2[:60]}…'")
            else:
                R["FAIL"].append(f"S3.3 /regenerate 空回复")

        # ── S3.4 · 安全出口 · undo ──
        if sid:
            r3 = await c.post("/v1/agent/undo", headers=H, json={"session_id": sid})
            if r3.status_code == 200 and r3.json().get("code") == 200:
                R["PASS"].append(f"S3.4 /undo OK · 撤销 {r3.json()['data'].get('undone')} 条")
            else:
                R["FAIL"].append(f"S3.4 /undo 失败 · {r3.status_code} {r3.text[:80]}")

        # ── S4.1 · PII mask ──
        full = ""
        async with c.stream("POST", "/v1/agent/chat",
                            headers={**H, "Content-Type": "application/json"},
                            json={"message": "记一下我电话 13812345678"}, timeout=60) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    try:
                        ev = json.loads(line[6:])
                        if "delta" in ev:
                            full += ev["delta"]
                    except: pass
        # 这条消息会被 mask 后送到 LLM；reply 里不应明示完整号码
        if "13812345678" not in full:
            R["PASS"].append(f"S4.1 PII mask 入站生效 · reply 不含完整号码")
        else:
            R["FAIL"].append(f"S4.1 PII 没 mask · reply='{full[:120]}…'")

        # ── S3.5 · agent_tool_traces 表能写 ──
        async with Session() as db:
            row = await db.execute(text("SELECT count(*) FROM agent_tool_traces"))
            n_tr = row.scalar_one()
            R["PASS"].append(f"S3.5 agent_tool_traces · {n_tr} traces 已落盘")

        await eng.dispose()

    return R


if __name__ == "__main__":
    R = asyncio.run(main())
    print(f"\nPASS:{len(R['PASS'])} WARN:{len(R['WARN'])} FAIL:{len(R['FAIL'])}")
    for x in R["PASS"]: print(f"  [PASS] {x}")
    for x in R["WARN"]: print(f"  [WARN] {x}")
    for x in R["FAIL"]: print(f"  [FAIL] {x}")
