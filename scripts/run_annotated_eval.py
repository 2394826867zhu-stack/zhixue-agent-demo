"""阶段 B 最后一公里 · 第 2 步：用真实标注样本跑检索评估。

读人工标注完的工作表（export_annotation_worksheet.py 产出），转成 CASES，
对**真实生产语料**跑 Recall@K / MRR / nDCG。与合成种子集不同——真实低质 query
（口语化 / 长尾 / 精确编号）才有区分度，能暴露纯向量在真实分布上的短板，
为阶段 C（BM25/混合/rerank）提供可量化的 A/B 对照。

只读（rag_service.search 仅 select），不写库、不 drop。手动跑：
    python scripts/run_annotated_eval.py --user-id <被标注 query 所属用户 UUID>
    # 可选 --file 指定工作表；--official-only 只评 official 层；--with-seed 合并合成种子集

注意：真实 query 的 relevant doc_id 必须在被检索的语料范围（该 user 的私有层 +
official 共享层）内可见——标注时请针对该范围标注。
"""
import argparse
import asyncio
import json
import os
import uuid

import app.main  # noqa: F401  # 注册全部 ORM model
from app.core.database import AsyncSessionLocal
from app.eval.annotation import worksheet_to_cases, merge_cases
from app.eval.retrieval_eval import make_rag_search_fn, evaluate_retrieval

DEFAULT_FILE = os.path.join("app", "eval", "annotations", "worksheet.json")


def _load_cases(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        worksheet = json.load(f)
    return worksheet_to_cases(worksheet)


async def _run(path: str, user_id, top_k: int, with_seed: bool) -> None:
    cases = _load_cases(path)
    if with_seed:
        from app.eval.seed_retrieval_cases import CASES as SEED
        cases = merge_cases(cases, SEED)
    if not cases:
        print(f"工作表 {path} 中没有已标注的 case（relevant 全为空）——先标注再跑。")
        return

    async with AsyncSessionLocal() as db:
        fn = make_rag_search_fn(db, user_id=user_id, top_k=top_k)
        report = await evaluate_retrieval(cases, fn, ks=(1, 3, 5))

    print("===== 真实标注检索评估（%d 个 query / 生产语料 / top_k=%d）=====" % (len(cases), top_k))
    for key in ("mean_recall@1", "mean_recall@3", "mean_recall@5", "mean_mrr", "mean_ndcg@5"):
        val = report.get(key)
        print(f"  {key:18s}: {val:.3f}" if val is not None else f"  {key}: n/a")
    print("--- 逐条（低分项即检索短板，回流标注/调参的靶子）---")
    for r in report["per_case"]:
        print(f"  {str(r['id']):10s} recall@1={r['recall@1']:.0f} recall@3={r['recall@3']:.0f} mrr={r['mrr']:.3f}")


def main() -> None:
    p = argparse.ArgumentParser(description="用真实标注样本跑检索评估")
    p.add_argument("--file", default=DEFAULT_FILE, help=f"标注工作表路径（默认 {DEFAULT_FILE}）")
    p.add_argument("--user-id", help="被标注 query 所属用户 UUID（决定可见私有语料；不填=仅 official 层）")
    p.add_argument("--top-k", type=int, default=10, help="检索召回深度（默认 10）")
    p.add_argument("--with-seed", action="store_true", help="同时合并合成种子集一起评测")
    args = p.parse_args()

    # 不传 user-id 时用一个随机 UUID → rag_service.search 只会命中 official（user_id IS NULL）层
    user_id = uuid.UUID(args.user_id) if args.user_id else uuid.uuid4()
    asyncio.run(_run(args.file, user_id, args.top_k, args.with_seed))


if __name__ == "__main__":
    main()
