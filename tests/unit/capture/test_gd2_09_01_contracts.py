"""Scaffold contract tests, NOT G2-09-A/B/C feature acceptance."""
from dataclasses import FrozenInstanceError
import pytest

from scantopath.modules.capture.domain.models import CameraState, DepthRoi, RoiSource
from scantopath.modules.capture.application.contracts import CaptureContext


def test_capture_context_requires_explicit_valid_ids():
    ctx = CaptureContext("C:/test-project", "p1", "s1", "t1")
    assert ctx.capture_id is None
    with pytest.raises(ValueError):
        CaptureContext("", "p1", "s1", "t1")
    with pytest.raises(ValueError):
        CaptureContext("C:/test-project", "../p1", "s1", "t1")
    with pytest.raises(FrozenInstanceError):
        ctx.session_id = "other"


def test_depth_roi_uses_depth_grid_and_rejects_out_of_bounds():
    box = DepthRoi(1, 2, 10, 20, 1280, 800, RoiSource.MANUAL)
    assert (box.x, box.y, box.width, box.height) == (1, 2, 10, 20)
    with pytest.raises(ValueError):
        DepthRoi(1279, 0, 2, 3, 1280, 800)
    with pytest.raises(TypeError):
        DepthRoi(True, 2, 10, 20, 1280, 800)


def test_camera_states_are_labels_not_running_workers():
    assert CameraState.IDLE.value == "idle"
    assert CameraState.FAILED.value == "failed"

@pytest.mark.parametrize(
    "field",
    ["project_id", "specimen_id", "session_id", "capture_id"],
)
@pytest.mark.parametrize(
    "bad",
    ["", " ", "../escape", "a/b", r"a\b", "x.y", 3, True],
)
def test_capture_context_rejects_invalid_identifiers(field, bad):
    args = dict(
        store_root="C:/data",
        project_id="p1",
        specimen_id="s1",
        session_id="t1",
        capture_id="c1",
    )
    args[field] = bad

    with pytest.raises(ValueError):
        CaptureContext(**args)


def test_replay_must_identify_a_capture_and_cannot_mutate_context():
    new = CaptureContext("C:/data", "p1", "s1", "t1")

    with pytest.raises(ValueError, match="explicit capture_id"):
        new.require_replay_capture_id()

    old = CaptureContext("C:/data", "p1", "s1", "t1", "c1")

    assert old.require_replay_capture_id() == "c1"

    with pytest.raises(FrozenInstanceError):
        old.capture_id = "c2"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"x": -1},
        {"y": -1},
        {"width": 0},
        {"height": 0},
        {"frame_width": 0},
        {"frame_height": 0},
        {"width": 1281},
        {"height": 801},
        {"source": "unknown"},
    ],
)
def test_depth_roi_rejects_invalid_geometry_and_source(kwargs):
    args = dict(
        x=0,
        y=0,
        width=10,
        height=10,
        frame_width=1280,
        frame_height=800,
        source=RoiSource.MANUAL,
    )
    args.update(kwargs)

    with pytest.raises((ValueError, TypeError)):
        DepthRoi(**args)


def test_depth_roi_can_touch_right_and_bottom_edges():
    roi = DepthRoi(1270, 790, 10, 10, 1280, 800)

    assert roi.x + roi.width == roi.frame_width
    assert roi.y + roi.height == roi.frame_height


def test_capture_ports_are_only_protocols_without_loading_runtime():
    import subprocess
    import sys

    code = (
        "import sys; "
        "from scantopath.modules.capture.application.ports "
        "import RawReplayPort, NativeCameraPort, CapturePersistencePort; "
        "from scantopath.modules.capture.domain.models "
        "import CameraState, DepthRoi; "
        "assert 'PySide6' not in sys.modules; "
        "assert 'scantopath.acquisition.native' not in sys.modules; "
        "assert 'scantopath.metadata.store' not in sys.modules; "
        "assert 'scantopath.storage.session_store' not in sys.modules; "
        "print('IMPORT_BOUNDARY_OK')"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "IMPORT_BOUNDARY_OK" in result.stdout


def test_port_signatures_match_approved_boundaries():
    from inspect import signature

    from scantopath.modules.capture.application.ports import (
        RawReplayPort,
        NativeCameraPort,
        CapturePersistencePort,
    )

    assert tuple(signature(RawReplayPort.load).parameters) == (
        "self", "context"
    )

    assert tuple(signature(NativeCameraPort.read_next).parameters) == (
        "self",
        "per_attempt_timeout_ms",
        "max_attempts",
    )

    assert tuple(signature(CapturePersistencePort.commit).parameters) == (
        "self", "context", "raw"
    )