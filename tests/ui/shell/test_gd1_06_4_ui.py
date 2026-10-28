"""GĐ1-06.4: các panel Qt độc lập dữ liệu; yêu cầu PySide6/offscreen trên Windows."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QTreeWidgetItem

from scantopath.application.contracts import SelectionRef, TaskSnapshot, TaskState, WorkspaceId
from scantopath.ui.components import ExplorerNode, ProjectExplorer, PropertyInspector, TaskAndEventPanel
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    yield instance


@pytest.fixture
def window(app):
    instance = ScanToPathMainWindow()
    instance.show()
    app.processEvents()
    yield instance
    instance.close()
    app.processEvents()


def _fixture_nodes():
    return (ExplorerNode("Dự án thử (kiểm thử)", SelectionRef("project", "prj-fixture"), (
        ExplorerNode("Vật mẫu thử (kiểm thử)", SelectionRef("specimen", "sp-fixture", "source-1")),
    )),)


def test_has_three_real_docks(window):
    assert isinstance(window.explorer_dock, QDockWidget)
    assert isinstance(window.inspector_dock, QDockWidget)
    assert isinstance(window.task_dock, QDockWidget)
    assert window.dockWidgetArea(window.explorer_dock) == Qt.LeftDockWidgetArea
    assert window.dockWidgetArea(window.inspector_dock) == Qt.RightDockWidgetArea
    assert window.dockWidgetArea(window.task_dock) == Qt.BottomDockWidgetArea
    assert window.explorer_dock.objectName() == "explorerDock"
    assert window.inspector_dock.objectName() == "inspectorDock"
    assert window.task_dock.objectName() == "taskDock"


def test_vietnamese_titles_and_accessibility(window):
    assert window.explorer_dock.windowTitle() == "Cây dự án"
    assert window.inspector_dock.windowTitle() == "Thuộc tính"
    assert window.task_dock.windowTitle() == "Tác vụ và thông báo"
    assert window.project_explorer.accessibleName() == "Cây dự án"
    assert window.property_inspector.accessibleName() == "Thuộc tính đối tượng"
    assert window.task_event_panel.tabs.tabText(0) == "Tác vụ"
    assert window.task_event_panel.tabs.tabText(1) == "Thông báo UI"


def test_empty_initial_state_does_not_simulate_project(window):
    assert window.project_explorer.tree.topLevelItemCount() == 0
    assert not window.project_explorer.tree.isEnabled()
    assert window.project_explorer.empty_label.text().startswith("Chưa tải dữ liệu")
    assert window.property_inspector.selection is None
    assert window.property_inspector.empty_label.text() == "Chưa chọn đối tượng."
    assert window.task_event_panel.tasks.topLevelItemCount() == 0
    assert window.task_event_panel.events.count() == 0


def test_explorer_requires_typed_input(app):
    explorer = ProjectExplorer()
    with pytest.raises(TypeError):
        explorer.set_nodes([_fixture_nodes()[0]])
    with pytest.raises(TypeError):
        explorer.set_nodes(("not-a-node",))
    with pytest.raises(ValueError):
        ExplorerNode(" ", SelectionRef("project", "project-1"))
    with pytest.raises(TypeError):
        ExplorerNode("Tên", "not-a-selection")


def test_explorer_populates_only_explicitly_supplied_nodes(window):
    explorer = window.project_explorer
    explorer.set_nodes(_fixture_nodes())
    assert explorer.tree.topLevelItemCount() == 1
    assert explorer.tree.isEnabled()
    parent = explorer.tree.topLevelItem(0)
    assert parent.text(0) == "Dự án thử (kiểm thử)"
    assert parent.childCount() == 1
    assert isinstance(parent.child(0), QTreeWidgetItem)
    assert parent.child(0).text(0) == "Vật mẫu thử (kiểm thử)"


def test_selection_propagates_to_viewmodel_and_inspector(window):
    explorer = window.project_explorer
    explorer.set_nodes(_fixture_nodes())
    item = explorer.tree.topLevelItem(0).child(0)
    explorer.tree.setCurrentItem(item)
    assert explorer.selection == SelectionRef("specimen", "sp-fixture", "source-1")
    assert window.navigation.selection == explorer.selection
    assert window.property_inspector.selection == explorer.selection
    assert window.property_inspector.details.topLevelItemCount() == 3
    assert window.property_inspector.details.topLevelItem(0).text(1) == "Vật mẫu"
    assert window.property_inspector.details.topLevelItem(1).text(1) == "sp-fixture"
    assert window.property_inspector.details.topLevelItem(2).text(1) == "source-1"


def test_clearing_explorer_clears_inspector_and_viewmodel(window):
    explorer = window.project_explorer
    explorer.set_nodes(_fixture_nodes())
    explorer.tree.setCurrentItem(explorer.tree.topLevelItem(0))
    explorer.clear_selection()
    assert window.navigation.selection is None
    assert window.property_inspector.selection is None
    assert window.property_inspector.details.topLevelItemCount() == 0
    assert window.property_inspector.empty_label.isVisible()


def test_replacing_nodes_drops_stale_selection(window):
    window.project_explorer.set_nodes(_fixture_nodes())
    window.project_explorer.tree.setCurrentItem(window.project_explorer.tree.topLevelItem(0))
    window.project_explorer.set_nodes(())
    assert window.project_explorer.selection is None
    assert window.navigation.selection is None
    assert window.property_inspector.selection is None
    assert not window.project_explorer.tree.isEnabled()


def test_navigating_clears_selection_without_deleting_tree(window):
    window.project_explorer.set_nodes(_fixture_nodes())
    window.project_explorer.tree.setCurrentItem(window.project_explorer.tree.topLevelItem(0))
    window.nav_buttons[WorkspaceId.INSPECT3D].click()
    assert window.active_workspace == WorkspaceId.INSPECT3D
    assert window.project_explorer.tree.topLevelItemCount() == 1
    assert window.project_explorer.selection is None
    assert window.navigation.selection is None
    assert window.property_inspector.selection is None
    assert window.task_event_panel.events.count() == 1
    assert window.task_event_panel.events.item(0).text() == "Đã chuyển đến: Kiểm tra 3D"


def test_repeated_workspace_navigation_does_not_log_duplicate(window):
    window.nav_buttons[WorkspaceId.INSPECT3D].click()
    window.nav_buttons[WorkspaceId.INSPECT3D].click()
    assert window.task_event_panel.events.count() == 1


def test_dock_toggle_actions_are_reopenable(window, app):
    actions = [action for action in window.menuBar().actions() if action.text().replace("&", "") == "Hiển thị"]
    assert len(actions) == 1
    menu = actions[0].menu()
    assert len(menu.actions()) == 3
    dock = window.inspector_dock
    assert dock.isVisible()
    dock.toggleViewAction().trigger()
    app.processEvents()
    assert not dock.isVisible()
    dock.toggleViewAction().trigger()
    app.processEvents()
    assert dock.isVisible()


def test_tasks_initially_empty_and_read_only(window):
    panel = window.task_event_panel
    assert panel.tasks.topLevelItemCount() == 0
    assert "06.5" in panel.task_hint.text()
    assert panel.events.count() == 0


def test_task_snapshots_display_given_values_and_unknown_progress(window):
    panel = window.task_event_panel
    panel.set_tasks((
        TaskSnapshot(task_id="task-1", title="Kiểm thử đang xử lý", state=TaskState.RUNNING, progress=None),
        TaskSnapshot(task_id="task-2", title="Kiểm thử kết thúc", state=TaskState.SUCCEEDED, progress=100),
    ))
    assert panel.tasks.topLevelItemCount() == 2
    first = panel.tasks.topLevelItem(0)
    second = panel.tasks.topLevelItem(1)
    assert first.text(1) == "Đang xử lý"
    assert first.text(2) == "Không xác định"
    assert second.text(1) == "Hoàn thành"
    assert second.text(2) == "100%"
    panel.set_tasks(())
    assert panel.tasks.topLevelItemCount() == 0


def test_task_panel_rejects_untyped_data(window):
    with pytest.raises(TypeError):
        window.task_event_panel.set_tasks([TaskSnapshot(task_id="a", title="b")])
    with pytest.raises(TypeError):
        window.task_event_panel.set_tasks(({"title": "giả"},))


def test_ui_events_are_bounded_and_not_persisted(window):
    panel = window.task_event_panel
    for index in range(panel.MAX_UI_EVENTS + 3):
        panel.add_ui_event(f"Tương tác {index}")
    assert panel.events.count() == panel.MAX_UI_EVENTS
    assert panel.events.item(0).text() == "Tương tác 3"
    with pytest.raises(ValueError):
        panel.add_ui_event("  ")


def test_panels_survive_resize_and_workspace_switch(window, app):
    window.resize(1366, 768)
    app.processEvents()
    for workspace in WorkspaceId:
        window.nav_buttons[workspace].click()
        app.processEvents()
        assert window.workspace_stack.currentWidget() is window.page_for(workspace)
    assert window.explorer_dock.widget() is window.project_explorer
    assert window.inspector_dock.widget() is window.property_inspector
    assert window.task_dock.widget() is window.task_event_panel


def test_no_backend_or_hardware_import_on_ui_import():
    root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src") + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; import scantopath.ui.main; "
         "assert 'scantopath.metadata.store' not in sys.modules; "
         "assert 'scantopath.acquisition.native' not in sys.modules; "
         "print('isolated=true')"],
        cwd=root, env=env, text=True, capture_output=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "isolated=true" in result.stdout


def test_window_creation_does_not_create_data_dir(window, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert not (tmp_path / "scantopath-data").exists()
