"""Offline tests: never initialize OrbbecSDK or require attached hardware."""
import importlib
import os
from types import SimpleNamespace
from unittest.mock import patch


def test_python_native_loader_is_lazy():
    module = importlib.import_module("scantopath.acquisition.native")
    assert callable(module.load_native)
    assert callable(module.main)


def test_python_native_loader_can_load_mocked_extension():
    from scantopath.acquisition import native
    fake = SimpleNamespace(binding_stage="GD1.2.3.2.2")
    with patch.dict(os.environ, {}, clear=False):
        with patch.object(native.importlib, "import_module", return_value=fake) as loader:
            got = native.load_native()
    assert got is fake
    loader.assert_called_once_with("scantopath._scantopath_native")
