"""Main query orchestrator — run_query()."""

from collections.abc import Callable

from ask_cli.core.history import ConversationHistory
from ask_cli.exceptions import AskCLIError
from ask_cli.providers.base import BaseProvider


def run_query(
    *,
    query: str,
    provider: BaseProvider,
    model: str,
    max_tokens: int,
    system_prompt: str | None,
    history: ConversationHistory,
    use_history: bool,
    on_chunk: Callable[[str], None],
    think: bool | None = None,
) -> str:
    """Stream a query through the provider, passing each chunk to on_chunk, and return
    the full response text. On Ctrl+C the partial response is saved to history and the
    KeyboardInterrupt is re-raised so the CLI can exit with 130."""
    messages = (history.messages if use_history else []) + [{"role": "user", "content": query}]

    accumulated: list[str] = []
    interrupted = False
    try:
        for chunk in provider.stream(messages, model, max_tokens, system_prompt, think=think):
            accumulated.append(chunk)
            on_chunk(chunk)
    except KeyboardInterrupt:
        interrupted = True

    full_response = "".join(accumulated)

    if full_response:
        history.add_user_message(query)
        suffix = " [interrupted]" if interrupted else ""
        history.add_assistant_message(full_response + suffix)
        history.save()

    if interrupted:
        raise KeyboardInterrupt
    return full_response


def check_completeness(
    response: str, stop_reason: str | None, max_tokens: int, quick: bool
) -> str | None:
    """Raise AskCLIError for an empty response; return a warning if it was cut off."""
    longer = "drop --quick" if quick else "raise defaults.max_tokens in your config"
    if not response:
        if stop_reason == "filtered":
            raise AskCLIError(
                "The model returned an empty response: it was blocked by a content filter.",
                hint="Rephrase the question, or try another provider with -p.",
            )
        hint = (
            f"The {max_tokens}-token limit was used up before any text (reasoning models do "
            f"this); {longer}."
            if stop_reason == "max_tokens"
            else "Try again, or try another model with --smart or -p."
        )
        raise AskCLIError("The model returned an empty response.", hint=hint)
    if stop_reason == "max_tokens":
        return f"Response was cut off at the {max_tokens}-token limit; {longer}."
    return None
