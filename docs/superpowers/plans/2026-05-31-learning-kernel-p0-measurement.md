# 知曜学习内核 P0「度量先行」Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在改任何学习策略之前，先为知曜建立"掌握度真相"——给每个知识点一个可校准的掌握概率（BKT + FSRS 遗忘层），把答题/费曼/闪卡作为更新信号，加探针测真实留存/迁移，并用 eval harness + 校准监控证明它没自欺。

**Architecture:** 新增一个纯函数化的 `measurement_service`（BKT 数学是纯函数，DB 写入是薄壳），叠加复用现有 `fsrs_service.retrievability` 做遗忘层；在现有 `submit_answer`/`feynman_grade`/闪卡复习三个答题事件里挂一个掌握度更新钩子；新增 `probe_service` 选取到期留存探针 + 标记探针结果（探针不计入练习统计）；仿照现有 `app/eval` + `scripts/run_retrieval_eval.py` 模式建学习增益 eval；用一个 Celery beat 任务做校准监控。**P0 不碰知识图谱（P1 才做），知识点之间视为孤立节点。**

**Tech Stack:** FastAPI · SQLAlchemy async（`declarative_base()` 经典 `Column` 风格）· Alembic（字符串 revision，当前 head `034`）· Celery + Redis · pytest + pytest-asyncio（`asyncio_mode=auto`）· 测试库 `zhiyao_test`（Postgres + pgvector）。

**理论出处**：`知曜学习内核_理论地基.md` 的 M2(BKT 四参数 + guess/slip≤0.5 钳制)、M3(FSRS retrievability/遗忘)、M9(留存/迁移探针)、M10(归一化增益 + 校准)。设计出处：`知曜学习内核_设计.md` §2、§4。

---

## ⚠️ 开工前必做（每个 Task 通用前置）

- [ ] 启动依赖：`docker compose up -d`（Postgres 容器 `zhiyao_pg`），确认 Redis（Windows 原生 6379）在跑。
- [ ] 激活 venv，`cd zhiyao-backend`。
- [ ] 基线绿：`PYTHONPATH=. pytest -q` 必须先全绿再开工。
- [ ] `git log --oneline -5` 确认起点，`alembic current` 应显示 `034`。
- [ ] **验证点（探查报告标注的"行号会漂移"项）**：动手改 `training_service.submit_answer` 前，先 `grep -n 'error_reason == "concept"' app/services/training_service.py` 定位掌握度变更块；改前先 `Read` 当前 `fsrs_service.retrievability` 的真实签名与 `app/celery_app.py` 的 `beat_schedule` 真实结构。计划里的引用以仓库现状为准，不一致以仓库为准。

---

## File Structure（P0 决策锁定）

| 文件 | 职责 | 新建/修改 |
|---|---|---|
| `alembic/versions/035_learning_kernel_mastery.py` | KP 加 `p_mastery`/`last_probe`；training_questions 加 `is_probe`/`probe_kind` | 新建 |
| `app/models/knowledge_point.py` | 加两列 | 修改 |
| `app/models/training.py` | TrainingQuestion 加两列 | 修改 |
| `app/services/measurement_service.py` | BKT 纯函数 + 遗忘层 + DB 更新薄壳 | 新建 |
| `app/services/probe_service.py` | 选到期留存探针 + 记录探针结果 | 新建 |
| `app/services/training_service.py` | submit_answer 挂掌握度钩子 + 尊重 is_probe | 修改 |
| `app/services/feynman_service.py` | feynman_grade 挂掌握度钩子 | 修改 |
| `app/services/flashcard_service.py`（或复习端点处） | 复习评分挂掌握度钩子 | 修改 |
| `app/eval/learning_gain.py` | 纯指标：归一化增益 / 单位时长增益 / 校准分箱 | 新建 |
| `scripts/run_learning_gain_eval.py` | 仿 run_retrieval_eval：seed→跑 BKT→出报告 | 新建 |
| `app/tasks/learning_kernel_tasks.py` | 校准监控 Celery 任务 | 新建 |
| `app/celery_app.py` | beat 加校准监控条目 | 修改 |
| `tests/services/test_measurement_service.py` | BKT/遗忘单测 | 新建 |
| `tests/services/test_probe_service.py` | 探针单测 | 新建 |
| `tests/services/test_mastery_update_integration.py` | 答题→掌握度集成测 | 新建 |
| `tests/eval/test_learning_gain.py` | 学习增益指标单测 | 新建 |
| `tests/tasks/test_calibration_monitor.py` | 校准任务单测 | 新建 |

**设计原则**：把"BKT 数学"和"DB 写入"彻底分离——数学是纯函数（零依赖、秒级 TDD），写入是只做 load→调纯函数→save 的薄壳。探针失败、kp_id 缺失都静默降级（设计§1.3 兜底）。

---

## Task 1: G-P0-1 数据库迁移 + 模型字段

**Files:**
- Create: `alembic/versions/035_learning_kernel_mastery.py`
- Modify: `app/models/knowledge_point.py`、`app/models/training.py`
- Test: `tests/services/test_measurement_service.py`（本任务先放一个 schema 冒烟测试）

- [ ] **Step 1: 写迁移文件**

```python
"""learning kernel: mastery probability + probe flags

Revision ID: 035
Revises: 034
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_points", sa.Column("p_mastery", sa.Float(), nullable=True))
    op.add_column("knowledge_points", sa.Column("last_probe", postgresql.JSONB(), nullable=True))
    op.add_column(
        "training_questions",
        sa.Column("is_probe", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("training_questions", sa.Column("probe_kind", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("training_questions", "probe_kind")
    op.drop_column("training_questions", "is_probe")
    op.drop_column("knowledge_points", "last_probe")
    op.drop_column("knowledge_points", "p_mastery")
```

- [ ] **Step 2: 改模型 `app/models/knowledge_point.py`**

在导入处确保 `Float` 已从 `sqlalchemy` 导入、`JSONB` 从 `sqlalchemy.dialects.postgresql` 导入；在 `tags` 列后加：

```python
    # 学习内核 P0：掌握度真相
    p_mastery = Column(Float, nullable=True)          # BKT 校准掌握概率 [0,1]；None=未评估
    last_probe = Column(JSONB, nullable=True)         # {"kind":"retention|transfer","correct":bool,"at":iso,"p_after":float}
```

- [ ] **Step 3: 改模型 `app/models/training.py`**

在 `TrainingQuestion` 的 `created_at` 前加：

```python
    is_probe = Column(Boolean, nullable=False, default=False)   # 探针题：不计入练习统计
    probe_kind = Column(String(20), nullable=True)              # 'retention' | 'transfer'
```

- [ ] **Step 4: 跑迁移并验证 head**

Run: `alembic upgrade head && alembic current`
Expected: 末行显示 `035 (head)`，无报错。

- [ ] **Step 5: schema 冒烟测试**

在 `tests/services/test_measurement_service.py` 写：

```python
import pytest
from app.models.knowledge_point import KnowledgePoint
from app.models.training import TrainingQuestion


def test_new_columns_exist_on_models():
    assert hasattr(KnowledgePoint, "p_mastery")
    assert hasattr(KnowledgePoint, "last_probe")
    assert hasattr(TrainingQuestion, "is_probe")
    assert hasattr(TrainingQuestion, "probe_kind")
```

Run: `PYTHONPATH=. pytest tests/services/test_measurement_service.py -v`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/035_learning_kernel_mastery.py app/models/knowledge_point.py app/models/training.py tests/services/test_measurement_service.py
git commit -m "feat(kernel): P0-1 add p_mastery/last_probe + probe flags (migration 035)"
```

---

## Task 2: G-P0-2 BKT 掌握度更新（纯函数）

**Files:**
- Create: `app/services/measurement_service.py`
- Test: `tests/services/test_measurement_service.py`（追加）

BKT 参数默认值（M2，钳制 guess/slip≤0.5）：`p_init=0.30, p_transit=0.15, p_guess=0.20, p_slip=0.10`。

- [ ] **Step 1: 写失败测试（追加到 test_measurement_service.py）**

```python
from app.services import measurement_service as ms


def test_bkt_correct_raises_mastery():
    after = ms.bkt_update(prior=0.30, correct=True)
    assert after > 0.30
    assert 0.0 <= after <= 1.0


def test_bkt_incorrect_lowers_belief_before_learning():
    # 答错：后验信念应低于"先验经过一次学习"的天花板；至少不应高于答对
    after_wrong = ms.bkt_update(prior=0.50, correct=False)
    after_right = ms.bkt_update(prior=0.50, correct=True)
    assert after_wrong < after_right


def test_bkt_guess_slip_are_clamped_to_half():
    # 传入退化参数（>0.5）必须被钳制，不得出现"答错反而更掌握"
    after_wrong = ms.bkt_update(prior=0.50, correct=False, guess=0.9, slip=0.9)
    after_right = ms.bkt_update(prior=0.50, correct=True, guess=0.9, slip=0.9)
    assert after_right >= after_wrong  # 钳制后答对不劣于答错


def test_bkt_none_prior_uses_p_init():
    after = ms.bkt_update(prior=None, correct=True)
    assert after > ms.P_INIT
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. pytest tests/services/test_measurement_service.py -v`
Expected: FAIL（`module has no attribute 'bkt_update'`）。

- [ ] **Step 3: 写实现 `app/services/measurement_service.py`**

```python
"""学习内核 · 度量服务（measurement_service）。

BKT 数学是纯函数（零 DB 依赖），便于 TDD 与 eval 复用。
理论：知曜学习内核_理论地基.md M2（BKT 四参数 + guess/slip≤0.5 钳制）。
"""
from __future__ import annotations

# BKT 默认四参数（M2）。guess/slip 运行时硬钳制到 [0, 0.5] 防退化。
P_INIT = 0.30      # p-init 先验掌握概率
P_TRANSIT = 0.15   # p-transit 学习率（未学→已学）
P_GUESS = 0.20     # p-guess 未掌握却答对
P_SLIP = 0.10      # p-slip 已掌握却答错
_CLAMP = 0.5       # M2: Baker/Corbett/Aleven 2008 退化边界


def _clamp_half(x: float) -> float:
    return max(0.0, min(_CLAMP, x))


def bkt_update(
    prior: float | None,
    correct: bool,
    *,
    guess: float = P_GUESS,
    slip: float = P_SLIP,
    learn: float = P_TRANSIT,
) -> float:
    """单技能 BKT 贝叶斯更新：返回观测+学习后的新掌握概率 [0,1]。

    prior=None 时用 P_INIT。guess/slip 钳制到 [0,0.5]（M2 防退化）。
    """
    p = P_INIT if prior is None else max(0.0, min(1.0, prior))
    g = _clamp_half(guess)
    s = _clamp_half(slip)

    if correct:
        num = p * (1.0 - s)
        den = p * (1.0 - s) + (1.0 - p) * g
    else:
        num = p * s
        den = p * s + (1.0 - p) * (1.0 - g)

    posterior = (num / den) if den > 0 else p
    # 学习转移：本次交互后可能从未学→已学
    p_next = posterior + (1.0 - posterior) * learn
    return max(0.0, min(1.0, p_next))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONPATH=. pytest tests/services/test_measurement_service.py -v`
Expected: PASS（全部）。

- [ ] **Step 5: Commit**

```bash
git add app/services/measurement_service.py tests/services/test_measurement_service.py
git commit -m "feat(kernel): P0-2 BKT mastery update (pure fn, guess/slip clamped)"
```

---

## Task 3: G-P0-3 FSRS 遗忘层（有效掌握度）

**Files:**
- Modify: `app/services/measurement_service.py`（追加 `effective_mastery`）
- Test: `tests/services/test_measurement_service.py`（追加）

思路：`p_mastery` 是"学没学会"，FSRS 的 R 是"还记不记得"，两者正交相乘 → 有效掌握度随时间衰减（设计§2.2）。

- [ ] **Step 1: 写失败测试**

```python
from datetime import datetime, timedelta, timezone


def test_effective_mastery_decays_with_time():
    now = datetime.now(timezone.utc)
    fresh = ms.effective_mastery(p_mastery=0.8, stability=10.0, last_reviewed_at=now, now=now)
    later = ms.effective_mastery(p_mastery=0.8, stability=10.0, last_reviewed_at=now,
                                 now=now + timedelta(days=30))
    assert fresh == pytest.approx(0.8, abs=1e-3)   # 刚复习 R≈1 → 有效≈p_mastery
    assert later < fresh                            # 时间推移有效掌握度下降
    assert 0.0 <= later <= 1.0


def test_effective_mastery_none_inputs_degrade_gracefully():
    # 兜底：缺 p_mastery 或缺 last_reviewed_at 不崩
    assert ms.effective_mastery(p_mastery=None, stability=10.0, last_reviewed_at=None, now=None) == 0.0
    val = ms.effective_mastery(p_mastery=0.7, stability=10.0, last_reviewed_at=None, now=None)
    assert val == pytest.approx(0.7, abs=1e-6)      # 无复习时间 → R=1 → 有效=p_mastery
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. pytest tests/services/test_measurement_service.py::test_effective_mastery_decays_with_time -v`
Expected: FAIL（`no attribute 'effective_mastery'`）。

- [ ] **Step 3: 写实现（追加到 measurement_service.py）**

```python
from datetime import datetime

from app.services import fsrs_service


def effective_mastery(
    *,
    p_mastery: float | None,
    stability: float,
    last_reviewed_at: datetime | None,
    now: datetime | None = None,
) -> float:
    """有效掌握度 = 学没学会 × 还记不记得 = p_mastery × R(FSRS)。

    p_mastery=None → 0.0（未评估）。last_reviewed_at=None → R=1（未复习过，按当前 p_mastery）。
    依赖 fsrs_service.retrievability（纯函数，幂律遗忘曲线）。
    """
    if p_mastery is None:
        return 0.0
    try:
        r = fsrs_service.retrievability(
            stability=stability, last_reviewed_at=last_reviewed_at, now=now
        )
    except Exception:
        r = 1.0  # 兜底：R 计算失败按"未衰减"，绝不因度量层拖垮主流程
    return max(0.0, min(1.0, p_mastery * r))
```

> 验证点：确认 `fsrs_service.retrievability` 真实签名与上面一致（探查报告：`stability=`, `last_reviewed_at=`, `now=`）。若不同，以仓库为准调整调用。

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONPATH=. pytest tests/services/test_measurement_service.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add app/services/measurement_service.py tests/services/test_measurement_service.py
git commit -m "feat(kernel): P0-3 FSRS forgetting layer (effective_mastery = p_mastery x R)"
```

---

## Task 4: G-P0-4 答题事件接 BKT（DB 薄壳 + 三处钩子）

**Files:**
- Modify: `app/services/measurement_service.py`（加 `update_mastery_on_answer` DB 薄壳）
- Modify: `app/services/training_service.py`、`app/services/feynman_service.py`、`app/services/flashcard_service.py`（复习处）
- Test: `tests/services/test_mastery_update_integration.py`

- [ ] **Step 1: 写 DB 薄壳的单测（追加到 test_measurement_service.py，纯逻辑部分）**

```python
class _FakeKP:
    def __init__(self, p_mastery=None):
        self.p_mastery = p_mastery


def test_apply_answer_to_kp_updates_in_place():
    kp = _FakeKP(p_mastery=0.3)
    ms.apply_answer_to_kp(kp, correct=True)
    assert kp.p_mastery > 0.3


def test_apply_answer_to_kp_handles_none_prior():
    kp = _FakeKP(p_mastery=None)
    ms.apply_answer_to_kp(kp, correct=True)
    assert kp.p_mastery is not None and kp.p_mastery > ms.P_INIT
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. pytest tests/services/test_measurement_service.py -k apply_answer -v`
Expected: FAIL。

- [ ] **Step 3: 写实现（追加到 measurement_service.py）**

```python
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.knowledge_point import KnowledgePoint

logger = logging.getLogger(__name__)


def apply_answer_to_kp(kp, correct: bool) -> None:
    """就地更新一个 KP 的 p_mastery（纯对象操作，便于测试）。"""
    kp.p_mastery = bkt_update(prior=kp.p_mastery, correct=correct)


async def update_mastery_on_answer(
    db: AsyncSession, kp_id: uuid.UUID | None, correct: bool
) -> None:
    """答题事件钩子：按作答正确与否更新该 KP 的 p_mastery。

    兜底：kp_id 为空或 KP 不存在 → 静默 no-op；任何异常吞掉并记日志，
    绝不让度量层拖垮答题主流程（设计§1.3）。不在此 commit（交由调用方事务）。
    """
    if kp_id is None:
        return
    try:
        kp = await db.get(KnowledgePoint, kp_id)
        if kp is None:
            return
        apply_answer_to_kp(kp, correct=correct)
    except Exception:  # noqa: BLE001
        logger.exception("update_mastery_on_answer failed kp_id=%s", kp_id)
```

- [ ] **Step 4: 跑纯逻辑测试通过**

Run: `PYTHONPATH=. pytest tests/services/test_measurement_service.py -k apply_answer -v`
Expected: PASS。

- [ ] **Step 5: 在 `training_service.submit_answer` 挂钩子**

先 `grep -n 'error_reason == "concept"' app/services/training_service.py` 定位掌握度变更块。在该块**之后、`await db.commit()` 之前**插入（`q` 为当前 TrainingQuestion）：

```python
        # 学习内核 P0-4：把作答正确与否喂给 BKT（探针在 Task 6 单独处理，这里普通题）
        if not q.is_probe:
            from app.services import measurement_service
            await measurement_service.update_mastery_on_answer(
                db, kp_id=q.knowledge_point_id, correct=(not q.is_wrong)
            )
```

- [ ] **Step 6: 在 `feynman_service.feynman_grade` 挂钩子**

在创建 `FeynmanAttempt`、拿到 `score` 后、`commit` 前插入（费曼 score≥70 视为掌握证据，M4 提取练习）：

```python
        from app.services import measurement_service
        await measurement_service.update_mastery_on_answer(
            db, kp_id=knowledge_point_id, correct=(score is not None and score >= 70)
        )
```

- [ ] **Step 7: 在闪卡复习处挂钩子**

先 `grep -rn "def review" app/services/flashcard_service.py app/api/v1/flashcards.py` 定位复习评分落库处。在评分 `rating` 落库后、commit 前插入（FSRS rating≥3=Good/Easy 视为答对，M3）：

```python
        from app.services import measurement_service
        await measurement_service.update_mastery_on_answer(
            db, kp_id=flashcard.knowledge_point_id, correct=(rating >= 3)
        )
```

- [ ] **Step 8: 写集成测试 `tests/services/test_mastery_update_integration.py`**

```python
import pytest
from app.models.knowledge_point import KnowledgePoint
from app.services import measurement_service


async def test_correct_answer_raises_kp_mastery(db, user):
    kp = KnowledgePoint(user_id=user.id, name="牛顿第二定律", content="F=ma",
                        bloom_level="apply", subject="物理")
    db.add(kp)
    await db.flush()
    assert kp.p_mastery is None

    await measurement_service.update_mastery_on_answer(db, kp_id=kp.id, correct=True)
    await db.flush()
    refreshed = await db.get(KnowledgePoint, kp.id)
    assert refreshed.p_mastery is not None and refreshed.p_mastery > measurement_service.P_INIT


async def test_none_kp_id_is_noop(db):
    # 兜底：kp_id=None 不报错
    await measurement_service.update_mastery_on_answer(db, kp_id=None, correct=True)
```

> 验证点：`db`/`user` fixture 名以 `tests/conftest.py` 实际为准（探查报告：存在 `db`、`user` 异步 fixture，`asyncio_mode=auto`）。

- [ ] **Step 9: 跑全套确认绿**

Run: `PYTHONPATH=. pytest tests/services/test_mastery_update_integration.py tests/services/test_measurement_service.py -v && PYTHONPATH=. pytest -q`
Expected: 新测试 PASS；全套 0 fail。

- [ ] **Step 10: Commit**

```bash
git add app/services/measurement_service.py app/services/training_service.py app/services/feynman_service.py app/services/flashcard_service.py tests/services/test_mastery_update_integration.py
git commit -m "feat(kernel): P0-4 wire BKT mastery update into training/feynman/flashcard answers"
```

---

## Task 5: G-P0-5 探针机制（留存探针选取 + 结果记录 + 不计练习）

**Files:**
- Create: `app/services/probe_service.py`
- Modify: `app/services/training_service.py`（is_probe 分支：记探针结果，跳过错题归档/练习统计）
- Test: `tests/services/test_probe_service.py`

留存探针触发：FSRS R 衰减到 ≈0.9 的 KP（M3 首复习最优时机）。迁移探针：换皮新题（probe_kind="transfer"），P0 只打通"标记 + 记录"，题目生成复用现有出题（spot_quiz/compose），不在 P0 造新生成器。

- [ ] **Step 1: 写失败测试**

```python
import pytest
from datetime import datetime, timedelta, timezone
from app.models.knowledge_point import KnowledgePoint
from app.services import probe_service


def test_is_retention_probe_due_at_r_threshold():
    now = datetime.now(timezone.utc)
    # 稳定性 10 天、距上次复习足够久 → R 落到 ~0.9 附近 → 到期
    due_old = probe_service.is_retention_probe_due(
        stability=10.0, last_reviewed_at=now - timedelta(days=8), now=now, target_r=0.9
    )
    due_fresh = probe_service.is_retention_probe_due(
        stability=10.0, last_reviewed_at=now, now=now, target_r=0.9
    )
    assert due_old is True
    assert due_fresh is False


async def test_record_probe_result_writes_last_probe(db, user):
    kp = KnowledgePoint(user_id=user.id, name="动量守恒", content="p=mv",
                        bloom_level="understand", subject="物理", p_mastery=0.6)
    db.add(kp)
    await db.flush()

    await probe_service.record_probe_result(db, kp_id=kp.id, kind="retention", correct=False)
    await db.flush()
    refreshed = await db.get(KnowledgePoint, kp.id)
    assert refreshed.last_probe is not None
    assert refreshed.last_probe["kind"] == "retention"
    assert refreshed.last_probe["correct"] is False
    # 探针也更新掌握度信念
    assert "p_after" in refreshed.last_probe
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. pytest tests/services/test_probe_service.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 写实现 `app/services/probe_service.py`**

```python
"""学习内核 · 探针服务（probe_service）。

留存探针：FSRS R 降到目标阈值时回测（M3）。迁移探针：换皮新题测真懂（M9）。
探针不计入练习统计，只更新掌握度信念 + 写 KP.last_probe。
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_point import KnowledgePoint
from app.services import fsrs_service, measurement_service

logger = logging.getLogger(__name__)

DEFAULT_TARGET_R = 0.9  # M3：R≈0.9 是首复习/留存回测的最优时机（可按学科校准）


def is_retention_probe_due(
    *,
    stability: float,
    last_reviewed_at: datetime | None,
    now: datetime | None = None,
    target_r: float = DEFAULT_TARGET_R,
) -> bool:
    """R 已衰减到 ≤ target_r 即到期。未复习过(None)不触发留存探针。"""
    if last_reviewed_at is None:
        return False
    try:
        r = fsrs_service.retrievability(
            stability=stability, last_reviewed_at=last_reviewed_at, now=now
        )
    except Exception:
        return False  # 兜底：算不出就不触发
    return r <= target_r


async def record_probe_result(
    db: AsyncSession, kp_id: uuid.UUID, kind: str, correct: bool
) -> None:
    """记录探针结果：更新 p_mastery 信念 + 写 KP.last_probe。不在此 commit。"""
    if kp_id is None:
        return
    try:
        kp = await db.get(KnowledgePoint, kp_id)
        if kp is None:
            return
        measurement_service.apply_answer_to_kp(kp, correct=correct)
        kp.last_probe = {
            "kind": kind,
            "correct": bool(correct),
            "at": datetime.now(timezone.utc).isoformat(),
            "p_after": kp.p_mastery,
        }
    except Exception:  # noqa: BLE001
        logger.exception("record_probe_result failed kp_id=%s", kp_id)
```

- [ ] **Step 4: 在 `submit_answer` 处理 is_probe 分支**

在 Task 4 Step 5 插入点改为分支：探针走探针记录、且**跳过错题归档/练习时间线**（探针不计练习，设计§4.2）：

```python
        from app.services import measurement_service, probe_service
        if q.is_probe:
            await probe_service.record_probe_result(
                db, kp_id=q.knowledge_point_id,
                kind=(q.probe_kind or "retention"), correct=(not q.is_wrong),
            )
        else:
            await measurement_service.update_mastery_on_answer(
                db, kp_id=q.knowledge_point_id, correct=(not q.is_wrong)
            )
```

> 同时确认：is_probe=True 时**不要**执行错题创建 / `enqueue_mistake_index` / mastery_status 降级（在那些块加 `and not q.is_probe` 守卫）。这一步要 `Read` submit_answer 现状逐条加守卫。

- [ ] **Step 5: 跑测试确认通过 + 全套绿**

Run: `PYTHONPATH=. pytest tests/services/test_probe_service.py -v && PYTHONPATH=. pytest -q`
Expected: PASS；全套 0 fail。

- [ ] **Step 6: Commit**

```bash
git add app/services/probe_service.py app/services/training_service.py tests/services/test_probe_service.py
git commit -m "feat(kernel): P0-5 retention/transfer probes (R-threshold trigger, not counted as practice)"
```

---

## Task 6: G-P0-6 学习增益 eval harness（纯指标 + 跑分脚本）

**Files:**
- Create: `app/eval/learning_gain.py`、`scripts/run_learning_gain_eval.py`
- Test: `tests/eval/test_learning_gain.py`

镜像现有 `app/eval/metrics.py`（纯函数）+ `scripts/run_retrieval_eval.py`（zhiyao_test seed→跑→drop）。

- [ ] **Step 1: 写失败测试 `tests/eval/test_learning_gain.py`**

```python
import pytest
from app.eval import learning_gain as lg


def test_normalized_gain_hake():
    # Hake: g = (post - pre) / (100 - pre)
    assert lg.normalized_gain(pre=40.0, post=70.0) == pytest.approx(0.5, abs=1e-6)
    assert lg.normalized_gain(pre=100.0, post=100.0) == 0.0  # 防除零


def test_mastery_gain_per_hour():
    assert lg.mastery_gain_per_hour(delta_mastery=0.3, hours=1.5) == pytest.approx(0.2, abs=1e-6)
    assert lg.mastery_gain_per_hour(delta_mastery=0.3, hours=0.0) == 0.0  # 防除零


def test_calibration_bins_groups_pred_vs_actual():
    # (predicted_p, actual_correct) 对，分箱后每箱给 预测均值 vs 实际正确率
    pairs = [(0.9, True), (0.85, True), (0.1, False), (0.15, False)]
    bins = lg.calibration_bins(pairs, n_bins=2)
    # 高分箱预测高、实际全对；低分箱预测低、实际全错
    high = [b for b in bins if b["pred_mean"] > 0.5][0]
    low = [b for b in bins if b["pred_mean"] <= 0.5][0]
    assert high["actual_rate"] == pytest.approx(1.0)
    assert low["actual_rate"] == pytest.approx(0.0)


def test_expected_calibration_error():
    pairs = [(0.9, True), (0.1, False)]  # 完美校准
    assert lg.expected_calibration_error(pairs, n_bins=2) == pytest.approx(0.0, abs=0.05)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. pytest tests/eval/test_learning_gain.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 写实现 `app/eval/learning_gain.py`**

```python
"""学习内核 · 学习增益与校准指标（纯函数）。

理论：知曜学习内核_理论地基.md M10（Hake 归一化增益 + 掌握度校准）。
"""
from __future__ import annotations


def normalized_gain(*, pre: float, post: float) -> float:
    """Hake 归一化增益 g = (post - pre) / (100 - pre)。pre>=100 时返回 0。"""
    denom = 100.0 - pre
    if denom <= 0:
        return 0.0
    return (post - pre) / denom


def mastery_gain_per_hour(*, delta_mastery: float, hours: float) -> float:
    """单位学习时间的掌握提升。hours<=0 返回 0（防除零）。"""
    if hours <= 0:
        return 0.0
    return delta_mastery / hours


def calibration_bins(pairs: list[tuple[float, bool]], n_bins: int = 10) -> list[dict]:
    """把 (预测掌握概率, 实际是否答对) 分箱，返回每箱 {pred_mean, actual_rate, n}。"""
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for p, correct in pairs:
        idx = min(n_bins - 1, max(0, int(p * n_bins)))
        buckets[idx].append((p, correct))
    out = []
    for b in buckets:
        if not b:
            continue
        preds = [p for p, _ in b]
        acts = [1.0 if c else 0.0 for _, c in b]
        out.append({
            "pred_mean": sum(preds) / len(preds),
            "actual_rate": sum(acts) / len(acts),
            "n": len(b),
        })
    return out


def expected_calibration_error(pairs: list[tuple[float, bool]], n_bins: int = 10) -> float:
    """ECE：各箱 |预测均值 − 实际正确率| 按样本数加权平均。0=完美校准。"""
    bins = calibration_bins(pairs, n_bins=n_bins)
    total = sum(b["n"] for b in bins)
    if total == 0:
        return 0.0
    return sum(b["n"] * abs(b["pred_mean"] - b["actual_rate"]) for b in bins) / total
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONPATH=. pytest tests/eval/test_learning_gain.py -v`
Expected: PASS。

- [ ] **Step 5: 写跑分脚本 `scripts/run_learning_gain_eval.py`**

先 `Read scripts/run_retrieval_eval.py` 抄它的 `zhiyao_test` 引擎/seed/cleanup 骨架，再填学习增益逻辑：

```python
"""学习增益基线脚本（手动跑）：
   PYTHONPATH=. python scripts/run_learning_gain_eval.py
用 zhiyao_test：构造一批合成答题序列，跑 BKT，输出
①平均归一化增益 ②单位时长掌握增益 ③校准 ECE + reliability 分箱。
"""
import asyncio
from app.services import measurement_service as ms
from app.eval import learning_gain as lg


# 合成"学生×知识点"的答题序列（P0 用合成集建立基线；P4 换真实数据）
SYNTH = [
    {"answers": [False, True, True, True], "hours": 0.5},   # 学会了
    {"answers": [False, False, True, False], "hours": 0.5}, # 没学会
    {"answers": [True, True, True, True], "hours": 0.3},    # 本来就会
]


def _run_sequence(answers: list[bool]) -> tuple[float, float, list[tuple[float, bool]]]:
    p = None
    pairs: list[tuple[float, bool]] = []
    pre = ms.P_INIT
    for correct in answers:
        # 校准对：用"更新前的预测概率"对"本次实际是否答对"
        pred = ms.P_INIT if p is None else p
        pairs.append((pred, correct))
        p = ms.bkt_update(prior=p, correct=correct)
    post = p if p is not None else pre
    return pre, post, pairs


def main() -> None:
    all_pairs: list[tuple[float, bool]] = []
    n_gains, n_rates = [], []
    for s in SYNTH:
        pre, post, pairs = _run_sequence(s["answers"])
        all_pairs.extend(pairs)
        n_gains.append(lg.normalized_gain(pre=pre * 100, post=post * 100))
        n_rates.append(lg.mastery_gain_per_hour(delta_mastery=post - pre, hours=s["hours"]))
    print("== 学习增益基线 ==")
    print(f"平均归一化增益 ⟨g⟩ = {sum(n_gains)/len(n_gains):.3f}")
    print(f"平均单位时长掌握增益 = {sum(n_rates)/len(n_rates):.3f} /h")
    print(f"校准 ECE = {lg.expected_calibration_error(all_pairs, n_bins=5):.3f}")
    for b in lg.calibration_bins(all_pairs, n_bins=5):
        print(f"  bin pred={b['pred_mean']:.2f} actual={b['actual_rate']:.2f} n={b['n']}")


if __name__ == "__main__":
    main()
```

> 说明：P0 用合成序列建立**可复现基线**（与 RAG 阶段"先合成集再真实集"一脉相承）；纯 BKT 逻辑不需 DB，故本脚本可不连 zhiyao_test 直接跑。若后续要测真实 KP 序列，再按 run_retrieval_eval 接 zhiyao_test。

- [ ] **Step 6: 手动跑脚本确认出报告**

Run: `PYTHONPATH=. python scripts/run_learning_gain_eval.py`
Expected: 打印 ⟨g⟩、单位时长增益、ECE 与分箱，无异常。

- [ ] **Step 7: Commit**

```bash
git add app/eval/learning_gain.py scripts/run_learning_gain_eval.py tests/eval/test_learning_gain.py
git commit -m "feat(kernel): P0-6 learning-gain eval harness (normalized gain + calibration ECE)"
```

---

## Task 7: G-P0-7 掌握度校准监控（Celery beat）

**Files:**
- Create: `app/tasks/learning_kernel_tasks.py`、`tests/tasks/test_calibration_monitor.py`
- Modify: `app/celery_app.py`（beat 加条目）

监控逻辑：取最近一段时间内"预测掌握概率 vs 实际作答"对，算 ECE，超阈值 `logger.error` 告警（沿用 F-11 死信队列的"显式告警替代静默"）。

- [ ] **Step 1: 写失败测试 `tests/tasks/test_calibration_monitor.py`**

```python
import pytest
from app.tasks import learning_kernel_tasks as lkt


def test_assess_calibration_flags_miscalibration(caplog):
    # 严重失准：预测都很高但实际全错
    pairs = [(0.9, False), (0.95, False), (0.85, False)]
    ece = lkt.assess_calibration(pairs, threshold=0.2)
    assert ece > 0.2


def test_assess_calibration_ok_when_calibrated():
    pairs = [(0.9, True), (0.1, False), (0.8, True), (0.2, False)]
    ece = lkt.assess_calibration(pairs, threshold=0.2)
    assert ece <= 0.2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. pytest tests/tasks/test_calibration_monitor.py -v`
Expected: FAIL。

- [ ] **Step 3: 写实现 `app/tasks/learning_kernel_tasks.py`**

```python
"""学习内核 · 周期任务：掌握度校准监控（M10）。"""
from __future__ import annotations

import asyncio
import logging

from app.eval import learning_gain as lg

logger = logging.getLogger(__name__)

ECE_ALERT_THRESHOLD = 0.2  # ECE 超此值告警（起步阈值，按数据校准）


def assess_calibration(pairs: list[tuple[float, bool]], threshold: float = ECE_ALERT_THRESHOLD) -> float:
    """计算 ECE，超阈值告警。返回 ECE。纯逻辑，便于测试。"""
    ece = lg.expected_calibration_error(pairs, n_bins=10)
    if ece > threshold:
        logger.error("掌握度校准失准告警：ECE=%.3f > %.2f（p_mastery 需回炉/重拟合）", ece, threshold)
    return ece


async def _collect_pairs_async() -> list[tuple[float, bool]]:
    """从最近作答中收集 (更新前预测概率, 实际答对) 对。

    P0 兜底实现：若暂无可用的"预测前快照"数据，返回空列表（任务安全 no-op）。
    数据管道在 P4 复利闭环完善。
    """
    # TODO(P4)：从 training_questions 近窗 + 答前 p_mastery 快照构造 pairs
    return []


def _collect_pairs() -> list[tuple[float, bool]]:
    return asyncio.run(_collect_pairs_async())
```

接着注册 Celery 任务（放本文件底部）：

```python
from app.celery_app import celery  # 若循环导入，改为在 celery_app 里 import 本模块的函数


@celery.task(name="mastery_calibration_check", time_limit=120)
def mastery_calibration_check() -> dict:
    pairs = _collect_pairs()
    ece = assess_calibration(pairs)
    return {"n_pairs": len(pairs), "ece": ece}
```

> 验证点：`app/celery_app.py` 的实例变量名以仓库为准（探查报告：`celery = Celery(...)`）。若有循环导入风险，按现有 task 文件的导入方式对齐。

- [ ] **Step 4: 注册 beat 调度（改 `app/celery_app.py`）**

先 `Read app/celery_app.py` 找到 `celery.conf.beat_schedule`，加一条（dev 10 分钟、prod 凌晨 2 点）：

```python
    "mastery-calibration-monitor": {
        "task": "mastery_calibration_check",
        "schedule": 600.0 if settings.APP_ENV == "dev" else crontab(hour=2, minute=0),
    },
```

并确保 `mastery_calibration_check` 所在模块被 Celery 发现（在 `celery.autodiscover_tasks([...])` 或 imports 列表加 `app.tasks.learning_kernel_tasks`）。

- [ ] **Step 5: 跑测试确认通过 + 全套绿**

Run: `PYTHONPATH=. pytest tests/tasks/test_calibration_monitor.py -v && PYTHONPATH=. pytest -q`
Expected: PASS；全套 0 fail。

- [ ] **Step 6: Commit**

```bash
git add app/tasks/learning_kernel_tasks.py app/celery_app.py tests/tasks/test_calibration_monitor.py
git commit -m "feat(kernel): P0-7 mastery calibration monitor (celery beat + ECE alert)"
```

---

## 收尾（P0 全部完成后）

- [ ] **全套回归**：`PYTHONPATH=. pytest -q` 必须 0 fail。
- [ ] **迁移可回滚验证**：`alembic downgrade -1 && alembic upgrade head` 无报错。
- [ ] **更新进度**：在 `知曜学习内核_架构迭代规划.md` 的「进度总览」把 P0 标完成；在 `V3_PRD_FRAMEWORK.md` 新增/更新主线 G 进度。
- [ ] **更新 SPEC.md**（若新增了对前端可见的字段/端点契约）。
- [ ] **同步云盘**：改了知识文档 → `powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\18208\Desktop\知曜创业项目\sync-knowledge-base.ps1"`。
- [ ] **记忆更新**：在 project_zhiyao 记一笔"学习内核 P0 落地（migration 035，measurement/probe service，learning_gain eval，校准 beat）"。

## P0 完成的标志（对齐设计§验收）

能对任一学生任一知识点回答三件事：**①掌握概率多少（p_mastery，已校准）②最近有没有遗忘（effective_mastery 随 R 衰减 + 留存探针）③单位时间学了多少（归一化增益 + 单位时长增益）**——且有校准监控保证这些数字没自欺。这是 P1 图谱、P2 策略脊柱能动工的前提。

## 不在 P0 范围（防 scope creep）

- ❌ 知识图谱 / 先修边 / 根因诊断 / 可学习前沿（P1）
- ❌ learning_engine 决策策略 / agent_service 重构（P2）
- ❌ 增益期望函数 / 交错出题 / PFA 对照（P3）
- ❌ 探针题的"换皮新题生成器"（P0 只打通标记+记录，生成复用现有出题）
- ❌ 前端掌握度地图 / 10 倍仪表盘展示（另起前端设计会话）
