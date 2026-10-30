"""09.02 unit contracts; no SQLite, Qt or Gemini 2 required."""
from dataclasses import FrozenInstanceError
import subprocess
import sys

import pytest

from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.replay import RawReplayError, RawReplayService
from tests.support.raw_fixture import raw


def ctx(*, capture_id="c1"):
    return CaptureContext("C:/existing", "p1", "s1", "t1", capture_id)


class FakePort:
    def __init__(self, packet):
        self.packet = packet
        self.calls = []

    def load(self, context):
        self.calls.append(context)
        return self.packet


def test_explicit_capture_roundtrip_and_no_mutation():
    packet = raw(session="t1", specimen="s1", capture_id="c1")
    port = FakePort(packet)
    context = ctx()
    service = RawReplayService(port)
    assert service.load(context) is packet
    assert service.load(context).color_mjpeg == packet.color_mjpeg
    assert port.calls == [context, context]
    with pytest.raises(FrozenInstanceError):
        context.capture_id = "c2"


def test_missing_capture_id_is_rejected_without_port_call():
    port = FakePort(None)
    with pytest.raises(RawReplayError) as ex:
        RawReplayService(port).load(ctx(capture_id=None))
    assert ex.value.code == "CAPTURE_ID_REQUIRED"
    assert port.calls == []


def test_wrong_input_type_is_rejected():
    with pytest.raises(TypeError):
        RawReplayService(FakePort(None)).load({"capture_id": "c1"})


@pytest.mark.parametrize("packet", [None, object(), {"data": "fake"}])
def test_non_raw_result_fails_closed(packet):
    with pytest.raises(RawReplayError) as ex:
        RawReplayService(FakePort(packet)).load(ctx())
    assert ex.value.code == "INVALID_REPLAY_RESULT"


@pytest.mark.parametrize("metadata", [
    {"session": "wrong"}, {"specimen": "wrong"}, {"capture_id": "wrong"},
])
def test_packet_identity_mismatch_rejected(metadata):
    args = {"session": "t1", "specimen": "s1", "capture_id": "c1"}
    args.update(metadata)
    port = FakePort(raw(**args))
    with pytest.raises(RawReplayError) as ex:
        RawReplayService(port).load(ctx())
    assert ex.value.code == "CAPTURE_CONTEXT_MISMATCH"


def test_port_failure_does_not_try_another_capture():
    class FailPort:
        def __init__(self): self.calls = 0
        def load(self, _context):
            self.calls += 1
            raise RawReplayError("RAW_MISSING", "Not present")
    port = FailPort()
    with pytest.raises(RawReplayError, match="Not present"):
        RawReplayService(port).load(ctx())
    assert port.calls == 1


def test_import_is_lazy_and_does_not_load_storage_sqlite_qt_or_sdk():
    script = (
        "import sys; "
        "from scantopath.modules.capture.application.replay import RawReplayService; "
        "from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter; "
        "assert 'PySide6' not in sys.modules; "
        "assert 'scantopath.storage.session_store' not in sys.modules; "
        "assert 'scantopath.metadata.store' not in sys.modules; "
        "assert 'scantopath.acquisition.native' not in sys.modules"
    )
    run = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
