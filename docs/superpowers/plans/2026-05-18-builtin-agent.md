# 知曜内置 AI Agent 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 zhiyao-backend 新增 `POST /v1/agent/chat` 端点，实现 DeepSeek function calling 驱动的 ReAct 循环 agent，具备 8 个语义工具，对话历史存 Redis，最终回答 SSE 流式输出。

**Architecture:** 新增 6 个文件（schema、prompt+工具定义、上下文加载器、工具实现、service、路由），LLMClient 新增两个 tool-capable 方法，router 注册一行。零改动现有 service 逻辑。

**Tech Stack:** FastAPI + AsyncOpenAI（DeepSeek OpenAI-compatible）+ redis.asyncio + StreamingResponse SSE

---

## 文件清单

| 操作 | 路径 |
|------|------|
| 修改 | `app/llm/client.py` — 新增 `call_with_tools()` + `stream_response()` |
| 新建 | `app/schemas/agent.py` — AgentChatRequest schema |
| 新建 | `app/llm/prompts/agent.py` — System Prompt builder + TOOL_DEFINITIONS |
| 新建 | `app/services/agent_context.py` — 用户上下文加载器 |
| 新建 | `app/services/agent_tools.py` — 8 个工具实现 + dispatcher |
| 新建 | `app/services/agent_service.py` — ReAct 主循环 + Redis 历史 |
| 新建 | `app/api/v1/agent.py` — SSE 路由 |
| 修改 | `app/api/v1/__init__.py` — 注册 agent router |

---

## Task 1: 扩展 LLMClient，支持 tool-use 调用

**Files:**
- Modify: `app/llm/client.py`

当前 `LLMClient.generate()` 只做无工具的文字生成。需要新增两个方法：
- `call_with_tools()` — 非流式，带 tools 参数，返回 DeepSeek 原始响应（用于工具调用轮）
- `stream_response()` — 流式，不带 tools，yield token（用于最终回答轮）

- [ ] **Step 1: 在 `app/llm/client.py` 末尾（`llm_client = LLMClient()` 之前）添加两个方法**

在类的最后一个方法 `_call_anthropic` 之后，`llm_client = LLMClient()` 之前，插入：

```python
    async def call_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str = "",
    ):
        """
        带工具定义的非流式调用，仅走 DeepSeek。
        返回 openai ChatCompletion choice 对象（含 finish_reason + message）。
        """
        if not self._deepseek:
            raise RuntimeError("DeepSeek not configured; set DEEPSEEK_API_KEY")
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)
        resp = await self._deepseek.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=full_messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=4096,
            stream=False,
        )
        return resp.choices[0]

    async def stream_response(
        self,
        messages: list[dict],
        system: str = "",
    ):
        """
        流式文字回复（最终回答轮，无工具），yield token 字符串。
        """
        if not self._deepseek:
            raise RuntimeError("DeepSeek not configured; set DEEPSEEK_API_KEY")
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)
        stream = await self._deepseek.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=full_messages,
            max_tokens=4096,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
```

- [ ] **Step 2: 验证 import 正确**

```bash
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
python -c "from app.llm.client import llm_client; print(hasattr(llm_client, 'call_with_tools'), hasattr(llm_client, 'stream_response'))"
```

Expected output: `True True`

- [ ] **Step 3: Commit**

```bash
git add app/llm/client.py
git commit -m "feat(agent): add call_with_tools and stream_response to LLMClient"
```

---

## Task 2: Schema + System Prompt + 工具定义

**Files:**
- Create: `app/schemas/agent.py`
- Create: `app/llm/prompts/agent.py`

- [ ] **Step 1: 创建 `app/schemas/agent.py`**

```python
from pydantic import BaseModel


class AgentChatRequest(BaseModel):
    message: str
    session_id: str | None = None
```

- [ ] **Step 2: 创建 `app/llm/prompts/agent.py`**

```python
"""
知曜内置 Agent 的 System Prompt 构建器和工具定义。
"""
from dataclasses import dataclass


@dataclass
class AgentContext:
    username: str
    grade: str
    subjects: list[str]
    streak_days: int
    done_tasks: int
    total_tasks: int
    upcoming_exam_name: str | None
    days_remaining: int | None
    weakest_subject: str | None
    learning_count: int
    checkin_summary: str | None


_IDENTITY = """你是「知曜」，专属学习管家。
服务对象：中国中高考/大学学生。
性格：温暖、简洁、务实，不废话，不说教。
始终使用中文回复。"""

_RULES = """## 工作规则
1. 需要实时数据时先调工具，不凭猜测回答
2. 分析+规划类任务：先调 diagnose_learning，再调 plan_study_schedule
3. 执行写操作后，用自然语言简洁告知用户做了什么
4. 只处理学习相关请求，其他话题礼貌拒绝并引回学习
5. 回复保持简洁，重点突出"""


def build_system_prompt(ctx: AgentContext) -> str:
    exam_line = (
        f"近期考试：{ctx.upcoming_exam_name}（还有 {ctx.days_remaining} 天）"
        if ctx.upcoming_exam_name
        else "近期考试：暂无"
    )
    subjects_str = "、".join(ctx.subjects) if ctx.subjects else "未设置"
    profile = f"""## 当前用户档案
姓名：{ctx.username}
年级：{ctx.grade}
主攻科目：{subjects_str}
连续学习：{ctx.streak_days} 天
今日任务：{ctx.done_tasks}/{ctx.total_tasks} 项已完成
{exam_line}
最需关注：{ctx.weakest_subject or "暂无数据"}（{ctx.learning_count} 个知识点待掌握）"""

    checkin_block = (
        f"\n## 今日签到\n{ctx.checkin_summary}" if ctx.checkin_summary else ""
    )

    return "\n\n".join([_IDENTITY, profile, _RULES]) + checkin_block


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_full_context",
            "description": "加载用户当前学习快照：KP 各掌握度数量、今日任务列表、近期考试、连续学习天数。需要整体了解用户状态时调用。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diagnose_learning",
            "description": "分析用户学科弱点，返回每科掌握情况、训练均分、错题数、最薄弱章节。制定计划前先调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "指定学科（如'数学'）。不传则分析全部学科。",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_study_schedule",
            "description": "根据弱点和考试压力批量创建学习任务，形成未来 N 天复习计划。",
            "parameters": {
                "type": "object",
                "properties": {
                    "subjects": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "需要规划的学科列表，如 ['数学', '物理']",
                    },
                    "days_ahead": {
                        "type": "integer",
                        "description": "规划天数，默认 7",
                    },
                    "goal": {
                        "type": "string",
                        "description": "备考目标描述，用于任务优先级排序",
                    },
                },
                "required": ["subjects"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_knowledge_points",
            "description": "知识点的查询、批量更新掌握状态、创建新知识点。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "update_mastery", "create"],
                        "description": "list=查询, update_mastery=批量更新掌握度, create=创建新知识点",
                    },
                    "filters": {
                        "type": "object",
                        "description": "list 时的筛选条件：{subject?, mastery_status?, search?}",
                    },
                    "updates": {
                        "type": "object",
                        "description": "update_mastery 时：{kp_ids: string[], new_mastery_status: string}",
                    },
                    "new_kps": {
                        "type": "array",
                        "description": "create 时：[{title, subject, content?, mastery_status?}]",
                        "items": {"type": "object"},
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_tasks",
            "description": "任务的查询、创建、批量创建、完成标记。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list_today", "create", "batch_create", "mark_done"],
                    },
                    "task_data": {
                        "type": "object",
                        "description": "create 时：{title, subject?, estimated_minutes?, due_date?, priority?}",
                    },
                    "tasks": {
                        "type": "array",
                        "description": "batch_create 时的任务列表，每项结构同 task_data",
                        "items": {"type": "object"},
                    },
                    "task_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "mark_done 时的任务 ID 列表",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_training",
            "description": "为用户发起训练练习，自动选取最弱知识点出题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "训练学科，如'数学'"},
                    "question_count": {
                        "type": "integer",
                        "description": "题目数量，默认 5",
                    },
                },
                "required": ["subject"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_exams",
            "description": "考试的查询、创建和倒计时。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "create", "countdown"],
                    },
                    "exam_data": {
                        "type": "object",
                        "description": "create 时：{name, subject?, exam_date (YYYY-MM-DD), notes?}",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_note",
            "description": "触发 AI 笔记生成（异步），用户可在笔记页查看。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "笔记主题，如'导数的定义与计算'"},
                    "subject": {"type": "string", "description": "所属学科"},
                },
                "required": ["topic", "subject"],
            },
        },
    },
]
```

- [ ] **Step 3: 验证导入**

```bash
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
python -c "from app.llm.prompts.agent import build_system_prompt, TOOL_DEFINITIONS, AgentContext; print('tools:', len(TOOL_DEFINITIONS))"
```

Expected output: `tools: 8`

- [ ] **Step 4: Commit**

```bash
git add app/schemas/agent.py app/llm/prompts/agent.py
git commit -m "feat(agent): add schema, system prompt builder and 8 tool definitions"
```

---

## Task 3: 用户上下文加载器

**Files:**
- Create: `app/services/agent_context.py`

从数据库实时拉取用户状态，注入 system prompt。

- [ ] **Step 1: 创建 `app/services/agent_context.py`**

```python
import uuid
import logging
from datetime import date, datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.models.task import DailyTask, PomodoroRecord
from app.models.exam import Exam
from app.models.checkin import CheckIn
from app.llm.prompts.agent import AgentContext

logger = logging.getLogger(__name__)

GRADE_DISPLAY = {
    "junior_1": "初一", "junior_2": "初二", "junior_3": "初三",
    "senior_1": "高一", "senior_2": "高二", "senior_3": "高三",
    "university": "大学",
}


async def load_user_context(db: AsyncSession, user_id: str) -> AgentContext:
    uid = uuid.UUID(user_id)

    # 1. 用户基础信息
    user_row = await db.execute(select(User).where(User.id == uid))
    user = user_row.scalar_one_or_none()
    username = user.username if user else "同学"
    grade_raw = user.grade if user else ""
    grade = GRADE_DISPLAY.get(grade_raw, grade_raw)
    profile = user.learning_profile or {}
    subjects = profile.get("subjects", [])

    # 2. 今日任务统计
    today = date.today()
    task_rows = await db.execute(
        select(DailyTask).where(
            DailyTask.user_id == uid,
            DailyTask.task_date == today,
        )
    )
    today_tasks = task_rows.scalars().all()
    done_tasks = sum(1 for t in today_tasks if t.status == "done")
    total_tasks = len(today_tasks)

    # 3. 连续学习天数（按番茄钟记录逆推）
    streak_days = await _calc_streak(db, uid)

    # 4. 最近一场未来考试
    exam_row = await db.execute(
        select(Exam)
        .where(Exam.user_id == uid, Exam.exam_date >= today)
        .order_by(Exam.exam_date.asc())
        .limit(1)
    )
    exam = exam_row.scalar_one_or_none()
    upcoming_exam_name = exam.name if exam else None
    days_remaining = (exam.exam_date - today).days if exam else None

    # 5. 最弱科目（learning 状态 KP 最多的科目）
    kp_stat = await db.execute(
        select(KnowledgePoint.subject, func.count(KnowledgePoint.id).label("cnt"))
        .where(
            KnowledgePoint.user_id == uid,
            KnowledgePoint.mastery_status == "learning",
            KnowledgePoint.subject.isnot(None),
        )
        .group_by(KnowledgePoint.subject)
        .order_by(func.count(KnowledgePoint.id).desc())
        .limit(1)
    )
    weakest_row = kp_stat.one_or_none()
    weakest_subject = weakest_row[0] if weakest_row else None
    learning_count = weakest_row[1] if weakest_row else 0

    # 6. 今日签到摘要（可选）
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
    checkin_row = await db.execute(
        select(CheckIn)
        .where(CheckIn.user_id == uid, CheckIn.created_at >= today_start)
        .order_by(CheckIn.created_at.desc())
        .limit(1)
    )
    checkin = checkin_row.scalar_one_or_none()
    checkin_summary = checkin.ai_summary if checkin else None

    return AgentContext(
        username=username,
        grade=grade,
        subjects=subjects,
        streak_days=streak_days,
        done_tasks=done_tasks,
        total_tasks=total_tasks,
        upcoming_exam_name=upcoming_exam_name,
        days_remaining=days_remaining,
        weakest_subject=weakest_subject,
        learning_count=learning_count,
        checkin_summary=checkin_summary,
    )


async def _calc_streak(db: AsyncSession, uid: uuid.UUID) -> int:
    """逆推连续学习天数：有番茄钟记录的天数连续多少天"""
    rows = await db.execute(
        select(func.date(PomodoroRecord.started_at).label("d"))
        .where(PomodoroRecord.user_id == uid)
        .distinct()
        .order_by(func.date(PomodoroRecord.started_at).desc())
        .limit(60)
    )
    days = [r[0] for r in rows.all()]
    if not days:
        return 0
    streak = 0
    check = date.today()
    for d in days:
        if d == check:
            streak += 1
            check = check - timedelta(days=1)
        else:
            break
    return streak
```

- [ ] **Step 2: 验证导入**

```bash
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
python -c "from app.services.agent_context import load_user_context; print('OK')"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/services/agent_context.py
git commit -m "feat(agent): add user context loader for system prompt"
```

---

## Task 4: 8 个工具实现 + Dispatcher

**Files:**
- Create: `app/services/agent_tools.py`

每个工具函数接受 `(db, uid, **kwargs)`，返回可 JSON 序列化的 dict。

- [ ] **Step 1: 创建 `app/services/agent_tools.py`**

```python
"""
Agent 工具实现层。每个工具调用现有 service 或直接操作 DB，返回 dict 供 LLM 读取。
"""
import json
import logging
import uuid
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.models.knowledge_point import KnowledgePoint
from app.models.task import DailyTask, PomodoroRecord
from app.models.exam import Exam
from app.models.training import TrainingSession, TrainingQuestion
from app.models.training import TrainingSession, TrainingQuestion

logger = logging.getLogger(__name__)


# ── dispatcher ─────────────────────────────────────────────────────────────

async def dispatch_tool(
    db: AsyncSession,
    user_id: str,
    tool_name: str,
    arguments_json: str,
) -> dict:
    """解析工具名和参数，调用对应实现，返回结果 dict。"""
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        args = {}

    uid = uuid.UUID(user_id)
    handlers = {
        "get_full_context": _get_full_context,
        "diagnose_learning": _diagnose_learning,
        "plan_study_schedule": _plan_study_schedule,
        "manage_knowledge_points": _manage_knowledge_points,
        "manage_tasks": _manage_tasks,
        "start_training": _start_training,
        "manage_exams": _manage_exams,
        "generate_note": _generate_note,
    }
    handler = handlers.get(tool_name)
    if not handler:
        return {"error": f"未知工具: {tool_name}"}
    try:
        return await handler(db, uid, **args)
    except Exception as e:
        logger.warning(f"tool {tool_name} failed: {e}")
        return {"error": str(e)}


# ── 工具 1：get_full_context ────────────────────────────────────────────────

async def _get_full_context(db: AsyncSession, uid: uuid.UUID, **_) -> dict:
    today = date.today()

    # KP 各状态数量
    kp_rows = await db.execute(
        select(KnowledgePoint.mastery_status, func.count(KnowledgePoint.id))
        .where(KnowledgePoint.user_id == uid)
        .group_by(KnowledgePoint.mastery_status)
    )
    kp_dist = {r[0]: r[1] for r in kp_rows.all()}

    # 今日任务
    task_rows = await db.execute(
        select(DailyTask).where(
            DailyTask.user_id == uid,
            DailyTask.task_date == today,
        ).order_by(DailyTask.priority.desc())
    )
    tasks = task_rows.scalars().all()

    # 近期3场考试
    exam_rows = await db.execute(
        select(Exam)
        .where(Exam.user_id == uid, Exam.exam_date >= today)
        .order_by(Exam.exam_date.asc())
        .limit(3)
    )
    exams = exam_rows.scalars().all()

    return {
        "kp_summary": {
            "total": sum(kp_dist.values()),
            "mastered": kp_dist.get("mastered", 0),
            "reviewing": kp_dist.get("reviewing", 0),
            "learning": kp_dist.get("learning", 0),
            "new": kp_dist.get("new", 0),
        },
        "today_tasks": [
            {"id": str(t.id), "title": t.title, "subject": t.subject, "status": t.status, "estimated_minutes": t.estimated_minutes}
            for t in tasks
        ],
        "upcoming_exams": [
            {"name": e.name, "subject": e.subject, "exam_date": str(e.exam_date), "days_remaining": (e.exam_date - today).days}
            for e in exams
        ],
    }


# ── 工具 2：diagnose_learning ───────────────────────────────────────────────

async def _diagnose_learning(db: AsyncSession, uid: uuid.UUID, subject: str | None = None, **_) -> dict:
    # KP 按科目 + 掌握度分布
    q = select(
        KnowledgePoint.subject,
        KnowledgePoint.mastery_status,
        func.count(KnowledgePoint.id),
    ).where(KnowledgePoint.user_id == uid)
    if subject:
        q = q.where(KnowledgePoint.subject == subject)
    q = q.group_by(KnowledgePoint.subject, KnowledgePoint.mastery_status)
    rows = await db.execute(q)

    dist: dict[str, dict] = {}
    for subj, mastery, cnt in rows.all():
        if subj not in dist:
            dist[subj] = {"mastered": 0, "reviewing": 0, "learning": 0, "new": 0}
        dist[subj][mastery] = cnt

    # 训练均分（按科目）
    train_rows = await db.execute(
        select(TrainingSession.subject, func.avg(TrainingSession.avg_score))
        .where(TrainingSession.user_id == uid, TrainingSession.status == "completed")
        .group_by(TrainingSession.subject)
    )
    train_avg = {r[0]: round(float(r[1]), 1) if r[1] else None for r in train_rows.all()}

    # 错题数（TrainingQuestion.is_wrong=True，按科目统计）
    mistake_rows = await db.execute(
        select(KnowledgePoint.subject, func.count(TrainingQuestion.id))
        .join(KnowledgePoint, TrainingQuestion.knowledge_point_id == KnowledgePoint.id)
        .where(TrainingQuestion.user_id == uid, TrainingQuestion.is_wrong == True)
        .group_by(KnowledgePoint.subject)
    )
    mistake_cnt = {r[0]: r[1] for r in mistake_rows.all()}

    report = []
    for subj, mastery_dist in dist.items():
        total = sum(mastery_dist.values())
        report.append({
            "subject": subj,
            "total_kps": total,
            "mastered": mastery_dist.get("mastered", 0),
            "reviewing": mastery_dist.get("reviewing", 0),
            "learning": mastery_dist.get("learning", 0),
            "training_avg_score": train_avg.get(subj),
            "pending_mistakes": mistake_cnt.get(subj, 0),
            "weakness_pct": round(mastery_dist.get("learning", 0) / max(total, 1) * 100, 1),
        })

    report.sort(key=lambda x: x["weakness_pct"], reverse=True)
    return {"diagnosis": report}


# ── 工具 3：plan_study_schedule ─────────────────────────────────────────────

async def _plan_study_schedule(
    db: AsyncSession,
    uid: uuid.UUID,
    subjects: list[str],
    days_ahead: int = 7,
    goal: str = "",
    **_,
) -> dict:
    today = date.today()
    created = []

    for i, subj in enumerate(subjects):
        # 每科安排的任务分布在 days_ahead 天内
        task_date = today + timedelta(days=(i % max(days_ahead, 1)))

        # 找该科最弱 KP（最多取3个名字用于任务标题）
        kp_rows = await db.execute(
            select(KnowledgePoint.name)
            .where(
                KnowledgePoint.user_id == uid,
                KnowledgePoint.subject == subj,
                KnowledgePoint.mastery_status == "learning",
            )
            .limit(3)
        )
        kp_names = [r[0] for r in kp_rows.all()]
        focus = "、".join(kp_names) if kp_names else subj + "复习"
        title = f"【{subj}】复习 {focus}"

        task = DailyTask(
            user_id=uid,
            task_date=task_date,
            title=title,
            task_type="ai_generated",
            subject=subj,
            estimated_minutes=45,
            status="pending",
            priority="high",
            ai_reason=f"根据{goal or '学习计划'}自动安排，{subj}有 {len(kp_names)} 个知识点待强化",
        )
        db.add(task)
        created.append({"title": title, "subject": subj, "date": str(task_date), "estimated_minutes": 45})

    await db.commit()
    return {"created_tasks": created, "total": len(created)}


# ── 工具 4：manage_knowledge_points ────────────────────────────────────────

async def _manage_knowledge_points(
    db: AsyncSession,
    uid: uuid.UUID,
    action: str,
    filters: dict | None = None,
    updates: dict | None = None,
    new_kps: list | None = None,
    **_,
) -> dict:
    filters = filters or {}
    updates = updates or {}
    new_kps = new_kps or []

    if action == "list":
        q = select(KnowledgePoint).where(KnowledgePoint.user_id == uid)
        if filters.get("subject"):
            q = q.where(KnowledgePoint.subject == filters["subject"])
        if filters.get("mastery_status"):
            q = q.where(KnowledgePoint.mastery_status == filters["mastery_status"])
        if filters.get("search"):
            q = q.where(KnowledgePoint.name.ilike(f"%{filters['search']}%"))
        q = q.limit(50)
        rows = await db.execute(q)
        kps = rows.scalars().all()
        return {
            "knowledge_points": [
                {"id": str(k.id), "name": k.name, "subject": k.subject, "mastery_status": k.mastery_status}
                for k in kps
            ]
        }

    if action == "update_mastery":
        kp_ids = [uuid.UUID(kid) for kid in updates.get("kp_ids", [])]
        new_status = updates.get("new_mastery_status", "reviewing")
        if kp_ids and new_status in ("new", "learning", "reviewing", "mastered"):
            for kid in kp_ids:
                row = await db.execute(
                    select(KnowledgePoint).where(
                        KnowledgePoint.id == kid, KnowledgePoint.user_id == uid
                    )
                )
                kp = row.scalar_one_or_none()
                if kp:
                    kp.mastery_status = new_status
            await db.commit()
        return {"updated": len(kp_ids), "new_status": new_status}

    if action == "create":
        created = []
        for item in new_kps:
            name = item.get("title", "").strip() or item.get("name", "").strip()
            if not name:
                continue
            kp = KnowledgePoint(
                user_id=uid,
                name=name,
                subject=item.get("subject"),
                content=item.get("content"),
                mastery_status=item.get("mastery_status", "learning"),
                bloom_level="remember",
            )
            db.add(kp)
            created.append(name)
        await db.commit()
        return {"created": created, "total": len(created)}

    return {"error": f"未知 action: {action}"}


# ── 工具 5：manage_tasks ────────────────────────────────────────────────────

async def _manage_tasks(
    db: AsyncSession,
    uid: uuid.UUID,
    action: str,
    task_data: dict | None = None,
    tasks: list | None = None,
    task_ids: list | None = None,
    **_,
) -> dict:
    task_data = task_data or {}
    tasks = tasks or []
    task_ids = task_ids or []
    today = date.today()

    if action == "list_today":
        rows = await db.execute(
            select(DailyTask)
            .where(DailyTask.user_id == uid, DailyTask.task_date == today)
            .order_by(DailyTask.priority.desc())
        )
        ts = rows.scalars().all()
        return {
            "tasks": [
                {"id": str(t.id), "title": t.title, "subject": t.subject, "status": t.status, "estimated_minutes": t.estimated_minutes}
                for t in ts
            ]
        }

    if action == "create":
        t = DailyTask(
            user_id=uid,
            task_date=today,
            title=task_data.get("title", "新任务"),
            task_type="manual",
            subject=task_data.get("subject"),
            estimated_minutes=task_data.get("estimated_minutes", 30),
            status="pending",
            priority=task_data.get("priority", "medium"),
        )
        db.add(t)
        await db.commit()
        return {"created": {"title": t.title, "subject": t.subject}}

    if action == "batch_create":
        created = []
        for item in tasks:
            t = DailyTask(
                user_id=uid,
                task_date=today,
                title=item.get("title", "新任务"),
                task_type="manual",
                subject=item.get("subject"),
                estimated_minutes=item.get("estimated_minutes", 30),
                status="pending",
                priority=item.get("priority", "medium"),
            )
            db.add(t)
            created.append(item.get("title"))
        await db.commit()
        return {"created": created, "total": len(created)}

    if action == "mark_done":
        done = 0
        for tid in task_ids:
            row = await db.execute(
                select(DailyTask).where(DailyTask.id == uuid.UUID(tid), DailyTask.user_id == uid)
            )
            t = row.scalar_one_or_none()
            if t:
                t.status = "done"
                done += 1
        await db.commit()
        return {"marked_done": done}

    return {"error": f"未知 action: {action}"}


# ── 工具 6：start_training ──────────────────────────────────────────────────

async def _start_training(
    db: AsyncSession,
    uid: uuid.UUID,
    subject: str,
    question_count: int = 5,
    **_,
) -> dict:
    from app.schemas.training import TrainingStartRequest
    from app.services.training_service import training_service

    data = TrainingStartRequest(mode="subject", subject=subject, question_count=min(question_count, 10))
    session = await training_service.start_session(db, str(uid), data)

    q_rows = await db.execute(
        select(TrainingQuestion).where(TrainingQuestion.session_id == session.id)
    )
    questions = q_rows.scalars().all()

    return {
        "session_id": str(session.id),
        "subject": subject,
        "question_count": len(questions),
        "questions": [
            {"id": str(q.id), "content": q.question_text, "bloom_level": q.bloom_level, "type": q.question_type}
            for q in questions
        ],
        "tip": f"训练已生成，共 {len(questions)} 道题。请前往训练页面作答，或告诉我题目答案我来批改。",
    }


# ── 工具 7：manage_exams ────────────────────────────────────────────────────

async def _manage_exams(
    db: AsyncSession,
    uid: uuid.UUID,
    action: str,
    exam_data: dict | None = None,
    **_,
) -> dict:
    exam_data = exam_data or {}
    today = date.today()

    if action == "list":
        rows = await db.execute(
            select(Exam).where(Exam.user_id == uid, Exam.exam_date >= today).order_by(Exam.exam_date.asc())
        )
        exams = rows.scalars().all()
        return {
            "exams": [
                {"name": e.name, "subject": e.subject, "exam_date": str(e.exam_date), "days_remaining": (e.exam_date - today).days}
                for e in exams
            ]
        }

    if action == "create":
        from datetime import date as date_type
        exam_date_str = exam_data.get("exam_date", "")
        try:
            exam_date = date_type.fromisoformat(exam_date_str)
        except ValueError:
            return {"error": f"日期格式无效: {exam_date_str}，请使用 YYYY-MM-DD"}
        exam = Exam(
            user_id=uid,
            name=exam_data.get("name", "考试"),
            subject=exam_data.get("subject"),
            exam_date=exam_date,
            notes=exam_data.get("notes"),
        )
        db.add(exam)
        await db.commit()
        return {"created": {"name": exam.name, "exam_date": str(exam.exam_date), "days_remaining": (exam_date - today).days}}

    if action == "countdown":
        rows = await db.execute(
            select(Exam).where(Exam.user_id == uid, Exam.exam_date >= today).order_by(Exam.exam_date.asc()).limit(5)
        )
        exams = rows.scalars().all()
        return {
            "countdown": [
                {"name": e.name, "days_remaining": (e.exam_date - today).days, "subject": e.subject}
                for e in exams
            ]
        }

    return {"error": f"未知 action: {action}"}


# ── 工具 8：generate_note ───────────────────────────────────────────────────

async def _generate_note(
    db: AsyncSession,
    uid: uuid.UUID,
    topic: str,
    subject: str,
    **_,
) -> dict:
    from app.schemas.note import NoteGenerateRequest
    from app.services.note_service import note_service

    data = NoteGenerateRequest(topic=topic, subject=subject)
    result = await note_service.create_from_ai(db, str(uid), data)
    return {
        "note_id": result["note_id"],
        "status": "generating",
        "message": f"「{topic}」的笔记正在生成中，大约需要 30 秒，请稍后在笔记页查看。",
    }
```

- [ ] **Step 2: 验证导入**

```bash
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
python -c "from app.services.agent_tools import dispatch_tool; print('OK')"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/services/agent_tools.py
git commit -m "feat(agent): implement 8 semantic tools with dispatcher"
```

---

## Task 5: Agent Service（ReAct 主循环 + Redis 历史）

**Files:**
- Create: `app/services/agent_service.py`

- [ ] **Step 1: 创建 `app/services/agent_service.py`**

```python
"""
Agent 主循环：ReAct 模式，最多 5 轮工具调用，最终流式输出。
对话历史存 Redis（TTL 24h，最多保留 20 条消息）。
"""
import json
import logging
import uuid
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.llm.client import llm_client
from app.llm.prompts.agent import build_system_prompt, TOOL_DEFINITIONS
from app.services.agent_context import load_user_context
from app.services.agent_tools import dispatch_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5
MAX_HISTORY_MESSAGES = 20
SESSION_TTL = 86400  # 24h


def _session_key(session_id: str) -> str:
    return f"agent_session:{session_id}"


async def load_history(session_id: str) -> list[dict]:
    redis = await get_redis()
    raw = await redis.get(_session_key(session_id))
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


async def save_history(session_id: str, messages: list[dict]) -> None:
    if len(messages) > MAX_HISTORY_MESSAGES:
        messages = messages[-MAX_HISTORY_MESSAGES:]
    redis = await get_redis()
    await redis.setex(_session_key(session_id), SESSION_TTL, json.dumps(messages, ensure_ascii=False))


def _serialize_message(msg) -> dict:
    """把 openai SDK message 对象转为可 JSON 序列化的 dict。"""
    if hasattr(msg, "model_dump"):
        d = msg.model_dump()
        # tool_calls 里的 function.arguments 已经是字符串，不需要额外处理
        return d
    return msg  # 已经是 dict（tool result 消息）


async def run(
    db: AsyncSession,
    user_id: str,
    message: str,
    session_id: str | None,
) -> AsyncGenerator[str, None]:
    """
    主 agent 循环，yield SSE data 行。
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    # 1. 加载上下文 + 历史
    ctx = await load_user_context(db, user_id)
    system = build_system_prompt(ctx)
    history = await load_history(session_id)
    history.append({"role": "user", "content": message})

    tools_called: list[str] = []

    # 2. 工具调用轮（最多 MAX_TOOL_ROUNDS 次）
    for _ in range(MAX_TOOL_ROUNDS):
        try:
            choice = await llm_client.call_with_tools(
                messages=history,
                tools=TOOL_DEFINITIONS,
                system=system,
            )
        except Exception as e:
            logger.error(f"DeepSeek tool call failed: {e}")
            break

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            tc = choice.message.tool_calls[0]
            tool_name = tc.function.name
            tools_called.append(tool_name)

            yield f'data: {json.dumps({"thinking": f"正在执行：{tool_name}…"}, ensure_ascii=False)}\n\n'

            result = await dispatch_tool(db, user_id, tool_name, tc.function.arguments)

            # 追加 assistant 消息（含 tool_calls）
            history.append(_serialize_message(choice.message))
            # 追加 tool 结果消息
            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
        else:
            # LLM 决定直接回答，退出工具循环
            break

    # 3. 最终回答轮（流式）
    full_reply = ""
    try:
        async for token in llm_client.stream_response(messages=history, system=system):
            full_reply += token
            escaped = token.replace('"', '\\"').replace('\n', '\\n')
            yield f'data: {{"delta": "{escaped}"}}\n\n'
    except Exception as e:
        logger.error(f"DeepSeek stream failed: {e}")
        error_msg = "抱歉，回复生成时遇到问题，请重试。"
        full_reply = error_msg
        yield f'data: {json.dumps({"delta": error_msg}, ensure_ascii=False)}\n\n'

    # 4. done 事件
    yield f'data: {json.dumps({"done": True, "session_id": session_id, "tools_called": tools_called}, ensure_ascii=False)}\n\n'

    # 5. 持久化对话历史
    history.append({"role": "assistant", "content": full_reply})
    try:
        await save_history(session_id, history)
    except Exception as e:
        logger.warning(f"Failed to save history: {e}")
```

- [ ] **Step 2: 验证导入**

```bash
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
python -c "from app.services.agent_service import run, load_history, save_history; print('OK')"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/services/agent_service.py
git commit -m "feat(agent): implement ReAct loop with Redis session history"
```

---

## Task 6: SSE 路由 + Router 注册

**Files:**
- Create: `app/api/v1/agent.py`
- Modify: `app/api/v1/__init__.py`

- [ ] **Step 1: 创建 `app/api/v1/agent.py`**

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.agent import AgentChatRequest
from app.services.agent_service import run

router = APIRouter(prefix="/agent", tags=["AI 管家 Agent"])


@router.post("/chat", summary="向 AI 管家发送消息（SSE 流式响应）")
async def agent_chat(
    body: AgentChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    async def event_stream():
        async for chunk in run(db, str(user.id), body.message, body.session_id):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 2: 在 `app/api/v1/__init__.py` 注册 router**

将文件内容替换为：

```python
from fastapi import APIRouter
from app.api.v1 import auth, notes, knowledge_points, flashcards, training, mistakes, tasks, progress, guidance, path, profile, exams, onboarding, checkin, agent

router = APIRouter(prefix="/v1")
router.include_router(auth.router)
router.include_router(notes.router)
router.include_router(knowledge_points.router)
router.include_router(flashcards.router)
router.include_router(training.router)
router.include_router(mistakes.router)
router.include_router(tasks.router)
router.include_router(progress.router)
router.include_router(guidance.router)
router.include_router(path.router)
router.include_router(profile.router)
router.include_router(exams.router)
router.include_router(onboarding.router)
router.include_router(checkin.router)
router.include_router(agent.router)
```

- [ ] **Step 3: 验证所有路由可以 import**

```bash
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
python -c "from app.api.v1 import router; print('all routers OK')"
```

Expected output: `all routers OK`

- [ ] **Step 4: 验证 /v1/agent/chat 出现在 OpenAPI**

重启 uvicorn（或让 reload 触发），然后：

```powershell
(Invoke-WebRequest -Uri "http://localhost:8000/openapi.json" -UseBasicParsing).Content | ConvertFrom-Json | Select-Object -ExpandProperty paths | Get-Member -MemberType NoteProperty | Where-Object { $_.Name -like "*agent*" }
```

Expected output: 包含 `/v1/agent/chat`

- [ ] **Step 5: Commit**

```bash
git add app/api/v1/agent.py app/api/v1/__init__.py
git commit -m "feat(agent): add SSE route POST /v1/agent/chat and register router"
```

---

## Task 7: SPEC 更新 + E2E 冒烟验证 + Push

**Files:**
- Modify: `C:\Users\18208\Desktop\知曜创业项目\SPEC.md` — 新增 Section 2.15

- [ ] **Step 1: 在 SPEC.md Section 2.14 之后插入 Section 2.15**

```markdown
### 2.15 AI 管家 Agent 模块 `/v1/agent`

> 内置 AI Agent：DeepSeek function calling 驱动的 ReAct 循环，8 个语义工具，对话历史存 Redis（TTL 24h）。

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | `/agent/chat` | 向 AI 管家发送消息，SSE 流式响应 | ✅ |

**AgentChatRequest（请求体）：**
```json
{ "message": "帮我安排本周数学复习", "session_id": "optional-uuid" }
```

**SSE 响应格式（text/event-stream）：**
```
data: {"thinking": "正在执行：diagnose_learning…"}
data: {"delta": "根据你当前的学习状态"}
data: {"delta": "，数学有 12 个知识点未掌握"}
data: {"done": true, "session_id": "xxx-uuid", "tools_called": ["diagnose_learning", "plan_study_schedule"]}
```

**session_id：** 首次不传，服务端生成并在 done 事件返回；下轮对话带上实现多轮上下文。
**tools_called：** 本轮实际调用的工具名列表，供前端显示"管家做了什么"。

**8 个工具能力：**
| 工具 | 典型触发语句 |
|------|-------------|
| `get_full_context` | "我现在状态怎么样" |
| `diagnose_learning` | "我哪科最弱" |
| `plan_study_schedule` | "帮我安排本周复习" |
| `manage_knowledge_points` | "把数学二次函数标成已掌握" |
| `manage_tasks` | "帮我加个任务：背英语单词" |
| `start_training` | "出5道物理题考我" |
| `manage_exams` | "下周有期末，帮我记一下" |
| `generate_note` | "帮我生成导数的笔记" |
```

- [ ] **Step 2: E2E 冒烟验证**

先获取 token（用真实注册账号）：

```powershell
$body = '{"email":"your@email.com","password":"yourpassword"}'
$resp = Invoke-WebRequest -Uri "http://localhost:8000/v1/auth/login" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
$token = ($resp.Content | ConvertFrom-Json).data.access_token
```

发送 agent 请求并读取 SSE 流：

```powershell
$headers = @{ "Authorization" = "Bearer $token"; "Content-Type" = "application/json" }
$body2 = '{"message":"你好，我今天想复习一下"}'
Invoke-WebRequest -Uri "http://localhost:8000/v1/agent/chat" -Method POST -Headers $headers -Body $body2 -UseBasicParsing | Select-Object -ExpandProperty Content
```

Expected: 响应包含 `data: {"delta":` 和 `data: {"done": true` 字段。HTTP 200，Content-Type 包含 `text/event-stream`。

- [ ] **Step 3: 验证工具实际执行（查 DB）**

发送 `"帮我加个任务：测试管家功能"` → 然后查 DB 确认任务创建：

```powershell
$body3 = '{"message":"帮我加个任务：测试管家功能"}'
Invoke-WebRequest -Uri "http://localhost:8000/v1/agent/chat" -Method POST -Headers $headers -Body $body3 -UseBasicParsing | Select-Object -ExpandProperty Content
```

随后调 `/v1/tasks/today` 验证任务存在。

- [ ] **Step 4: 提交 SPEC + Push**

```bash
cd "C:\Users\18208\Desktop\知曜创业项目"
git add SPEC.md
git commit -m "docs: add Section 2.15 for agent module"

cd zhiyao-backend
git push origin main
```

---

## 验收清单

- [ ] `python -c "from app.api.v1 import router"` 无报错
- [ ] OpenAPI 包含 `/v1/agent/chat`
- [ ] SSE 响应格式正确（thinking → delta → done）
- [ ] 工具调用后 DB 实际变更（任务/KP 被创建/更新）
- [ ] 5 轮工具上限不死循环
- [ ] Redis 断连时不 500（graceful fallback）
- [ ] 多轮对话：第二条消息能读到第一轮历史
