"""GD2-09.06 pure lifecycle transitions: no Qt/OrbbecSDK required."""
import pytest

from scantopath.modules.capture.application.lifecycle import CameraLifecycle
from scantopath.modules.capture.domain.models import CameraState as S


def test_normal_start_stop_reopen():
    m = CameraLifecycle()
    assert m.state is S.IDLE
    assert m.start() and m.state is S.OPENING
    assert not m.start()
    assert m.opened() and m.state is S.STREAMING
    assert not m.opened()
    assert m.stop() and m.state is S.STOPPING
    assert not m.stop()
    assert m.finished() is S.CLOSED
    assert m.error_code is None
    assert m.start() and m.state is S.OPENING


def test_stop_while_opening_without_late_open():
    m = CameraLifecycle()
    assert m.start()
    assert m.stop()
    assert not m.opened()
    assert m.finished() is S.CLOSED


def test_failure_is_only_terminal_after_cleanup():
    m = CameraLifecycle()
    m.start()
    m.record_failure("OPEN_FAILED")
    assert m.state is S.OPENING
    assert not m.start()
    assert m.finished() is S.FAILED
    assert m.error_code == "OPEN_FAILED"
    assert m.start()
    assert m.error_code is None


def test_cleanup_error_preserves_primary_reason():
    m = CameraLifecycle()
    m.start()
    m.opened()
    m.record_failure("READ_FAILED")
    m.record_failure("CLOSE_FAILED")
    assert m.finished() is S.FAILED
    assert m.error_code == "READ_FAILED"


def test_stopping_then_timeout_becomes_failed_only_after_finish():
    m = CameraLifecycle()
    m.start()
    m.stop()
    m.record_failure("STOP_TIMEOUT")
    assert m.state is S.STOPPING
    assert m.finished() is S.FAILED


def test_unexpected_worker_exit_rejected_as_success():
    m = CameraLifecycle()
    m.start()
    m.opened()
    assert m.finished() is S.FAILED
    assert m.error_code == "WORKER_UNEXPECTED_EXIT"


@pytest.mark.parametrize("code", ["", "foo", "path/to/error", "LỖI", None, 42])
def test_reject_unsafe_error_codes(code):
    m = CameraLifecycle()
    m.start()
    with pytest.raises(ValueError):
        m.record_failure(code)


def test_disallow_finished_without_worker_and_failure_in_idle():
    m = CameraLifecycle()
    with pytest.raises(RuntimeError):
        m.finished()
    with pytest.raises(RuntimeError):
        m.record_failure("ERROR")
