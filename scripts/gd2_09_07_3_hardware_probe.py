"""GD2-09.07.3: operator-triggered Windows/Gemini 2 live UI lifecycle probe.

Opens camera ONLY by explicit CLI invocation, never saves RAW or screenshots.
Proves streaming/ROI-path wiring and safe stop/reopen/close; semantic bbox
correctness needs the separate operator physical scene protocol.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from scantopath.application.contracts import WorkspaceId
from scantopath.modules.capture.domain.models import CameraState
from scantopath.ui.shell import ScanToPathMainWindow


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.cycles <= 5 or not 2 <= args.seconds <= 15:
        parser.error("cycles must be 1..5 and seconds must be 2..15")
    if args.output.exists():
        parser.error("output already exists; never overwrite acceptance evidence")
    if args.output.is_symlink() or any(parent.is_symlink() for parent in args.output.parents):
        parser.error("symlink output path is not allowed")
    app = QApplication.instance() or QApplication([])
    # Keep polling until the asynchronous camera/analyzer shutdown is reaped.
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("ScanToPath GD2-09.07.3 hardware acceptance")
    window = ScanToPathMainWindow()
    live = window.capture_live
    panel = live.panel

    report = {
        "schema": "scantopath-gd2-09-07-3-hardware-ui-v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "INCOMPLETE",
        "manual_object_accuracy": "NOT_TESTED",
        "capture_saved": False,
        "raw_written": False,
        "startup_idle": live.state is CameraState.IDLE and live.safe_to_dispose,
        "replay_panel_present": window.capture_preview.panel.objectName() == "capturePreview",
        "workspace_count": len(window._pages),
        "cycles_requested": args.cycles,
        "cycles_completed": 0,
        "cycles": [],
        "state_log": [],
        "failures": [],
    }
    current = {}
    t0 = time.monotonic()
    phase = "start"
    phase_since = t0
    close_requested = False
    closed_finished = False
    errors = report["failures"]
    last_heartbeat = 0.0

    def entered(name: str):
        nonlocal phase, phase_since
        phase = name
        phase_since = time.monotonic()
        print(f"probe.phase={name}", flush=True)

    def on_state(state: CameraState):
        report["state_log"].append(state.value)
        print(f"camera.state={state.value}", flush=True)

    def on_error(code: str):
        errors.append("CAMERA_" + code)
        print(f"camera.error={code}", flush=True)

    live.camera.state_changed.connect(on_state)
    live.camera.failure.connect(on_error)

    def collect() -> None:
        pix = panel._rgb_original
        roi = panel.displayed_roi
        current["rgb_size"] = ([pix.width(), pix.height()] if pix is not None else None)
        current["depth_size"] = list(panel.depth_overlay.image_size or ()) or None
        current["frames_published"], current["frames_dropped"] = live.camera.stats()
        current["frames_analyzed"] = 1 if live._last_analyzed_frame is not None else 0
        current["roi_status_label"] = panel.roi_label.text()
        if roi is not None:
            current["roi"] = {
                "xywh": [roi.x, roi.y, roi.width, roi.height],
                "grid": [roi.frame_width, roi.frame_height],
                "source": roi.source.value,
            }
        if live._last_analyzed_frame is not None:
            current["analysis_observed"] = True

    def request_close():
        nonlocal close_requested
        if close_requested:
            return
        close_requested = True
        entered("closing")
        window.close()  # cooperative async shutdown; never terminate worker

    def fail(reason: str):
        if reason not in errors:
            errors.append(reason)
            print("probe.failure=" + reason, flush=True)
        request_close()

    def tick() -> None:
        nonlocal current, closed_finished, last_heartbeat
        now = time.monotonic()
        if phase == "start":
            if not report["startup_idle"] or not report["replay_panel_present"] or report["workspace_count"] != 4:
                fail("STARTUP_CONTRACT_FAILED")
                return
            if not live.start():
                fail("START_REJECTED")
                return
            current = {"cycle": len(report["cycles"]) + 1, "analysis_observed": False}
            entered("opening")
        elif phase == "opening":
            if live.state is CameraState.STREAMING:
                entered("streaming")
            elif live.state is CameraState.FAILED:
                fail("OPEN_FAILED")
            elif now - phase_since > 25.0:
                fail("OPENING_TIMEOUT")
        elif phase == "streaming":
            collect()
            if live.state is CameraState.FAILED:
                fail("STREAM_FAILED")
            elif now - phase_since >= args.seconds:
                if not live.stop():
                    fail("STOP_REJECTED")
                else:
                    entered("stopping")
        elif phase == "stopping":
            if live.state is CameraState.FAILED:
                fail("STOP_FAILED")
            elif live.state is CameraState.CLOSED and live.camera.safe_to_dispose:
                current["worker_reaped"] = True
                current["ended_closed"] = True
                current["overlay_cleared"] = panel.depth_overlay.image_size is None
                current["elapsed_stream_seconds"] = round(args.seconds, 2)
                ok_frame = (current.get("frames_published", 0) >= 2)
                ok_rgb = current.get("rgb_size") == [1920, 1080]
                ok_depth = current.get("depth_size") == [1280, 800]
                current["cycle_pass"] = bool(
                    ok_frame and ok_rgb and ok_depth and current.get("analysis_observed")
                    and current["overlay_cleared"]
                )
                report["cycles"].append(current)
                report["cycles_completed"] = len(report["cycles"])
                print("cycle.%d.result=%s" % (len(report["cycles"]),
                    "PASS" if current["cycle_pass"] else "FAIL"), flush=True)
                if not current["cycle_pass"]:
                    fail("CYCLE_ASSERTIONS_FAILED")
                elif len(report["cycles"]) < args.cycles:
                    current = {}
                    entered("start")
                else:
                    request_close()
            elif now - phase_since > 25.0:
                fail("STOPPING_TIMEOUT_PENDING_CLEANUP")
        elif phase == "closing":
            if (not window.isVisible() and live.safe_to_dispose
                    and live.camera.safe_to_dispose):
                closed_finished = True
                app.quit()
            elif now - phase_since > 25.0 and now - last_heartbeat > 5.0:
                last_heartbeat = now
                print("probe.warning=WAITING_FOR_COOPERATIVE_NATIVE_SHUTDOWN", flush=True)
                # Deliberately DO NOT quit or delete running QThreads.

    timer = QTimer()
    timer.setInterval(50)
    timer.timeout.connect(tick)
    window.show()
    window._navigate(WorkspaceId.CAPTURE)
    timer.start()
    app.exec()
    timer.stop()

    report["final_state"] = live.state.value
    report["window_closed"] = not window.isVisible()
    report["camera_reaped"] = live.camera.safe_to_dispose
    report["analysis_reaped"] = live.safe_to_dispose
    report["elapsed_seconds"] = round(time.monotonic() - t0, 2)
    ok = bool(
        not errors and closed_finished and report["startup_idle"]
        and report["replay_panel_present"] and report["workspace_count"] == 4
        and report["cycles_completed"] == args.cycles
        and all(c["cycle_pass"] for c in report["cycles"])
        and report["window_closed"] and report["camera_reaped"] and report["analysis_reaped"]
    )
    report["status"] = "AUTOMATED_HARDWARE_PASS" if ok else "FAIL"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # exclusive creation: never overwrite a previous acceptance receipt
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print("evidence.report=" + str(args.output.resolve()))
    print(f"cycles.completed={report['cycles_completed']}/{args.cycles}")
    print(f"camera.final_state={report['final_state']}")
    print(f"camera.worker_reaped={report['camera_reaped']}")
    print(f"analysis.worker_reaped={report['analysis_reaped']}")
    print("manual.object_accuracy=NOT_TESTED")
    print("capture.saved=false")
    print("GD2_09_07_3_HARDWARE_UI=" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
