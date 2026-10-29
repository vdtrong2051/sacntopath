"""GD2-09.06: operator-triggered real Gemini 2 start/stop/reopen probe.

Does not persist RAW, open the desktop shell, create a project, or retry errors
unconditionally. This probe must run from the repository root with SDK DLLs
configured, OrbbecViewer closed, and an attached Gemini 2.
"""
from __future__ import annotations

import argparse
import sys
import time

from PySide6.QtCore import QCoreApplication, QTimer

from scantopath.modules.capture.application.live_stream import LiveCaptureService
from scantopath.modules.capture.domain.models import CameraState
from scantopath.modules.capture.infrastructure.native_camera import Gemini2NativeCameraAdapter
from scantopath.modules.capture.infrastructure.jpeg_codec import PillowMjpegDecoder
from scantopath.modules.capture.presentation.live_controller import LiveCameraController
from scantopath.modules.capture.presentation.live_worker import LiveStreamWorker


def worker_factory() -> LiveStreamWorker:
    return LiveStreamWorker(
        service_factory=lambda: LiveCaptureService(
            Gemini2NativeCameraAdapter(), PillowMjpegDecoder()
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--seconds", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.cycles <= 10 or not 1 <= args.seconds <= 30:
        parser.error("cycles: 1..10; seconds per cycle: 1..30")

    app = QCoreApplication.instance() or QCoreApplication([])
    ctl = LiveCameraController(worker_factory=worker_factory)
    state_log = []
    errors = []
    cycles_done = 0
    consumed = 0
    per_cycle_frames = 0
    streaming_since = None
    shutdown_requested = False
    ok = True

    def on_state(state: CameraState):
        nonlocal streaming_since
        state_log.append(state.value)
        print(f"camera.state={state.value}", flush=True)
        if state is CameraState.STREAMING:
            streaming_since = time.monotonic()

    def on_failure(code):
        errors.append(code)
        print(f"camera.error={code}", flush=True)

    def tick():
        nonlocal consumed, per_cycle_frames, cycles_done, ok, shutdown_requested
        frame = ctl.take_latest()
        if frame is not None:
            consumed += 1
            per_cycle_frames += 1
        if ctl.state is CameraState.STREAMING and streaming_since is not None:
            if time.monotonic() - streaming_since >= args.seconds:
                ctl.stop()
        elif ctl.safe_to_dispose and ctl.state is CameraState.CLOSED and not shutdown_requested:
            cycles_done += 1
            print(f"cycle.{cycles_done}.frames_consumed={per_cycle_frames}", flush=True)
            if per_cycle_frames < 1:
                ok = False
            per_cycle_frames = 0
            if cycles_done == args.cycles or not ok:
                shutdown_requested = True
                ctl.request_shutdown()
            elif not ctl.start():
                ok = False
                shutdown_requested = True
                ctl.request_shutdown()
        elif ctl.safe_to_dispose and ctl.state is CameraState.FAILED and not shutdown_requested:
            ok = False
            shutdown_requested = True
            ctl.request_shutdown()

    def safe_quit():
        # Schedule the quit so synchronous start failures before exec() are safe.
        QTimer.singleShot(0, app.quit)

    ctl.state_changed.connect(on_state)
    ctl.failure.connect(on_failure)
    ctl.shutdown_ready.connect(safe_quit)
    timer = QTimer()
    timer.setInterval(40)
    timer.timeout.connect(tick)
    timer.start()
    if not ctl.start():
        ok = False
        ctl.request_shutdown()
    app.exec()
    timer.stop()
    success = ok and not errors and cycles_done == args.cycles and ctl.safe_to_dispose
    print(f"cycles.completed={cycles_done}/{args.cycles}")
    print(f"preview.frames_consumed={consumed}")
    print(f"camera.final_state={ctl.state.value}")
    print(f"camera.worker_reaped={ctl.safe_to_dispose}")
    print("capture.saved=false")
    print("GD2_09_06_LIFECYCLE_PROBE=" + ("PASS" if success else "FAIL"))
    return 0 if success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Operator interrupt: do not terminate a running native QThread abruptly.", file=sys.stderr)
        raise
