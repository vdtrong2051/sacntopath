"""HF03: long manual sweep retains up to 96 real measured keyframes."""
from __future__ import annotations
from types import SimpleNamespace as NS
import pytest
from scantopath.modules.reconstruction.application.keyframe_sampling import retain_spaced_frame


def packet(i):
    return NS(metadata=NS(depth=NS(timestamp_us=10_000+i*1_200_000,
                                    frame_index=i)))


@pytest.mark.parametrize('observed',[2,19,20,21,39,60,88,96,121,150])
def test_long_sweep_retains_first_latest_in_order(observed):
    kept=[]
    for i in range(observed):
        retain_spaced_frame(kept,packet(i))
        assert len(kept)<=96
        assert kept[0].metadata.depth.frame_index==0
        assert kept[-1].metadata.depth.frame_index==i
    indexes=[f.metadata.depth.frame_index for f in kept]
    assert indexes==sorted(indexes)
    assert len(indexes)==min(observed,96)
    assert len(set(indexes))==len(indexes)
    if observed>96:
        assert any(i<observed//2 for i in indexes[1:-1])
        assert any(i>=observed//2 for i in indexes[1:-1])


def test_refuses_out_of_order_depth():
    kept=[packet(0)]
    with pytest.raises(ValueError,match='TIMESTAMP_ORDER'):
        retain_spaced_frame(kept,packet(0))
    assert len(kept)==1


@pytest.mark.parametrize('cap',[1,97,120])
def test_contract_max_ninetysix(cap):
    with pytest.raises(ValueError,match='LIMIT_OUT_OF_RANGE'):
        retain_spaced_frame([],packet(1),limit=cap)


def test_retains_actual_packet_identity_not_centroids():
    original=[packet(i) for i in range(45)]
    kept=[]
    for frame in original:
        retain_spaced_frame(kept,frame)
    assert all(any(f is src for src in original) for f in kept)


def test_ui_does_not_end_after_twenty_frames():
    from pathlib import Path
    code=(Path(__file__).resolve().parents[3]/'src/scantopath/modules/reconstruction'
          /'presentation/sequence_capture_ui.py').read_text(encoding='utf8')
    assert 'if count >= self.MAX_FRAMES:' not in code
    assert 'retain_spaced_frame(self._packets, packet, limit=self.MAX_FRAMES)' in code
    assert 'if self._stopping:' in code
