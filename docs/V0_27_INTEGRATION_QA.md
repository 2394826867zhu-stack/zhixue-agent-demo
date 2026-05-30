# v0.27 整合细节问题清单 — 等用户决策

> 这份文档是后端代码整合审计的产出，列出所有**跨模块联动**的不一致 / 缺失 / 需要决策的点。
> 你按编号回答即可，我按你的回复继续修。

---

## 🔴 一、确定 Bug（先告诉我修哪个，不需要决策）

### Bug-01 · `EquippedCosmeticsResponse` 字段过时
**位置**：`app/schemas/star.py:43-47`

```python
class EquippedCosmeticsResponse(BaseModel):
    material: str | None        # ← 旧类目
    accessory: str | None
    aura: str | None             # ← 旧类目
    voice: str | None            # ← 旧类目
```

但 v0.24 我把 catalog 改成 **clothing / hair / accessory / background**（PRD 9.10 行 694）。

**症状**：用户装备一件 clothing_default_white_tee（category=clothing）后调 `GET /v1/cosmetics/equipped`，返回的全是 null，clothing 字段不存在。**v0.24 e2e 测试时就遇到了**。

**建议改法**：
```python
class EquippedCosmeticsResponse(BaseModel):
    clothing: str | None
    hair: str | None
    accessory: str | None
    background: str | None
```

→ 同时改 `star_service.get_equipped`。
**🔧 修不修？(Y/N)**

---

### Bug-02 · `find_active_ss_session_id` 假设单一活跃会话
**位置**：`app/services/ss_timeline_service.py:22-42`

现在用户可能同时挂 2 个 active SS session（例如 forgot to complete 上次的），导致训练答题、闪卡复习的时间线写入**最近开始的 session**，而不是用户当前真正在做的那个。

**建议改法**：要么 (a) 强制单 active（开始新 session 时把旧的 status='paused'），要么 (b) 写时间线时通过显式 `ss_session_id` 参数传入。

**选哪个？**：
- **A. 强制单 active** — 新建 SS 时把同用户所有 active session 自动 → paused
- **B. 显式传 session_id** — 训练/闪卡 API body 加 `ss_session_id` 可选字段，前端要传
- **C. 都做**（强制单 active + 提供显式参数 override）

---

## 🟡 二、关键设计决策（影响业务语义）

### Q-01 · `notebook_origin` 自动判定规则
PRD 5.4 行 528-540 明确"官方课程笔记"vs"用户自主笔记"必须区分。但当前代码所有路径都默认 `notebook_origin="user_project"`，没有任何地方设置 "official"。

**哪些路径应该自动设为 official？**

- [ ] **A.** 从 `curriculum_chapters` 派生的 SS session 内生成的 KP / Note → official
- [ ] **B.** Project 创建时 `source="official"` 的项目下生成的所有 KP / Note → official
- [ ] **C.** 课程目录 `/curriculum/chapters/{id}/generate-note` 端点产物 → official
- [ ] **D.** 全部默认 user_project，让用户手动改
- [ ] **E.** 由 Agent 在生成时自己判断（用 prompt 让模型决定）

我建议 **A + B + C 三个组合**（确定的官方场景就标官方，其他保留 user_project）。**你的选择？**

---

### Q-02 · `project_id` 自动挂载规则
现在 KP/Note/Flashcard 创建时**都没有自动设 project_id**。需要决策"什么时候自动挂"。

**触发场景**：
- [ ] **A.** SS session 有 `project_id` → 该 SS 内生成的所有 KP/Note/Flashcard 自动继承
- [ ] **B.** 用户在某项目下手动点"生成笔记" → 该笔记 project_id = 该项目
- [ ] **C.** 用户在某项目下做训练答题 → 错题加入该项目错题本
- [ ] **D.** 完全不自动挂，所有内容默认游离，用户手动整理（Notion 风）
- [ ] **E.** Agent 在调用 `generate_note` 工具时根据上下文判断

我建议 **A + B + C**。**你的选择？**

---

### Q-03 · 树状路径节点 locked → available 解锁策略
PRD 行 394 提到"推荐学习顺序用路径高亮"，但目前**没有任何代码让 locked 节点变 available**。
（除了 root 节点 depth=0 默认 available，其他都永远 locked）

**解锁策略选哪个？**
- [ ] **A.** 父节点 completed → 直接子节点全部 available（树形递进）
- [ ] **B.** is_on_main_path=True 的节点按 sort_order 顺序解锁（主干推荐路径递进）
- [ ] **C.** 用户随时可以学任何节点，没有锁概念，只用 mastery_pct 标记进度（Notion 自由风）
- [ ] **D.** Agent 决定何时解锁（Agent 调用 tool 来更新 status）
- [ ] **E.** 自动 A + 手动 D（默认按 A 解锁，Agent 可以提前解锁）

我建议 **E**（默认 A 严格父→子，Agent 可override）。**你的选择？**

---

### Q-04 · Agent 状态机自动转换触发点
现在 `agent_avatar_state` 只通过 `set_agent_state` 工具显式切换。没有任何业务事件自动触发状态变化。

**应该哪些事件自动设 Agent 状态？**

| 事件 | 自动设状态 | 持续多久 |
|------|-----------|--------|
| Agent 正在执行工具（`/agent/chat` 中调 tool） | thinking | 工具执行期 |
| Agent 流式生成回复 | speaking | 流式期 |
| StudySpace 完成 | celebrate | 5s 后回 idle |
| 连击 7 天 | celebrate | 10s |
| 闪卡复习全对 | celebrate | 5s |
| 番茄钟开始 | focus | 番茄钟期间 |
| 用户进入沉浸模式 | focus | 沉浸期 |
| 1 小时无活动 | sleepy | 直到活动 |

**全做？还是只选关键？** **你的选择？**

---

### Q-05 · `compose-quiz` 的 `ss_session_id` 字段如何使用
我加了 `ComposeQuizRequest.ss_session_id` 但 service 没用它。当前 compose-quiz 的训练答题时间线写入靠 `find_active_ss_session_id` 自动找。

**保留这个字段吗？**
- [ ] **A.** 删掉它，统一靠 `find_active_ss_session_id` 自动判
- [ ] **B.** 保留，前端必传，时间线写到这个明确的 session（更可靠）
- [ ] **C.** 保留，前端可选传，传了就用、没传就自动找

我建议 **C**。**你的选择？**

---

### Q-06 · Agent 浏览记录 upsert 时机
现在 `agent_history_service.upsert_log` 在 SSE 流**完成后**才写一次。

**风险**：用户中途断网，对话永远不会进浏览记录。

**改进方案**：
- [ ] **A.** 流式开始时就 upsert 一次（仅 title 和首条消息），结束时再 update
- [ ] **B.** 每发一条 user message 就 upsert，结束再 update tools_called
- [ ] **C.** 保持现状，断流就丢（简单可靠）

我建议 **A**。**你的选择？**

---

### Q-07 · `immersion_sessions.pomodoros_completed` 与 `pomodoro_records` 是否双写
两张表都存番茄钟数据：
- `pomodoro_records`（v1 老表，按单次番茄记录）
- `immersion_sessions.pomodoros_completed`（v2 新字段，统计本次沉浸会话累计）

**目标**：进入沉浸模式完成番茄钟，**只写 immersion_sessions** 还是**双写**？

- [ ] **A.** 沉浸期间只写 `immersion_sessions`，老 pomodoro_records 仅供非沉浸番茄使用
- [ ] **B.** 双写（pomodoro_records 是事实源，immersion_sessions 只汇总）
- [ ] **C.** pomodoro_records 加 `immersion_session_id` 外键 → 沉浸番茄都进 pomodoro_records，immersion_sessions 通过 join 汇总
- [ ] **D.** 弃 pomodoro_records，全用 immersion_sessions（破坏 v1 API）

我建议 **C**（保留 pomodoro_records 作为唯一事实源，加外键 join）。**你的选择？**

---

### Q-08 · SS `complete_session` 是否写多条时间线节点
现在 SS 完成只写 **1 条** `agent_action`。但理论上一次完成可能涉及：
- 提取了 N 个知识点
- 自动生成了 M 张闪卡
- 奖励了 K 个知星
- 解锁了下一课时

**应该拆开还是合并？**
- [ ] **A.** 保持 1 条（合并版，简洁）
- [ ] **B.** 拆 3-4 条（KP 提取 1 条 + 闪卡生成 1 条 + 完成总结 1 条），用户翻阅时间线更详细
- [ ] **C.** 总结 1 条 + 每个 KP 1 条 `kp_extracted` 节点

我建议 **B**（清晰但不啰嗦）。**你的选择？**

---

### Q-09 · 闪卡批量生成的触发时机
现在 SS 完成后 `flashcards_created` 是个统计字段，但**实际闪卡生成动作没看到自动执行**。
查 `note_service.py:217` 有 `flashcards_generated = True` 标志，但这是另一条 ai-generated note 的链路。

**SS 完成后是否应该自动批量生成闪卡？**
- [ ] **A.** 自动生成（用户 KP → 每个 KP 至少 1 张闪卡）
- [ ] **B.** 不自动，用户在 SS 时间线点"生成闪卡"按钮触发
- [ ] **C.** Agent 决定（在 complete 时调 generate_flashcards 工具）

我建议 **A**（系统自动是 v2 强反馈的关键）。**你的选择？**

---

### Q-10 · onboarding 自动生成项目的策略
v0.26 我把 onboarding 完成后的"自动生成路径"改成"自动生成项目"。但项目名只取了 `goal[:20]` 或 `subjects[0]`，很笨。

**改成什么？**
- [ ] **A.** 跑 LLM `draft_from_dialog`，让 Agent 整理整段 onboarding 对话生成 draft
- [ ] **B.** 按 subject 数量生成 N 个项目（每个学科一个）
- [ ] **C.** 不自动生成，引导用户进学习工作台点"+ 新建项目"
- [ ] **D.** 保持当前，简单 fallback

我建议 **A**（用 LLM 生成才符合 PRD 9.2 "Agent 对话式收集"）。**你的选择？**

---

## 🟢 三、命名 / 一致性（小事，但需要统一）

### N-01 · 同一个枚举值在不同模型用了不同字段名
- `projects.source`（enum `project_source`）= "official" | "user_project"
- `notes.notebook_origin`（**同一个 enum**）= "official" | "user_project"
- `knowledge_points.notebook_origin`（同上）
- `flashcards.notebook_origin`（同上）

**统一到哪个？**
- [ ] **A.** 全部叫 `notebook_origin`（包括项目主表 `projects.source` 改成 `projects.notebook_origin`）
- [ ] **B.** 全部叫 `source`（保持项目主表，其他改）
- [ ] **C.** 项目用 `source`，内容用 `notebook_origin`（保持现状，因为项目本身不是 "notebook"）

我建议 **C**（语义清晰，保持现状）。**你的选择？**

---

### N-02 · 题型 enum 是 string 还是 Postgres ENUM 类型
现在 `training_questions.question_type` 是 `String(20)`，前端传"choice"就存进去，没有 DB 层校验。新加的 8 种题型只是 Python `Literal` 校验。

**要不要升级成 Postgres ENUM？**
- [ ] **A.** 升级（migration 加 enum，给 DB 强约束）
- [ ] **B.** 保持 String + Python 层校验（灵活，加新题型不用迁移）

我建议 **B**（前端 API 已经强校验，DB 灵活更好）。**你的选择？**

---

## 🔵 四、运维 / 工程纪律（建议你审一下）

### W-01 · 路径已删但 `__pycache__/path.cpython-312.pyc` 还在
**建议**：清理 `__pycache__` 一次。代码里没有引用了，但缓存还留着。
**🔧 清不清？(Y/N)**

---

### W-02 · `datetime.utcnow()` 用法零次（全用 `datetime.now(timezone.utc)`）
扫了一遍 zero 出现。**👍 一致性达标，无需动作。**

---

### W-03 · Token 配额追踪 — 新增的 LLM 调用都带了 `user_id`
✅ `project_service.draft_from_dialog` 带了
✅ `project_service.generate_tree_nodes` 带了
✅ `training_service.compose_quiz` 带了

**👍 配额覆盖完整，无需动作。**

---

### W-04 · `mistake_service` 用 `TrainingQuestion.is_wrong=True` 而非独立 mistake 表
现在没有独立 `mistakes` 表，错题就是 `training_questions` 表里 `is_wrong=True` 的记录。**保留这个设计？**

- [ ] **A.** 保留（PRD 9.5 行 654 "错题本身是知识点集合"，单独表无意义）
- [ ] **B.** 拆出独立 mistake 表（更易扩展错因分类、错题笔记等）

我建议 **A**（PRD 已经说过了，单独表多余）。**你的选择？**

---

### W-05 · `EquippedCosmeticsResponse` 修了后 — 前端响应字段变了
现在 frontend 已经下线，不影响。等做新前端时按 v0.27 新 schema 写。

---

## ⚪ 五、可选增量（v0.27 候选，告诉我做不做）

### F-01 · 沉浸场景资产 seed
PRD 6.1 第一版只做"书桌/房间"。但我已经在 cosmetic_catalog 里加了 background 类目（咖啡馆 / 夜景 / 极光 / 宿舍 / 图书馆 / 书桌）。

**是否把这些背景同步到 `immersion_scenes` 表 seed 数据？**（让沉浸场景列表自动显示这些）
- [ ] **A. 做** — 沉浸场景和背景装扮统一来源
- [ ] **B. 不做** — 沉浸场景独立资产，装扮独立
- [ ] **C. 做但解耦** — 背景装扮触发后才解锁对应沉浸场景

我建议 **A**。**你的选择？**

---

### F-02 · Celery beat 定时通知（PRD 行 553 "有机推送"）
现在 `app/tasks/notification_tasks.py` 有 `push_organic_notifications` 但没有 beat 配置定时跑。

**是否加 beat 配置每天定时推？**
- [ ] **A. 加** — Celery beat 配置 + Schedule（每天 8:00 / 12:00 / 20:00 各一次）
- [ ] **B. 不加** — 通知靠业务事件触发（用户行为驱动）
- [ ] **C. 都做** — Beat 兜底 + 事件触发

我建议 **C**（兜底不会缺，事件更精准）。**你的选择？**

---

### F-03 · pgvector 已装但未用 — 启用 KP 向量化
`requirements.txt` 有 `pgvector==0.3.6`，Postgres 也跑着 pgvector 扩展（其实没启用 extension，只是 driver 装了）。
启用后能做：跨 KP 语义相似度搜索 / Agent 找类似知识点 / 错题推荐相关 KP 复习。

- [ ] **A. v0.27 做** — 加 KP.embedding 字段 + 后台任务批量向量化
- [ ] **B. v0.28 做** — 优先级低
- [ ] **C. 不做** — pgvector 从依赖里删

我建议 **B**（不是 MVP 必需）。**你的选择？**

---

### F-04 · Admin 后台扩 v2 维度
现有 `/admin/dashboard` 只统计 v1 维度（用户/笔记/KP/Token）。

**是否加 v2 维度？**
- 项目总数 / 活跃项目
- 沉浸会话总时长
- Agent 工具调用 top10
- 装扮购买率
- compose-quiz 使用率

- [ ] **A. 全做**
- [ ] **B. 只加项目 + 沉浸**
- [ ] **C. 暂不做**

我建议 **B**。**你的选择？**

---

## 📋 总览：等你逐条回复后，我会按以下顺序修

| # | 类别 | 项 | 优先级 |
|---|------|---|------|
| 1 | Bug | Bug-01 EquippedCosmeticsResponse | 🔴 高 |
| 2 | Bug | Bug-02 多 active SS session | 🔴 高 |
| 3 | 设计 | Q-01~10 业务规则 | 🟡 看你选 |
| 4 | 命名 | N-01, N-02 | 🟢 低 |
| 5 | 运维 | W-01, W-04 | 🟢 低 |
| 6 | 增量 | F-01~04 | ⚪ 你定 |

**你的回复格式（建议直接复制下面填）**：
```
Bug-01: Y
Bug-02: A
Q-01: A+B+C
Q-02: A+B+C
Q-03: E
Q-04: 全做 / 只 thinking + celebrate + focus
Q-05: C
Q-06: A
Q-07: C
Q-08: B
Q-09: A
Q-10: A
N-01: C
N-02: B
W-01: Y
W-04: A
F-01: A
F-02: C
F-03: B
F-04: B
```

或者你写"按推荐全选"，我就按我建议的执行。
