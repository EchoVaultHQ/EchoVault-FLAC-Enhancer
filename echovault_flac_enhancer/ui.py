"""Rich-based presentation layer: colorized console output, progress bars, and
humanized error messages. Kept separate from cli.py so rendering logic can be
unit-tested without going through Typer's CliRunner."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from . import batch

console = Console()
error_console = Console(stderr=True)

ERROR_MESSAGES: dict[str, tuple[str, str]] = {
    "MODEL_NOT_FOUND": (
        "Enhancement model isn't installed yet.",
        "Run `echovault-flac-enhancer setup` to download it.",
    ),
    "ORT_INIT_FAILED": (
        "ONNX runtime failed to initialize on this machine.",
        "Run `echovault-flac-enhancer check` to see available execution providers, "
        "or reinstall onnxruntime.",
    ),
    "INPUT_READ_FAILED": (
        "Input file couldn't be read — it may be corrupt or an unsupported format.",
        "Confirm the file plays normally elsewhere, then retry.",
    ),
    "GENERIC": (
        "An unexpected error occurred during enhancement.",
        "Retry the file; if it keeps failing, please open an issue with the details.",
    ),
}


def _format_bytes(n: int | float | None) -> str:
    if n is None:
        return "—"
    value = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def render_error(code: str | None, message: str | None) -> None:
    title, hint = ERROR_MESSAGES.get(code or "GENERIC", ERROR_MESSAGES["GENERIC"])
    error_console.print(f"[bold red]:heavy_multiplication_x: {title}[/bold red]")
    error_console.print(f"  [dim]{hint}[/dim]")
    if message:
        error_console.print(f"  [dim]Details: {message}[/dim]")


def render_file_success(result: batch.InferenceResult) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_row("Output:", str(result.output_path))
    if result.input_bytes is not None and result.output_bytes is not None:
        delta_pct = (
            (result.output_bytes - result.input_bytes) / result.input_bytes * 100
            if result.input_bytes
            else 0.0
        )
        table.add_row("Input size:", _format_bytes(result.input_bytes))
        table.add_row("Output size:", _format_bytes(result.output_bytes))
        table.add_row("Size change:", f"{delta_pct:+.1f}%")
    if result.elapsed_seconds:
        table.add_row("Elapsed:", f"{result.elapsed_seconds:.1f}s")
        if result.output_bytes is not None:
            table.add_row(
                "Throughput:",
                f"{_format_bytes(result.output_bytes / result.elapsed_seconds)}/s",
            )
    console.print(
        Panel(table, title="[bold green]Done[/bold green]", border_style="green")
    )


def render_batch_summary(summary: batch.BatchSummary) -> None:
    table = Table(title="Batch summary")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("[green]Succeeded[/green]", str(len(summary.succeeded)))
    table.add_row("[yellow]Skipped[/yellow]", str(len(summary.skipped)))
    table.add_row("[red]Failed[/red]", str(len(summary.failed)))
    console.print(table)
    for path, code, message in summary.failed:
        title, _hint = ERROR_MESSAGES.get(code, ERROR_MESSAGES["GENERIC"])
        error_console.print(f"  [red]FAILED[/red] {path}: {title}")


def render_check_status(status: dict) -> None:
    table = Table(title="Environment check")
    table.add_column("Component")
    table.add_column("Status")
    table.add_column("Detail")
    for name, ver in status["deps"].items():
        ok = ver is not None
        table.add_row(
            name,
            "[green]OK[/green]" if ok else "[red]MISSING[/red]",
            ver or "not installed",
        )
    for label, entry in (("model", status["model"]), ("config", status["config"])):
        table.add_row(
            label,
            "[green]OK[/green]" if entry["ok"] else "[red]MISSING[/red]",
            f"{entry['reason']} ({entry['path']})",
        )
    console.print(table)


def _build_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )


def build_file_progress() -> Progress:
    return _build_progress()


def build_batch_progress() -> Progress:
    return _build_progress()
