# 学习内核失败案例 eval 集（G-P4-3）

把真实作答里的**失败案例**沉淀成学习内核的回归评估集，随数据增长。沿用 RAG 阶段
`annotations/` 的 build→merge 范式（`app/eval/failure_cases.py`）。

## 是什么
- 来源：训练作答中 `is_wrong=True` 的题（含探针失败）+ 该 KP 的掌握度。
- 单元：按 `(kp_id, kind)` 去重聚合的 case，带 `wrong_count` / `error_reasons` 频次 /
  `surprising`（掌握度 ≥0.6 却答错 = 模型高估，最有信息量）。

## 怎么用
```bash
# 沉淀（只读 DB，写 failures.json；多次跑随真实数据增长）
PYTHONPATH=. python scripts/run_failure_harvest.py
```
- `failures.json` 与历史 `merge`（频次累加、新 key 进集）。
- 下游：`surprising` 案例是 BKT 校准（learning_gain ECE）与引擎对照（engine_comparison）
  最该盯的硬样本——模型在这些点上预测错了，是迭代靶子。

## 为什么不进 git 跟踪具体数据
`failures.json` 是随真实数据增长的运维产物（含用户 KP id），默认不提交；只提交本说明与管道代码。
