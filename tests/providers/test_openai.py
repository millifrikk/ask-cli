"""Tests for OpenAIProvider streaming and error handling."""

from unittest.mock import MagicMock, patch

import httpx
import openai
import pytest

from ask_cli.config import ProviderConfig
from ask_cli.exceptions import ModelNotFoundError, ProviderError
from ask_cli.providers.openai import OpenAIProvider
from tests.providers.conftest import (
    broken_sse_response,
    error_response,
    openai_sse,
    raising,
    sse_response,
)

MESSAGES = [{"role": "user", "content": "hi"}]


def _make_chunk(content: str | None):
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta = MagicMock()
    chunk.choices[0].delta.content = content
    return chunk


@pytest.fixture
def openai_config():
    return ProviderConfig(api_key="sk-test", default_model="gpt-4o")


@pytest.fixture
def openai_provider(openai_config):
    return OpenAIProvider(openai_config)


class TestOpenAIProvider:
    def test_stream_yields_chunks(self, openai_provider):
        chunks = [_make_chunk("Hello"), _make_chunk(", "), _make_chunk("world!")]

        with patch.object(openai_provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.chat.completions.create.return_value = iter(chunks)

            result = list(
                openai_provider.stream([{"role": "user", "content": "hi"}], "gpt-4o", 100)
            )

        assert result == ["Hello", ", ", "world!"]

    def test_none_delta_content_is_skipped(self, openai_provider):
        """Chunks with None content (e.g. finish_reason chunks) must be skipped."""
        chunks = [_make_chunk("Hello"), _make_chunk(None), _make_chunk("!")]

        with patch.object(openai_provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.chat.completions.create.return_value = iter(chunks)

            result = list(
                openai_provider.stream([{"role": "user", "content": "hi"}], "gpt-4o", 100)
            )

        assert result == ["Hello", "!"]

    def test_system_prompt_injected_at_index_zero(self, openai_provider):
        with patch.object(openai_provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.chat.completions.create.return_value = iter([])

            list(
                openai_provider.stream(
                    [{"role": "user", "content": "hi"}],
                    "gpt-4o",
                    100,
                    system_prompt="Be terse.",
                )
            )

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            messages = call_kwargs["messages"]
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "Be terse."
            assert messages[1]["role"] == "user"

    def test_legacy_model_uses_max_tokens(self, openai_provider):
        with patch.object(openai_provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.chat.completions.create.return_value = iter([])

            list(openai_provider.stream([{"role": "user", "content": "hi"}], "gpt-4o", 123))

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["max_tokens"] == 123
            assert "max_completion_tokens" not in call_kwargs

    def test_gpt5_model_uses_max_completion_tokens(self, openai_provider):
        with patch.object(openai_provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.chat.completions.create.return_value = iter([])

            list(openai_provider.stream([{"role": "user", "content": "hi"}], "gpt-5.4-mini", 123))

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["max_completion_tokens"] == 123
            assert "max_tokens" not in call_kwargs

    def test_o1_model_uses_max_completion_tokens(self, openai_provider):
        with patch.object(openai_provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.chat.completions.create.return_value = iter([])

            list(openai_provider.stream([{"role": "user", "content": "hi"}], "o1-mini", 123))

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["max_completion_tokens"] == 123

    def test_missing_api_key_raises_provider_error(self):
        provider = OpenAIProvider(ProviderConfig(api_key=""))
        with pytest.raises(ProviderError, match="not configured"):
            list(provider.stream([{"role": "user", "content": "hi"}], "model", 100))

    def test_auth_error_raises_provider_error(self, openai_provider):
        with patch.object(openai_provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.chat.completions.create.side_effect = openai.AuthenticationError(
                message="bad key",
                response=MagicMock(),
                body={},
            )

            with pytest.raises(ProviderError) as exc_info:
                list(openai_provider.stream([{"role": "user", "content": "hi"}], "model", 100))

        assert exc_info.value.status_code == 401


class TestOpenAIProviderTransport:
    @pytest.fixture
    def make_provider(self, http_client):
        def build(handler) -> OpenAIProvider:
            provider = OpenAIProvider(ProviderConfig(api_key="test-key"))
            provider._client = openai.OpenAI(
                api_key="test-key", http_client=http_client(handler), max_retries=0
            )
            return provider

        return build

    def test_streams_over_http(self, make_provider):
        provider = make_provider(lambda request: sse_response(openai_sse("a", "b")))
        assert list(provider.stream(MESSAGES, "gpt-4o", 100)) == ["a", "b"]

    @pytest.mark.parametrize(
        ("status", "error_type"),
        [(401, ProviderError), (429, ProviderError), (404, ModelNotFoundError)],
    )
    def test_http_errors_map_to_typed_errors(self, make_provider, status, error_type):
        provider = make_provider(lambda request: error_response(status))
        with pytest.raises(error_type) as exc_info:
            list(provider.stream(MESSAGES, "gpt-4o", 100))
        assert exc_info.value.status_code == status

    def test_unreachable_host(self, make_provider):
        provider = make_provider(raising(httpx.ConnectError("refused")))
        with pytest.raises(ProviderError, match="Cannot reach OpenAI"):
            list(provider.stream(MESSAGES, "gpt-4o", 100))

    def test_connection_drop_mid_stream(self, make_provider):
        provider = make_provider(lambda request: broken_sse_response(openai_sse("Hello")[:200]))
        with pytest.raises(ProviderError, match="lost"):
            list(provider.stream(MESSAGES, "gpt-4o", 100))

    @pytest.mark.parametrize(
        ("finish_reason", "expected"),
        [("stop", "end"), ("length", "max_tokens"), ("content_filter", "filtered")],
    )
    def test_records_why_the_stream_stopped(self, make_provider, finish_reason, expected):
        body = openai_sse("partial", finish_reason=finish_reason)
        provider = make_provider(lambda request: sse_response(body))
        list(provider.stream(MESSAGES, "gpt-4o", 100))
        assert provider.last_stop_reason == expected
