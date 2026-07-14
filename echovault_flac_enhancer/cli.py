"""argparse CLI surface: --folder/--file-name/--setup/--check."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tqdm import tqdm

from . import batch, model_manager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="echovault-flac-enhancer")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--folder", type=Path, help="Enhance all lossy tracks in a folder"
    )
    mode.add_argument("--file-name", type=Path, help="Enhance a single track")
    mode.add_argument(
        "--setup",
        action="store_true",
        help="Download/verify the model and run a self-test",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Report runtime/deps/model/self-test status",
    )

    parser.add_argument(
        "--recursive", action="store_true", help="Walk subfolders (only with --folder)"
    )
    parser.add_argument(
        "--workers", type=int, default=1, help="Parallel workers (v1: must be 1)"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip files with an existing enhanced output",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Write outputs here instead of alongside sources",
    )
    return parser


def _cmd_setup() -> int:
    def on_progress(name: str, done: int, total: int) -> None:
        pct = round(done / total * 100) if total else 0
        print(f"Downloading {name}: {pct}%", end="\r")

    print("Downloading model assets...")
    paths = model_manager.ensure_model_assets(on_progress)
    print("\nRunning self-test...")
    inference_script = model_manager.inference_script_path()
    if model_manager.run_self_test(
        inference_script, paths.model_path, paths.config_path
    ):
        print("SELF-TEST PASS")
        return 0
    print("SELF-TEST FAILED", file=sys.stderr)
    return 1


def _cmd_check() -> int:
    status = model_manager.check_status()
    print("Dependencies:")
    for name, version in status["deps"].items():
        print(f"  {name}: {version if version else 'MISSING'}")
    print(
        f"Model:  ok={status['model']['ok']}  ({status['model']['reason']})  {status['model']['path']}"
    )
    print(
        f"Config: ok={status['config']['ok']}  ({status['config']['reason']})  {status['config']['path']}"
    )
    return (
        0
        if status["model"]["ok"]
        and status["config"]["ok"]
        and all(status["deps"].values())
        else 1
    )


def _print_summary(summary: batch.BatchSummary) -> None:
    print(
        f"\nSucceeded: {len(summary.succeeded)}  Skipped: {len(summary.skipped)}  Failed: {len(summary.failed)}"
    )
    for path, code, message in summary.failed:
        print(f"  FAILED {path}: {code} {message}")


def _cmd_file(args: argparse.Namespace) -> int:
    paths = model_manager.ensure_model_assets()
    inference_script = model_manager.inference_script_path()
    input_path: Path = args.file_name
    output_path = batch.output_path_for(input_path, input_path.parent, args.output_dir)

    with tqdm(total=100, desc=input_path.name) as bar:

        def on_progress(pct: int) -> None:
            bar.n = pct
            bar.refresh()

        result = batch.run_single_file(
            inference_script,
            paths.model_path,
            paths.config_path,
            input_path,
            output_path,
            on_progress,
        )

    if result.success:
        print(f"DONE {result.output_path}")
        return 0
    print(f"ERROR {result.error_code} {result.error_message}", file=sys.stderr)
    return {"MODEL_NOT_FOUND": 3, "INPUT_READ_FAILED": 2, "ORT_INIT_FAILED": 4}.get(
        result.error_code, 1
    )


def _cmd_folder(args: argparse.Namespace) -> int:
    if args.workers > 1:
        print(
            "ERROR: parallel workers not implemented yet — v2. Use --workers 1.",
            file=sys.stderr,
        )
        return 1

    folder: Path = args.folder
    files = batch.resolve_files(folder, args.recursive)
    if not files:
        print("No lossy tracks found.")
        return 0

    paths = model_manager.ensure_model_assets()
    inference_script = model_manager.inference_script_path()

    outer = tqdm(total=len(files), position=0, desc="Batch")
    inner = tqdm(total=100, position=1, leave=False)

    def on_file_progress(path: Path, idx: int, total: int, pct: int) -> None:
        outer.set_postfix_str(f"Track {idx}/{total}")
        inner.n = pct
        inner.refresh()

    summary = batch.run_batch(
        files,
        folder,
        paths.model_path,
        paths.config_path,
        inference_script,
        args.output_dir,
        args.skip_existing,
        on_file_progress=on_file_progress,
    )
    for _ in files:
        outer.update(1)
        inner.reset()
    outer.close()
    inner.close()

    _print_summary(summary)
    return 0 if not summary.failed else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.setup:
        return _cmd_setup()
    if args.check:
        return _cmd_check()
    if args.file_name:
        return _cmd_file(args)
    return _cmd_folder(args)
