from echovault_flac_enhancer import batch


def _run(fake_inference_script, tmp_path, simulate="success"):
    model_path = tmp_path / "model.onnx"
    config_path = tmp_path / "config.json"
    input_path = tmp_path / "in.mp3"
    input_path.write_bytes(b"fake-mp3")
    output_path = tmp_path / "out.flac"

    progresses = []
    import subprocess

    orig_popen = subprocess.Popen

    def popen_with_simulate(args, **kwargs):
        args = list(args) + ["--simulate", simulate]
        return orig_popen(args, **kwargs)

    subprocess.Popen = popen_with_simulate
    try:
        result = batch.run_single_file(
            fake_inference_script,
            model_path,
            config_path,
            input_path,
            output_path,
            on_progress=progresses.append,
        )
    finally:
        subprocess.Popen = orig_popen
    return result, progresses


def test_success(fake_inference_script, tmp_path):
    result, progresses = _run(fake_inference_script, tmp_path, "success")
    assert result.success
    assert result.output_path == tmp_path / "out.flac"
    assert progresses == [50, 100]


def test_model_not_found(fake_inference_script, tmp_path):
    result, _ = _run(fake_inference_script, tmp_path, "MODEL_NOT_FOUND")
    assert not result.success
    assert result.error_code == "MODEL_NOT_FOUND"


def test_input_read_failed(fake_inference_script, tmp_path):
    result, _ = _run(fake_inference_script, tmp_path, "INPUT_READ_FAILED")
    assert not result.success
    assert result.error_code == "INPUT_READ_FAILED"


def test_ort_init_failed(fake_inference_script, tmp_path):
    result, _ = _run(fake_inference_script, tmp_path, "ORT_INIT_FAILED")
    assert not result.success
    assert result.error_code == "ORT_INIT_FAILED"


def test_generic_error(fake_inference_script, tmp_path):
    result, _ = _run(fake_inference_script, tmp_path, "GENERIC")
    assert not result.success
    assert result.error_code == "GENERIC"


def test_malformed_progress_line_ignored(tmp_path):
    assert batch.PROGRESS_RE.match("PROGRESS abc") is None
    assert batch.PROGRESS_RE.match("PROGRESS 42").group(1) == "42"
