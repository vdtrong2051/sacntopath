"""Kiểm tra JUnit: Qt bắt buộc và SKIP symlink có định danh cụ thể.

Không chạy Qt, camera hoặc test: chỉ đọc XML. Một SKIP ngoài danh sách là lỗi.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

REQUIRED = (
    'test_shell_composes_feature_controller_without_autoload',
    'test_project_flow_through_composed_controller_in_v1_view_mode',
    'test_0712_qt_collaborators_share_only_the_feature_qobject',
    'test_0712_qt_shell_retains_controller_legacy_delegates',
)

# Chỉ ba ca đã ghi nhận tại R6/R7-D trên Windows; đường dẫn R8.2 + lịch sử.
_ALLOWED = (
    ('integration.storage.test_gd1_07_2_numbered_storage',
     'test_path_rejects_escape_alias_and_symlinks'),
    ('native.renderer.test_gd1_r4_3_transport_lifecycle',
     'test_r43_source_symlink_is_not_followed'),
    ('unit.raw.test_raw_storage',
     'test_extra_file_or_symlink_is_rejected'),
)


def _canonical_class(value: str) -> str:
    # Chấp nhận tên pytest `tests.<category>.<module>` hoặc `<category>.<module>`.
    return value.removeprefix('tests.')


def _allowed_keys() -> set[tuple[str, str]]:
    allowed = set(_ALLOWED)
    for class_name, test_name in _ALLOWED:
        # Hồ sơ trước R8.2 dùng đường dẫn tests/<file>.py.
        allowed.add((class_name.rsplit('.', 1)[-1], test_name))
    return allowed


def validate(path: Path, *, platform: str | None = None) -> dict:
    current_platform = sys.platform if platform is None else platform
    tests = list(ET.parse(path).iter('testcase'))
    issues: list[str] = []
    if len(tests) < 350:
        issues.append('Regression suite appears incomplete: fewer than 350 tests')
    for name in REQUIRED:
        matching = [case for case in tests if case.get('name') == name]
        if len(matching) != 1 or list(matching[0]):
            issues.append(f'Qt test missing, skipped, failed or duplicated: {name}')
    if any(case.find('failure') is not None or case.find('error') is not None for case in tests):
        issues.append('At least one JUnit failure/error')
    skip_entries = [case for case in tests if case.find('skipped') is not None]
    seen: set[tuple[str, str]] = set()
    allow = _allowed_keys()
    for case in skip_entries:
        key = (_canonical_class(case.get('classname', '')), case.get('name', ''))
        detail = case.find('skipped')
        assert detail is not None
        reason = ((detail.get('message') or '') + ' ' + (detail.text or '')).lower()
        if current_platform != 'win32' or key not in allow or 'symlink' not in reason or 'privilege' not in reason:
            issues.append(f'Unexpected skip: {key[0]}::{key[1]}: {reason[:150]}')
        if key in seen:
            issues.append(f'Duplicate skip entry: {key[0]}::{key[1]}')
        seen.add(key)
    return {'cases': len(tests), 'qt_required': len(REQUIRED), 'skips': len(skip_entries),
            'allowed_skips': len(skip_entries) - sum('Unexpected skip:' in x for x in issues),
            'errors': issues}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--junit', type=Path, required=True)
    a = p.parse_args()
    try:
        result = validate(a.junit)
    except (OSError, ET.ParseError) as exc:
        print('Qt acceptance XML error:', exc)
        return 1
    print('Qt acceptance:', result)
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
