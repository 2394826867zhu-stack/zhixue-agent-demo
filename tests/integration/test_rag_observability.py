"""E 可观测·第二步：召回 trace 落库 + 聚合统计。"""
import uuid

import pytest

from app.services import rag_service as R


@pytest.mark.asyncio
async def test_record_retrieval_persists_metrics(db):
    uid = uuid.uuid4()
    row = await R.record_retrieval(
        db,
        user_id=uid,
        session_id=None,
        source="auto_inject",
        query="2x的导数",
        hits=[
            {"doc_kind": "note", "score": 0.8, "doc_id": "n1"},
            {"doc_kind": "kp", "score": 0.6, "doc_id": "k1"},
        ],
    )
    assert row.id is not None
    assert row.hit_count == 2
    assert row.is_empty is False
    assert row.query_len == len("2x的导数")
    assert row.kind_distribution == {"note": 1, "kp": 1}


@pytest.mark.asyncio
async def test_recall_stats_aggregates_empty_rate_and_kinds(db):
    uid = uuid.uuid4()
    await R.record_retrieval(db, user_id=uid, session_id=None, source="auto_inject",
                             query="q1", hits=[{"doc_kind": "note", "score": 0.8, "doc_id": "n1"},
                                               {"doc_kind": "kp", "score": 0.6, "doc_id": "k1"}])
    await R.record_retrieval(db, user_id=uid, session_id=None, source="auto_inject",
                             query="q2", hits=[{"doc_kind": "note", "score": 0.4, "doc_id": "n2"}])
    await R.record_retrieval(db, user_id=uid, session_id=None, source="auto_inject",
                             query="q3", hits=[])

    stats = await R.recall_stats(db, days=7)
    assert stats["total"] == 3
    assert stats["empty_count"] == 1
    assert round(stats["empty_rate"], 4) == round(1 / 3, 4)
    assert stats["kind_totals"] == {"note": 2, "kp": 1}
    assert stats["avg_score"] is not None  # 非空召回的平均 score_avg


@pytest.mark.asyncio
async def test_recall_stats_flags_low_score_pseudo_recall(db):
    """伪召回：有命中但相关度低（score 偏低），比零召回更隐蔽的检索问题。"""
    uid = uuid.uuid4()
    # 高分召回（健康）
    await R.record_retrieval(db, user_id=uid, session_id=None, source="auto_inject",
                             query="q1", hits=[{"doc_kind": "note", "score": 0.85, "doc_id": "n1"}])
    # 低分召回（伪召回）
    await R.record_retrieval(db, user_id=uid, session_id=None, source="auto_inject",
                             query="q2", hits=[{"doc_kind": "note", "score": 0.30, "doc_id": "n2"}])
    # 零召回（单独计 empty，不算 low_score）
    await R.record_retrieval(db, user_id=uid, session_id=None, source="auto_inject",
                             query="q3", hits=[])

    stats = await R.recall_stats(db, days=7, low_score_threshold=0.5)
    assert stats["low_score_threshold"] == 0.5
    assert stats["low_score_count"] == 1  # 仅 q2（非空且 avg < 0.5）


@pytest.mark.asyncio
async def test_collects_masked_query_only_for_low_quality(db):
    """仅低质召回（零召回 / 伪召回）采集脱敏 query；健康召回不存。"""
    uid = uuid.uuid4()
    healthy = await R.record_retrieval(db, user_id=uid, session_id=None, source="auto_inject",
                                       query="高分健康问题", hits=[{"doc_kind": "note", "score": 0.9, "doc_id": "n1"}])
    assert healthy.masked_query is None

    empty = await R.record_retrieval(db, user_id=uid, session_id=None, source="auto_inject",
                                     query="一个冷门没召回的问题", hits=[])
    assert empty.masked_query == "一个冷门没召回的问题"

    low = await R.record_retrieval(db, user_id=uid, session_id=None, source="auto_inject",
                                   query="低分伪召回问题", hits=[{"doc_kind": "note", "score": 0.3, "doc_id": "n2"}])
    assert low.masked_query == "低分伪召回问题"


@pytest.mark.asyncio
async def test_masks_pii_in_collected_query(db):
    """采集前经 pii_filter 脱敏，手机号等不落库。"""
    uid = uuid.uuid4()
    row = await R.record_retrieval(db, user_id=uid, session_id=None, source="auto_inject",
                                   query="我的手机是13800138000帮我查", hits=[])
    assert row.masked_query is not None
    assert "13800138000" not in row.masked_query


@pytest.mark.asyncio
async def test_list_low_quality_samples_for_eval_curation(db):
    """导出待标注的低质召回样本，供沉淀进检索评估集。"""
    uid = uuid.uuid4()
    await R.record_retrieval(db, user_id=uid, session_id=None, source="auto_inject",
                             query="冷门问题", hits=[])
    await R.record_retrieval(db, user_id=uid, session_id=None, source="auto_inject",
                             query="健康问题", hits=[{"doc_kind": "note", "score": 0.9, "doc_id": "n1"}])

    samples = await R.list_low_quality_samples(db, days=7, limit=50)
    assert len(samples) == 1
    s = samples[0]
    assert s["masked_query"] == "冷门问题"
    assert s["is_empty"] is True
    assert s["hit_count"] == 0


@pytest.mark.asyncio
async def test_recall_stats_empty_table(db):
    stats = await R.recall_stats(db, days=7)
    assert stats["total"] == 0
    assert stats["empty_count"] == 0
    assert stats["empty_rate"] == 0.0
    assert stats["avg_score"] is None
    assert stats["kind_totals"] == {}
