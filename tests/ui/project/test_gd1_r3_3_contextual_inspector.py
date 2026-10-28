"""R3.3 Qt contract: truthful metadata, context controls and visible separators."""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame
from scantopath.application.contracts import SelectionRef
from scantopath.modules.project_workspace.application.models import ProjectTree
from scantopath.modules.project_workspace.presentation.presenter import project_rows
from scantopath.ui.components.property_inspector import PropertyInspector


@pytest.fixture(scope='module')
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def inspector(qapp):
    widget = PropertyInspector()
    widget.resize(260, 590)
    widget.show()
    qapp.processEvents()
    yield widget
    widget.close()
    qapp.processEvents()


def _rows(view):
    return {view.details.topLevelItem(i).text(0): view.details.topLevelItem(i).text(1)
            for i in range(view.details.topLevelItemCount())}


def test_empty_state_is_compact_and_does_not_show_stale_controls(inspector):
    assert inspector.selection is None
    assert inspector.empty_label.isVisible()
    assert not inspector.context_frame.isVisible()
    assert not inspector.actions_frame.isVisible()
    assert inspector.details.topLevelItemCount() == 0


def test_project_context_has_real_header_separator_and_read_only_fields(inspector, qapp):
    inspector.set_selection(SelectionRef('project', 'project-1'))
    inspector.set_store_fields((('Mã', 'P0001'), ('Tên dự án', 'Mẫu kỹ thuật'),
                                ('Mô tả', 'Đã được nhập'), ('Đường dẫn', '01_PROJECTS/...')))
    inspector.set_actions(can_edit=True, can_close_session=False)
    qapp.processEvents()
    assert inspector.context_frame.isVisible()
    assert inspector.context_separator.isVisible()
    assert inspector.context_separator.height() == 1
    assert inspector.action_separator.height() == 1
    assert inspector.context_frame.geometry().bottom() < inspector.properties_frame.geometry().top()
    assert inspector.title_label.text() == 'P0001 · Mẫu kỹ thuật'
    assert _rows(inspector)['Đường dẫn'] == '01_PROJECTS/...'
    assert inspector.edit_button.isEnabled()
    assert inspector.edit_button.isVisible()
    assert not inspector.close_button.isVisible()
    assert not inspector.verify_button.isVisible()
    assert 'SQLITE' in inspector.section_label.text()


def test_kind_specific_actions_and_no_previous_metadata_leak(inspector, qapp):
    inspector.set_selection(SelectionRef('scan_session', 'session-1'))
    inspector.set_store_fields((('Mã', 'T0001'), ('Tên phiên quét', 'Quét chính'),
                                ('Trạng thái', 'Đang mở')))
    inspector.set_actions(can_edit=True, can_close_session=True)
    qapp.processEvents()
    assert inspector.close_button.isVisible() and inspector.close_button.isEnabled()
    assert 'Mẫu kỹ thuật' not in inspector.title_label.text()
    assert 'Đường dẫn' not in _rows(inspector)
    inspector.set_selection(SelectionRef('capture', 'capture-1'))
    inspector.set_store_fields((('Mã', 'C0001'), ('RAW', 'Chưa kiểm tra RAW')))
    inspector.set_verify_capability(True)
    qapp.processEvents()
    assert inspector.verify_button.isVisible() and inspector.verify_button.isEnabled()
    assert not inspector.edit_button.isVisible()
    inspector.set_capture_inspection('verified', 'Checksum đúng.')
    assert _rows(inspector)['RAW'] == 'Đã kiểm tra'
    assert 'không phải xác nhận độ chính xác hình học' in inspector.note.text()
    inspector.set_selection(SelectionRef('processing_run', 'run-1'))
    inspector.set_store_fields((('Mã', 'R0001'), ('Công đoạn', 'lọc điểm'),
                                ('Đầu ra (tham chiếu)', 'output.ply')))
    qapp.processEvents()
    assert not inspector.actions_frame.isVisible()
    assert _rows(inspector)['Công đoạn'] == 'lọc điểm'
    assert 'RAW' not in _rows(inspector)
    inspector.set_selection(None)
    qapp.processEvents()
    assert inspector.empty_label.isVisible() and not inspector.context_frame.isVisible()
    assert not inspector.actions_frame.isVisible()


def test_specimen_metadata_and_reference_only_selection(inspector):
    inspector.set_selection(SelectionRef('specimen', 's1'))
    inspector.set_store_fields((('Mã', 'S0001'), ('Tên vật mẫu', 'Chi tiết A'),
                                ('Dự án ID', 'p1'), ('Mô tả', 'Kim loại')))
    assert inspector.title_label.text() == 'S0001 · Chi tiết A'
    assert _rows(inspector)['Dự án ID'] == 'p1'
    inspector.set_selection(SelectionRef('point', 'point-1'))
    assert 'SQLITE' not in inspector.section_label.text()
    assert 'tham chiếu' in inspector.note.text()


def test_invalid_fields_rejected_without_any_sqlite_operation(inspector):
    inspector.set_selection(SelectionRef('project', 'p1'))
    with pytest.raises(TypeError):
        inspector.set_store_fields([('Mã', 'P0001')])
    with pytest.raises(TypeError):
        inspector.set_store_fields((('Mã', 1),))
    assert 'Mã' not in _rows(inspector)


def _storage(code, path='01_PROJECTS/P0001', state='not_materialized'):
    return SimpleNamespace(public_code=code, relative_path=path, state=state)


def test_project_projection_includes_metadata_for_five_entity_types_without_guessing_raw():
    p = SimpleNamespace(project_id='p', name='Dự án', description='Mô tả thật',
                        created_at='2026-01-01', updated_at='2026-01-02', storage=_storage('P0001'))
    s = SimpleNamespace(specimen_id='s', project_id='p', label='Vật mẫu', description='Vật thử',
                        created_at='2026-01-03', updated_at='2026-01-04', storage=_storage('S0001'))
    c = SimpleNamespace(capture_id='c', session_id='t', schema_version=2, kind='rgbd',
                        data_state=SimpleNamespace(value='measured'), registered_at='2026-01-05',
                        storage=_storage('C0001', state='not_checked'))
    r = SimpleNamespace(run_id='r', session_id='t', stage='filter', algorithm='test-algorithm',
                        version='v1', state='completed', input_capture_ids=('c',),
                        output_files=('point_cloud.ply',), parameters_json='{}', error_message=None,
                        created_at='2026-01-06', started_at=None, finished_at=None,
                        storage=_storage('R0001'))
    t = SimpleNamespace(session_id='t', specimen_id='s', label='Phiên', state='open',
                        created_at='2026-01-03', closed_at=None, storage=_storage('T0001'),
                        captures=(c,), processing_runs=(r,))
    tree = ProjectTree(project=p, specimens=(SimpleNamespace(specimen=s, sessions=(t,)),))
    rows = project_rows((tree,))
    pr = rows[0]
    sp = pr.children[0]
    sess = sp.children[0]
    cap, run = sess.children
    def fields(row): return dict(row.fields)
    assert fields(pr)['Mô tả'] == 'Mô tả thật'
    assert fields(sp)['Dự án ID'] == 'p'
    assert fields(sess)['Tạo lúc'] == '2026-01-03'
    assert fields(cap)['RAW schema'] == '2'
    assert fields(cap)['RAW'] == 'Chưa kiểm tra RAW'
    assert fields(run)['Đầu ra (tham chiếu)'] == 'point_cloud.ply'
    assert fields(run)['Bắt đầu'] == 'Chưa có'
    assert fields(pr)['Lưu trữ'] == 'Chưa có thư mục vật lý'
