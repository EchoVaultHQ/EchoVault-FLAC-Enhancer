from echovault_flac_enhancer import batch, ui


def test_every_error_exit_code_has_a_message():
    for code in list(batch.ERROR_EXIT_CODES) + ["GENERIC"]:
        assert code in ui.ERROR_MESSAGES


def test_render_error_does_not_raise():
    ui.render_error("MODEL_NOT_FOUND", "details here")
    ui.render_error(None, None)
    ui.render_error("UNKNOWN_CODE", None)


def test_render_file_success_does_not_raise(tmp_path):
    result = batch.InferenceResult(
        success=True,
        output_path=tmp_path / "out.flac",
        error_code=None,
        error_message=None,
        elapsed_seconds=1.5,
        input_bytes=1000,
        output_bytes=2000,
    )
    ui.render_file_success(result)


def test_render_batch_summary_does_not_raise(tmp_path):
    summary = batch.BatchSummary(
        succeeded=[tmp_path / "a.mp3"],
        skipped=[],
        failed=[(tmp_path / "b.mp3", "MODEL_NOT_FOUND", "not found")],
        results=[],
    )
    ui.render_batch_summary(summary)


def test_render_check_status_does_not_raise():
    ui.render_check_status(
        {
            "deps": {"numpy": "1.26.0", "onnxruntime": None},
            "model": {"path": "/tmp/model.onnx", "ok": True, "reason": "ok"},
            "config": {"path": "/tmp/config.json", "ok": False, "reason": "missing"},
        }
    )
