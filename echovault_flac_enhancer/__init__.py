"""echovault-flac-enhancer: standalone CLI wrapper around EchoVault's ONNX FLAC enhancer."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("echovault-flac-enhancer")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
