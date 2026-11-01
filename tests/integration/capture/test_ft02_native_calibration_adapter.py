"""FT-02a injected fake-native adapter checks; no physical device."""
from __future__ import annotations

import pickle
from types import SimpleNamespace as NS
import numpy as np

from scantopath.modules.capture.infrastructure.native_camera import Gemini2NativeCameraAdapter


def native_packet(with_cal: bool = True):
    p = NS(
        validate=lambda: True, align_disabled=True,
        device=NS(name="Orbbec Gemini 2", firmware="fake"),
        color=NS(encoding=NS(name="MJPEG"), width=5, height=4,
                 frame_index=1, timestamp_us=10000, bytes=b"jpeg"),
        depth=NS(encoding=NS(name="Y16"), width=3, height=2,
                 frame_index=2, timestamp_us=10100,
                 bytes=np.full((2, 3), 900, dtype="<u2").tobytes()),
        depth_scale_m_per_unit=0.001,
    )
    if with_cal:
        p.color_intrinsics = NS(width=5, height=4, fx=5., fy=5., cx=2., cy=2.)
        p.depth_intrinsics = NS(width=3, height=2, fx=3., fy=3., cx=1., cy=1.)
        p.color_distortion = NS(sdk_model=0, k1_k6_p1_p2=[0.] * 8)
        p.depth_distortion = NS(sdk_model=0, k1_k6_p1_p2=[0.] * 8)
        p.depth_to_color = NS(rotation=[1.,0.,0.,0.,1.,0.,0.,0.,1.],
                              translation_mm=[-13.7, 0., 0.])
    return p


class Source:
    def __init__(self, packet):
        self.packet = packet
    def open(self): pass
    def close(self): pass
    def read_next(self, **kw): return self.packet


def read(p):
    adapter = Gemini2NativeCameraAdapter(native_loader=lambda: NS(OrbbecCameraSource=lambda: Source(p)))
    adapter.open()
    try:
        return adapter.read_next(per_attempt_timeout_ms=300, max_attempts=1)
    finally:
        adapter.close()


def test_cal05_copies_same_frame_and_pipe_pickle():
    f = read(native_packet())
    assert f.calibration is not None
    assert f.calibration.depth_intrinsics.width == 3
    assert np.isclose(f.calibration.translation_C_D_m[0], -0.0137, rtol=0.0, atol=1e-12)
    f2 = pickle.loads(pickle.dumps(f))
    assert f2.calibration.fingerprint == f.calibration.fingerprint
    assert f2.depth_y16_le == f.depth_y16_le


def test_legacy_mock_still_previews_but_no_calibration():
    f = read(native_packet(with_cal=False))
    assert f.calibration is None
    assert f.calibration_error == "LIVE_CALIBRATION_MISSING"


def test_unsupported_model_is_recorded_not_silently_zeroed():
    p = native_packet()
    p.depth_distortion.sdk_model = 2
    p.depth_distortion.k1_k6_p1_p2[0] = 0.1
    f = read(p)
    assert f.calibration is not None
    assert f.calibration.depth_distortion.sdk_model == 2
    assert f.calibration.depth_distortion.k1_k6_p1_p2[0] == 0.1


def test_malformed_calibration_stops_geometry_not_preview():
    p = native_packet()
    p.depth_intrinsics.fx = 0
    f = read(p)
    assert f.calibration is None and f.calibration_error == "INTRINSICS_INVALID"
    assert f.depth_width == 3 and f.color_mjpeg == b"jpeg"
