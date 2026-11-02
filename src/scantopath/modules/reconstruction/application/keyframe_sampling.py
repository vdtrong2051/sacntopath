"""Bounded online selection of *measured* RAW keyframes for manual freehand scan.

Never synthesizes frames/poses. Preserve first and most recent sample, discard
only an interior frame whose removal least reduces temporal coverage. All
frame identity, timestamp, and acquisition ordering checks are the UI caller's
responsibility. FT09/FT10 receive <=96 original, sensor-measured packets.
"""
from __future__ import annotations

from typing import TypeVar

T = TypeVar('T')


def retain_spaced_frame(frames: list[T], packet: T, *, limit: int = 96) -> None:
    """Append a real packet, thin most redundant interior time gap if at capacity.

    Mutates *frames* in place without allocating/copying RAW buffers. All
    metadata timestamps are native depth microseconds and strictly increasing.
    """
    if not 2 <= limit <= 96:
        raise ValueError('KEYFRAME_LIMIT_OUT_OF_RANGE')
    stamp = int(packet.metadata.depth.timestamp_us)
    if frames and stamp <= int(frames[-1].metadata.depth.timestamp_us):
        raise ValueError('KEYFRAME_TIMESTAMP_ORDER_INVALID')
    frames.append(packet)
    if len(frames) <= limit:
        return
    # For one candidate removal at position i, span across its neighbours is
    # a proxy for temporal information lost. The narrowest span is most redundant.
    # Never remove the anchor (0) or latest frame (-1).
    timestamps = [int(f.metadata.depth.timestamp_us) for f in frames]
    remove = min(range(1, len(frames) - 1),
                 key=lambda i: (timestamps[i + 1] - timestamps[i - 1], i))
    frames.pop(remove)
