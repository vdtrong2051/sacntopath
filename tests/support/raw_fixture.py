"""Fixture RAW tổng hợp dùng chung; giữ nguyên dữ liệu 07.2 (không phải camera thật)."""
from __future__ import annotations
import numpy as np
from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.domain.models import CaptureKind
from scantopath.domain.raw_rgbd import (
    RawDepthToColorExtrinsics, RawDeviceInfo, RawDistortion, RawIntrinsics,
    RawPixelEncoding, RawRgbdCaptureMetadataV2, RawStreamInfo,
)


def raw(*, session="sess", specimen="spec", capture_id="fixed-raw-id") -> RawRgbdCapture:
    jpeg = b"\xff\xd8fixture\xff\xd9"
    depth = np.array([[0, 1, 99], [100, 900, 1200]], dtype="<u2").tobytes()
    zeros = (0.0,) * 8
    return RawRgbdCapture(
        metadata=RawRgbdCaptureMetadataV2(
            session_id=session, specimen_id=specimen, capture_id=capture_id,
            kind=CaptureKind.SYNTHETIC, measured=False,
            device=RawDeviceInfo(name="FIXTURE_NOT_REAL_CAMERA"),
            color=RawStreamInfo(encoding=RawPixelEncoding.MJPEG, width=5, height=4,
                                frame_index=1, timestamp_us=100000, payload_size_bytes=len(jpeg)),
            depth=RawStreamInfo(encoding=RawPixelEncoding.Y16, width=3, height=2,
                                frame_index=2, timestamp_us=101000, payload_size_bytes=len(depth)),
            color_intrinsics=RawIntrinsics(width=5, height=4, fx=4., fy=4., cx=2., cy=2.),
            depth_intrinsics=RawIntrinsics(width=3, height=2, fx=3., fy=3., cx=1., cy=1.),
            color_distortion=RawDistortion(sdk_model=0, k1_k6_p1_p2=zeros),
            depth_distortion=RawDistortion(sdk_model=0, k1_k6_p1_p2=zeros),
            depth_to_color=RawDepthToColorExtrinsics(
                rotation=(1.,0.,0.,0.,1.,0.,0.,0.,1.), translation_mm=(0.,0.,0.)),
            depth_scale_m_per_unit=0.001,
        ), color_mjpeg=jpeg, depth_y16_le=depth,
    )
