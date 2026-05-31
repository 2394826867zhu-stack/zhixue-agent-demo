"""阶段 B 最后一公里：把 E→B 导出的低质召回脱敏样本桥接成检索评估集。

数据通路：
  运维 `GET /admin/rag/low-quality-samples`（或 scripts/export_annotation_worksheet.py）
    → build_worksheet()   生成去重 + 频次 + 诊断信号的标注工作表（relevant 待人工填）
    → 【人工标注期望 doc_id】
    → worksheet_to_cases() 转成 evaluate_retrieval 吃的 CASES 契约（query → relevant doc_id）
    → merge_cases()        与合成种子集合并，跑 run_retrieval_eval 量化真实数据上的检索质量

全部纯函数（零 DB / 零 IO），秒级 TDD；DB / 文件读写在 scripts/ 薄壳里。

CASES 契约（与 app/eval/seed_retrieval_cases.py、retrieval_eval.evaluate_retrieval 对齐）：
    {"id": str, "query": str, "relevant": list[str]}
"""
from __future__ import annotations

WORKSHEET_VERSION = 1


def _clean(s) -> str:
    return s.strip() if isinstance(s, str) else ""


def build_worksheet(samples: list[dict]) -> dict:
    """低质召回导出样本 → 待标注工作表。

    - 跳过 masked_query 为空/纯空白的行（脱敏后可能为空）
    - 按 query 精确去重，聚合出现频次 + 最差信号（是否零召回 / 最低非空平均分）
    - 高频在前（确定性排序：freq desc, query asc），id 稳定（同输入同输出）
    """
    groups: dict[str, dict] = {}
    order: list[str] = []
    for s in samples:
        q = _clean(s.get("masked_query"))
        if not q:
            continue
        g = groups.get(q)
        if g is None:
            g = {"query": q, "freq": 0, "any_empty": False, "min_score_avg": None}
            groups[q] = g
            order.append(q)
        g["freq"] += 1
        if s.get("is_empty"):
            g["any_empty"] = True
        sa = s.get("score_avg")
        if sa is not None:
            g["min_score_avg"] = sa if g["min_score_avg"] is None else min(g["min_score_avg"], sa)

    ordered = sorted(groups.values(), key=lambda g: (-g["freq"], g["query"]))
    cases = []
    for i, g in enumerate(ordered, 1):
        cases.append({
            "id": f"lq_{i:04d}",
            "query": g["query"],
            "relevant": [],            # ← 人工填入期望召回的 doc_id（字符串）
            "annotated": False,
            "freq": g["freq"],
            "signal": {
                "any_empty": g["any_empty"],
                "min_score_avg": g["min_score_avg"],
            },
        })
    return {
        "version": WORKSHEET_VERSION,
        "source": "low_quality_samples",
        "instructions": (
            "为每条 query 填写 relevant：该 query 本应召回的 doc_id 列表（字符串）。"
            "留空表示尚未标注，会被跳过。标注完成后跑 scripts/run_annotated_eval.py。"
        ),
        "cases": cases,
    }


def worksheet_to_cases(worksheet: dict) -> list[dict]:
    """已标注工作表 → evaluate_retrieval 吃的 CASES（只保留 relevant 非空的条目）。

    - 去除 signal/freq/annotated 等元字段，只留 id/query/relevant 契约三元组
    - relevant 内部去重并去空白，保持顺序；全空白视为未标注 → 跳过
    """
    cases = []
    for c in worksheet.get("cases", []):
        seen: set[str] = set()
        relevant: list[str] = []
        for r in c.get("relevant", []) or []:
            rr = _clean(r)
            if rr and rr not in seen:
                seen.add(rr)
                relevant.append(rr)
        if not relevant:
            continue
        cases.append({"id": c["id"], "query": c["query"], "relevant": relevant})
    return cases


def merge_cases(*case_lists: list[dict]) -> list[dict]:
    """合并多个 CASES 列表，按 id 去重（先到先得），用于合成种子集 + 真实标注集联合评测。"""
    merged: list[dict] = []
    seen: set[str] = set()
    for cases in case_lists:
        for c in cases:
            cid = c["id"]
            if cid in seen:
                continue
            seen.add(cid)
            merged.append(c)
    return merged
