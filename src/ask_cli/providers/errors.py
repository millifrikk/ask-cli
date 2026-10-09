"""Translate SDK and transport exceptions into ProviderError, shared by SDK family."""

from collections.abc import Iterator
from contextlib import contextmanager

import anthropic
import httpx
import openai

from ask_cli.exceptions import ModelNotFoundError, ProviderError

NETWORK_HINT = "Check your network connection and try again."


def connection_lost(provider_id: str, display_name: str, error: httpx.HTTPError) -> ProviderError:
    # SDKs only wrap transport errors raised while sending the request; a connection
    # dropped while reading the stream surfaces as a bare httpx error.
    return ProviderError(
        f"Connection to {display_name} was lost mid-response: {error}",
        provider=provider_id,
        hint=NETWORK_HINT,
    )


@contextmanager
def anthropic_errors(provider_id: str, display_name: str, model: str) -> Iterator[None]:
    try:
        yield
    except anthropic.AuthenticationError as e:
        raise ProviderError(
            f"Authentication failed — {display_name} rejected the API key.",
            provider=provider_id,
            status_code=401,
        ) from e
    except anthropic.RateLimitError as e:
        raise ProviderError(
            f"Rate limit exceeded on {display_name}.", provider=provider_id, status_code=429
        ) from e
    except anthropic.NotFoundError as e:
        raise ModelNotFoundError(
            f"Model '{model}' not found on {display_name}.", provider=provider_id, status_code=404
        ) from e
    except anthropic.APITimeoutError as e:
        raise ProviderError(
            f"Request to {display_name} timed out.", provider=provider_id, hint=NETWORK_HINT
        ) from e
    except anthropic.APIConnectionError as e:
        raise ProviderError(
            f"Cannot reach {display_name}: {e}",
            provider=provider_id,
            hint=f"{NETWORK_HINT} If you set a custom base_url, check it.",
        ) from e
    except anthropic.APIError as e:
        raise ProviderError(
            f"{display_name} API error: {e}",
            provider=provider_id,
            status_code=getattr(e, "status_code", None),
        ) from e
    except httpx.HTTPError as e:
        raise connection_lost(provider_id, display_name, e) from e


@contextmanager
def openai_errors(
    provider_id: str,
    display_name: str,
    model: str,
    *,
    unreachable_hint: str | None = None,
    not_found_hint: str | None = None,
) -> Iterator[None]:
    try:
        yield
    except openai.AuthenticationError as e:
        raise ProviderError(
            f"Authentication failed — {display_name} rejected the API key.",
            provider=provider_id,
            status_code=401,
        ) from e
    except openai.RateLimitError as e:
        raise ProviderError(
            f"Rate limit exceeded on {display_name}.", provider=provider_id, status_code=429
        ) from e
    except openai.NotFoundError as e:
        raise ModelNotFoundError(
            f"Model '{model}' not found on {display_name}.",
            provider=provider_id,
            status_code=404,
            hint=not_found_hint,
        ) from e
    # APITimeoutError subclasses APIConnectionError, so it must be caught first
    except openai.APITimeoutError as e:
        raise ProviderError(
            f"Request to {display_name} timed out.", provider=provider_id, hint=NETWORK_HINT
        ) from e
    except openai.APIConnectionError as e:
        raise ProviderError(
            f"Cannot reach {display_name}: {e}",
            provider=provider_id,
            hint=unreachable_hint or NETWORK_HINT,
        ) from e
    except openai.APIError as e:
        raise ProviderError(
            f"{display_name} API error: {e}",
            provider=provider_id,
            status_code=getattr(e, "status_code", None),
        ) from e
    except httpx.HTTPError as e:
        raise connection_lost(provider_id, display_name, e) from e
