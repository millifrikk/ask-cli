"""Tests for GoogleProvider message mapping and error handling."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from google.genai import errors as genai_errors

from ask_cli.config import ProviderConfig
from ask_cli.exceptions import ModelNotFoundError, ProviderError
from ask_cli.providers.google import GoogleProvider

MESSAGES = [
    {"role": "user", "content": "q1"},
    {"role": "assistant", "content": "a1"},
    {"role": "user", "content": "q2"},
]


@pytest.fixture
def client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def provider(client) -> GoogleProvider:
    google = GoogleProvider(ProviderConfig(api_key="test-key"))
    google._client = client
    return google


def _chunks(*texts: str | None):
    return iter(SimpleNamespace(text=text) for text in texts)


def _client_error(code: int, message: str) -> genai_errors.ClientError:
    return genai_errors.ClientError(code, {"error": {"code": code, "message": message}})


def test_streams_text_and_skips_empty_chunks(provider, client):
    client.models.generate_content_stream.return_value = _chunks("Hel", None, "", "lo")
    assert list(provider.stream(MESSAGES, "gemini", 100)) == ["Hel", "lo"]


def test_maps_assistant_role_to_model_and_passes_system_instruction(provider, client):
    client.models.generate_content_stream.return_value = _chunks("ok")
    list(provider.stream(MESSAGES, "gemini", 77, system_prompt="be terse"))
    kwargs = client.models.generate_content_stream.call_args.kwargs
    assert [content.role for content in kwargs["contents"]] == ["user", "model", "user"]
    assert kwargs["config"].system_instruction == "be terse"
    assert kwargs["config"].max_output_tokens == 77


@pytest.mark.parametrize(
    ("code", "message"),
    [(401, "unauthenticated"), (403, "permission denied"), (400, "API key not valid.")],
)
def test_auth_failures_map_to_401(provider, client, code, message):
    client.models.generate_content_stream.side_effect = _client_error(code, message)
    with pytest.raises(ProviderError) as exc_info:
        list(provider.stream(MESSAGES, "gemini", 100))
    assert exc_info.value.status_code == 401
    assert exc_info.value.provider == "google"


def test_rate_limit_maps_to_429(provider, client):
    client.models.generate_content_stream.side_effect = _client_error(429, "quota")
    with pytest.raises(ProviderError) as exc_info:
        list(provider.stream(MESSAGES, "gemini", 100))
    assert exc_info.value.status_code == 429


def test_unknown_model_maps_to_model_not_found(provider, client):
    client.models.generate_content_stream.side_effect = _client_error(404, "not found")
    with pytest.raises(ModelNotFoundError):
        list(provider.stream(MESSAGES, "gemini-nope", 100))


def test_connection_drop_mid_stream(provider, client):
    def broken():
        yield SimpleNamespace(text="Hi")
        raise httpx.ReadError("reset")

    client.models.generate_content_stream.return_value = broken()
    with pytest.raises(ProviderError, match="lost"):
        list(provider.stream(MESSAGES, "gemini", 100))


def test_programming_errors_are_not_disguised_as_api_errors(provider, client):
    client.models.generate_content_stream.side_effect = TypeError("bug in our code")
    with pytest.raises(TypeError):
        list(provider.stream(MESSAGES, "gemini", 100))


@pytest.mark.parametrize(
    ("finish_reason", "expected"),
    [("STOP", "end"), ("MAX_TOKENS", "max_tokens"), ("SAFETY", "filtered")],
)
def test_records_why_the_stream_stopped(provider, client, finish_reason, expected):
    from google.genai import types

    last = SimpleNamespace(
        text="", candidates=[SimpleNamespace(finish_reason=types.FinishReason(finish_reason))]
    )
    client.models.generate_content_stream.return_value = iter(
        [SimpleNamespace(text="Hi", candidates=None), last]
    )
    list(provider.stream(MESSAGES, "gemini", 100))
    assert provider.last_stop_reason == expected
