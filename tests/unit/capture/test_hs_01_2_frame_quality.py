"""HS-01.2 frame-quality tests: no camera, Qt, filesystem, or SDK."""
from types import SimpleNamespace

import numpy as np
import pytest

from scantopath.modules.capture.application.frame_quality import (
    FrameQualityConfig, FrameQualityEvaluator, FrameQualityStatus,
)
from scantopath.modules.capture.domain.models import DepthRoi


def frame(idx=1, depth_value=1000, *, size=(48, 64), rgb_pattern=False):
    h, w = size
    depth = np.full((h, w), depth_value, dtype=np.uint16)
    rgb = np.full((h * 2, w * 3, 3), 100, dtype=np.uint8)
    if rgb_pattern:
        yy, xx = np.indices(rgb.shape[:2])
        rgb[:] = (((xx // 7 + yy // 5) % 2) * 200 + 20)[:, :, None]
    source = SimpleNamespace(depth_height=h, depth_width=w,
        color_height=h * 2, color_width=w * 3,
        depth_frame_index=idx, color_frame_index=idx,
        depth_timestamp_us=idx * 100_000, color_timestamp_us=idx * 100_000,
        depth_scale_m_per_unit=0.001)
    return SimpleNamespace(source=source, depth_u16=depth, color_rgb=rgb)


def roi(f):
    return DepthRoi(0, 0, f.source.depth_width, f.source.depth_height,
                    f.source.depth_width, f.source.depth_height)


def test_roi_required_is_not_implicit_full_scene():
    q = FrameQualityEvaluator().evaluate(frame(), None)
    assert q.status is FrameQualityStatus.ROI_REQUIRED
    assert not q.usable


def test_valid_depth_and_metric_range_and_no_input_mutation():
    f = frame()
    before = f.depth_u16.copy(), f.color_rgb.copy()
    q = FrameQualityEvaluator().evaluate(f, roi(f))
    assert q.usable and q.valid_depth_fraction == 1
    assert q.valid_depth_samples == 256
    assert np.isclose(q.depth_signature_m[0, 0], 1.0)
    assert np.array_equal(f.depth_u16, before[0])
    assert np.array_equal(f.color_rgb, before[1])
    assert not q.depth_signature_m.flags.writeable
    assert not q.intensity_signature.flags.writeable
    assert not q.valid_signature.flags.writeable
    with pytest.raises(ValueError):
        q.depth_signature_m[0, 0] = 2


@pytest.mark.parametrize("value", [0, 65535, 100, 3000])
def test_out_of_range_or_invalid_depth_rejected(value):
    f = frame(depth_value=value)
    q = FrameQualityEvaluator().evaluate(f, roi(f))
    assert q.status is FrameQualityStatus.INSUFFICIENT_DEPTH


def test_mixed_valid_fraction_below_threshold_rejected():
    f = frame()
    f.depth_u16[:, :48] = 0
    q = FrameQualityEvaluator().evaluate(f, roi(f))
    assert q.valid_depth_fraction < .35
    assert q.status is FrameQualityStatus.INSUFFICIENT_DEPTH


def test_roi_bound_to_depth_grid():
    f = frame()
    bad_roi = DepthRoi(0, 0, 64, 48, 65, 48)
    with pytest.raises(ValueError, match="depth grid"):
        FrameQualityEvaluator().evaluate(f, bad_roi)


def test_manual_sub_roi_is_used_not_background():
    f = frame()
    f.depth_u16[:, :32] = 0
    selected = DepthRoi(32, 0, 32, 48, 64, 48)
    q = FrameQualityEvaluator().evaluate(f, selected)
    assert q.usable and q.valid_depth_fraction == 1


def test_tiny_roi_cannot_inflate_valid_sample_count():
    f = frame()
    one_pixel = DepthRoi(1, 1, 1, 1, 64, 48)
    q = FrameQualityEvaluator().evaluate(f, one_pixel)
    assert q.status is FrameQualityStatus.INSUFFICIENT_DEPTH
    assert q.valid_depth_samples == 0


def test_focus_is_optional_and_explicit():
    f = frame()
    selected = roi(f)
    assert FrameQualityEvaluator().evaluate(f, selected).usable
    q = FrameQualityEvaluator(FrameQualityConfig(min_focus_score=1.0)).evaluate(f, selected)
    assert q.status is FrameQualityStatus.LOW_FOCUS
    pattern = frame(rgb_pattern=True)
    assert FrameQualityEvaluator(FrameQualityConfig(min_focus_score=1.0)).evaluate(pattern, roi(pattern)).usable


def test_invalid_quality_config_rejected():
    for kw in ({"min_depth_m": -1}, {"max_depth_m": .1},
               {"sample_grid": 1000}, {"min_valid_fraction": 1.1},
               {"min_focus_score": float("nan")}, {"min_valid_samples": 0},
               {"sample_grid": 4, "min_valid_samples": 17}):
        with pytest.raises(ValueError):
            FrameQualityConfig(**kw)
