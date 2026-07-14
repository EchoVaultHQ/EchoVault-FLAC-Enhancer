from pathlib import Path

import pytest

from echovault_flac_enhancer import model_manager


@pytest.fixture
def fake_inference_script() -> Path:
    return Path(__file__).parent / "fixtures" / "fake_inference.py"


@pytest.fixture
def fake_cache_dir(tmp_path, monkeypatch):
    d = tmp_path / "cache"
    monkeypatch.setattr(
        model_manager.platformdirs, "user_cache_dir", lambda *a, **k: str(d)
    )
    return d


@pytest.fixture
def fake_manifest():
    return model_manager.Manifest(
        version="1.0.0",
        base_url="https://example.invalid/releases/download/v0.1.0",
        model=model_manager.ManifestEntry(file="model.onnx", sha256="a" * 64, bytes=16),
        config=model_manager.ManifestEntry(
            file="config.json", sha256="b" * 64, bytes=4
        ),
    )
