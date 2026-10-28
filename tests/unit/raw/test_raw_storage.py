"""PRE-03: offline persistence, corruption and v1 read compatibility tests.

Every capture here is synthetic; no native SDK or physical Gemini 2 needed.
"""
import hashlib
import json

import numpy as np
import pytest

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.acquisition.sources import SyntheticSource
from scantopath.domain.models import CaptureKind
from scantopath.domain.raw_rgbd import (
    RawDepthToColorExtrinsics, RawDeviceInfo, RawDistortion,
    RawIntrinsics, RawRgbdCaptureMetadataV2, RawStreamInfo, RawPixelEncoding,
)
from scantopath.storage.session_store import SessionStore


def fixture_capture(*, capture_id="test-raw-001", session_id="handheld-001"):
    # JPEG marker-only synthetic bytes: not a real, decodable image.
    color = b"\xff\xd8fake-mjpeg-fixture\xff\xd9"
    depth = np.array([[0, 1024, 65535], [42, 43, 44]], dtype="<u2").tobytes()
    zero_dist = RawDistortion(sdk_model=0, k1_k6_p1_p2=(0.,) * 8)
    meta = RawRgbdCaptureMetadataV2(
        capture_id=capture_id, session_id=session_id, specimen_id="object-A",
        kind=CaptureKind.SYNTHETIC, measured=False,
        device=RawDeviceInfo(name="SYNTHETIC_ONLY"),
        color=RawStreamInfo(encoding=RawPixelEncoding.MJPEG, width=5, height=4,
                            frame_index=13, timestamp_us=100_000,
                            payload_size_bytes=len(color)),
        depth=RawStreamInfo(encoding=RawPixelEncoding.Y16, width=3, height=2,
                            frame_index=9, timestamp_us=103_308,
                            payload_size_bytes=len(depth)),
        color_intrinsics=RawIntrinsics(width=5, height=4, fx=5., fy=5., cx=2., cy=2.),
        depth_intrinsics=RawIntrinsics(width=3, height=2, fx=3., fy=3., cx=1., cy=1.),
        color_distortion=zero_dist,
        depth_distortion=zero_dist,
        depth_to_color=RawDepthToColorExtrinsics(
            rotation=(1., 0., 0., 0., 1., 0., 0., 0., 1.),
            translation_mm=(-13.787516, -0.10409, -1.982521),
        ),
        depth_scale_m_per_unit=0.001, alignment_mode="disabled",
        frame_sync_requested=True,
    )
    return RawRgbdCapture(metadata=meta, color_mjpeg=color, depth_y16_le=depth)


def test_raw_commit_roundtrip_and_preserved_metadata(tmp_path):
    store = SessionStore(tmp_path)
    before = fixture_capture()
    path = store.commit_raw(before)
    assert path == tmp_path / "sessions/handheld-001/captures/test-raw-001"
    assert {p.name for p in path.iterdir()} == {
        "metadata.json", "manifest.json", "color.mjpg", "depth.y16", "COMMITTED"
    }
    assert (path / "COMMITTED").read_bytes() == b"1\n"
    assert (path / "color.mjpg").read_bytes() == before.color_mjpeg
    assert (path / "depth.y16").read_bytes() == before.depth_y16_le
    after = SessionStore(tmp_path).read_raw(path)
    assert after == before
    assert after.metadata.camera_pose is None
    assert after.metadata.alignment_mode == "disabled"
    assert after.metadata.observed_timestamp_delta_us == 3308
    assert after.metadata.depth_to_color.translation_mm[0] == -13.787516
    np.testing.assert_array_equal(after.depth_u16_copy(),
                                  np.array([[0, 1024, 65535], [42, 43, 44]], dtype=np.uint16))


def test_manifest_hashes_include_calibration_metadata(tmp_path):
    path = SessionStore(tmp_path).commit_raw(fixture_capture())
    manifest = json.loads((path / "manifest.json").read_text("utf-8"))
    assert manifest["manifest_schema_version"] == 1
    assert manifest["capture_schema_version"] == 2
    assert manifest["capture_id"] == "test-raw-001"
    assert set(manifest["files"]) == {"color.mjpg", "depth.y16", "metadata.json"}
    for file, info in manifest["files"].items():
        contents = (path / file).read_bytes()
        assert info["size_bytes"] == len(contents)
        assert info["sha256"] == hashlib.sha256(contents).hexdigest()


@pytest.mark.parametrize("name", ["color.mjpg", "depth.y16", "metadata.json"])
def test_detect_same_length_data_corruption(tmp_path, name):
    store = SessionStore(tmp_path)
    path = store.commit_raw(fixture_capture())
    original = bytearray((path / name).read_bytes())
    original[-1] ^= 1
    (path / name).write_bytes(original)
    with pytest.raises(ValueError, match="checksum mismatch"):
        store.read_raw(path)


@pytest.mark.parametrize("name", ["color.mjpg", "depth.y16", "metadata.json"])
def test_detect_truncated_payload(tmp_path, name):
    store = SessionStore(tmp_path)
    path = store.commit_raw(fixture_capture())
    (path / name).write_bytes((path / name).read_bytes()[:-1])
    with pytest.raises(ValueError, match="length mismatch"):
        store.read_raw(path)


def test_reject_manifest_bad_digest_or_unexpected_files(tmp_path):
    store = SessionStore(tmp_path)
    path = store.commit_raw(fixture_capture())
    manifest_file = path / "manifest.json"
    obj = json.loads(manifest_file.read_text("utf-8"))
    obj["files"]["depth.y16"]["sha256"] = "0" * 64
    manifest_file.write_text(json.dumps(obj), "utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        store.read_raw(path)
    obj["files"]["depth.y16"]["sha256"] = hashlib.sha256((path / "depth.y16").read_bytes()).hexdigest()
    obj["files"]["extra.exe"] = obj["files"]["depth.y16"]
    manifest_file.write_text(json.dumps(obj), "utf-8")
    with pytest.raises(ValueError, match="file list"):
        store.read_raw(path)


def test_reject_uncommitted_and_partial_capture(tmp_path):
    store = SessionStore(tmp_path)
    path = store.commit_raw(fixture_capture())
    (path / "COMMITTED").unlink()
    with pytest.raises(ValueError, match="incomplete"):
        store.read_raw(path)
    assert store.list_committed("handheld-001") == []
    partial = path.parent / ".random.partial"
    partial.mkdir()
    (partial / "COMMITTED").write_text("1\n", encoding="utf-8")
    assert store.list_committed("handheld-001") == []


def test_reject_duplicate_capture_without_overwrite(tmp_path):
    store = SessionStore(tmp_path)
    capture = fixture_capture()
    path = store.commit_raw(capture)
    first = (path / "color.mjpg").read_bytes()
    with pytest.raises(FileExistsError):
        store.commit_raw(capture)
    assert (path / "color.mjpg").read_bytes() == first
    assert store.read_raw(path) == capture


def test_write_failure_cleans_partial_and_never_commits(tmp_path, monkeypatch):
    store = SessionStore(tmp_path)
    save = store._write_bytes
    calls = []

    def failing_write(path, data):
        calls.append(path.name)
        if path.name == "depth.y16":
            raise OSError("synthetic write failure")
        return save(path, data)

    monkeypatch.setattr(store, "_write_bytes", failing_write)
    with pytest.raises(OSError, match="synthetic write failure"):
        store.commit_raw(fixture_capture())
    assert "depth.y16" in calls
    parent = tmp_path / "sessions/handheld-001/captures"
    assert list(parent.iterdir()) == []
    assert store.list_committed("handheld-001") == []


def test_reject_capture_outside_store_and_mismatched_path_identity(tmp_path):
    store = SessionStore(tmp_path / "root")
    path = store.commit_raw(fixture_capture())
    another = SessionStore(tmp_path / "other")
    with pytest.raises(ValueError, match="inside this SessionStore"):
        another.read_raw(path)
    renamed = path.with_name("another-capture-id")
    path.rename(renamed)
    with pytest.raises(ValueError, match="ID"):
        store.read_raw(renamed)


def test_reject_mismatched_metadata_even_with_updated_manifest(tmp_path):
    store = SessionStore(tmp_path)
    path = store.commit_raw(fixture_capture())
    meta_file = path / "metadata.json"
    metadata = json.loads(meta_file.read_text("utf-8"))
    metadata["specimen_id"] = "changed"  # Hashes alone aren't authentication.
    metadata["capture_id"] = "forged-capture-id"
    modified = json.dumps(metadata).encode("utf-8")
    meta_file.write_bytes(modified)
    manifest_file = path / "manifest.json"
    manifest = json.loads(manifest_file.read_text("utf-8"))
    manifest["files"]["metadata.json"] = {
        "size_bytes": len(modified), "sha256": hashlib.sha256(modified).hexdigest()
    }
    manifest_file.write_text(json.dumps(manifest), "utf-8")
    with pytest.raises(ValueError, match="metadata disagrees"):
        store.read_raw(path)


def test_v1_and_v2_coexist_and_version_dispatch(tmp_path):
    store = SessionStore(tmp_path)
    v1 = store.commit(SyntheticSource().capture(), "handheld-001", "object-A")
    expected_raw = fixture_capture()
    v2 = store.commit_raw(expected_raw)
    assert store.list_committed("handheld-001") == sorted([v1, v2])
    old = SessionStore(tmp_path).read(v1)
    assert old[0].schema_version == 1
    assert old[1].dtype == np.uint16
    assert SessionStore(tmp_path).read_capture(v1)[0] == old[0]
    raw = SessionStore(tmp_path).read_capture(v2)
    assert isinstance(raw, RawRgbdCapture) and raw == expected_raw


def test_extra_file_or_symlink_is_rejected(tmp_path):
    store = SessionStore(tmp_path)
    path = store.commit_raw(fixture_capture())
    (path / "rogue.txt").write_text("oops", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected"):
        store.read_raw(path)
    (path / "rogue.txt").unlink()
    # Symlinks aren't necessarily available without developer mode on Windows.
    try:
        (path / "color.mjpg").unlink()
        (path / "color.mjpg").symlink_to(tmp_path / "external.mjpg")
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks requires Windows privilege")
    with pytest.raises(ValueError, match="Invalid RAW file"):
        store.read_raw(path)


def test_large_unaligned_gemini_geometry_layout_roundtrip(tmp_path):
    """A 2 MB *synthetic* buffer, matching 1280x800 Y16 layout, not hardware."""
    original = fixture_capture()
    depth = np.full((800, 1280), 1250, dtype="<u2").tobytes()
    meta = original.metadata.model_copy(update={
        "color": original.metadata.color.model_copy(update={"width": 1920, "height": 1080}),
        "color_intrinsics": original.metadata.color_intrinsics.model_copy(update={"width": 1920, "height": 1080}),
        "depth": original.metadata.depth.model_copy(update={"width": 1280, "height": 800, "payload_size_bytes": len(depth)}),
        "depth_intrinsics": original.metadata.depth_intrinsics.model_copy(update={"width": 1280, "height": 800}),
    })
    capture = RawRgbdCapture(meta, original.color_mjpeg, depth)
    store = SessionStore(tmp_path)
    restored = store.read_raw(store.commit_raw(capture))
    assert restored.depth_y16_le == depth
    assert restored.metadata.color.width == 1920
    assert restored.metadata.depth.height == 800
    assert restored.depth_u16_copy()[400, 400] == 1250
