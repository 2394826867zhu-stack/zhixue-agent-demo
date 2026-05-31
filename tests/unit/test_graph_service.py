def test_prerequisite_edge_model_exists():
    from app.models.prerequisite_edge import PrerequisiteEdge
    for col in ("from_kp_id", "to_kp_id", "confidence", "source", "user_id"):
        assert hasattr(PrerequisiteEdge, col)
