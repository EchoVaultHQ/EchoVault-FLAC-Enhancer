# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
