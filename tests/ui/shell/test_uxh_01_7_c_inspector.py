"""01.7-C Inspector layout: preserve metadata/provenance and typed actions."""
from __future__ import annotations
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHeaderView
from scantopath.application.contracts import SelectionRef
from scantopath.ui.components.property_inspector import PropertyInspector


@pytest.fixture
def inspector():
    app = QApplication.instance() or QApplication([])
    p = PropertyInspector()
    p.resize(320, 650)
    p.show()
    app.processEvents()
    yield p
    p.close()
    app.processEvents()


def test_columns_expand_and_long_title_and_source_note_are_unclipped(inspector):
    p=inspector
    name='Scan session with long provenance ' * 8
    p.set_selection(SelectionRef('scan_session','session-017c'))
    p.set_store_fields((('Mã','S001'),('Tên phiên quét',name)))
    assert p.title_label.maximumHeight() > 10000
    assert p.note.maximumHeight() > 10000
    assert p.title_label.toolTip() == 'S001 · ' + name
    assert p.details.header().sectionResizeMode(1) == QHeaderView.Stretch
    assert p.details.topLevelItemCount() >= 2
    for width in (240,320,420):
        p.resize(width,650)
        QApplication.processEvents()
        assert p.details.header().sectionSize(1) >= 0
        assert p.details.topLevelItem(0).toolTip(1)


def test_capture_permissions_and_raw_disclaimer_not_changed(inspector):
    p=inspector
    p.set_selection(SelectionRef('capture','capture-017c'))
    p.set_store_fields((('Mã','C001'),('RAW','Chưa kiểm tra')))
    p.set_verify_capability(True)
    assert p.verify_button.isVisible()
    assert p.verify_button.isEnabled()
    assert p.edit_button.isHidden()
    p.set_capture_inspection('verified','RAW đã xác thực.')
    assert 'không phải xác nhận độ chính xác hình học' in p.note.text()
    assert any(p.details.topLevelItem(i).text(1) == 'Đã kiểm tra'
               for i in range(p.details.topLevelItemCount()))
