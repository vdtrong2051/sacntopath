"""FT-08.17 minimal Qt capture controls hosted inside the existing Live 3D panel.

Uses the already-open LiveCameraController (single camera owner), its owned RAW-v2
keyframe signal, the existing FT05.8+B01 tracking, and B02 evidence writer.
No second camera, camera SDK, VTK, new 3D renderer, SQLite or fusion pipeline.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QComboBox, QHBoxLayout, QLabel, QPushButton

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.modules.capture.domain.models import CameraState
from scantopath.modules.reconstruction.application.keyframe_sampling import retain_spaced_frame


class _SequenceProcessThread(QThread):
    success = Signal(str, int, int, str)
    failure = Signal(str)
    registration_progress = Signal(int, int)

    def __init__(self, packets: list[RawRgbdCapture], output: Path, parent=None,
                 *, captured_total: int | None = None, failed_attempts: int = 0,
                 interval_ms: int | None = None, stop_reason: str = 'unknown',
                 project_context: dict | None = None, tier_split: int | None = None):
        super().__init__(parent)
        self._packets = list(packets)  # owned RAW-v2 immutable bytes; no SDK references
        self._output = output
        self._captured_total = len(packets) if captured_total is None else captured_total
        self._failed_attempts = failed_attempts
        self._interval_ms = interval_ms
        self._stop_reason = stop_reason
        self._project_context = project_context
        self._tier_split = tier_split

    def run(self) -> None:
        try:
            from scantopath.modules.reconstruction.application.sequence_tracking import track_sequence
            # Reuse B02's existing proven atomic/hash-verified artifact writer.
            # This integration targets the source checkout, not an installed wheel.
            # Resolve the source-checkout script by a fixed package-relative path;
            # GUI launch working directory is not guaranteed to be repository root.
            import importlib.util
            script = Path(__file__).resolve().parents[5] / 'scripts' / 'b02_live_sequence.py'
            if not script.is_file():
                raise RuntimeError('B02_EVIDENCE_WRITER_MISSING')
            spec = importlib.util.spec_from_file_location('_scantopath_b02_evidence', script)
            if spec is None or spec.loader is None:
                raise RuntimeError('B02_EVIDENCE_WRITER_UNAVAILABLE')
            b02 = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(b02)
            save_evidence, verify_artifact = b02.save_evidence, b02.verify_artifact
            if self._tier_split is None:
                record = track_sequence(self._packets)
            else:
                from scantopath.modules.reconstruction.application.guided_two_tier import track_two_tier
                record = track_two_tier(self._packets, self._tier_split)
            record['source_mode'] = 'LIVE_3D_EXISTING_CAMERA_KEYFRAMES'
            record['capture_interval_requested_ms'] = self._interval_ms
            record['ui_capture'] = True
            if self._project_context is not None:
                record['project_context'] = self._project_context
            # Capture may continue past the 96-frame FT09/FT10 input budget.
            # Only the retained real RAW keyframes are serialized to B02.
            record['operator_stop_requested'] = (self._stop_reason == 'operator')
            record['stop_reason'] = self._stop_reason
            record['online_keyframe_policy'] = 'TEMPORAL_SPACING_FIRST_LAST_MAX_96'
            record['captured_keyframes_total'] = self._captured_total
            record['retained_keyframes'] = len(self._packets)
            record['discarded_keyframes_from_memory'] = self._captured_total - len(self._packets)
            record['failed_capture_attempts'] = self._failed_attempts
            output = save_evidence(self._output, self._packets, record)

            verified = verify_artifact(output)
            if self._project_context is not None:
                from scantopath.modules.reconstruction.application.project_sessions import register_raw
                # Per-capture numbered v2 RAW commit and SQLite audit; performed
                # entirely on the existing background sequence worker.
                register_raw(self._project_context, self._packets,
                             progress=lambda n, total: self.registration_progress.emit(n,total))
            self.success.emit(str(output), int(verified['accepted_poses']),
                              int(verified['source_frame_count']), str(verified['status']))
        except Exception as exc:
            code = str(getattr(exc, 'code', type(exc).__name__))
            self.failure.emit(code[:120])
        finally:
            self._packets.clear()


class SequenceCaptureUi(QObject):
    """Small controls added to an existing panel. No camera/geometry ownership.

    Start only while Live 3D shows an object with ChArUco reference. The
    operator controls stop; an online sampler retains at most 96 real frames
    spanning the sweep for the existing FT09/FT10 contracts. Processing runs
    in a QThread only after Stop or a terminal camera/stream failure.
    """
    completed = Signal(str, int, int, str)  # FT11: verified B02 artifact ready
    processing_started = Signal(int)  # FT11: async FT09 computation started

    MAX_FRAMES = 96  # B02/FT09/FT10 input limit; NOT a capture stop threshold

    def __init__(self, panel, camera, parent=None):
        super().__init__(parent)
        self._panel = panel
        self._camera = camera
        self._closing = False
        self._recording = False
        self._stopping = False
        self._inflight = False
        self._packets: list[RawRgbdCapture] = []
        self._captured_total = 0
        self._failed_attempts = 0
        self._stop_reason = 'unknown'
        self._session_id = ''
        self._specimen_id = ''
        self._project_context: dict | None = None
        self._tier = 1
        self._tier_paused = False
        self._tier_1_packets: list[RawRgbdCapture] = []
        self._output: Path | None = None
        self._job: _SequenceProcessThread | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._request_sample)

        row = QHBoxLayout()
        self.start_button = QPushButton('Bắt đầu quét đa góc', panel)
        self.start_button.setObjectName('ft0817SequenceStart')
        self.stop_button = QPushButton('Dừng & tái tạo', panel)
        self.stop_button.setObjectName('ft0817SequenceStop')
        self.interval = QComboBox(panel)
        self.interval.setObjectName('ft0817SequenceInterval')
        self.interval.addItem('1,2 giây/frame', 1200)
        self.interval.addItem('2 giây/frame', 2000)
        self.interval.setCurrentIndex(1)
        self.interval.setToolTip('Không tự dừng ở 96 frame. Giữ tối đa 96 khung hình đo thật; chỉ xử lý khi bạn nhấn Dừng.')
        row.addWidget(self.start_button)
        row.addWidget(self.stop_button)
        row.addWidget(self.interval)
        self.folder_button = QPushButton('Thư mục…', panel)
        self.folder_button.setObjectName('ft11SequenceFolder')
        self.folder_button.setToolTip('Tùy chọn: đổi vị trí lưu RAW; mặc định tự lưu vào Documents/ScanToPath/Sequences.')
        self.folder_button.clicked.connect(self._choose_output)
        row.addWidget(self.folder_button)
        self._chosen_output = None
        self.status = QLabel('Quét đa góc: chọn Vật thể + ChArUco, kết nối camera rồi Bắt đầu', panel)
        self.status.setObjectName('ft0817SequenceStatus')
        self.status.setWordWrap(True)
        # Reuse existing Live 3D panel; do not create a second viewport or page.
        layout = panel.layout()
        layout.insertLayout(3, row)  # after existing action buttons
        layout.insertWidget(4, self.status)
        self.tier_guide = QLabel('', panel)
        self.tier_guide.setObjectName('twoTierTrajectoryGuide')
        self.tier_guide.setWordWrap(True)
        layout.insertWidget(5, self.tier_guide)
        # Primary scan actions stay on one line. Mode and advanced recording
        # settings form a separate compact line instead of overflowing 3D.
        row.removeWidget(self.interval)
        row.removeWidget(self.folder_button)
        config_row = QHBoxLayout()
        self.capture_mode = QComboBox(panel)
        self.capture_mode.setObjectName('ft11CaptureMode')
        self.capture_mode.addItem('Quét đa góc', 'multi')
        self.capture_mode.addItem('Hai tầng · pose độc lập', 'two_tier')
        self.capture_mode.addItem('Chụp đơn', 'single')
        self.capture_mode.currentIndexChanged.connect(self._sync_capture_mode)
        config_row.addWidget(self.capture_mode)
        config_row.addWidget(self.interval)
        config_row.addWidget(self.folder_button)
        config_row.addStretch(1)
        layout.insertLayout(4, config_row)
        self.details_toggle = QPushButton('Thông số Live 3D ▸', panel)
        self.details_toggle.setObjectName('ft11LiveDetailsToggle')
        self.details_toggle.setCheckable(True)
        self.details_toggle.toggled.connect(self._sync_capture_mode)
        layout.insertWidget(6, self.details_toggle)

        self.start_button.clicked.connect(self._start)
        self.stop_button.clicked.connect(self._stop)
        camera.state_changed.connect(self._camera_state)
        camera.keyframe_ready.connect(self._keyframe_ready)
        camera.keyframe_failed.connect(self._keyframe_failed)
        panel.scope_mode_changed.connect(self._mode_changed)
        panel.reference_mode_changed.connect(self._mode_changed)
        self._update_controls()
        self._sync_capture_mode()

    @property
    def safe_to_dispose(self) -> bool:
        return self._job is None or not self._job.isRunning()

    def begin_shutdown(self) -> None:
        self._closing = True
        self._timer.stop()
        self._recording = self._stopping = self._inflight = False
        self._packets.clear()
        self._tier_1_packets.clear()
        self._tier_paused = False
        self._update_controls()
        # The active processing thread is allowed to finish and is reaped by
        # its own finished signal; the parent shell already waits on safe_to_dispose.

    def _ready_to_start(self) -> bool:
        return bool(self.capture_mode.currentData() in ('multi', 'two_tier') and
                    not self._closing and not self._recording and self._job is None
                    and self._camera.state is CameraState.STREAMING
                    and self._panel.scope_mode.currentData() == 'object'
                    and self._panel.reference_mode.currentData() == 'charuco')

    def _update_controls(self) -> None:
        self.start_button.setEnabled(self._ready_to_start())
        self.start_button.setText('Bắt đầu tầng 2 · mặt trên' if self._tier_paused else
                                  'Bắt đầu quét hai tầng' if self.capture_mode.currentData() == 'two_tier'
                                  else 'Bắt đầu quét đa góc')
        self.stop_button.setText('Kết thúc tầng 1' if self.capture_mode.currentData() == 'two_tier' and
                                 self._tier == 1 else 'Dừng & tái tạo')
        two_tier = self.capture_mode.currentData() == 'two_tier'
        self.tier_guide.setVisible(two_tier)
        if two_tier:
            if self._tier_paused:
                self.tier_guide.setText('CHUYỂN TẦNG · Đã giữ RAW tầng 1 trong bộ nhớ. ChArUco và vật phải đứng yên. '
                                        'Nâng camera lên tầng 2 (60–70°), sau đó nhấn Bắt đầu tầng 2.')
            elif self._tier == 1:
                self.tier_guide.setText('TẦNG 1 · Quét thân: nâng 40–50°, bán kính 0,5–0,7 m, đi vòng 0→360° '
                                        '(6–8°/frame). Giữ vật và ChArUco đủ rõ. Nhấn Kết thúc tầng 1.')
            else:
                self.tier_guide.setText('TẦNG 2 · Mặt trên: nâng 60–70°, đi cung 0→180° '
                                        '(8–10°/frame). Giữ bảng ChArUco cố định và trong khung hình.')
        self.stop_button.setEnabled(self._recording and not self._stopping)
        self.interval.setEnabled(not self._recording and not self._tier_paused and self._job is None)
        self.folder_button.setEnabled(not self._recording and not self._tier_paused and self._job is None)
        self.capture_mode.setEnabled(not self._recording and not self._tier_paused and self._job is None)

    def _sync_capture_mode(self, *_args):
        multi = self.capture_mode.currentData() in ('multi', 'two_tier')
        for widget in (self.start_button, self.stop_button, self.interval, self.folder_button):
            widget.setVisible(multi)
        # Retain all original Single-frame controls and their signal wiring.
        # A stub panel in offscreen tests may not implement these optional UI items.
        for name in ('freeze_button', 'resume_button', 'snapshot_button', 'enhance_toggle'):
            widget = getattr(self._panel, name, None)
            if widget is not None:
                widget.setVisible(not multi)
        for name in ('geometry_info', 'scope', 'help'):
            widget = getattr(self._panel, name, None)
            if widget is not None:
                widget.setVisible(self.details_toggle.isChecked())
        self.details_toggle.setText('Ẩn thông số Live 3D ▾' if self.details_toggle.isChecked()
                                    else 'Thông số Live 3D ▸')
        parent = self.parent()
        capture = getattr(getattr(parent, '_live', None), 'panel', None)
        if capture is not None:
            for name in ('capture_button', 'auto_capture_button'):
                widget = getattr(capture, name, None)
                if widget is not None:
                    widget.setVisible(not multi)
        self._update_controls()

    @Slot()
    def _choose_output(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self._panel, 'Chọn thư mục RAW của phiên tái tạo',
            str(self._chosen_output or (Path.home()/'Documents'/'ScanToPath'/'Sequences')))
        if selected:
            self._chosen_output = Path(selected)

    @Slot()
    def _start(self) -> None:
        if not self._ready_to_start():
            self.status.setText('Chuỗi: chọn Vật thể + ChArUco, rồi bật camera trước.')
            return
        if self._tier_paused:
            # Never resume into another Project or scan session.
            view = getattr(self.parent(), '_view', None)
            try:
                from scantopath.modules.reconstruction.application.project_sessions import active_ui_session
                context = active_ui_session(view)
                if context is None or context != self._project_context:
                    raise ValueError('TWO_TIER_SESSION_CHANGED')
            except (ValueError, OSError, RuntimeError) as exc:
                self.status.setText('Không thể tiếp tục tầng 2: ' + str(exc)[:100])
                return
            self._tier_paused = False
            self._recording = True
            self._stopping = self._inflight = False
            self.status.setText('TẦNG 2/2 · nâng camera 60–70°, giữ đủ ChArUco; '
                                'thu vòng cung mặt trên và nhấn Dừng & tái tạo.')
            self._update_controls()
            QTimer.singleShot(0, self._request_sample)
            return
        # No repetitive folder dialog at every Start; optional override above.
        output = self._chosen_output or (Path.home()/'Documents'/'ScanToPath'/'Sequences')
        # Reuse the proven output-location safeguard before a camera command.
        from scantopath.modules.reconstruction.infrastructure.live_artifact_writer import _safe_output_parent
        try:
            self._output = _safe_output_parent(output)
        except (ValueError, RuntimeError, OSError) as exc:
            self.status.setText('Thư mục kết quả không hợp lệ: ' + str(getattr(exc, 'code', type(exc).__name__)))
            return
        token = uuid4().hex[:16]
        self._project_context = None
        view = getattr(self.parent(), '_view', None)
        if view is not None:
            try:
                from scantopath.modules.reconstruction.application.project_sessions import active_ui_session, project_pipeline_root
                self._project_context = active_ui_session(view)
                if self._project_context is not None:
                    output = project_pipeline_root(self._project_context, create=True) / '00_RAW_SEQUENCES'
                    self._output = _safe_output_parent(output)
            except (ValueError, OSError, RuntimeError) as exc:
                self.status.setText('Phiên Project không hợp lệ: ' + str(exc)[:160])
                return
        if self._project_context is None:
            self.status.setText('Hãy mở kho, chọn một PHIÊN QUÉT đang mở trong Cây dự án rồi bắt đầu.')
            return
        self._session_id = self._project_context['session_id']
        self._specimen_id = self._project_context['specimen_id']
        self._packets = []
        self._tier_1_packets = []
        self._tier = 1
        self._tier_paused = False
        self._captured_total = 0
        self._failed_attempts = 0
        self._stop_reason = 'unknown'
        self._recording = True
        self._stopping = False
        self._inflight = False
        self.status.setText('ĐANG THU · RAW sẽ lưu vào phiên Project' if self._project_context else
                            'ĐANG THU (ngoài Project) · hãy chọn phiên quét để RAW và mesh đồng bộ')
        self._update_controls()
        QTimer.singleShot(0, self._request_sample)

    @Slot()
    def _request_sample(self) -> None:
        if not self._recording or self._stopping or self._inflight or self._closing:
            return
        if self._camera.state is not CameraState.STREAMING:
            # The camera controller serializes capture requests; never open a
            # second source or submit a new request during CAPTURING.
            self._timer.start(150)
            return
        self._inflight = self._camera.capture_keyframe(
            session_id=self._session_id, specimen_id=self._specimen_id)
        if not self._inflight:
            self._timer.start(150)

    @Slot(object)
    def _keyframe_ready(self, packet: object) -> None:
        if not self._recording or not self._inflight or self._closing:
            return
        self._inflight = False
        if not isinstance(packet, RawRgbdCapture):
            self._stopping = True
            self._stop_reason = 'invalid_raw'
            self.status.setText('Chuỗi: Camera trả về dữ liệu RAW không hợp lệ')
        elif (packet.metadata.session_id != self._session_id or
              packet.metadata.specimen_id != self._specimen_id or
              ((self._packets or self._tier_1_packets) and (
                  packet.metadata.depth.frame_index <=
                  (self._packets or self._tier_1_packets)[-1].metadata.depth.frame_index
                  or packet.metadata.depth.timestamp_us <=
                  (self._packets or self._tier_1_packets)[-1].metadata.depth.timestamp_us))):
            self._stopping = True
            self._stop_reason = 'capture_identity_or_order_invalid'
            self.status.setText('Chuỗi: dữ liệu không cùng phiên hoặc sai thứ tự frame')
        else:
            self._captured_total += 1
            budget = self.MAX_FRAMES // 2 if self.capture_mode.currentData() == 'two_tier' else self.MAX_FRAMES
            retain_spaced_frame(self._packets, packet, limit=budget)
            count = len(self._packets)
            prefix = f'TẦNG {self._tier}/2' if self.capture_mode.currentData() == 'two_tier' else 'ĐANG THU'
            self.status.setText(f'{prefix} · đã chụp {self._captured_total} frame, '
                                f'giữ {count}/{budget} frame đại diện · lỗi tạm: '
                                f'{self._failed_attempts} · Nhấn Dừng khi đủ góc')
        if self._stopping:
            self._finish_capture()
        else:
            self._timer.start(int(self.interval.currentData()))

    @Slot(str)
    def _keyframe_failed(self, code: str) -> None:
        if not self._recording or not self._inflight:
            return
        self._inflight = False
        if self._stopping:
            self._finish_capture()
            return
        # An isolated keyframe capture failure must not truncate a sweep.
        # CameraState.FAILED/CLOSED is still handled as a terminal state below.
        self._failed_attempts += 1
        self.status.setText(
            f'ĐANG THU · lỗi chụp tạm thời ({code[:70]}), đang thử lại · '
            f'giữ {len(self._packets)} frame; nhấn Dừng khi quét xong')
        self._timer.start(max(1500, int(self.interval.currentData())))

    @Slot()
    def _stop(self) -> None:
        if not self._recording:
            return
        self._stopping = True
        self._stop_reason = 'operator'
        self._timer.stop()
        self.stop_button.setEnabled(False)
        if self._inflight:
            self.status.setText('Chuỗi: chờ hoàn tất frame đang chụp…')
        else:
            self._finish_capture()

    def _finish_capture(self) -> None:
        self._timer.stop()
        self._recording = self._stopping = self._inflight = False
        if self._closing:
            self._packets.clear()
            self._tier_1_packets.clear()
            return
        if len(self._packets) < 2:
            self.status.setText(f'Chuỗi: chỉ có {len(self._packets)} frame; cần tối thiểu 2. '
                                'Không tạo trajectory.')
            self._packets.clear()
            self._update_controls()
            return
        if self.capture_mode.currentData() == 'two_tier' and self._tier == 1 and self._stop_reason == 'operator':
            if len(self._packets) < 2:
                self.status.setText('Tầng 1 cần ít nhất 2 frame; chưa thể chuyển sang tầng 2.')
                self._recording = True
                self._stopping = False
                self._update_controls()
                self._timer.start(int(self.interval.currentData()))
                return
            self._tier_1_packets = list(self._packets)
            self._packets = []
            self._tier = 2
            self._tier_paused = True
            self.status.setText(f'ĐÃ LƯU TRONG BỘ NHỚ {len(self._tier_1_packets)} RAW tầng 1. '
                                'Nâng camera 60–70° giữ ChArUco, rồi nhấn Bắt đầu tầng 2. '
                                'KHÔNG di chuyển bảng/vật thể.')
            self._update_controls()
            return
        split = len(self._tier_1_packets) if self._tier_1_packets else None
        if split is not None and len(self._packets) < 2:
            self.status.setText('Tầng 2 cần ít nhất 2 frame, chưa xử lý.')
            self._recording = True
            self._stopping = False
            self._timer.start(int(self.interval.currentData()))
            self._update_controls()
            return
        packets = self._tier_1_packets + self._packets
        count = len(packets)
        job = _SequenceProcessThread(
            packets, self._output, self,
            captured_total=self._captured_total,
            failed_attempts=self._failed_attempts,
            interval_ms=int(self.interval.currentData()),
            stop_reason=self._stop_reason,
            project_context=self._project_context, tier_split=split)
        self._job = job
        self._packets.clear()
        self._tier_1_packets.clear()
        job.success.connect(self._on_success)
        job.failure.connect(self._on_failure)
        job.registration_progress.connect(self._registration_progress)
        job.finished.connect(self._on_finished)
        self.status.setText(f'Đã dừng · xử lý {count} frame đại diện từ {self._captured_total} frame đã chụp…')
        self._update_controls()
        job.start()
        self.processing_started.emit(count)

    @Slot(int, int)
    def _registration_progress(self, done: int, total: int) -> None:
        self.status.setText(f'Đang đưa RAW vào phiên SQLite: {done}/{total} · xin giữ ứng dụng mở')

    @Slot(str, int, int, str)
    def _on_success(self, path: str, accepted: int, total: int, state: str) -> None:
        if not self._closing:
            self.status.setText(f'Chuỗi 6DoF: {state} · {accepted}/{total} pose · '
                                f'Đã lưu: {Path(path).name}')
            self.status.setToolTip(path)
            self.completed.emit(path, accepted, total, state)
            if self._project_context is not None:
                view = getattr(self.parent(), '_view', None)
                if view is not None:
                    # Update SQLite Explorer after worker registered all RAW.
                    try:
                        view._reload_project_store()
                    except AttributeError:
                        pass

    @Slot(str)
    def _on_failure(self, code: str) -> None:
        if not self._closing:
            self.status.setText('Chuỗi 6DoF: xử lý lỗi (' + code + ')')

    @Slot()
    def _on_finished(self) -> None:
        job = self._job
        if job is None:
            return
        if job.isRunning() or not job.wait(0):
            QTimer.singleShot(30, self._on_finished)
            return
        self._job = None
        job.deleteLater()
        if not self._closing:
            self._update_controls()

    @Slot(object)
    def _camera_state(self, state) -> None:
        if self._recording and state in (CameraState.STOPPING, CameraState.CLOSED,
                                          CameraState.FAILED, CameraState.IDLE):
            self._stopping = True
            self._stop_reason = 'camera_stream_ended'
            self._inflight = False  # failed camera may never emit captured
            self._finish_capture()
        self._update_controls()

    @Slot(str)
    def _mode_changed(self, *_args) -> None:
        if self._recording:
            self._stopping = True
            self._stop_reason = 'operator_changed_mode'
            if not self._inflight:
                self._finish_capture()
        self._update_controls()
