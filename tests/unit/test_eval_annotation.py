"""阶段 B 最后一公里：低质召回导出样本 → 标注工作表 → 检索评估集 CASES 的桥接（纯函数 TDD）。"""
import pytest

from app.eval.annotation import build_worksheet, worksheet_to_cases, merge_cases


# ---------- build_worksheet ----------

def test_build_worksheet_skips_null_query():
    samples = [
        {"masked_query": None, "is_empty": True, "hit_count": 0, "score_avg": None},
        {"masked_query": "导数怎么算", "is_empty": True, "hit_count": 0, "score_avg": None},
        {"masked_query": "   ", "is_empty": True, "hit_count": 0, "score_avg": None},
    ]
    ws = build_worksheet(samples)
    queries = [c["query"] for c in ws["cases"]]
    assert queries == ["导数怎么算"]


def test_build_worksheet_dedups_and_counts_freq():
    samples = [
        {"masked_query": "牛顿第二定律", "is_empty": False, "hit_count": 2, "score_avg": 0.41},
        {"masked_query": "牛顿第二定律", "is_empty": False, "hit_count": 1, "score_avg": 0.33},
        {"masked_query": "光合作用", "is_empty": True, "hit_count": 0, "score_avg": None},
    ]
    ws = build_worksheet(samples)
    by_q = {c["query"]: c for c in ws["cases"]}
    assert by_q["牛顿第二定律"]["freq"] == 2
    assert by_q["光合作用"]["freq"] == 1
    # 高频在前（确定性排序）
    assert ws["cases"][0]["query"] == "牛顿第二定律"


def test_build_worksheet_stub_shape():
    samples = [{"masked_query": "abc", "is_empty": True, "hit_count": 0, "score_avg": None}]
    ws = build_worksheet(samples)
    c = ws["cases"][0]
    assert c["relevant"] == []            # 待人工填
    assert c["annotated"] is False
    assert isinstance(c["id"], str) and c["id"]
    assert "signal" in c
    assert ws["version"] == 1


def test_build_worksheet_signal_aggregates_worst():
    samples = [
        {"masked_query": "q", "is_empty": False, "hit_count": 3, "score_avg": 0.45},
        {"masked_query": "q", "is_empty": True, "hit_count": 0, "score_avg": None},
    ]
    ws = build_worksheet(samples)
    sig = ws["cases"][0]["signal"]
    assert sig["any_empty"] is True
    assert sig["min_score_avg"] == 0.45


def test_build_worksheet_ids_unique_and_stable():
    samples = [
        {"masked_query": "a", "is_empty": True, "hit_count": 0, "score_avg": None},
        {"masked_query": "b", "is_empty": True, "hit_count": 0, "score_avg": None},
    ]
    ws1 = build_worksheet(samples)
    ws2 = build_worksheet(samples)
    ids = [c["id"] for c in ws1["cases"]]
    assert len(ids) == len(set(ids))
    assert [c["id"] for c in ws2["cases"]] == ids  # 同输入同输出


# ---------- worksheet_to_cases ----------

def test_worksheet_to_cases_only_annotated():
    ws = {
        "version": 1,
        "cases": [
            {"id": "lq_0001", "query": "已标注", "relevant": ["d1"], "signal": {}, "annotated": False},
            {"id": "lq_0002", "query": "未标注", "relevant": [], "signal": {}, "annotated": False},
        ],
    }
    cases = worksheet_to_cases(ws)
    assert [c["id"] for c in cases] == ["lq_0001"]


def test_worksheet_to_cases_strips_meta_keeps_contract():
    ws = {
        "version": 1,
        "cases": [
            {"id": "lq_0001", "query": "q", "relevant": ["d1", "d2"],
             "signal": {"freq": 3}, "annotated": False, "freq": 3},
        ],
    }
    cases = worksheet_to_cases(ws)
    assert cases == [{"id": "lq_0001", "query": "q", "relevant": ["d1", "d2"]}]


def test_worksheet_to_cases_dedups_relevant_preserving_order():
    ws = {"version": 1, "cases": [
        {"id": "x", "query": "q", "relevant": ["d1", "d1", "d2"], "signal": {}},
    ]}
    cases = worksheet_to_cases(ws)
    assert cases[0]["relevant"] == ["d1", "d2"]


def test_worksheet_to_cases_rejects_blank_relevant():
    ws = {"version": 1, "cases": [
        {"id": "x", "query": "q", "relevant": ["", "  "], "signal": {}},
    ]}
    # 全为空白的 relevant 视为未标注，不产出 case
    assert worksheet_to_cases(ws) == []


# ---------- merge_cases ----------

def test_merge_cases_dedups_by_id_first_wins():
    seed = [{"id": "c1", "query": "seed", "relevant": ["s"]}]
    annotated = [
        {"id": "c1", "query": "dup", "relevant": ["x"]},
        {"id": "lq_1", "query": "new", "relevant": ["y"]},
    ]
    merged = merge_cases(seed, annotated)
    by_id = {c["id"]: c for c in merged}
    assert by_id["c1"]["query"] == "seed"     # 先到先得
    assert "lq_1" in by_id
    assert len(merged) == 2


# ---------- 元测试：产出符合 evaluate_retrieval 契约 ----------

def test_pipeline_output_is_valid_eval_cases():
    samples = [{"masked_query": "牛顿定律", "is_empty": True, "hit_count": 0, "score_avg": None}]
    ws = build_worksheet(samples)
    ws["cases"][0]["relevant"] = ["e0000000-0000-0000-0000-000000000003"]
    cases = worksheet_to_cases(ws)
    for c in cases:
        assert set(c.keys()) == {"id", "query", "relevant"}
        assert c["query"] and isinstance(c["query"], str)
        assert c["relevant"] and all(isinstance(r, str) and r for r in c["relevant"])
