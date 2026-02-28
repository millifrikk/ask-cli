"""Main query orchestrator — run_query() and output rendering."""

import re

from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text

from ask_cli.core.history import ConversationHistory
from ask_cli.output import console, render_code, render_raw
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
    output_mode: str,
) -> str:
    """Stream a query through the provider and return the full response text."""
    messages = (history.messages if use_history else []) + [{"role": "user", "content": query}]

    accumulated: list[str] = []
    interrupted = False

    # --code-only needs the full text before it can extract blocks, so we stream
    # with transient=True and do a separate render pass after. Every other mode
    # renders inline during streaming (no double output regardless of length).
    code_only = output_mode == "code"

    try:
        with Live(
            console=console,
            refresh_per_second=15,
            transient=code_only,
        ) as live:
            for chunk in provider.stream(messages, model, max_tokens, system_prompt):
                accumulated.append(chunk)
                text = "".join(accumulated)
                live.update(_live_renderable(text, output_mode))
    except KeyboardInterrupt:
        interrupted = True

    full_response = "".join(accumulated)

    if code_only and full_response:
        _render_code_blocks(full_response)

    if full_response:
        history.add_user_message(query)
        suffix = " [interrupted]" if interrupted else ""
        history.add_assistant_message(full_response + suffix)
        history.save()

    return full_response


def _live_renderable(text: str, output_mode: str) -> Markdown | Text:
    """Return the right rich renderable for the streaming display."""
    if output_mode in ("markdown", ""):
        return Markdown(text)
    # raw / json / code — plain text during streaming
    return Text(text)


def _render_code_blocks(text: str) -> None:
    """Extract and render code blocks from a response. Falls back to raw if none found."""
    pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
    matches = pattern.findall(text)
    if not matches:
        render_raw(text)
        return
    for language, code in matches:
        render_code(code.rstrip("\n"), language=language)
