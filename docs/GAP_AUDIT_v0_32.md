# v0.32 → 成熟版本 · 深度差距审计

> 2026-05-24 · 当前状态：后端 v0.32 / 152 API / 32 tests / Agent 全栈完整
> 审计维度：① PRD 还差什么 · ② 大厂工程标准还差什么 · ③ Agent 能力深化空间 · ④ 学习产品独特深化空间

---

## 一、PRD 对照 · 七层架构残缺清单

### L1 知识来源层 · 完整度 90%

| PRD 要求 | 实现 | 状态 |
|---|---|---|
| 官方课程预设系统 | curriculum_chapters (117 条) | ✅ |
| 用户自主框架（图片/PDF/文字粘贴） | files + Note source_type | ✅ 文字+图片 OCR / 🟡 PDF 解析 |
| 项目对话式初始化 | onboarding_service + create_project_from_dialog | ✅ |
| 官方 vs 自主笔记 UI 区分 | notebook_origin 字段（official/user_project） | ✅ |

**残缺**：
- 🟡 **PDF 解析链路缺失** — 上传 PDF 没有专用 parser，目前只走 image OCR 路径
- 🟡 **教材版本管理** — curriculum_chapters 有 textbook_version 字段但没有切换机制（人教/北师/苏教等多版本）

### L2 知识加工层 · 完整度 65%

| PRD 要求 | 实现 | 状态 |
|---|---|---|
| StudySpace 自动笔记沉淀 | studyspace_service 时间线 | ✅ 时间线骨架 |
| Agent 路线挖掘 → 知识点大纲 → 逐个讲解 → 随堂测验 → 总结 | system_prompt 提了规则 | 🔴 **prompts 引导但没流程编排器** |
| 知识点卡片自动生成（蓝/紫/金）| KP + ProjectTreeNode.tier | ✅ tier 字段 / 🟡 自动着色规则 |
| 难点自动标记 + 优先级 | KP.bloom_level + is_key | 🟡 字段有，自动入队没 |
| 知识图谱可视化（Mermaid） | note.graph_mermaid | ✅ |
| 树状知识路径（项目页展示） | ProjectTreeNode 树 | ✅ 数据 / 🟡 交互前端 |

**残缺（严重）**：
- 🔴 **课程随堂测验自动生成缺**：PRD 行 217-223 明确写"每个知识点讲解后 → 随堂测验"，目前 SS 流程仅靠 system prompt 引导 LLM 自己出题；没有专用 `auto_quiz_after_kp` 服务把测验题写进 training_questions 表。
- 🔴 **学习路线图挖掘缺**：PRD 行 207-208 "Agent 挖本课学习路线图和知识图谱"，目前没有独立 service / 提示词把官方课程拆成结构化路线节点（只有项目树是用户级，课程级没有）。
- 🟡 **难点优先级队列缺**：bloom_level 写进 KP，但没有"重点练习队列"表 / 调度器把 hard KP 优先排进每日任务。
- 🟡 **蓝/紫/金自动着色规则缺**：tier 是手动设的，没有 LLM 推理"这个 KP 是金卡（核心高难）"的逻辑。

### L3 记忆强化层 · 完整度 75%

| PRD 要求 | 实现 | 状态 |
|---|---|---|
| AI 闪卡自动生成 | fsrs_service.create_card + SS hook | ✅ |
| 学完笔记 **24h 内自动推送首次复习** | ❌ **完全缺失** | 🔴 |
| FSRS 间隔重复 | py-fsrs + fallback | ✅ |
| 错题本三维分类（知识点/题型/错误原因） | mistake_service + question_type | 🟡 "错误原因"标签缺 |
| 闪卡 3 类（概念/公式/应用） | Flashcard.card_type | ✅ |

**残缺（严重）**：
- 🔴 **24h 首次复习推送完全没实现**。PRD 行 311 黑字写明，对抗遗忘曲线的核心机制。需要：
  - `create_card` 时把 `due_date = today + 1 day`
  - Celery beat 每小时扫描"24h 内学过但未复习"的 KP，推送 notification
- 🟡 **错题"错误原因"分类缺**：现在只分知识点 + 题型，"粗心 / 概念不清 / 方法不会"这个维度需要 LLM grade 时归类（grade_answer prompt 改）。
- 🟡 **错题优先级高于普通闪卡未体现**：PRD 行 344 写"错题优先级高于普通闪卡"，目前 daily_task 排序按 priority，但闪卡和错题混在 due_date 队列中，没有显式权重。

### L4 主动训练层 · 完整度 50%

| PRD 要求 | 实现 | 状态 |
|---|---|---|
| AI 分层出题（记忆/理解/应用/分析） | training_service.compose_quiz + BLOOM_TO_QTYPE | 🟡 按 KP.bloom_level 选，但同一会话没多层 |
| **自适应难度（最近发展区）** | ❌ | 🔴 |
| **交错练习模式** | ❌ | 🔴 |
| **费曼输出练习** | ❌ | 🔴 |

**残缺（严重）**：
- 🔴 **自适应难度完全没**：PRD 行 364 "根据答题结果动态调整出题层次"。现在 compose_quiz 出完 5 题就结束，不根据正确率往上/下调。需要：
  - submit_answer 后更新 user_skill_level
  - 下次出题时按 user_skill_level 选 bloom_level
- 🔴 **交错练习完全没**：PRD 行 367-369 "混合当前 + 历史相关知识点"。compose_quiz 现在只在指定 KP 池里出，没"相关历史 KP"召回逻辑。可以基于 RAG 召回 + bloom_level 邻近度做。
- 🔴 **费曼输出完全没**：PRD 行 372-379 "请用最简单的语言向不懂的人解释……AI 评估准确性"。完整缺失，需要：
  - 新表 `feynman_attempts` (kp_id, user_explanation, ai_eval, gaps[])
  - LLM prompt 做 grading + gap detection
  - 引导用户补缺

### L5 引导答疑层 · 完整度 60%

| PRD 要求 | 实现 | 状态 |
|---|---|---|
| 苏格拉底引导 | guidance_service + prompts | ✅ |
| **绝对禁止直接给答案（系统级强制）** | 仅 prompt 提示 | 🟡 |
| **最多 5 轮限制** | ❌ | 🔴 |
| 知识库联动答疑 | _fetch_kp_context | ✅ |

**残缺**：
- 🔴 **5 轮上限强制缺**：PRD 行 396 "最多 5 轮引导，超出给提示词"。代码里 chat 端点没轮次计数，理论上可以聊到天荒地老。需要 `MAX_GUIDANCE_TURNS=5` + 第 6 轮自动给"提示词卡片"。
- 🟡 **"禁止给完整答案"靠 prompt 不可靠**：高危场景需要 output filter — 用第二个 LLM call 判定"上一条 Agent 回复里有没有直接给完整答案"，有就 reject + 重生。

### L6 时间管理层 · 完整度 85%

| PRD 要求 | 实现 | 状态 |
|---|---|---|
| 番茄钟 25min + 自定义 | pomodoro_records + immersion_sessions | ✅ |
| 番茄钟自动记录到知识点/学科 | PomodoroRecord 字段 | ✅ |
| 每日任务清单自动生成 | task_service.generate_today | ✅ |
| 考试倒计时影响计划密度 | exam countdown | 🟡 显示有，密度调整逻辑无 |

**残缺**：
- 🟡 **考试越近计划越密**：PRD 行 426 写"自动影响学习计划密度"。当前 plan_study_schedule 不读考试 deadline。修：在 plan 工具里检查最近考试，距离 <14 天则任务密度 ×1.5。

### L7 规划与洞察层 · 完整度 55%

| PRD 要求 | 实现 | 状态 |
|---|---|---|
| AI 学习计划生成 | plan_study_schedule 工具 + Plan-Execute | ✅ |
| 进度仪表盘 | profile_service.get_insights | ✅ 数据 / 🟡 多维聚合 |
| 知识点掌握度地图（按布鲁姆层次） | mastery_status by bloom | 🟡 数据有，按 bloom 切片缺 |
| 学习时长趋势（番茄钟数据） | progress_service | ✅ |
| 连续打卡记录 | streak_days | ✅ |
| 薄弱点分析 | diagnose_learning 工具 | ✅ |
| **AI 周复盘报告（每周日自动生成）** | reflection 表有，自动生成无 | 🔴 |
| **"如果现在考试哪些点最危险"** | ❌ | 🔴 |

**残缺**：
- 🔴 **周复盘自动生成完全没**：PRD 行 453-458。reflection 表只支持用户手动写。需要：
  - Celery beat 每周日 20:00 跑 `generate_weekly_reflection(user_id)`
  - LLM 整理：本周新 KP 数 / 闪卡完成率 / 薄弱 Top3 / 下周建议
  - 写入 reflection 表 + 推 notification
- 🔴 **"如果现在考试"模拟评估缺**：PRD 行 451。需要新工具 `simulate_exam_readiness(exam_id)` — 按掌握度 + 错题率算预测分。

### 跨层 · Agent 角色升级

| PRD 要求 | 实现 | 状态 |
|---|---|---|
| Agent 项目初始化对话式建模 | onboarding + create_project_from_dialog | ✅ |
| Agent 主导 StudySpace 流程 | system prompt | 🟡 prompt 引导，没流程状态机 |
| Agent 三层入口（首页对话/悬浮球/控制台） | API 后端中性 | ✅ 后端就绪 |
| **功能不说话，Agent 才说话** | 大部分遵守 | 🟡 仍有少量 service 直接 return 模板文案 |

---

## 二、大厂工程标准 · 生产级 gap

### 2.1 可观测性 · 完整度 40%

| 大厂标准 | 知曜现状 |
|---|---|
| 结构化日志（JSON line + trace_id） | 🔴 Python logger 文本，没 trace_id |
| OpenTelemetry 链路追踪 | 🔴 |
| Prometheus metrics endpoint | 🔴 |
| Sentry / 异常自动上报 | 🔴 |
| 慢查询日志 | 🔴 |
| N+1 检测 | 🔴 |
| 数据库连接池监控 | 🔴 |
| Redis 命中率 | 🔴 |
| **agent_tool_traces 工具调用 trace** | ✅ v0.30 |
| **token_usage 成本 trace** | ✅ |

### 2.2 安全 · 完整度 55%

| 大厂标准 | 现状 |
|---|---|
| JWT 校验 | ✅ |
| 限流（IP + 用户） | 🟡 仅 IP，没有 per-user |
| HTTPS / HSTS / Secure cookies | 🔴 (部署期) |
| CSP / X-Frame-Options / X-Content-Type-Options | 🔴 |
| CSRF token | 🔴（Bearer 模式可豁免，但 admin 可能要） |
| SQL 注入防护 | ✅（SQLAlchemy 参数化） |
| XSS 防护 | 🟡 后端 JSON，前端责任 |
| **PII mask（身份证/手机/银行卡）** | ✅ v0.31 |
| 内容安全（涉政/涉黄/暴力） | 🔴 |
| Prompt injection 防护 | 🔴 |
| 密码强度规则 | 🟡 |
| 邮箱验证 | 🔴 |
| 手机号短信验证 | 🔴 |
| OAuth（微信/Apple/QQ） | 🔴 |
| 密码重置流程 | 🔴 |
| 账号注销 + 数据删除（GDPR/个保法） | 🔴 |
| 数据导出（用户主权数据） | 🔴 |
| 加密静态存储（at rest） | 🔴 |
| 审计日志（admin 操作） | 🟡 admin_user 表 |
| 后台权限分级 | 🔴 |

### 2.3 可靠性 · 完整度 50%

| 大厂标准 | 现状 |
|---|---|
| /health 健康检查 | ✅ 基础版 |
| Readiness vs Liveness 分离 | 🔴 |
| 优雅关闭 | 🟡 FastAPI 默认 |
| Celery 死信队列 | 🟡 max_retries 有 |
| Celery 任务超时 | 🟡 部分有 |
| 数据库连接池配置 | 🟡 pool_size=10 max_overflow=20 |
| 数据库读写分离 | 🔴 |
| Redis 哨兵 / 集群 | 🔴 |
| 数据库每日备份 | 🔴 |
| 跨区域 / 跨可用区 | 🔴 |
| 蓝绿/金丝雀部署 | 🔴 |
| **Docker compose 一键启动** | ✅ v0.28 |
| K8s manifests | 🔴 |
| CI/CD pipeline | 🔴 |

### 2.4 测试与质量 · 完整度 35%

| 大厂标准 | 现状 |
|---|---|
| 单元测试 | 🟡 32 个（核心模块覆盖率 60%） |
| 集成测试 | 🟡 7 个（auth） |
| E2E 测试 | 🟡 手工 audit 脚本 |
| 性能 / 负载测试 | 🔴 |
| 安全扫描（SAST/DAST） | 🔴 |
| 依赖漏洞扫描 | 🔴 |
| Eval 自动化（LLM 输出质量） | 🟡 v0.31 case 集已写但 skip |
| Mutation testing | 🔴 |
| Coverage gate（CI） | 🔴 |

### 2.5 用户体验工程 · 完整度 35%

| 大厂标准 | 现状 |
|---|---|
| SSE 流式 | ✅ |
| 用户中断流（stop button） | 🔴 |
| 请求幂等（idempotency-key） | 🔴 |
| 多语言 i18n | 🔴 |
| 时区处理 | 🟡 |
| 推送通知（Web + 移动） | 🟡 Expo push token 有，Web Push 无 |
| Webhook 出站 | 🔴 |
| 客户端版本管理 + 强制升级 | 🔴 |
| 客户端崩溃上报 | 🔴 |
| 离线模式 + 同步 | 🔴 |

---

## 三、Agent 能力 · 对标 SOTA 的深化空间

### 对标对象：OpenAI GPT / Anthropic Claude / Notion AI / Cursor / 元宝 / 豆包

### 3.1 已经做的（接近 SOTA）

- ✅ ReAct + Plan-Execute-Verify-Reflect（业内主流）
- ✅ 跨 session 长期记忆（episodic memory，胜过大部分对话产品）
- ✅ RAG with HNSW（标准做法）
- ✅ 工具调用 + 流式 + thinking 事件
- ✅ 用户行为信号自动捕获（6 类 hook，比 ChatGPT 强）
- ✅ Safety exits（regenerate/correct/undo）
- ✅ Prompt cache 计费检测
- ✅ Multi-LLM provider 抽象

### 3.2 SOTA 标杆但还差的

| # | 能力 | 标杆 | 知曜 |
|---|------|------|------|
| 1 | **多步推理 UI 透出**（show reasoning） | Claude / o1 | 🔴 reasoning_content 已捕获但前端没透出 |
| 2 | **并行工具调用** | GPT-4o / Claude Sonnet 3.5 | 🔴 串行 |
| 3 | **工具调用人在回路**（高危操作 confirm） | Cursor / Lindy | 🔴 |
| 4 | **代码执行 sandbox** | ChatGPT Code Interpreter | 🔴（学习场景需求待评估） |
| 5 | **画板协同编辑**（实时） | Notion / Figma | 🟡 表有，WebSocket 无 |
| 6 | **跨 session 对话搜索** | Claude search | ✅ 已有 |
| 7 | **对话分支（branching）** | ChatGPT / Claude | 🔴 |
| 8 | **对话导出 Markdown / PDF** | Claude / 豆包 | 🔴 |
| 9 | **Reranker (cross-encoder)** | Anthropic Contextual Retrieval | 🔴（用 RAG 直接出，没 rerank） |
| 10 | **Long context Contextual Retrieval** | Anthropic 2024-09 | 🔴 |
| 11 | **GraphRAG**（实体关系图召回） | Microsoft GraphRAG | 🔴 |
| 12 | **Self-RAG / Reflection RAG** | 业内 SOTA | 🟡 verify 类似但不针对 RAG |
| 13 | **Citation enforcement + 视觉化** | Perplexity / Claude | 🟡 prompt 提示，前端展示无 |
| 14 | **Tool fallback / 重试**（指数退避） | LangChain Agents | 🟡 try/except，无智能重试 |
| 15 | **Conversation memory consolidation**（LLM 周期性总结整理 episodic） | Letta (MemGPT) | 🔴 |
| 16 | **Procedural memory**（工具使用模式学习） | 计划文档 K-3 提了 | 🔴 |
| 17 | **多 Agent 协作** | AutoGPT / CrewAI | 🔴 |
| 18 | **Voice 输入** | OpenAI Realtime | 🔴 |
| 19 | **Multi-modal 真视觉理解** | GPT-4o / Claude | 🟡 OCR 仅文字（无图片关系/结构理解） |
| 20 | **结构化输出 schema 强制** | OpenAI JSON mode / function calling strict | 🟡 部分 |

### 3.3 大厂级运营基础设施

| # | 能力 | 知曜 |
|---|------|------|
| 1 | A/B test 框架 | 🔴 |
| 2 | Feature flag | 🔴 |
| 3 | Cohort 分析 | 🔴 |
| 4 | 用户漏斗 | 🔴 |
| 5 | LTV / 留存预测 | 🔴 |
| 6 | Prompt 版本管理 | 🔴（prompts 写死代码里，没版本管理） |
| 7 | Model 版本切换 | 🟡 env 配置可切，无 per-user routing |
| 8 | 灰度发布新 prompt | 🔴 |
| 9 | 用户反馈采集（👍👎/star） | 🟡 agent_tool_traces.was_helpful 字段有但没 API |
| 10 | 实时大盘（admin dashboard） | 🟡 admin v2 维度有 |

---

## 四、学习产品独特深化点（教育科学层）

### 4.1 PRD 已有但浅的 · 可深挖

| 维度 | 现状 | 深化方向 |
|------|------|----------|
| **遗忘曲线** | FSRS 算法 | 加 **个性化遗忘曲线**：每用户的 stability decay rate 不同，按学科分别校准 |
| **布鲁姆分层** | bloom_level 字段 | 加 **横向迁移测试**：在"应用层"题目里混入其他学科的等价问题，测真理解 |
| **苏格拉底引导** | 5 轮 prompt | 加 **认知漏洞图谱**：每轮失败用 LLM 标记是哪类漏洞（概念混淆/逻辑跳跃/计算粗心），积累成 misconception 表 |
| **错题归档** | 三维分类 | 加 **错题孪生题生成**：每条错题自动 LLM 生成 1-3 道同型异质题（不是变数字，是变情境） |
| **进度仪表盘** | 数据齐 | 加 **下一步推荐引擎**：根据掌握度地图 + FSRS + 考试日期算"下一个 30 分钟最该做什么" |

### 4.2 PRD 没写但教育意义大的

| # | 功能 | 学习科学依据 |
|---|------|-------------|
| 1 | **学习证据画像**（自己讲解→视频/语音录制） | 费曼法 + 双重编码（语言+动觉） |
| 2 | **同伴/AI 模拟同桌**（小组讨论模拟） | 社会建构主义（Vygotsky） |
| 3 | **元认知日记**（学了什么 / 还没懂什么 / 下一步） | 元认知策略培养 |
| 4 | **知识跨学科桥接**（"导数 ↔ 化学反应速率"） | 知识网络化 |
| 5 | **预测性自评**（学之前估能拿多少分） | 校准过度自信偏误 |
| 6 | **答题后置信度标注**（答完打 1-5 信心） | Confidence-weighted scoring |
| 7 | **学习风格画像**（视觉/听觉/动手/逻辑） | VARK 模型 |
| 8 | **休息提醒 + 注意力曲线建模** | 注意力节律 + 番茄钟数据 |
| 9 | **错题情绪标签** | 哪些错是焦虑 / 哪些是知识漏洞 |
| 10 | **同辈匿名对比**（你这个 KP 比 80% 同年级强） | 社会比较激励 |

### 4.3 学习闭环关键缺口（最影响"用户能学好"的）

1. 🔴 **24h 首次复习推送**（PRD 已写但没实现）— 直接对抗遗忘曲线，**影响留存最大**
2. 🔴 **课程内随堂测验自动生成**（PRD 已写但只在 prompt 里引导）— 影响"学完真懂了吗"
3. 🔴 **费曼输出**（PRD 已写完全没）— 检测真理解
4. 🔴 **自适应难度**（PRD 已写完全没）— 保持最近发展区
5. 🔴 **交错练习**（PRD 已写完全没）— 强化辨别
6. 🔴 **周复盘自动**（PRD 已写完全没）— 元认知
7. 🔴 **错题孪生题**（PRD 没写但教育意义大）— 真正闭合漏洞

---

## 五、最关键的 10 件事 · 离 1.0 的核心路径

按"对学习效果影响 × 实现成本"双维度排序：

| 优先级 | 任务 | 影响 | 工时 | PRD 行 |
|--------|------|------|------|--------|
| **P0** | 24h 首次复习推送（FSRS due_date 改为 +1d + Celery 扫描 + 推送） | 🔥🔥🔥 | 1d | 311 |
| **P0** | 课程随堂测验自动生成（SS 内 每 KP 讲完触发 quiz 生成） | 🔥🔥🔥 | 1.5d | 213-218 |
| **P0** | 周复盘自动生成（Celery 每周日 20:00 + LLM 整理） | 🔥🔥 | 1d | 453-458 |
| P1 | 费曼输出 + AI 评估（新表 + 工具 + prompt） | 🔥🔥 | 2d | 372-379 |
| P1 | 自适应难度（按答题正确率动态选 bloom_level） | 🔥🔥 | 1.5d | 364 |
| P1 | 交错练习（compose_quiz 混入历史 KP，基于 RAG） | 🔥🔥 | 1d | 367 |
| P1 | 错题孪生题生成 + "错误原因" 三类标签 | 🔥🔥 | 1.5d | 338-340 |
| P1 | 苏格拉底 5 轮强制 + 第 6 轮提示词卡片 | 🔥 | 0.5d | 396 |
| P2 | 蓝/紫/金 KP 自动着色（LLM 推理） | 🔥 | 0.5d | 243-245 |
| P2 | 考试越近计划越密（plan 工具读 exam deadline） | 🔥 | 0.5d | 426 |

**P0 三件 合计 ~3.5 工作日就能让"学习闭环"质量上一个台阶。**

---

## 六、按"产品成熟度"分期的落地路线

### Phase A · 学习闭环完整化（~7 工作日）

> 目标：把 PRD 七层每一层补到 90%+，让"学完→记住→真懂→不忘→进步"完整可见

- [ ] 24h 首次复习推送（Celery beat + Flashcard.first_review_at）
- [ ] 随堂测验自动生成（SS 内 hook + training_question 写入）
- [ ] 周复盘自动（Celery beat 每周日 + reflection 表 + 推送）
- [ ] 费曼输出（新表 feynman_attempts + tool + prompt + 评估）
- [ ] 自适应难度（user_skill_level 字段 + 出题选层逻辑）
- [ ] 交错练习（compose_quiz 加 interleave_ratio）
- [ ] 错题孪生题 + 错误原因分类
- [ ] 苏格拉底 5 轮强制
- [ ] 蓝/紫/金自动着色
- [ ] 考试密度调整

### Phase B · 大厂工程标准对齐（~10 工作日）

> 目标：从 demo 级到 production-ready

- [ ] 结构化日志 + trace_id（structlog + middleware）
- [ ] Sentry / 异常监控接入
- [ ] OpenTelemetry 链路追踪
- [ ] Prometheus /metrics endpoint
- [ ] 邮箱验证 + 密码重置流程
- [ ] OAuth 微信 + Apple 登录
- [ ] 账号注销 + 数据导出（个保法合规）
- [ ] 内容安全 API（自建关键词 + 阿里云接入）
- [ ] Prompt injection defense（检测 + reject）
- [ ] 数据库每日备份脚本（cron）
- [ ] 慢查询日志开启
- [ ] CI/CD pipeline（GitHub Actions）
- [ ] K8s manifests + Docker Hub 镜像
- [ ] 限流升级（per-user + per-endpoint）

### Phase C · Agent 能力 SOTA 化（~12 工作日）

> 目标：在国产 Agent 产品中处于第一梯队

- [ ] reasoning_content 透出给前端 + 折叠 UI 协议
- [ ] 工具调用人在回路（高危 op confirm）
- [ ] Reranker (bge-reranker-v2-m3 本地)
- [ ] Contextual Retrieval（query 上下文化重写）
- [ ] Conversation memory consolidation（LLM 周报式整理 episodes）
- [ ] Procedural memory（工具使用模式学习）
- [ ] 用户反馈 👍/👎 + tool_trace.was_helpful 接入
- [ ] Prompt 版本管理（prompts 拆 YAML + Redis cache）
- [ ] Feature flag（Unleash 或自建轻量）
- [ ] A/B test 框架（prompt 版本灰度）
- [ ] 对话分支（branch from a message）
- [ ] 对话导出 Markdown
- [ ] 用户中断 stream（cancel token）
- [ ] 多 LLM provider 智能路由（按场景选模型）

### Phase D · 教育科学深化（~15 工作日）

> 目标：超过现有教培产品的"学习科学"维度

- [ ] 个性化遗忘曲线（每用户每学科 stability 校准）
- [ ] 错题情绪标签 + 焦虑 vs 漏洞区分
- [ ] 元认知日记（每日 3 问）
- [ ] 预测性自评 + 校准曲线
- [ ] 答题置信度标注
- [ ] 学习风格画像（VARK）
- [ ] 同辈匿名对比（差分隐私统计）
- [ ] 跨学科桥接（导数↔化学速率，向量召回 + LLM 推理）
- [ ] 注意力曲线建模（pomodoro 数据 → 推荐学习时段）
- [ ] 认知漏洞图谱（苏格拉底失败模式归类）

### Phase E · 商业化与运营（~10 工作日）

- [ ] 订阅计费（微信支付 + 苹果内购）
- [ ] 套餐管理（免费 / Pro / 团购）
- [ ] 推荐奖励（邀请好友 → 知星）
- [ ] 学习排行榜（周/月 + 学科分榜）
- [ ] 成就系统完整化（解锁条件 / 进度）
- [ ] 装扮商店真正可买
- [ ] 客户支持工单系统
- [ ] 邮件 / 短信营销
- [ ] 转化漏斗大盘
- [ ] 留存大盘

---

## 七、综合评分

| 维度 | 满分 | 当前 |
|------|------|------|
| PRD 七层完整度 | 100 | **68** |
| 大厂工程标准 | 100 | **42** |
| Agent SOTA 能力 | 100 | **65** |
| 教育科学深度 | 100 | **35** |
| **综合（加权 40/25/20/15）** | 100 | **57** |

### 评分解读

- **57 分** = "Agent 基础设施完整 + 学习闭环骨架到位"
- **80 分** = "完整 PRD + 大厂工程 → 可商用"
- **90 分** = "Agent 能力 SOTA + 教育科学领先 → 行业第一梯队"

---

## 八、给你的判断建议

**如果目标是先跑 20-30 用户验证（PRD MVP 标准）**：
- 只做 Phase A 的 P0 三件（24h 推送 + 随堂测验 + 周复盘）= 3.5 天
- 加上前端联调
- → 可以验证"学完→自动复习→不遗忘"的核心闭环

**如果目标是 v1.0 商用上线**：
- Phase A 全做（~7 天）+ Phase B 关键项（邮箱/OAuth/注销/备份/Sentry，~5 天）
- → 12 工作日具备商用底气

**如果目标是行业第一梯队**：
- Phase A 全做 + Phase B 全做 + Phase C 关键项 = 25-30 工作日

**我的推荐节奏**：
1. 先 P0 三件（学习闭环最大短板）→ 立刻显著提升留存
2. 同时给前端时间联调 v0.32 现有功能
3. 拿到前端反馈和 20 用户行为数据后，再决定 Phase B/C 取舍

---

报告完。
