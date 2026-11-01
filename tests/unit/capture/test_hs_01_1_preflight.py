"""HS-01.1 tests: no camera, SDK import, Qt application, RAW, or SQLite."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "hs_01_1_preflight.py"
spec = importlib.util.spec_from_file_location("hs_01_1_preflight", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sdk_diagnostic = module.sdk_diagnostic
write_report = module.write_report


def test_sdk_missing_variable_is_unverified_not_hardware_pass():
    assert sdk_diagnostic({})["status"] == "UNVERIFIED"


def test_sdk_requires_real_vendor_dll(tmp_path: Path):
    assert sdk_diagnostic({"SCANTOPATH_ORBBEC_SDK_BIN": str(tmp_path)})["status"] == "FAIL"
    (tmp_path / "OrbbecSDK.dll").write_bytes(b"only-a-filename-test")
    assert sdk_diagnostic({"SCANTOPATH_ORBBEC_SDK_BIN": str(tmp_path)})["status"] == "PASS"


def test_evidence_must_be_outside_repo_and_never_overwritten(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError, match="OUTSIDE_REPOSITORY"):
        write_report(repo / "evidence.json", {"decision": "PASS"}, root=repo)
    target = tmp_path / "reports" / "result.json"
    write_report(target, {"decision": "PASS_OFFLINE"}, root=repo)
    assert '"PASS_OFFLINE"' in target.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_report(target, {"decision": "FAIL"}, root=repo)
