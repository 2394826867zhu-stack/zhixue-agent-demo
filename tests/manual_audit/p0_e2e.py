"""v0.33 P0 三件 端到端真打"""
import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
import httpx

BASE = "http://127.0.0.1:8000"


async def main():
    R = {"PASS": [], "WARN": [], "FAIL": []}
    log = R["PASS"].append

    async with httpx.AsyncClient(base_url=BASE, timeout=180) as c:
        em = f"p0_test_{uuid.uuid4().hex[:6]}@test.com"
        await c.post("/v1/auth/register", json={"email": em, "password": "TestPass123!"})
        l = await c.post("/v1/auth/login", json={"email": em, "password": "TestPass123!"})
        tok = l.json()["data"]["access_token"]
        H = {"Authorization": f"Bearer {tok}"}
        import base64
        uid = json.loads(base64.urlsafe_b64decode(tok.split('.')[1] + '=='))['sub']

        # ===== P0-1 · 24h 首次复习 =====
        # 创建 KP + 闪卡，验证 due_date=tomorrow
        r = await c.post("/v1/knowledge-points", headers=H, json={
            "name": "导数定义", "subject": "数学",
            "content": "f'(x) = lim Δx→0 [f(x+Δx)-f(x)]/Δx",
            "bloom_level": "remember",
        })
        if r.status_code != 200:
            R["FAIL"].append(f"P0-1 创建 KP 失败: {r.text[:80]}")
            return R
        kp_id = r.json()["data"]["id"]

        r = await c.post("/v1/flashcards", headers=H, json={
            "knowledge_point_id": kp_id,
            "front": "导数的定义？", "back": "lim Δx→0 ...",
            "card_type": "concept",
        })
        if r.status_code != 200:
            R["FAIL"].append(f"P0-1 创建闪卡失败: {r.text[:80]}")
            return R
        card = r.json()["data"]
        from datetime import date
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        if card["due_date"] == tomorrow:
            log(f"P0-1 闪卡 due_date = 明天 ({tomorrow}) ✓ 24h 机制生效")
        else:
            R["FAIL"].append(f"P0-1 due_date={card['due_date']} 不是明天 {tomorrow}")

        # 手动伪造 created_at 到 24h 前（直接 SQL）然后跑扫描
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import text
        from app.config import settings
        eng = create_async_engine(settings.DATABASE_URL, echo=False)
        S = async_sessionmaker(eng, expire_on_commit=False)
        async with S() as db:
            await db.execute(text("""
                UPDATE flashcards
                SET created_at = now() - interval '24 hours',
                    first_review_pushed_at = NULL,
                    review_count = 0
                WHERE id = :cid
            """), {"cid": card["id"]})
            await db.commit()
        # 跑扫描
        from app.tasks.first_review_tasks import _scan_async
        scan_result = await _scan_async()
        if scan_result.get("pushed", 0) >= 1:
            log(f"P0-1 scan_first_review_due 推送 {scan_result['pushed']} 张卡 ✓")
        else:
            R["WARN"].append(f"P0-1 扫描未推送: {scan_result}")
        # 验证 notification 写入
        async with S() as db:
            r2 = await db.execute(text(
                "SELECT count(*) FROM notifications WHERE user_id=:uid AND notification_type='first_review_24h'"
            ), {"uid": uid})
            n = r2.scalar_one()
        if n >= 1:
            log(f"P0-1 notifications 写入 {n} 条 (first_review_24h) ✓")
        else:
            R["FAIL"].append(f"P0-1 notification 没写入")
        # 验证 first_review_pushed_at 标记
        async with S() as db:
            r2 = await db.execute(text(
                "SELECT first_review_pushed_at IS NOT NULL FROM flashcards WHERE id=:cid"
            ), {"cid": card["id"]})
            ok_marked = r2.scalar_one()
        if ok_marked:
            log(f"P0-1 flashcard first_review_pushed_at 已标记 ✓")
        else:
            R["FAIL"].append(f"P0-1 first_review_pushed_at 未标记")

        # 二次扫描验证幂等
        scan2 = await _scan_async()
        if scan2.get("pushed", 0) == 0:
            log(f"P0-1 二次扫描幂等 · 不重复推 ✓")
        else:
            R["WARN"].append(f"P0-1 二次扫描重复推 {scan2}")

        # ===== P0-2 · spot_quiz =====
        # 通过 API 触发（需要 ss_session_id）
        # 先随便建一个 ss session — 但 createSession 需要 chapter_id。我们用 mock_exam 简化
        # 实际可以直接调 service 验证
        from app.services.spot_quiz_service import spot_quiz_service
        async with S() as db:
            result = await spot_quiz_service.generate_for_kp(
                db, user_id=uid, kp_id=kp_id, count=1,
            )
        if result.get("questions"):
            q = result["questions"][0]
            log(f"P0-2 spot_quiz 生成 1 题 ✓ · text='{q['question_text'][:50]}' · ref='{q['reference_answer'][:40]}'")
        else:
            R["FAIL"].append(f"P0-2 spot_quiz 出题失败: {result}")

        # 二次调用同 KP 应复用同一 session
        async with S() as db:
            r2 = await spot_quiz_service.generate_for_kp(
                db, user_id=uid, kp_id=kp_id, count=1,
            )
        if r2.get("questions") and r2["training_session_id"] == result["training_session_id"]:
            log(f"P0-2 复用 session OK · 单日同 KP 同 session ✓")
        else:
            R["WARN"].append(f"P0-2 复用逻辑可疑")

        # 测 Agent 工具调用路径
        # 让 Agent 在 chat 里被请求出题
        full = ""
        tools = []
        try:
            async with c.stream("POST", "/v1/agent/chat",
                                headers={**H, "Content-Type": "application/json"},
                                json={"message": f"刚学完知识点 {kp_id}，调用 spot_quiz 给我出 1 道题"},
                                timeout=120) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            if "delta" in ev:
                                full += ev["delta"]
                            if ev.get("done"):
                                tools = ev.get("tools_called", [])
                        except Exception:
                            pass
        except Exception as e:
            R["WARN"].append(f"P0-2 Agent chat exception: {e}")
        if "spot_quiz" in tools:
            log(f"P0-2 Agent 通过工具调用 spot_quiz ✓ · reply='{full[:60]}'")
        else:
            R["WARN"].append(f"P0-2 Agent 没调 spot_quiz · tools={tools}")

        # ===== P0-3 · 周复盘 =====
        # 调用 API 触发
        t0 = time.time()
        r = await c.post("/v1/profile/reflection/generate", headers=H)
        elapsed = time.time() - t0
        if r.status_code == 200 and r.json().get("code") == 200:
            data = r.json()["data"]
            log(f"P0-3 周复盘生成 OK · {elapsed:.1f}s · week_start={data.get('week_start')} · len={data.get('len')}")
        else:
            R["FAIL"].append(f"P0-3 复盘生成失败: {r.status_code} {r.text[:100]}")

        # 验证 reflection 表写入
        async with S() as db:
            row = await db.execute(text(
                "SELECT content FROM weekly_reflections WHERE user_id=:uid ORDER BY week_start DESC LIMIT 1"
            ), {"uid": uid})
            r3 = row.scalar_one_or_none()
        if r3:
            log(f"P0-3 reflection 已落盘 ✓ · content='{r3[:80]}…'")
        else:
            R["FAIL"].append(f"P0-3 reflection 未落盘")

        # 验证 notification + episode
        async with S() as db:
            cnt = (await db.execute(text(
                "SELECT count(*) FROM notifications WHERE user_id=:uid AND notification_type='weekly_reflection'"
            ), {"uid": uid})).scalar_one()
        if cnt >= 1:
            log(f"P0-3 周复盘 notification 推送 ✓ · {cnt} 条")
        else:
            R["WARN"].append("P0-3 notification 未推")

        async with S() as db:
            cnt = (await db.execute(text(
                "SELECT count(*) FROM agent_episodes WHERE user_id=:uid AND event_kind='agent_observation' AND summary LIKE '周复盘%'"
            ), {"uid": uid})).scalar_one()
        if cnt >= 1:
            log(f"P0-3 周复盘 episode 写入 ✓ · {cnt} 条")

        # 二次生成应覆盖（幂等）
        r = await c.post("/v1/profile/reflection/generate", headers=H)
        if r.status_code == 200:
            async with S() as db:
                cnt = (await db.execute(text(
                    "SELECT count(*) FROM weekly_reflections WHERE user_id=:uid"
                ), {"uid": uid})).scalar_one()
            if cnt == 1:
                log(f"P0-3 重复生成覆盖 ✓ · 仍只有 1 条本周记录")
            else:
                R["WARN"].append(f"P0-3 重复生成产生 {cnt} 条")

        await eng.dispose()

    return R


if __name__ == "__main__":
    R = asyncio.run(main())
    print()
    print("=" * 72)
    print(f"PASS:{len(R['PASS'])} WARN:{len(R['WARN'])} FAIL:{len(R['FAIL'])}")
    print("=" * 72)
    for x in R["PASS"]:
        print(f"  [PASS] {x}")
    for x in R["WARN"]:
        print(f"  [WARN] {x}")
    for x in R["FAIL"]:
        print(f"  [FAIL] {x}")
