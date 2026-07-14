import hashlib

import pytest

from echovault_flac_enhancer import model_manager


def test_sha256_file(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello world")
    assert model_manager.sha256_file(f) == hashlib.sha256(b"hello world").hexdigest()


def test_verify_asset_missing(tmp_path, fake_manifest):
    ok, reason = model_manager.verify_asset(
        tmp_path / "missing.bin", fake_manifest.model
    )
    assert not ok
    assert reason == "missing"


def test_verify_asset_size_mismatch(tmp_path, fake_manifest):
    f = tmp_path / "model.onnx"
    f.write_bytes(b"x" * 4)  # fake_manifest.model.bytes == 16
    ok, reason = model_manager.verify_asset(f, fake_manifest.model)
    assert not ok
    assert "size mismatch" in reason


def test_verify_asset_hash_mismatch(tmp_path, fake_manifest):
    f = tmp_path / "model.onnx"
    f.write_bytes(b"x" * 16)  # right size, wrong hash
    ok, reason = model_manager.verify_asset(f, fake_manifest.model)
    assert not ok
    assert "checksum mismatch" in reason


def test_verify_asset_ok(tmp_path):
    f = tmp_path / "asset.bin"
    f.write_bytes(b"hello world")
    entry = model_manager.ManifestEntry(
        file="asset.bin", sha256=hashlib.sha256(b"hello world").hexdigest(), bytes=11
    )
    ok, reason = model_manager.verify_asset(f, entry)
    assert ok
    assert reason == "ok"


def test_verify_asset_unpinned_trusts_presence(tmp_path):
    f = tmp_path / "asset.bin"
    f.write_bytes(b"anything")
    entry = model_manager.ManifestEntry(file="asset.bin", sha256="", bytes=0)
    ok, reason = model_manager.verify_asset(f, entry)
    assert ok
    assert "unpinned" in reason


def test_download_to_follows_redirect_then_downloads(tmp_path, monkeypatch):
    calls = []

    class FakeResp:
        def __init__(self, status, headers, body=b""):
            self.status = status
            self.headers = headers
            self._body = body

        def read(self, n):
            chunk, self._body = self._body[:n], self._body[n:]
            return chunk

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    responses = [
        FakeResp(302, {"Location": "https://cdn.example.invalid/real"}),
        FakeResp(200, {}, b"real-bytes"),
    ]

    def fake_urlopen(req, *a, **k):
        calls.append(req.full_url)
        return responses.pop(0)

    monkeypatch.setattr(model_manager.urllib.request, "urlopen", fake_urlopen)

    dest = tmp_path / "out.bin"
    received = []
    model_manager.download_to(
        "https://example.invalid/model.onnx", dest, received.append
    )

    assert dest.read_bytes() == b"real-bytes"
    assert calls == [
        "https://example.invalid/model.onnx",
        "https://cdn.example.invalid/real",
    ]
    assert sum(received) == len(b"real-bytes")


def test_ensure_model_assets_retries_once_then_raises(
    tmp_path, fake_cache_dir, fake_manifest, monkeypatch
):
    monkeypatch.setattr(model_manager, "load_manifest", lambda: fake_manifest)

    def bad_download(url, dest, on_bytes, redirects_left=5):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(
            b"wrong-bytes-entirely"
        )  # wrong size vs fake_manifest.model.bytes == 16

    monkeypatch.setattr(model_manager, "download_to", bad_download)

    with pytest.raises(ValueError, match="size mismatch"):
        model_manager.ensure_model_assets()
