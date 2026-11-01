"""01.7-C static contract: only UI layout; no device/data/VTK code changes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def test_capture_is_presentation_only_and_tabs_keep_identity():
    text = read('src/scantopath/modules/capture/presentation/workspace_layout.py')
    assert 'class ResponsiveCaptureWorkflowBar(QFrame)' in text
    assert 'self.workflow_bar.attach_hint(hint)' in text
    assert 'self.tabs.setUsesScrollButtons(True)' in text
    assert 'self.tabs.setElideMode(Qt.ElideRight)' in text
    assert 'self.tabs.setCurrentWidget(live)' in text
    assert 'self.tabs.addTab(replay, "02  RAW đã lưu · Phát lại")' in text
    assert 'process_camera' not in text
    assert 'native_camera' not in text


def test_inspector_layout_does_not_infer_data_or_geometry():
    text = read('src/scantopath/ui/components/property_inspector.py')
    assert 'self.details.header().setSectionResizeMode(1, QHeaderView.Stretch)' in text
    assert 'self.title_label.setMaximumHeight(56)' not in text
    assert 'self.note.setMaximumHeight(70)' not in text
    assert 'def set_store_fields' in text
    assert 'def set_capture_inspection' in text
    assert 'RAW chưa được kiểm tra theo thao tác này' in text
