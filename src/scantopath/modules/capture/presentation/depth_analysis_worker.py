"""GD2-09.07.2: one-slot Depth analyzer; never blocks the Qt event loop.

Only the immutable owned frame is shared between GUI and this worker.
Generation-tagged results are rejected when the live camera is reopened.
"""
from __future__ import annotations

from threading import Condition

from PySide6.QtCore import QThread, Signal

from scantopath.modules.capture.application.bbox_tracking import DepthBboxTracker
from scantopath.modules.capture.application.live_stream import LiveRgbdFrame


class DepthAnalysisThread(QThread):
    analyzed = Signal(int, int, object)  # generation, frame index, TrackingResult|None

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cv = Condition()
        self._pending: tuple[int, int, LiveRgbdFrame] | None = None
        self._generation = 0
        self._closing = False

    def change_generation(self, generation: int) -> None:
        with self._cv:
            self._generation = generation
            self._pending = None
            self._cv.notify_all()

    def submit(self, generation: int, frame: LiveRgbdFrame) -> bool:
        if not isinstance(frame, LiveRgbdFrame):
            raise TypeError("expected live frame")
        with self._cv:
            if self._closing or generation != self._generation:
                return False
            self._pending = (generation, frame.source.depth_frame_index, frame)
            self._cv.notify()
        return True

    def request_stop(self) -> None:
        with self._cv:
            self._closing = True
            self._pending = None
            self._cv.notify_all()

    def run(self) -> None:
        tracker = DepthBboxTracker()
        last_generation: int | None = None
        while True:
            with self._cv:
                while self._pending is None and not self._closing:
                    self._cv.wait()
                if self._closing:
                    return
                generation, frame_index, frame = self._pending
                self._pending = None
            if generation != last_generation:
                tracker.reset()
                last_generation = generation
            try:
                result = tracker.update(frame.depth_u16,
                                        frame.source.depth_scale_m_per_unit)
            except (ValueError, TypeError):
                result = None
            # Never publish results after a source switch or shutdown.
            with self._cv:
                if self._closing or generation != self._generation:
                    continue
            self.analyzed.emit(generation, frame_index, result)
