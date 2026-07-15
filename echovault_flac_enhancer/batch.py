"""Single-file and batch enhancement: spawns inference.py, parses its stdout/stderr
contract, and drives sequential batch processing over a folder of tracks."""

from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, NamedTuple

LOSSY_EXTENSIONS = {
    ".mp3",
    ".aac",
    ".ogg",
    ".wma",
}  # .m4a excluded: ambiguous AAC-vs-ALAC codec-in-container

PROGRESS_RE = re.compile(r"^PROGRESS\s+(\d+)$")
DONE_RE = re.compile(r"^DONE\s+(.+)$")
ERROR_RE = re.compile(r"ERROR\s+(\w+)\s*(.*)")

EXIT_CODE_FALLBACK = {
    1: "GENERIC",
    2: "INPUT_READ_FAILED",
    3: "MODEL_NOT_FOUND",
    4: "ORT_INIT_FAILED",
}

ERROR_EXIT_CODES = {code: rc for rc, code in EXIT_CODE_FALLBACK.items()}


class InferenceResult(NamedTuple):
    success: bool
    output_path: Path | None
    error_code: str | None
    error_message: str | None
    elapsed_seconds: float | None = None
    input_bytes: int | None = None
    output_bytes: int | None = None


def run_single_file(
    inference_script: Path,
    model_path: Path,
    config_path: Path,
    input_path: Path,
    output_path: Path,
    on_progress: Callable[[int], None] = lambda pct: None,
) -> InferenceResult:
    start = time.perf_counter()
    proc = subprocess.Popen(
        [
            sys.executable,
            str(inference_script),
            "--model",
            str(model_path),
            "--config",
            str(config_path),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--provider",
            "auto",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stderr_lines: list[str] = []

    def drain_stderr() -> None:
        for line in proc.stderr:
            stderr_lines.append(line.rstrip("\n"))

    stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
    stderr_thread.start()

    done_path: Path | None = None
    for line in proc.stdout:
        line = line.strip()
        if m := PROGRESS_RE.match(line):
            on_progress(int(m.group(1)))
        elif m := DONE_RE.match(line):
            done_path = Path(m.group(1))

    returncode = proc.wait()
    stderr_thread.join()
    elapsed = time.perf_counter() - start

    if returncode == 0:
        if done_path is not None and done_path != output_path:
            print(
                f"WARN inference reported DONE {done_path}, expected {output_path}",
                file=sys.stderr,
            )
        return InferenceResult(
            success=True,
            output_path=output_path,
            error_code=None,
            error_message=None,
            elapsed_seconds=elapsed,
            input_bytes=input_path.stat().st_size,
            output_bytes=output_path.stat().st_size,
        )

    error_code = None
    error_message = None
    for line in stderr_lines:
        if m := ERROR_RE.search(line):
            error_code = m.group(1)
            error_message = m.group(2).strip() or None
            break
    if error_code is None:
        error_code = EXIT_CODE_FALLBACK.get(returncode, "GENERIC")

    return InferenceResult(
        success=False,
        output_path=None,
        error_code=error_code,
        error_message=error_message,
        elapsed_seconds=elapsed,
    )


def resolve_files(folder: Path, recursive: bool) -> list[Path]:
    candidates = folder.rglob("*") if recursive else folder.glob("*")
    return sorted(
        p for p in candidates if p.is_file() and p.suffix.lower() in LOSSY_EXTENSIONS
    )


def output_path_for(
    input_path: Path, source_root: Path, output_dir: Path | None
) -> Path:
    stem_name = f"{input_path.stem}.enhanced.flac"
    if output_dir is None:
        return input_path.with_name(stem_name)
    rel_parent = input_path.parent.relative_to(source_root)
    dest_dir = output_dir / rel_parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir / stem_name


def should_skip(output_path: Path) -> bool:
    return output_path.exists()


class BatchSummary(NamedTuple):
    succeeded: list[Path]
    skipped: list[Path]
    failed: list[tuple[Path, str, str]]  # (input_path, error_code, message)
    results: list[InferenceResult]


def run_batch(
    files: list[Path],
    source_root: Path,
    model_path: Path,
    config_path: Path,
    inference_script: Path,
    output_dir: Path | None,
    skip_existing: bool,
    on_file_progress: Callable[[Path, int, int, int], None] = lambda *a: None,
) -> BatchSummary:
    succeeded: list[Path] = []
    skipped: list[Path] = []
    failed: list[tuple[Path, str, str]] = []
    results: list[InferenceResult] = []

    for i, input_path in enumerate(files, start=1):
        out_path = output_path_for(input_path, source_root, output_dir)
        if skip_existing and should_skip(out_path):
            skipped.append(input_path)
            continue

        result = run_single_file(
            inference_script,
            model_path,
            config_path,
            input_path,
            out_path,
            on_progress=lambda pct, idx=i, total=len(
                files
            ), p=input_path: on_file_progress(p, idx, total, pct),
        )
        results.append(result)
        if result.success:
            succeeded.append(input_path)
        else:
            failed.append(
                (input_path, result.error_code or "GENERIC", result.error_message or "")
            )

    return BatchSummary(
        succeeded=succeeded, skipped=skipped, failed=failed, results=results
    )
