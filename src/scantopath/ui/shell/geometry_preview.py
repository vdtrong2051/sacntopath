"""GD2-10.08.1: opt-in Capture -> verified replay -> temporary RGB PLY preview.

No VTK in Qt; no ProcessingRun/export; source RAW and SQLite are never opened
for writing. Temporary PLY is a display transport, NOT a trusted artifact.
"""
from __future__ import annotations

from pathlib import Path
import re
import tempfile

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot, Qt
from PySide6.QtWidgets import QLabel, QPushButton

from scantopath.application.contracts import WorkspaceId
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.geometry.application.service import SingleViewXYZRGB
from scantopath.application.contracts.preview import GeometryPreviewError, PreviewReceipt
# Compatibility aliases for existing GD2-10 public test imports. No I/O in this module.
from scantopath.bootstrap.geometry_preview import (
    MAX_PREVIEW_BYTES, MAX_PREVIEW_VERTICES, snapshot_capture, write_preview_ply,
)


class GeometryPreviewWorker(QThread):
    ready = Signal(object, object, object, object)  # receipt, scratch, context, SingleViewXYZRGB
    failed = Signal(str)

    def __init__(self, context: CaptureContext, parent=None):
        super().__init__(parent)
        self.context = context

    def run(self) -> None:
        scratch = None
        try:
            scratch = tempfile.TemporaryDirectory(prefix="stp-gd2-10-08-")
            root = Path(scratch.name)
            from scantopath.bootstrap.geometry_preview import build_preview_use_case
            receipt, result = build_preview_use_case().process(self.context, root)
            self.ready.emit(receipt, scratch, self.context, result)
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
        self._workflow_revision_at_request: int | None = None
        self._sensor_view_token = None
        self._viewer_label: QLabel | None = None
        self._measurement_ui = None  # lazy, after Viewer initialization
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
        # A different Capture or Store invalidates A/B even within Inspect3D.
        if (self._measurement_ui is not None and
                self._receipt is not None and
                (context is None or context.capture_id != self._receipt.capture_id)):
            self._measurement_ui.unbind()
        self.button.setEnabled(bool(ok))

    @Slot()
    def open_selected(self) -> bool:
        self._refresh()
        if not self.button.isEnabled():
            return False
        context = self.host.capture_preview.context
        if context is None or context.capture_id is None:
            return False
        workflow = getattr(self.host, "workflow_context", None)
        if workflow is not None and workflow.current.actionable_capture_id != context.capture_id:
            return False
        self._workflow_revision_at_request = workflow.revision if workflow is not None else None
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

    @Slot(object, object, object, object)
    def _ready(self, receipt: PreviewReceipt, scratch, context: CaptureContext, view: SingleViewXYZRGB) -> None:
        workflow = getattr(self.host, "workflow_context", None)
        current_revision = workflow.revision if workflow is not None else None
        if (self._workflow_revision_at_request is not None and
                current_revision != self._workflow_revision_at_request):
            scratch.cleanup()
            return
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
            if self._measurement_ui is not None:
                self._measurement_ui.unbind()
            return
        # Keep the original float64 XYZ and RGB->XYZ row map until scene switch.
        # VTK's PLY point IDs are NOT the ValidGeometry row indices.
        if not hasattr(viewer, 'scene_inspection'):
            return  # Qt offscreen viewer cannot perform source-backed native picking.
        if self._measurement_ui is None:
            from .geometry_measurement import GeometryMeasurementPanel
            self._measurement_ui = GeometryMeasurementPanel(viewer, self)
        self._measurement_ui.bind_preview(receipt, view)

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
            selected = self.host.capture_preview.context
            if (selected is None or selected.store_root != self.host.project_explorer.store_root
                    or selected.capture_id != receipt.capture_id):
                self._viewer_label.setText(
                    f"RAW Preview {receipt.capture_id} đang hiển thị, nhưng không phải Capture hiện hành. "
                    "Không sử dụng Preview này để đo; hãy chọn Capture và mở Preview mới."
                )
                return
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
        if self._measurement_ui is not None:
            self._measurement_ui.dispose()
        self._availability_timer.stop()
        if getattr(self, "_info_timer", None) is not None:
            self._info_timer.stop()
        for item in self._scratch:
            item.cleanup()
        self._scratch.clear()
