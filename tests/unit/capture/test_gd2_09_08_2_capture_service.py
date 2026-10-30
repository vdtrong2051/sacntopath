"""09.08.2 application-only tests: no disk, SQLite, Qt or OrbbecSDK."""
from __future__ import annotations

from dataclasses import replace

import pytest

from scantopath.modules.capture.application.capture_service import (
    CaptureCommitService, CaptureCommitError,
)
from scantopath.modules.capture.application.contracts import CaptureContext
from tests.support.raw_fixture import raw


class FakePersistence:
    def __init__(self, result="ok") -> None:
        self.result = result
        self.calls = []

    def commit(self, context, packet):
        self.calls.append((context, packet))
        if isinstance(self.result, Exception):
            raise self.result
        return packet.metadata.capture_id if self.result == "ok" else self.result


def ctx(*, session="t1", specimen="s1", capture_id=None):
    return CaptureContext("/fixture/not/accessed", "p1", specimen, session, capture_id)


def test_application_calls_persistence_once_with_same_owned_packet():
    packet = raw(session="t1", specimen="s1", capture_id="capt-1")
    fake = FakePersistence()
    assert CaptureCommitService(fake).commit(ctx(), packet) == "capt-1"
    assert fake.calls == [(ctx(), packet)]


@pytest.mark.parametrize("context", [
    ctx(session="other"), ctx(specimen="other"), ctx(capture_id="other"),
])
def test_metadata_context_mismatch_never_calls_persistence(context):
    fake = FakePersistence()
    with pytest.raises(CaptureCommitError) as e:
        CaptureCommitService(fake).commit(context, raw(session="t1", specimen="s1"))
    assert e.value.code == "CAPTURE_CONTEXT_MISMATCH"
    assert fake.calls == []


def test_port_exception_has_safe_code():
    fake = FakePersistence(OSError("sensitive absolute path"))
    with pytest.raises(CaptureCommitError) as e:
        CaptureCommitService(fake).commit(ctx(), raw(session="t1", specimen="s1"))
    assert e.value.code == "CAPTURE_PERSISTENCE_FAILED"


def test_existing_typed_persistence_error_is_preserved():
    fake = FakePersistence(CaptureCommitError("RAW_WRITE_FAILED"))
    with pytest.raises(CaptureCommitError) as e:
        CaptureCommitService(fake).commit(ctx(), raw(session="t1", specimen="s1"))
    assert e.value.code == "RAW_WRITE_FAILED"


@pytest.mark.parametrize("bad_result", [None, "wrong-id", 42])
def test_bad_port_result_is_never_success(bad_result):
    fake = FakePersistence(bad_result)
    with pytest.raises(CaptureCommitError) as e:
        CaptureCommitService(fake).commit(ctx(), raw(session="t1", specimen="s1"))
    assert e.value.code == "INVALID_PERSISTENCE_RESULT"


def test_invalid_input_types_rejected_before_port():
    fake = FakePersistence()
    with pytest.raises(TypeError):
        CaptureCommitService(fake).commit(object(), raw(session="t1", specimen="s1"))
    with pytest.raises(TypeError):
        CaptureCommitService(fake).commit(ctx(), object())
    assert not fake.calls
