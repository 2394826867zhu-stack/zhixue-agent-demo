"""G-P4-3 · 失败案例沉淀回 eval 集（沿用 RAG 阶段做法 [M10]）。

把探针失败 / 低分作答沉淀成学习内核的**回归评估集**，随真实数据增长：
- build_failure_set：从作答记录里挑出失败项，按 (kp_id, kind) 去重 + 聚合频次/错因，
  并标 "surprising"（掌握度高却答错 = 模型高估，最有信息量）。
- merge_failure_sets：把多次/多源沉淀合并（频次累加、新 key 进集），eval 集随数据增长。
纯函数、空样本安全。沉淀文件由 runner 读真实库写盘（app/eval/learning_cases/）。

record 形状：{kp_id, subject, kind('probe'|'practice'), correct: bool, error_reason, p_mastery}
注：surprising 用当前 p_mastery 近似"答题时掌握度"（与 P4-2/P4-4 同口径文档化近似）。
"""
from __future__ import annotations

# 掌握度达此阈仍答错 → 模型高估，标 surprising（与 learner_state mastered 阈一致）
_SURPRISE_MASTERY = 0.6


def _key(rec: dict) -> tuple:
    return (str(rec.get("kp_id")), rec.get("kind") or "practice")


def build_failure_set(records: list[dict]) -> dict:
    """从作答记录沉淀失败案例集（仅 correct==False），去重 + 聚合。"""
    cases: dict[tuple, dict] = {}
    for r in records:
        if r.get("correct") is not False:  # 只留明确失败
            continue
        k = _key(r)
        c = cases.get(k)
        if c is None:
            c = {
                "kp_id": k[0], "kind": k[1], "subject": r.get("subject"),
                "wrong_count": 0, "error_reasons": {}, "surprising": False,
            }
            cases[k] = c
        c["wrong_count"] += 1
        reason = r.get("error_reason")
        if reason:
            c["error_reasons"][reason] = c["error_reasons"].get(reason, 0) + 1
        m = r.get("p_mastery")
        if m is not None and m >= _SURPRISE_MASTERY:
            c["surprising"] = True
    return {"total_records": len(records), "cases": list(cases.values())}


def merge_failure_sets(*sets: dict) -> dict:
    """沉淀合并：频次累加、错因合并、surprising 取或、新 key 进集（eval 集随数据增长）。"""
    merged: dict[tuple, dict] = {}
    for s in sets:
        for c in s.get("cases", []):
            k = (str(c.get("kp_id")), c.get("kind") or "practice")
            m = merged.get(k)
            if m is None:
                merged[k] = {
                    "kp_id": k[0], "kind": k[1], "subject": c.get("subject"),
                    "wrong_count": int(c.get("wrong_count", 0)),
                    "error_reasons": dict(c.get("error_reasons", {})),
                    "surprising": bool(c.get("surprising", False)),
                }
            else:
                m["wrong_count"] += int(c.get("wrong_count", 0))
                for reason, n in c.get("error_reasons", {}).items():
                    m["error_reasons"][reason] = m["error_reasons"].get(reason, 0) + n
                m["surprising"] = m["surprising"] or bool(c.get("surprising", False))
                m["subject"] = m["subject"] or c.get("subject")
    return {"cases": list(merged.values())}


def failure_set_stats(failure_set: dict) -> dict:
    cases = failure_set.get("cases", [])
    return {
        "n_cases": len(cases),
        "total_wrong": sum(int(c.get("wrong_count", 0)) for c in cases),
        "surprising_count": sum(1 for c in cases if c.get("surprising")),
    }
