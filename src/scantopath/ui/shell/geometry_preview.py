"""GD2-10.08.1: opt-in Capture -> verified replay -> temporary RGB PLY preview.

No VTK in Qt; no ProcessingRun/export; source RAW and SQLite are never opened
for writing. Temporary PLY is a display transport, NOT a trusted artifact.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile

import numpy as np
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot, Qt
from PySide6.QtWidgets import QLabel, QPushButton

from scantopath.application.contracts import WorkspaceId
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.geometry.application.service import SingleViewXYZRGB


MAX_PREVIEW_VERTICES = 1_500_000
MAX_PREVIEW_BYTES = 256 * 1024 * 1024
_VERTEX_DTYPE = np.dtype([
    ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
    ("red", "u1"), ("green", "u1"), ("blue", "u1"),
])


class GeometryPreviewError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PreviewReceipt:
    path: Path
    capture_id: str
    xyz_points: int
    colored_points: int
    ply_sha256: str
    frame: str = "depth_optical"
    units: str = "m"
    status: str = "PROVISIONAL_NOT_METRIC_VALIDATED"


def write_preview_ply(view: SingleViewXYZRGB, path: Path) -> PreviewReceipt:
    """Only actual RGB-assigned points go to a binary VTK-compatible temp PLY.

    Do not synthesize RGB for uncolored XYZ or label this PLY metric-certified.
    Selection/picking IDs in this PLY are NOT the source XYZ row indices.
    """
    if not isinstance(view, SingleViewXYZRGB):
        raise GeometryPreviewError("PREVIEW_INPUT_INVALID")
    if view.frame != "depth_optical" or view.units != "m" or view.metric_validated:
        raise GeometryPreviewError("PREVIEW_PROVENANCE_INVALID")
    xyz = view.points_xyz_m
    ix = view.colored_point_indices
    rgb = view.colors_rgb
    if (not isinstance(xyz, np.ndarray) or xyz.dtype != np.float64 or
            xyz.ndim != 2 or xyz.shape[1] != 3 or
            not isinstance(ix, np.ndarray) or ix.dtype != np.int32 or ix.ndim != 1 or
            not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8 or
            rgb.shape != (ix.size, 3) or
            not 1 <= ix.size <= min(xyz.shape[0], MAX_PREVIEW_VERTICES) or
            np.any(ix < 0) or np.any(ix >= xyz.shape[0]) or
            np.unique(ix).size != ix.size):
        raise GeometryPreviewError("PREVIEW_POINT_MAPPING_INVALID")
    selected = xyz[ix]
    if not np.isfinite(selected).all() or np.any(selected[:, 2] <= 0):
        raise GeometryPreviewError("PREVIEW_COORDINATES_INVALID")
    vertices = np.empty(ix.size, dtype=_VERTEX_DTYPE)
    for key, j in (("x", 0), ("y", 1), ("z", 2)):
        vertices[key] = selected[:, j]
    for key, j in (("red", 0), ("green", 1), ("blue", 2)):
        vertices[key] = rgb[:, j]
    if not all(np.isfinite(vertices[key]).all() for key in ("x", "y", "z")):
        raise GeometryPreviewError("PREVIEW_FLOAT32_OVERFLOW")
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        "comment ScanToPath GD2-10.08.1 temporary visual preview only\n"
        "comment not a validated metric artifact or a source point-index map\n"
        f"element vertex {ix.size}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "end_header\n"
    ).encode("ascii")
    if len(header) + vertices.nbytes > MAX_PREVIEW_BYTES:
        raise GeometryPreviewError("PREVIEW_SIZE_LIMIT")
    path = Path(path)
    if path.suffix.lower() != ".ply" or not path.parent.is_dir() or path.exists():
        raise GeometryPreviewError("PREVIEW_DESTINATION_INVALID")
    with path.open("xb") as stream:
        stream.write(header)
        stream.write(vertices.tobytes(order="C"))
    digest = sha256(path.read_bytes()).hexdigest()
    return PreviewReceipt(
        path=path, capture_id=view.source_capture_id,
        xyz_points=int(xyz.shape[0]), colored_points=int(ix.size),
        ply_sha256=digest,
    )


def snapshot_capture(context: CaptureContext, destination: Path) -> CaptureContext:
    """Snapshot SQLite using read-only source and copy ONLY chosen RAW v2 files.

    This is a best-effort source immutability boundary. The injected replay
    adapter authenticates the snapshot's RAW manifest before processing.
    """
    if not isinstance(context, CaptureContext) or not context.capture_id:
        raise GeometryPreviewError("CAPTURE_ID_REQUIRED")
    source = Path(context.store_root).absolute()
    if (not source.is_dir() or source.is_symlink() or
            source.resolve(strict=True) != source):
        raise GeometryPreviewError("STORE_NOT_OPEN")
    db_path = source / "metadata.sqlite3"
    if not db_path.is_file() or db_path.is_symlink():
        raise GeometryPreviewError("STORE_NOT_OPEN")
    destination = Path(destination)
    if destination.exists():
        raise GeometryPreviewError("SNAPSHOT_DESTINATION_EXISTS")
    destination.mkdir(parents=True)
    db_hash_before = sha256(db_path.read_bytes()).digest()
    conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        row = conn.execute(
            "SELECT relative_path, schema_version, session_id, specimen_id "
            "FROM captures WHERE capture_id=?", (context.capture_id,),
        ).fetchone()
        if (row is None or row[1:] != (2, context.session_id, context.specimen_id)):
            raise GeometryPreviewError("CAPTURE_CONTEXT_MISMATCH")
        relative = row[0]
        parts = relative.split("/") if isinstance(relative, str) else []
        if (not 1 <= len(parts) <= 8 or "\\" in relative or
                any(p in ("", ".", "..") for p in parts) or
                (len(parts) == 8 and (parts[0] != "01_PROJECTS" or parts[6] != "01_CAPTURES")) or
                (len(parts) == 4 and (parts[0] != "sessions" or parts[2] != "captures")) or
                len(parts) not in (4, 8)):
            raise GeometryPreviewError("RAW_PATH_UNSAFE")
        src_dir = source.joinpath(*parts)
        if (not src_dir.is_dir() or src_dir.is_symlink() or
                not src_dir.resolve(strict=True).is_relative_to(source)):
            raise GeometryPreviewError("RAW_PATH_UNSAFE")
        # Transactionally consistent SQLite snapshot: do not copy live DB bytes.
        target_db = sqlite3.connect(destination / "metadata.sqlite3")
        try:
            conn.backup(target_db)
        finally:
            target_db.close()
    finally:
        conn.close()
    dst_dir = destination.joinpath(*parts)
    dst_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("color.mjpg", "depth.y16", "metadata.json", "manifest.json", "COMMITTED"):
        source_file = src_dir / filename
        if not source_file.is_file() or source_file.is_symlink():
            raise GeometryPreviewError("RAW_MISSING")
        data = source_file.read_bytes()
        digest = sha256(data).digest()
        (dst_dir / filename).write_bytes(data)
        if (sha256(source_file.read_bytes()).digest() != digest or
                sha256((dst_dir / filename).read_bytes()).digest() != digest):
            raise GeometryPreviewError("RAW_CHANGED_DURING_SNAPSHOT")
    if sha256(db_path.read_bytes()).digest() != db_hash_before:
        raise GeometryPreviewError("SQLITE_CHANGED_DURING_SNAPSHOT")
    return replace(context, store_root=str(destination))


class GeometryPreviewWorker(QThread):
    ready = Signal(object, object, object)  # PreviewReceipt, TemporaryDirectory, CaptureContext
    failed = Signal(str)

    def __init__(self, context: CaptureContext, parent=None):
        super().__init__(parent)
        self.context = context

    def run(self) -> None:
        scratch = None
        try:
            scratch = tempfile.TemporaryDirectory(prefix="stp-gd2-10-08-")
            root = Path(scratch.name)
            snap_context = snapshot_capture(self.context, root / "snapshot")
            # Application composition in worker thread, never in Qt GUI thread.
            from scantopath.modules.capture.application.replay import RawReplayService
            from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter
            from scantopath.modules.capture.application.decoding import RgbdDecoder
            from scantopath.modules.capture.infrastructure.jpeg_codec import PillowMjpegDecoder
            from scantopath.modules.geometry.application.replay_geometry import ReplayGeometryService
            pipeline = ReplayGeometryService(
                RawReplayService(RawReaderAdapter()), RgbdDecoder(PillowMjpegDecoder()),
            )
            result = pipeline.process(snap_context)
            receipt = write_preview_ply(
                result, root / f"capture_{self.context.capture_id}_preview.ply",
            )
            self.ready.emit(receipt, scratch, self.context)
            scratch = None  # The receiver now owns its lifetime.
        except Exception as exc:
            code = getattr(exc, "code", "PREVIEW_PIPELINE_FAILED")
            self.failed.emit(code if type(code) is str and re.fullmatch(r"[A-Z0-9_]{3,60}", code) else "PREVIEW_PIPELINE_FAILED")
        finally:
            if scratch is not None:
                scratch.cleanup()


class GeometryPreviewBridge(QObject):
    """One opt-in button; Qt owns no native renderer and no decoded RAW arrays."""

    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self._worker: GeometryPreviewWorker | None = None
        self._closing = False
        self._scratch: list[tempfile.TemporaryDirectory] = []
        self._receipt: PreviewReceipt | None = None
        self._sensor_view_token = None
        self._viewer_label: QLabel | None = None
        panel = host.capture_preview.panel
        self.button = QPushButton("Xem XYZRGB 3D", panel)
        self.button.setObjectName("captureGeometryPreviewButton")
        self.button.setToolTip("Tạo bản xem tạm có RGB từ RAW đã lưu; chưa kiểm định đo lường")
        header = panel.layout().itemAt(0).layout()
        header.insertWidget(header.count() - 1, self.button)
        self.button.clicked.connect(self.open_selected)
        host.project_explorer.selection_changed.connect(self._refresh)
        host.project_loader.busy_changed.connect(self._refresh)
        host.project_writer.busy_changed.connect(self._refresh)
        # The existing ReplayThread does not publish a finished/busy signal.
        # A cheap poll restores the button when auto-Replay finishes.
        self._availability_timer = QTimer(self)
        self._availability_timer.setInterval(200)
        self._availability_timer.timeout.connect(self._refresh)
        self._availability_timer.start()
        self._refresh()

    @Slot()
    def _refresh(self, *_args) -> None:
        context = self.host.capture_preview.context
        ok = (not self._closing and self._worker is None and context is not None and
              self.host.project_explorer.store_root == context.store_root and
              self.host.active_workspace is WorkspaceId.CAPTURE and
              not self.host.capture_preview.busy and
              not self.host.project_loader.busy and
              not self.host.project_writer.busy and
              not self.host.capture_checker.busy)
        self.button.setEnabled(bool(ok))

    @Slot()
    def open_selected(self) -> bool:
        self._refresh()
        if not self.button.isEnabled():
            return False
        context = self.host.capture_preview.context
        if context is None or context.capture_id is None:
            return False
        self._worker = GeometryPreviewWorker(context, self)
        self._worker.ready.connect(self._ready)
        self._worker.failed.connect(self._failed)
        self._worker.finished.connect(self._finished)
        self._worker.finished.connect(self._worker.deleteLater)
        self.button.setEnabled(False)
        self.host.capture_preview.panel.state_label.setText(
            "Đang tạo XYZRGB từ RAW đã lưu trên bản sao tạm…"
        )
        self._worker.start()
        return True

    @Slot(object, object, object)
    def _ready(self, receipt: PreviewReceipt, scratch, context: CaptureContext) -> None:
        if (self._closing or context is None or
                self.host.capture_preview.context != context or
                self.host.project_explorer.store_root != context.store_root):
            scratch.cleanup()
            return
        self._scratch.append(scratch)  # Keep PLY alive throughout render-host use.
        self._receipt = receipt
        self._sensor_view_token = None
        self.host._navigate(WorkspaceId.INSPECT3D)
        viewer = self.host.viewer3d
        if viewer is None:
            return
        self._ensure_viewer_label(viewer)
        self._update_viewer_label()
        if not viewer.load_ply(receipt.path):
            self._viewer_label.setText("Không mở được XYZRGB; dữ liệu RAW vẫn nguyên vẹn.")

    def _ensure_viewer_label(self, viewer) -> None:
        if self._viewer_label is not None:
            return
        label = QLabel("", viewer.page)
        label.setObjectName("gd2GeometryPreviewInfo")
        label.setWordWrap(True)
        label.setTextFormat(Qt.PlainText)
        viewer.page.layout().insertWidget(1, label)
        self._viewer_label = label
        # Scene inspection fires whenever an externally loaded scene replaces ours.
        if hasattr(viewer, "scene_inspection"):
            viewer.scene_inspection.connect(self._update_viewer_label)
        self._info_timer = QTimer(self)
        self._info_timer.setInterval(250)
        self._info_timer.timeout.connect(self._update_viewer_label)
        self._info_timer.start()

    @Slot()
    def _update_viewer_label(self, *_args) -> None:
        if self._viewer_label is None or self.host.viewer3d is None:
            return
        viewer = self.host.viewer3d
        receipt = self._receipt
        if receipt is None:
            self._viewer_label.setText("PLY ngoài: tọa độ/đơn vị chưa xác minh.")
            return
        current = getattr(viewer, "_current_source", None)
        pending = getattr(viewer, "_pending_source", None)
        if current == receipt.path and getattr(viewer, "_live_phase", None) == "ready":
            descriptor = getattr(viewer, "_descriptor", None)
            if getattr(descriptor, "source_sha256", None) == receipt.ply_sha256:
                token = (receipt.path, receipt.ply_sha256,
                         getattr(viewer, "_expected_scene_revision", None))
                if token != self._sensor_view_token:
                    # Set token first: navigate() may synchronously emit inspector signals.
                    self._sensor_view_token = token
                    if not viewer.navigate("sensor_view"):
                        self._sensor_view_token = None
                    else:
                        # Display-only default for Capture geometry, not for PLY/OBJ.
                        # Toggle through existing UI signal so host & toolbar agree.
                        tools = getattr(viewer, "tools", None)
                        grid = getattr(tools, "grid_button", None)
                        if grid is not None and grid.isChecked():
                            grid.setChecked(False)
            self._viewer_label.setText(
                f"RAW Capture {receipt.capture_id} | depth_optical (m) | "
                f"XYZ={receipt.xyz_points:,} | RGB={receipt.colored_points:,} | "
                "góc nhìn Depth auto-fit | chỉ hiện điểm có màu | "
                "PROVISIONAL_NOT_METRIC_VALIDATED"
            )
        elif pending == receipt.path:
            self._viewer_label.setText("Đang mở XYZRGB tạm trong VTK Render Host…")
        else:
            self._viewer_label.setText(
                "Không phải preview RAW đang chọn: tệp Viewer có đơn vị/hệ tọa độ chưa xác minh."
            )

    @Slot(str)
    def _failed(self, code: str) -> None:
        if not self._closing:
            self.host.capture_preview.panel.state_label.setText(
                "Không thể tạo preview XYZRGB (" + code + "). RAW không bị sửa."
            )

    @Slot()
    def _finished(self) -> None:
        self._worker = None
        if not self._closing:
            self._refresh()
        else:
            QTimer.singleShot(0, self.host.close)

    def begin_shutdown(self) -> bool:
        self._closing = True
        self.button.setEnabled(False)
        return self._worker is None or not self._worker.isRunning()

    def dispose(self) -> None:
        self._availability_timer.stop()
        if getattr(self, "_info_timer", None) is not None:
            self._info_timer.stop()
        for item in self._scratch:
            item.cleanup()
        self._scratch.clear()
