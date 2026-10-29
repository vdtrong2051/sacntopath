
"""Explicit Gemini 2 live-stream probe. No RAW/SQLite writes or Qt windows.

Example:
    python scripts/gd2_09_05_live_probe.py --seconds 15
"""
from __future__ import annotations

import argparse
import time

from PySide6.QtCore import QCoreApplication, QTimer

from scantopath.modules.capture.application.live_stream import (
    LiveCaptureService,
)
from scantopath.modules.capture.infrastructure.native_camera import (
    Gemini2NativeCameraAdapter,
)
from scantopath.modules.capture.infrastructure.jpeg_codec import (
    PillowMjpegDecoder,
)
from scantopath.modules.capture.presentation.live_worker import (
    LiveStreamWorker,
)


def _service_factory() -> LiveCaptureService:
    return LiveCaptureService(
        Gemini2NativeCameraAdapter(),
        PillowMjpegDecoder(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="GD2-09.05 Gemini 2 live probe"
    )
    parser.add_argument(
        "--seconds",
        type=int,
        default=15,
    )
    args = parser.parse_args()

    if not 1 <= args.seconds <= 120:
        parser.error("--seconds must be 1..120")

    app = (
        QCoreApplication.instance()
        or QCoreApplication([])
    )

    worker = LiveStreamWorker(
        service_factory=_service_factory
    )

    errors: list[str] = []
    seen = 0
    last = None
    opened = False

    start = time.monotonic()

    def on_opened() -> None:
        nonlocal opened
        opened = True
        print(
            "camera.opened=true",
            flush=True,
        )

    def on_error(code: str) -> None:
        errors.append(code)
        print(
            f"camera.error={code}",
            flush=True,
        )

    def poll() -> None:
        nonlocal seen, last

        frame = worker.take_latest()

        if frame is not None:
            seen += 1
            last = frame

        if time.monotonic() - start >= args.seconds:
            worker.request_stop()

    timer = QTimer()
    timer.setInterval(60)
    timer.timeout.connect(poll)

    worker.camera_opened.connect(on_opened)
    worker.failed.connect(on_error)
    worker.finished.connect(app.quit)

    # Explicit entrypoint. Nothing opens at module import.
    timer.start()
    worker.start()

    app.exec()

    timer.stop()
    poll()

    # The finished signal has already fired.
    worker.wait()

    published, dropped = worker.stats()
    elapsed = max(
        time.monotonic() - start,
        0.001,
    )

    print(f"camera.opened={str(opened).lower()}")
    print(f"preview.frames_published={published}")
    print(f"preview.frames_consumed={seen}")
    print(f"preview.frames_dropped={dropped}")
    print(f"probe.elapsed_seconds={elapsed:.2f}")
    print(f"source.observed_fps={published / elapsed:.2f}")
    print("capture.saved=false")

    if last is not None:
        source = last.source

        print(f"device.name={source.device_name}")
        print(f"device.firmware={source.firmware}")

        print(
            f"rgb.size="
            f"{source.color_width}x{source.color_height}"
        )
        print(
            f"depth.size="
            f"{source.depth_width}x{source.depth_height}"
        )
        print(
            "depth.scale_m_per_unit="
            f"{source.depth_scale_m_per_unit:g}"
        )

        print(
            "timing.last_delta_us="
            f"{abs(source.color_timestamp_us - source.depth_timestamp_us)}"
        )
        print(
            "buffers.owned="
            f"{last.color_rgb.flags.owndata and last.depth_u16.flags.owndata}"
        )

    ok = opened and seen > 0 and not errors

    print(
        "GD2_09_05_DEVICE_PROBE="
        f"{'PASS' if ok else 'FAIL'}"
    )

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
