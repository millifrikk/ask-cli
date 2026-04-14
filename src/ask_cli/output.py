"""Single rich.Console instance and all rendering helpers for ask-cli."""

from rich.console import Console
from rich.markdown import CodeBlock, Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

console = Console(highlight=False)


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
    """Replace the module-level console with a no-markup, no-color instance."""
    global console
    console = Console(highlight=False, markup=False, no_color=True)


def render_markdown(text: str) -> None:
    """Render text as markdown."""
    console.print(AskMarkdown(text))


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
    lines = [f"[bold red]Error:[/bold red] {message}"]
    if hint:
        lines.append(f"[dim]{hint}[/dim]")
    console.print("\n".join(lines))


def render_warning(message: str) -> None:
    """Render a warning message."""
    console.print(f"[bold yellow]Warning:[/bold yellow] {message}")


def render_info(message: str) -> None:
    """Render an informational message."""
    console.print(f"[dim]{message}[/dim]")


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


def render_model_list(provider: str, models: dict[str, str], default: str) -> None:
    """Render a provider's available models (default, fast, smart)."""
    table = Table(title=f"Models for {provider}", show_header=True, header_style="bold")
    table.add_column("Tier", style="cyan")
    table.add_column("Model")
    for tier, model in models.items():
        marker = " [bold green]*[/bold green]" if model == default else ""
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
