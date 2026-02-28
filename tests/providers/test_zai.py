"""Tests for ZaiProvider streaming and error handling."""

from unittest.mock import MagicMock, patch

import anthropic
import pytest

from ask_cli.config import ProviderConfig
from ask_cli.exceptions import ProviderError
from ask_cli.providers.zai import ZaiProvider


@pytest.fixture
def zai_config():
    return ProviderConfig(
        api_key="test-key",
        base_url="https://api.z.ai/v1",
        default_model="claude-sonnet-4-5-20251001",
    )


@pytest.fixture
def provider(zai_config):
    return ZaiProvider(zai_config)


def _make_mock_stream(chunks: list[str]):
    """Build a mock context manager that yields text chunks."""
    mock_stream = MagicMock()
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)
    mock_stream.text_stream = iter(chunks)
    return mock_stream


def test_stream_yields_chunks(provider):
    mock_stream = _make_mock_stream(["Hello", ", ", "world!"])

    with patch("anthropic.Anthropic") as mock_anthropic_class:
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.stream.return_value = mock_stream
        # Force client creation
        provider._client = None
        provider._client = mock_client

        chunks = list(provider.stream([{"role": "user", "content": "hi"}], "model", 100))

    assert chunks == ["Hello", ", ", "world!"]


def test_stream_passes_system_prompt(provider):
    mock_stream = _make_mock_stream(["ok"])

    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.stream.return_value = mock_stream

        list(
            provider.stream(
                [{"role": "user", "content": "hi"}],
                "model",
                100,
                system_prompt="Be terse.",
            )
        )

        call_kwargs = mock_client.messages.stream.call_args[1]
        assert call_kwargs["system"] == "Be terse."


def test_no_system_prompt_omitted(provider):
    mock_stream = _make_mock_stream(["ok"])

    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.stream.return_value = mock_stream

        list(provider.stream([{"role": "user", "content": "hi"}], "model", 100))

        call_kwargs = mock_client.messages.stream.call_args[1]
        assert "system" not in call_kwargs


def test_authentication_error_raises_provider_error(provider):
    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.stream.side_effect = anthropic.AuthenticationError(
            message="bad key", response=MagicMock(), body={}
        )

        with pytest.raises(ProviderError) as exc_info:
            list(provider.stream([{"role": "user", "content": "hi"}], "model", 100))

    assert exc_info.value.status_code == 401
    assert exc_info.value.provider == "zai"


def test_rate_limit_error_raises_provider_error(provider):
    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.stream.side_effect = anthropic.RateLimitError(
            message="rate limited", response=MagicMock(), body={}
        )

        with pytest.raises(ProviderError) as exc_info:
            list(provider.stream([{"role": "user", "content": "hi"}], "model", 100))

    assert exc_info.value.status_code == 429


def test_missing_api_key_raises_provider_error():
    provider = ZaiProvider(ProviderConfig(api_key=""))
    with pytest.raises(ProviderError, match="not configured"):
        list(provider.stream([{"role": "user", "content": "hi"}], "model", 100))


def test_is_configured_true_with_key(zai_config):
    assert ZaiProvider(zai_config).is_configured() is True


def test_is_configured_false_without_key():
    assert ZaiProvider(ProviderConfig()).is_configured() is False
