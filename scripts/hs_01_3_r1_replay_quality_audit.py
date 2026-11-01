"""HS-01.3-R1 read-only RAW-v2 audit; optional *proxy* comparison of a fixed ROI.

Uses the authoritative RawReplayService for integrity/lineage. No SQLite writes,
no RAW rewrite, no camera SDK, no Qt. ROI cannot recover historical LIVE ROI:
novelty results are diagnostics, NOT a retroactive capture acceptance verdict.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.frame_quality import FrameQualityEvaluator
from scantopath.modules.capture.application.keyframe_selection_models import KeyframeSelectionConfig
from scantopath.modules.capture.application.keyframe_selector import _robust_novelty
from scantopath.modules.capture.application.replay import RawReplayService
from scantopath.modules.capture.domain.models import DepthRoi
from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter
from scantopath.modules.capture.infrastructure.jpeg_codec import PillowMjpegDecoder


def parse_roi(value: str):
    try:
        dimensions = tuple(int(x.strip()) for x in value.split(','))
        if len(dimensions) != 4 or dimensions[0] < 0 or dimensions[1] < 0 or min(dimensions[2:]) <= 0:
            raise ValueError
        return dimensions
    except ValueError as exc:
        raise argparse.ArgumentTypeError('ROI must be x,y,width,height in native DEPTH pixels') from exc


def read_rows(store: Path, session: str | None):
    file = store / 'metadata.sqlite3'
    if not file.is_file():
        raise ValueError('SQLite v2 store not found')
    con = sqlite3.connect(file.resolve(strict=True).as_uri() + '?mode=ro', uri=True)
    try:
        if con.execute('PRAGMA user_version').fetchone()[0] != 2:
            raise ValueError('Only numbered SQLite v2 supported')
        rows = con.execute('''
            SELECT p.project_id, sp.specimen_id, s.session_id, s.label,
                   sc.code, c.capture_id
            FROM captures AS c
            JOIN storage_captures AS sc ON sc.capture_id=c.capture_id
            JOIN scan_sessions AS s ON s.session_id=c.session_id
            JOIN specimens AS sp ON sp.specimen_id=s.specimen_id
            JOIN projects AS p ON p.project_id=sp.project_id
            WHERE (? IS NULL OR s.label = ?)
            ORDER BY s.label, sc.ordinal
        ''', (session, session)).fetchall()
        return rows
    finally:
        con.close()


def inspect(store: Path, session: str | None, roi_rect: tuple[int,int,int,int] | None):
    rows = read_rows(store, session)
    if not rows:
        raise ValueError('No captures found in requested scope')
    replay = RawReplayService(RawReaderAdapter())
    decoder = PillowMjpegDecoder()
    evaluator = FrameQualityEvaluator()
    cfg = KeyframeSelectionConfig()
    passed = failed = 0
    duplicate_proxy = novel_proxy = inconclusive = 0
    reference = None
    reference_session = None
    for project_id, specimen_id, session_id, label, code, capture_id in rows:
        if session_id != reference_session:
            reference = None
            reference_session = session_id
        ctx = CaptureContext(str(store), project_id, specimen_id, session_id, capture_id)
        try:
            raw = replay.load(ctx)
            passed += 1
            verdict = 'ROI_NOT_PROVIDED'
            if roi_rect is not None:
                m = raw.metadata
                roi = DepthRoi(*roi_rect, m.depth.width, m.depth.height)
                rgb = decoder.decode(raw.color_mjpeg, width=m.color.width, height=m.color.height)
                depth = raw.depth_u16_copy()
                source = SimpleNamespace(
                    depth_height=m.depth.height, depth_width=m.depth.width,
                    color_height=m.color.height, color_width=m.color.width,
                    depth_frame_index=m.depth.frame_index, color_frame_index=m.color.frame_index,
                    depth_timestamp_us=m.depth.timestamp_us,
                    depth_scale_m_per_unit=m.depth_scale_m_per_unit,
                )
                assessment = evaluator.evaluate(SimpleNamespace(source=source, depth_u16=depth,
                                                                 color_rgb=rgb), roi)
                if not assessment.usable:
                    verdict = assessment.status.value
                    inconclusive += 1
                elif reference is None:
                    reference = assessment
                    verdict = 'REFERENCE'
                else:
                    score = _robust_novelty(assessment, reference, cfg)
                    if score is None:
                        verdict = 'INCONCLUSIVE_LOW_OVERLAP'
                        inconclusive += 1
                    elif score < cfg.min_novelty_score:
                        verdict = f'DUPLICATE_PROXY({score:.4f})'
                        duplicate_proxy += 1
                    else:
                        verdict = f'NOVEL_PROXY({score:.4f})'
                        novel_proxy += 1
                        # Diagnostic reference selection, not original live selector state.
                        reference = assessment
            print(f'RAW_PASS {label}/{code} | {verdict}', flush=True)
        except Exception as exc:
            failed += 1
            print(f'RAW_FAIL {label}/{code} | {type(exc).__name__}: {exc}', flush=True)
    print(f'RAW_PASSED={passed} RAW_FAILED={failed} TOTAL={len(rows)}')
    if roi_rect is not None:
        print(f'DUPLICATE_PROXY={duplicate_proxy} NOVEL_PROXY={novel_proxy} INCONCLUSIVE={inconclusive}')
        print('QUALITY_SCOPE=FIXED_DEPTH_ROI_PROXY_NOT_ORIGINAL_LIVE_ROI_OR_6DOF')
    else:
        print('QUALITY_SCOPE=NOT_EVALUATED_WITHOUT_ROI')
    print('STORE_MODE=READ_ONLY_NO_WRITES')
    print('HS_01_3_R1_AUDIT=' + ('PASS_RAW_REPLAY' if passed == len(rows) and failed == 0 else 'FAIL'))
    return 0 if passed == len(rows) and failed == 0 else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--session', help='Exact Scan Session label; optional')
    parser.add_argument('--roi-depth', type=parse_roi,
                        help='Fixed native-depth ROI x,y,w,h; useful for S02, not a mask')
    args = parser.parse_args()
    try:
        return inspect(args.root.resolve(strict=True), args.session, args.roi_depth)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(2, f'HS_01_3_R1_AUDIT=FAIL ({type(exc).__name__}: {exc})\n')


if __name__ == '__main__':
    raise SystemExit(main())
