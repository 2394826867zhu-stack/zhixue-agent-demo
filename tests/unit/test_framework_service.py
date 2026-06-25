"""v3 F1: 纯生成式框架构建器单测（校验 + 重试 + 全失败 None）。"""
import json
import pytest

from app.services import framework_service as fs


def _well_formed() -> dict:
    """真实规模的合格框架（INC-C 后硬闸要求 total_lessons >= max(chapters, 8)）。"""
    chapters = [
        {"title": "德语字母表", "phase_name": "语音与文字", "lessons": [
            {"title": "元音 a/e/i/o/u 发音", "kp_names": ["元音a", "元音e"], "difficulty": "blue"},
            {"title": "辅音发音", "kp_names": ["辅音b", "辅音d"], "difficulty": "blue"},
        ]},
        {"title": "基础词汇", "phase_name": "语音与文字", "lessons": [
            {"title": "数字与时间", "kp_names": ["数字1-100"], "difficulty": "blue"},
            {"title": "日常问候", "kp_names": ["问候语"], "difficulty": "blue"},
        ]},
        {"title": "名词与冠词", "phase_name": "基础语法", "lessons": [
            {"title": "三种性别冠词", "kp_names": ["定冠词", "不定冠词"], "difficulty": "purple"},
            {"title": "名词复数", "kp_names": ["复数规则"], "difficulty": "purple"},
        ]},
        {"title": "动词变位", "phase_name": "基础语法", "lessons": [
            {"title": "现在时变位", "kp_names": ["规则动词变位"], "difficulty": "purple"},
            {"title": "情态动词", "kp_names": ["情态动词用法"], "difficulty": "gold"},
        ]},
        {"title": "句子结构", "phase_name": "基础语法", "lessons": [
            {"title": "语序规则", "kp_names": ["框型结构"], "difficulty": "gold"},
            {"title": "从句", "kp_names": ["从句语序"], "difficulty": "gold", "optional": True},
        ]},
    ]
    return {
        "phases": [{"name": "语音与文字", "description": "发音基础", "weeks": 4},
                   {"name": "基础语法", "description": "语法骨架", "weeks": 10}],
        "chapters": chapters,
        "prereqs": [["元音a", "辅音b"], ["定冠词", "复数规则"], ["规则动词变位", "情态动词用法"]],
    }


_VALID = _well_formed()


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


def test_validate_rejects_flat_placeholder():
    """INC-C 反扁平占位（feasibility-audit 断点①）：章节有但课时太少 → 拒。"""
    flat = {
        "phases": [{"name": "p"}],
        "chapters": [
            {"title": f"章{i}", "phase_name": "p", "lessons": [{"title": f"课{i}"}]}
            for i in range(4)
        ],
    }  # 4 章 4 课 < max(chapters=4, 8)
    assert fs.validate_framework(flat) is False


@pytest.mark.asyncio
async def test_generate_accepts_inc_c_params(monkeypatch):
    """INC-C 富化签名（goal_type/mastery_depth/domain_template/scope）被接受并注入 prompt。"""
    captured = {}

    async def _gen(self, **k):
        captured["prompt"] = k.get("prompt", "")
        return json.dumps(_VALID, ensure_ascii=False)

    monkeypatch.setattr("app.llm.client.LLMClient.generate", _gen)
    out = await fs.generate_framework(
        name="德语", subject="语言文学 > 法语/德语/西语", summary="",
        weeks=14, goal_type="exam", mastery_depth="deep",
        domain_template="语音 → 词汇 → 语法", scope_mode="full_subject",
    )
    assert out is not None
    # goal_type=exam 的刚性措辞 + mastery_depth=deep 的难度分布措辞注入了 prompt
    assert "考试备考" in captured["prompt"]
    assert "迁移" in captured["prompt"]
