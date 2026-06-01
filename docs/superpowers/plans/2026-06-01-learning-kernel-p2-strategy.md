# 学习内核 P2 策略脊柱 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把"做什么"的决策权从 LLM 收归到确定性 `learning_engine`：引擎按优先级选动作，LLM 只负责执行和发声；feature flag 可一键回退旧 ReAct。

**Architecture:** 新增 `learning_engine.py`（纯函数策略）和 `learning_intent.py`（意图分类），在 `agent_service.py` 插入引擎分支——意图是"学习推进"时，引擎决策 → 直接 dispatch 工具 → LLM 格式化回复；自由聊天/答疑路径保持 ReAct 不变。Feature flag `LEARNING_ENGINE_ENABLED`（默认 True）可一键回退。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy async · pytest-asyncio · 现有 `learner_state_service`（P1 产出，已 156 pass）

---

## 文件总览

| 操作 | 路径 | 职责 |
|------|------|------|
| 创建 | `app/services/learning_engine.py` | 纯函数：策略/难度/工具适配 (G-P2-1~6) |
| 创建 | `app/services/learning_intent.py` | 纯函数：学习推进意图分类 (G-P2-4) |
| 创建 | `app/api/v1/learning_engine.py` | GET /v1/learning/recommended-actions (G-P2-7) |
| 创建 | `tests/unit/test_learning_engine.py` | 策略单元测试 |
| 创建 | `tests/unit/test_learning_intent.py` | 意图分类单元测试 |
| 创建 | `tests/unit/test_agent_engine_branch.py` | agent_service 引擎分支测试 |
| 修改 | `app/config.py` | 加 LEARNING_ENGINE_ENABLED flag |
| 修改 | `app/services/agent_service.py` | 插入引擎分支 + done 事件加 decision 字段 |
| 修改 | `app/main.py` | 注册新路由 |

---

## Task 1: `learning_engine.py` 核心策略（G-P2-1, G-P2-6）

**Files:**
- Create: `app/services/learning_engine.py`
- Create: `tests/unit/test_learning_engine.py`

- [ ] **Step 1: 写失败测试（策略推荐）**

```python
# tests/unit/test_learning_engine.py
import pytest
from app.services.learning_engine import (
    recommend_actions, ActionType, RecommendedAction,
)


def _state(due=0, frontier=None, streak=0):
    return {
        "review_due": {"due": due},
        "knowledge_graph": {
            "total": 5, "mastered": 2, "learning": 3,
            "frontier": frontier or [],
        },
        "exams": {"next": None, "stress_level": "low"},
        "streak": streak,
    }


# ── 优先级顺序 ──

def test_due_flashcards_first():
    """到期闪卡 → 最高优先级（G-P2-1 优先级 1）"""
    acts = recommend_actions(_state(due=3))
    assert acts[0].action_type == ActionType.REVIEW_FLASHCARD
    assert "3" in acts[0].reason


def test_weak_frontier_fill_prerequisite():
    """前沿节点 p_mastery < 0.3 → FILL_PREREQUISITE（G-P2-1 优先级 2）"""
    frontier = [{"id": "kp1", "name": "极限", "p_mastery": 0.1}]
    acts = recommend_actions(_state(due=0, frontier=frontier))
    assert acts[0].action_type == ActionType.FILL_PREREQUISITE
    assert acts[0].params["kp_id"] == "kp1"
    assert "极限" in acts[0].reason


def test_due_before_fill_prerequisite():
    """到期复习 > 根因补漏"""
    frontier = [{"id": "kp1", "name": "极限", "p_mastery": 0.1}]
    types = [a.action_type for a in recommend_actions(_state(due=2, frontier=frontier))]
    assert types.index(ActionType.REVIEW_FLASHCARD) < types.index(ActionType.FILL_PREREQUISITE)


def test_healthy_frontier_explore():
    """前沿节点 p_mastery >= 0.3 → EXPLORE_FRONTIER（G-P2-1 优先级 3）"""
    frontier = [{"id": "kp2", "name": "导数", "p_mastery": 0.45}]
    types = [a.action_type for a in recommend_actions(_state(due=0, frontier=frontier))]
    assert ActionType.EXPLORE_FRONTIER in types
    assert ActionType.FILL_PREREQUISITE not in types


def test_practice_always_present():
    """PRACTICE（做题/回忆）总是在队列中（G-P2-3 提取优先）"""
    acts = recommend_actions(_state(due=0))
    assert any(a.action_type == ActionType.PRACTICE for a in acts)


def test_fill_before_explore():
    """弱节点(p<0.3) 在队列中先于 EXPLORE"""
    frontier = [
        {"id": "k1", "name": "极限", "p_mastery": 0.1},   # 弱
        {"id": "k2", "name": "导数", "p_mastery": 0.45},   # 就绪
    ]
    types = [a.action_type for a in recommend_actions(_state(due=0, frontier=frontier))]
    assert types.index(ActionType.FILL_PREREQUISITE) < types.index(ActionType.EXPLORE_FRONTIER)


# ── 兜底（G-P2-6）──

def test_fallback_empty_state():
    """完全空 state → 仍返回非空动作列表"""
    empty = {"review_due": {}, "knowledge_graph": {"frontier": []}, "exams": {}, "streak": 0}
    acts = recommend_actions(empty)
    assert len(acts) >= 1


def test_fallback_includes_practice():
    """兜底：无 KP 无复习 → 至少有 PRACTICE"""
    empty = {"review_due": {}, "knowledge_graph": {"frontier": []}, "exams": {}, "streak": 0}
    types = [a.action_type for a in recommend_actions(empty)]
    assert ActionType.PRACTICE in types
```

- [ ] **Step 2: 跑测试，确认全部 FAIL**

```powershell
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
python -m pytest tests/unit/test_learning_engine.py -v 2>&1 | head -30
```

预期：`ModuleNotFoundError: No module named 'app.services.learning_engine'`

- [ ] **Step 3: 实现 `learning_engine.py`**

```python
# app/services/learning_engine.py
"""学习内核 P2 · 策略脊柱（learning_engine）。

确定性优先级策略，把"做什么"的决策权从 LLM 收归到引擎。
纯函数，零 DB、零 IO，便于 TDD。
设计见《知曜学习内核_设计.md》§3.2。

优先级（高 → 低）：
  1. REVIEW_FLASHCARD  — FSRS 到期复习
  2. FILL_PREREQUISITE — 根因补漏（先修 p_mastery < WEAK_THRESHOLD）
  3. EXPLORE_FRONTIER  — 前沿新点（先修就绪）
  4. PRACTICE          — 做题/回忆（M4 提取优先）
  5. EXPAND            — 拓展阅读（被 PRACTICE 排后）

兜底（G-P2-6）：state 不全/策略给不出 → FSRS 到期 + 前沿新点，绝不空转。
"""
from __future__ import annotations

from dataclasses import dataclass, field


class ActionType:
    REVIEW_FLASHCARD = "review_flashcard"
    FILL_PREREQUISITE = "fill_prerequisite"
    EXPLORE_FRONTIER = "explore_frontier"
    PRACTICE = "practice"
    EXPAND = "expand"


@dataclass
class RecommendedAction:
    action_type: str
    reason: str
    params: dict = field(default_factory=dict)
    priority: int = 0  # 数字越小优先级越高


_WEAK_THRESHOLD = 0.3
_DIFFICULTY_TIERS = ("blue", "purple", "gold")


# ─── 主策略（G-P2-1）────────────────────────────────────────────────────────


def recommend_actions(learner_state: dict) -> list[RecommendedAction]:
    """给定学习者状态，返回有序动作队列（纯函数，不含 DB）。"""
    actions: list[RecommendedAction] = []

    # 1 FSRS 到期复习
    due_count = learner_state.get("review_due", {}).get("due", 0)
    if due_count > 0:
        actions.append(RecommendedAction(
            action_type=ActionType.REVIEW_FLASHCARD,
            reason=f"你有 {due_count} 张闪卡到期，现在复习可强化记忆",
            params={"due_count": due_count},
            priority=1,
        ))

    # 2 根因补漏（弱节点 p_mastery < WEAK_THRESHOLD）
    frontier = learner_state.get("knowledge_graph", {}).get("frontier", [])
    weak = [n for n in frontier if n.get("p_mastery", 0.0) < _WEAK_THRESHOLD]
    if weak:
        target = min(weak, key=lambda n: n.get("p_mastery", 0.0))
        actions.append(RecommendedAction(
            action_type=ActionType.FILL_PREREQUISITE,
            reason=f"建议先巩固「{target.get('name', '')}」（掌握度 {target.get('p_mastery', 0):.0%}），这是后续知识的地基",
            params={"kp_id": target.get("id", ""), "kp_name": target.get("name", "")},
            priority=2,
        ))

    # 3 前沿新点（先修就绪，自身未掌握）
    non_weak = [n for n in frontier if n.get("p_mastery", 0.0) >= _WEAK_THRESHOLD]
    if non_weak:
        target = non_weak[0]  # frontier 已按 p_mastery 升序
        actions.append(RecommendedAction(
            action_type=ActionType.EXPLORE_FRONTIER,
            reason=f"推荐学习「{target.get('name', '')}」，你的先修知识已就绪",
            params={"kp_id": target.get("id", ""), "kp_name": target.get("name", "")},
            priority=3,
        ))

    # 4 提取练习（M4：做题 > 重读；EXPAND 若存在会被 _apply_retrieval_preference 排后）
    actions.append(RecommendedAction(
        action_type=ActionType.PRACTICE,
        reason="做一组练习题，用提取练习强化已学内容",
        params={},
        priority=4,
    ))

    # 仅有 PRACTICE 说明 state 为空 → 走兜底
    if len(actions) == 1 and actions[0].action_type == ActionType.PRACTICE:
        actions = _fallback_actions(learner_state)

    _apply_retrieval_preference(actions)
    return sorted(actions, key=lambda a: a.priority)


# ─── 兜底（G-P2-6）──────────────────────────────────────────────────────────


def _fallback_actions(learner_state: dict) -> list[RecommendedAction]:
    """state 不全时：FSRS 到期 + 前沿新点；都没有则 PRACTICE。"""
    actions: list[RecommendedAction] = []
    due = learner_state.get("review_due", {}).get("due", 0)
    if due > 0:
        actions.append(RecommendedAction(
            action_type=ActionType.REVIEW_FLASHCARD,
            reason=f"（兜底）{due} 张到期闪卡，建议复习",
            params={"due_count": due},
            priority=1,
        ))
    frontier = learner_state.get("knowledge_graph", {}).get("frontier", [])
    if frontier:
        t = frontier[0]
        actions.append(RecommendedAction(
            action_type=ActionType.EXPLORE_FRONTIER,
            reason=f"（兜底）学习前沿知识点「{t.get('name', '')}」",
            params={"kp_id": t.get("id", ""), "kp_name": t.get("name", "")},
            priority=3,
        ))
    if not actions:
        actions.append(RecommendedAction(
            action_type=ActionType.PRACTICE,
            reason="（兜底）开始一组练习",
            params={},
            priority=4,
        ))
    return actions


# ─── 难度选择（G-P2-2）──────────────────────────────────────────────────────


def select_difficulty(correct_rate: float | None, *, current_tier: str = "blue") -> dict:
    """答对率硬规则难度调整（G-P2-2）。

    Returns {"tier": str, "should_fallback_to_prereq": bool}
    - correct_rate > 0.9  → 升一档
    - correct_rate < 0.8  → 降一档；已在 blue → should_fallback_to_prereq=True
    - 0.8–0.9 或 None     → 不变
    """
    if correct_rate is None:
        return {"tier": current_tier, "should_fallback_to_prereq": False}
    idx = _DIFFICULTY_TIERS.index(current_tier) if current_tier in _DIFFICULTY_TIERS else 0
    if correct_rate > 0.9:
        return {"tier": _DIFFICULTY_TIERS[min(idx + 1, len(_DIFFICULTY_TIERS) - 1)],
                "should_fallback_to_prereq": False}
    if correct_rate < 0.8:
        if idx == 0:
            return {"tier": "blue", "should_fallback_to_prereq": True}
        return {"tier": _DIFFICULTY_TIERS[idx - 1], "should_fallback_to_prereq": False}
    return {"tier": current_tier, "should_fallback_to_prereq": False}


# ─── 提取优先规则（G-P2-3）──────────────────────────────────────────────────


def _apply_retrieval_preference(actions: list[RecommendedAction]) -> None:
    """同等情况 PRACTICE（做题/回忆）优先于 EXPAND（再读讲义）。就地修改。"""
    practice = next((a for a in actions if a.action_type == ActionType.PRACTICE), None)
    expand = next((a for a in actions if a.action_type == ActionType.EXPAND), None)
    if practice and expand and expand.priority < practice.priority:
        practice.priority, expand.priority = expand.priority, practice.priority


# ─── 工具适配器（G-P2-5）────────────────────────────────────────────────────


def action_to_tool_call(action: RecommendedAction) -> tuple[str, dict]:
    """把引擎动作映射到 (tool_name, args_dict)，供 agent_service 直接 dispatch。

    绕过 LLM 自由选工具——引擎决策，LLM 执行。
    """
    t = action.action_type
    if t == ActionType.REVIEW_FLASHCARD:
        # FSRS 复习走前端 /v1/flashcards/due；Agent 设为 remind 状态引导用户
        return ("set_agent_state", {"state": "remind", "context": "review_flashcard"})
    if t in (ActionType.FILL_PREREQUISITE, ActionType.EXPLORE_FRONTIER):
        kp_id = action.params.get("kp_id", "")
        kp_name = action.params.get("kp_name", "")
        return ("start_training", {
            "knowledge_point_ids": [kp_id] if kp_id else [],
            "difficulty_tiers": ["blue"],
            "question_count": 5,
            "note": kp_name,
        })
    if t == ActionType.PRACTICE:
        return ("start_training", {"question_count": 10, "difficulty_tiers": ["blue", "purple"]})
    # EXPAND → 让 LLM 获取上下文后自由回复
    return ("get_full_context", {})
```

- [ ] **Step 4: 跑测试，确认全部 PASS**

```powershell
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
python -m pytest tests/unit/test_learning_engine.py -v
```

预期：全部 PASS（8 个 test_）

- [ ] **Step 5: Commit**

```powershell
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
git add app/services/learning_engine.py tests/unit/test_learning_engine.py
git commit -m "feat(kernel): P2-1 learning_engine pure strategy (priority/difficulty/retrieval-pref/tool-adapter)"
```

---

## Task 2: 难度选择 + 提取优先单测（G-P2-2, G-P2-3）

**Files:**
- Modify: `tests/unit/test_learning_engine.py`（追加测试类）

- [ ] **Step 1: 追加难度和提取优先测试**

在 `tests/unit/test_learning_engine.py` 末尾追加：

```python
# ── 追加到 tests/unit/test_learning_engine.py ──

from app.services.learning_engine import (
    select_difficulty, _apply_retrieval_preference, action_to_tool_call,
)


class TestSelectDifficulty:
    def test_high_correct_rate_upgrades_tier(self):
        r = select_difficulty(0.95, current_tier="blue")
        assert r["tier"] == "purple"
        assert r["should_fallback_to_prereq"] is False

    def test_cannot_upgrade_beyond_gold(self):
        r = select_difficulty(0.95, current_tier="gold")
        assert r["tier"] == "gold"

    def test_low_rate_downgrades_tier(self):
        r = select_difficulty(0.75, current_tier="purple")
        assert r["tier"] == "blue"
        assert r["should_fallback_to_prereq"] is False

    def test_low_rate_at_blue_flags_prereq_fallback(self):
        r = select_difficulty(0.75, current_tier="blue")
        assert r["tier"] == "blue"
        assert r["should_fallback_to_prereq"] is True

    def test_mid_range_rate_no_change(self):
        r = select_difficulty(0.85, current_tier="purple")
        assert r["tier"] == "purple"
        assert r["should_fallback_to_prereq"] is False

    def test_none_correct_rate_no_change(self):
        r = select_difficulty(None, current_tier="gold")
        assert r["tier"] == "gold"
        assert r["should_fallback_to_prereq"] is False


class TestRetrievalPreference:
    def test_practice_beats_expand_when_expand_has_lower_priority_num(self):
        actions = [
            RecommendedAction(action_type=ActionType.EXPAND, reason="x", priority=2),
            RecommendedAction(action_type=ActionType.PRACTICE, reason="y", priority=4),
        ]
        _apply_retrieval_preference(actions)
        sorted_acts = sorted(actions, key=lambda a: a.priority)
        types = [a.action_type for a in sorted_acts]
        assert types.index(ActionType.PRACTICE) < types.index(ActionType.EXPAND)

    def test_no_expand_in_list_is_noop(self):
        actions = [
            RecommendedAction(action_type=ActionType.PRACTICE, reason="y", priority=4),
        ]
        _apply_retrieval_preference(actions)  # must not raise
        assert actions[0].priority == 4


class TestActionToToolCall:
    def test_review_flashcard_routes_to_set_agent_state(self):
        a = RecommendedAction(ActionType.REVIEW_FLASHCARD, "复习", params={"due_count": 2})
        tool, args = action_to_tool_call(a)
        assert tool == "set_agent_state"
        assert args["state"] == "remind"

    def test_fill_prerequisite_routes_to_start_training(self):
        a = RecommendedAction(ActionType.FILL_PREREQUISITE, "补漏",
                              params={"kp_id": "abc-123", "kp_name": "极限"})
        tool, args = action_to_tool_call(a)
        assert tool == "start_training"
        assert "abc-123" in args["knowledge_point_ids"]
        assert args["difficulty_tiers"] == ["blue"]

    def test_explore_frontier_routes_to_start_training(self):
        a = RecommendedAction(ActionType.EXPLORE_FRONTIER, "探索",
                              params={"kp_id": "xyz", "kp_name": "导数"})
        tool, args = action_to_tool_call(a)
        assert tool == "start_training"

    def test_practice_routes_to_start_training(self):
        a = RecommendedAction(ActionType.PRACTICE, "练习", params={})
        tool, args = action_to_tool_call(a)
        assert tool == "start_training"
        assert args["question_count"] == 10
```

- [ ] **Step 2: 跑全套测试，确认 PASS**

```powershell
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
python -m pytest tests/unit/test_learning_engine.py -v
```

预期：全部 PASS（~14 个测试）

- [ ] **Step 3: Commit**

```powershell
git add tests/unit/test_learning_engine.py
git commit -m "test(kernel): P2-2/3 difficulty selector + retrieval preference tests"
```

---

## Task 3: 意图分类器（G-P2-4 前置）

**Files:**
- Create: `app/services/learning_intent.py`
- Create: `tests/unit/test_learning_intent.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_learning_intent.py
from app.services.learning_intent import classify_learning_intent


def test_explicit_start_learning():
    assert classify_learning_intent("帮我学高数") is True


def test_review_trigger():
    assert classify_learning_intent("复习今天的内容") is True


def test_do_practice_trigger():
    assert classify_learning_intent("给我出几道练习题") is True


def test_quiz_trigger():
    assert classify_learning_intent("测一测我的掌握情况") is True


def test_arrangement_trigger():
    assert classify_learning_intent("今天该学什么") is True


def test_greeting_not_learning():
    assert classify_learning_intent("你好") is False


def test_explain_question_not_learning():
    assert classify_learning_intent("什么是微分？") is False


def test_why_question_not_learning():
    assert classify_learning_intent("为什么要学导数") is False


def test_empty_message_not_learning():
    assert classify_learning_intent("") is False
```

- [ ] **Step 2: 跑测试，确认 FAIL**

```powershell
python -m pytest tests/unit/test_learning_intent.py -v 2>&1 | head -20
```

预期：`ModuleNotFoundError`

- [ ] **Step 3: 实现 `learning_intent.py`**

```python
# app/services/learning_intent.py
"""学习推进意图分类器（G-P2-4 前置）。

规则：关键词快速 path（覆盖 ~80% 常见学习推进指令）。
保守策略：不确定时返回 False（保持旧 ReAct 行为），避免误分类破坏自由对话。
"""
from __future__ import annotations

import re

# 自由聊天/答疑模式——优先级更高，命中则直接返回 False
_CHAT_PATTERNS = [
    r"^\s*(你好|hi|hello|嗨|哈喽)",
    r"(?:是什么|什么是|怎么理解|解释一下)",
    r"(?:为什么|原因|原理|怎么证明)",
    r"帮我.*(?:写|翻译|查|找)",   # 写作/查询类，非学习推进
]

# 学习推进触发词——明确请求 Agent 执行学习动作
_LEARNING_PATTERNS = [
    r"帮.*(?:我|我学|安排).*学",
    r"开始.*学习",
    r"安排.*学习",
    r"今天.*(?:学什么|学哪|该学)",
    r"该.*学(?:什么|哪)",
    r"推荐.*学",
    r"学习.*计划",
    r"(?:开始|做|来|出).*复习",
    r"复习",
    r"(?:出|做|给我|来几道).*(?:练习题|题目|习题|训练)",
    r"刷题",
    r"测(?:一测|测|试)",
    r"检测.*掌握",
    r"背单词",
    r"闪卡.*复习",
    r"记忆.*卡",
]


def classify_learning_intent(message: str) -> bool:
    """返回 True 表示"学习推进"意图（引擎驱动），False 保持 ReAct。"""
    if not message or not message.strip():
        return False
    for pat in _CHAT_PATTERNS:
        if re.search(pat, message, re.IGNORECASE):
            return False
    for pat in _LEARNING_PATTERNS:
        if re.search(pat, message):
            return True
    return False
```

- [ ] **Step 4: 跑测试，确认全部 PASS**

```powershell
python -m pytest tests/unit/test_learning_intent.py -v
```

预期：全部 PASS（9 个测试）

- [ ] **Step 5: Commit**

```powershell
git add app/services/learning_intent.py tests/unit/test_learning_intent.py
git commit -m "feat(kernel): P2-4a learning_intent classifier (keyword-based, conservative)"
```

---

## Task 4: Feature Flag + agent_service 引擎分支（G-P2-4）

**Files:**
- Modify: `app/config.py`
- Modify: `app/services/agent_service.py`
- Create: `tests/unit/test_agent_engine_branch.py`

- [ ] **Step 1: 写失败测试（agent_service 引擎分支）**

```python
# tests/unit/test_agent_engine_branch.py
"""G-P2-4: agent_service 引擎驱动分支测试。

验证：意图 = 学习推进 + engine enabled → 引擎选动作 → dispatch 工具 → done 带 decision 字段。
复用 test_agent_sources.py 的 monkeypatch 模式。
"""
import json
import uuid

import pytest


class _FakeMsg:
    content = "好的，为你安排了练习。"
    tool_calls = None

    def model_dump(self):
        return {}


class _FakeChoice:
    finish_reason = "stop"
    message = _FakeMsg()


def _base_patches(monkeypatch):
    """patch 所有与本测试无关的外部依赖。"""
    from app.services import agent_service
    from app.llm.prompts.agent import AgentContext

    async def fake_search(db, **kw):
        return []

    monkeypatch.setattr("app.services.rag_service.search", fake_search)

    async def fake_audit(*a, **k):
        return {"safe": True}

    monkeypatch.setattr("app.services.content_safety_service.audit_text", fake_audit)

    async def fake_ctx(db, user_id):
        return AgentContext(
            username="测试", grade="senior_1", subjects=["math"], streak_days=0,
            done_tasks=0, total_tasks=0, upcoming_exam_name=None, days_remaining=None,
            weakest_subject=None, learning_count=0, checkin_summary=None,
        )

    monkeypatch.setattr("app.services.agent_service.load_user_context", fake_ctx)

    async def fake_eps(db, **kw):
        return []

    monkeypatch.setattr("app.services.episodic_memory_service.retrieve_relevant", fake_eps)

    async def fake_classify(db, user_id, message):
        return ("simple", "")

    monkeypatch.setattr("app.services.planner_service.classify_complexity", fake_classify)

    async def fake_call_with_tools(**kw):
        return _FakeChoice()

    monkeypatch.setattr(agent_service.llm_client, "call_with_tools", fake_call_with_tools)

    async def fake_stream(**kw):
        for t in ["好", "的"]:
            yield t

    monkeypatch.setattr(agent_service.llm_client, "stream_response", fake_stream)

    async def fake_tts(*a, **k):
        return None

    monkeypatch.setattr("app.services.tts_service.synthesize", fake_tts)


async def _collect_done(monkeypatch, message="帮我学高数今天", extra_patches=None):
    from app.services import agent_service

    _base_patches(monkeypatch)
    if extra_patches:
        extra_patches(monkeypatch)
    done = None
    async for line in agent_service.run(
        db=None, user_id=str(uuid.uuid4()), message=message, session_id=None
    ):
        if not line.startswith("data:"):
            continue
        payload = json.loads(line[len("data:"):].strip())
        if payload.get("done"):
            done = payload
    return done


@pytest.mark.asyncio
async def test_engine_branch_adds_decision_to_done(monkeypatch):
    """学习推进意图 → done 事件携带 decision 字段。"""
    _state = {
        "review_due": {"due": 2},
        "knowledge_graph": {"total": 3, "mastered": 1, "learning": 2, "frontier": []},
        "exams": {"next": None, "stress_level": "low"},
        "streak": 0,
    }

    async def fake_get_state(db, user_id):
        return _state

    monkeypatch.setattr("app.services.learner_state_service.get_learner_state", fake_get_state)

    done = await _collect_done(monkeypatch, message="帮我安排复习")
    assert done is not None
    assert "decision" in done, f"done 事件应包含 decision 字段，实际: {done}"
    assert done["decision"]["action"] == "review_flashcard"
    assert "reason" in done["decision"]


@pytest.mark.asyncio
async def test_engine_disabled_no_decision(monkeypatch):
    """LEARNING_ENGINE_ENABLED=false → done 不含 decision 字段（回退 ReAct）。"""
    import os
    monkeypatch.setenv("LEARNING_ENGINE_ENABLED", "false")

    done = await _collect_done(monkeypatch, message="帮我安排复习")
    assert done is not None
    assert "decision" not in done


@pytest.mark.asyncio
async def test_free_chat_no_decision(monkeypatch):
    """自由聊天（非学习推进意图） → done 不含 decision 字段。"""
    done = await _collect_done(monkeypatch, message="什么是微分？")
    assert done is not None
    assert "decision" not in done


@pytest.mark.asyncio
async def test_engine_failure_falls_back_gracefully(monkeypatch):
    """learner_state_service 异常 → 引擎分支静默降级，对话仍正常完成。"""
    async def fail_get_state(db, user_id):
        raise RuntimeError("DB unavailable")

    monkeypatch.setattr("app.services.learner_state_service.get_learner_state", fail_get_state)

    done = await _collect_done(monkeypatch, message="帮我学高数")
    assert done is not None  # 对话必须完成，不能崩
```

- [ ] **Step 2: 跑测试，确认 FAIL（预期引擎分支尚未在 agent_service 中）**

```powershell
python -m pytest tests/unit/test_agent_engine_branch.py -v 2>&1 | head -30
```

预期：`test_engine_branch_adds_decision_to_done` FAIL（done 无 decision 字段）

- [ ] **Step 3: 在 `app/config.py` 加 feature flag**

读 `app/config.py` 后在 Settings 类末尾追加（在 `class Settings(BaseSettings):` 中）：

```python
    # 学习内核 P2：引擎驱动模式（feature flag，可一键回退旧 ReAct）
    LEARNING_ENGINE_ENABLED: bool = True
```

- [ ] **Step 4: 修改 `app/services/agent_service.py`——插入引擎分支**

在 agent_service.py 中，找到以下行（约第 280 行）：

```python
    _react_max = 0 if (complexity == "complex" and plan_summary) else MAX_TOOL_ROUNDS
    for _ in range(_react_max):
```

将其改为：

```python
    _react_max = 0 if (complexity == "complex" and plan_summary) else MAX_TOOL_ROUNDS

    # G-P2-4 · 学习引擎分支（feature flag: LEARNING_ENGINE_ENABLED）
    # 意图=学习推进 → 引擎决策 → 直接 dispatch 工具 → LLM 只格式化回复
    _engine_decision: dict | None = None
    try:
        from app.core.config import settings as _s
        if _s.LEARNING_ENGINE_ENABLED:
            from app.services.learning_intent import classify_learning_intent
            if classify_learning_intent(message):
                from app.services.learner_state_service import get_learner_state
                from app.services.learning_engine import recommend_actions, action_to_tool_call
                _state = await get_learner_state(db, user_id)
                _actions = recommend_actions(_state)
                if _actions:
                    _act = _actions[0]
                    _tool_nm, _tool_av = action_to_tool_call(_act)
                    yield f'data: {json.dumps({"thinking": _act.reason}, ensure_ascii=False)}\n\n'
                    _tool_result = await dispatch_tool(
                        db, user_id, _tool_nm, json.dumps(_tool_av, ensure_ascii=False)
                    )
                    tools_called.append(_tool_nm)
                    _engine_decision = {"action": _act.action_type, "reason": _act.reason}
                    _res_txt = json.dumps(_tool_result, ensure_ascii=False)[:2000]
                    system = (
                        system
                        + f"\n\n[引擎决策] {_act.reason}\n"
                        + f"工具执行结果：{_res_txt}\n"
                        + "请基于结果用自然语言引导学生，说明为什么这对他有帮助。"
                    )
                    _react_max = 0  # 跳过 ReAct 循环
    except Exception as _engine_err:
        logger.warning("learning_engine branch failed (fallback to ReAct): %s", _engine_err)

    for _ in range(_react_max):
```

- [ ] **Step 5: 修改 done 事件，加入 decision 字段**

找到以下代码块（约第 344 行）：

```python
    from app.services.rag_service import format_citations
    done_payload: dict = {
        "done": True,
        "session_id": session_id,
        "tools_called": tools_called,
        "sources": format_citations(rag_hits),
    }
```

改为：

```python
    from app.services.rag_service import format_citations
    done_payload: dict = {
        "done": True,
        "session_id": session_id,
        "tools_called": tools_called,
        "sources": format_citations(rag_hits),
    }
    if _engine_decision:
        done_payload["decision"] = _engine_decision
```

- [ ] **Step 6: 跑所有单元测试，确认 PASS + 总数正确**

```powershell
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
python -m pytest tests/unit/ -v --tb=short 2>&1 | tail -20
```

预期：`test_agent_engine_branch.py` 4 个全 PASS；之前所有测试保持绿。

- [ ] **Step 7: Commit**

```powershell
git add app/config.py app/services/agent_service.py tests/unit/test_agent_engine_branch.py
git commit -m "feat(kernel): P2-4 agent_service engine-driven branch with feature flag"
```

---

## Task 5: API 端点（G-P2-7 可视化入口）

**Files:**
- Create: `app/api/v1/learning_engine.py`
- Modify: `app/main.py`

- [ ] **Step 1: 创建路由文件**

```python
# app/api/v1/learning_engine.py
"""GET /v1/learning/recommended-actions — G-P2-7 决策可解释端点。

前端 C-13/C-14 可视化组件的数据源：展示"引擎此刻为你推荐的学习动作"。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.learner_state_service import get_learner_state
from app.services.learning_engine import recommend_actions

router = APIRouter(prefix="/learning", tags=["learning-engine"])


@router.get("/recommended-actions")
async def get_recommended_actions(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """返回当前用户的有序学习动作推荐（引擎决策，带原因）。"""
    user_id = str(current_user.id)
    state = await get_learner_state(db, user_id)
    actions = recommend_actions(state)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "actions": [
                {
                    "action_type": a.action_type,
                    "reason": a.reason,
                    "params": a.params,
                    "priority": a.priority,
                }
                for a in actions
            ],
            "learner_state_summary": {
                "due_count": state.get("review_due", {}).get("due", 0),
                "frontier_count": len(state.get("knowledge_graph", {}).get("frontier", [])),
                "stress_level": state.get("exams", {}).get("stress_level", "low"),
            },
        },
    }
```

- [ ] **Step 2: 注册路由到 main.py**

在 `app/main.py` 中，找到已有路由注册的区域（如 `app.include_router(...)`），追加：

```python
from app.api.v1.learning_engine import router as learning_engine_router
app.include_router(learning_engine_router, prefix="/v1")
```

- [ ] **Step 3: 冒烟验证——uvicorn 启动不崩**

```powershell
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
python -c "from app.main import app; print('import ok')"
```

预期：`import ok`（无异常）

- [ ] **Step 4: 跑全套单元测试**

```powershell
python -m pytest tests/unit/ -v --tb=short 2>&1 | tail -10
```

预期：总数增加；全绿。

- [ ] **Step 5: Commit**

```powershell
git add app/api/v1/learning_engine.py app/main.py
git commit -m "feat(kernel): P2-7 GET /v1/learning/recommended-actions decision explainability endpoint"
```

---

## Task 6: 全套回归 + 收尾

**Files:**
- 无新文件

- [ ] **Step 1: 清除 __pycache__（防陈旧字节码假失败）**

```powershell
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
```

- [ ] **Step 2: 跑全套测试**

```powershell
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

预期：
- 之前基线 156 pass + P2 新增 ~25 pass = **约 181 pass**（精确数以实际为准）
- 0 fail / 10 skip（原 skip 不变）

- [ ] **Step 3: 验证 feature flag 回退可用（保障 G-P2-6 兜底机制）**

```powershell
# 临时设 flag=false，确认 agent 无 decision 字段
$env:LEARNING_ENGINE_ENABLED = "false"
python -m pytest tests/unit/test_agent_engine_branch.py::test_engine_disabled_no_decision -v
$env:LEARNING_ENGINE_ENABLED = "true"
```

预期：PASS

- [ ] **Step 4: 更新 `知曜学习内核_架构迭代规划.md` 进度**

将 P2 进度表更新为：

```markdown
| P2 策略脊柱 | 7 | 7 | ✅ 已完成（agent_service 引擎分支 + feature flag，全套 ~181 pass） |
```

同时在 P2 落地记录区追加：

```markdown
### P2 落地记录（2026-06-01，已合并 main，全套 ~181 pass / 0 fail）

| 任务 | 产出 |
|---|---|
| G-P2-1 | `learning_engine.recommend_actions`（确定性优先级：到期复习>根因补漏>前沿新点>提取练习） |
| G-P2-2 | `select_difficulty`（答对率硬规则：>90%升/< 80%降/已蓝→先修兜底） |
| G-P2-3 | `_apply_retrieval_preference`（PRACTICE 排在 EXPAND 前，提取优先 M4） |
| G-P2-4 | `learning_intent.classify_learning_intent` + `agent_service` 引擎分支（意图分类→引擎决策→直接 dispatch→LLM 格式化） |
| G-P2-5 | `action_to_tool_call`（引擎动作→工具调用适配器，绕过 LLM 自由选工具） |
| G-P2-6 | `_fallback_actions`（state 不全→FSRS到期+前沿新点，绝不空转）+ feature flag 一键回退 ReAct |
| G-P2-7 | done 事件加 `decision` 字段 + `GET /v1/learning/recommended-actions` 端点 |
```

- [ ] **Step 5: 同步云盘（改了知识文档）**

```powershell
cd C:\Users\18208\Desktop\知曜创业项目
pwsh sync-knowledge-base.ps1
```

- [ ] **Step 6: 最终 Commit**

```powershell
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
git add 知曜学习内核_架构迭代规划.md 2>/dev/null; git add ../知曜学习内核_架构迭代规划.md 2>/dev/null
git add docs/superpowers/plans/2026-06-01-learning-kernel-p2-strategy.md
git commit -m "docs(kernel): P2 implementation complete — engine strategy / intent / API endpoint"
```

---

## 自审（Spec Coverage Check）

| G-P2 任务 | 覆盖 |
|---|---|
| G-P2-1 确定性优先级策略 | ✅ Task 1 `recommend_actions` + 8 单测 |
| G-P2-2 难度选择硬规则 | ✅ Task 2 `select_difficulty` + 6 单测 |
| G-P2-3 提取优先规则 | ✅ Task 2 `_apply_retrieval_preference` + 2 单测 |
| G-P2-4 重构 `agent_service` | ✅ Task 4 引擎分支 + 4 单测（含 fallback/flag/intent 分支）|
| G-P2-5 17 工具适配执行末端 | ✅ Task 1 `action_to_tool_call` + 4 单测（主要 4 种 action type 覆盖）|
| G-P2-6 策略兜底 | ✅ Task 1 `_fallback_actions` + 2 单测 + feature flag 回退测试 |
| G-P2-7 决策可解释 | ✅ Task 5 done 事件 `decision` 字段 + API 端点 |

**Placeholder scan:** 无 TBD / TODO / "similar to above" 占位。所有代码均完整。

**Type consistency:** `RecommendedAction.action_type` 使用 `ActionType` 常量字符串，`action_to_tool_call` 用相同常量匹配，一致。`done_payload["decision"]` 的结构与 `test_agent_engine_branch` 中的 `assert done["decision"]["action"]` 对齐。
