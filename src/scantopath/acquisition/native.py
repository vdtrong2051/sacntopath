"""Lazy and explicit loader for the ScanToPath pybind11 acquisition module.

Importing this Python module NEVER opens a camera or requires the native extension.
Set SCANTOPATH_ORBBEC_SDK_BIN to the SDK's Windows ``bin`` folder before loading.
"""
from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path
from typing import Any

_DLL_DIRECTORY_HANDLE: Any = None


def load_native() -> Any:
    """Load the compiled native module, registering vendor DLLs when needed."""
    global _DLL_DIRECTORY_HANDLE
    if os.name == "nt":
        path = os.getenv("SCANTOPATH_ORBBEC_SDK_BIN")
        if path:
            sdk_bin = Path(path).expanduser()
            if not sdk_bin.is_dir() or not (sdk_bin / "OrbbecSDK.dll").is_file():
                raise RuntimeError(
                    "SCANTOPATH_ORBBEC_SDK_BIN must be the folder containing OrbbecSDK.dll: "
                    + str(sdk_bin)
                )
            if _DLL_DIRECTORY_HANDLE is None:
                # Since Python 3.8, PATH alone is not sufficient for extension DLLs.
                _DLL_DIRECTORY_HANDLE = os.add_dll_directory(str(sdk_bin))
    try:
        return importlib.import_module("scantopath._scantopath_native")
    except ImportError as exc:
        raise RuntimeError(
            "Cannot import ScanToPath native extension. Build with "
            "-DSCANTOPATH_BUILD_PYTHON_BINDINGS=ON and use the SAME Python "
            "interpreter/architecture as CMake. On Windows set "
            "SCANTOPATH_ORBBEC_SDK_BIN to your OrbbecSDK bin folder. "
            f"Original error: {exc}"
        ) from exc


def _self_test(native: Any) -> None:
    source = native.OrbbecCameraSource()
    assert source.is_open() is False
    source.close()  # Must be safe before open().
    try:
        source.device()
    except (RuntimeError, ValueError):
        pass
    else:
        raise AssertionError("device() before open() must fail")
    assert native.binding_stage == "GD1.2.3.2.2"
    if not hasattr(native, "_test_copy_y16"):
        raise RuntimeError("Binding self-test needs CMake BUILD_TESTING=ON")
    arr = native._test_copy_y16()
    assert arr.dtype.name == "uint16"
    assert arr.shape == (2, 3)
    assert arr.tolist() == [[1, 2, 3], [65535, 256, 0]]
    arr[0, 0] = 4321
    assert arr[0, 0] == 4321
    assert arr.flags.owndata
    print("native.import=true")
    print("native.memory_ownership=true")
    print("native.hardware_access=false")


def _one_capture(native: Any) -> None:
    source = native.OrbbecCameraSource()
    try:
        source.open()
        identity = source.device()
        capture = source.read_next()
        assert capture.validate()
    finally:
        source.close()
    # Both Python bytes and NumPy own their buffers after camera close.
    color = capture.color.bytes
    depth = capture.depth_u16()
    assert len(color) > 0
    assert depth.shape == (800, 1280)
    assert depth.dtype.name == "uint16" and depth.flags.owndata
    assert capture.depth_scale_m_per_unit > 0
    print(f"device.name={identity.name}")
    print(f"device.firmware={identity.firmware}")
    print(f"color.size={capture.color.width}x{capture.color.height}")
    print(f"color.encoding={capture.color.encoding.name}")
    print(f"color.bytes={len(color)}")
    print(f"depth.size={capture.depth.width}x{capture.depth.height}")
    print(f"depth.encoding={capture.depth.encoding.name}")
    print(f"depth.numpy.dtype={depth.dtype.name}")
    print(f"depth.numpy.shape={depth.shape}")
    print(f"depth.numpy.owns_data={depth.flags.owndata}")
    print(f"depth.scale_m_per_unit={capture.depth_scale_m_per_unit:.9f}")
    print(f"calibration.depth.fx={capture.depth_intrinsics.fx:.6f}")
    print(f"calibration.depth_to_color.tx_mm={capture.depth_to_color.translation_mm[0]:.6f}")
    print(f"timing.delta_us={capture.timestamp_delta_us()}")
    print("capture.valid=true")
    print("buffer.copy_survived_close=true")
    print("capture.saved=false")


def main() -> int:
    parser = argparse.ArgumentParser(description="ScanToPath pybind11 integration diagnostics")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--self-test", action="store_true", help="No camera required")
    choice.add_argument("--once", action="store_true", help="Read one real Gemini 2 capture")
    args = parser.parse_args()
    native = load_native()
    if args.self_test:
        _self_test(native)
    else:
        _one_capture(native)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
