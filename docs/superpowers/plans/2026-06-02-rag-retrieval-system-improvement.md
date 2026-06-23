# 知曜 · 知识库检索系统工程优化方案

> 日期：2026-06-02 · 适配对象：zhiyao-backend RAG（v0.34）
> 定位：**这不是"换 Embedding 模型"项目，而是"检索系统工程优化"项目**——
> 用知曜自己的业务评测集驱动，靠分库路由降噪、问题改写对齐语义、多路召回扩覆盖、Reranker 提排序、持续评测保长效。
>
> 本方案基于通用 RAG 优化方法论，但**已对照知曜真实代码现状逐条核销**：凡知曜已落地或不适用的，明确标注，不重复提议；只在真缺口上展开。

---

## 一、为什么知曜的起点和通用方案不同

通用方案默认"从零搭检索体系"。知曜不是——v0.28~v0.34 已经把**评测地基、向量存储、嵌入选型**三件大事大体做完了。盲目照搬通用方案会重复造轮子。先做一次诚实的核销：

| 通用方案条目 | 知曜现状 | 结论 |
|---|---|---|
| 1. 业务评测集建设 | rag_retrieval_traces 表 + 零召回/伪召回采集 + masked_query 脱敏 + `export_annotation_worksheet.py` + `run_annotated_eval.py` + `annotation.py`(build_worksheet/worksheet_to_cases/merge_cases) + `metrics.py`(Recall@K/MRR/nDCG) + seed_retrieval_cases | **地基已建，差最后一公里**：标注集尚未真正标完、未记录基线、未按教育场景分类 |
| 2. Embedding 重新选型 | Q13 已锁定 BAAI/bge-m3 本地（1024 维，零云依赖，CPU torch） | **决策已做且非排行榜驱动**；但从未在知曜自己的评测集上 A/B 过候选模型 → 低优先级 |
| 3. 向量存储优化 | pgvector 0.8.2(pg17) + HNSW cosine + vector(1024) float32 | **基本健康，通用方案最大的"维度超限/halfvec 降精度"担忧对知曜不成立**（1024 < pgvector 可索引上限 2000，无需 halfvec，原生 float32）→ 只剩 HNSW 调参的微优化 |
| 4. 文档分库 + 元数据治理 | 单表 `document_embeddings` + `doc_kind` 列 + `doc_kinds` 过滤参数 + subject metadata 隔离 | **具备"逻辑分层"能力但无自动路由**；doc_metadata 稀疏（仅 title/subject）→ 真缺口 |
| 5. 问题改写 | 无。Agent 把**用户原始消息**直接 embed 召回 top-5 | **完全缺失** → 知曜第一痛点（口语化提问 ↔ 规范化笔记/课程） |
| 6. 分库路由 | `doc_kinds` 参数存在但实际总是默认/全检 | **未启用**；但 P2 已有 learning_intent 分类器 + Q8 复杂度分类器可复用 |
| 7. 多路召回 | 纯向量 cosine 单路 | **完全缺失**；search_service 已注释"未来可升级 GIN 全文索引" |
| 8. Reranker | 无 | **完全缺失**；受 CPU torch + SSE 延迟预算约束 |
| 9. 文档切分 | KB 文件固定 800 字/100 重叠；笔记 full_version 切块 | **弱**：固定长度切分，错题未把题干+答案+解析绑定成完整 chunk |
| 10. 同义词/术语映射 | 无 | **完全缺失** |

**核销结论**：知曜的真缺口集中在 **问题改写 / 结构化切分+元数据 / 多路召回+Reranker / 路由**。评测地基只差"标完+记基线"。存储与选型基本不用动。这与通用方案的优先级排序**高度吻合**——"建测试集、分库、问题改写、元数据治理 比单纯换模型收益大"——但知曜要做的是"补完上半场"，不是"重开一局"。

---

## 二、改进目标（知曜化）

1. 把"口语化学习提问"与"规范化笔记/课程/知识点"对齐，提升 Top-K 召回准确率。
2. 降低**跨学科、跨考试轨道**（EJU 数学 / 托福 / 校内初级1 / 日语）混检串味。
3. 把已有评测地基**跑通成可复现基线**，每次策略改动做回归对照。
4. 让错题/笔记/课程/记忆各 doc_kind 召回各归其位，引用来源（C-12 sources）更可信。
5. 形成 trace 采集 → 标注 → 评测 → 策略迭代的闭环，已建一半，补完它。

---

## 三、知曜专属评测集（补完阶段 A/B 的最后一公里）

通用方案要"建 300~500 条测试集"。知曜**采集管线已就绪**（trace → 脱敏 → worksheet），缺的是：① 真正标完、② 按教育场景分类、③ 记录基线。

### 3.1 教育场景分类（替换通用方案的电力规程场景）

| 场景 | 知曜示例 query | 考察点 |
|---|---|---|
| 口语化提问 | "这题为啥选 B" / "刚学那个公式忘了" / "が 和 は 到底啥区别" | 改写前后召回提升幅度 |
| 学科术语 | "二次函数判别式" / "現在完了形" / "托福综合写作模板" | 精准命中 |
| 错题回溯 | "我上次做错的那道三角函数题" / "之前纠结的那个语法点" | mistake doc_kind 命中 + 记忆对齐 |
| 跨学科隔离 | 数学 query 不得召回日语 KP | **学科串味率（知曜独有指标）** |
| 精确编号/长尾 | "第3章第2节" / "动词 て形" / "EJU 2023 第二题" | 精确匹配（纯向量弱项，BM25 强项） |
| 模糊指代 | "上周那个我没搞懂的点" | 意图理解 + 记忆库路由 |
| 考试轨道 | "EJU 数学排列组合" vs "托福听力" vs "校内期中" | 轨道隔离 + metadata 过滤 |

### 3.2 评测样本字段（在现有 CASES 契约上扩展）

现有 `{id, query, relevant:[doc_id...]}` 基础上，标注时补：`rewritten_query` / `scene`（上表 7 类）/ `expected_doc_kinds` / `expected_subject` / `distractor_doc_ids`（不应召回的干扰项，用于算错误召回率）。

### 3.3 指标体系（通用指标 + 知曜独有）

- 通用：Recall@5 / Recall@10 / MRR / nDCG / Top1 命中率 / 错误召回率（metrics.py 已实现前几项）
- **知曜独有**：学科串味率、考试轨道串味率、doc_kind 命中分布（kind_totals 已采集）、引用来源正确率（C-12 sources 命中 relevant 的比例）

### 3.4 本阶段动作

1. `python scripts/export_annotation_worksheet.py --days 30 --limit 200` 导出真实低质 query。
2. 人工标注 relevant + 上述扩展字段，目标先 **150~300 条真实样本**（合成 seed 集全 1.000 测不出问题，真实长尾才有区分度）。
3. `python scripts/run_annotated_eval.py --user-id <uid> --with-seed` 跑出**当前纯向量基线**，写进本文件附录，作为后续所有改动的对照锚。

**交付物**：标注完成的 `worksheet.json`（脱敏，可入库）+ 基线评测报告。

---

## 四、真缺口的具体改造方案

### 改造 1 ·【高】结构化切分 + 元数据治理（最高 ROI，最便宜）

**问题**：KB 文件固定 800 字切分会把"题干 / 公式 / 例题"切碎；错题未把 题干+参考答案+解析 绑成一个 chunk；doc_metadata 只有 title/subject，无法做轨道/年级/章节路径过滤。

**方案**：
- 错题（mistake）：一道题的 `question_text + reference_answer + 解析` 绑定为**单个不可切碎 chunk**，metadata 带 `subject / question_type / difficulty_tier / kp_id`。
- KB 文件：`document_extraction_service.extract_chunks` 升级为结构感知——优先按标题/段落边界切，保留"标题路径"，公式块/表格不切碎；保底再退化到长度切分。
- 课程章节（chapter）：已结构化，补 metadata `chapter_path / grade / exam_track`。
- 统一 chunk metadata 规范（写进 doc_metadata JSONB）：
  `doc_kind · subject · exam_track(eju/toefl/school) · grade · difficulty_tier · chapter_path · kp_id · version · is_current · title`。
- 写入侧统一入口 `rag_index.py` 已存在，metadata 在各 `embed_*` 任务里补齐即可，**无需改表**（JSONB 扩展）。

**风险**：错题绑定后单 chunk 变长，注意 bge-m3 输入截断（8192 token 内安全）。

### 改造 2 ·【高】问题改写（Query Rewrite）

**问题**：Agent 直接拿原始口语消息 embed，"が和は啥区别"和笔记标题"助词 は/が 的主题/主格辨析"语义距离大。

**方案**：在 `agent_service` 注入 RAG 前加一个轻量改写步骤，输出：
- 标准化 query（口语 → 学科术语）
- 多个等价改写 query（2~3 条）用于多路召回
- 关键词 + 识别出的实体（学科/KP 名/题型）
- 库路由建议（见改造 4）+ 用户意图分类（复用 P2 learning_intent）

**实现取舍**（关键，受成本约束 ¥500-3000/月 + 单用户日 500k token）：
- 优先**术语映射表 + 规则改写**（零 LLM 成本，见改造 5），覆盖高频口语。
- 命中不了再走**一次 DeepSeek 轻量改写**（已是主 LLM，复用现有 client），prompt 独立放 `llm/prompts/`。
- 用 feature flag `QUERY_REWRITE_ENABLED`（默认关），灰度 + 可回退，对齐知曜既有 flag 习惯（LEARNING_ENGINE_ENABLED / LEARNING_GAIN_ENABLED）。

### 改造 3 ·【中高】多路召回 + Reranker

**问题**：纯向量单路对"精确编号/长尾术语"弱（动词て形、第3章第2节、EJU 题号）。

**方案**（分两步，先 BM25 再 Reranker）：
1. **混合召回**：在 Postgres 内加关键词路（pg_trgm 或 tsvector GIN，中文可配 pg_jieba / zhparser；最省事先上 pg_trgm `ILIKE`+相似度，search_service 已有 ILIKE 经验）。向量 top-N + 关键词 top-N 合并去重，RRF（Reciprocal Rank Fusion）融合打分。
2. **Reranker**：`BAAI/bge-reranker-v2-m3`（与 bge-m3 同源，sentence-transformers CrossEncoder，CPU 可跑）对融合后 top-30~50 重排取 top-5。

**延迟与成本约束（必须正视）**：CPU 跑 reranker 对 50 条候选有显著延迟，会拖慢 SSE 首字。对策：
- reranker 仅在 `retrieve_knowledge` **主动召回**时启用，自动注入 top-5 那条链路先只上混合召回（不 rerank）。
- 或 reranker 候选压到 top-20、flag `RERANKER_ENABLED` 默认关，先在评测集量化收益再决定上不上生产。

**流程目标**：用户问题 → 改写 → 路由 → 向量召回 top-30 + BM25 top-30 → RRF 合并去重 → (可选)Reranker top-10 → 取 top-3~5 → format_for_prompt → DeepSeek 生成（禁无依据编造，已在 prompt）→ C-12 sources 返回。

### 改造 4 ·【中】分库路由

**问题**：`doc_kinds` / subject 过滤参数都已存在，但调用方总是全检，噪声来自不分库。

**方案**：召回前先判定问题该查哪些库（doc_kinds + subject + exam_track），**规则路由 + 模型路由结合**：
- 规则：出现"错题/做错/上次那道"→ `mistake`；"公式/定义/概念"→ `kp`+`chapter`；"我笔记/我记的"→ `note`；"上周/之前纠结"→ `episode`。
- 模型：复用 P2 已有的 learning_intent 分类器 / Q8 关键词 fast-path + LLM 兜底，输出候选库，**不新建分类器**。
- subject/exam_track 从改写阶段识别的实体填入 search 的 subject 参数（已支持）。

### 改造 5 ·【中】教育术语映射表

知曜版"用户口语 ↔ 规范术语"映射（喂给问题改写 + BM25 + 标签补全）：

| 用户口语 | 规范术语 |
|---|---|
| 开口向上/向下 | 二次函数图像开口方向 |
| 那个求导 | 导数 / 微分 |
| 嗡嗡的（误） | （N/A，教育域剔除电力示例） |
| が和は | 助词 は/が · 主题/主格辨析 |
| 过去式那个 | 動詞過去形 / 現在完了形 |
| 听力第一部分 | TOEFL Listening Section 1 |
| 大作文/小作文 | 综合写作 / 独立写作 |

落库为可维护配置（YAML/表），按 subject 分组，初版人工 + 后续从低质 query 失败案例自动补。

### 改造 6 ·【低】Embedding/存储——明确**暂不动**

- bge-m3（1024 维）+ pgvector + HNSW + float32 现状健康，**不存在维度超限/halfvec 降精度问题**，不要制造假问题。
- 换模型（bge-large-zh / Qwen-Embedding）受"零云依赖 + CPU torch"约束，Qwen 系常需 GPU/云，与 Q13 决策冲突；**仅在评测集证明 bge-m3 是瓶颈后才评估**，属第三优先级。
- 唯一值得做的微优化：评测集稳定后再调 HNSW `m / ef_construction / ef_search`，按 doc_kind 建 partial index。

---

## 五、目标架构（标注知曜现状 ✅/缺口 ❌）

```
用户输入层      ✅ POST /agent/chat（SSE + image OCR）
问题理解层      ❌ 改写/实体/术语标准化/意图  ← 改造 2+5
路由层          ❌ doc_kinds+subject+轨道路由  ← 改造 4（参数已具备）
召回层          ⚠️ 仅向量；缺 BM25/多 query   ← 改造 3
融合层          ❌ RRF 去重融合               ← 改造 3
重排序层        ❌ bge-reranker-v2-m3         ← 改造 3
上下文构建层    ✅ format_for_prompt（已截断/引用提示/禁编造）
答案生成层      ✅ DeepSeek V4 Flash（prompt 已禁无依据编造）
评测监控层      ✅ rag_retrieval_traces + /admin/rag/recall-stats + 标注管线（差跑通）← 改造/阶段三
```

缺的恰好是中间四层：**问题理解 / 路由 / 融合 / 重排序**。

---

## 六、实施路径（按知曜真实状态压缩，非从零）

| 阶段 | 周期 | 内容 | 交付 |
|---|---|---|---|
| **一·跑通基线** | 3~5 天 | 导出+标注 150~300 条真实样本（按 7 场景分类）；跑出纯向量基线写入附录 | 标注集 + 基线报告 |
| **二·切分+元数据** | 1 周 | 错题绑定 chunk；KB 结构化切分；统一 metadata 规范回填 | 切分规范 + 元数据规范 + 重跑评测对照 |
| **三·改写+术语表+路由** | 1.5~2 周 | 术语映射表；规则+LLM 改写（flag 灰度）；复用 P2 分类器做路由 | 改写模块 + 术语表 + 路由 + 评测对照 |
| **四·混合召回** | 1 周 | pg_trgm/tsvector 关键词路 + RRF 融合 | 混合召回 + 评测对照 |
| **五·Reranker** | 1 周 | bge-reranker-v2-m3 接入（flag 默认关），评测量化收益与延迟 | rerank 模块 + 延迟/收益报告，据此决定是否上生产 |
| **六·闭环常态化** | 长期 | recall-stats 看板；每次策略改动跑回归；失败案例反哺标注集 | 回归流程 + 月度优化报告 |

每阶段**必须在评测集上对照基线**，无对照不合并（对齐知曜工程质量准则：不做表面修复）。

---

## 七、优先级（知曜化排序）

- **第一优先级**：跑通基线（阶段一）· 结构化切分+元数据（改造1）· 问题改写+术语表（改造2/5）
- **第二优先级**：分库路由（改造4）· 混合召回（改造3 上半）· Reranker（改造3 下半，需评测验证延迟可接受）
- **第三优先级（暂不做）**：换 Embedding / 换向量库 / 多模型融合 / HNSW 精调——存储与选型现状健康，无证据前不动

---

## 八、约束与坑（知曜专属）

- **成本**：¥500-3000/月、单用户日 500k token——改写优先走零成本术语表/规则，LLM 改写兜底；Reranker 走本地 CPU 不增 API 成本但增延迟。
- **延迟**：SSE 首字体验敏感，Reranker 在 CPU 上是主要风险点，必须 flag 化 + 评测量化后再上。
- **零云依赖**：嵌入/重排都用 BGE 同源本地模型，延续 Q13 决策。
- **回退**：每个新链路都加 feature flag（默认关），对齐 LEARNING_ENGINE_ENABLED 习惯，一键回旧行为。
- **多学科多轨道**是知曜区别于通用知识库的核心——"学科/轨道串味率"是必须盯的独有指标。
- **无 gh CLI**；后端用系统 python 跑 pytest/alembic（见项目 CLAUDE.md）。

---

## 九、最终建议

知曜的 RAG 不应被当成"该换个更高分 Embedding 了"——它的评测地基、存储、选型都已就位，**真正的杠杆在中间四层（问题理解/路由/融合/重排序）和切分/元数据**。

推荐路线：**先把已有评测管线跑出真实基线 → 结构化切分+元数据治理（最便宜高 ROI）→ 问题改写+术语表对齐口语 → 分库路由降噪 → 混合召回扩覆盖 → Reranker 验证后提排序 → 评测闭环常态化。**

只有这样，知曜知识库才能从"召回了 top-5"升级为"召回的就是用户那道错题、那条笔记、那个语法点"。

---

## 附录 A · 基线评测结果（阶段一完成后回填）

| 指标 | 纯向量基线 | 目标 |
|---|---|---|
| Recall@5 | _待测_ | — |
| Recall@10 | _待测_ | — |
| MRR | _待测_ | — |
| nDCG | _待测_ | — |
| Top1 命中率 | _待测_ | — |
| 错误召回率 | _待测_ | — |
| 学科串味率 | _待测_ | — |
