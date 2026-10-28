"""R8.3: hợp đồng fixture tổng hợp và danh mục SKIP, không mở camera/VTK."""
from __future__ import annotations

import ast
from pathlib import Path

from tests.support.raw_fixture import raw
from tests.support.project_seed import _seed_v1, _seed_numbered

ROOT = Path(__file__).resolve().parents[3]


def test_r83_raw_fixture_is_synthetic_deterministic_and_independent():
    a = raw(session='a', specimen='b', capture_id='c')
    b = raw(session='a', specimen='b', capture_id='c')
    assert a is not b
    assert a.color_mjpeg == b.color_mjpeg and a.depth_y16_le == b.depth_y16_le
    assert a.metadata.measured is False
    assert a.metadata.capture_id == 'c'
    assert len(a.depth_y16_le) == 3 * 2 * 2
    assert a.metadata.depth_scale_m_per_unit == 0.001


def test_r83_v1_seed_uses_only_temporary_store(tmp_path):
    from scantopath.metadata.store import MetadataStore
    assert _seed_v1(tmp_path, with_capture=False) is None
    with MetadataStore(tmp_path) as store:
        projects = store.list_projects()
        assert any(p['project_id'] == 'p-078' for p in projects)
    assert (tmp_path / 'metadata.sqlite3').is_file()
    assert not (tmp_path / 'sessions').exists()


def test_r83_numbered_seed_only_explicitly_migrates_temporary_store(tmp_path):
    from scantopath.metadata.store import MetadataStore
    cap, backup, _assigned = _seed_numbered(tmp_path, with_capture=False)
    assert cap is None and backup.is_file()
    with MetadataStore(tmp_path) as store:
        assert any(p['project_id'] == 'p-078' for p in store.list_projects())
    assert not (tmp_path / 'sessions').exists()


def test_r83_no_cross_test_import_in_shared_fixtures():
    for name in ('raw_fixture.py', 'project_seed.py'):
        tree = ast.parse((ROOT / 'tests/support' / name).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').startswith(('test_', 'tests.unit', 'tests.integration'))


def test_r83_legacy_source_string_check_replaced_by_ast_contract():
    src = (ROOT / 'tests/ui/viewer/test_gd1_r5_2_live_viewer.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    targeted = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef)
                    and node.name == 'test_r52_composition_root_contains_bounded_close_gate')
    assert 'ast.parse' in ast.get_source_segment(src, targeted)
    assert "assert 'LiveViewer3DController(' in bootstrap" not in ast.get_source_segment(src, targeted)


def test_r83_required_skip_functions_exist_in_correct_files():
    accepted = {
        'tests/integration/storage/test_gd1_07_2_numbered_storage.py':
            'test_path_rejects_escape_alias_and_symlinks',
        'tests/native/renderer/test_gd1_r4_3_transport_lifecycle.py':
            'test_r43_source_symlink_is_not_followed',
        'tests/unit/raw/test_raw_storage.py':
            'test_extra_file_or_symlink_is_rejected',
    }
    for path, name in accepted.items():
        tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
        assert any(isinstance(n, ast.FunctionDef) and n.name == name for n in tree.body)
