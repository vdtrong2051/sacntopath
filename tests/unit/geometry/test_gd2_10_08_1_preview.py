"""GD2-10.08.1 isolated preview transport and read-only store snapshot tests."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import struct

import numpy as np
import pytest

from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.replay import RawReplayService
from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter
from scantopath.modules.geometry.application.service import GeometryService
from scantopath.ui.shell.geometry_preview import (
    GeometryPreviewError,
    snapshot_capture,
    write_preview_ply,
)
from scantopath.modules.viewer3d.infrastructure.ply_header import inspect_ply
from scantopath.metadata.store import MetadataStore
from scantopath.storage.session_store import SessionStore
from scantopath.storage.numbered import NumberedStorageRegistry
from tests.support.raw_fixture import raw


def xyzrgb_view():
    packet = raw()
    metadata = packet.metadata
    image = np.full((metadata.color.height, metadata.color.width, 3),
                    (23, 120, 208), dtype=np.uint8)
    return GeometryService.process(
        depth_u16=packet.depth_u16_copy(), color_rgb=image,
        metadata=metadata, capture_id=metadata.capture_id)


def test_preview_binary_ply_is_color_subset_and_never_metric_certificate(tmp_path):
    view = xyzrgb_view()
    before_xyz = view.points_xyz_m.copy()
    out = tmp_path / "preview.ply"
    receipt = write_preview_ply(view, out)
    info = inspect_ply(out)
    assert info.ply_format == "binary_little_endian"
    assert info.has_rgb and info.vertex_count == view.colors_rgb.shape[0]
    assert receipt.xyz_points == view.points_xyz_m.shape[0]
    assert receipt.colored_points == view.colored_point_indices.size
    assert receipt.status == "PROVISIONAL_NOT_METRIC_VALIDATED"
    assert receipt.ply_sha256 == sha256(out.read_bytes()).hexdigest()
    assert receipt.capture_id == view.source_capture_id
    content = out.read_bytes()
    assert b"metric artifact" in content[:600]
    assert b"property uchar red\nproperty uchar green\nproperty uchar blue" in content[:600]
    body = content.split(b"end_header\n", 1)[1]
    assert len(body) == 15 * info.vertex_count  # float32 XYZ and uchar RGB
    x, y, z, r, g, b = struct.unpack_from('<fffBBB', body, 0)
    p = view.points_xyz_m[view.colored_point_indices[0]]
    np.testing.assert_allclose((x, y, z), p, rtol=2e-7, atol=1e-7)
    assert (r, g, b) == tuple(int(k) for k in view.colors_rgb[0])
    np.testing.assert_array_equal(view.points_xyz_m, before_xyz)


def test_invalid_preview_inputs_fail_closed(tmp_path):
    view = xyzrgb_view()
    with pytest.raises(GeometryPreviewError) as ex:
        write_preview_ply(replace(view, metric_validated=True), tmp_path / "bad.ply")
    assert ex.value.code == "PREVIEW_PROVENANCE_INVALID"
    with pytest.raises(GeometryPreviewError) as ex:
        write_preview_ply(replace(view, colored_point_indices=np.array([], dtype=np.int32),
                                  colors_rgb=np.empty((0, 3), dtype=np.uint8)), tmp_path / "empty.ply")
    assert ex.value.code == "PREVIEW_POINT_MAPPING_INVALID"
    with pytest.raises(GeometryPreviewError):
        write_preview_ply(view, tmp_path / "bad.txt")


@pytest.mark.parametrize('numbered', [False, True])
def test_snapshot_reads_real_registered_capture_without_touching_original(tmp_path, numbered):
    origin = tmp_path / "origin"
    origin.mkdir()
    with MetadataStore(origin) as store:
        store.create_project("p1", "Project")
        store.create_specimen("s1", "p1", "Specimen")
        store.create_scan_session("t1", "s1", "Scan")
    if numbered:
        NumberedStorageRegistry.migrate_database(origin)
        registry = NumberedStorageRegistry(origin)
        capture = raw(session="t1", specimen="s1", capture_id="c1")
        registry.reserve_capture("c1", "t1", "s1")
        directory = registry.write_reserved_capture(capture)
        registry.register_reserved_capture("c1")
    else:
        capture = raw(session="t1", specimen="s1", capture_id="c1")
        directory = SessionStore(origin).commit_raw(capture)
        with MetadataStore(origin) as store:
            store.register_capture(directory)
    before = {p.relative_to(origin).as_posix(): sha256(p.read_bytes()).hexdigest()
              for p in origin.rglob('*') if p.is_file()}
    context = CaptureContext(str(origin), 'p1', 's1', 't1', 'c1')
    result = snapshot_capture(context, tmp_path / "shadow")
    assert Path(result.store_root).resolve() != origin.resolve()
    assert RawReplayService(RawReaderAdapter()).load(result) == capture
    after = {p.relative_to(origin).as_posix(): sha256(p.read_bytes()).hexdigest()
             for p in origin.rglob('*') if p.is_file()}
    assert after == before


def test_missing_source_fails_without_creating_root(tmp_path):
    missing = tmp_path / "no-source"
    ctx = CaptureContext(str(missing), 'p1', 's1', 't1', 'c1')
    with pytest.raises(GeometryPreviewError) as error:
        snapshot_capture(ctx, tmp_path / 'snapshot')
    assert error.value.code == 'STORE_NOT_OPEN'
    assert not missing.exists()


def test_ui_bridge_button_is_not_enabled_without_capture_selection(monkeypatch):
    from PySide6.QtWidgets import QApplication, QPushButton
    from scantopath.ui.shell.main_window import ScanToPathMainWindow
    app = QApplication.instance() or QApplication([])
    window = ScanToPathMainWindow()
    try:
        button = window.findChild(QPushButton, 'captureGeometryPreviewButton')
        assert button is window.geometry_preview.button
        assert not button.isEnabled()
        assert window.viewer3d is None  # no eager VTK native process
    finally:
        window.close()
