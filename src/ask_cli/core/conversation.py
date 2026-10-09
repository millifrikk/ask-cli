"""Main query orchestrator — run_query()."""

from collections.abc import Callable

from ask_cli.core.history import ConversationHistory
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
    the full response text. Ctrl+C stops the stream and keeps the partial response."""
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

    return full_response
