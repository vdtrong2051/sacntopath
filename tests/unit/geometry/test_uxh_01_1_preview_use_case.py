"""UXH-01.1: application orchestration with fakes, no native viewer/camera."""
from __future__ import annotations

from pathlib import Path

import pytest

from scantopath.application.contracts.preview import PreviewReceipt
from scantopath.application.geometry_preview import PreviewGeometryUseCase
from scantopath.modules.capture.application.contracts import CaptureContext


def test_preview_use_case_orchestrates_one_explicit_capture(tmp_path):
    events = []
    context = CaptureContext(str(tmp_path), "p", "s", "t", "c")
    shadow = CaptureContext(str(tmp_path / "snapshot"), "p", "s", "t", "c")
    geometry = object()

    def snapshot(selected, target):
        events.append(("snapshot", selected, target))
        return shadow

    class Replay:
        def process(self, selected):
            events.append(("replay", selected))
            return geometry

    def write_ply(cloud, target):
        events.append(("ply", cloud, target))
        return PreviewReceipt(Path(target), "c", 2, 1, "a" * 64)

    service = PreviewGeometryUseCase(snapshot, Replay(), write_ply)
    receipt, output = service.process(context, tmp_path)
    assert output is geometry
    assert receipt.capture_id == "c"
    assert receipt.status == "PROVISIONAL_NOT_METRIC_VALIDATED"
    assert events == [
        ("snapshot", context, tmp_path / "snapshot"),
        ("replay", shadow),
        ("ply", geometry, tmp_path / "capture_c_preview.ply"),
    ]


def test_preview_use_case_rejects_implicit_capture_before_io(tmp_path):
    calls = []
    def snapshot(*args):
        calls.append("snapshot")
    class Replay:
        def process(self, *_args):
            calls.append("replay")
    def write_ply(*args):
        calls.append("ply")
    service = PreviewGeometryUseCase(snapshot, Replay(), write_ply)
    with pytest.raises(ValueError, match="explicit capture_id"):
        service.process(CaptureContext(str(tmp_path), "p", "s", "t"), tmp_path)
    assert calls == []


def test_preview_use_case_propagates_snapshot_failure(tmp_path):
    class Failure(ValueError):
        code = "RAW_CHANGED_DURING_SNAPSHOT"
    def snapshot(*args):
        raise Failure("source changed")
    class Replay:
        def process(self, *_args):
            pytest.fail("must not replay after snapshot failure")
    service = PreviewGeometryUseCase(snapshot, Replay(), lambda *_: None)
    with pytest.raises(Failure) as error:
        service.process(CaptureContext(str(tmp_path), "p", "s", "t", "c"), tmp_path)
    assert error.value.code == "RAW_CHANGED_DURING_SNAPSHOT"


def test_preview_use_case_rejects_invalid_ports():
    with pytest.raises(TypeError):
        PreviewGeometryUseCase(None, object(), None)
