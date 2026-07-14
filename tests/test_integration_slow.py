"""Real end-to-end tests: real model download + real onnxruntime inference.
Excluded by default (pytest.ini addopts = -m "not slow"); run explicitly with
`pytest -m slow` after a GitHub Release with the real model assets exists."""

import pytest

from echovault_flac_enhancer import model_manager


@pytest.mark.slow
def test_real_setup_and_self_test():
    paths = model_manager.ensure_model_assets()
    inference_script = model_manager.inference_script_path()
    assert model_manager.run_self_test(
        inference_script, paths.model_path, paths.config_path
    )
