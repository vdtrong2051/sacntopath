"""FT-03: bounded asynchronous Geometry worker, independent of camera and VTK.

QThread executes ONE geometry computation at a time. Incoming/outgoing slots are
latest-wins, with generation/frame-index fencing and cooperative shutdown.
No file, SDK, SQLite, RAW, VTK, or shared-memory I/O is performed here.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Callable
from math import isfinite
from statistics import mean
from threading import Condition
from time import monotonic

from PySide6.QtCore import QThread, Signal

from scantopath.modules.capture.application.live_stream import LiveRgbdFrame
from scantopath.modules.geometry.application.live_object_isolation import isolate_object_depth
from scantopath.modules.geometry.application.live_charuco_isolation import isolate_charuco_object
from scantopath.modules.geometry.application.live_geometry import (
    LiveCloudFrame, LiveGeometryError, LiveGeometryService,
)


class LiveGeometryThread(QThread):
    """One pending frame + one pending result; events never queue entire clouds."""

    result_available = Signal()  # wake-up only, retrieve with take_latest_result()

    def __init__(self, *, processor: Callable | None = None, parent=None) -> None:
        super().__init__(parent)
        self._standard_processor = processor is None
        self._processor = processor or LiveGeometryService.process
        self._denoise_mode = "standard" if processor is None else "off"
        self._scope_mode = "scene"  # FT-03/FT-05 compatibility; UI selects object
        self._scope_revision = 0
        self._last_isolation_status = "SCENE"
        self._reference_mode = "depth"  # FT-05.7 compatibility, Qt opts into ChArUco
        self._last_board_corners = 0
        self._last_board_reprojection_px = None
        self._last_board_support_fraction = None
        if not callable(self._processor):
            raise TypeError("processor must be callable")
        self._cv = Condition()
        self._generation = 0
        self._pending: tuple[int, int, LiveRgbdFrame, tuple[int, int, int, int] | None] | None = None
        self._latest: tuple[int, int, LiveCloudFrame | None, str | None] | None = None
        self._notice_pending = False
        self._closing = False
        self._last_submitted = -1
        self._last_output = -1
        self._since = monotonic()
        self._durations_ms: deque[float] = deque(maxlen=128)
        self._counts = {
            "frames_received": 0,
            "frames_rejected_order": 0,
            "frames_dropped_input": 0,
            "frames_processed": 0,
            "frames_published": 0,
            "frames_dropped_output": 0,
            "frames_rejected_stale": 0,
            "geometry_errors": 0,
        }
        self._last_error_code: str | None = None
        self._last_point_count = 0

    def change_generation(self, generation: int) -> None:
        if type(generation) is not int or generation <= 0:
            raise ValueError("generation must be a positive integer")
        with self._cv:
            if generation <= self._generation:
                raise ValueError("generation must strictly increase on active worker")
            if self._pending is not None:
                self._counts["frames_dropped_input"] += 1
            if self._latest is not None:
                self._counts["frames_dropped_output"] += 1
            self._generation = generation
            self._pending = None
            self._latest = None
            self._notice_pending = False
            self._last_submitted = -1
            self._last_output = -1
            self._last_error_code = None
            self._last_board_corners = 0
            self._last_board_reprojection_px = None
            self._last_board_support_fraction = None
            self._cv.notify_all()

    def submit(self, generation: int, frame: LiveRgbdFrame,
               *, depth_roi: tuple[int, int, int, int] | None = None) -> bool:
        if not isinstance(frame, LiveRgbdFrame):
            raise TypeError("expected owned LiveRgbdFrame")
        if depth_roi is not None and (not isinstance(depth_roi, tuple)
                or len(depth_roi) != 4 or any(type(v) is not int for v in depth_roi)):
            raise ValueError("depth_roi must be native grid integer rectangle")
        index = frame.source.depth_frame_index
        with self._cv:
            if self._closing or generation != self._generation or generation <= 0:
                return False
            if index <= self._last_submitted:
                self._counts["frames_rejected_order"] += 1
                return False
            self._counts["frames_received"] += 1
            if self._pending is not None:
                self._counts["frames_dropped_input"] += 1
            self._last_submitted = index
            self._pending = (generation, index, frame, depth_roi)
            self._cv.notify()
            return True

    def set_denoise_mode(self, mode: str) -> None:
        if type(mode) is not str or mode not in ("standard", "off"):
            raise ValueError("DENOISE_MODE_INVALID")
        with self._cv:
            if self._closing:
                return
            self._denoise_mode = mode

    def set_scope_mode(self, mode: str) -> None:
        if type(mode) is not str or mode not in ("scene", "object"):
            raise ValueError("SCOPE_MODE_INVALID")
        with self._cv:
            if self._closing or mode == self._scope_mode:
                return
            self._scope_mode = mode
            self._scope_revision += 1
            if self._pending is not None:
                self._counts["frames_dropped_input"] += 1
            if self._latest is not None:
                self._counts["frames_dropped_output"] += 1
            self._pending = self._latest = None
            self._notice_pending = False
            self._last_isolation_status = "PENDING" if mode == "object" else "SCENE"
            self._cv.notify_all()

    def set_reference_mode(self, mode: str) -> None:
        if type(mode) is not str or mode not in ("depth", "charuco"):
            raise ValueError("REFERENCE_MODE_INVALID")
        with self._cv:
            if self._closing or mode == self._reference_mode:
                return
            self._reference_mode = mode
            self._scope_revision += 1
            if self._pending is not None:
                self._counts["frames_dropped_input"] += 1
            if self._latest is not None:
                self._counts["frames_dropped_output"] += 1
            self._pending = self._latest = None
            self._notice_pending = False
            self._last_isolation_status = "PENDING"
            self._last_board_corners = 0
            self._last_board_reprojection_px = None
            self._last_board_support_fraction = None
            self._cv.notify_all()

    def request_stop(self) -> None:
        """Nonblocking; inflight calculation may complete but cannot publish."""
        with self._cv:
            self._closing = True
            self._pending = None
            self._latest = None
            self._notice_pending = False
            self._cv.notify_all()

    def take_latest_result(self) -> tuple[int, int, LiveCloudFrame | None, str | None] | None:
        with self._cv:
            value = self._latest
            self._latest = None
            self._notice_pending = False
            return value

    def statistics(self) -> dict[str, int | float | str | None]:
        """Thread-safe aggregate; no camera timestamp used as a wall clock."""
        with self._cv:
            elapsed = max(monotonic() - self._since, 1e-9)
            samples = sorted(self._durations_ms)
            p95 = samples[min(len(samples)-1, int((len(samples)-1)*0.95))] if samples else None
            return {
                **self._counts,
                "camera_generation": self._generation,
                "denoise_mode": self._denoise_mode,
                "scope_mode": self._scope_mode,
                "reference_mode": self._reference_mode,
                "board_corners": self._last_board_corners,
                "board_reprojection_px": self._last_board_reprojection_px,
                "board_support_fraction": self._last_board_support_fraction,
                "last_isolation_status": self._last_isolation_status,
                "pending_input": int(self._pending is not None),
                "pending_output": int(self._latest is not None),
                "worker_closing": int(self._closing),
                "geometry_fps_since_start": self._counts["frames_published"] / elapsed,
                "processing_mean_ms_last128": mean(samples) if samples else None,
                "processing_p95_ms_last128": p95,
                "last_point_count": self._last_point_count,
                "last_error_code": self._last_error_code,
            }

    def run(self) -> None:
        while True:
            with self._cv:
                while self._pending is None and not self._closing:
                    self._cv.wait()
                if self._closing:
                    return
                generation, index, frame, roi = self._pending
                denoise_mode = self._denoise_mode
                scope_mode = self._scope_mode
                reference_mode = self._reference_mode
                scope_revision = self._scope_revision
                self._pending = None
            before = monotonic()
            cloud: LiveCloudFrame | None = None
            error: str | None = None
            isolation_status = "SCENE"
            board_metrics = (0, None, None)
            try:
                kw = {"camera_generation": generation, "depth_roi": roi}
                if scope_mode == "object" and self._standard_processor:
                    calibration = frame.source.calibration
                    if calibration is None:
                        raise LiveGeometryError("LIVE_CALIBRATION_MISSING", "No calibration")
                    if reference_mode == "charuco":
                        isolated = isolate_charuco_object(
                            frame.color_rgb, frame.depth_u16, calibration, depth_roi=roi)
                    else:
                        isolated = isolate_object_depth(
                            frame.depth_u16, frame.source.depth_scale_m_per_unit,
                            calibration.depth_intrinsics, depth_roi=roi)
                    isolation_status = isolated.status
                    if reference_mode == "charuco":
                        board_metrics = (isolated.corner_count, isolated.reprojection_px,
                                         isolated.support_fraction)
                    if not isolated.usable:
                        raise LiveGeometryError(isolated.status, isolated.message)
                    kw["object_mask"] = isolated.object_mask
                if self._standard_processor:
                    kw["denoise_mode"] = denoise_mode
                cloud = self._processor(frame, **kw)
                if (not isinstance(cloud, LiveCloudFrame)
                        or cloud.camera_generation != generation
                        or cloud.depth_frame_index != index):
                    cloud = None
                    error = "GEOMETRY_RESULT_INVALID"
            except LiveGeometryError as exc:
                error = exc.code
            except Exception:
                # Do not expose SDK, raw paths or non-stable exception text to Qt.
                error = "GEOMETRY_UNEXPECTED_ERROR"
            duration_ms = (monotonic() - before) * 1000.0
            if not isfinite(duration_ms):
                duration_ms = 0.0
            notify = False
            with self._cv:
                self._counts["frames_processed"] += 1
                self._durations_ms.append(duration_ms)
                if (self._closing or generation != self._generation or
                        scope_revision != self._scope_revision or index <= self._last_output):
                    self._counts["frames_rejected_stale"] += 1
                    continue
                self._last_output = index
                self._last_isolation_status = isolation_status if error is None else (
                    error if error.startswith(("ISOLATION_", "CHARUCO_")) else "ERROR")
                self._last_board_corners, self._last_board_reprojection_px, (
                    self._last_board_support_fraction) = board_metrics
                if self._latest is not None:
                    self._counts["frames_dropped_output"] += 1
                if error is not None:
                    self._counts["geometry_errors"] += 1
                    self._last_error_code = error
                    self._last_point_count = 0
                else:
                    self._counts["frames_published"] += 1
                    self._last_error_code = None
                    self._last_point_count = int(cloud.statistics.output_points)
                self._latest = (generation, index, cloud, error)
                if not self._notice_pending:
                    self._notice_pending = True
                    notify = True
            if notify:
                self.result_available.emit()
