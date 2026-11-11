from __future__ import annotations

import json
from types import SimpleNamespace as NS

import httpx
import pytest

pytest.importorskip("anthropic")

from app.research.llm import AnthropicProvider, ModelCallError, OpenAICompatibleProvider  # noqa: E402
from app.research.schemas import ClaimsOutput, ReviewOutput  # noqa: E402

VALID = '{"verdicts": []}'
SYSTEM = [{"type": "text", "text": "资料"}, {"type": "text", "text": "说明"}]


def anthropic_returning(stop_reason, content):
    usage = NS(input_tokens=5, output_tokens=7, cache_creation_input_tokens=2, cache_read_input_tokens=3)
    message = NS(stop_reason=stop_reason, content=content, usage=usage, stop_details=None)

    class Stream:
        def __enter__(self):
            return NS(get_final_message=lambda: message)

        def __exit__(self, *_):
            return False

    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.model, provider.effort, provider.max_tokens = "m", "high", 100
    provider._client = NS(beta=NS(messages=NS(stream=lambda **_: Stream())))
    return provider


def test_anthropic_output_and_usage():
    parsed, usage = anthropic_returning("end_turn", [NS(type="thinking"), NS(type="text", text=VALID)]).call(
        system=[], user="u", output=ReviewOutput
    )
    assert parsed.verdicts == [] and (usage.input_tokens, usage.cache_read_tokens, usage.cache_write_tokens) == (5, 3, 2)


@pytest.mark.parametrize(("stop", "content"), [("refusal", []), ("max_tokens", [NS(type="text", text="{")]), ("end_turn", [])])
def test_anthropic_unusable_responses_keep_billed_usage(stop, content):
    with pytest.raises(ModelCallError) as caught:
        anthropic_returning(stop, content).call(system=[], user="u", output=ReviewOutput)
    assert caught.value.usage.output_tokens == 7


def openai_response(content, finish="stop", prompt=100, cached=40, completion=9):
    return httpx.Response(200, json={
        "choices": [{"message": {"content": content}, "finish_reason": finish}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion, "prompt_tokens_details": {"cached_tokens": cached}},
    })


def openai_provider(responses, seen=None):
    queue = list(responses)

    def handler(request):
        if seen is not None:
            seen.append(request)
        return queue.pop(0)

    return OpenAICompatibleProvider("glm-x", "secret", "https://example.test/api/v4", transport=httpx.MockTransport(handler))


def test_openai_request_and_cache_accounting():
    seen = []
    parsed, usage = openai_provider([openai_response(VALID)], seen).call(system=SYSTEM, user="u", output=ReviewOutput)
    body = json.loads(seen[0].content)
    assert parsed.verdicts == [] and str(seen[0].url) == "https://example.test/api/v4/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer secret" and body["model"] == "glm-x"
    assert body["messages"][0]["content"].startswith("资料\n\n说明") and "JSON Schema" in body["messages"][0]["content"]
    assert (usage.input_tokens, usage.cache_read_tokens, usage.output_tokens) == (60, 40, 9)


def test_stage_options_apply_only_to_their_stage():
    seen = []
    queue = [openai_response(VALID), openai_response('{"claims": []}')]

    def handler(request):
        seen.append(json.loads(request.content))
        return queue.pop(0)

    provider = OpenAICompatibleProvider(
        "m", "k", "https://example.test/v4", transport=httpx.MockTransport(handler),
        stage_options={"ReviewOutput": {"thinking": {"type": "disabled"}}},
    )
    provider.call(system=SYSTEM, user="u", output=ReviewOutput)
    provider.call(system=SYSTEM, user="u", output=ClaimsOutput)
    assert seen[0]["thinking"] == {"type": "disabled"} and "thinking" not in seen[1]


def test_openai_client_identity_is_not_overridden():
    seen = []
    openai_provider([openai_response(VALID)], seen).call(system=SYSTEM, user="u", output=ReviewOutput)
    assert seen[0].headers["user-agent"].startswith("python-httpx/")


def test_openai_retries_invalid_json_and_sums_usage():
    _, usage = openai_provider([openai_response("不是 JSON"), openai_response(VALID)]).call(system=SYSTEM, user="u", output=ReviewOutput)
    assert usage.output_tokens == 18


@pytest.mark.parametrize(
    "responses",
    [
        [openai_response("x"), openai_response("y")],
        [openai_response(VALID, finish="length")],
        [httpx.Response(401, text="unauthorized")],
    ],
)
def test_openai_failures_raise(responses):
    with pytest.raises(ModelCallError):
        openai_provider(responses).call(system=SYSTEM, user="u", output=ReviewOutput)


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr("app.research.llm.time.sleep", lambda _: None)


def test_gateway_errors_are_retried(no_sleep):
    parsed, _ = openai_provider([httpx.Response(504, text="x"), httpx.Response(429, text="x"), openai_response(VALID)]).call(
        system=SYSTEM, user="u", output=ReviewOutput
    )
    assert parsed.verdicts == []


def test_gateway_errors_give_up_after_limit(no_sleep):
    with pytest.raises(ModelCallError):
        openai_provider([httpx.Response(504, text="x") for _ in range(5)]).call(system=SYSTEM, user="u", output=ReviewOutput)


def test_auth_errors_are_not_retried(no_sleep):
    seen = []
    with pytest.raises(ModelCallError):
        openai_provider([httpx.Response(401, text="x")], seen).call(system=SYSTEM, user="u", output=ReviewOutput)
    assert len(seen) == 1
