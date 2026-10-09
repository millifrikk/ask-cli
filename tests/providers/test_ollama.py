"""Tests for OllamaProvider streaming and error handling."""

from unittest.mock import MagicMock, patch

import httpx
import openai
import pytest

from ask_cli.config import ProviderConfig
from ask_cli.exceptions import ModelNotFoundError, ProviderError
from ask_cli.providers.ollama import OllamaProvider
from tests.providers.conftest import (
    broken_sse_response,
    error_response,
    openai_sse,
    raising,
    sse_response,
)

MESSAGES = [{"role": "user", "content": "hi"}]


class TestOllamaProvider:
    def test_is_configured_always_true(self):
        provider = OllamaProvider(ProviderConfig())
        assert provider.is_configured() is True

    def test_default_base_url(self):
        provider = OllamaProvider(ProviderConfig())
        client = provider._get_client()
        assert "localhost:11434" in str(client.base_url)

    def test_connection_error_raises_provider_error(self):
        provider = OllamaProvider(ProviderConfig(base_url="http://localhost:11434"))

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.chat.completions.create.side_effect = openai.APIConnectionError(
                request=MagicMock()
            )

            with pytest.raises(ProviderError, match="Ollama"):
                list(provider.stream([{"role": "user", "content": "hi"}], "llama3", 100))

    def test_think_false_passed_as_extra_body(self):
        provider = OllamaProvider(ProviderConfig())
        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.chat.completions.create.return_value = iter([])

            list(provider.stream([{"role": "user", "content": "hi"}], "qwen3.5", 100, think=False))

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["extra_body"] == {"think": False}

    def test_think_none_omits_extra_body(self):
        provider = OllamaProvider(ProviderConfig())
        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.chat.completions.create.return_value = iter([])

            list(provider.stream([{"role": "user", "content": "hi"}], "llama3", 100))

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["extra_body"] is None

    @pytest.fixture
    def make_provider(self, http_client):
        def build(handler) -> OllamaProvider:
            provider = OllamaProvider(ProviderConfig(base_url="http://localhost:11434"))
            provider._client = openai.OpenAI(
                api_key="ollama",
                base_url="http://localhost:11434/v1",
                http_client=http_client(handler),
                max_retries=0,
            )
            return provider

        return build

    def test_streams_over_http(self, make_provider):
        provider = make_provider(lambda request: sse_response(openai_sse("a", "b")))
        assert list(provider.stream(MESSAGES, "llama", 100)) == ["a", "b"]

    def test_not_running_suggests_ollama_serve(self, make_provider):
        provider = make_provider(raising(httpx.ConnectError("refused")))
        with pytest.raises(ProviderError) as exc_info:
            list(provider.stream(MESSAGES, "llama", 100))
        assert "ollama serve" in exc_info.value.hint

    def test_timeout_is_not_reported_as_not_running(self, make_provider):
        provider = make_provider(raising(httpx.ReadTimeout("slow model")))
        with pytest.raises(ProviderError, match="timed out") as exc_info:
            list(provider.stream(MESSAGES, "llama", 100))
        assert "ollama serve" not in (exc_info.value.hint or "")

    def test_missing_model_suggests_pull(self, make_provider):
        provider = make_provider(lambda request: error_response(404))
        with pytest.raises(ModelNotFoundError) as exc_info:
            list(provider.stream(MESSAGES, "llama", 100))
        assert "ollama pull llama" in exc_info.value.hint

    def test_connection_drop_mid_stream(self, make_provider):
        provider = make_provider(lambda request: broken_sse_response(openai_sse("Hi")[:150]))
        with pytest.raises(ProviderError, match="lost"):
            list(provider.stream(MESSAGES, "llama", 100))

    def test_records_token_limit_stop(self, make_provider):
        body = openai_sse("partial", finish_reason="length")
        provider = make_provider(lambda request: sse_response(body))
        list(provider.stream(MESSAGES, "llama", 100))
        assert provider.last_stop_reason == "max_tokens"
