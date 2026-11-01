"""Shared provenance-preserving XYZ/PLY fixture and typed point pick."""
from __future__ import annotations
from dataclasses import replace
import numpy as np
from scantopath.modules.geometry.application.service import GeometryService
from scantopath.modules.viewer3d.application.scene_contracts import SceneSelectionRef
from scantopath.ui.shell.geometry_preview import write_preview_ply
from tests.support.raw_fixture import raw

def fixture(tmp_path):
    packet = raw()
    meta = packet.metadata
    rgb = np.full((meta.color.height, meta.color.width, 3), (21, 133, 219), dtype=np.uint8)
    view = GeometryService.process(depth_u16=packet.depth_u16_copy(), color_rgb=rgb,
                                  metadata=meta, capture_id=meta.capture_id)
    assert len(view.colored_point_indices) >= 3
    # Simulate a colored subset with gaps: PLY index must not be used as XYZ ID.
    ids = view.colored_point_indices[::2].copy()
    colors = view.colors_rgb[::2].copy()
    view = replace(view, colored_point_indices=ids, colors_rgb=colors)
    receipt = write_preview_ply(view, tmp_path/'temporary.ply')
    return view, receipt


def pick(view, receipt, row, rev=3):
    p = view.points_xyz_m[view.colored_point_indices[row]]
    rounded = tuple(float(x) for x in np.asarray(p, dtype=np.float32))
    return SceneSelectionRef(receipt.ply_sha256, rev, 'point', row, rounded)
