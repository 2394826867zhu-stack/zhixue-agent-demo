"""阶段 B 最后一公里 · 第 1 步：导出低质召回脱敏样本 → 待标注工作表。

从生产库 `rag_retrieval_traces` 拉取最近 N 天采集到的低质召回（零召回 / 伪召回）
脱敏 query，去重 + 聚合频次/诊断信号，写成 JSON 工作表供人工标注期望 doc_id。

只读（select），不写库。手动跑：
    python scripts/export_annotation_worksheet.py --days 30 --limit 200
    # → 默认写到 app/eval/annotations/worksheet.json

标注：打开该 JSON，给每条 case 的 "relevant" 填上本应召回的 doc_id 列表（字符串）。
留空 = 未标注（跑评估时跳过）。标注完跑 scripts/run_annotated_eval.py。
"""
import argparse
import asyncio
import json
import os

from app.core.database import AsyncSessionLocal
from app.eval.annotation import build_worksheet
from app.services.rag_service import list_low_quality_samples

DEFAULT_OUT = os.path.join("app", "eval", "annotations", "worksheet.json")


async def _run(days: int, limit: int, out: str) -> None:
    async with AsyncSessionLocal() as db:
        samples = await list_low_quality_samples(db, days=days, limit=limit)
    worksheet = build_worksheet(samples)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(worksheet, f, ensure_ascii=False, indent=2)
    n_raw = len(samples)
    n_cases = len(worksheet["cases"])
    print(f"拉取低质样本 {n_raw} 条 → 去重后 {n_cases} 个待标注 query")
    print(f"工作表已写入：{out}")
    if n_cases:
        print("下一步：编辑该文件，为每条 case 填 relevant=[doc_id...]，再跑 run_annotated_eval.py")
    else:
        print("（暂无低质样本——说明近期召回质量健康，或采集窗口内无流量）")


def main() -> None:
    p = argparse.ArgumentParser(description="导出低质召回样本为标注工作表")
    p.add_argument("--days", type=int, default=30, help="回溯天数（默认 30）")
    p.add_argument("--limit", type=int, default=200, help="最多导出条数（默认 200）")
    p.add_argument("--out", default=DEFAULT_OUT, help=f"输出路径（默认 {DEFAULT_OUT}）")
    args = p.parse_args()
    asyncio.run(_run(args.days, args.limit, args.out))


if __name__ == "__main__":
    main()
