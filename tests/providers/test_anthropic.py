"""Tests for AnthropicProvider over a mocked HTTP transport."""

import json

import anthropic
import httpx
import pytest

from ask_cli.config import ProviderConfig
from ask_cli.exceptions import ModelNotFoundError, ProviderError
from ask_cli.providers.anthropic import AnthropicProvider
from tests.providers.conftest import (
    anthropic_sse,
    anthropic_sse_complete,
    broken_sse_response,
    error_response,
    raising,
    sse_response,
)

MESSAGES = [{"role": "user", "content": "hi"}]


@pytest.fixture
def make_provider(http_client):
    def build(handler) -> AnthropicProvider:
        provider = AnthropicProvider(ProviderConfig(api_key="test-key"))
        provider._client = anthropic.Anthropic(
            api_key="test-key", http_client=http_client(handler), max_retries=0
        )
        return provider

    return build


def test_streams_text_chunks(make_provider):
    provider = make_provider(lambda request: sse_response(anthropic_sse_complete("Hel", "lo")))
    assert list(provider.stream(MESSAGES, "m", 100)) == ["Hel", "lo"]


def test_sends_system_prompt_and_max_tokens(make_provider):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return sse_response(anthropic_sse_complete("ok"))

    list(make_provider(handler).stream(MESSAGES, "m", 123, system_prompt="be terse"))
    assert seen["system"] == "be terse"
    assert seen["max_tokens"] == 123


@pytest.mark.parametrize(
    ("status", "error_type", "code"),
    [(401, ProviderError, 401), (429, ProviderError, 429), (404, ModelNotFoundError, 404)],
)
def test_http_errors_map_to_typed_errors(make_provider, status, error_type, code):
    provider = make_provider(lambda request: error_response(status))
    with pytest.raises(error_type) as exc_info:
        list(provider.stream(MESSAGES, "m", 100))
    assert exc_info.value.status_code == code
    assert exc_info.value.provider == "anthropic"


def test_server_error_keeps_status(make_provider):
    provider = make_provider(lambda request: error_response(500, "overloaded"))
    with pytest.raises(ProviderError) as exc_info:
        list(provider.stream(MESSAGES, "m", 100))
    assert exc_info.value.status_code == 500


def test_unreachable_host_is_a_provider_error_with_hint(make_provider):
    provider = make_provider(raising(httpx.ConnectError("name resolution failed")))
    with pytest.raises(ProviderError) as exc_info:
        list(provider.stream(MESSAGES, "m", 100))
    assert "Cannot reach Anthropic" in str(exc_info.value)
    assert exc_info.value.hint


def test_timeout_is_reported_as_timeout(make_provider):
    provider = make_provider(raising(httpx.ReadTimeout("slow")))
    with pytest.raises(ProviderError, match="timed out"):
        list(provider.stream(MESSAGES, "m", 100))


def test_connection_drop_mid_stream_is_a_provider_error(make_provider):
    provider = make_provider(lambda request: broken_sse_response(anthropic_sse("Hello")))
    received: list[str] = []
    with pytest.raises(ProviderError, match="lost"):
        for chunk in provider.stream(MESSAGES, "m", 100):
            received.append(chunk)
    assert received == ["Hello"]


def test_missing_api_key_fails_before_any_request():
    provider = AnthropicProvider(ProviderConfig())
    with pytest.raises(ProviderError, match="not configured"):
        list(provider.stream(MESSAGES, "m", 100))


@pytest.mark.parametrize(
    ("stop_reason", "expected"),
    [("end_turn", "end"), ("max_tokens", "max_tokens"), ("refusal", "filtered")],
)
def test_records_why_the_stream_stopped(make_provider, stop_reason, expected):
    body = anthropic_sse_complete("partial", stop_reason=stop_reason)
    provider = make_provider(lambda request: sse_response(body))
    list(provider.stream(MESSAGES, "m", 100))
    assert provider.last_stop_reason == expected


def test_custom_base_url_is_used():
    provider = AnthropicProvider(
        ProviderConfig(api_key="k", base_url="https://proxy.example/anthropic")
    )
    assert str(provider._get_client().base_url).startswith("https://proxy.example/anthropic")


def test_zai_is_the_anthropic_provider_with_its_own_identity():
    from ask_cli.providers.zai import ZaiProvider

    assert issubclass(ZaiProvider, AnthropicProvider)
    assert (ZaiProvider.provider_id, ZaiProvider.display_name) == ("zai", "Z.ai")
