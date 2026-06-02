"""G-P4-2 · 外部成绩锚报告（手动跑，只读）：

  PYTHONPATH=. python scripts/run_score_anchor.py            # 全局
  PYTHONPATH=. python scripts/run_score_anchor.py --user <uuid>

把所有（或某用户）已录成绩的考试与其学科内部掌握度配对，输出 Pearson 相关。
数据稀疏 → correlation=None，诚实留空（理论地基 M10：验证不自欺）。只读，不写库。
"""
import argparse
import asyncio
import json


async def _run(user_id: str | None) -> None:
    import app.main  # noqa: F401  注册全部 ORM model
    from app.core.database import AsyncSessionLocal
    from app.services.anchor_service import compute_score_anchor

    async with AsyncSessionLocal() as db:
        rep = await compute_score_anchor(db, user_id=user_id)

    print("== G-P4-2 外部成绩锚（考试分 vs 内部掌握度）==")
    print(f"配对数 n={rep['n']}")
    if rep["correlation"] is None:
        print("相关=None（数据不足/零方差，诚实留空，不自欺）")
    else:
        print(f"Pearson 相关={rep['correlation']:.3f}  平均考分={rep['mean_score_pct']:.1f}  平均掌握={rep['mean_mastery_pct']:.1f}")
    print(json.dumps(rep, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=None, help="限定某用户 UUID（默认全局）")
    args = ap.parse_args()
    asyncio.run(_run(args.user))


if __name__ == "__main__":
    main()
