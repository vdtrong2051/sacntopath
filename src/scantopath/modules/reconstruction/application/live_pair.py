"""FT-08.16 live Gemini 2 pair registration without Project/SQLite/previous RAW.

Capture snapshots are real, newly acquired RAW-v2 payloads, held in memory until
written as separate standalone evidence outside the official RAW store.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Any

import numpy as np

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.modules.reconstruction.application.contracts import (
    InputCloud, RegistrationConfig, RegistrationError, TwoViewResult,
)
from scantopath.modules.reconstruction.application.two_view_registration import register_two_views


@dataclass(frozen=True)
class LivePairView:
    cloud: InputCloud
    source_ref: dict[str, Any]
    roi_xyxy: tuple[int, int, int, int]
    selected_points: int
    board_pose_C_B: np.ndarray | None = None


def validate_live_pair(packet0: RawRgbdCapture, packet1: RawRgbdCapture) -> None:
    if not isinstance(packet0, RawRgbdCapture) or not isinstance(packet1, RawRgbdCapture):
        raise RegistrationError('LIVE_CAPTURE_INVALID', 'Camera did not provide two RAW-v2 packets')
    a, b = packet0.metadata, packet1.metadata
    if (a.capture_id == b.capture_id or
            (a.color.frame_index, a.depth.frame_index) == (b.color.frame_index, b.depth.frame_index)):
        raise RegistrationError('DUPLICATE_FRAME', 'Capture two genuinely distinct frames')
    if a.session_id != b.session_id or a.specimen_id != b.specimen_id:
        raise RegistrationError('LIVE_CONTEXT_MISMATCH', 'Live pair belongs to different temporary contexts')
    if a.kind != b.kind or not (a.measured and b.measured):
        raise RegistrationError('NOT_SENSOR_MEASURED', 'Both live views must contain measured sensor depth')
    if (a.device.name != b.device.name or a.device.pid != b.device.pid or
            (a.device.serial and b.device.serial and a.device.serial != b.device.serial)):
        raise RegistrationError('CAMERA_CHANGED', 'The two views were not captured by the same device')
    if (a.depth.width != b.depth.width or a.depth.height != b.depth.height or
            a.alignment_mode != 'disabled' or b.alignment_mode != 'disabled'):
        raise RegistrationError('CAMERA_GRID_CHANGED', 'Native depth grid or alignment changed')
    if (a.depth_intrinsics != b.depth_intrinsics or a.depth_distortion != b.depth_distortion or
            a.depth_scale_m_per_unit != b.depth_scale_m_per_unit):
        raise RegistrationError('CALIBRATION_CHANGED', 'Live per-frame geometry calibration changed')


def _region(packet: RawRgbdCapture, requested: tuple[int, int, int, int] | None):
    m = packet.metadata
    w, h = m.depth.width, m.depth.height
    # Center crop is only a starting diagnostic; NOT proven object segmentation.
    if requested is None:
        result = (int(w * .18), int(h * .18), int(w * .82), int(h * .82))
        roi_mode = 'CENTER_CROP_PROVISIONAL'
    else:
        result = requested
        roi_mode = 'MANUAL_DEPTH_GRID'
    x0, y0, x1, y1 = result
    if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
        raise RegistrationError('ROI_OUTSIDE_DEPTH_GRID', 'ROI must be native depth pixels xyxy')
    return result, roi_mode


def _calibration_from_raw(metadata):
    """Bridge existing RAW v2 numeric calibration into the FT-05.8 live DTO.

    No inferred calibration, pixel-grid resampling, or change to RAW.
    """
    from scantopath.modules.capture.application.live_calibration import (
        LiveCalibrationSnapshot, LiveDistortion, LiveIntrinsics,
    )

    def intr(source):
        return LiveIntrinsics(source.width, source.height,
                              float(source.fx), float(source.fy),
                              float(source.cx), float(source.cy))

    def dist(source):
        return LiveDistortion(int(source.sdk_model),
                              tuple(float(x) for x in source.k1_k6_p1_p2))

    return LiveCalibrationSnapshot(
        depth_intrinsics=intr(metadata.depth_intrinsics),
        color_intrinsics=intr(metadata.color_intrinsics),
        depth_distortion=dist(metadata.depth_distortion),
        color_distortion=dist(metadata.color_distortion),
        rotation_C_D=tuple(float(x) for x in metadata.depth_to_color.rotation),
        translation_C_D_m=tuple(float(x)/1000. for x in metadata.depth_to_color.translation_mm),
        depth_scale_m_per_unit=float(metadata.depth_scale_m_per_unit),
    )


def _board_T_color_from_board(pose):
    R, t = pose[:2]
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = np.asarray(R, dtype=np.float64)
    T[:3, 3] = np.asarray(t, dtype=np.float64).reshape(3)
    return T


def _camera_T_color_from_depth(metadata):
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = np.asarray(metadata.depth_to_color.rotation, dtype=np.float64).reshape(3,3)
    T[:3, 3] = np.asarray(metadata.depth_to_color.translation_mm, dtype=np.float64) / 1000.
    return T


def _charuco_initial_depth1_to_depth0(meta0, meta1, view0, view1):
    """Stationary board only: T_D0_D1 = T_D0_B @ inv(T_D1_B).

    Neither board pose nor ICP result is a verified robot/world metrology pose.
    """
    def depth_from_board(metadata, view):
        return np.linalg.solve(_camera_T_color_from_depth(metadata), view.board_pose_C_B)
    return depth_from_board(meta0, view0) @ np.linalg.inv(depth_from_board(meta1, view1))


def cloud_from_live_packet(packet: RawRgbdCapture, *,
                           roi: tuple[int, int, int, int] | None,
                           min_depth_m: float,
                           max_depth_m: float,
                           reference_mode: str = 'charuco') -> LivePairView:
    """Reuse FT-05.8/FT-05.7 object masks before B-01 ICP.

    NO default center crop masquerading as object isolation; fail closed when
    the requested existing detector cannot identify a supported object.
    """
    if reference_mode not in ('charuco', 'depth'):
        raise RegistrationError('REFERENCE_MODE_INVALID', 'Expected charuco or depth')
    if not (0 < min_depth_m < max_depth_m < 50):
        raise RegistrationError('DEPTH_RANGE_INVALID', 'Expected a positive depth interval in metres')
    if not isinstance(packet, RawRgbdCapture) or not packet.metadata.measured:
        raise RegistrationError('LIVE_CAPTURE_INVALID', 'Expected measured Gemini RAW-v2 payload')

    from scantopath.modules.capture.application.decoding import RgbdDecoder
    from scantopath.modules.capture.infrastructure.jpeg_codec import PillowMjpegDecoder
    from scantopath.modules.geometry.application.service import GeometryService
    decoded = RgbdDecoder(PillowMjpegDecoder()).decode(packet)
    m = packet.metadata
    payload_hashes = {
        'color.mjpg': sha256(packet.color_mjpeg).hexdigest(),
        'depth.y16': sha256(packet.depth_y16_le).hexdigest(),
    }
    geo = GeometryService.process(
        depth_u16=decoded.depth_u16,
        color_rgb=decoded.color_rgb,
        metadata=m,
        capture_id=m.capture_id,
        source_raw_sha256=payload_hashes,
    )
    calibration = _calibration_from_raw(m)
    if roi is None:
        roi_actual = (0, 0, m.depth.width, m.depth.height)
        roi_source = 'FULL_DEPTH_GRID_FOR_EXISTING_OBJECT_ISOLATION'
    else:
        roi_actual, roi_source = _region(packet, roi)
    x0, y0, x1, y1 = roi_actual
    roi_xywh = (x0, y0, x1-x0, y1-y0)

    board_pose = None
    if reference_mode == 'charuco':
        from scantopath.modules.geometry.application.live_charuco_isolation import (
            isolate_charuco_object, detect_charuco_pose,
        )
        pose_holder = {}
        def detected_pose(rgb, cal, cfg, *, timestamp_us):
            pose = detect_charuco_pose(rgb, cal, cfg)
            if isinstance(pose, tuple):
                pose_holder['board_pose'] = pose
            return pose, 'detected', 0
        isolated = isolate_charuco_object(
            decoded.color_rgb, decoded.depth_u16, calibration,
            depth_roi=roi_xywh, pose_provider=detected_pose,
            timestamp_us=int(m.color.timestamp_us),
        )
        if isolated.usable and 'board_pose' not in pose_holder:
            raise RegistrationError('CHARUCO_POSE_MISSING', 'FT-05.8 mask has no measured board pose')
        if isolated.usable:
            board_pose = _board_T_color_from_board(pose_holder['board_pose'])
    else:
        from scantopath.modules.geometry.application.live_object_isolation import isolate_object_depth
        isolated = isolate_object_depth(
            decoded.depth_u16, float(m.depth_scale_m_per_unit),
            calibration.depth_intrinsics, depth_roi=roi_xywh,
        )
    if not isolated.usable:
        raise RegistrationError(isolated.status,
            'Existing FT-05.8/FT-05.7 object isolation rejected this frame; do not register scene/background')
    if isolated.object_mask.dtype != np.bool_ or isolated.object_mask.shape != decoded.depth_u16.shape:
        raise RegistrationError('OBJECT_MASK_INVALID', 'Invalid native Depth mask from existing isolation')

    points, uv = geo.points_xyz_m, geo.depth_source_uv
    selected = (isolated.object_mask[uv[:, 1], uv[:, 0]] &
                (points[:, 2] >= min_depth_m) & (points[:, 2] <= max_depth_m))
    xyz = np.array(points[selected], dtype=np.float64, order='C', copy=True)
    uv_selected = np.array(uv[selected], dtype=np.int32, order='C', copy=True)
    if len(xyz) < 350:
        raise RegistrationError('TOO_FEW_OBJECT_POINTS', 'FT-05.8/FT-05.7 isolated object has fewer than 350 measured Depth points')
    source_ref = {
        'capture_id': m.capture_id,
        'session_id': m.session_id,
        'specimen_id': m.specimen_id,
        'source_origin': 'NEW_DIRECT_GEMINI2_LIVE_CAPTURE',
        'registered_in_project_store': False,
        'sensor_measured': True,
        'source_kind': 'MEASURED_RAW',
        'world_pose_estimated': True,
        'metric_accuracy_verified': False,
        'camera_name': m.device.name,
        'camera_pid': m.device.pid,
        'color_frame_index': int(m.color.frame_index),
        'depth_frame_index': int(m.depth.frame_index),
        'color_timestamp_us': int(m.color.timestamp_us),
        'depth_timestamp_us': int(m.depth.timestamp_us),
        'timestamp_domain': str(m.timestamp_domain),
        'depth_scale_m_per_unit': float(m.depth_scale_m_per_unit),
        'alignment_mode': str(m.alignment_mode),
        'calibration_fingerprint': geo.calibration_fingerprint,
        'ft058_calibration_fingerprint': calibration.fingerprint,
        'native_depth_grid_wh': [int(m.depth.width), int(m.depth.height)],
        'native_color_grid_wh': [int(m.color.width), int(m.color.height)],
        'source_raw_sha256': payload_hashes,
        'roi_xyxy_depth_grid': list(roi_actual),
        'roi_source': roi_source,
        'depth_range_m': [float(min_depth_m), float(max_depth_m)],
        'selected_measured_points': int(len(xyz)),
        'isolation_source': ('FT-05.8_CHARUCO' if reference_mode == 'charuco'
                             else 'FT-05.7_DEPTH_GEOMETRIC'),
        'isolation_status': isolated.status,
        'isolation_mask_sha256': sha256(isolated.object_mask.tobytes()).hexdigest(),
        'isolation_mask_selected_pixels': int(isolated.selected_pixels),
        'board_pose_source': 'detected' if board_pose is not None else 'not_applicable',
        'board_pose_color_from_board': board_pose.tolist() if board_pose is not None else None,
        'board_corners': int(isolated.corner_count) if board_pose is not None else None,
        'board_reprojection_px': float(isolated.reprojection_px) if board_pose is not None else None,
        'board_support_fraction': float(isolated.support_fraction) if board_pose is not None else None,
        'depth_enhancement_mode': 'off',
        'semantic_object_identity_verified': False,
    }
    return LivePairView(
        cloud=InputCloud(m.capture_id, xyz, geo.calibration_fingerprint,
                         tuple(sorted(payload_hashes.items())), uv_selected),
        source_ref=source_ref,
        roi_xyxy=roi_actual,
        selected_points=len(xyz),
        board_pose_C_B=board_pose,
    )

def _adaptive_object_registration_config(view0: LivePairView, view1: LivePairView,
                                         config: RegistrationConfig,
                                         diagnostics: dict[str, Any] | None = None
                                         ) -> RegistrationConfig:
    """Change only ICP sampling resolution, not ChArUco/Depth masks or quality gates.

    A valid small object can have thousands of measured Depth pixels but <80
    distinct 20-mm voxel cells. Preserve >= config.min_correspondences at the
    coarse scale, or BLOCK; never decrease min correspondences to force ACCEPT.
    """
    from scantopath.modules.reconstruction.application.two_view_registration import _voxel_representatives

    # Keep operator-supplied registration scales untouched if the default coarse
    # setting is already viable. Restrict automatic refinement to smaller scales.
    coarse = float(config.voxel_scales_m[0])
    candidates = tuple(dict.fromkeys((coarse, *(
        v for v in (0.015, 0.010, 0.0075, 0.005)
        if v < coarse - 1e-12
    ))))
    measurements = []
    chosen = None
    for step in candidates:
        counts = [int(len(_voxel_representatives(v.cloud.xyz_depth_m, step,
                          config.min_correspondences))) for v in (view0, view1)]
        measurements.append({'voxel_m': step, 'view0_voxels_at_least': counts[0],
                             'view1_voxels_at_least': counts[1]})
        if min(counts) >= config.min_correspondences:
            chosen = step
            break

    if diagnostics is not None:
        diagnostics['isolation_source'] = [v.source_ref['isolation_source'] for v in (view0, view1)]
        diagnostics['isolation_status'] = [v.source_ref['isolation_status'] for v in (view0, view1)]
        diagnostics['selected_measured_points'] = [v.selected_points for v in (view0, view1)]
        diagnostics['object_bounds_m'] = [
            np.round(np.ptp(v.cloud.xyz_depth_m, axis=0), 5).tolist() for v in (view0, view1)
        ]
        diagnostics['board_corners'] = [v.source_ref.get('board_corners') for v in (view0, view1)]
        diagnostics['voxel_candidates_tested'] = measurements
        diagnostics['required_min_correspondences'] = config.min_correspondences

    if chosen is None:
        raise RegistrationError('TOO_FEW_OBJECT_VOXELS',
            'FT-05 object mask retained measured points but fewer than '
            f'{config.min_correspondences} distinct voxel cells even at 5 mm; '
            'inspect board footprint, measured object extent and Depth range. '
            'The ICP minimum was NOT relaxed.')

    if chosen == coarse:
        updated = config
    else:
        finer = min(config.voxel_scales_m[1], max(0.6 * chosen, config.voxel_scales_m[-1]))
        finest = min(config.voxel_scales_m[-1], finer)
        scales = (chosen, finer, finest)
        thresholds = (min(config.correspondences_m[0], max(2.5 * chosen,
                      config.correspondences_m[-1])),
                      min(config.correspondences_m[1], max(2.5 * finer,
                      config.correspondences_m[-1])), config.correspondences_m[-1])
        updated = replace(config, voxel_scales_m=scales, correspondences_m=thresholds)

    summary = {
        'icp_voxel_scales_m': list(updated.voxel_scales_m),
        'icp_correspondences_m': list(updated.correspondences_m),
        'adaptive_voxel': chosen != coarse,
        'icp_min_correspondences_unchanged': updated.min_correspondences,
    }
    view0.source_ref.update(summary)
    view1.source_ref.update(summary)
    if diagnostics is not None:
        diagnostics.update(summary)
    return updated


def process_live_pair(packet0: RawRgbdCapture, packet1: RawRgbdCapture, *,
                      roi0: tuple[int, int, int, int] | None = None,
                      roi1: tuple[int, int, int, int] | None = None,
                      min_depth_m: float = .30,
                      max_depth_m: float = 1.20,
                      reference_mode: str = 'charuco',
                      config: RegistrationConfig | None = None,
                      diagnostics: dict[str, Any] | None = None,
                      effective_config: dict[str, RegistrationConfig] | None = None,
                      ) -> tuple[LivePairView, LivePairView, TwoViewResult]:
    validate_live_pair(packet0, packet1)
    a = cloud_from_live_packet(packet0, roi=roi0, min_depth_m=min_depth_m,
                               max_depth_m=max_depth_m, reference_mode=reference_mode)
    b = cloud_from_live_packet(packet1, roi=roi1, min_depth_m=min_depth_m,
                               max_depth_m=max_depth_m, reference_mode=reference_mode)
    initial = None
    if reference_mode == 'charuco':
        initial = _charuco_initial_depth1_to_depth0(packet0.metadata, packet1.metadata, a, b)
        if not np.isfinite(initial).all() or not np.allclose(initial[3], [0,0,0,1]):
            raise RegistrationError('BOARD_SEED_INVALID', 'Invalid ChArUco relative pose')
        a.source_ref['board_seed_policy'] = 'FT05.8_DETECTED_BOARD_STATIC_TWO_VIEW'
        b.source_ref['board_seed_T_depth0_from_depth1'] = initial.tolist()
        b.source_ref['board_seed_is_estimated_not_metric_verified'] = True
    cfg = _adaptive_object_registration_config(a, b, config or RegistrationConfig(), diagnostics)
    if effective_config is not None:
        effective_config['config'] = cfg
    result = register_two_views(a.cloud, b.cloud, cfg, initial_T_world_depth1=initial)
    if reference_mode == 'charuco' and result.accepted:
        # Independent consistency check: registration must remain near the
        # measured stationary-board estimate. Fail closed when ICP diverges.
        from dataclasses import replace
        from math import acos, degrees
        delta = np.linalg.solve(initial, result.T_world_depth_1)
        pos_error = float(np.linalg.norm(delta[:3, 3]))
        rot_error = degrees(acos(float(np.clip((np.trace(delta[:3,:3])-1)/2,-1,1))))
        b.source_ref['board_icp_residual_translation_m'] = pos_error
        b.source_ref['board_icp_residual_rotation_deg'] = rot_error
        if pos_error > 0.045 or rot_error > 12.0:
            quality = replace(result.quality, accepted=False,
                              reject_reasons=(*result.quality.reject_reasons,
                                              'CHARUCO_ICP_POSE_INCONSISTENT'))
            result = TwoViewResult(quality, result.T_world_depth_0,
                                   None, None, None, result.backend)
    return a, b, result
