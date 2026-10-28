"""R5.3 presentation-only Inspector routing for external 3D geometry.

Does not identify external PLY/OBJ files as SQLite project objects.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QTreeWidgetItem, QPushButton, QApplication


class SceneInspectorBridge(QObject):
    def __init__(self, inspector, viewer):
        super().__init__(viewer.page)
        self.inspector = inspector
        self.viewer = viewer
        self._owned = False
        self._xyz_to_copy: str | None = None
        self.copy_button = QPushButton('Sao chép XYZ', inspector.properties_frame)
        self.copy_button.setObjectName('viewer3dCopyXYZ')
        self.copy_button.setToolTip('Sao chép đầy đủ tọa độ từ kết quả hình học; đơn vị chưa xác nhận')
        self.copy_button.clicked.connect(self._copy_xyz)
        inspector.properties_frame.layout().insertWidget(
            inspector.properties_frame.layout().count()-1, self.copy_button)
        self.copy_button.hide()
        viewer.scene_inspection.connect(self.show_scene)
        viewer.page.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.viewer.page and event.type() == QEvent.Hide:
            self.clear()
        return super().eventFilter(watched, event)

    def _copy_xyz(self):
        if self._owned and self._xyz_to_copy is not None:
            QApplication.clipboard().setText(self._xyz_to_copy)

    def clear(self):
        if not self._owned:
            return
        self._owned = False
        self._xyz_to_copy = None
        self.copy_button.hide()
        self.inspector.set_selection(None)

    def show_scene(self, payload):
        if payload is None:
            self.clear()
            return
        if (type(payload) is not dict or set(payload) != {'kind', 'title', 'fields', 'note', 'copy_xyz'} or
                type(payload['kind']) is not str or type(payload['title']) is not str or
                type(payload['note']) is not str or
                (payload['copy_xyz'] is not None and
                 (type(payload['copy_xyz']) is not str or len(payload['copy_xyz']) > 120)) or
                type(payload['fields']) is not tuple or
                any(type(f) is not tuple or len(f) != 2 or
                    any(type(s) is not str or len(s) > 300 for s in f)
                    for f in payload['fields'])):
            raise ValueError('INVALID_SCENE_INSPECTOR_PAYLOAD')
        self.inspector.set_selection(None)
        self._owned = True
        self._xyz_to_copy = payload['copy_xyz']
        self.copy_button.setVisible(self._xyz_to_copy is not None)
        self.inspector.kind_label.setText(payload['kind'])
        self.inspector.title_label.setText(payload['title'])
        self.inspector.title_label.setToolTip(payload['title'])
        self.inspector.section_label.setText('THÔNG TIN HÌNH HỌC')
        self.inspector.details.clear()
        for name, value in payload['fields']:
            item = QTreeWidgetItem(self.inspector.details, [name, value])
            item.setToolTip(0, name)
            item.setToolTip(1, value)
        self.inspector.note.setText(payload['note'])
        self.inspector.empty_label.hide()
        self.inspector.context_frame.show()
        self.inspector.context_separator.show()
        self.inspector.properties_frame.show()
        self.inspector.actions_frame.hide()
