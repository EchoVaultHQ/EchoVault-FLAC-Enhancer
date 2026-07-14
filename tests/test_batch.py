import subprocess

from echovault_flac_enhancer import batch


def test_resolve_files_filters_extensions_and_excludes_m4a(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"")
    (tmp_path / "b.flac").write_bytes(b"")
    (tmp_path / "c.m4a").write_bytes(b"")
    (tmp_path / "d.aac").write_bytes(b"")
    files = batch.resolve_files(tmp_path, recursive=False)
    assert [f.name for f in files] == ["a.mp3", "d.aac"]


def test_resolve_files_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "top.mp3").write_bytes(b"")
    (sub / "nested.mp3").write_bytes(b"")
    assert len(batch.resolve_files(tmp_path, recursive=False)) == 1
    assert len(batch.resolve_files(tmp_path, recursive=True)) == 2


def test_output_path_for_no_output_dir(tmp_path):
    input_path = tmp_path / "track.mp3"
    out = batch.output_path_for(input_path, tmp_path, None)
    assert out == tmp_path / "track.enhanced.flac"


def test_output_path_for_with_output_dir_nested(tmp_path):
    sub = tmp_path / "artist" / "album"
    sub.mkdir(parents=True)
    input_path = sub / "track.mp3"
    output_dir = tmp_path / "out"
    out = batch.output_path_for(input_path, tmp_path, output_dir)
    assert out == output_dir / "artist" / "album" / "track.enhanced.flac"
    assert out.parent.is_dir()


def test_should_skip(tmp_path):
    out = tmp_path / "x.enhanced.flac"
    assert not batch.should_skip(out)
    out.write_bytes(b"x")
    assert batch.should_skip(out)


def test_run_batch_continues_after_failure(
    fake_inference_script, tmp_path, monkeypatch
):
    good = tmp_path / "good.mp3"
    bad = tmp_path / "bad.mp3"
    good.write_bytes(b"x")
    bad.write_bytes(b"x")

    orig_popen = subprocess.Popen

    def popen_with_simulate(args, **kwargs):
        simulate = (
            "MODEL_NOT_FOUND" if any("bad.mp3" in str(a) for a in args) else "success"
        )
        return orig_popen(list(args) + ["--simulate", simulate], **kwargs)

    monkeypatch.setattr(subprocess, "Popen", popen_with_simulate)

    summary = batch.run_batch(
        [bad, good],
        tmp_path,
        tmp_path / "model.onnx",
        tmp_path / "config.json",
        fake_inference_script,
        output_dir=None,
        skip_existing=False,
    )

    assert summary.succeeded == [good]
    assert len(summary.failed) == 1
    assert summary.failed[0][0] == bad
    assert summary.failed[0][1] == "MODEL_NOT_FOUND"


def test_run_batch_skip_existing(fake_inference_script, tmp_path):
    track = tmp_path / "track.mp3"
    track.write_bytes(b"x")
    (tmp_path / "track.enhanced.flac").write_bytes(b"already there")

    summary = batch.run_batch(
        [track],
        tmp_path,
        tmp_path / "model.onnx",
        tmp_path / "config.json",
        fake_inference_script,
        output_dir=None,
        skip_existing=True,
    )
    assert summary.skipped == [track]
    assert summary.succeeded == []
