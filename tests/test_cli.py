import pytest

from echovault_flac_enhancer import cli, model_manager


def test_mutually_exclusive_modes_required():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_mutually_exclusive_modes_conflict():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--folder", "x", "--file-name", "y"])


def test_workers_greater_than_one_errors(tmp_path, capsys):
    args = cli.build_parser().parse_args(["--folder", str(tmp_path), "--workers", "2"])
    rc = cli._cmd_folder(args)
    assert rc == 1
    assert "not implemented" in capsys.readouterr().err


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
