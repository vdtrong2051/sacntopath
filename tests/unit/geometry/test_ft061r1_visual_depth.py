"""Pure array tests, no hardware, no Qt, no RAW."""
import numpy as np
import pytest
from scantopath.modules.geometry.application.live_visual_depth import (
    StableDepthScale, VisualDepthEnhancer,
)


def scene():
    a = np.full((90, 120), 900, np.uint16)
    a[25:65, 36:90] = 848
    return a


def test_small_hole_filled_with_explicit_provenance():
    a=scene()
    a[45,55]=0
    e=VisualDepthEnhancer()
    out, inferred, modified=e.process(a,generation=1,frame_index=0)
    assert 845 <= out[45,55] <= 850
    assert inferred[45,55]
    assert not inferred[5,5]
    assert not out.flags.writeable
    assert a[45,55]==0


def test_large_void_not_fabricated():
    a=scene()
    a[35:55,45:70]=0
    out, inferred, _=VisualDepthEnhancer().process(a,generation=1,frame_index=0)
    assert out[46,55]==0
    assert not inferred[46,55]


def test_hard_edge_not_smoothed_across_depth_jump():
    a=scene()
    out, _,_=VisualDepthEnhancer().process(a,generation=1,frame_index=0)
    assert out[44,35]==900 and out[44,36]==848


def test_mode_off_preserves_exact_depth_and_no_inference():
    a=scene(); a[40,40]=0
    out, inf, mod=VisualDepthEnhancer().process(a,generation=1,frame_index=10,mode='off')
    np.testing.assert_array_equal(out,a)
    assert not inf.any() and not mod.any()


def test_generation_and_mode_switch_do_not_reuse_old_data():
    e=VisualDepthEnhancer()
    a=scene()
    for i in range(3):e.process(a,generation=1,frame_index=i)
    b=scene();b[40,40]=0
    e.process(b,generation=2,frame_index=4)
    assert len(e._history)==1
    e.process(b,generation=2,frame_index=5,mode='off')
    assert len(e._history)==0
    e.process(b,generation=2,frame_index=6,mode='visual')
    assert len(e._history)==1


def test_motion_resets_temporal_memory():
    e=VisualDepthEnhancer()
    a=scene(); e.process(a,generation=1,frame_index=0)
    b=np.full_like(a,1060)
    e.process(b,generation=1,frame_index=1)
    assert len(e._history)==1


def test_display_scale_smooths_without_touching_source():
    s=StableDepthScale(alpha=.1)
    a=scene();b=a.copy();b[:15,:]=2400
    first=s.update(a)
    p=s._hi
    s.update(b)
    assert s._hi > p
    assert s._hi < 2400
    assert a[44,55]==848
    assert first.dtype==np.uint8 and first.shape==a.shape


def test_invalid_inputs_are_rejected():
    e=VisualDepthEnhancer()
    with pytest.raises(ValueError,match='VISUAL_DEPTH_INPUT_INVALID'):
        e.process(np.zeros((2,2),np.float32),generation=1,frame_index=0)
