
"""GD2-09.04: offline Replay + Decode in a dedicated QThread.

Presentation receives application services through dependency injection.
No infrastructure, SQLite, camera SDK or Qt widget access in run().
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.replay import (
    RawReplayError,
    RawReplayService,
)
from scantopath.modules.capture.application.decoding import (
    RgbdDecodeError,
    RgbdDecoder,
)

from .preview_widget import depth_display_u8


ReplayServiceFactory = Callable[
    [],
    tuple[RawReplayService, RgbdDecoder],
]


class ReplayThread(QThread):
    """Worker for explicitly requested offline Capture replay."""

    loaded = Signal(int, object, object)
    failed = Signal(int, str)

    def __init__(
        self,
        context: CaptureContext,
        request_id: int,
        *,
        service_factory: ReplayServiceFactory,
        parent=None,
    ) -> None:
        super().__init__(parent)

        if not callable(service_factory):
            raise TypeError("service_factory must be callable")

        self.context = context
        self.request_id = request_id
        self._service_factory = service_factory

    def run(self) -> None:
        try:
            # Service construction happens inside the worker thread.
            # The presentation module does not import infrastructure.
            replay_service, decoder = self._service_factory()

            packet = replay_service.load(self.context)
            frame = decoder.decode(packet)

            gray = depth_display_u8(frame.depth_u16)

            # Deliver plain Python/NumPy data to the GUI thread.
            # QPixmap/QImage creation belongs to CapturePreviewWidget.
            self.loaded.emit(
                self.request_id,
                frame,
                gray,
            )

        except (RawReplayError, RgbdDecodeError) as exc:
            self.failed.emit(
                self.request_id,
                exc.code,
            )

        except Exception:
            # Do not expose internal paths, SQLite details or payloads.
            self.failed.emit(
                self.request_id,
                "REPLAY_UNEXPECTED_ERROR",
            )
