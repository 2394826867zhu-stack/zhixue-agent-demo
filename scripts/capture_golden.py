"""SDD 契约 · Golden 快照抓取（计划 0.3 落地）。

把一组代表性端点的**真实 Envelope 响应**抓成 golden fixtures，写入
`tests/contract/golden/*.json`。这些 fixtures 同时给后端做字段裁剪安全网，
并被前端 vendor 一份当 jest 契约测试的样本 —— 前后端用同一组真实样本双向锁定：
后端字段漂移 → 重抓 golden → 前端 `zod.gen` parse 失败 → 测试红。

**确定性**：种子数据全部用固定 UUID + 固定时间戳（不依赖运行时 now/random），
聚合端点（insights/overview/stats）由固定种子算出固定整数，因此重复运行
产出 byte 稳定的 golden（`sort_keys=True`），diff 干净。

运行（需 zhiyao_test 库 + Postgres 在跑）：
    $env:PYTHONPATH="."; $env:PYTHONIOENCODING="utf-8"
    python scripts/capture_golden.py

每个 golden 记录后端契约真相：method / path / 该路由 200 响应的 OpenAPI
组件 $ref（前端据此解析对应生成的 zod schema）/ 完整 envelope 响应。
"""
import asyncio
import json
import uuid
from datetime import datetime, date, timezone
from pathlib import Path

from httpx import AsyncClient, ASGITransport
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.models.training import TrainingSession, TrainingQuestion
from app.models.task import DailyTask
from app.models.project import Project, ProjectPhase, ProjectMilestone

TEST_DATABASE_URL = "postgresql+asyncpg://zhiyao:zhiyao_dev_password@localhost:5432/zhiyao_test"
GOLDEN_DIR = Path(__file__).resolve().parent.parent / "tests" / "contract" / "golden"

# ── 固定种子（确定性）────────────────────────────────────────────────
DT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
DT2 = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
D = date(2026, 1, 1)

KP_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
SESS_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
Q_CORRECT_ID = uuid.UUID("00000000-0000-4000-8000-000000000003")
Q_WRONG_ID = uuid.UUID("00000000-0000-4000-8000-000000000004")  # = 错题
TASK_ID = uuid.UUID("00000000-0000-4000-8000-000000000005")
PROJ_ID = uuid.UUID("00000000-0000-4000-8000-000000000006")
PHASE_ID = uuid.UUID("00000000-0000-4000-8000-000000000007")
MILESTONE_ID = uuid.UUID("00000000-0000-4000-8000-000000000008")

SEED_EMAIL = "golden@zhiyao.ai"
SEED_PASSWORD = "password123"


async def _seed(db: AsyncSession, uid: uuid.UUID) -> None:
    """在已注册用户名下种入确定性的代表性数据。"""
    db.add(KnowledgePoint(
        id=KP_ID, user_id=uid, name="一元二次方程的求根公式", subject="math",
        content="ax^2+bx+c=0 的根为 x=(-b±√(b²-4ac))/2a",
        key_formula="x=(-b±√(b²-4ac))/2a", bloom_level="apply",
        mastery_status="reviewing", difficulty_tier="purple",
        notebook_origin="user_project", p_mastery=0.75,
        created_at=DT, updated_at=DT,
    ))
    db.add(TrainingSession(
        id=SESS_ID, user_id=uid, mode="single_kp", subject="math",
        knowledge_point_id=KP_ID, status="completed",
        question_count=2, answered_count=2, avg_score=65.0,
        created_at=DT, completed_at=DT2,
    ))
    db.add(TrainingQuestion(
        id=Q_CORRECT_ID, session_id=SESS_ID, user_id=uid, knowledge_point_id=KP_ID,
        bloom_level="apply", question_type="short_answer",
        question_text="请写出一元二次方程的求根公式。",
        reference_answer="x=(-b±√(b²-4ac))/2a",
        user_answer="x=(-b±√(b²-4ac))/2a", ai_score=90,
        ai_feedback="完全正确，公式记得很牢。", is_wrong=False, is_retry=False,
        notebook_origin="user_project", answered_at=DT2, created_at=DT,
    ))
    db.add(TrainingQuestion(
        id=Q_WRONG_ID, session_id=SESS_ID, user_id=uid, knowledge_point_id=KP_ID,
        bloom_level="apply", question_type="calculation",
        question_text="解方程 x²-5x+6=0。",
        reference_answer="x=2 或 x=3",
        user_answer="x=1 或 x=6", ai_score=40,
        ai_feedback="因式分解的两个根之积应等于常数项 6，请重新检查。",
        is_wrong=True, is_retry=False, error_reason="concept",
        notebook_origin="user_project", answered_at=DT2, created_at=DT,
    ))
    db.add(DailyTask(
        id=TASK_ID, user_id=uid, task_date=D, title="复习一元二次方程错题",
        task_type="manual", subject="math", estimated_minutes=30,
        priority="high", ai_priority_score=80.0,
        ai_priority_reason="该知识点近期有错题，且明天有考试。",
        sort_order=0, source="user", status="pending", created_at=DT,
    ))
    db.add(Project(
        id=PROJ_ID, user_id=uid, name="中考数学冲刺", summary="系统复习初中数学核心考点。",
        source="user_project", subject="math", status="active", init_context={},
        target_completion_date=DT2, weekly_hours=10.0,
        completion_pct=30.0, mastery_pct=20.0, sort_order=0,
        started_at=DT, created_at=DT, updated_at=DT,
    ))
    db.add(ProjectPhase(
        id=PHASE_ID, project_id=PROJ_ID, name="基础巩固", description="过一遍全部知识点。",
        start_date=DT, end_date=DT2, sort_order=0, is_current=True,
        completion_pct=30.0, created_at=DT,
    ))
    db.add(ProjectMilestone(
        id=MILESTONE_ID, project_id=PROJ_ID, title="期中模拟考", description="阶段检测。",
        milestone_type="exam", event_date=DT2, is_completed=False, created_at=DT,
    ))
    await db.commit()


def _ref_for(openapi: dict, path: str, method: str) -> str:
    """取该路由 200 响应的 OpenAPI 组件名（去掉 #/components/schemas/ 前缀）。

    前端据此解析对应生成的 zod schema —— golden 记录的是后端契约真相
    （OpenAPI 组件 ref），不耦合前端命名。
    """
    schema = (
        openapi["paths"][path][method.lower()]
        ["responses"]["200"]["content"]["application/json"]["schema"]
    )
    ref = schema.get("$ref")
    if not ref:
        raise RuntimeError(f"{method} {path} 200 响应无 $ref（response_model 缺失？）: {schema}")
    return ref.rsplit("/", 1)[-1]


# 抓取清单：(golden 文件名, method, 真实路径, OpenAPI 路径模板)
CAPTURES = [
    ("mistakes_list",     "GET", "/v1/mistakes",                  "/v1/mistakes"),
    ("mistakes_detail",   "GET", f"/v1/mistakes/{Q_WRONG_ID}",    "/v1/mistakes/{question_id}"),
    ("mistakes_stats",    "GET", "/v1/mistakes/stats",            "/v1/mistakes/stats"),
    ("tasks_today",       "GET", "/v1/tasks",                     "/v1/tasks"),
    ("project_detail",    "GET", f"/v1/projects/{PROJ_ID}",       "/v1/projects/{project_id}"),
    ("training_detail",   "GET", f"/v1/training/{SESS_ID}",       "/v1/training/{session_id}"),
    ("profile_insights",  "GET", "/v1/profile/insights",          "/v1/profile/insights"),
    ("progress_overview", "GET", "/v1/progress/overview",         "/v1/progress/overview"),
]


async def main() -> None:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 干净重建 schema（capture 跑在 zhiyao_test，独占）
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session = Session()

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app, client=("203.0.113.1", 123))

    openapi = app.openapi()
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    written = []

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            reg = await client.post("/v1/auth/register", json={"email": SEED_EMAIL, "password": SEED_PASSWORD})
            assert reg.status_code == 200, f"register failed: {reg.text}"
            token = reg.json()["data"]["access_token"]
            uid = (await session.execute(select(User).where(User.email == SEED_EMAIL))).scalar_one().id

            await _seed(session, uid)

            headers = {"Authorization": f"Bearer {token}"}
            for name, method, real_path, tmpl in CAPTURES:
                resp = await client.request(method, real_path, headers=headers)
                assert resp.status_code == 200, f"{method} {real_path} → {resp.status_code}: {resp.text}"
                body = resp.json()
                assert body.get("code") == 200, f"{real_path}: 非成功响应 {body}"

                golden = {
                    "name": name,
                    "method": method,
                    "path": real_path,
                    "openapi_path": tmpl,
                    "openapi_ref": _ref_for(openapi, tmpl, method),
                    "status": resp.status_code,
                    "response": body,
                }
                out = GOLDEN_DIR / f"{name}.json"
                out.write_text(
                    json.dumps(golden, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                written.append(out.name)
                print(f"  ✓ {name:<18} {method} {real_path}  →  {golden['openapi_ref']}")
    finally:
        app.dependency_overrides.clear()
        await session.close()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    print(f"\n抓取完成：{len(written)} 个 golden 写入 {GOLDEN_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
