"""G-P1-6 · 先修图谱边自愈（手动跑）：

  # 全用户预演（不写库，看会怎么自愈）：
  PYTHONPATH=. python scripts/run_edge_healing.py
  # 对某用户真正落库自愈：
  PYTHONPATH=. python scripts/run_edge_healing.py --user <uuid> --apply
  # 全用户落库：
  PYTHONPATH=. python scripts/run_edge_healing.py --all --apply

用真实掌握度校验先修边：下游明确掌握却没掌握先修 → 违例衰减 confidence，
持续违例跌破地板 → 剪除（不动人工边）；一致 → 加固。默认 dry-run（只读不写），
--apply 才 commit。机制已就位，定时自动化（Celery beat）待数据规模够再开。
"""
import argparse
import asyncio


async def _run(user_filter: str | None, all_users: bool, apply: bool) -> None:
    import app.main  # noqa: F401  注册全部 ORM model
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.prerequisite_edge import PrerequisiteEdge
    from app.services import edge_healing as eh

    async with AsyncSessionLocal() as db:
        if user_filter:
            uids = [user_filter]
        else:
            rows = (await db.execute(select(PrerequisiteEdge.user_id).distinct())).all()
            uids = [str(u) for (u,) in rows]
            if not all_users:
                uids = uids[:1]  # 默认只看第一个用户，避免误扫全库

        tot_e = tot_v = tot_p = 0
        for uid in uids:
            rep = await eh.assess_and_heal(db, uid, apply=apply)
            tot_e += rep["n_edges"]; tot_v += rep["violated"]; tot_p += rep["pruned"]
            if rep["n_edges"]:
                print(f"  user={uid[:8]}… edges={rep['n_edges']} violated={rep['violated']} "
                      f"consistent={rep['consistent']} pruned={rep['pruned']}")
        if apply:
            await db.commit()

    mode = "已落库" if apply else "预演(未写库)"
    print(f"== G-P1-6 边自愈 [{mode}] ==")
    print(f"用户数={len(uids)} 边总数={tot_e} 违例={tot_v} 剪除={tot_p}")
    if not apply:
        print("（加 --apply 才真正落库自愈）")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=None, help="限定某用户 UUID")
    ap.add_argument("--all", action="store_true", help="扫描所有有边的用户")
    ap.add_argument("--apply", action="store_true", help="真正落库（默认 dry-run 只读）")
    args = ap.parse_args()
    asyncio.run(_run(args.user, args.all, args.apply))


if __name__ == "__main__":
    main()
