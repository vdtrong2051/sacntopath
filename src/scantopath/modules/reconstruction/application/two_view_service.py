"""B-01 RAW-v2 two-capture orchestration; no RAW/SQLite writes."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import numpy as np

from .contracts import InputCloud, RegistrationConfig, RegistrationError, TwoViewResult
from .two_view_registration import register_two_views


@dataclass(frozen=True)
class PairInput:
    cloud: InputCloud
    source_ref: dict[str, Any]
    roi_xyxy: tuple[int, int, int, int]
    selected_points: int


class _VerifiedReplayRecorder:
    """Keep original verified packet metadata from the replay already in progress."""
    def __init__(self, reader):
        self.reader = reader
        self.packet = None

    def load(self, context):
        self.packet = self.reader.load(context)
        return self.packet


def _read_capture(context, roi: tuple[int, int, int, int],
                  min_depth_m: float, max_depth_m: float) -> PairInput:
    from scantopath.modules.capture.application.replay import RawReplayService
    from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter
    from scantopath.modules.capture.application.decoding import RgbdDecoder
    from scantopath.modules.capture.infrastructure.jpeg_codec import PillowMjpegDecoder
    from scantopath.modules.geometry.application.replay_geometry import ReplayGeometryService

    recorder = _VerifiedReplayRecorder(RawReaderAdapter())
    geometry = ReplayGeometryService(RawReplayService(recorder),
                                     RgbdDecoder(PillowMjpegDecoder())).process(context)
    packet = recorder.packet
    if packet is None:
        raise RegistrationError("RAW_LOAD_FAILED", "Verified replay did not yield a packet")
    meta = packet.metadata
    x0, y0, x1, y1 = roi
    if not (0 <= x0 < x1 <= meta.depth.width and 0 <= y0 < y1 <= meta.depth.height):
        raise RegistrationError("ROI_OUTSIDE_DEPTH_GRID", "ROI must be within native depth pixels")
    points = geometry.points_xyz_m
    uv = geometry.depth_source_uv
    selected = ((uv[:, 0] >= x0) & (uv[:, 0] < x1) &
                (uv[:, 1] >= y0) & (uv[:, 1] < y1) &
                (points[:, 2] >= min_depth_m) & (points[:, 2] <= max_depth_m))
    xyz = np.array(points[selected], dtype=np.float64, order='C', copy=True)
    uv_selected = np.array(uv[selected], dtype=np.int32, order='C', copy=True)
    if len(xyz) == 0:
        raise RegistrationError("EMPTY_ROI", "No measured depth points in selected ROI")
    hashes = tuple(geometry.source_raw_sha256)
    fingerprint = geometry.calibration_fingerprint
    source_ref = {
        'capture_id': str(meta.capture_id),
        'session_id': str(meta.session_id),
        'specimen_id': str(meta.specimen_id),
        'camera_name': str(meta.device.name),
        'rgb_frame_index': int(meta.color.frame_index),
        'depth_frame_index': int(meta.depth.frame_index),
        'color_timestamp_us': int(meta.color.timestamp_us),
        'depth_timestamp_us': int(meta.depth.timestamp_us),
        'timestamp_domain': str(meta.timestamp_domain),
        'calibration_fingerprint': fingerprint,
        'depth_scale_m_per_unit': float(meta.depth_scale_m_per_unit),
        'native_depth_grid_wh': [int(meta.depth.width), int(meta.depth.height)],
        'native_color_grid_wh': [int(meta.color.width), int(meta.color.height)],
        'alignment_mode': str(meta.alignment_mode),
        'source_raw_sha256': dict(hashes),
        'source_kind': 'MEASURED_RAW',
        'metric_accuracy_verified': False,
        'roi_xyxy_depth_grid': list(roi),
        'depth_range_m': [min_depth_m, max_depth_m],
        'selected_measured_points': int(len(xyz)),
    }
    return PairInput(
        cloud=InputCloud(meta.capture_id, xyz, fingerprint, hashes, uv_selected),
        source_ref=source_ref,
        roi_xyxy=roi,
        selected_points=len(xyz))


def process_two_captures(context0, context1, *,
                         roi0: tuple[int, int, int, int],
                         roi1: tuple[int, int, int, int],
                         min_depth_m: float, max_depth_m: float,
                         config: RegistrationConfig | None = None,
                         initial_T_world_depth1: np.ndarray | None = None):
    """Produces a candidate pair and input provenance; never writes to a project store."""
    if (context0.store_root != context1.store_root or
            context0.project_id != context1.project_id or
            context0.specimen_id != context1.specimen_id or
            context0.session_id != context1.session_id):
        raise RegistrationError("CROSS_SESSION_PAIR", "Two captures must share a ScanSession")
    if context0.capture_id == context1.capture_id:
        raise RegistrationError("DUPLICATE_CAPTURE", "Select two distinct RAW captures")
    if not (0 < min_depth_m < max_depth_m < 50):
        raise RegistrationError("DEPTH_RANGE_INVALID", "Invalid metre-scale depth range")
    first = _read_capture(context0, roi0, min_depth_m, max_depth_m)
    second = _read_capture(context1, roi1, min_depth_m, max_depth_m)
    result: TwoViewResult = register_two_views(first.cloud, second.cloud,
                                               config, initial_T_world_depth1)
    return first, second, result
