# v0.33 P0 三件 · 同步报告

> 2026-05-24 完成
> 目标：补齐 PRD 学习闭环最大短板 — 24h 首次复习 + 随堂测验 + 周复盘
> 入口：审计发现 PRD 七层完整度 68% → 补这 3 件后预估 80%+

---

## 落地清单

| # | 任务 | PRD 行 | 实现路径 | 真实验证 |
|---|------|--------|---------|---------|
| **P0-1** | 24h 首次复习推送 | 行 311 | Flashcard `due_date = today+1` 创建时设 / 新字段 `first_review_pushed_at` / Celery 每小时扫 / 推 notification | ✅ 5/5 pass |
| **P0-2** | 课程随堂测验自动生成 | 行 213-218 | 新 service `spot_quiz_service` / 新 Agent 工具 `spot_quiz` / 新 endpoint `POST /studyspace/sessions/{id}/spot-quiz` / SS prompt 更新引导调用 | ✅ 3/3 pass |
| **P0-3** | 周复盘自动 | 行 453-458 | Celery beat 每周日 20:00 `weekly_reflection_tasks.generate_all_users` / LLM 整理 5 个维度 / 写 reflection + notification + episode / 用户可主动触发 `POST /profile/reflection/generate` | ✅ 5/5 pass |

**累计 13/13 PASS · 0 WARN · 0 FAIL**

---

## P0-1 · 24h 首次复习推送

### 流程

```
用户 SS 完成 → 自动生成闪卡（or 手动建卡）
   ↓
Flashcard.due_date = today + 1 day
Flashcard.first_review_pushed_at = NULL
Flashcard.review_count = 0
   ↓
[24h 后]
   ↓
Celery beat 每小时跑 scan_first_review_due
   ↓
扫描 created_at ∈ [now-26h, now-22h]
    AND review_count = 0
    AND first_review_pushed_at IS NULL
   ↓
按用户聚合 → 推 notification("昨天学的卡快忘了，今天看看吧。导数定义、二次函数…")
   ↓
标记 first_review_pushed_at = now（防重推）
```

### 真实测试

```
[PASS] 闪卡 due_date = 明天 (2026-05-25) ✓ 24h 机制生效
[PASS] scan_first_review_due 推送 1 张卡 ✓
[PASS] notifications 写入 1 条 (first_review_24h) ✓
[PASS] flashcard first_review_pushed_at 已标记 ✓
[PASS] 二次扫描幂等 · 不重复推 ✓
```

### 关键文件
- 新增：`alembic/versions/029_v0_33_first_review_at.py`
- 改：`app/models/flashcard.py`（+ first_review_pushed_at 字段）
- 改：`app/services/fsrs_service.py::create_card`（due_date = today+1）
- 新增：`app/tasks/first_review_tasks.py`
- 改：`app/tasks/celery_app.py`（每小时 scan-first-review-due）

---

## P0-2 · 课程随堂测验自动生成

### 流程

```
SS 中 Agent 讲完一个 KP
   ↓
Agent 自动调 spot_quiz(kp_id=...)
   ↓
spot_quiz_service.generate_for_kp
   ├─ 取 KP → LLM 出 1-2 道题（题型按 bloom_level 自动选）
   ├─ 创建/复用 TrainingSession (mode='spot_check', ss_session_id=...)
   ├─ 写 TrainingQuestion 条目
   └─ 写 SS 时间线 kind=spot_quiz_generated
   ↓
返回题目给 Agent，Agent 让用户作答
   ↓
用户答题 → 走原训练 submit_answer 流程
```

### 题型自动选择

| KP bloom_level | spot_quiz 题型 | 作答时长 |
|---|---|---|
| remember/understand | fill_blank（填空/名词解释） | ~1min |
| apply/analyze | short_answer（应用/计算简答） | ~2min |
| evaluate/create | essay（短答 ≤50 字） | ~2min |

**单题字数约束**：题目 ≤100 字 / 参考答案 ≤200 字 / 不出复杂证明题

### 真实测试

```
[PASS] spot_quiz 生成 1 题 ✓
  text='函数 f(x) 在点 x 处的导数定义为 f'(x) = ________。'
  ref='lim_{Δx→0} [f(x+Δx) - f(x)] / Δx'
[PASS] 复用 session OK · 单日同 KP 同 session ✓
[PASS] Agent 通过工具调用 spot_quiz ✓
  reply='导数定义的填空题：f'(x) = lim Δx→0 ________，其中Δx表示自变量的增量。答案填什么？直接...'
```

### 关键文件
- 新增：`app/services/spot_quiz_service.py`
- 改：`app/llm/prompts/agent.py`（+ TOOL_DEFINITIONS spot_quiz + SS 行为规则改）
- 改：`app/services/agent_tools.py`（+ _spot_quiz handler）
- 改：`app/api/v1/studyspace.py`（+ POST /sessions/{id}/spot-quiz）

---

## P0-3 · 周复盘自动

### 流程

```
Celery beat 每周日 20:00
   ↓
weekly_reflection_tasks.generate_all_users
   ↓
对每个 onboarding 完成的用户：
   ├─ 收集本周（周一→周日）数据：
   │   ├─ 本周新学 KP 数
   │   ├─ 闪卡到期 / 已复习 / 完成率
   │   ├─ 训练答题平均分 by KP（薄弱 Top3）
   │   ├─ 番茄钟总时长
   │   └─ 未来 14 天考试 Top3
   ├─ LLM 按知曜 voice 整理（150 字以内，结构①做了什么 ②哪里不行 ③下周重点）
   ├─ 写 weekly_reflections 表（per-week 唯一约束 → 覆盖）
   ├─ 推 notification("周复盘已生成。…")
   └─ 写 episode（importance=6，便于跨 session 召回）
   ↓
用户也可主动触发 POST /v1/profile/reflection/generate
```

### LLM voice 实测

> "本周你学了 1 个新知识点。闪卡复习和番茄钟全是 0，训练数据也没有。下周重点：先把每日闪卡复习补上，再定一个固定番茄时段。"

✓ 短句 / 不打鸡血 / 不"首先其次" / 全程"你" / 给可行动建议（PRD voice 满分）

LLM 失败时有 `_fallback_summary` 模板兜底，保证用户永远有内容看。

### 真实测试

```
[PASS] 周复盘生成 OK · 3.8s · week_start=2026-05-18 · len=62
[PASS] reflection 已落盘 ✓
[PASS] 周复盘 notification 推送 ✓
[PASS] 周复盘 episode 写入 ✓
[PASS] 重复生成覆盖 ✓ · 仍只有 1 条本周记录
```

### 关键文件
- 新增：`app/tasks/weekly_reflection_tasks.py`
- 改：`app/tasks/celery_app.py`（+ generate-weekly-reflection 每周日 20:00）
- 改：`app/api/v1/profile.py`（+ POST /v1/profile/reflection/generate）

---

## 完整改动清单（v0.32 → v0.33）

**新增 4 个文件**：
```
alembic/versions/029_v0_33_first_review_at.py
app/services/spot_quiz_service.py
app/tasks/first_review_tasks.py
app/tasks/weekly_reflection_tasks.py
tests/manual_audit/p0_e2e.py
```

**修改 8 个文件**：
```
app/models/flashcard.py
app/services/fsrs_service.py
app/llm/prompts/agent.py
app/services/agent_tools.py
app/api/v1/studyspace.py
app/api/v1/profile.py
app/tasks/celery_app.py
SPEC.md
```

---

## 状态

| 维度 | 改动后 |
|---|---|
| Alembic head | 029 |
| API 端点 | **155**（+2 新端点） |
| pytest | 32/32 pass |
| Agent 工具 | **16**（+spot_quiz） |
| Celery 任务 | **11**（+scan-first-review-due + generate-weekly-reflection） |
| PRD 七层完整度（估） | 68 → **80** |

---

## 接下来

P0 三件已落地。距 PRD MVP 标准（连续使用 ≥2 周 + NPS ≥50）所需的"学习闭环可见"已经齐了。

**P1 候选**（按"对学习效果影响 × 实现成本"）：
1. 费曼输出 + AI 评估（2d）
2. 自适应难度（1.5d）
3. 交错练习（1d）
4. 错题孪生题 + 错误原因（1.5d）
5. 苏格拉底 5 轮强制（0.5d）

也可以现在停下来等前端联调反馈，看 20 用户真实数据再决定优先级。

**报告完。**
