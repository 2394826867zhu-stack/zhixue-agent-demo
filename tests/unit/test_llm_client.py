import pytest

from app.llm.client import LLMClient


@pytest.mark.asyncio
async def test_openai_compat_sends_image_content():
    captured = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)

            class Message:
                content = "ok"

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    client = LLMClient()

    result = await client._call_openai_compat(
        FakeClient(),
        "gpt-4o",
        "请识别图片",
        "system",
        image_b64="abc123",
    )

    assert result == "ok"
    user_content = captured["messages"][-1]["content"]
    assert isinstance(user_content, list)
    assert user_content[1]["type"] == "image_url"
    assert user_content[1]["image_url"]["url"] == "data:image/png;base64,abc123"
