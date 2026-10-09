"""Tests for the typed exception hierarchy."""

from ask_cli.exceptions import AskCLIError, HistoryError, ProviderError


def test_errors_carry_optional_hint():
    assert HistoryError("broken", hint="Run `ask --clear`.").hint == "Run `ask --clear`."
    assert AskCLIError("plain").hint is None


def test_provider_error_keeps_provider_and_status_and_hint():
    error = ProviderError("nope", provider="openai", status_code=429, hint="Wait.")
    assert (error.provider, error.status_code, error.hint, str(error)) == (
        "openai",
        429,
        "Wait.",
        "nope",
    )
