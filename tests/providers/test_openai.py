"""Tests for OpenAIProvider and OllamaProvider streaming."""

from unittest.mock import MagicMock, patch

import openai
import pytest

from ask_cli.config import ProviderConfig
from ask_cli.exceptions import ProviderError
from ask_cli.providers.ollama import OllamaProvider
from ask_cli.providers.openai import OpenAIProvider


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
