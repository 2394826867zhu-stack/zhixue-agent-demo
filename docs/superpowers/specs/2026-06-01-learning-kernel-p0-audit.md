# 知曜学习内核 P0 · 全面审计报告

> 日期：2026-06-01 · 范围：聚焦学习内核 P0（已 FF 合并 main，HEAD=be3f6eb，alembic 037，全套 134 pass）
> 方法：单线程逐行审计 P0 七任务的提交版代码 + 测试 + 迁移。每条结论附文件:行与证据。
> 结论先行：**P0 功能正确、可上线，但有 1 个 P1 测试盲区（三钩子无端到端测试）+ 若干 P2 卫生问题**。无 P0 级阻断缺陷。

---

## 一、评级汇总

| # | 等级 | 问题 | 文件 |
|---|---|---|---|
| A-1 | 🟠 P1 | **三个答题钩子（training/feynman/fsrs）无端到端测试** — P0-4 的核心集成完全未被验证 | `tests/integration/test_mastery_update.py` |
| A-2 | 🟠 P1 | **BKT guess/slip 钳制无测试守护** — M2 防退化的安全不变量裸奔；计划里的 `test_bkt_guess_slip_clamped_to_half` 丢失 | `tests/unit/test_measurement_service.py` |
| A-3 | 🟡 P2 | 测试文件 `test_new_columns_exist_on_models` **重复定义两次**（L39/L82，后者遮蔽前者）| `tests/unit/test_measurement_service.py` |
| A-4 | 🟡 P2 | BKT 落地 `_BKT_P_GUESS=0.25`，**偏离**理论地基/计划锁定的 0.20，无说明 | `app/services/measurement_service.py:22` |
| A-5 | 🟡 P2 | `question.is_correct` 是**瞬态属性非数据库列**（伪持久化），易误导 | `app/services/training_service.py:363` |
| A-6 | 🟡 P2 | `update_mastery_on_answer` 有 `db.flush()`、`record_probe_result` **无** flush — 两者都声称"不 commit"却不一致 | `measurement_service.py:111` vs `probe_service.py` |
| A-7 | 🟡 P2 | pgvector 扩展不被 conftest 管理 — 测试库 schema 一旦重置即丢 `vector`，全 RAG/集成测试崩 | `tests/conftest.py` |

---

## 二、正面确认（P0 做对的地方）

逐项核对，以下均正确，**不需改动**：

1. **migration 037** — 四列（KP.p_mastery/last_probe + TQ.is_probe/probe_kind）全 nullable/defaulted，向后兼容；upgrade/downgrade 对称、逆序 drop；revision 037→036 链正确；已验证可逆（downgrade -1 + upgrade head 无错）。
2. **BKT 数学** — `bkt_update`：答对>答错、结果恒在 [0,1]、prior=None→P_INIT；贝叶斯后验 + 学习转移公式正确（`measurement_service.py:67-95`）。
3. **FSRS 遗忘曲线** — `retrievability` 幂律 `(1+19/81·t/S)^-0.5`，t=S 时 R=0.9（数学核验通过）；`effective_mastery = p_mastery×R`，None/异常优雅降级。
4. **training `is_probe` 分支（这是 P0-5 最关键的正确性点）** — `submit_answer` 中：
   - 探针 → `record_probe_result`（仅更新信念 + 写 last_probe）；普通题 → `update_mastery_on_answer`（`training_service.py:363-373`）。
   - 错题归档守卫**双处到位**：`enqueue_mistake_index` 加 `and not question.is_probe`（L413）；`kind="mistake"` 时间线节点同样加守卫（L446）。
   - `training_result` 时间线节点对探针**保留**（探针仍是答题事件）。
   - ✅ 结论：普通错答的归档/RAG/时间线链路**完全未被破坏**，探针正确地"不计练习、不归错题"。
5. **feynman/fsrs 钩子** — feynman `total≥70`、fsrs `rating≥3` 作为掌握证据，均在 commit 前、就地更新已取出的 kp 对象，feynman 侧包 try/except fail-safe（`feynman_service.py:163-168`、`fsrs_service.py:204-205`）。
6. **eval 指标** — Hake 归一化增益、单位时长增益、ECE 分箱，除零守卫齐全；纯函数。
7. **celery beat** — `mastery-calibration-monitor` 已进 `beat_schedule` + `include`；真实数据管道按设计是安全 no-op（P4 再建）。
8. **全套测试 134 pass / 10 skip / 0 fail**（schema 完好时），合并前后双次验证一致。

---

## 三、问题详述与修复建议

### A-1 🟠 P1 · 三个答题钩子无端到端测试（最重要）

**证据**：`tests/integration/test_mastery_update.py` 仅 3 个用例，全部**直接调用 service 函数**：
- `test_update_mastery_on_answer_raises_p_mastery` → 直调 `measurement_service.update_mastery_on_answer`
- `test_update_mastery_on_answer_none_kp_is_safe` → 直调，测兜底
- `test_record_probe_writes_last_probe` → 直调 `probe_service.record_probe_result`

**没有**任何用例经由 `training_service.submit_answer` / `feynman_service.submit` / `fsrs_service.review` 触发钩子。

**风险**：P0-4 的全部价值就是"把三个真实答题事件接进掌握度更新"。这层集成**零覆盖** —— 任何人删掉钩子、改错 kp 变量、或重构 submit 流程，测试仍全绿。这正是本会话两度发生"钩子丢失/在错分支"却没被测试拦住的根因。

**建议修复**（P1，TDD）：加 3 个集成测试——分别走 submit_answer（普通题答对→p_mastery 升 / 探针→不写 mistake 只写 last_probe）、feynman.submit（total≥70→p_mastery 升）、fsrs.review（rating≥3→p_mastery 升）。这是 P1 动工前最该补的安全网。

### A-2 🟠 P1 · BKT 钳制无测试

**证据**：计划 Task 2 明确含 `test_bkt_guess_slip_clamped_to_half`（传 guess=slip=0.9 验证"答对不劣于答错"），但落地 `test_measurement_service.py` 的 BKT 测试只有 correct/wrong/none/unit-interval 四个，**钳制测试丢失**。`_clamp_half` 逻辑在代码里（`measurement_service.py:28-29`）但无守护。

**风险**：钳制是 M2「防退化」的安全核心（guess/slip>0.5 会让"答错反而更掌握"）。无测试 = 未来改动可能静默破坏这个不变量。

**建议修复**（P1）：补回该测试。

### A-3 🟡 P2 · 测试重复定义

**证据**：`test_new_columns_exist_on_models` 在 L39-47 与 L82-90 **完全重复**，pytest 只跑后者。是并发会话拼接文件的残留。
**建议**：删掉其一。

### A-4 🟡 P2 · BKT 参数偏离

**证据**：`measurement_service.py:22` `_BKT_P_GUESS = 0.25`，但理论地基 M2 与 P0 计划锁定 `p_guess=0.20`。
**判断**：0.25 仍 ≤0.5，可辩护（选择题蒙对率更接近 0.25），但**未记录为有意偏离**。
**建议**：二选一——对齐回 0.20，或在代码注释 + 理论地基里记一句"知曜选 0.25 因含较多选择题"。倾向后者（0.25 更贴合实际），但要留痕。

### A-5 🟡 P2 · is_correct 伪持久化

**证据**：`question.is_correct = not is_wrong`（`training_service.py:363`），但 `grep is_correct app/models/training.py` = 0 命中 —— TrainingQuestion **无此列**，这是 SQLAlchemy 允许的瞬态实例属性，永不入库。
**判断**：钩子在同一函数作用域内紧接着读它（L368/372），值正确，**功能无 bug**。但"看起来像列实则不持久化"会误导后人（若有人 `SELECT question.is_correct` 会得 None）。
**建议**：钩子直接用 `not is_wrong`（语义等价、不造假象）；或正式加列（若产品需要持久化对错）。倾向前者。

### A-6 🟡 P2 · flush 不一致

**证据**：`update_mastery_on_answer` 末尾 `await db.flush()`（`measurement_service.py:111`）；`record_probe_result` 无 flush（只改对象，依赖调用方 commit）。两者 docstring 都写"不 commit"。
**判断**：在 submit_answer 里两路径最终都到 `db.commit()`（L462），当前**能正常工作**。但不对称是潜在陷阱——若将来探针路径在无尾随 commit 的上下文被调用，改动不落库。
**建议**：统一——要么都 flush，要么都不 flush（推荐都不 flush，让调用方掌控事务边界，最小惊讶）。

### A-7 🟡 P2（基础设施）· pgvector 不被 conftest 管理

**证据**：本次审计中 `DROP SCHEMA public CASCADE` 连带删了 `vector` 扩展（`drop cascades to extension vector`），导致 58 errors，手动 `CREATE EXTENSION IF NOT EXISTS vector` 才恢复。conftest 的 `create_all` 不保证扩展存在。
**建议**：conftest 建表前执行 `CREATE EXTENSION IF NOT EXISTS vector`，让测试库自愈（符合"必须有自动恢复机制"的工程准则）。

---

## 四、修复优先级建议（待你点头）

**进 P1 前强烈建议先做（P1 级，约 1 个 TDD 小循环）：**
- [ ] A-1 补三个钩子的端到端集成测试 ← 最高价值
- [ ] A-2 补回 BKT 钳制测试

**可顺手清理（P2 级，几分钟）：**
- [ ] A-3 删重复测试
- [ ] A-5 钩子改用 `not is_wrong`
- [ ] A-6 统一 flush 语义
- [ ] A-7 conftest 自愈 vector 扩展

**需你拍板（P2 决策）：**
- [ ] A-4 p_guess=0.25 → 对齐 0.20 还是留 0.25 + 记录理由？

**不动**：第二节所有正面确认项。

---

## 五、审计结论

P0 作为"度量地基"是**扎实且正确**的：数学对、迁移稳、探针隔离逻辑严谨、错题链路无损、全套绿。唯一的实质风险是 **A-1 集成测试盲区**——它恰好是本会话反复出问题（钩子丢失）却没被自动拦截的根因，建议在推进 P1 前补齐这张安全网。其余均为卫生级、不阻断。
