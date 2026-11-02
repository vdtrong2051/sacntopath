"""Two-tier ChArUco-guided offline tracking, sharing a verified board frame.

Each tier runs FT-09 independently; the second tier's local poses are mapped into
first-tier optical coordinates using independently detected static-board anchors.
No fabricated pose, re-use of a lost frame, or geometric orientation guessing.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

import numpy as np

from scantopath.modules.reconstruction.application.sequence_tracking import _is_se3


class TwoTierError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class TierPolicy:
    first_max: int = 48
    second_max: int = 48
    min_each: int = 2
    max_total: int = 96


def board_depth_transform(packet) -> np.ndarray:
    """Measured depth-camera <- stationary ChArUco board (one RAW packet)."""
    from scantopath.modules.reconstruction.application.live_pair import (
        cloud_from_live_packet, _camera_T_color_from_depth,
    )
    view = cloud_from_live_packet(packet, roi=None, min_depth_m=.30,
                                  max_depth_m=1.20, reference_mode='charuco')
    if view.board_pose_C_B is None:
        raise TwoTierError('TWO_TIER_BOARD_ANCHOR_MISSING')
    transform = np.linalg.solve(_camera_T_color_from_depth(packet.metadata),
                                view.board_pose_C_B)
    if not _is_se3(transform):
        raise TwoTierError('TWO_TIER_BOARD_ANCHOR_INVALID')
    return transform


def track_two_tier(packets, split_index: int, *,
                   tracker: Callable | None = None,
                   board_provider: Callable | None = None,
                   on_event: Callable | None = None) -> dict:
    """Track 2 tiers independently and bridge their anchors via static ChArUco.

    The returned format remains FT-09's proven B02/FT10 tracking contract.
    A second-tier local anchor is converted into a measured board-aligned pose;
    accepted/rejected decisions of the two independent trackers are preserved.
    """
    p = TierPolicy()
    n = len(packets)
    if not (p.min_each <= split_index <= p.first_max and
            p.min_each <= n - split_index <= p.second_max and n <= p.max_total):
        raise TwoTierError('TWO_TIER_SAMPLE_BUDGET_INVALID')
    from scantopath.modules.reconstruction.application.live_pair import validate_live_pair
    # Cross-phase RAW identities, timestamps and device calibration must agree.
    validate_live_pair(packets[0], packets[split_index])
    all_ids = [x.metadata.capture_id for x in packets]
    if len(set(all_ids)) != n:
        raise TwoTierError('TWO_TIER_DUPLICATE_RAW')
    for first, second in zip(packets, packets[1:]):
        if (second.metadata.depth.timestamp_us <= first.metadata.depth.timestamp_us or
                second.metadata.depth.frame_index <= first.metadata.depth.frame_index):
            raise TwoTierError('TWO_TIER_NON_MONOTONIC_RAW')

    tracker = tracker or __import__(
        'scantopath.modules.reconstruction.application.sequence_tracking',
        fromlist=['track_sequence']).track_sequence
    board_provider = board_provider or board_depth_transform
    # Anchor provenance must be re-measured from both RAW frames, not assumed.
    anchor_first = np.asarray(board_provider(packets[0]), dtype=np.float64)
    anchor_second = np.asarray(board_provider(packets[split_index]), dtype=np.float64)
    if not _is_se3(anchor_first) or not _is_se3(anchor_second):
        raise TwoTierError('TWO_TIER_BOARD_ANCHOR_INVALID')
    world_second = anchor_first @ np.linalg.inv(anchor_second)
    if not _is_se3(world_second):
        raise TwoTierError('TWO_TIER_BOARD_BRIDGE_INVALID')

    first = tracker(list(packets[:split_index]))
    second = tracker(list(packets[split_index:]))
    if (first.get('source_frame_count') != split_index or
            second.get('source_frame_count') != n-split_index or
            not first.get('frames') or not second.get('frames') or
            first['frames'][0].get('status') != 'ANCHOR' or
            second['frames'][0].get('status') != 'ANCHOR'):
        raise TwoTierError('TWO_TIER_TRACKING_RECORD_INVALID')
    combined = deepcopy(first)
    rows = deepcopy(first['frames'])
    for local in second['frames']:
        row = deepcopy(local)
        old_index = int(row['sample_index'])
        row['sample_index'] = old_index+split_index
        row['tier'] = 2
        row['tier_local_index'] = old_index
        for field in ('reference_sample_index', 'last_trusted_sample_index'):
            if row.get(field) is not None:
                row[field] += split_index
        for attempt in row.get('recovery_attempts', []):
            if attempt.get('reference_sample_index') is not None:
                attempt['reference_sample_index'] += split_index
        if row.get('accepted_for_trajectory'):
            local_transform = np.asarray(row['T_world_depth'], dtype=np.float64)
            if not _is_se3(local_transform):
                raise TwoTierError('TWO_TIER_LOCAL_POSE_INVALID')
            converted = world_second @ local_transform
            if not _is_se3(converted):
                raise TwoTierError('TWO_TIER_GLOBAL_POSE_INVALID')
            row['T_world_depth'] = converted.tolist()
            if old_index == 0:
                row['status'] = 'TRACKING'
                row['pose_source'] = 'TWO_TIER_STATIC_CHARUCO_BOARD_BRIDGE'
                row['reference_sample_index'] = 0
                row['reference_capture_id'] = packets[0].metadata.capture_id
                row['T_reference_depth_from_curr_depth'] = converted.tolist()
        rows.append(row)
    for row in rows[:split_index]:
        row['tier'] = 1
        row['tier_local_index'] = row['sample_index']
    if len(rows) != n:
        raise TwoTierError('TWO_TIER_FRAME_COUNT_MISMATCH')
    combined['frames'] = rows
    combined['source_frame_count'] = n
    combined['accepted_poses'] = int(first['accepted_poses']+second['accepted_poses'])
    combined['rejected_or_untracked_frames'] = n-combined['accepted_poses']
    for key in ('recovered_poses', 'stationary_frames', 'degraded_frames',
                'lost_frames', 'recovery_pair_attempts'):
        combined[key] = int(first.get(key, 0)+second.get(key, 0))
    combined['status'] = second.get('status', 'DEGRADED')
    combined['two_tier'] = {
        'schema': 'scantopath.two_tier_tracking.v1',
        'board_static_required': True,
        'anchor_alignment': 'FT05.8_CHARUCO_TWO_INDEPENDENT_MEASURED_ANCHORS',
        'tier_1': {'start': 0, 'end_exclusive': split_index,
                   'frames': split_index, 'accepted_poses': int(first['accepted_poses']),
                   'tracking_status': first.get('status')},
        'tier_2': {'start': split_index, 'end_exclusive': n,
                   'frames': n-split_index, 'accepted_poses': int(second['accepted_poses']),
                   'tracking_status': second.get('status')},
        'T_world_from_tier2_depth_anchor': world_second.tolist(),
        'metric_accuracy_verified': False,
        'loop_closure_optimized': False,
    }
    # A single global trajectory with valid monotonic indices is necessary for FT10/C1.
    from scantopath.modules.reconstruction.application.multiview_accumulation import validated_trajectory
    validated_trajectory(combined)
    if on_event is not None:
        for row in rows:
            on_event(dict(row))
    return combined
