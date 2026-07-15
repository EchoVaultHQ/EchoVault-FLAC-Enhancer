# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2026-07-15

### Changed

- Migrated the CLI from flat argparse flags to Typer subcommands: `enhance
  file`, `enhance folder`, `setup`, `check` replace `--file-name`,
  `--folder`, `--setup`, `--check`. **Breaking change** to the command-line
  surface.

### Added

- Colorized output and live progress bars via Rich (replacing `tqdm`).
- `--version` flag.
- Richer success output: input/output file size, size change %, elapsed
  time, and throughput after single-file and batch runs.
- Humanized error messages with remediation hints (e.g. pointing at `setup`
  or `check`) instead of raw internal error codes.

### Fixed

- Version now read from installed package metadata instead of a hardcoded
  constant that had drifted from `pyproject.toml`.
- Model-download progress now reports cumulative bytes downloaded instead
  of only the current chunk's size.
- Batch-mode progress now advances live as each file completes, instead of
  only jumping to 100% after the whole batch already finished.

## [0.1.1] - 2026-07-14

### Fixed

- Relax `onnxruntime` pin from `==1.20.1` to `>=1.20.1` — the exact pin had
  no wheel for Python 3.9 or 3.14+, and `inference.py` only uses the stable
  `InferenceSession` API so an exact pin wasn't needed.

## [0.1.0] - 2026-07-14

### Added

- Initial release: `--setup`, `--check`, `--file-name`, `--folder`
  (`--recursive`, `--skip-existing`, `--output-dir`) CLI commands.
- Model download/verification against a GitHub Release asset, ported from
  EchoVault's own `downloader.js`.
