"""G-P3-5 · 学生模型对照报告（手动跑）：

  # 合成数据（无需 DB，验证管道）：
  PYTHONPATH=. python scripts/run_engine_comparison.py
  # 真实数据（只读 zhiyao 库的训练作答）：
  PYTHONPATH=. python scripts/run_engine_comparison.py --db

同一份作答序列上跑 BKT / PFA / Best-LR，输出 log-loss / accuracy / AUC 对照
与"是否换引擎"建议（保守兜底：未明显胜出则保持 BKT）。

真实序列构造：按 (user_id, knowledge_point_id) 分组、按时间排序的 `correct = not is_wrong`
（仅取已作答 answered_at 非空者）。数据不足 → 报告 insufficient_data 安全 no-op。
只读（仅 select），不写库。
"""
import argparse
import asyncio
import json

from app.eval import engine_comparison as ec

_SYNTH = [
    [False, False, True, True, True, True],
    [False, True, False, True, True, True],
    [True, True, True, True],
    [False, False, False, True, False, True],
]


async def _load_real_sequences() -> list[list[bool]]:
    import app.main  # noqa: F401  注册全部 ORM model
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.training import TrainingQuestion

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(
                    TrainingQuestion.user_id,
                    TrainingQuestion.knowledge_point_id,
                    TrainingQuestion.is_wrong,
                    TrainingQuestion.answered_at,
                    TrainingQuestion.created_at,
                )
                .where(TrainingQuestion.answered_at.is_not(None))
                .order_by(TrainingQuestion.answered_at.asc())
            )
        ).all()

    groups: dict[tuple, list[bool]] = {}
    for user_id, kp_id, is_wrong, _ans, _created in rows:
        groups.setdefault((str(user_id), str(kp_id)), []).append(not bool(is_wrong))
    return list(groups.values())


def _print_report(rep: dict) -> None:
    print("== G-P3-5 学生模型对照（BKT / PFA / Best-LR）==")
    print(f"序列数={rep['n_sequences']}  作答数={rep['n_responses']}")
    if rep["recommendation"] == "insufficient_data":
        print(f"数据不足（< {ec._MIN_RESPONSES} 条）→ 保持现有 BKT。")
        return
    for name in ("bkt", "pfa", "base_rate"):
        m = rep["models"][name]
        auc = f"{m['auc']:.3f}" if m["auc"] is not None else "n/a"
        print(f"  {name:9s} log_loss={m['log_loss']:.4f}  acc={m['accuracy']:.3f}  auc={auc}")
    print(f"最优(log_loss)={rep['best_by_log_loss']}  建议={rep['recommendation']}")
    if rep["pfa_params"]:
        p = rep["pfa_params"]
        print(f"  PFA 参数: beta0={p['beta0']:.3f} gamma={p['gamma']:.3f} rho={p['rho']:.3f}")
    print(json.dumps(rep, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", action="store_true", help="从 zhiyao 库读真实训练作答（默认用合成数据）")
    args = ap.parse_args()
    sequences = asyncio.run(_load_real_sequences()) if args.db else _SYNTH
    _print_report(ec.engine_comparison_report(sequences))


if __name__ == "__main__":
    main()
