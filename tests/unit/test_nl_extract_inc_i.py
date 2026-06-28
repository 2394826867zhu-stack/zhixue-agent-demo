"""INC-I NL 快速预填提取 单测（mock LLM，无 DB）。

设计：docs/superpowers/specs/2026-06-25-project-creation-system-v3-design.md §10
"""
import json

import pytest
from unittest.mock import AsyncMock, patch

from app.services.project_service import project_service
from app.llm.prompts.project_init import SYSTEM_DRAFT_EXTRACT, DRAFT_EXTRACT


@pytest.mark.asyncio
async def test_extract_passthrough():
    payload = {
        "fields": {
            "goal_type": {"value": "exam", "confidence": 0.9},
            "subject": {"value": "数理科学 > 数学", "confidence": 0.82},
        },
        "warnings": ["请确认考试日期"],
    }
    with patch("app.services.project_service.LLMClient") as M:
        M.return_value.generate = AsyncMock(return_value=json.dumps(payload))
        out = await project_service.extract_draft_fields(None, "u1", "我要考研数学")
    assert out.fields["goal_type"]["value"] == "exam"
    assert out.fields["subject"]["confidence"] == 0.82
    assert out.warnings == ["请确认考试日期"]


@pytest.mark.asyncio
async def test_extract_empty_input_no_llm_call():
    with patch("app.services.project_service.LLMClient") as M:
        gen = AsyncMock()
        M.return_value.generate = gen
        out = await project_service.extract_draft_fields(None, "u1", "   ")
    assert out.fields == {} and out.warnings == []
    gen.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_llm_failure_fallback():
    with patch("app.services.project_service.LLMClient") as M:
        M.return_value.generate = AsyncMock(side_effect=RuntimeError("llm down"))
        out = await project_service.extract_draft_fields(None, "u1", "我想学点东西")
    assert out.fields == {} and out.warnings  # 兜底 warning，不崩（200 不 500）


@pytest.mark.asyncio
async def test_extract_garbage_json_fallback():
    with patch("app.services.project_service.LLMClient") as M:
        M.return_value.generate = AsyncMock(return_value="这不是合法 JSON")
        out = await project_service.extract_draft_fields(None, "u1", "随便学学")
    assert out.fields == {}  # _extract_json 抛 → 兜底


def test_prompt_has_safety_rules():
    # 安全规则在 prompt（spec §10.2）：保守 goal_type + 日期不推断 + subject 映射 + 宁缺毋错
    assert "保守" in SYSTEM_DRAFT_EXTRACT
    assert "不推断" in SYSTEM_DRAFT_EXTRACT
    assert "宁缺毋错" in SYSTEM_DRAFT_EXTRACT
    assert "大类 > 细分" in DRAFT_EXTRACT
