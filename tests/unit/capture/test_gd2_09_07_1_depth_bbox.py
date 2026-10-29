"""GD2-09.07.1: NumPy-only unit tests, no SDK/Qt/hardware."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from scantopath.modules.capture.application.depth_bbox import (
    DepthBboxConfig, DepthBboxDetector, DetectionStatus,
)
from scantopath.modules.capture.application.bbox_tracking import (
    DepthBboxTracker, TrackingConfig, TrackingStatus,
)
from scantopath.modules.capture.domain.models import RoiSource


CFG = DepthBboxConfig(sample_step=2, min_valid_samples=30,
                      min_component_samples=12)


def scene(*, box=(20, 20, 30, 25), background=1500,
          object_depth=650, width=120, height=90):
    img = np.full((height, width), background, dtype=np.uint16)
    if box is not None:
        x, y, w, h = box
        img[y:y+h, x:x+w] = object_depth
    return img


def detect(image, config=CFG):
    return DepthBboxDetector(config).detect(image, 0.001)


def test_single_object_native_depth_roi_and_no_mutation():
    image = scene()
    original = image.copy()
    found = detect(image)
    assert found.status is DetectionStatus.OK
    assert found.usable
    r = found.roi
    assert r is not None
    assert (r.x, r.y, r.width, r.height) == (20, 20, 30, 26)
    assert (r.frame_width, r.frame_height) == (120, 90)
    assert r.source is RoiSource.DEPTH_SUGGESTION
    assert found.confidence >= 0.55
    assert np.array_equal(image, original)


def test_empty_or_insufficient_valid_depth_rejected():
    for arr in (np.zeros((90, 120), np.uint16),
                np.full((90, 120), 65535, np.uint16),
                np.full((90, 120), 100, np.uint16)):
        found = detect(arr)
        assert found.status is DetectionStatus.NO_VALID_DEPTH
        assert found.roi is None


def test_uniform_background_rejected_without_fake_roi():
    found = detect(scene(box=None))
    assert found.status is DetectionStatus.LOW_CONTRAST
    assert found.roi is None


def test_two_equivalent_objects_ambiguous():
    image = scene(box=(12, 14, 24, 24))
    image[14:38, 76:100] = 650
    found = detect(image)
    assert found.status is DetectionStatus.AMBIGUOUS
    assert found.roi is None
    assert len(found.candidates) == 2
    assert found.confidence == 0.0


def test_dominant_candidate_beats_noise_component():
    image = scene()
    image[60:64, 90:94] = 650
    found = detect(image)
    assert found.status is DetectionStatus.OK
    assert found.roi.x == 20
    assert len(found.candidates) == 1


def test_foreground_small_is_rejected_without_choosing_noise():
    image = scene(box=(20, 20, 4, 4))
    found = detect(image)
    assert found.status in (DetectionStatus.NO_CANDIDATE, DetectionStatus.LOW_CONTRAST)
    assert found.roi is None


def test_missing_background_or_full_frame_near_is_rejected():
    image = np.full((90, 120), 650, np.uint16)
    assert detect(image).roi is None


def test_non_aligned_color_dimensions_never_enter_roi():
    found = detect(scene(width=128, height=88))
    assert found.roi.frame_width == 128
    assert found.roi.frame_height == 88
    assert found.roi.frame_width != 1920


def test_scale_and_range_are_metric_not_raw_units():
    image = scene(background=3000, object_depth=1300)
    cfg = replace(CFG, max_depth_m=3.5)
    assert DepthBboxDetector(cfg).detect(image, 0.0005).status is DetectionStatus.OK
    assert DepthBboxDetector(cfg).detect(image, 0.001).status is DetectionStatus.OK


@pytest.mark.parametrize("invalid", [None, [[1, 2]],
                                    np.zeros((3, 4), np.float32),
                                    np.zeros((3, 4, 1), np.uint16),
                                    np.zeros((0, 5), np.uint16)])
def test_invalid_depth_shapes_rejected(invalid):
    with pytest.raises(ValueError):
        detect(invalid)


@pytest.mark.parametrize("scale", [None, True, 0, -0.1, float("nan"), float("inf")])
def test_invalid_depth_scale_rejected(scale):
    with pytest.raises(ValueError):
        DepthBboxDetector(CFG).detect(scene(), scale)


@pytest.mark.parametrize("change", [
    {"sample_step": 0}, {"sample_step": 17}, {"sample_step": True},
    {"min_depth_m": 0.0}, {"max_depth_m": 0.1},
    {"foreground_quantile": 90.0}, {"background_quantile": 0.0},
    {"min_component_samples": 0}, {"ambiguity_ratio": 1.1},
    {"min_confidence": float("nan")}, {"max_candidates": 100},
])
def test_invalid_config_rejected(change):
    with pytest.raises(ValueError):
        DepthBboxConfig(**change)


def test_tracker_requires_two_consistent_frames():
    tracker = DepthBboxTracker(DepthBboxDetector(CFG))
    first = tracker.update(scene(), 0.001)
    second = tracker.update(scene(), 0.001)
    assert first.status is TrackingStatus.ACQUIRING
    assert first.roi is None
    assert second.status is TrackingStatus.TRACKING
    assert second.usable


def test_tracker_smoothing_reduces_jitter():
    tracker = DepthBboxTracker(DepthBboxDetector(CFG))
    tracker.update(scene(box=(20, 20, 30, 24)), 0.001)
    original = tracker.update(scene(box=(20, 20, 30, 24)), 0.001)
    moved = tracker.update(scene(box=(24, 22, 30, 24)), 0.001)
    assert original.roi.x == 20
    assert 20 < moved.roi.x < 24
    assert 20 < moved.roi.y < 22 + 1


def test_tracker_large_jump_not_emitted_as_new_object():
    tracker = DepthBboxTracker(DepthBboxDetector(CFG))
    tracker.update(scene(box=(10, 20, 20, 24)), 0.001)
    tracker.update(scene(box=(10, 20, 20, 24)), 0.001)
    jump = tracker.update(scene(box=(90, 20, 20, 24)), 0.001)
    assert jump.status is TrackingStatus.JUMP_REJECTED
    assert jump.roi is None
    assert not jump.usable


def test_tracker_missing_frames_never_publish_stale_roi():
    tracker = DepthBboxTracker(DepthBboxDetector(CFG),
                               TrackingConfig(max_missing_frames=2))
    tracker.update(scene(), 0.001)
    tracker.update(scene(), 0.001)
    blank = scene(box=None)
    assert tracker.update(blank, 0.001).status is TrackingStatus.HOLDING
    assert tracker.update(blank, 0.001).status is TrackingStatus.HOLDING
    lost = tracker.update(blank, 0.001)
    assert lost.status is TrackingStatus.NO_TARGET
    assert lost.roi is None
    assert tracker.update(scene(), 0.001).status is TrackingStatus.ACQUIRING


def test_tracker_reset_on_reopen_clears_history():
    tracker = DepthBboxTracker(DepthBboxDetector(CFG))
    tracker.update(scene(), 0.001)
    assert tracker.update(scene(), 0.001).usable
    tracker.reset()
    result = tracker.update(scene(), 0.001)
    assert result.status is TrackingStatus.ACQUIRING
    assert result.roi is None


def test_tracker_ambiguous_scene_requires_manual_fallback():
    tracker = DepthBboxTracker(DepthBboxDetector(CFG))
    image = scene(box=(12, 14, 24, 24))
    image[14:38, 76:100] = 650
    result = tracker.update(image, 0.001)
    assert result.status is TrackingStatus.AMBIGUOUS
    assert result.roi is None


def test_tracker_invalid_frame_keeps_prior_state():
    tracker = DepthBboxTracker(DepthBboxDetector(CFG))
    tracker.update(scene(), 0.001)
    tracker.update(scene(), 0.001)
    with pytest.raises(ValueError):
        tracker.update(np.zeros((10, 10), np.float32), 0.001)
    assert tracker.update(scene(), 0.001).usable


@pytest.mark.parametrize("change", [
    {"confirmation_frames": 0}, {"confirmation_frames": True},
    {"max_missing_frames": -1}, {"smoothing_alpha": 0},
    {"smoothing_alpha": float("inf")}, {"max_center_shift_fraction": 1.1},
])
def test_invalid_tracking_config_rejected(change):
    with pytest.raises(ValueError):
        TrackingConfig(**change)


def test_existing_track_does_not_silence_ambiguity():
    tracker = DepthBboxTracker(DepthBboxDetector(CFG))
    tracker.update(scene(box=(12, 14, 24, 24)), 0.001)
    assert tracker.update(scene(box=(12, 14, 24, 24)), 0.001).usable
    image = scene(box=(12, 14, 24, 24))
    image[14:38, 76:100] = 650
    result = tracker.update(image, 0.001)
    assert result.status is TrackingStatus.AMBIGUOUS
    assert result.roi is None


def test_depth_detector_full_gemini_grid_without_extra_packages():
    depth = np.full((800, 1280), 1600, dtype=np.uint16)
    depth[230:580, 440:820] = 650
    detected = DepthBboxDetector().detect(depth, 0.001)
    assert detected.status is DetectionStatus.OK
    box = detected.roi
    assert box is not None
    assert box.frame_width == 1280 and box.frame_height == 800
    assert abs(box.x - 440) <= 4 and abs(box.y - 230) <= 4
    assert abs(box.width - 380) <= 4 and abs(box.height - 350) <= 4
