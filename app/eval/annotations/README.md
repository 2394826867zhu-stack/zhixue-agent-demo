# 真实低质召回 → 检索评估集（标注工作区）

阶段 B 最后一公里：把 E→B 采集的真实低质召回脱敏 query 标注成评估集，
量化纯向量检索在**真实数据分布**上的短板（合成种子集全 1.000 测不出问题）。

## 工作流

```
# 1) 导出近 N 天低质召回（零召回 / 伪召回）脱敏样本为待标注工作表
python scripts/export_annotation_worksheet.py --days 30 --limit 200
#    → 写到 app/eval/annotations/worksheet.json

# 2) 人工标注：编辑 worksheet.json，给每条 case 的 relevant 填上
#    “这条 query 本应召回的 doc_id 列表”（字符串）。留空 = 跳过。

# 3) 跑评估（对真实生产语料，只读）
python scripts/run_annotated_eval.py --user-id <query 所属用户 UUID> --with-seed
#    → 打印 Recall@K / MRR / nDCG，低分项就是检索短板的靶子
```

## 契约

- 工作表 / 标注：`app/eval/annotation.py`（`build_worksheet` / `worksheet_to_cases` / `merge_cases`，纯函数）
- 评估集 CASES：`{"id", "query", "relevant": [doc_id...]}`，与 `app/eval/seed_retrieval_cases.py` 一致
- 标注时 relevant 的 doc_id 必须在被检索语料范围（该用户私有层 + official 共享层）内可见

> 标注完成的 `worksheet.json` 可作为长期评估资产提交入库（含真实 query 的脱敏样本，
> 已经过 `pii_filter.mask_pii` 脱敏；提交前请再人工确认无残留隐私）。
