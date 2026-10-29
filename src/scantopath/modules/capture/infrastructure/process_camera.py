"""GD2-09.07.3: crash-isolated Gemini 2 camera IPC adapter.

The native OrbbecSDK is loaded only in a spawned disposable child process.
The Qt GUI and LiveStreamWorker receive owned Python frames, never SDK pointers.
"""
from __future__ import annotations

from collections.abc import Callable
import pickle
import multiprocessing as mp
from multiprocessing.connection import Connection
from typing import Any

from scantopath.modules.capture.application.live_stream import LiveCameraError, LiveNativeFrame


def _default_camera_factory():
    # No vendor library is loaded until explicit operator Start and child spawn.
    from scantopath.modules.capture.infrastructure.native_camera import Gemini2NativeCameraAdapter
    return Gemini2NativeCameraAdapter()


def _child_main(conn: Connection, factory: Callable[[], Any]) -> None:
    """The ONLY process that may call native open/read/close."""
    camera = None
    try:
        camera = factory()
        camera.open()
        conn.send(("OPENED", None))
        while True:
            command, value = conn.recv()
            if command == "READ":
                timeout, attempts = value
                try:
                    frame = camera.read_next(
                        per_attempt_timeout_ms=timeout, max_attempts=attempts
                    )
                    conn.send(("FRAME", frame))
                except TimeoutError:
                    conn.send(("TIMEOUT", None))
                except LiveCameraError as exc:
                    conn.send(("ERROR", exc.code))
                    return
                except Exception:
                    conn.send(("ERROR", "READ_FAILED"))
                    return
            elif command == "CLOSE":
                camera.close()  # Ack only after native stop/destruction returns.
                camera = None
                conn.send(("CLOSED", None))
                return
            else:
                conn.send(("ERROR", "INVALID_CAMERA_COMMAND"))
                return
    except (EOFError, BrokenPipeError, OSError):
        pass
    except LiveCameraError as exc:
        try:
            conn.send(("ERROR", exc.code))
        except (OSError, EOFError, BrokenPipeError):
            pass
    except Exception:
        try:
            conn.send(("ERROR", "OPEN_FAILED"))
        except (OSError, EOFError, BrokenPipeError):
            pass
    finally:
        if camera is not None:
            try:
                camera.close()
            except Exception:
                pass  # Only the expendable child risks native shutdown.
        conn.close()


class ProcessIsolatedCameraAdapter:
    """NativeCameraPort via trusted local multiprocessing Pipe (no network).

    All API calls occur inside one LiveStreamWorker QThread. Native crashes
    are converted to DEVICE_PROCESS_CRASH in the parent. Never terminate Qt.
    """

    def __init__(
        self,
        *,
        camera_factory: Callable[[], Any] = _default_camera_factory,
        opening_timeout_ms: int = 15000,
        read_timeout_ms: int = 5000,
        close_timeout_ms: int = 2500,
    ) -> None:
        if not callable(camera_factory):
            raise TypeError("camera_factory must be callable")
        for name, value in (
            ("opening_timeout_ms", opening_timeout_ms),
            ("read_timeout_ms", read_timeout_ms),
            ("close_timeout_ms", close_timeout_ms),
        ):
            if type(value) is not int or not 100 <= value <= 120000:
                raise ValueError(f"{name} out of bounds")
        self._factory = camera_factory
        self._opening_timeout_ms = opening_timeout_ms
        self._read_timeout_ms = read_timeout_ms
        self._close_timeout_ms = close_timeout_ms
        self._context = mp.get_context("spawn")
        self._conn: Connection | None = None
        self._proc: mp.Process | None = None
        self._opened = False
        self.last_exit_code: int | None = None

    @property
    def child_pid(self) -> int | None:
        return self._proc.pid if self._proc is not None else None

    def _rpc(self, message: tuple[str, Any] | None, timeout_ms: int) -> tuple[str, Any]:
        conn, proc = self._conn, self._proc
        if conn is None or proc is None:
            raise LiveCameraError("NOT_OPEN")
        try:
            if message is not None:
                conn.send(message)
            if not conn.poll(timeout_ms / 1000):
                if proc.exitcode is not None:
                    raise LiveCameraError("DEVICE_PROCESS_CRASH")
                raise LiveCameraError("DEVICE_PROCESS_TIMEOUT")
            result = conn.recv()
        except (EOFError, BrokenPipeError, OSError, pickle.UnpicklingError) as exc:
            raise LiveCameraError("DEVICE_PROCESS_CRASH") from exc
        if not isinstance(result, tuple) or len(result) != 2 or type(result[0]) is not str:
            raise LiveCameraError("INVALID_DEVICE_RESPONSE")
        return result

    def _cleanup(self) -> bool:
        conn, proc = self._conn, self._proc
        self._conn = None
        self._proc = None
        self._opened = False
        if conn is not None:
            conn.close()
        forced = False
        if proc is not None:
            try:
                if proc.pid is None:
                    return False  # spawn failed before child was started
                proc.join(timeout=3.0)
                if proc.is_alive():
                    forced = True
                    proc.terminate()  # ONLY isolated subprocess; never a Qt thread.
                    proc.join(timeout=1.0)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=1.0)
                self.last_exit_code = proc.exitcode
            finally:
                proc.close()
        return forced

    def open(self) -> None:
        if self._proc is not None:
            raise LiveCameraError("ALREADY_OPEN")
        self.last_exit_code = None
        parent, child = self._context.Pipe(duplex=True)
        try:
            process = self._context.Process(
                target=_child_main,
                args=(child, self._factory),
                daemon=True,
                name="ScanToPathGemini2Camera",
            )
            self._conn, self._proc = parent, process
            process.start()
            child.close()
            kind, data = self._rpc(None, self._opening_timeout_ms)
            if kind == "ERROR":
                raise LiveCameraError(str(data))
            if kind != "OPENED":
                raise LiveCameraError("INVALID_DEVICE_RESPONSE")
            self._opened = True
        except Exception as exc:
            child.close()
            self._cleanup()
            if isinstance(exc, LiveCameraError):
                raise
            raise LiveCameraError("OPEN_FAILED") from exc

    def read_next(self, *, per_attempt_timeout_ms: int, max_attempts: int) -> LiveNativeFrame:
        if not self._opened:
            raise LiveCameraError("NOT_OPEN")
        if (type(per_attempt_timeout_ms) is not int or type(max_attempts) is not int
                or not 1 <= per_attempt_timeout_ms <= 1000 or not 1 <= max_attempts <= 3):
            raise ValueError("native read timeout/attempts invalid")
        kind, data = self._rpc(
            ("READ", (per_attempt_timeout_ms, max_attempts)), self._read_timeout_ms
        )
        if kind == "TIMEOUT":
            raise TimeoutError("bounded camera read timeout")
        if kind == "ERROR":
            raise LiveCameraError(str(data))
        if kind != "FRAME" or not isinstance(data, LiveNativeFrame):
            raise LiveCameraError("INVALID_DEVICE_RESPONSE")
        return data

    def close(self) -> None:
        if self._proc is None:
            self._opened = False
            return
        error: LiveCameraError | None = None
        try:
            if self._opened:
                kind, data = self._rpc(("CLOSE", None), self._close_timeout_ms)
                if kind == "ERROR":
                    error = LiveCameraError(str(data))
                elif kind != "CLOSED":
                    error = LiveCameraError("INVALID_DEVICE_RESPONSE")
        except LiveCameraError as exc:
            error = exc
        finally:
            forced = self._cleanup()
        if error is None and forced:
            error = LiveCameraError("DEVICE_PROCESS_TIMEOUT")
        elif error is None and self.last_exit_code != 0:
            error = LiveCameraError("DEVICE_PROCESS_CRASH")
        if error is not None:
            raise error
