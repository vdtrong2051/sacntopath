"""09.07.3 subprocess isolation: fatal native-style exits cannot kill parent."""
import pytest

from scantopath.modules.capture.application.live_stream import LiveCameraError, LiveNativeFrame
from scantopath.modules.capture.infrastructure.process_camera import ProcessIsolatedCameraAdapter
from tests.support.process_camera_fakes import (
    normal_camera, crash_open_camera, crash_read_camera, crash_close_camera,
    timeout_camera, fail_open_camera, read_error_camera, invalid_packet_camera,
    hang_camera,
)


def test_process_open_read_close_and_reopen():
    adapter = ProcessIsolatedCameraAdapter(camera_factory=normal_camera)
    for _ in range(2):
        adapter.open()
        assert adapter.child_pid is not None
        frame = adapter.read_next(per_attempt_timeout_ms=300, max_attempts=1)
        assert isinstance(frame, LiveNativeFrame)
        assert frame.color_mjpeg == b"fake-jpeg"
        assert frame.depth_y16_le == b"\x02\x00" * 6
        adapter.close()
        assert adapter.child_pid is None
        assert adapter.last_exit_code == 0
    adapter.close()  # Idempotent.


def test_child_heap_corruption_equivalent_on_read():
    adapter = ProcessIsolatedCameraAdapter(camera_factory=crash_read_camera)
    adapter.open()
    with pytest.raises(LiveCameraError) as exc:
        adapter.read_next(per_attempt_timeout_ms=300, max_attempts=1)
    assert exc.value.code == "DEVICE_PROCESS_CRASH"
    with pytest.raises(LiveCameraError):
        adapter.close()
    assert adapter.child_pid is None
    assert adapter.last_exit_code == 93


def test_child_heap_corruption_equivalent_on_close():
    adapter = ProcessIsolatedCameraAdapter(camera_factory=crash_close_camera)
    adapter.open()
    adapter.read_next(per_attempt_timeout_ms=300, max_attempts=1)
    with pytest.raises(LiveCameraError) as exc:
        adapter.close()
    assert exc.value.code == "DEVICE_PROCESS_CRASH"
    assert adapter.last_exit_code == 92
    assert adapter.child_pid is None


def test_child_crashes_during_open():
    adapter = ProcessIsolatedCameraAdapter(camera_factory=crash_open_camera)
    with pytest.raises(LiveCameraError) as exc:
        adapter.open()
    assert exc.value.code == "DEVICE_PROCESS_CRASH"
    assert adapter.last_exit_code == 91
    assert adapter.child_pid is None


def test_child_ordinary_open_failure():
    adapter = ProcessIsolatedCameraAdapter(camera_factory=fail_open_camera)
    with pytest.raises(LiveCameraError) as exc:
        adapter.open()
    assert exc.value.code == "OPEN_FAILED"
    assert adapter.child_pid is None


def test_child_timeout_remains_recoverable():
    adapter = ProcessIsolatedCameraAdapter(camera_factory=timeout_camera)
    adapter.open()
    try:
        with pytest.raises(TimeoutError):
            adapter.read_next(per_attempt_timeout_ms=300, max_attempts=1)
    finally:
        adapter.close()
    assert adapter.last_exit_code == 0


def test_child_read_error():
    adapter = ProcessIsolatedCameraAdapter(camera_factory=read_error_camera)
    adapter.open()
    try:
        with pytest.raises(LiveCameraError) as exc:
            adapter.read_next(per_attempt_timeout_ms=300, max_attempts=1)
        assert exc.value.code == "READ_FAILED"
    finally:
        # Child has already returned after fatal read error.
        try:
            adapter.close()
        except LiveCameraError:
            pass
    assert adapter.child_pid is None


def test_child_rejects_noncontract_frame():
    adapter = ProcessIsolatedCameraAdapter(camera_factory=invalid_packet_camera)
    adapter.open()
    try:
        with pytest.raises(LiveCameraError) as exc:
            adapter.read_next(per_attempt_timeout_ms=300, max_attempts=1)
        assert exc.value.code == "INVALID_DEVICE_RESPONSE"
    finally:
        adapter.close()


def test_unresponsive_child_is_killed_not_main_thread():
    adapter = ProcessIsolatedCameraAdapter(
        camera_factory=hang_camera, read_timeout_ms=120, close_timeout_ms=120
    )
    adapter.open()
    with pytest.raises(LiveCameraError) as exc:
        adapter.read_next(per_attempt_timeout_ms=300, max_attempts=1)
    assert exc.value.code == "DEVICE_PROCESS_TIMEOUT"
    with pytest.raises(LiveCameraError):
        adapter.close()
    assert adapter.child_pid is None
    assert adapter.last_exit_code is not None


def test_process_port_does_not_accept_unsafe_parameters():
    with pytest.raises(ValueError):
        ProcessIsolatedCameraAdapter(read_timeout_ms=0)
    with pytest.raises(TypeError):
        ProcessIsolatedCameraAdapter(camera_factory=None)
    adapter = ProcessIsolatedCameraAdapter(camera_factory=normal_camera)
    with pytest.raises(LiveCameraError) as exc:
        adapter.read_next(per_attempt_timeout_ms=300, max_attempts=1)
    assert exc.value.code == "NOT_OPEN"
    adapter.open()
    try:
        with pytest.raises(LiveCameraError) as exc:
            adapter.open()
        assert exc.value.code == "ALREADY_OPEN"
        with pytest.raises(ValueError):
            adapter.read_next(per_attempt_timeout_ms=0, max_attempts=1)
    finally:
        adapter.close()
