import typing
from app.schemas.studyspace_timeline import NODE_KIND_T


def test_spot_quiz_generated_is_valid_kind():
    assert "spot_quiz_generated" in typing.get_args(NODE_KIND_T)
