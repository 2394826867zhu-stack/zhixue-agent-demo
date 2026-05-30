# 知曜 Agent 全面配置 · 操作报告

> **目标**：把当前的"基础聊天 + 14 工具 ReAct" 升级到 **生产级 AI Agent OS**，含 RAG / 分层记忆 / 规划循环 / 可观测性
>
> **文档时间**：2026-05-24
> **当前 backend 版本**：v0.27
> **PRD 真源**：`zhiyao-mobile-app/docs/v2-prd-memory.md`

---

## 🔒 决策锁定表（2026-05-24 用户确认）

| Q | 决策 | 备注 |
|---|------|------|
| Q1 RAG 范围 | A · 仅用户自己的 KP/notes | |
| Q2 跨学科 | A · 严格按 subject 隔离 | |
| Q3 重建 embedding | B · Celery 异步 5min | |
| Q4 agent_memory 写入 | A · 仅 Agent 主动 save_memory | |
| Q5 行为信号 | 全选 6 类（KP答错/未学/考前/连击/phase/节奏） | |
| Q6 Episodes 保留 | B · 90 天，importance≥7 永久 | |
| Q7 推理模式 | A · Plan-Execute-Verify-Reflect | |
| Q8 复杂度分类器 | B · LLM 小调用 | |
| Q9 安全出口 | 全选（重新生成/追加/撤销） | |
| Q10 引用 | B · 推荐但不强制 | |
| Q11 self-critique | B · 仅 Plan-Execute 模式 | |
| **Q12 主 LLM** | **DeepSeek V4 Flash**（用户指定） | 待补 model string |
| Q13 嵌入模型 | A · OpenAI text-embedding-3-small | |
| Q14 月预算 | B · ¥500–3000 | |
| Q15 单用户日 Token | B · 500,000 | |
| Q16 pgvector | B · Docker pgvector/pgvector:pg17 | 待确认 Docker Desktop |
| Q17 内容安全 | C · 暂不做 | |
| Q18 PII | A · 正则 mask | |

**剩余 blocker**：
- ~~DeepSeek V4 Flash 的真实 API model string~~ ✅ `deepseek-v4-flash` @ `https://api.deepseek.com`
- ~~Docker Desktop 是否已装~~ ✅ 已装 v29.4.3 + pgvector/pgvector:pg17 容器跑通
- Q13 修订：**OpenAI text-embedding-3-small → BAAI/bge-m3 本地**（用户决定零依赖云 API）

## 🚀 Sprint 1 完成（2026-05-24）

- migration 026 · `document_embeddings` 表 + HNSW cosine 索引
- `app/services/embedding_service.py` · BGE-M3 lazy init 单例
- `app/services/rag_service.py` · upsert / search / format_for_prompt
- `app/tasks/embedding_tasks.py` · 4 个 Celery 任务（embed_kp / embed_note / embed_chapter / backfill_*）
- `app/services/agent_service.py` · 每条消息前自动注入 top-5 RAG
- 新工具 `retrieve_knowledge`（让 Agent 主动深度召回）
- 笔记完成 hook → 5min 延迟入库（Q3）
- 主 LLM 全面切 `deepseek-v4-flash`
- 117 课程章节 + 190 KP 已 backfill 入向量库（307 向量 / 4.3MB）
- pytest 28/28 通过（含 6 个新增 RAG 用例）
- SPEC.md → v0.28

---

## A · 现状盘点

### A.1 已有能力（v0.27）

| 能力维度 | 现状 | 评分 |
|---------|------|------|
| **对话** | SSE 流式 / DeepSeek function calling / ReAct 5 轮工具 | 🟢 7/10 |
| **工具** | 14 个（context / 学习诊断 / 任务 / 训练 / 考试 / 笔记 / 记忆 / 课程导入 / 模拟考 / 项目骨架 / 项目树 / 状态切换 / 记忆保存 / 模拟考） | 🟢 7/10 |
| **状态机** | 10 状态库 + 4 自动触发事件（SS 完成 / 沉浸 / 工具 / 流结束） | 🟢 8/10 |
| **短期记忆** | Redis `agent_session:{user}:{session}` 单 session 历史 24h TTL | 🟡 5/10 |
| **长期记忆** | `users.agent_memory` JSONB（preferences / personality / goals / observations）+ `save_memory` 工具 | 🟡 5/10 |
| **浏览记录** | `agent_conversation_logs` 表 + ILIKE 全文搜索 | 🟢 7/10 |
| **多模态** | 图片 base64 注入 chat 已支持 | 🟢 7/10 |
| **TTS** | OpenAI TTS + Redis 缓存 1h | 🟢 7/10 |
| **Token 配额** | TokenUsage 表 + 每用户每日上限 | 🟢 8/10 |
| **LLM Provider** | DeepSeek 主 + OpenAI 备 + Anthropic 备 | 🟢 8/10 |
| **RAG** | **完全没有** | 🔴 0/10 |
| **向量化** | pgvector 在 requirements 但 PG **未启用** extension | 🔴 0/10 |
| **规划层** | 无 plan-then-execute / 无 reflection / 无 verification | 🔴 2/10 |
| **可观测性** | 基础 logger，无 trace / 无 eval pipeline | 🔴 2/10 |
| **安全/红线** | 无 prompt injection 检测 / 无内容审核 | 🔴 1/10 |

### A.2 数据规模（决定 RAG 策略）

```
curriculum_chapters    117 行（官方课程目录）
knowledge_points       190 行（用户 KP）
notes                   15 行（用户笔记）
training_questions     待统计
flashcards             待统计
guidance_messages      待统计（苏格拉底引导消息）
```

**结论**：当前数据量很小（< 1000 文档），向量化全量后存储 < 50MB，可全量 in-memory，也可走 pgvector 持久化。规模升到 10万级前都不需要专业向量数据库。

### A.3 关键基础设施缺口

| 缺口 | 影响 |
|------|------|
| ❌ pgvector extension 未启用 | 无法在 Postgres 做向量检索 |
| ❌ 嵌入模型未选 | 无法生成 embedding |
| ❌ 嵌入流水线未建 | 即使有模型也没流水线把 KP/notes 入库 |
| ❌ 检索服务未写 | 即使有 embedding 也没接到 chat 流 |
| ❌ 工具调用结果未沉淀 | tool 返回的 dict 用完即丢，应转成长期记忆 |
| ❌ 行为信号未自动捕获 | "Agent 记着用户哪一章老出错" 这种 PRD 承诺没数据流支撑 |
| ❌ Plan/Reflect 缺失 | 复杂任务 5 轮工具不够（如"帮我安排接下来一周复习"） |
| ❌ Citation 缺失 | Agent 引用了哪个 KP / 笔记 无追溯 |

---

## B · 目标架构（"真正的 Agent OS"）

### B.1 七层架构

```
┌───────────────────────────────────────────────────────────┐
│  L7 · Eval & Observability                                │
│       Trace · Metrics · Hallucination · Cost · Latency   │
├───────────────────────────────────────────────────────────┤
│  L6 · Safety & Quality                                    │
│       Content moderation · PII filter · Citation · Verify │
├───────────────────────────────────────────────────────────┤
│  L5 · Planning & Reasoning                                │
│       ReAct (have) → Plan-Execute → Reflexion → Verify   │
├───────────────────────────────────────────────────────────┤
│  L4 · Tool Ecosystem                                      │
│       14 tools (have) + RAG retrieve + cite + verify     │
├───────────────────────────────────────────────────────────┤
│  L3 · Memory System                                       │
│       Short / Working / Episodic / Semantic / Procedural │
├───────────────────────────────────────────────────────────┤
│  L2 · Retrieval (RAG)                                     │
│       Embedding · Chunking · Vector store · Rerank · Cite │
├───────────────────────────────────────────────────────────┤
│  L1 · LLM Provider Abstraction                            │
│       DeepSeek · OpenAI · Anthropic (have) + embeddings  │
└───────────────────────────────────────────────────────────┘
```

### B.2 PRD 对 Agent 的明确要求（逐条）

| PRD 行 | 要求 | 当前实现 |
|--------|------|---------|
| 行 17-19 | AI native 学习 OS, Agent 是主要卖点 | ✅ |
| 行 60-66 | Notion + Notion AI 类比，框架本身可用 + Agent 深化 | ✅ |
| 行 79-105 | 悬浮球抽象 + 小浮窗 + 控制台双层 | 前端 |
| 行 156-170 | 形象 + 10 状态库 + idle/thinking/celebrate 等 | ✅ |
| 行 234-242 | 工具调用 → "正在整理知识点" 等状态条反馈 | ✅ SSE thinking 事件 |
| 行 244-248 | 重新生成 / 追加修正 / 撤销 三个安全出口 | ❌ 待加 |
| **行 25** | **"记着用户什么时候开始拖延、哪一章老出错、考试前几天的状态"** | 🟡 agent_memory 字段在，但**自动捕获缺失** |
| 行 60-66 | Agent 可调用工具 / 可串联上下文 / 可组织学习流程 / 可给反馈和复盘 | ✅ |
| 行 137 | AI 深度控制台需要重点可视化 | 前端 |
| 行 154-158 | Q 版小女孩 / 2.5D / 装扮系统 | 前端 |
| **PRD 行 488** | **"系统不说话，只有 Agent 说话"** | 🟡 文案散落各处需统一 |
| 行 537 | 知识点卡片**优先从 StudySpace 学习过程生成** | 🟡 没专门 prompts 优化 SS 内提取 |
| 行 542 | **错题解析由 Agent 自动生成** | 🟢 已有 grade_answer LLM 调用 |

### B.3 关键差异：从"对话 LLM"到"真 Agent"

| 维度 | 对话 LLM | 真 Agent |
|------|---------|---------|
| 上下文 | 仅当前 session | 跨 session 持久化记忆 + RAG 召回 |
| 工具调用 | 单轮 ReAct | 多轮 Plan-Execute-Reflect |
| 知识源 | 只看 system prompt | 检索用户全部 KP/notes + 官方课程 |
| 行动 | 等用户问 | 主动观察行为，触发提醒/建议 |
| 引用 | 编 / 不引用 | 明确指明引用了哪个 KP/笔记 |
| 学习 | 静态 | 工具调用模式沉淀进 procedural memory |
| 评估 | 无 | 答非所问检测 + 幻觉检测 + 用户满意度 |

---

## C · RAG 基础设施详细方案

### C.1 三层 RAG 架构

```
┌────────────────────────────────────────────────────┐
│ Hot Layer (Redis Cache)                           │
│ ├── Query embedding cache (10 min TTL)            │
│ ├── Top-K retrieval result cache (5 min TTL)      │
│ └── Embedding model warm cache                    │
├────────────────────────────────────────────────────┤
│ Warm Layer (Postgres + pgvector)                  │
│ ├── kp_embeddings              (190 vectors)      │
│ ├── note_embeddings            (15 vectors)       │
│ ├── chapter_embeddings         (117 vectors)      │
│ ├── guidance_message_embeddings (动态增长)         │
│ └── conversation_summary_embeddings (周报 / 复盘)  │
├────────────────────────────────────────────────────┤
│ Cold Layer (Object Storage)                       │
│ ├── 原始文档 (用户上传 PDF / 图片)                  │
│ ├── 历史对话归档                                    │
│ └── Embedding 模型版本快照                          │
└────────────────────────────────────────────────────┘
```

### C.2 嵌入模型选型对比

| 选项 | 优势 | 劣势 | 月成本（10k 用户） |
|------|------|------|---------------------|
| **OpenAI text-embedding-3-small** | 1536 维 / 中英好 / API 稳 / $0.02/M tokens | 依赖海外 API | ~ $5 |
| **BGE-large-zh-v1.5** | 开源 / 中文 SOTA / 1024 维 | 需自部署 GPU 推理 | $0 / 但需 1×A10 ≈ ¥500 |
| **DashScope text-embedding-v2** | 阿里 / 国内速度快 / ¥0.0007/1k tokens | 锁阿里云 | ~ ¥150 |
| **M3E-base** | 开源 / 中文 / 768 维 / 体积小 | 中等质量 | $0 / 1×T4 ≈ ¥300 |

**🎯 推荐**：**OpenAI text-embedding-3-small** 作为主选（已配 OPENAI_API_KEY） + **BGE-large-zh-v1.5** 作 fallback（本地离线）。
理由：先用云端把流程跑通；规模上来再迁本地。

### C.3 Chunking 策略

| 文档类型 | Chunk 大小 | Overlap | 切分依据 |
|---------|-----------|---------|---------|
| Curriculum Chapter | 整章不切（小） | 0 | chapter 本身就是 unit |
| Knowledge Point | 整 KP 不切 | 0 | KP 本身就是 atom |
| Note `full_version` | 500 tokens | 80 | 按标题层级 (## / ###) |
| Note `exam_version` | 不切（小） | 0 | 摘要本身已浓缩 |
| Guidance Message | 整条不切 | 0 | 对话消息天然短 |
| Conversation Summary | 500 tokens | 50 | 周报 / 复盘按段落 |

### C.4 检索流水线

```
用户消息
  │
  ▼
[1] Query Rewrite（LLM 改写为查询友好句）
  │
  ▼
[2] Embed query（text-embedding-3-small）
  │
  ▼
[3] pgvector 检索 top-30（在 hot cache 5 min）
  │
  ├── KP 相似度
  ├── Note chunk 相似度
  ├── Curriculum chapter 相似度
  └── 用户历史对话总结相似度
  │
  ▼
[4] Filter by user_id + project_id（hard filter）
  │
  ▼
[5] Rerank top-30 → top-5（可选，提升质量）
  │
  ▼
[6] Inject into context with citations [1][2][3]
  │
  ▼
[7] LLM 调用 + 流式输出
  │
  ▼
[8] 后处理：抽取引用 → 写时间线 → 写 conversation_log
```

### C.5 表设计（新增）

```sql
-- 嵌入向量主表
CREATE TABLE document_embeddings (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,                    -- 用户隔离
  project_id UUID,                          -- 项目筛选
  notebook_origin VARCHAR(20),              -- official / user_project
  
  doc_kind VARCHAR(30) NOT NULL,            -- kp / note / chapter / guidance / summary
  doc_id UUID NOT NULL,                     -- 原文档 FK（多态）
  chunk_index INTEGER DEFAULT 0,            -- chunk 序号
  
  content TEXT NOT NULL,                    -- chunk 原文
  embedding vector(1536) NOT NULL,          -- pgvector 列
  
  metadata JSONB DEFAULT '{}',              -- {title, source, subject, ...}
  
  embedding_model VARCHAR(50) NOT NULL,     -- 'text-embedding-3-small' / 'bge-large-zh'
  embedding_version VARCHAR(20),            -- 模型版本快照
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_doc_embed_user ON document_embeddings (user_id);
CREATE INDEX ix_doc_embed_project ON document_embeddings (project_id);
CREATE INDEX ix_doc_embed_kind ON document_embeddings (doc_kind);
CREATE INDEX ix_doc_embed_hnsw ON document_embeddings
  USING hnsw (embedding vector_cosine_ops);    -- HNSW 索引 (pgvector 0.5+)
```

### C.6 ⚠️ 关键阻塞：pgvector extension 未安装

**当前 Postgres 17 Windows 服务里 `pg_available_extensions` 不含 vector**。

**3 个解决路径**：

| 选项 | 难度 | 时间 | 适合 |
|------|------|------|-----|
| **A. 本地编译 pgvector for Win Postgres 17** | 高 | 半天 | 一次性投入 |
| **B. 换 Docker pgvector/pgvector:pg17 容器** | 中 | 1h | 长期推荐（部署一致性） |
| **C. 不用 pgvector，改 Chroma 本地** | 低 | 1h | demo 期快速跑通 |

**🎯 推荐**：**B Docker pgvector**（如果你愿装 Docker Desktop）/ **C Chroma**（如果想最快跑通）

---

## D · Memory 系统分层方案

### D.1 五层记忆模型

```
┌──────────────────────────────────────────────┐
│ L1 Working Memory                            │
│ 当前对话 + 当前任务的临时变量                  │
│ Storage: Python in-process                   │
│ TTL: 单次 run() 调用                         │
├──────────────────────────────────────────────┤
│ L2 Short-term Memory                         │
│ 当前 session 的对话历史                       │
│ Storage: Redis agent_session:{u}:{s}         │
│ TTL: 24h (现状)                              │
├──────────────────────────────────────────────┤
│ L3 Episodic Memory                           │
│ 跨 session 的对话事件 + 工具调用结果           │
│ Storage: agent_conversation_logs + 新表       │
│ TTL: 永久（带向量化）                         │
├──────────────────────────────────────────────┤
│ L4 Semantic Memory                           │
│ 用户全部 KP + Notes + 课程内容               │
│ Storage: 既有表 + document_embeddings        │
│ TTL: 永久（用户主动删除）                     │
├──────────────────────────────────────────────┤
│ L5 Procedural / Identity Memory              │
│ 用户画像 + 学习偏好 + 长期目标 + 关键事件      │
│ Storage: users.agent_memory JSONB           │
│ TTL: 永久（Agent 主动 save_memory）          │
└──────────────────────────────────────────────┘
```

### D.2 L3 Episodic 新表设计

```sql
CREATE TABLE agent_episodes (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  session_id UUID,
  
  -- 事件类型
  event_kind VARCHAR(30),         -- conversation_summary / tool_outcome / observation / milestone
  
  -- 事件摘要（LLM 后处理）
  summary TEXT NOT NULL,          -- 短摘要，用于召回
  detail JSONB DEFAULT '{}',      -- 详细数据
  
  -- 涉及实体
  ref_kp_ids UUID[],
  ref_note_ids UUID[],
  ref_project_id UUID,
  
  -- 情绪/重要性（influence 检索权重）
  importance SMALLINT DEFAULT 5,  -- 0-10
  emotional_tone VARCHAR(20),     -- positive / negative / neutral
  
  -- 向量化（关联 document_embeddings 行）
  embedding_id UUID,
  
  occurred_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### D.3 自动行为记录（PRD 行 25 落地）

| 用户行为 | Agent 自动写 episodes | 实现位置 |
|---------|--------------------|---------|
| 连续 3 天未学习 | observation: "user_inactive_3d" | Celery beat 每日扫描 |
| 同一 KP 闪卡连续 3 次答错 | observation: "kp_struggle:{kp_id}" | fsrs_service.review hook |
| 训练题正确率 < 50% | observation: "weak_in_{subject}" | training_service.submit_answer |
| 考试前 7 天 | observation: "exam_approaching" | Celery beat |
| 连击 7/14/30 天 | milestone: "streak_{n}d" | checkin / pomodoro hook |
| 完成一个 phase | milestone: "phase_completed" | project_tree_service.mark_completed |
| 切换学习节奏（夜读→早起等）| observation: "schedule_shift" | pomodoro_records 分析 |

### D.4 Memory 检索策略

每次 `agent_service.run()` 启动时按优先级注入 context：

```
1. L5 Identity Memory  →  直接拼进 system prompt（已有）
2. L3 Episodic 召回    →  按当前 message 检索 top-3 重要 episodes
3. L4 Semantic 召回    →  按当前 message 检索 top-5 KP/notes
4. L2 Short-term       →  最近 N 条对话（已有，20 条）
5. L1 Working          →  本轮 run 临时变量
```

---

## E · 推理与规划方案

### E.1 当前 ReAct 模式（v0.27）

```python
for _ in range(MAX_TOOL_ROUNDS=5):
    choice = await llm.call_with_tools(messages, tools)
    if choice.has_tool_calls:
        for tc in choice.tool_calls:
            result = await dispatch_tool(tc)
            messages.append(result)
    else:
        break
# 然后 stream final reply
```

**不足**：
- 一次 LLM 调用同时决定"思考 + 选工具"，复杂任务在 5 轮内做不完
- 工具结果不反思，错了照常走
- 无验证步骤

### E.2 升级目标：Plan-Execute-Verify-Reflect 4 阶段

```
User: "帮我安排接下来一周的复习计划"

┌─────────────────────────────────────┐
│ STAGE 1 · PLAN                      │
│ LLM 不调工具，只产 plan JSON：       │
│ {                                   │
│   "goal": "...",                    │
│   "steps": [                        │
│     {"tool": "get_full_context"},   │
│     {"tool": "diagnose_learning"},  │
│     {"tool": "plan_study_schedule"} │
│   ]                                 │
│ }                                   │
├─────────────────────────────────────┤
│ STAGE 2 · EXECUTE                   │
│ 按 plan 顺序调工具，每一步把结果回填  │
├─────────────────────────────────────┤
│ STAGE 3 · VERIFY                    │
│ LLM 检查结果是否满足 goal：           │
│ - 任务是否覆盖了所有薄弱学科？       │
│ - 时间分布是否合理？                 │
├─────────────────────────────────────┤
│ STAGE 4 · REFLECT (失败时)           │
│ 如果 VERIFY 失败：                   │
│ - 重写 plan                          │
│ - 限制最多 reflect 2 次              │
└─────────────────────────────────────┘
```

### E.3 何时走 ReAct vs Plan-Execute？

| 用户输入特征 | 走哪个 |
|------------|--------|
| "今天数学怎么样" | ReAct（单工具） |
| "帮我安排一周复习" | Plan-Execute |
| "我做错了这道题怎么办" | ReAct → 转 Guidance |
| "新建一个 X 项目" | Plan-Execute（preview + confirm + tree gen） |
| "考前怎么冲刺" | Plan-Execute |

通过简单的**任务复杂度分类器**（LLM 一次调用 输出 simple/complex）决定。

### E.4 安全出口（PRD 行 244-248 落地）

| 安全出口 | 端点 | 用户操作 |
|---------|-----|---------|
| **重新生成** | `POST /v1/agent/regenerate` | 把上一次 user message 重发，丢上次的 assistant reply |
| **追加修正** | `POST /v1/agent/chat` 加 `correction_to: msg_id` | 把"对刚才那条 → 我的修正是..."作为新消息 |
| **撤销** | `POST /v1/agent/messages/{id}/undo` | 标记某条消息废弃 + 后续 context 不再使用 |

---

## F · 工具生态扩展

### F.1 当前 14 工具分类

| 类别 | 工具 |
|------|------|
| 上下文 | get_full_context |
| 诊断 | diagnose_learning |
| 学习计划 | plan_study_schedule · manage_tasks |
| 内容创建 | manage_knowledge_points · generate_note · import_curriculum |
| 训练 | start_training · generate_mock_exam |
| 考试 | manage_exams |
| 项目 | create_project_from_dialog · generate_project_tree |
| 状态 | set_agent_state |
| 记忆 | save_memory |

### F.2 RAG 启用后新增工具（4 个）

| 新工具 | 用途 |
|--------|------|
| `retrieve_knowledge` | 主动 RAG 检索（用户当前学习内容相关的 KP/notes） |
| `cite_source` | 在回答中明确引用某个 KP/note，前端显示卡片 |
| `summarize_session` | 把当前对话整理成 episode，写入 L3 记忆 |
| `verify_answer` | 验证 Agent 自己上一条回答是否准确（self-critique） |

### F.3 Procedural Tool Learning（后期）

- 跟踪每个工具的成功率（用户后续是否撤销 / 追加修正）
- 工具调用模式入库 → 后期可用 prompts cache + few-shot
- 没掌握时调"基础工具"，掌握后调"组合工具"

---

## G · 可观测性 (L7)

### G.1 必须建立的 4 个监控

| 监控项 | 工具 | 阈值 |
|--------|------|------|
| **Token 成本** | TokenUsage 表 + admin dashboard | 单用户日 > 200k 报警 |
| **Tool 调用延迟** | 新表 agent_tool_traces | p95 > 5s 标红 |
| **幻觉率** | 用户撤销/追加修正比例 | > 15% 告警 |
| **LLM 错误率** | logger error count | > 1% 告警 |

### G.2 新表 `agent_tool_traces`

```sql
CREATE TABLE agent_tool_traces (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  session_id UUID,
  
  tool_name VARCHAR(50),
  arguments JSONB,
  result_summary TEXT,           -- 截断
  
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  latency_ms INTEGER,
  
  status VARCHAR(20),            -- success / error / timeout
  error_message TEXT,
  
  tokens_in INTEGER,
  tokens_out INTEGER,
  cost_usd NUMERIC(10, 6),
  
  -- 用户后续是否撤销/追加（标记此 tool 是否成功）
  was_helpful BOOLEAN,           -- 默认 NULL，用户反馈后写
  
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_tool_traces_user ON agent_tool_traces (user_id);
CREATE INDEX ix_tool_traces_tool ON agent_tool_traces (tool_name);
CREATE INDEX ix_tool_traces_latency ON agent_tool_traces (latency_ms DESC);
```

### G.3 Eval Pipeline（v0.28 后）

```
Test set: 50 个真实用户对话 + 标注 expected outcomes
  │
  ▼
每次 LLM prompt / tool 更新 → 跑 eval
  │
  ▼
对比上一版本: pass_rate ↑ / latency ↓ / cost ↓
```

测试集示例：
- "我数学函数还没学懂" → 应调 diagnose_learning + 输出苏格拉底引导
- "帮我规划期末复习" → 应调 plan_study_schedule + 输出周计划
- "这道题怎么做" → 应**拒答 + 引导式提问**（PRD 不直接给答案）

---

## H · PRD 补全需求清单

下面这些 PRD 没写或者不够细，**需要你确认**：

### H.1 RAG 范围决策

```
Q1. 检索源是否包括官方课程章节？
  □ A. 仅检索用户自己的 KP/notes
  □ B. + 官方课程章节
  □ C. + 跨用户匿名总结（"做错同类题的用户 X 这么解决"）

Q2. 是否做跨学科横向检索？
  □ A. 严格按 subject 隔离
  □ B. 允许跨学科召回（如学化学时也召回相关物理 KP）

Q3. 内容修改后是否实时重建 embedding？
  □ A. 同步重建（写入耗时增加）
  □ B. Celery 异步重建（5min 延迟）
  □ C. 每日批量重建（24h 延迟）
```

### H.2 Memory 策略

```
Q4. agent_memory 长期画像由谁写？
  □ A. 只在 Agent 主动调 save_memory 时
  □ B. 每次对话结束 LLM 自动后处理生成
  □ C. 关键事件（连击/考试/项目完成）触发

Q5. 行为信号自动捕获哪些事件？（多选）
  □ 同一 KP 连续答错
  □ 连续 N 天未学习
  □ 考试倒计时 < 7 天
  □ 连击突破 3/7/14/30 天
  □ 一个 phase 完成
  □ 学习节奏切换

Q6. Episodes 保留多久？
  □ A. 永久
  □ B. 90 天，重要的（importance≥7）永久
  □ C. 30 天，重要的（importance≥7）永久
```

### H.3 推理模式

```
Q7. 是否启用 Plan-Execute-Verify-Reflect？
  □ A. 启用，简单任务降级 ReAct，复杂任务走完整 4 阶段
  □ B. 仅启用 Plan-Execute（不要 Verify/Reflect 节省成本）
  □ C. 保持 ReAct，加大 MAX_TOOL_ROUNDS 到 10

Q8. 复杂度分类器用什么？
  □ A. 关键词规则（便宜）
  □ B. LLM 一次小调用（准确但贵）

Q9. 安全出口（PRD 行 244-248）：哪些做？
  □ 重新生成
  □ 追加修正
  □ 撤销
```

### H.4 引用与验证

```
Q10. 是否强制 Agent 回答时引用来源？
  □ A. 强制（每条回复必须 cite 至少 1 个）
  □ B. 推荐（系统提示要求，但不强制）
  □ C. 不要求

Q11. self-critique 何时跑？
  □ A. 每条 assistant 回复后跑一次
  □ B. 仅 Plan-Execute 模式跑
  □ C. 不跑
```

### H.5 LLM Provider 与成本

```
Q12. 主 LLM 用 DeepSeek-V3 / Claude / GPT-4o？
  □ 当前默认 DeepSeek-Chat
  □ Plan 阶段用 DeepSeek，Verify 用 Claude？
  □ 完全切 Claude opus-4-7（CLAUDE.md 提到）

Q13. 嵌入模型？（见 C.2 表）
  □ OpenAI text-embedding-3-small（推荐）
  □ BGE-large-zh
  □ DashScope
  □ M3E

Q14. 月预算上限？
  □ < ¥500
  □ ¥500 - 3000
  □ 不设上限

Q15. 单用户日 Token 上限？
  □ 当前 200,000 token/day
  □ 调高到 500,000？
```

### H.6 部署与安全

```
Q16. pgvector 安装路径？
  □ A. 本地 Postgres 17 编译装 pgvector（复杂）
  □ B. 装 Docker Desktop + 切 pgvector/pgvector:pg17 容器（推荐）
  □ C. 不用 pgvector，用 Chroma 本地（最快跑通）

Q17. 内容安全？
  □ A. 集成阿里云内容安全 API（中文优）
  □ B. 关键词 + 黑名单
  □ C. 暂不做，等出问题再加

Q18. PII 过滤？（用户输入身份证 / 手机号识别）
  □ A. 正则提取后 mask
  □ B. 不处理
```

---

## I · 框架选型决策

### I.1 不引入重型框架的理由

**❌ LangChain / LlamaIndex 不引入**：
- 当前代码已经有清晰的 LLM client + tool registry + ReAct loop
- LangChain 学习曲线陡，黑盒多
- 对小项目 over-engineered

**✅ 自建轻量层 + 选择性引入**：

| 能力 | 自建 / 第三方 | 理由 |
|------|-------------|------|
| LLM 调用 | 自建 LLMClient（已有） | DeepSeek/OpenAI/Anthropic 一层抽象足够 |
| Embedding | OpenAI SDK 直调 | 一个 endpoint 不需要框架 |
| Vector store | pgvector（首选）/ Chroma | 都不需要框架包装 |
| Reranker | bge-reranker via HF transformers（如果做）| 简单调用 |
| Chunking | 自建（小项目内容简单）| <100 行代码 |
| Observability | 自建 agent_tool_traces 表 + Postgres 查询 | 数据量小用不上 Sentry/Grafana |
| Eval | 自建 pytest fixtures + 50 case 标注 | 简单 |

### I.2 必须引入的依赖

```python
# requirements.txt 新增
openai>=1.58.1                  # 已有，复用
pgvector>=0.3.6                 # 已有，启用
tiktoken>=0.5                   # token 计数（chunking 用）
numpy>=1.26                     # 向量运算 fallback
# 如果 reranker 本地化：
sentence-transformers>=2.7      # bge-reranker
# 如果做 PII：
presidio-analyzer               # PII 识别（中文支持一般）
```

---

## J · 分期实施路径（4 个 Sprint）

### Sprint 1 · RAG MVP（1-2 天）

**目标**：能从用户 KP/Notes 检索注入 chat 流

```
☐ 1. 启用 pgvector extension（见 Q16 决策）
☐ 2. migration 026: document_embeddings 表
☐ 3. 新增 app/services/embedding_service.py
   - resolve_provider()
   - embed_text(text) -> list[float]
   - embed_batch(texts) -> list[list[float]]
☐ 4. 新增 app/services/rag_service.py
   - upsert_doc(doc_id, kind, content, metadata)
   - search(user_id, query, top_k, filter)
☐ 5. Celery task: backfill_embeddings_for_user
   - 把现有 190 KP / 15 notes / 117 chapters 入库
☐ 6. 接入 agent_service.run
   - 在 build_system_prompt 后追加 retrieved context
☐ 7. 新工具 retrieve_knowledge（让 Agent 自己决定何时召回）
☐ 8. pytest: test_rag_basic.py
```

### Sprint 2 · Memory & 自动行为捕获（2 天）

```
☐ 9.  migration 027: agent_episodes 表
☐ 10. app/services/episodic_memory_service.py
   - record_event(user_id, kind, summary, ref_*)
   - retrieve_relevant(user_id, query, top_k)
☐ 11. 在 7 个业务事件挂自动 record:
   - kp 答错 N 次（fsrs_service）
   - 连续 X 天未学习（celery beat）
   - 考试 < 7 天（celery beat）
   - 连击突破阈值（checkin / pomodoro）
   - phase 完成（project_tree_service）
   - SS 完成（studyspace_service）
   - 重要里程碑
☐ 12. agent_service.run 注入 top-3 相关 episodes
☐ 13. LLM 后处理：每次对话结束后跑 summarize → 写 episodes
☐ 14. pytest: 行为信号正确触发
```

### Sprint 3 · 推理升级 + 安全出口（2 天）

```
☐ 15. app/services/planner_service.py
   - classify_complexity(message) -> simple|complex
   - plan(message, ctx) -> Plan JSON
   - execute(plan, db) -> step_results
   - verify(plan, results) -> ok|reason
☐ 16. 在 agent_service 中分流 simple → ReAct，complex → Plan
☐ 17. 端点：POST /v1/agent/regenerate
☐ 18. 端点：POST /v1/agent/messages/{id}/undo
☐ 19. 端点：POST /v1/agent/messages/{id}/correct
☐ 20. migration 028: agent_tool_traces 表
☐ 21. 在 dispatch_tool 外层 wrap trace 记录
☐ 22. admin dashboard 加 tool latency + helpful_rate 维度
```

### Sprint 4 · Eval + 安全 + Cite（1-2 天）

```
☐ 23. tests/eval/test_agent_quality.py
   - 50 case 真实对话标注
   - 跑 LLM-as-judge 评分
☐ 24. 新工具 cite_source
   - retrieved doc 注入到 reply 末尾以 [1][2] 标记
☐ 25. 新工具 verify_answer
   - 调用第二个 LLM 独立验证 reply 是否事实正确
☐ 26. 内容安全集成（按 Q17 决策）
☐ 27. 更新 SPEC.md 到 v0.28
☐ 28. 写运维 runbook
```

---

## K · 工作量估算

| Sprint | 后端代码 | LLM 调试 | 测试 | 文档 | 合计 |
|--------|---------|---------|------|------|------|
| 1 · RAG MVP | 4h | 2h | 2h | 1h | **1 工作日** |
| 2 · Memory | 5h | 2h | 2h | 1h | **1.5 工作日** |
| 3 · Plan/Reflect | 6h | 3h | 2h | 1h | **2 工作日** |
| 4 · Eval/Safety | 4h | 3h | 3h | 2h | **1.5 工作日** |
| **总计** | | | | | **~ 6 工作日** |

---

## L · 我对你的建议

1. **先解决 pgvector 阻塞**（Q16 决策）→ 这是 RAG 一切的前提
2. **回答 H 节 18 个补全问题** → 我按答案调整 Sprint 计划
3. **从 Sprint 1 开始**，RAG MVP 跑通 = 立刻能感受到 Agent "记得用户在学什么"
4. **不引入 LangChain** → 当前架构清爽，引入后调试成本暴涨

---

## M · 等你的回复

**最小决策集（让 Sprint 1 能起跑）**：

```
Q1 (RAG 范围)      = ?
Q13 (嵌入模型)     = ?
Q14 (月预算)       = ?
Q16 (pgvector)     = ?
```

**完整决策（让 Sprint 1-4 全规划好）**：回答 Q1-Q18 全部。

或者说"按推荐全选"，我用文档里我的推荐执行。

---

**报告完。**
