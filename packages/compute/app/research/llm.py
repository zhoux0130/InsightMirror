"""Model providers behind one interface, so the pipeline and its tests never depend on a vendor."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

EFFORT = "high"
MAX_TOKENS = 32000
FALLBACK_BETA = "server-side-fallback-2026-07-01"
HTTP_TIMEOUT_SECONDS = 600
JSON_ATTEMPTS = 2
HTTP_ATTEMPTS = 5
RETRY_BASE_SECONDS = 10
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class Usage:
    """input_tokens excludes cache reads and writes for every provider."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class ModelCallError(RuntimeError):
    """The model stopped without a usable answer. Tokens may still have been billed."""

    def __init__(self, message: str, usage: Usage | None = None):
        super().__init__(message)
        self.usage = usage or Usage()


class Provider(Protocol):
    model: str

    def call(self, *, system: list[dict[str, Any]], user: str, output: type[T]) -> tuple[T, Usage]: ...


class StructuredClient(Protocol):
    model: str

    def complete(self, *, system: list[dict[str, Any]], user: str, output: type[T]) -> T: ...


def strict_schema(output: type[BaseModel]) -> dict[str, Any]:
    """Drop annotation keywords. No model here has a field named title or default."""

    def clean(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: clean(v) for k, v in node.items() if k not in ("title", "default")}
        if isinstance(node, list):
            return [clean(v) for v in node]
        return node

    return clean(output.model_json_schema())


class AnthropicProvider:
    def __init__(self, model: str, api_key: str, effort: str = EFFORT, max_tokens: int = MAX_TOKENS):
        import anthropic

        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=4)

    def call(self, *, system: list[dict[str, Any]], user: str, output: type[T]) -> tuple[T, Usage]:
        with self._client.beta.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            betas=[FALLBACK_BETA],
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": strict_schema(output)},
            },
            fallbacks="default",
        ) as stream:
            message = stream.get_final_message()

        usage = Usage(
            input_tokens=message.usage.input_tokens or 0,
            output_tokens=message.usage.output_tokens or 0,
            cache_read_tokens=getattr(message.usage, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(message.usage, "cache_creation_input_tokens", 0) or 0,
        )
        if message.stop_reason == "refusal":
            raise ModelCallError(f"model declined: {getattr(message, 'stop_details', None)}", usage)
        if message.stop_reason == "max_tokens":
            raise ModelCallError("output truncated at max_tokens", usage)
        text = next((b.text for b in message.content if b.type == "text"), None)
        if text is None:
            raise ModelCallError(f"no text block, stop_reason={message.stop_reason}", usage)
        try:
            return output.model_validate_json(text), usage
        except ValidationError as error:
            raise ModelCallError(f"schema validation failed: {error}", usage) from error


class OpenAICompatibleProvider:
    """GLM and Kimi open-platform chat completions. Keeps an honest default client identity."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        transport: httpx.BaseTransport | None = None,
        stage_options: dict[str, dict[str, Any]] | None = None,
    ):
        self.model = model
        self._stage_options = stage_options or {}
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=HTTP_TIMEOUT_SECONDS,
            transport=transport,
        )

    @staticmethod
    def _usage(payload: dict[str, Any]) -> Usage:
        usage = payload.get("usage") or {}
        details = usage.get("prompt_tokens_details") or {}
        cached = details.get("cached_tokens") or usage.get("cached_tokens") or 0
        return Usage(
            input_tokens=max((usage.get("prompt_tokens") or 0) - cached, 0),
            output_tokens=usage.get("completion_tokens") or 0,
            cache_read_tokens=cached,
        )

    def _post(self, body: dict[str, Any], usage_so_far: Usage) -> httpx.Response:
        """Retry only gateway-level failures; quota and auth errors surface immediately after retries."""
        for attempt in range(HTTP_ATTEMPTS):
            last_attempt = attempt == HTTP_ATTEMPTS - 1
            try:
                response = self._client.post("chat/completions", json=body)
            except httpx.TransportError as error:
                if last_attempt:
                    raise ModelCallError(f"transport error: {type(error).__name__}", usage_so_far) from error
            else:
                if response.status_code not in RETRYABLE_STATUS or last_attempt:
                    return response
            time.sleep(RETRY_BASE_SECONDS * 2**attempt)
        raise AssertionError("unreachable")

    def call(self, *, system: list[dict[str, Any]], user: str, output: type[T]) -> tuple[T, Usage]:
        schema = json.dumps(strict_schema(output), ensure_ascii=False)
        system_text = "\n\n".join(part["text"] for part in system)
        system_text += f"\n\n只输出一个符合下列 JSON Schema 的 JSON 对象，所有字段都必须出现，不要输出其他文字：\n{schema}"
        total = Usage()
        last_error = ""
        for _ in range(JSON_ATTEMPTS):
            response = self._post(
                {
                    "model": self.model,
                    "max_tokens": MAX_TOKENS,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": system_text}, {"role": "user", "content": user}],
                    **self._stage_options.get(output.__name__, {}),
                },
                total,
            )
            if response.status_code != 200:
                raise ModelCallError(f"http {response.status_code}: {response.text[:300]}", total)
            payload = response.json()
            usage = self._usage(payload)
            total = Usage(
                input_tokens=total.input_tokens + usage.input_tokens,
                output_tokens=total.output_tokens + usage.output_tokens,
                cache_read_tokens=total.cache_read_tokens + usage.cache_read_tokens,
            )
            choice = payload["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ModelCallError("output truncated at max_tokens", total)
            try:
                return output.model_validate_json(choice["message"]["content"] or ""), total
            except ValidationError as error:
                last_error = str(error)
        raise ModelCallError(f"schema validation failed after {JSON_ATTEMPTS} attempts: {last_error}", total)
