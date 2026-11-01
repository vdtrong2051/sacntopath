"""HS-01.3-R1 regression: static camera must not produce false NEW-VIEW requests."""
import numpy as np
import pytest

from scantopath.modules.capture.application.keyframe_selector import KeyframeSelector
from scantopath.modules.capture.application.keyframe_selection_models import (
    KeyframeDecision, KeyframeSelectionConfig, SelectionReason,
)
from scantopath.modules.capture.domain.models import DepthRoi
from tests.unit.capture.test_hs_01_2_frame_quality import frame


def _make(idx, *, illumination=100, depth=1000):
    f = frame(idx, depth, size=(64, 80))
    # Nearby box 30% of crop, with the table farther away.
    f.depth_u16[:, :] = 1210
    f.depth_u16[15:45, 22:58] = depth
    yy_rgb, xx_rgb = np.indices(f.color_rgb.shape[:2])
    f.color_rgb[:] = np.clip(illumination + ((xx_rgb // 5 + yy_rgb // 7) % 2) * 24,
                             0, 255)[:, :, None]
    return f


def _roi():
    return DepthRoi(12, 9, 56, 44, 80, 64)


def _first(s):
    assert s.evaluate(_make(1), _roi()).decision is KeyframeDecision.WAIT
    assert s.evaluate(_make(2), _roi()).decision is KeyframeDecision.SELECT
    s.capture_completed(True)


def test_static_depth_speckle_and_global_brightness_change_not_novel():
    s = KeyframeSelector(config=KeyframeSelectionConfig(cooldown_us=0))
    _first(s)
    rng = np.random.default_rng(15)
    for index in range(3, 35):
        f = _make(index, illumination=100 + (index % 3) * 12)
        perturb = rng.integers(-6, 7, size=f.depth_u16.shape, dtype=np.int16)
        f.depth_u16[:] = (f.depth_u16.astype(np.int32) + perturb).astype(np.uint16)
        selection = s.evaluate(f, _roi())
        assert selection.decision is KeyframeDecision.WAIT, (index, selection)
        assert selection.reason_code is SelectionReason.DUPLICATE_VIEW_PROXY
    assert not s.capture_pending


def test_background_changes_outside_roi_cannot_trigger_capture():
    s = KeyframeSelector(config=KeyframeSelectionConfig(cooldown_us=0))
    _first(s)
    f = _make(12)
    f.depth_u16[:8, :] = 600
    f.depth_u16[-8:, :] = 2200
    f.color_rgb[:12, :] = 0
    f.color_rgb[-12:, :] = 255
    result = s.evaluate(f, _roi())
    assert result.decision is KeyframeDecision.WAIT
    assert result.reason_code is SelectionReason.DUPLICATE_VIEW_PROXY


def test_coherent_new_depth_40mm_can_still_trigger():
    s = KeyframeSelector(config=KeyframeSelectionConfig(cooldown_us=0))
    _first(s)
    result = s.evaluate(_make(12, depth=1040), _roi())
    assert result.decision is KeyframeDecision.SELECT
    assert result.reason_code is SelectionReason.SELECT_NOVEL
    assert s.capture_pending


def test_pending_and_failed_commit_do_not_advance_reference():
    s = KeyframeSelector(config=KeyframeSelectionConfig(cooldown_us=0))
    assert s.evaluate(_make(1), _roi()).decision is KeyframeDecision.WAIT
    assert s.evaluate(_make(2), _roi()).decision is KeyframeDecision.SELECT
    assert s.evaluate(_make(3, depth=1040), _roi()).reason_code is SelectionReason.CAPTURE_PENDING
    s.capture_completed(False)
    assert s.evaluate(_make(4, depth=1040), _roi()).decision is KeyframeDecision.SELECT
    assert s.evaluate(_make(5, depth=1040), _roi()).decision is KeyframeDecision.WAIT
    s.capture_completed(True)
    assert s.evaluate(_make(6, depth=1040), _roi()).decision is KeyframeDecision.WAIT


@pytest.mark.parametrize('config', [
    {'depth_noise_floor_m': -1}, {'color_noise_floor_gray': 100},
    {'near_surface_band_m': 0}, {'min_near_surface_samples': 0},
    {'max_signature_shift_cells': 3}, {'silhouette_noise_fraction': .8},
])
def test_config_bounds(config):
    with pytest.raises(ValueError):
        KeyframeSelectionConfig(**config)


def test_one_sample_cell_roi_drift_is_not_a_new_view():
    """ROI tracker drift of a few depth pixels should not create novelty."""
    s = KeyframeSelector(config=KeyframeSelectionConfig(cooldown_us=0))
    def scene(i):
        f = frame(i, depth_value=1000, size=(80, 100))
        y, x = np.indices(f.depth_u16.shape)
        f.depth_u16[:] = (1000 + ((x // 6 + y // 8) % 4) * 13).astype(np.uint16)
        yc, xc = np.indices(f.color_rgb.shape[:2])
        f.color_rgb[:] = (((xc // 5 + yc // 5) % 2) * 150 + 40)[:, :, None]
        return f
    r0 = DepthRoi(12, 8, 64, 64, 100, 80)
    r1 = DepthRoi(16, 8, 64, 64, 100, 80)
    assert s.evaluate(scene(1), r0).decision is KeyframeDecision.WAIT
    assert s.evaluate(scene(2), r0).decision is KeyframeDecision.SELECT
    s.capture_completed(True)
    outcome = s.evaluate(scene(12), r1)
    assert outcome.decision is KeyframeDecision.WAIT, outcome
    assert outcome.reason_code is SelectionReason.DUPLICATE_VIEW_PROXY
