"""阶段 B 检索评测基线脚本。

连 zhiyao_test 库，seed 合成评估集（真实 BGE-M3 嵌入），跑当前检索，
输出 Recall@K / MRR / nDCG 基线。作为阶段 C 检索升级（BM25/混合/rerank）的 A/B 对照。

手动跑：  python scripts/run_retrieval_eval.py
"""
import asyncio
import uuid

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

import app.main  # noqa: F401  # 触发全部 ORM model 注册到 Base.metadata
from app.core.database import Base
from app.eval.seed_retrieval_cases import DOCS, CASES
from app.eval.retrieval_eval import make_rag_search_fn, evaluate_retrieval
from app.services.rag_service import upsert_batch

TEST_DB = "postgresql+asyncpg://zhiyao:zhiyao_dev_password@localhost:5432/zhiyao_test"


async def main():
    engine = create_async_engine(TEST_DB, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as db:
            await upsert_batch(
                db,
                [
                    {"doc_kind": "eval", "doc_id": d["doc_id"], "content": d["content"], "user_id": None}
                    for d in DOCS
                ],
            )
            fn = make_rag_search_fn(db, user_id=uuid.uuid4(), doc_kinds=["eval"], top_k=5)
            report = await evaluate_retrieval(CASES, fn, ks=(1, 3, 5))

        print("===== 检索基线（纯向量 BGE-M3，%d 文档 / %d 查询）=====" % (len(DOCS), len(CASES)))
        for key in ("mean_recall@1", "mean_recall@3", "mean_recall@5", "mean_mrr", "mean_ndcg@5"):
            val = report.get(key)
            print(f"  {key:18s}: {val:.3f}" if val is not None else f"  {key}: n/a")
        print("--- 逐条 ---")
        for r in report["per_case"]:
            print(f"  {r['id']:10s} recall@1={r['recall@1']:.0f} recall@3={r['recall@3']:.0f} mrr={r['mrr']:.3f}")
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
