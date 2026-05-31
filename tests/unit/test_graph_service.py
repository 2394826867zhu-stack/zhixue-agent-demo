from app.services import graph_service as gs


def test_prerequisite_edge_model_exists():
    from app.models.prerequisite_edge import PrerequisiteEdge
    for col in ("from_kp_id", "to_kp_id", "confidence", "source", "user_id"):
        assert hasattr(PrerequisiteEdge, col)


# ---------- 防环 ----------

def test_would_create_cycle_detects_direct_back_edge():
    edges = [("A", "B")]
    assert gs.would_create_cycle(edges, "B", "A") is True
    assert gs.would_create_cycle(edges, "A", "C") is False


def test_would_create_cycle_detects_transitive():
    edges = [("A", "B"), ("B", "C")]
    assert gs.would_create_cycle(edges, "C", "A") is True   # C->A 经 A->B->C 成环
    assert gs.would_create_cycle(edges, "A", "C") is False  # 已可达，非环（重复另行去重）


def test_self_loop_is_cycle():
    assert gs.would_create_cycle([], "A", "A") is True


# ---------- 可学习前沿 ----------

def test_learnable_frontier_picks_mastered_prereq_unmastered_self():
    mastery = {"A": 0.9, "B": 0.2, "C": 0.2}
    edges = [("A", "B")]
    frontier = gs.learnable_frontier(mastery, edges, threshold=0.6)
    assert "B" in frontier   # 先修 A 已掌握、B 未掌握 → 前沿
    assert "C" in frontier   # 无先修、未掌握 → 前沿
    assert "A" not in frontier  # 已掌握


def test_learnable_frontier_excludes_node_with_unmastered_prereq():
    mastery = {"A": 0.9, "B": 0.2, "C": 0.2}
    edges = [("A", "B"), ("B", "C")]
    frontier = gs.learnable_frontier(mastery, edges, threshold=0.6)
    assert "B" in frontier
    assert "C" not in frontier  # 先修 B 没掌握 → 不在前沿（应先学 B）


# ---------- 根因回溯 ----------

def test_root_cause_traces_to_weakest_prerequisite():
    mastery = {"A": 0.9, "B": 0.2, "C": 0.3}
    edges = [("A", "B"), ("B", "C")]
    assert gs.root_cause("C", mastery, edges, threshold=0.6) == "B"


def test_root_cause_none_when_all_prereqs_mastered():
    mastery = {"A": 0.9, "B": 0.9, "C": 0.3}
    edges = [("A", "B"), ("B", "C")]
    assert gs.root_cause("C", mastery, edges, threshold=0.6) == "C"


def test_root_cause_picks_lowest_mastery_branch():
    # C 有两个薄弱先修 A(0.1) 和 B(0.4)，应沿掌握度最低的 A 回溯
    mastery = {"A": 0.1, "B": 0.4, "C": 0.3}
    edges = [("A", "C"), ("B", "C")]
    assert gs.root_cause("C", mastery, edges, threshold=0.6) == "A"
