"""Single rich.Console instance and all rendering helpers for ask-cli."""

from types import TracebackType

import pyperclip
from rich.console import Console
from rich.live import Live
from rich.markdown import CodeBlock, Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from ask_cli.core.fences import extract_code_blocks, strip_outer_fence

# Answers go to stdout; errors, warnings, notices and prompts go to stderr so that
# `ask ... | jq` and `ask ... > file` only ever receive the model's response.
console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)


class PlainCodeBlock(CodeBlock):
    """Code block renderer without padding or filled background.

    The default rich CodeBlock wraps fenced code in a padded panel that fills
    the terminal width — pretty, but makes terminal click-selection include
    leading spaces and trailing background padding. This subclass strips both
    so triple-click grabs exactly the code.
    """

    def __rich_console__(self, console, options):
        code = str(self.text).rstrip()
        yield Syntax(
            code,
            self.lexer_name,
            theme=self.theme,
            word_wrap=True,
            padding=0,
            background_color="default",
        )


class AskMarkdown(Markdown):
    """Markdown renderer that emits click-selectable code blocks."""

    elements = {
        **Markdown.elements,
        "fence": PlainCodeBlock,
        "code_block": PlainCodeBlock,
    }


def disable_color() -> None:
    """Swap both consoles for colourless ones that still interpret markup.

    Rich cannot change a console's colour system after construction, so the
    module-level instances are rebound. Callers must therefore reference
    `output.console` at call time, never `from ask_cli.output import console`.
    """
    global console, err_console
    console = Console(highlight=False, color_system=None)
    err_console = Console(stderr=True, highlight=False, color_system=None)


class ResponseDisplay:
    """Render a streaming response for the given output mode.

    On a terminal the response is drawn live (Markdown for markdown mode). When
    stdout is a pipe or file, the text is written verbatim — no wrapping, padding
    or Markdown rendering — so `| jq`, `> script.py` and `> notes.md` get exactly
    what the model produced. Modes that need the whole response (json, code) are
    written once the stream ends.
    """

    def __init__(self, output_mode: str) -> None:
        self._mode = output_mode
        self._chunks: list[str] = []
        self._live: Live | None = None

    def __enter__(self) -> "ResponseDisplay":
        if console.is_terminal:
            code_only = self._mode == "code"
            if not code_only:
                console.rule("ask", align="left", style="dim", characters="─")
            # --code-only streams transiently, then re-renders just the code blocks
            self._live = Live(console=console, refresh_per_second=15, transient=code_only)
            self._live.__enter__()
        return self

    def update(self, chunk: str) -> None:
        self._chunks.append(chunk)
        if self._live is not None:
            self._live.update(self._live_renderable("".join(self._chunks)))
        elif self._mode in ("markdown", "raw"):
            console.out(chunk, end="", highlight=False)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        text = "".join(self._chunks)
        if self._live is not None:
            self._live.__exit__(exc_type, exc, traceback)
            if self._mode == "code" and text:
                _render_code_blocks(text)
            return
        if not text:
            return
        if self._mode == "json":
            console.out(strip_outer_fence(text), highlight=False)
        elif self._mode == "code":
            blocks = extract_code_blocks(text)
            body = "\n\n".join(code for _, code in blocks) if blocks else text.rstrip("\n")
            console.out(body, highlight=False)
        elif not text.endswith("\n"):
            console.out("", highlight=False)

    def _live_renderable(self, text: str) -> AskMarkdown | Text:
        if self._mode == "markdown":
            return AskMarkdown(text)
        return Text(text)


def _render_code_blocks(text: str) -> None:
    blocks = extract_code_blocks(text)
    if not blocks:
        render_raw(text)
        return
    for language, code in blocks:
        render_code(code, language=language)


def render_markdown(text: str) -> None:
    """Render text as markdown on a terminal; write the source verbatim when piped."""
    if console.is_terminal:
        console.print(AskMarkdown(text))
    else:
        console.out(text.rstrip("\n"), highlight=False)


def render_raw(text: str) -> None:
    """Print text with no formatting."""
    console.print(text, markup=False, highlight=False)


def render_code(code: str, language: str = "", theme: str = "monokai") -> None:
    """Render a code block with syntax highlighting, click-selection friendly."""
    syntax = Syntax(
        code,
        language or "text",
        theme=theme,
        word_wrap=True,
        padding=0,
        background_color="default",
    )
    console.print(syntax)


def render_error(message: str, hint: str | None = None) -> None:
    """Render an error message with optional actionable hint."""
    # Messages carry file paths, provider error bodies and user input — escape them
    # so brackets render literally instead of being parsed as Rich markup.
    lines = [f"[bold red]Error:[/bold red] {escape(message)}"]
    if hint:
        lines.append(f"[dim]{escape(hint)}[/dim]")
    err_console.print("\n".join(lines))


def render_warning(message: str) -> None:
    """Render a warning message."""
    err_console.print(f"[bold yellow]Warning:[/bold yellow] {escape(message)}")


def render_info(message: str) -> None:
    """Render an informational message."""
    err_console.print(f"[dim]{escape(message)}[/dim]")


def _sanitize_for_clipboard(text: str) -> str:
    # Trailing \n auto-executes on paste into a shell prompt; \r can hide
    # content from the pre-paste preview on some terminals.
    return text.replace("\r", "").rstrip("\n")


def copy_to_clipboard(content: str, label: str) -> None:
    """Copy content to clipboard with pastejacking hygiene and unified error rendering."""
    safe = _sanitize_for_clipboard(content)
    try:
        pyperclip.copy(safe)
        render_info(f"{label} copied to clipboard.")
    except pyperclip.PyperclipException as e:
        render_warning(f"Clipboard unavailable: {e}. Install xclip or xsel.")


def render_provider_table(rows: list[tuple[str, str, str]]) -> None:
    """Render a table of providers with name, status, and default model columns."""
    table = Table(title="Available Providers", show_header=True, header_style="bold")
    table.add_column("Provider", style="cyan")
    table.add_column("Status")
    table.add_column("Default Model")
    for name, status, model in rows:
        status_text = (
            "[green]configured[/green]" if status == "configured" else "[dim]not configured[/dim]"
        )
        table.add_row(name, status_text, model)
    console.print(table)


def render_model_list(provider: str, models: dict[str, str]) -> None:
    """Render a provider's model tiers (default, fast, smart), starring the default tier."""
    table = Table(title=f"Models for {provider}", show_header=True, header_style="bold")
    table.add_column("Tier", style="cyan")
    table.add_column("Model")
    for tier, model in models.items():
        marker = " [bold green]*[/bold green]" if tier == "default" else ""
        table.add_row(tier, f"{model}{marker}")
    console.print(table)


def render_saved_list(entries: list[dict]) -> None:
    """Render a table of saved responses, or a dim message if none exist."""
    if not entries:
        console.print("[dim]No saved responses.[/dim]")
        return
    table = Table(title="Saved Responses", show_header=True, header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Saved")
    for entry in entries:
        table.add_row(entry.get("name", ""), entry.get("timestamp", ""))
    console.print(table)


def render_stats(stats: dict) -> None:
    """Render usage statistics as a rich Panel."""
    total = stats.get("total_queries", 0)
    if total == 0:
        console.print(Panel("[dim]No statistics recorded yet.[/dim]", title="Usage Statistics"))
        return

    input_chars = stats.get("input_chars", 0)
    output_chars = stats.get("output_chars", 0)
    by_mode = stats.get("queries_by_mode", {})
    first_use = stats.get("first_use") or "—"
    last_use = stats.get("last_use") or "—"

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    table.add_row("Total queries", str(total))
    table.add_row("Input tokens (approx)", str(input_chars // 4))
    table.add_row("Output tokens (approx)", str(output_chars // 4))
    table.add_row("First use", first_use)
    table.add_row("Last use", last_use)

    if by_mode:
        top_modes = sorted(by_mode.items(), key=lambda x: x[1], reverse=True)[:5]
        table.add_row("Top modes", ", ".join(f"{m}({c})" for m, c in top_modes))

    console.print(Panel(table, title="Usage Statistics"))
