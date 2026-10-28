"""DOC-03A static documentation gate. Read-only; evidence only outside repo.

Tests scope/links/source refs and DOC-02 content coverage without touching Git
history, app runtime, camera, SQLite or any human/manual acceptance result.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

BASELINE = '7a0df7c5b596ff8750bf91f47310067c53a8b204'
FILES = (
    'README.md', 'docs/README.md',
    'docs/01-tong-quan/GIOI_THIEU_DU_AN.md',
    'docs/01-tong-quan/PHAM_VI_VA_NANG_LUC.md',
    'docs/01-tong-quan/LO_TRINH_PHAT_TRIEN.md',
    'docs/02-kien-truc/KIEN_TRUC_HE_THONG.md',
    'docs/02-kien-truc/DU_LIEU_VA_HE_TOA_DO.md',
    'docs/02-kien-truc/CONG_NGHE_VA_PHU_THUOC.md',
)
SOURCE_PATHS = (
    'pyproject.toml', 'cpp/CMakeLists.txt', 'src/scantopath/ui/main.py',
    'src/scantopath/ui/shell/main_window.py',
    'src/scantopath/ui/shell/viewer_bootstrap.py',
    'src/scantopath/modules/viewer3d/application/scene_contracts.py',
    'src/scantopath/modules/viewer3d/presentation/interactive_controller.py',
    'src/scantopath/modules/viewer3d/infrastructure/resident_poc/async_session.py',
    'src/scantopath/storage/session_store.py',
    'src/scantopath/metadata/store.py',
    'src/scantopath/domain/raw_rgbd.py',
    'tests/unit/raw/test_raw_rgbd_contract.py',
    'tests/native/viewer/test_gd1_r5_3_geometry_interaction.py',
    'scripts/verify.ps1',
)
LINK = re.compile(r'(?<!!)\[[^\]]+\]\(([^)]+)\)')


def safe_relative(ref: str) -> bool:
    return bool(ref and not ref.startswith(('/', '\\')) and '\\' not in ref
                and not re.match(r'^[A-Za-z]:', ref)
                )


def broken_links(root: Path, path: str, body: str) -> list[str]:
    errors = []
    for match in LINK.finditer(body):
        ref = match.group(1).split(' "')[0].strip()
        if ref.startswith(('https://', 'http://', 'mailto:', '#')):
            continue
        target = ref.split('#', 1)[0].split('?', 1)[0]
        if not safe_relative(target):
            errors.append(f'UNSAFE_LINK:{path}:{ref}')
            continue
        resolved = (root / path).parent.joinpath(target).resolve()
        if not resolved.is_relative_to(root.resolve()):
            errors.append(f'LINK_ESCAPES_REPO:{path}:{ref}')
        elif not resolved.is_file():
            errors.append(f'BROKEN_LINK:{path}:{ref}')
    return errors


def content_errors(text: dict[str, str]) -> list[str]:
    errors = []
    for path in FILES:
        data = text.get(path, '')
        if not data.startswith('# ') or len(data.strip()) < 1000:
            errors.append('DOCUMENT_TOO_SHORT_OR_NO_TITLE:' + path)
        if '7a0df7c5b596ff8750bf91f47310067c53a8b204' not in data:
            errors.append('COMMIT_PROVENANCE_MISSING:' + path)
        if not any(x in data for x in ('28/10/2026', '2026-10-28')):
            errors.append('VERIFIED_DATE_MISSING:' + path)
        if not any(x in data.lower() for x in ('giới hạn', 'không', 'chưa')):
            errors.append('LIMITATION_MISSING:' + path)
    checks = {
        'README.md': ('## 1.', '## 8.', '[Tài liệu GĐ1 hiện hành](docs/INDEX.md)',
                      'scantopath.ui.main', 'Quick', 'Full', 'Acceptance'),
        'docs/README.md': ('DOC-03B', 'DOC-03C', 'DOC-04', 'DOC-05'),
        'docs/01-tong-quan/GIOI_THIEU_DU_AN.md': ('RAW', 'SQLite', 'PLY', 'OBJ', 'Zigzag'),
        'docs/01-tong-quan/PHAM_VI_VA_NANG_LUC.md': ('CAP-01', 'CAP-13', 'NOT_IMPLEMENTED_IN_THIS_BUILD'),
        'docs/01-tong-quan/LO_TRINH_PHAT_TRIEN.md': ('GĐ0', 'GĐ1', 'GĐ2', 'GĐ3', 'GĐ4', 'GĐ5'),
        'docs/02-kien-truc/KIEN_TRUC_HE_THONG.md': ('## 5.', '## 6.', '## 7.', 'Render Host', 'ACK', 'IPC'),
        'docs/02-kien-truc/DU_LIEU_VA_HE_TOA_DO.md': ('m/unit', 'translation_mm', 'measured=True', 'unknown', 'COMMITTED'),
        'docs/02-kien-truc/CONG_NGHE_VA_PHU_THUOC.md': ('pyproject.toml', 'cpp/CMakeLists.txt',
                                                        'SCANTOPATH_BUILD_PYTHON_BINDINGS', 'Open3D', 'PCL'),
    }
    for path, required in checks.items():
        for token in required:
            if token not in text.get(path, ''):
                errors.append('REQUIRED_CONTEXT_MISSING:' + path + ':' + token)
    if 'R6_OVERALL_PASS' in text.get('README.md', ''):
        errors.append('PREMATURE_R6_ACCEPTANCE')
    if not all('NOT_TESTED' in text[p] or 'PENDING' in text[p] for p in (FILES[0], FILES[3], FILES[5])):
        errors.append('MANUAL_GATE_BOUNDARY_MISSING')
    return errors


def baseline_files(root: Path) -> set[str]:
    proc = subprocess.run(['git', 'ls-tree', '-r', '--name-only', BASELINE], cwd=root,
                          capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
    if proc.returncode:
        raise RuntimeError('DOC03A_GIT_BASELINE_NOT_FOUND:' + proc.stderr[-200:])
    return set(proc.stdout.splitlines())


def verify(root: Path) -> dict:
    root = root.resolve(strict=True)
    errors: list[str] = []
    texts: dict[str, str] = {}
    for path in FILES:
        target = root / path
        if not target.is_file() or target.is_symlink():
            errors.append('MISSING_OR_SYMLINK:' + path)
            texts[path] = ''
            continue
        try:
            body = target.read_text(encoding='utf-8-sig')
        except UnicodeError:
            errors.append('BAD_UTF8:' + path)
            texts[path] = ''
            continue
        texts[path] = body
        errors.extend(broken_links(root, path, body))
    errors.extend(content_errors(texts))
    baseline = baseline_files(root)
    for path in SOURCE_PATHS:
        if path not in baseline:
            errors.append('SOURCE_NOT_PRESENT_AT_BASELINE:' + path)
    # Bất biến tương thích: bảy alias và hồ sơ nguyên gốc không được dời ở DOC-03A.
    for path in (
        'docs/INDEX.md', 'docs/architecture/CURRENT_GD1_ARCHITECTURE.md',
        'docs/modules/VIEWER3D.md', 'docs/modules/PROJECT_WORKSPACE.md',
        'docs/development/ENGINEERING_STANDARDS.md',
        'docs/development/R7_DOCUMENTATION_POLICY.md',
        'docs/roadmap/ROADMAP_V1_ARCHIVED.md',
    ):
        if not (root / path).is_file():
            errors.append('R7_ALIAS_MISSING:' + path)
    return {'schema': 'scantopath-doc03a-content-v1',
            'baseline': BASELINE, 'status': 'PASS' if not errors else 'FAIL',
            'docs_checked': len(FILES), 'source_paths_checked': len(SOURCE_PATHS),
            'manual_hmi': 'NOT_TESTED', 'hardware_decision': 'OPEN_REQUIRED_SOURCE_DECISION',
            'errors': errors}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        root = args.project_root.resolve(strict=True)
        output = args.out_dir.resolve()
        if output == root or output.is_relative_to(root):
            raise ValueError('EVIDENCE_MUST_BE_OUTSIDE_REPOSITORY')
        report = verify(root)
        output.mkdir(parents=True, exist_ok=True)
        (output / 'DOC03A_CONTENT_GATE.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('DOC-03A CONTENT', report['status'], 'docs', report['docs_checked'],
              'source_paths', report['source_paths_checked'], 'errors', len(report['errors']))
        for error in report['errors']:
            print('DOC-03A ERROR:', error)
        return 0 if report['status'] == 'PASS' else 1
    except (ValueError, OSError, RuntimeError) as exc:
        print('DOC-03A GATE ERROR:', repr(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
