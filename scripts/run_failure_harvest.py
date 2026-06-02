"""G-P4-3 · 失败案例沉淀（手动跑，读真实库 + 写盘沉淀）：

  PYTHONPATH=. python scripts/run_failure_harvest.py
  # → 默认沉淀到 app/eval/learning_cases/failures.json（与历史合并，eval 集随数据增长）

从训练作答（answered + is_wrong）+ KP 掌握度，沉淀学习内核失败案例集：
按 (kp_id, kind) 去重 + 聚合错因频次，标 surprising（高掌握却答错=模型高估）。
与既有沉淀文件 merge（频次累加、新 key 进集），多次跑即随真实数据增长。

只读 DB（select），仅写沉淀 JSON。沿用 RAG 阶段 annotation 管道范式（build→merge）。
"""
import argparse
import asyncio
import json
import os

from app.eval import failure_cases as fc

DEFAULT_OUT = os.path.join("app", "eval", "learning_cases", "failures.json")


async def _harvest() -> list[dict]:
    import app.main  # noqa: F401  注册全部 ORM model
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.training import TrainingQuestion
    from app.models.knowledge_point import KnowledgePoint

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(
                    TrainingQuestion.knowledge_point_id,
                    TrainingQuestion.is_probe,
                    TrainingQuestion.is_wrong,
                    TrainingQuestion.error_reason,
                    KnowledgePoint.subject,
                    KnowledgePoint.p_mastery,
                )
                .join(KnowledgePoint, KnowledgePoint.id == TrainingQuestion.knowledge_point_id)
                .where(TrainingQuestion.answered_at.is_not(None), TrainingQuestion.is_wrong.is_(True))
            )
        ).all()

    return [
        {
            "kp_id": str(kp_id),
            "subject": subject,
            "kind": "probe" if is_probe else "practice",
            "correct": not bool(is_wrong),  # is_wrong=True → False
            "error_reason": error_reason,
            "p_mastery": float(p_m) if p_m is not None else None,
        }
        for kp_id, is_probe, is_wrong, error_reason, subject, p_m in rows
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    records = asyncio.run(_harvest())
    fresh = fc.build_failure_set(records)

    prev = {"cases": []}
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as f:
            prev = json.load(f)
    before = len(prev.get("cases", []))

    merged = fc.merge_failure_sets(prev, fresh)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    st = fc.failure_set_stats(merged)
    print("== G-P4-3 失败案例沉淀 ==")
    print(f"本次新采失败记录 {fresh['total_records']} 条；沉淀集 {before} → {st['n_cases']} 个案例")
    print(f"累计错答 {st['total_wrong']}，其中 surprising(模型高估) {st['surprising_count']}")
    print(f"沉淀文件：{args.out}（随真实数据增长）")


if __name__ == "__main__":
    main()
