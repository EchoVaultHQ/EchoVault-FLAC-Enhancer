"""Download/verify the ONNX model + config, and run the self-test.

Ports the exact logic of EchoVault's own src/backend/main/downloader.js
(byte-size + sha256 verification, redirect-following streamed download,
retry-with-backoff) to a standalone, GitHub-Release-asset-based fetch —
no git/git-lfs dependency needed since Release assets are served as plain
binaries, not git-LFS-pointer-fronted blobs.
"""

from __future__ import annotations

import hashlib
import importlib.resources
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, NamedTuple

import platformdirs

MAX_REDIRECTS = 5
CHUNK_SIZE = 1024 * 1024


class ManifestEntry(NamedTuple):
    file: str
    sha256: str
    bytes: int


class Manifest(NamedTuple):
    version: str
    base_url: str
    model: ManifestEntry
    config: ManifestEntry


class ModelPaths(NamedTuple):
    model_path: Path
    config_path: Path


def load_manifest() -> Manifest:
    raw = json.loads(
        importlib.resources.files("echovault_flac_enhancer.data")
        .joinpath("manifest.json")
        .read_text()
    )
    return Manifest(
        version=raw["version"],
        base_url=raw["baseUrl"],
        model=ManifestEntry(**raw["model"]),
        config=ManifestEntry(**raw["config"]),
    )


def cache_dir() -> Path:
    d = Path(platformdirs.user_cache_dir("echovault-flac-enhancer")) / "model"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_asset(path: Path, entry: ManifestEntry) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    actual_bytes = path.stat().st_size
    if entry.bytes and actual_bytes != entry.bytes:
        return False, f"size mismatch (expected {entry.bytes}, got {actual_bytes})"
    if not entry.sha256:
        return True, "unpinned, trusted"
    actual_sha = sha256_file(path)
    if actual_sha.lower() != entry.sha256.lower():
        return False, f"checksum mismatch (expected {entry.sha256}, got {actual_sha})"
    return True, "ok"


def download_to(
    url: str,
    dest: Path,
    on_bytes: Callable[[int], None],
    redirects_left: int = MAX_REDIRECTS,
) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "echovault-flac-enhancer"})
    with urllib.request.urlopen(req) as resp:
        if 300 <= resp.status < 400 and resp.headers.get("Location"):
            if redirects_left <= 0:
                raise urllib.error.URLError("too many redirects")
            download_to(resp.headers["Location"], dest, on_bytes, redirects_left - 1)
            return
        if resp.status != 200:
            raise urllib.error.URLError(
                f"download failed: HTTP {resp.status} for {url}"
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as out:
            while chunk := resp.read(CHUNK_SIZE):
                out.write(chunk)
                on_bytes(len(chunk))
        tmp.replace(dest)


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (404, 408, 429) or exc.code >= 500
    return True


def _with_retry(
    fn: Callable[[], None], attempts: int = 3, base_seconds: float = 1.0
) -> None:
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            fn()
            return
        except (
            Exception
        ) as exc:  # noqa: BLE001 - broad on purpose, mirrors withRetry in downloader.js
            last_exc = exc
            if i == attempts - 1 or not _is_transient(exc):
                raise
            time.sleep(base_seconds * (2**i))
    if last_exc:
        raise last_exc


def _fetch_asset(
    base_url: str,
    entry: ManifestEntry,
    dest: Path,
    on_progress: Callable[[str, int, int], None],
) -> None:
    url = f"{base_url}/{entry.file}"

    def attempt() -> None:
        downloaded = 0

        def on_chunk(n: int) -> None:
            nonlocal downloaded
            downloaded += n
            on_progress(entry.file, downloaded, entry.bytes)

        download_to(url, dest, on_chunk)

    _with_retry(attempt)

    ok, reason = verify_asset(dest, entry)
    if not ok:
        dest.unlink(missing_ok=True)
        # one retry after a checksum/size mismatch, per the plan's contract
        _with_retry(attempt)
        ok, reason = verify_asset(dest, entry)
        if not ok:
            dest.unlink(missing_ok=True)
            raise ValueError(f"{entry.file}: {reason}")


def ensure_model_assets(
    on_progress: Callable[[str, int, int], None] = lambda *a: None,
) -> ModelPaths:
    manifest = load_manifest()
    d = cache_dir()
    model_path = d / manifest.model.file
    config_path = d / manifest.config.file

    for entry, dest in ((manifest.model, model_path), (manifest.config, config_path)):
        ok, _ = verify_asset(dest, entry)
        if not ok:
            _fetch_asset(manifest.base_url, entry, dest, on_progress)

    return ModelPaths(model_path=model_path, config_path=config_path)


def inference_script_path() -> Path:
    return Path(__file__).resolve().parent / "inference.py"


def run_self_test(inference_script: Path, model_path: Path, config_path: Path) -> bool:
    result = subprocess.run(
        [
            sys.executable,
            str(inference_script),
            "--model",
            str(model_path),
            "--config",
            str(config_path),
            "--self-test",
            "--provider",
            "auto",
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and "SELF-TEST PASS" in result.stdout


def check_status() -> dict:
    deps: dict[str, str | None] = {}
    for mod_name in ("onnxruntime", "soundfile", "scipy", "mutagen", "numpy"):
        try:
            mod = __import__(mod_name)
            deps[mod_name] = getattr(mod, "__version__", "unknown")
        except ImportError:
            deps[mod_name] = None

    manifest = load_manifest()
    d = cache_dir()
    model_path = d / manifest.model.file
    config_path = d / manifest.config.file
    model_ok, model_reason = verify_asset(model_path, manifest.model)
    config_ok, config_reason = verify_asset(config_path, manifest.config)

    return {
        "deps": deps,
        "model": {"path": str(model_path), "ok": model_ok, "reason": model_reason},
        "config": {"path": str(config_path), "ok": config_ok, "reason": config_reason},
    }
