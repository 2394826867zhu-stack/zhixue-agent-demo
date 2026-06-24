"""v3 F1: 纯生成式框架构建器单测（校验 + 重试 + 全失败 None）。"""
import json
import pytest

from app.services import framework_service as fs


_VALID = {
    "phases": [{"name": "语音与文字", "description": "发音基础", "weeks": 14}],
    "chapters": [
        {"title": "德语字母表", "phase_name": "语音与文字",
         "lessons": [{"title": "元音 a/e/i/o/u 发音", "kp_names": ["元音 a", "元音 e"]}]},
    ],
    "prereqs": [["元音 a", "元音 e"]],
}


def test_validate_accepts_well_formed():
    assert fs.validate_framework(_VALID) is True


@pytest.mark.parametrize("bad", [
    {},
    {"phases": [], "chapters": []},
    {"phases": [{"name": ""}], "chapters": [{"title": "x", "lessons": [{"title": "y"}]}]},   # 空 phase name
    {"phases": [{"name": "p"}], "chapters": []},                                              # 无 chapter
    {"phases": [{"name": "p"}], "chapters": [{"title": "c", "lessons": []}]},                 # 章节无课时
    {"phases": [{"name": "p"}], "chapters": [{"title": "c", "lessons": [{"title": ""}]}]},    # 课时无标题
    {"phases": [{"name": "p"}], "chapters": [{"lessons": [{"title": "y"}]}]},                 # 章节无标题
])
def test_validate_rejects_malformed(bad):
    assert fs.validate_framework(bad) is False


@pytest.mark.asyncio
async def test_generate_returns_valid_first_try(monkeypatch):
    async def _gen(self, **k):
        return "```json\n" + json.dumps(_VALID, ensure_ascii=False) + "\n```"
    monkeypatch.setattr("app.llm.client.LLMClient.generate", _gen)
    out = await fs.generate_framework(name="德语", subject="德语", summary="完全学会", weeks=84)
    assert out is not None and out["chapters"][0]["title"] == "德语字母表"


@pytest.mark.asyncio
async def test_generate_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}
    async def _gen(self, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return "这不是 JSON，纯文本胡言乱语"      # 第一次无效 → 重试
        return json.dumps(_VALID, ensure_ascii=False)
    monkeypatch.setattr("app.llm.client.LLMClient.generate", _gen)
    out = await fs.generate_framework(name="德语", subject="德语", summary="", weeks=84)
    assert out is not None and calls["n"] == 2, "应重试一次后成功"


@pytest.mark.asyncio
async def test_generate_all_fail_returns_none(monkeypatch):
    async def _boom(self, **k):
        raise RuntimeError("llm down")
    monkeypatch.setattr("app.llm.client.LLMClient.generate", _boom)
    out = await fs.generate_framework(name="德语", subject="德语", summary="", weeks=84)
    assert out is None, "纯生成式全失败应返回 None（调用方置 failed，不退模板）"
