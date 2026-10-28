"""R8.3: chính sách SKIP theo định danh ca test thay vì số lượng."""
from __future__ import annotations

from pathlib import Path
import sys
from xml.etree.ElementTree import Element, SubElement, ElementTree

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_qt_acceptance_xml import REQUIRED, validate

_ALLOWED = (
    ('tests.integration.storage.test_gd1_07_2_numbered_storage',
     'test_path_rejects_escape_alias_and_symlinks'),
    ('tests.native.renderer.test_gd1_r4_3_transport_lifecycle',
     'test_r43_source_symlink_is_not_followed'),
    ('tests.unit.raw.test_raw_storage',
     'test_extra_file_or_symlink_is_rejected'),
)


def _fake_xml(path: Path, *, skips=(), duplicate=False, failure=False):
    root = Element('testsuite')
    for name in REQUIRED:
        SubElement(root, 'testcase', name=name, classname='tests.contracts.kien_truc.test_required')
    for i in range(350):
        SubElement(root, 'testcase', classname='tests.other.test_old', name=f'test_old_{i}')
    for klass, name, reason in skips:
        node = SubElement(root, 'testcase', classname=klass, name=name)
        SubElement(node, 'skipped', message=reason)
        if duplicate:
            node = SubElement(root, 'testcase', classname=klass, name=name)
            SubElement(node, 'skipped', message=reason)
    if failure:
        node = SubElement(root, 'testcase', classname='tests.other.test_broken', name='test_broken')
        SubElement(node, 'error', message='AssertionError')
    ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def test_r83_all_three_known_windows_symlink_skips_accepted(tmp_path):
    f = tmp_path / 'r.xml'
    skips = [(klass, name, 'Creating symlinks requires Windows privilege') for klass, name in _ALLOWED]
    _fake_xml(f, skips=skips)
    r = validate(f, platform='win32')
    assert r['errors'] == [] and r['skips'] == r['allowed_skips'] == 3


def test_r83_known_skip_refused_on_non_windows(tmp_path):
    f = tmp_path / 'r.xml'
    _fake_xml(f, skips=[(*_ALLOWED[0], 'Creating symlinks requires Windows privilege')])
    assert any('Unexpected skip' in x for x in validate(f, platform='linux')['errors'])


def test_r83_unknown_skip_refused_even_when_reason_mentions_symlink(tmp_path):
    f = tmp_path / 'r.xml'
    _fake_xml(f, skips=[('tests.other.test_random', 'test_random', 'Windows symlink privilege')])
    assert any('Unexpected skip' in x for x in validate(f, platform='win32')['errors'])


def test_r83_known_skip_requires_correct_reason(tmp_path):
    f = tmp_path / 'r.xml'
    _fake_xml(f, skips=[(*_ALLOWED[0], 'not installed')])
    assert any('Unexpected skip' in x for x in validate(f, platform='win32')['errors'])


def test_r83_duplicate_skipped_test_is_rejected(tmp_path):
    f = tmp_path / 'r.xml'
    _fake_xml(f, skips=[(*_ALLOWED[1], 'Windows symlink privilege')], duplicate=True)
    assert any('Duplicate skip entry' in x for x in validate(f, platform='win32')['errors'])


def test_r83_historical_flat_junit_classname_supported(tmp_path):
    f = tmp_path / 'r.xml'
    _fake_xml(f, skips=[('tests.test_raw_storage', _ALLOWED[2][1], 'Creating symlinks requires Windows privilege')])
    assert validate(f, platform='win32')['errors'] == []


def test_r83_failed_test_is_never_accepted(tmp_path):
    f = tmp_path / 'r.xml'
    _fake_xml(f, failure=True)
    assert any('failure/error' in x for x in validate(f)['errors'])


def test_r83_no_skips_is_valid_even_on_windows(tmp_path):
    f = tmp_path / 'r.xml'
    _fake_xml(f)
    assert validate(f, platform='win32')['errors'] == []
