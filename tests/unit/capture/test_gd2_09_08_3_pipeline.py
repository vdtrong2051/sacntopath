"""09.08.3 offline application contract tests. No hardware, SQLite, filesystem or Qt."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.modules.capture.application.capture_service import CaptureCommitError, CaptureCommitService
from scantopath.modules.capture.application.capture_pipeline import CapturePipelineService, CapturePipelineError
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.live_stream import LiveCameraError
from tests.support.raw_fixture import raw
from tests.support.gd2_0983_camera_fakes import PipelineFakeCamera


def context(capture_id=None):
    return CaptureContext("C:/temp/fake", "p1", "s1", "t1", capture_id)


class FakeStore:
    def __init__(self, events, failure=None):
        self.events = events
        self.failure = failure
        self.accepted = []

    def validate_context(self, ctx):
        self.events.append("preflight")
        if self.failure == "context":
            raise CaptureCommitError("SESSION_NOT_OPEN")

    def commit(self, ctx, packet):
        self.events.append("commit")
        if self.failure == "write":
            raise CaptureCommitError("RAW_WRITE_FAILED")
        self.accepted.append(packet)
        return packet.metadata.capture_id


class Source:
    def __init__(self, events, mode="normal"):
        self.events = events
        self.fake = PipelineFakeCamera(mode)
        self.fake.open()

    def capture_next_raw(self, *, session_id, specimen_id):
        self.events.append("capture")
        return self.fake.capture_next_raw(session_id=session_id, specimen_id=specimen_id)


def build(*, failure=None, mode="normal"):
    events = []
    store = FakeStore(events, failure=failure)
    source = Source(events, mode)
    return CapturePipelineService(source, CaptureCommitService(store), store), store, events


def test_preflight_happens_before_camera_and_storage():
    service, store, events = build()
    result = service.capture_and_commit(context())
    assert events == ["preflight", "capture", "commit"]
    assert result.capture_id == "pipeline-fake-0001"
    assert result.color_frame_index == 1
    assert len(result.color_sha256) == len(result.depth_sha256) == 64
    assert store.accepted[0].metadata.measured is False


def test_five_distinct_capture_ids_monotonic_stream_indices():
    service, _, events = build()
    receipts = [service.capture_and_commit(context()) for _ in range(5)]
    assert [r.color_frame_index for r in receipts] == [1, 2, 3, 4, 5]
    assert len(set(r.capture_id for r in receipts)) == 5
    assert events.count("preflight") == events.count("capture") == events.count("commit") == 5


def test_invalid_store_rejected_before_camera_read():
    service, _, events = build(failure="context")
    with pytest.raises(CapturePipelineError) as exc:
        service.capture_and_commit(context())
    assert exc.value.code == "SESSION_NOT_OPEN"
    assert events == ["preflight"]


def test_existing_capture_identity_not_allowed_for_new_sensor_frame():
    service, _, events = build()
    with pytest.raises(CapturePipelineError) as exc:
        service.capture_and_commit(context("already-registered"))
    assert exc.value.code == "NEW_CAPTURE_CONTEXT_REQUIRED"
    assert events == []


def test_acquisition_timeout_does_not_commit():
    service, _, events = build(mode="timeout")
    with pytest.raises(CapturePipelineError) as exc:
        service.capture_and_commit(context())
    assert exc.value.code == "CAPTURE_TIMEOUT"
    assert events == ["preflight", "capture"]


def test_acquisition_wrong_packet_does_not_commit():
    service, _, events = build(mode="bad")
    with pytest.raises(CapturePipelineError) as exc:
        service.capture_and_commit(context())
    assert exc.value.code == "INVALID_KEYFRAME"
    assert events == ["preflight", "capture"]


def test_wrong_session_metadata_cannot_be_registered():
    events = []
    store = FakeStore(events)
    class WrongContext:
        def capture_next_raw(self, *, session_id, specimen_id):
            events.append("capture")
            return raw(session="wrong", specimen=specimen_id, capture_id="x")
    service = CapturePipelineService(WrongContext(), CaptureCommitService(store), store)
    with pytest.raises(CapturePipelineError) as exc:
        service.capture_and_commit(context())
    assert exc.value.code == "INVALID_KEYFRAME"
    assert events == ["preflight", "capture"]


def test_repeated_frame_indices_rejected_before_commit():
    events = []
    store = FakeStore(events)
    class SamePacket:
        def capture_next_raw(self, *, session_id, specimen_id):
            events.append("capture")
            return raw(session=session_id, specimen=specimen_id, capture_id=f"different-{events.count('capture')}")
    service = CapturePipelineService(SamePacket(), CaptureCommitService(store), store)
    assert service.capture_and_commit(context()).capture_id == "different-1"
    with pytest.raises(CapturePipelineError) as exc:
        service.capture_and_commit(context())
    assert exc.value.code == "STALE_KEYFRAME"
    assert events.count("commit") == 1


def test_capture_id_reused_with_fresh_frame_index_rejected():
    events = []
    store = FakeStore(events)
    class SameID:
        def __init__(self): self.i = 0
        def capture_next_raw(self, *, session_id, specimen_id):
            self.i += 1
            events.append("capture")
            packet = raw(session=session_id, specimen=specimen_id, capture_id="same-id")
            m = packet.metadata.model_copy(update={
                "color": packet.metadata.color.model_copy(update={"frame_index": self.i}),
                "depth": packet.metadata.depth.model_copy(update={"frame_index": self.i}),
            })
            return RawRgbdCapture(m, packet.color_mjpeg, packet.depth_y16_le)
    service = CapturePipelineService(SameID(), CaptureCommitService(store), store)
    assert service.capture_and_commit(context()).capture_id == "same-id"
    with pytest.raises(CapturePipelineError) as exc:
        service.capture_and_commit(context())
    assert exc.value.code == "DUPLICATE_KEYFRAME_ID"
    assert events.count("commit") == 1


def test_storage_failure_cannot_be_reported_as_capture_success():
    service, _, events = build(failure="write")
    with pytest.raises(CapturePipelineError) as exc:
        service.capture_and_commit(context())
    assert exc.value.code == "RAW_WRITE_FAILED"
    assert events == ["preflight", "capture", "commit"]


def test_preflight_unexpected_error_is_stable():
    events = []
    store = FakeStore(events)
    def fails(_):
        raise RuntimeError("do not expose private path")
    store.validate_context = fails
    source = Source(events)
    service = CapturePipelineService(source, CaptureCommitService(store), store)
    with pytest.raises(CapturePipelineError) as exc:
        service.capture_and_commit(context())
    assert exc.value.code == "CAPTURE_PREFLIGHT_FAILED"
    assert events == []
