"""PRE-04 integration tests use MOCK native packets; no OrbbecSDK/camera required."""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace as NS
import subprocess
import sys

import numpy as np
import pytest
from pydantic import ValidationError

from scantopath.acquisition import capture_once
from scantopath.acquisition.orbbec_adapter import capture_one_raw, raw_capture_from_native
from scantopath.domain.models import CaptureKind
from scantopath.storage.session_store import SessionStore


JPEG = b"\xff\xd8synthetic PRE-04 packet\xff\xd9"  # Not a decodable image.
DEPTH = np.array([[0, 12, 65535], [1000, 2000, 3500]], dtype="<u2").tobytes()


def _native_packet():
    """Fake pybind11 object matching actual fields exposed in orbbec_bindings.cpp."""
    return NS(
        validate=lambda: True,
        device=NS(name="Orbbec Gemini 2", firmware="1.4.98", usb_connection="USB 3.0", pid=1234),
        color=NS(encoding=NS(name="MJPEG"), width=5, height=4,
                 frame_index=23, timestamp_us=100_000, bytes=JPEG),
        depth=NS(encoding=NS(name="Y16"), width=3, height=2,
                 frame_index=24, timestamp_us=103_308, bytes=DEPTH),
        color_intrinsics=NS(width=5, height=4, fx=4.5, fy=4.6, cx=2.0, cy=1.5),
        depth_intrinsics=NS(width=3, height=2, fx=3.5, fy=3.6, cx=1.0, cy=0.5),
        color_distortion=NS(sdk_model=1, k1_k6_p1_p2=[0.] * 8),
        depth_distortion=NS(sdk_model=2, k1_k6_p1_p2=[0.1] + [0.] * 7),
        depth_to_color=NS(rotation=[1., 0., 0., 0., 1., 0., 0., 0., 1.],
                          translation_mm=[-13.787516, -0.10409, -1.982521]),
        depth_scale_m_per_unit=0.001,
        align_disabled=True,
        frame_sync_requested=True,
    )


class FakeSource:
    def __init__(self, packet=None, error=None, open_error=None):
        self.packet = _native_packet() if packet is None else packet
        self.error = error
        self.open_error = open_error
        self.events = []

    def open(self):
        self.events.append("open")
        if self.open_error:
            raise self.open_error

    def read_next(self):
        self.events.append("read")
        if self.error:
            raise self.error
        return self.packet

    def close(self):
        self.events.append("close")


def test_native_fields_mapped_without_alignment_or_pose():
    raw = raw_capture_from_native(_native_packet(), session_id="sess-1", specimen_id="obj-1")
    m = raw.metadata
    assert m.schema_version == 2 and m.measured and m.kind == CaptureKind.ORBBEC
    assert m.device.name == "Orbbec Gemini 2" and m.device.firmware_version == "1.4.98"
    assert m.device.sdk_version is None and m.device.serial is None
    assert (m.color.width, m.color.height) == (5, 4)
    assert (m.depth.width, m.depth.height) == (3, 2)
    assert m.color.frame_index == 23 and m.depth.frame_index == 24
    assert m.color.timestamp_us == 100_000 and m.depth.timestamp_us == 103_308
    assert m.observed_timestamp_delta_us == 3308
    assert m.timestamp_domain == "sdk_reported_unverified" and m.frame_sync_requested
    assert m.alignment_mode == "disabled" and m.camera_pose is None
    assert m.depth_to_color.translation_mm[0] == pytest.approx(-13.787516)
    assert m.depth_scale_m_per_unit == 0.001
    assert m.color_distortion.sdk_model != m.depth_distortion.sdk_model
    assert raw.color_mjpeg == JPEG and raw.depth_y16_le == DEPTH
    np.testing.assert_array_equal(raw.depth_u16_copy(), np.array([[0, 12, 65535], [1000, 2000, 3500]], dtype=np.uint16))


def test_no_vendor_sdk_import_to_convert_fake_packet():
    # PRE-04 tests do not import native camera extension as a side effect.
    assert "scantopath._scantopath_native" not in sys.modules
    raw_capture_from_native(_native_packet(), session_id="s", specimen_id="p")
    assert "scantopath._scantopath_native" not in sys.modules


def test_source_closed_before_packet_is_converted(monkeypatch):
    source = FakeSource()
    original = raw_capture_from_native

    def convert_after_close(packet, **kwargs):
        assert source.events == ["open", "read", "close"]
        source.events.append("convert")
        return original(packet, **kwargs)

    monkeypatch.setattr("scantopath.acquisition.orbbec_adapter.raw_capture_from_native",
                        convert_after_close)
    raw = capture_one_raw(native=NS(OrbbecCameraSource=lambda: source),
                          session_id="s", specimen_id="p")
    assert source.events == ["open", "read", "close", "convert"]
    assert raw.depth_y16_le == DEPTH


def test_source_always_closed_after_frame_read_failure():
    source = FakeSource(error=RuntimeError("timeout"))
    with pytest.raises(RuntimeError, match="timeout"):
        capture_one_raw(native=NS(OrbbecCameraSource=lambda: source),
                        session_id="s", specimen_id="p")
    assert source.events == ["open", "read", "close"]


def test_source_closed_after_open_failure():
    source = FakeSource(open_error=RuntimeError("camera unavailable"))
    with pytest.raises(RuntimeError, match="camera unavailable"):
        capture_one_raw(native=NS(OrbbecCameraSource=lambda: source),
                        session_id="s", specimen_id="p")
    assert source.events == ["open", "close"]


@pytest.mark.parametrize("alter,match", [
    (lambda p: setattr(p, "validate", lambda: False), "Native RGB-D"),
    (lambda p: setattr(p.color.encoding, "name", "RGB8"), "original MJPEG"),
    (lambda p: setattr(p, "align_disabled", False), "aligned"),
])
def test_invalid_native_frame_rejected(alter, match):
    pkt = _native_packet()
    alter(pkt)
    with pytest.raises(ValueError, match=match):
        raw_capture_from_native(pkt, session_id="s", specimen_id="p")


def test_mismatched_calibration_rejected():
    pkt = _native_packet()
    pkt.depth_intrinsics.width = 4
    with pytest.raises(ValidationError, match="Depth intrinsics"):
        raw_capture_from_native(pkt, session_id="s", specimen_id="p")


def test_malformed_native_payload_length_rejected():
    pkt = _native_packet()
    pkt.depth.bytes = DEPTH[:-2]
    with pytest.raises(ValidationError, match="Y16 must use exactly"):
        raw_capture_from_native(pkt, session_id="s", specimen_id="p")


def test_fake_native_end_to_end_disk_roundtrip(tmp_path):
    source = FakeSource()
    raw = capture_one_raw(native=NS(OrbbecCameraSource=lambda: source),
                          session_id="scan-01", specimen_id="part-01")
    assert source.events == ["open", "read", "close"]
    store = SessionStore(tmp_path)
    path = store.commit_raw(raw)
    replay = store.read_raw(path)
    assert replay == raw
    assert replay.metadata.camera_pose is None
    assert (path / "color.mjpg").read_bytes() == JPEG
    assert (path / "depth.y16").read_bytes() == DEPTH
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["files"]["color.mjpg"]["sha256"]) == 64
    assert store.read_capture(path) == raw


def test_cli_once_persists_and_reports_without_printing_private_device_info(tmp_path, monkeypatch, capsys):
    raw = raw_capture_from_native(_native_packet(), session_id="s", specimen_id="p")
    monkeypatch.setattr(capture_once, "capture_one_raw", lambda **kw: raw)
    assert capture_once.main(["--once", "--output", str(tmp_path),
                              "--session", "s", "--specimen", "p"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["saved"] is True and result["checksum_verified"] is True
    assert result["schema_version"] == 2 and result["camera_pose_known"] is False
    assert result["color"]["encoding"] == "MJPEG" and result["depth"]["encoding"] == "Y16"
    assert "serial" not in result and "firmware" not in result
    assert (Path(result["capture_path"]) / "COMMITTED").exists()
    assert capture_once.main(["--verify", result["capture_path"], "--output", str(tmp_path)]) == 0
    verified = json.loads(capsys.readouterr().out)
    assert verified["capture_id"] == result["capture_id"]


def test_reopen_in_separate_python_process_without_native_or_camera(tmp_path):
    raw = raw_capture_from_native(_native_packet(), session_id="s", specimen_id="p")
    path = SessionStore(tmp_path).commit_raw(raw)
    # Force subprocess to import project src irrespective of editable pip state.
    src = str(Path(__file__).resolve().parents[1] / "src")
    env = os.environ.copy()
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, "-m", "scantopath.acquisition.capture_once", "--verify",
         str(path), "--output", str(tmp_path)],
        env=env, text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["checksum_verified"] and report["capture_id"] == raw.metadata.capture_id


def test_cli_verify_rejects_corrupted_frame(tmp_path):
    raw = raw_capture_from_native(_native_packet(), session_id="s", specimen_id="p")
    path = SessionStore(tmp_path).commit_raw(raw)
    (path / "color.mjpg").write_bytes(JPEG + b"tampered")
    with pytest.raises(ValueError, match="length mismatch"):
        capture_once.main(["--verify", str(path), "--output", str(tmp_path)])


def test_cli_rejects_invalid_session_before_opening_camera(monkeypatch, tmp_path):
    monkeypatch.setattr(capture_once, "capture_one_raw", lambda **kw: pytest.fail("camera opened"))
    with pytest.raises(ValueError, match="IDs must"):
        capture_once.main(["--once", "--output", str(tmp_path),
                           "--session", "../escape", "--specimen", "p"])


def test_gemini2_full_resolution_mock_native_storage_roundtrip(tmp_path):
    """2 MiB synthetic Y16 at real device dimensions; NOT a hardware capture."""
    pkt = _native_packet()
    pkt.color.width, pkt.color.height = 1920, 1080
    pkt.color_intrinsics.width, pkt.color_intrinsics.height = 1920, 1080
    pkt.depth.width, pkt.depth.height = 1280, 800
    pkt.depth_intrinsics.width, pkt.depth_intrinsics.height = 1280, 800
    pkt.depth.bytes = np.full((800, 1280), 420, dtype="<u2").tobytes()
    raw = raw_capture_from_native(pkt, session_id="s", specimen_id="p")
    path = SessionStore(tmp_path).commit_raw(raw)
    replay = SessionStore(tmp_path).read_raw(path)
    assert replay == raw
    assert replay.depth_u16_copy().shape == (800, 1280)
    assert replay.depth_u16_copy()[799, 1279] == 420
    assert replay.metadata.camera_pose is None
