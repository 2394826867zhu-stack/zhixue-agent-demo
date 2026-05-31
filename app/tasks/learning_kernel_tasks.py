"""学习内核 · 周期任务：掌握度校准监控（M10）。"""
from __future__ import annotations

import asyncio
import logging

from celery import shared_task

from app.eval import learning_gain as lg

logger = logging.getLogger(__name__)

ECE_ALERT_THRESHOLD = 0.2  # ECE 超此值告警（起步阈值，按数据校准）


def assess_calibration(pairs: list[tuple[float, bool]], threshold: float = ECE_ALERT_THRESHOLD) -> float:
    """计算 ECE，超阈值告警。返回 ECE。纯逻辑，便于测试。"""
    ece = lg.expected_calibration_error(pairs, n_bins=10)
    if ece > threshold:
        logger.error("掌握度校准失准告警：ECE=%.3f > %.2f（p_mastery 需回炉/重拟合）", ece, threshold)
    return ece


async def _collect_pairs_async() -> list[tuple[float, bool]]:
    """从最近作答收集 (答前预测概率, 实际答对) 对。

    P0 兜底实现：暂无"答前预测快照"数据管道时返回空列表（任务安全 no-op）。
    完整数据管道在 P4 复利闭环建（届时从答题事件落一份答前 p_mastery 快照）。
    """
    return []


@shared_task(name="app.tasks.learning_kernel_tasks.mastery_calibration_check", time_limit=120)
def mastery_calibration_check() -> dict:
    pairs = asyncio.run(_collect_pairs_async())
    ece = assess_calibration(pairs)
    return {"n_pairs": len(pairs), "ece": ece}
