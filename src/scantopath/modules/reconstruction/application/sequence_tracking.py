"""FT-08.17: sampled freehand RGB-D 6DoF sequence, based entirely on B-01.

No new pose estimator, segmentation, ICP backend, camera owner or fused map.
World = first accepted depth optical frame, metres; T_A_B maps B -> A.
Any rejected edge fails closed (LOST); recovery and fusion belong to FT-09/10.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from math import isfinite
from typing import Callable

import numpy as np

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.modules.reconstruction.application.contracts import RegistrationConfig
from scantopath.modules.reconstruction.application.live_pair import (
    process_live_pair, validate_live_pair,
)


def _identity() -> list[list[float]]:
    return np.eye(4, dtype=np.float64).tolist()


def _is_se3(T: object) -> bool:
    try:
        m = np.asarray(T, dtype=np.float64)
        return bool(m.shape == (4, 4) and np.isfinite(m).all()
                    and np.allclose(m[3], [0, 0, 0, 1], atol=1e-8)
                    and np.allclose(m[:3, :3].T @ m[:3, :3], np.eye(3), atol=1e-4)
                    and np.isclose(np.linalg.det(m[:3, :3]), 1.0, atol=1e-4))
    except (TypeError, ValueError, np.linalg.LinAlgError):
        return False


def _frame_id(packet: RawRgbdCapture, index: int) -> dict:
    m = packet.metadata
    return {
        'sample_index': index,
        'capture_id': m.capture_id,
        'color_frame_index': m.color.frame_index,
        'depth_frame_index': m.depth.frame_index,
        'color_timestamp_us': m.color.timestamp_us,
        'depth_timestamp_us': m.depth.timestamp_us,
        'calibration_source': 'RAW_V2_SAME_FRAMESET',
        'depth_units': 'm',
        'world_pose_estimated_not_metric_verified': True,
    }


def track_sequence(
    packets: list[RawRgbdCapture], *,
    config: RegistrationConfig | None = None,
    min_depth_m: float = .30,
    max_depth_m: float = 1.20,
    pair_processor: Callable | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> dict:
    """Evaluate measured frames in order and chain ONLY accepted B-01 edges.

    Distinct-view criterion from B-01 is not a tracking quality gate: a still
    camera may legitimately produce another frame. All geometric/pose gates
    and the FT-05.8 ChArUco--ICP cross-check stay untouched.
    """
    if not isinstance(packets, list) or not 2 <= len(packets) <= 20:
        raise ValueError('B02_SEQUENCE_LENGTH_INVALID: expected 2..20 frames')
    if not (isfinite(min_depth_m) and isfinite(max_depth_m)
            and 0 < min_depth_m < max_depth_m < 50):
        raise ValueError('B02_DEPTH_RANGE_INVALID')
    if any(not isinstance(packet, RawRgbdCapture) or not packet.metadata.measured
           for packet in packets):
        raise ValueError('B02_MEASURED_RAW_REQUIRED')
    # Preserve all ICP validation thresholds. Only B01's pairwise demonstration
    # requirement for distinct motion is not relevant to sequence tracking.
    base = config or RegistrationConfig()
    tracking_cfg = replace(base, min_distinct_view_translation_m=1e-6,
                           min_distinct_view_rotation_deg=1e-5)
    processor = pair_processor or process_live_pair
    rows: list[dict] = []

    def record(row: dict) -> None:
        rows.append(row)
        if on_event is not None:
            on_event(dict(row))

    world_pose = np.eye(4, dtype=np.float64)
    first = dict(_frame_id(packets[0], 0), status='ANCHOR',
                 T_world_depth=_identity(),
                 accepted_for_trajectory=True,
                 pose_origin='identity_anchor_depth_optical', quality=None)
    record(first)
    accepted = 1
    last_packet = packets[0]
    lost = False
    for i in range(1, len(packets)):
        packet = packets[i]
        row = _frame_id(packet, i)
        if lost:
            record(dict(row, status='LOST_NO_RECOVERY', accepted_for_trajectory=False,
                        T_world_depth=None, reject_code='WAIT_FOR_FT09_RECOVERY', quality=None))
            continue
        diagnostics: dict = {}
        try:
            # Reuse B01's metadata/lineage protections even for skipped motion.
            validate_live_pair(last_packet, packet)
            if packet.metadata.depth.frame_index <= last_packet.metadata.depth.frame_index:
                raise ValueError('B02_NON_MONOTONIC_DEPTH_FRAME')
            a, b, result = processor(
                last_packet, packet, reference_mode='charuco',
                min_depth_m=min_depth_m, max_depth_m=max_depth_m,
                config=tracking_cfg, diagnostics=diagnostics)
            quality = result.quality.to_json()
            row.update(quality=quality, object_points=[a.selected_points, b.selected_points],
                       isolation_status=[a.source_ref['isolation_status'],
                                         b.source_ref['isolation_status']],
                       registration_backend=result.backend,
                       pose_source='B01_ICP_WITH_FT058_CHARUCO_BOARD_SEED',
                       diagnostics=diagnostics)
            if not result.accepted or result.T_world_depth_1 is None:
                # A truly stationary frame is not a LOST event and adds no
                # trajectory step. Keep the last accepted reference.
                reasons = result.quality.reject_reasons
                if reasons == ('NO_DISTINCT_VIEW_MOTION',):
                    record(dict(row, status='HELD_STATIONARY',
                                accepted_for_trajectory=False, T_world_depth=None,
                                reject_code='NO_DISTINCT_VIEW_MOTION'))
                    continue
                reason = '|'.join(reasons) or 'B02_POSE_REJECTED'
                record(dict(row, status='LOST', accepted_for_trajectory=False,
                            T_world_depth=None, reject_code=reason))
                lost = True
                continue
            edge = result.T_world_depth_1  # maps CURRENT depth -> PREVIOUS depth
            if not _is_se3(edge):
                raise ValueError('B02_POSE_NOT_SE3')
            candidate = world_pose @ edge   # maps CURRENT depth -> ANCHOR depth
            if not _is_se3(candidate):
                raise ValueError('B02_CHAIN_NOT_SE3')
            world_pose = candidate
            accepted += 1
            last_packet = packet
            record(dict(row, status='TRACKING', accepted_for_trajectory=True,
                        T_world_depth=world_pose.tolist(),
                        T_prev_depth_from_curr_depth=edge.tolist()))
        except (ValueError, RuntimeError, TypeError) as exc:
            # No pose is emitted on ChArUco failure, unsupported calibration,
            # poor geometry, native error or source contract violation.
            code = str(getattr(exc, 'code', None) or str(exc).split(':')[0] or type(exc).__name__)
            record(dict(row, status='LOST', accepted_for_trajectory=False,
                        T_world_depth=None, reject_code=code, quality=None,
                        diagnostics=diagnostics))
            lost = True
    return {
        'schema': 'scantopath.ft08.17.sampled_pose_sequence.v1',
        'status': ('LOST' if lost else 'INSUFFICIENT_MOTION' if accepted < 2 else 'TRACKING'),
        'trajectory_frame': 'depth_optical_of_sample_0',
        'matrix_convention': 'T_A_B maps coordinates B into A; column homogeneous vectors',
        'units': 'm',
        'method': 'FT05.8_CHARUCO + B01_BOUNDED_ICP',
        'tracking_mode': 'SAMPLED_NEW_RAW_KEYFRAMES_OFFLINE_CPU',
        'live_preview_tracking_claimed': False,
        'ft061_optical_flow_claimed': False,
        'recovery_implemented': False,
        'fusion_implemented': False,
        'metric_accuracy_verified': False,
        'robot_executable': False,
        'source_frame_count': len(packets),
        'accepted_poses': accepted,
        'rejected_or_untracked_frames': len(packets) - accepted,
        'registration_config': asdict(tracking_cfg),
        'frames': rows,
    }
