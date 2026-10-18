"""PRE-04: one-shot Gemini 2 native capture -> immutable RAW v2 packet.

The adapter does not import OrbbecSDK or open hardware at module import time.
The camera is closed before a RAW packet is returned; copied Python bytes
remain owned by the application. Persistence belongs to SessionStore.
"""
from __future__ import annotations

from typing import Any

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.domain.models import CaptureKind
from scantopath.domain.raw_rgbd import (
    RawDepthToColorExtrinsics,
    RawDeviceInfo,
    RawDistortion,
    RawIntrinsics,
    RawPixelEncoding,
    RawRgbdCaptureMetadataV2,
    RawStreamInfo,
)


def _intrinsics(native: Any) -> RawIntrinsics:
    return RawIntrinsics(
        width=int(native.width), height=int(native.height),
        fx=float(native.fx), fy=float(native.fy),
        cx=float(native.cx), cy=float(native.cy),
    )


def _distortion(native: Any) -> RawDistortion:
    return RawDistortion(
        sdk_model=int(native.sdk_model),
        k1_k6_p1_p2=tuple(float(x) for x in native.k1_k6_p1_p2),
    )


def _stream(native: Any, encoding: RawPixelEncoding, payload: bytes) -> RawStreamInfo:
    return RawStreamInfo(
        encoding=encoding,
        width=int(native.width), height=int(native.height),
        frame_index=int(native.frame_index),
        timestamp_us=int(native.timestamp_us),
        payload_size_bytes=len(payload),
    )


def raw_capture_from_native(
    packet: Any, *, session_id: str, specimen_id: str
) -> RawRgbdCapture:
    """Translate an owned pybind11 RgbdCapture without decode or pixel changes.

    PRE-02's strict schema performs the full metadata and payload validation.
    ``packet.validate()`` also enforces the native vendor-neutral contract.
    Camera pose stays unknown; requested frame sync is NOT an accuracy claim.
    """
    if packet.validate() is not True:
        raise ValueError("Native RGB-D packet validation failed")
    if packet.color.encoding.name != "MJPEG" or packet.depth.encoding.name != "Y16":
        raise ValueError("PRE-04 requires original MJPEG and Y16 streams")
    if packet.align_disabled is not True:
        raise ValueError("PRE-04 cannot accept aligned or transformed streams")

    # The pybind11 .bytes getter creates a new Python-owned immutable copy.
    # Do not call depth_u16() (which is an additional conversion/copy).
    color_bytes = packet.color.bytes
    depth_bytes = packet.depth.bytes
    device = packet.device
    metadata = RawRgbdCaptureMetadataV2(
        session_id=session_id,
        specimen_id=specimen_id,
        kind=CaptureKind.ORBBEC,
        measured=True,  # Sensor provenance, NOT certified dimensional accuracy.
        device=RawDeviceInfo(
            name=device.name,
            firmware_version=device.firmware or None,
            usb_connection=device.usb_connection or None,
            pid=int(device.pid),
            # Current native binding does not expose SDK version or serial.
            sdk_version=None,
            serial=None,
        ),
        color=_stream(packet.color, RawPixelEncoding.MJPEG, color_bytes),
        depth=_stream(packet.depth, RawPixelEncoding.Y16, depth_bytes),
        color_intrinsics=_intrinsics(packet.color_intrinsics),
        depth_intrinsics=_intrinsics(packet.depth_intrinsics),
        color_distortion=_distortion(packet.color_distortion),
        depth_distortion=_distortion(packet.depth_distortion),
        depth_to_color=RawDepthToColorExtrinsics(
            rotation=tuple(float(x) for x in packet.depth_to_color.rotation),
            translation_mm=tuple(float(x) for x in packet.depth_to_color.translation_mm),
        ),
        depth_scale_m_per_unit=float(packet.depth_scale_m_per_unit),
        alignment_mode="disabled",
        frame_sync_requested=bool(packet.frame_sync_requested),
        timestamp_domain="sdk_reported_unverified",
        coordinate_frame="depth_optical",
        camera_pose=None,
    )
    return RawRgbdCapture(
        metadata=metadata,
        color_mjpeg=color_bytes,
        depth_y16_le=depth_bytes,
    )


def capture_one_raw(*, session_id: str, specimen_id: str, native: Any = None) -> RawRgbdCapture:
    """Read exactly one native frameset and always release camera resources.

    ``native`` allows offline testing with a fake pybind11 module. Otherwise
    the native loader is invoked lazily; no SDK needed for unrelated imports.
    """
    if native is None:
        from scantopath.acquisition.native import load_native
        native = load_native()
    source = native.OrbbecCameraSource()
    try:
        source.open()
        packet = source.read_next()
    finally:
        source.close()
    # Deliberately convert AFTER close, testing the native owned-copy guarantee.
    return raw_capture_from_native(packet, session_id=session_id, specimen_id=specimen_id)
