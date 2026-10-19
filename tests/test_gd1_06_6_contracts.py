"""06.6 integrated acceptance: deterministic, headless foundation invariants.

No camera, Qt, SQLite or VTK dependency. Assertions reflect code contracts,
not claims about metrology or camera pose accuracy.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

from scantopath.application.contracts import (
    CommandRequest, CommandStatus, SelectionRef, SourceContext, UiDataState,
    WorkspaceId,
)
from scantopath.application.services import CommandService
from scantopath.ui.viewmodels.navigation import NavigationViewModel


def test_four_workspace_ids_stable():
    assert [w.value for w in WorkspaceId] == [
        "projects", "capture", "inspect3d", "processing",
    ]


def test_command_service_cannot_claim_missing_capabilities():
    commands = CommandService()
    for operation in ("project.create", "camera.start", "geometry.reconstruct", "metric.validate"):
        result = commands.execute(CommandRequest(
            request_id=f"gd1-{operation}", command=operation,
        ))
        assert result.status is CommandStatus.NOT_IMPLEMENTED
        assert result.error_code == "NOT_IMPLEMENTED"
        assert result.value is None
        json.dumps(result.as_dict(), allow_nan=False)


def test_measured_is_not_metric_validated():
    assert UiDataState.MEASURED is not UiDataState.VALIDATED
    assert UiDataState.FIXTURE is not UiDataState.MEASURED
    context = SourceContext(data_state=UiDataState.MEASURED, source_ids=("capture-1",))
    assert context.data_state is UiDataState.MEASURED
    assert context.frame_id is None
    assert context.units is None


def test_selection_cleared_after_navigation_without_loading_metadata():
    vm = NavigationViewModel()
    vm.select_entity(SelectionRef("project", "project-local-only"))
    result = vm.select_workspace(WorkspaceId.INSPECT3D)
    assert result.status is CommandStatus.SUCCEEDED
    assert vm.selection is None
    assert vm.workspace == WorkspaceId.INSPECT3D


def test_ui_hmi_qss_is_packaged_as_resource_without_importing_qt():
    from scantopath.ui.theme import load_hmi_qss

    qss = load_hmi_qss()
    assert len(qss) > 100
    assert "QMainWindow" in qss
    assert "QDockWidget" in qss
    assert "QStatusBar" in qss


def test_ui_entrypoint_remains_offline_by_default():
    # Static contract: import PySide6 only; NEVER import SDK or open camera by default.
    root = Path(__file__).resolve().parents[1]
    entry = (root / "src/scantopath/ui/main.py").read_text(encoding="utf-8")
    assert "ScanToPathMainWindow" in entry
    assert "app.exec()" in entry
    assert "capture_one_raw" not in entry
    assert "OrbbecCameraSource" not in entry
    assert "MetadataStore(" not in entry
