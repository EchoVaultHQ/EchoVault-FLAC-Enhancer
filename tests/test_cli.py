from typer.testing import CliRunner

from echovault_flac_enhancer import __version__, cli, model_manager

runner = CliRunner()


def test_no_args_shows_help():
    result = runner.invoke(cli.app, [])
    assert "enhance" in result.stdout


def test_version_flag():
    result = runner.invoke(cli.app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_enhance_file_rejects_nonexistent_path(tmp_path):
    missing = tmp_path / "does-not-exist.mp3"
    result = runner.invoke(cli.app, ["enhance", "file", str(missing)])
    assert result.exit_code != 0


def test_enhance_folder_rejects_a_file_path(tmp_path):
    a_file = tmp_path / "track.mp3"
    a_file.write_bytes(b"fake")
    result = runner.invoke(cli.app, ["enhance", "folder", str(a_file)])
    assert result.exit_code != 0


def test_workers_greater_than_one_errors(tmp_path):
    rc = cli._cmd_folder(tmp_path, False, 2, False, None)
    assert rc == 1


def test_check_reports_failure_when_model_missing(
    monkeypatch, fake_cache_dir, fake_manifest
):
    monkeypatch.setattr(model_manager, "load_manifest", lambda: fake_manifest)
    rc = cli._cmd_check()
    assert rc == 1


def test_setup_calls_model_manager(monkeypatch):
    calls = []

    def fake_ensure(on_progress=None):
        calls.append("ensure")
        return model_manager.ModelPaths(model_path="m", config_path="c")

    monkeypatch.setattr(model_manager, "ensure_model_assets", fake_ensure)
    monkeypatch.setattr(model_manager, "inference_script_path", lambda: "script.py")
    monkeypatch.setattr(model_manager, "run_self_test", lambda *a: True)

    rc = cli._cmd_setup()
    assert rc == 0
    assert calls == ["ensure"]
