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
async def test_recall_stats_empty_table(db):
    stats = await R.recall_stats(db, days=7)
    assert stats["total"] == 0
    assert stats["empty_count"] == 0
    assert stats["empty_rate"] == 0.0
    assert stats["avg_score"] is None
    assert stats["kind_totals"] == {}
