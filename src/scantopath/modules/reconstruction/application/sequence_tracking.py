"""FT-09.18/19: quality classification and bounded keyframe recovery for FT-08.17.

Reuses FT-05.8 ChArUco, B-01 ICP, adaptive voxel and FT-08.17 RAW evidence.
Does NOT estimate poses from an untrusted frame, interpolate trajectories,
continue previous camera pose as a new measurement, or change camera/Qt/SQLite.
Offline sampled-keyframe tracking only; not real-time 6DoF odometry.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from math import isfinite
from typing import Callable

import numpy as np

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.modules.reconstruction.application.contracts import RegistrationConfig
from scantopath.modules.reconstruction.application.live_pair import (
    process_live_pair, validate_live_pair,
)


@dataclass(frozen=True)
class TrackingQualityPolicy:
    """Conservative state policy; NEVER overrides B-01 geometric acceptance."""

    degraded_frames_before_lost: int = 2
    max_recovery_references: int = 3
    stationary_translation_m: float = .006
    stationary_rotation_deg: float = 1.0
    stationary_min_overlap: float = .50
    stationary_max_rmse_m: float = .006

    def __post_init__(self):
        if (not 1 <= self.degraded_frames_before_lost <= 5 or
                not 1 <= self.max_recovery_references <= 5 or
                not 0 < self.stationary_translation_m < .03 or
                not 0 < self.stationary_rotation_deg < 3.0 or
                not 0 < self.stationary_min_overlap <= 1.0 or
                not 0 < self.stationary_max_rmse_m <= .009):
            raise ValueError('FT09_POLICY_INVALID')


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


def _exception_code(exc: Exception) -> str:
    return str(getattr(exc, 'code', None) or str(exc).split(':')[0] or type(exc).__name__)[:120]


def _quality_dict(result) -> dict:
    data = result.quality.to_json()
    return dict(data) if isinstance(data, dict) else {}


def _is_stationary(result, policy: TrackingQualityPolicy) -> bool:
    """Only a B-01-validated pair may be held as stationary.

    Exact-zero movement is rejected by B-01's distinct-view demonstration gate.
    Such a rejection is stationary ONLY when it is the sole failure reason.
    An accepted near-zero edge must additionally have well-supported geometry.
    """
    q = result.quality
    reasons = tuple(q.reject_reasons)
    if not result.accepted:
        return reasons == ('NO_DISTINCT_VIEW_MOTION',)
    if result.T_world_depth_1 is None or not _is_se3(result.T_world_depth_1):
        return False
    T = np.asarray(result.T_world_depth_1, dtype=np.float64)
    translation = float(np.linalg.norm(T[:3, 3]))
    angle = float(np.degrees(np.arccos(np.clip((np.trace(T[:3, :3])-1.)/2., -1., 1.))))
    rmse = getattr(q, 'inlier_rmse_m', None)
    overlap = getattr(q, 'overlap', None)
    inliers = getattr(q, 'inlier_count', None)
    # B-01's accepted flag already enforces min_correspondences and degeneracy;
    # this extra classification only avoids generating redundant keyframes.
    return bool(translation < policy.stationary_translation_m and
                angle < policy.stationary_rotation_deg and
                type(overlap) in (float, int) and isfinite(overlap) and
                overlap >= policy.stationary_min_overlap and
                type(rmse) in (float, int) and isfinite(rmse) and
                rmse <= policy.stationary_max_rmse_m and
                (inliers is None or inliers >= 80))


def track_sequence(
    packets: list[RawRgbdCapture], *,
    config: RegistrationConfig | None = None,
    min_depth_m: float = .30,
    max_depth_m: float = 1.20,
    pair_processor: Callable | None = None,
    on_event: Callable[[dict], None] | None = None,
    quality_policy: TrackingQualityPolicy | None = None,
) -> dict:
    """Chain accepted measured poses and retry failed intervals against trusted keyframes.

    A rejected frame NEVER becomes a reference; LOST does not stop input.
    Reference world transforms are saved only for accepted keyframes. ChArUco
    seed, isolation, ICP, board/ICP consistency are all B-01's existing gates.
    """
    if not isinstance(packets, list) or not 2 <= len(packets) <= 96:
        raise ValueError('B02_SEQUENCE_LENGTH_INVALID: expected 2..96 frames')
    if not (isfinite(min_depth_m) and isfinite(max_depth_m)
            and 0 < min_depth_m < max_depth_m < 50):
        raise ValueError('B02_DEPTH_RANGE_INVALID')
    if any(not isinstance(packet, RawRgbdCapture) or not packet.metadata.measured
           for packet in packets):
        raise ValueError('B02_MEASURED_RAW_REQUIRED')
    policy = quality_policy or TrackingQualityPolicy()
    if not isinstance(policy, TrackingQualityPolicy):
        raise ValueError('FT09_POLICY_INVALID')

    # B-01 distinct motion is a demonstration requirement, not a tracking gate.
    # All ICP/degeneracy/ChArUco thresholds remain exactly as in B-01.
    base = config or RegistrationConfig()
    tracking_cfg = replace(base, min_distinct_view_translation_m=1e-6,
                           min_distinct_view_rotation_deg=1e-5)
    processor = pair_processor or process_live_pair
    rows: list[dict] = []

    def record(row: dict) -> None:
        rows.append(row)
        if on_event is not None:
            on_event(dict(row))

    ident = np.eye(4, dtype=np.float64)
    # (sample index, immutable RAW, verified T_world_from_depth)
    keyframes: list[tuple[int, RawRgbdCapture, np.ndarray]] = [(0, packets[0], ident)]
    record(dict(_frame_id(packets[0], 0), status='ANCHOR',
                T_world_depth=ident.tolist(), accepted_for_trajectory=True,
                pose_origin='identity_anchor_depth_optical', quality=None))

    accepted = 1
    failures = 0
    state = 'TRACKING'
    recovery_attempt_count = 0
    recovered_count = 0
    stationary_count = 0
    degraded_count = 0
    lost_count = 0
    prev_source = packets[0]

    for i in range(1, len(packets)):
        packet = packets[i]
        base_row = _frame_id(packet, i)
        attempts: list[dict] = []
        selected = None
        last_quality = None
        last_diagnostics = {}
        reject_code = 'NO_VERIFIED_POSE'
        hard_source_failure = False

        # Validate against both the preceding RAW and fixed source anchor.
        # A skipped/bad sample cannot make a later chronology check disappear.
        try:
            validate_live_pair(packets[0], packet)
            if (packet.metadata.depth.frame_index <= prev_source.metadata.depth.frame_index
                    or packet.metadata.depth.timestamp_us <= prev_source.metadata.depth.timestamp_us):
                raise ValueError('B02_NON_MONOTONIC_DEPTH_FRAME')
        except (RuntimeError, ValueError, TypeError) as exc:
            hard_source_failure = True
            reject_code = _exception_code(exc)
        prev_source = packet

        if not hard_source_failure:
            # Normal tracking: latest accepted keyframe. After failure,
            # attempt bounded relocalization newest -> older trusted keyframes.
            references = keyframes[-1:] if failures == 0 else keyframes[-policy.max_recovery_references:][::-1]
            for ref_index, ref_packet, ref_world in references:
                diagnostic = {}
                recovery_attempt_count += int(failures > 0)
                try:
                    validate_live_pair(ref_packet, packet)
                    a, b, result = processor(
                        ref_packet, packet, reference_mode='charuco',
                        min_depth_m=min_depth_m, max_depth_m=max_depth_m,
                        config=tracking_cfg, diagnostics=diagnostic)
                    quality = _quality_dict(result)
                    last_quality, last_diagnostics = quality, diagnostic
                    reasons = tuple(result.quality.reject_reasons)
                    attempt = {'reference_sample_index': ref_index,
                               'reference_capture_id': ref_packet.metadata.capture_id,
                               'overlap': quality.get('overlap'),
                               'rmse_m': quality.get('inlier_rmse_m'),
                               'inlier_count': quality.get('inlier_count'),
                               'reject_reasons': list(reasons)}
                    if _is_stationary(result, policy):
                        # A stationary pair still has a trusted reference and
                        # must not shift world frame or add a duplicate keyframe.
                        attempt['decision'] = 'STATIONARY'
                        attempts.append(attempt)
                        selected = (ref_index, ref_packet, ref_world, a, b, result,
                                    diagnostic, quality, None, 'STATIONARY')
                        break
                    if not result.accepted or result.T_world_depth_1 is None:
                        reject_code = '|'.join(reasons) or 'B02_POSE_REJECTED'
                        attempt['decision'] = 'REJECT'
                        attempts.append(attempt)
                        continue
                    if not _is_se3(result.T_world_depth_1):
                        raise ValueError('B02_POSE_NOT_SE3')
                    candidate = ref_world @ np.asarray(result.T_world_depth_1, dtype=np.float64)
                    if not _is_se3(candidate):
                        raise ValueError('B02_CHAIN_NOT_SE3')
                    attempt['decision'] = 'ACCEPT'
                    attempts.append(attempt)
                    selected = (ref_index, ref_packet, ref_world, a, b, result,
                                diagnostic, quality, candidate, 'POSE')
                    break
                except (RuntimeError, ValueError, TypeError) as exc:
                    reject_code = _exception_code(exc)
                    attempts.append({'reference_sample_index': ref_index,
                                     'reference_capture_id': ref_packet.metadata.capture_id,
                                     'decision': 'ERROR', 'reject_code': reject_code})
                    # Invalid SE3 is a hard rejection, NEVER fall back to a
                    # different keyframe to rescue untrusted numeric transforms.
                    if reject_code in ('B02_POSE_NOT_SE3', 'B02_CHAIN_NOT_SE3'):
                        hard_source_failure = True
                        break

        if selected is not None:
            ref_i, ref_packet, ref_world, a, b, result, diag, quality, world, kind = selected
            info = dict(base_row,
                        quality=quality,
                        object_points=[a.selected_points, b.selected_points],
                        isolation_status=[a.source_ref['isolation_status'],
                                          b.source_ref['isolation_status']],
                        registration_backend=result.backend,
                        pose_source='B01_ICP_WITH_FT058_CHARUCO_BOARD_SEED',
                        diagnostics=diag,
                        reference_sample_index=ref_i,
                        reference_capture_id=ref_packet.metadata.capture_id,
                        recovery_attempts=attempts)
            if kind == 'STATIONARY':
                stationary_count += 1
                failures = 0
                state = 'STATIONARY'
                record(dict(info, status='STATIONARY', accepted_for_trajectory=False,
                            T_world_depth=None, reject_code=None,
                            disposition='SKIP_REDUNDANT_MEASURED_FRAME'))
                continue

            was_recovery = failures > 0
            failures = 0
            state = 'TRACKING'
            accepted += 1
            if was_recovery:
                recovered_count += 1
            keyframes.append((i, packet, world))
            row = dict(info,
                       status='RECOVERED' if was_recovery else 'TRACKING',
                       accepted_for_trajectory=True,
                       T_world_depth=world.tolist(),
                       T_reference_depth_from_curr_depth=result.T_world_depth_1.tolist(),
                       reject_code=None)
            # Historical field is correct only for adjacent accepted samples.
            if ref_i == i - 1:
                row['T_prev_depth_from_curr_depth'] = result.T_world_depth_1.tolist()
            record(row)
            continue

        failures += 1
        state = ('LOST' if hard_source_failure or
                 failures >= policy.degraded_frames_before_lost else 'DEGRADED')
        if state == 'LOST':
            lost_count += 1
        else:
            degraded_count += 1
        record(dict(base_row, status=state, accepted_for_trajectory=False,
                    T_world_depth=None, reject_code=reject_code,
                    quality=last_quality, diagnostics=last_diagnostics,
                    recovery_attempts=attempts,
                    last_trusted_sample_index=keyframes[-1][0],
                    disposition='DO_NOT_PUBLISH_UNTRUSTED_POSE'))

    if state == 'LOST':
        final = 'LOST'
    elif state == 'DEGRADED':
        final = 'DEGRADED'
    elif accepted == 1:
        final = 'STATIONARY' if stationary_count else 'INSUFFICIENT_MOTION'
    else:
        final = 'TRACKING'  # latest good pose, even if stationary after it

    return {
        'schema': 'scantopath.ft08.17.sampled_pose_sequence.v1',
        'ft09_extension': 'scantopath.ft09.quality_recovery.v1',
        'status': final,
        'trajectory_frame': 'depth_optical_of_sample_0',
        'matrix_convention': 'T_A_B maps coordinates B into A; column homogeneous vectors',
        'units': 'm',
        'method': 'FT05.8_CHARUCO + B01_BOUNDED_ICP + FT09_QUALITY_RECOVERY',
        'tracking_mode': 'SAMPLED_NEW_RAW_KEYFRAMES_OFFLINE_CPU',
        'live_preview_tracking_claimed': False,
        'ft061_optical_flow_claimed': False,
        'recovery_implemented': True,
        'fusion_implemented': False,
        'metric_accuracy_verified': False,
        'robot_executable': False,
        'source_frame_count': len(packets),
        'accepted_poses': accepted,
        'rejected_or_untracked_frames': len(packets) - accepted,
        'recovered_poses': recovered_count,
        'stationary_frames': stationary_count,
        'degraded_frames': degraded_count,
        'lost_frames': lost_count,
        'recovery_pair_attempts': recovery_attempt_count,
        'quality_policy': asdict(policy),
        'registration_config': asdict(tracking_cfg),
        'frames': rows,
    }
