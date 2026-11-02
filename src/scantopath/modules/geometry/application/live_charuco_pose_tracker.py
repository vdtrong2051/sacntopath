"""FT-06.1 R2: bounded optical-flow continuation of measured ChArUco corners.

Research-grade visual pose estimate, NOT verified metrology. This module does
not hold/publish prior Point Clouds or change original RAW/camera acquisition.
Continuations must pass PnP, forward/back optical flow and downstream Depth
plane validation. Old poses are never silently used as current geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import cv2
import numpy as np

from .live_charuco_isolation import detect_charuco_pose, _camera_model


@dataclass(frozen=True)
class ContinuityPolicy:
    max_bridged_frames: int = 5
    max_gap_us: int = 600_000
    max_point_flow_px: float = 42.0
    max_flow_fb_px: float = 1.8
    max_pnp_rmse_px: float = 2.0
    max_translation_m: float = 0.12
    min_pose_cosine: float = 0.93
    min_tracked_corners: int = 7


class TemporalCharucoPoseTracker:
    """Owned by ONE Geometry worker; invoked on its processing thread only."""

    def __init__(self, policy: ContinuityPolicy | None = None):
        self.policy = policy or ContinuityPolicy()
        self.reset()

    def reset(self):
        self._gray = None
        self._pixels = None
        self._object = None
        self._pose = None
        self._time_us = None
        self._confirmed_us = None  # timestamp of last REAL ChArUco detector success
        self._age = 0
        self._fingerprint = None

    def estimate(self, rgb: np.ndarray, calibration, cfg, *, timestamp_us: int):
        """Return (pose_tuple_or_failure, source, continuation_age).

        pose tuple uses the exact original FT05.8 API (R,t,markers,corners,rmse).
        No new cloud or mask is ever synthesized by the tracker itself.
        """
        if (type(timestamp_us) is not int or timestamp_us < 0 or
                not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8 or
                rgb.ndim != 3 or rgb.shape[-1] != 3):
            self.reset()
            raise ValueError('CHARUCO_CONTINUITY_INPUT_INVALID')
        key = getattr(calibration, 'fingerprint', None)
        if key is None:  # synthetic calibration fixture, still generation-fenced by worker
            key = (calibration.color_intrinsics.width, calibration.color_intrinsics.height)
        if self._fingerprint is not None and self._fingerprint != key:
            self.reset()
        gray = cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2GRAY)
        captured = {}
        normal = detect_charuco_pose(rgb, calibration, cfg, feature_sink=captured)
        if isinstance(normal, tuple):
            self._gray = gray
            self._pixels = captured['image_points'].astype(np.float32).reshape(-1, 1, 2)
            self._object = captured['object_points'].astype(np.float32).reshape(-1, 3)
            self._pose = normal
            self._age = 0
            self._time_us = timestamp_us
            self._confirmed_us = timestamp_us
            self._fingerprint = key
            return normal, 'detected', 0

        # A camera/frame that lost the board completely may still carry tracked
        # image features. But it NEVER receives a frozen/old pose as live data.
        if (self._gray is None or self._pose is None or self._pixels is None or
                self._time_us is None or self._confirmed_us is None or
                timestamp_us <= self._time_us or
                timestamp_us - self._confirmed_us > self.policy.max_gap_us or
                self._age >= self.policy.max_bridged_frames or self._fingerprint != key):
            self.reset()
            return normal, 'none', 0
        continuation = self._optical_flow_pose(gray, calibration)
        if continuation is None:
            self.reset()
            return normal, 'none', 0
        pose, points, obj = continuation
        self._gray = gray
        self._pixels = points
        self._object = obj
        self._pose = pose
        self._time_us = timestamp_us
        self._age += 1
        return pose, 'optical_flow_estimate', self._age

    def _optical_flow_pose(self, gray: np.ndarray, calibration):
        policy = self.policy
        before = self._pixels
        after, status, _ = cv2.calcOpticalFlowPyrLK(
            self._gray, gray, before, None, winSize=(21, 21), maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 25, 0.02))
        if after is None or status is None:
            return None
        backward, back_status, _ = cv2.calcOpticalFlowPyrLK(
            gray, self._gray, after, None, winSize=(21, 21), maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 25, 0.02))
        if backward is None or back_status is None:
            return None
        movement = np.linalg.norm(after.reshape(-1, 2) - before.reshape(-1, 2), axis=1)
        fb = np.linalg.norm(backward.reshape(-1, 2) - before.reshape(-1, 2), axis=1)
        h, w = gray.shape
        xy = after.reshape(-1, 2)
        ok = ((status.reshape(-1) == 1) & (back_status.reshape(-1) == 1) &
              np.isfinite(xy).all(axis=1) & (movement < policy.max_point_flow_px) &
              (fb < policy.max_flow_fb_px) & (xy[:, 0] >= 0) & (xy[:, 0] < w) &
              (xy[:, 1] >= 0) & (xy[:, 1] < h))
        if np.count_nonzero(ok) < policy.min_tracked_corners:
            return None
        obj = self._object[ok].astype(np.float32)
        image = after[ok].astype(np.float32).reshape(-1, 1, 2)
        k, dist = _camera_model(calibration.color_intrinsics, calibration.color_distortion)
        try:
            accepted, rvec, tvec, inliers = cv2.solvePnPRansac(
                obj, image, k, dist, flags=cv2.SOLVEPNP_ITERATIVE,
                iterationsCount=70, reprojectionError=2.4, confidence=0.995)
            if not accepted or inliers is None or len(inliers) < policy.min_tracked_corners:
                return None
            idx = inliers.reshape(-1)
            obj, image = obj[idx], image[idx]
            # Refine against inlier correspondences, preserving optical-flow seed.
            refined, rvec, tvec = cv2.solvePnP(
                obj, image, k, dist, rvec, tvec, True, cv2.SOLVEPNP_ITERATIVE)
            if not refined:
                return None
            projected, _ = cv2.projectPoints(obj, rvec, tvec, k, dist)
            rmse = float(np.sqrt(np.mean(np.sum((projected.reshape(-1, 2) -
                                                image.reshape(-1, 2))**2, axis=1))))
            R, _ = cv2.Rodrigues(rvec)
            t = tvec.reshape(3)
        except (ValueError, cv2.error):
            return None
        previous_R, previous_t = self._pose[:2]
        direction = float(np.dot(R[:, 2], previous_R[:, 2]))
        if (not isfinite(rmse) or rmse > policy.max_pnp_rmse_px or
                not np.isfinite(R).all() or not np.isfinite(t).all() or
                t[2] < 0.10 or t[2] > 3.5 or
                np.linalg.norm(t - previous_t) > policy.max_translation_m or
                direction < policy.min_pose_cosine):
            return None
        pose = (R, t, 0, int(len(obj)), rmse)
        return pose, image.astype(np.float32), obj.astype(np.float32)
