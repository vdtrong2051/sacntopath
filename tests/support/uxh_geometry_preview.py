"""Shared synthetic RGB-D XYZRGB source fixture; no camera/RAW persistence."""
from __future__ import annotations
import numpy as np
from scantopath.modules.geometry.application.service import GeometryService
from tests.support.raw_fixture import raw

def xyzrgb_view():
    packet = raw()
    metadata = packet.metadata
    image = np.full((metadata.color.height, metadata.color.width, 3),
                    (23, 120, 208), dtype=np.uint8)
    return GeometryService.process(
        depth_u16=packet.depth_u16_copy(), color_rgb=image,
        metadata=metadata, capture_id=metadata.capture_id)
