"""Typer CLI surface: `enhance file`, `enhance folder`, `setup`, `check`."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from . import __version__, batch, model_manager, ui

app = typer.Typer(no_args_is_help=True, add_completion=False)
enhance_app = typer.Typer(no_args_is_help=True)
app.add_typer(enhance_app, name="enhance", help="Enhance lossy audio to FLAC")


def _version_callback(value: bool) -> None:
    if value:
        ui.console.print(f"echovault-flac-enhancer {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    )
) -> None:
    """Enhance lossy audio (MP3/AAC/OGG/WMA) to FLAC via EchoVault's ONNX model."""


def _cmd_setup() -> int:
    with ui.build_file_progress() as progress:
        task = progress.add_task("Downloading model assets", total=100)

        def on_progress(name: str, done: int, total: int) -> None:
            progress.update(
                task,
                description=f"Downloading {name}",
                total=total or 100,
                completed=done,
            )

        paths = model_manager.ensure_model_assets(on_progress)

    ui.console.print("Running self-test...")
    inference_script = model_manager.inference_script_path()
    if model_manager.run_self_test(
        inference_script, paths.model_path, paths.config_path
    ):
        ui.console.print("[bold green]Self-test passed[/bold green]")
        return 0
    ui.error_console.print("[bold red]Self-test failed[/bold red]")
    return 1


def _cmd_check() -> int:
    status = model_manager.check_status()
    ui.render_check_status(status)
    return (
        0
        if status["model"]["ok"]
        and status["config"]["ok"]
        and all(status["deps"].values())
        else 1
    )


def _cmd_file(input_path: Path, output_dir: Optional[Path]) -> int:
    paths = model_manager.ensure_model_assets()
    inference_script = model_manager.inference_script_path()
    output_path = batch.output_path_for(input_path, input_path.parent, output_dir)

    with ui.build_file_progress() as progress:
        task = progress.add_task(input_path.name, total=100)
        result = batch.run_single_file(
            inference_script,
            paths.model_path,
            paths.config_path,
            input_path,
            output_path,
            on_progress=lambda pct: progress.update(task, completed=pct),
        )

    if result.success:
        ui.render_file_success(result)
        return 0
    ui.render_error(result.error_code, result.error_message)
    return batch.ERROR_EXIT_CODES.get(result.error_code or "GENERIC", 1)


def _cmd_folder(
    folder: Path,
    recursive: bool,
    workers: int,
    skip_existing: bool,
    output_dir: Optional[Path],
) -> int:
    if workers > 1:
        ui.error_console.print(
            "[bold red]Parallel workers aren't implemented yet (v2). Use --workers 1.[/bold red]"
        )
        return 1

    files = batch.resolve_files(folder, recursive)
    if not files:
        ui.console.print("No lossy tracks found.")
        return 0

    paths = model_manager.ensure_model_assets()
    inference_script = model_manager.inference_script_path()

    with ui.build_batch_progress() as progress:
        outer = progress.add_task("Batch", total=len(files))
        inner = progress.add_task("", total=100)
        seen_idx = 0

        def on_file_progress(path: Path, idx: int, total: int, pct: int) -> None:
            nonlocal seen_idx
            if idx != seen_idx:
                if seen_idx:
                    progress.update(outer, advance=1)
                progress.reset(inner, total=100)
                progress.update(inner, description=path.name)
                seen_idx = idx
            progress.update(inner, completed=pct)

        summary = batch.run_batch(
            files,
            folder,
            paths.model_path,
            paths.config_path,
            inference_script,
            output_dir,
            skip_existing,
            on_file_progress=on_file_progress,
        )
        progress.update(outer, completed=len(files))

    ui.render_batch_summary(summary)
    return 0 if not summary.failed else 1


@enhance_app.command("file")
def enhance_file(
    path: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", help="Write output here instead of alongside the source"
    ),
) -> None:
    """Enhance a single track."""
    raise typer.Exit(code=_cmd_file(path, output_dir))


@enhance_app.command("folder")
def enhance_folder(
    path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    recursive: bool = typer.Option(False, "--recursive", help="Walk subfolders"),
    workers: int = typer.Option(
        1, "--workers", help="Parallel workers (v1: must be 1)"
    ),
    skip_existing: bool = typer.Option(
        False, "--skip-existing", help="Skip files with an existing enhanced output"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", help="Write outputs here instead of alongside sources"
    ),
) -> None:
    """Enhance all lossy tracks in a folder."""
    raise typer.Exit(
        code=_cmd_folder(path, recursive, workers, skip_existing, output_dir)
    )


@app.command()
def setup() -> None:
    """Download/verify the model and run a self-test."""
    raise typer.Exit(code=_cmd_setup())


@app.command()
def check() -> None:
    """Report runtime/deps/model/self-test status."""
    raise typer.Exit(code=_cmd_check())


def main() -> None:
    app()
