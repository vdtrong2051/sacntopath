"""GD1 06.2: unit/contract tests, no camera, Qt or filesystem side effects."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import subprocess
import sys

import pytest

from scantopath.application.contracts import (
    CommandOutcome, CommandRequest, CommandStatus, SelectionRef, SourceContext,
    TaskSnapshot, TaskState, UiDataState, WorkspaceId,
)
from scantopath.application.services import CommandService, NavigationService
from scantopath.ui.viewmodels import NavigationViewModel


def test_workspace_ids_match_approved_four_workspaces():
    assert {v.value for v in WorkspaceId} == {
        "projects", "capture", "inspect3d", "processing",
    }


def test_data_state_keeps_observed_estimated_validated_distinct():
    assert UiDataState.MEASURED != UiDataState.VALIDATED
    assert UiDataState.FIXTURE != UiDataState.MEASURED
    assert UiDataState.INSUFFICIENT_EVIDENCE != UiDataState.ESTIMATED


def test_navigation_service_select_idempotent_revision():
    service = NavigationService()
    assert service.current().as_dict() == {"workspace": "projects", "revision": 0}
    assert service.select(WorkspaceId.PROJECTS).revision == 0
    assert service.select(WorkspaceId.INSPECT3D).revision == 1
    assert service.select(WorkspaceId.INSPECT3D).revision == 1
    assert service.select(WorkspaceId.PROCESSING).revision == 2


def test_navigation_service_rejects_unknown_workspace_without_state_change():
    service = NavigationService()
    with pytest.raises(ValueError):
        service.select("unknown")
    assert service.current().workspace == WorkspaceId.PROJECTS


def test_command_exec_select_and_current_have_matching_request_ids():
    bus = CommandService()
    request = CommandRequest(request_id="req-01", command="workspace.select",
                             parameters={"workspace": "capture"})
    result = bus.execute(request)
    assert result.status is CommandStatus.SUCCEEDED
    assert result.request_id == "req-01"
    assert result.as_dict()["value"] == {"workspace": "capture", "revision": 1}
    assert bus.execute(CommandRequest("req-02", "workspace.current")).as_dict() == {
        "request_id": "req-02", "status": "succeeded",
        "value": {"workspace": "capture", "revision": 1},
        "error_code": None, "message": None,
    }


@pytest.mark.parametrize("parameters", [{}, {"workspace": "bogus"},
                                        {"workspace": 7}, {"workspace": "projects", "extra": True}])
def test_navigation_command_bad_arguments_fail_not_crash(parameters):
    bus = CommandService()
    result = bus.execute(CommandRequest("req", "workspace.select", parameters))
    assert result.status is CommandStatus.FAILED
    assert result.error_code == "INVALID_ARGUMENT"
    assert bus.navigation.current().workspace == WorkspaceId.PROJECTS


def test_current_command_rejects_parameters():
    result = CommandService().execute(CommandRequest("req", "workspace.current", {"a": 1}))
    assert result.status is CommandStatus.FAILED
    assert result.error_code == "INVALID_ARGUMENT"


@pytest.mark.parametrize("command", ["camera.capture", "geometry.measure", "project.create", "ai.segment"])
def test_unimplemented_commands_never_fake_a_success(command):
    result = CommandService().execute(CommandRequest("req", command))
    assert result.status is CommandStatus.NOT_IMPLEMENTED
    assert result.error_code == "NOT_IMPLEMENTED"
    assert result.value is None


def test_json_parameters_are_snapshot_and_immutable():
    params = {"nested": {"items": [1, {"value": True}]}}
    request = CommandRequest("req", "workspace.current", params)
    params["nested"]["items"].append(5)
    assert len(request.parameters["nested"]["items"]) == 2
    with pytest.raises(TypeError):
        request.parameters["nested"]["other"] = "modified"
    with pytest.raises((TypeError, AttributeError)):
        request.parameters["nested"]["items"][0] = 999


def test_outcome_serializes_without_framework_objects():
    outcome = CommandOutcome("req-3", CommandStatus.SUCCEEDED,
                             value={"display": ["a", {"ok": True}]})
    assert json.loads(json.dumps(outcome.as_dict()))["value"]["display"][1] == {"ok": True}
    with pytest.raises(FrozenInstanceError):
        outcome.request_id = "tamper"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), object(), {1: 2}])
def test_commands_reject_non_json_values(bad):
    with pytest.raises(ValueError):
        CommandRequest("req", "workspace.current", {"bad": bad})


def test_outcome_status_error_invariants():
    with pytest.raises(ValueError):
        CommandOutcome("req", CommandStatus.FAILED)
    with pytest.raises(ValueError):
        CommandOutcome("req", CommandStatus.SUCCEEDED, error_code="BAD")
    assert CommandOutcome("req", CommandStatus.CANCELLED,
                          error_code="USER_CANCELLED").status is CommandStatus.CANCELLED


def test_source_context_preserves_unknown_frame_and_no_fake_pose():
    ctx = SourceContext(data_state=UiDataState.MEASURED,
                        source_ids=("capture-1",))
    assert ctx.frame_id is None
    assert ctx.units is None
    assert not hasattr(ctx, "world_pose")
    assert ctx.data_state is not UiDataState.VALIDATED


def test_selection_is_id_reference_not_loaded_object():
    value = SelectionRef("capture", "abc_12", source_id="raw-1")
    assert value.entity_id == "abc_12"
    with pytest.raises(ValueError):
        SelectionRef("Bad Type", "abc")


@pytest.mark.parametrize("progress", [-0.5, 100.1, float("nan"), "12", True])
def test_task_snapshot_rejects_invalid_progress(progress):
    with pytest.raises(ValueError):
        TaskSnapshot(task_id="task", title="Test", progress=progress)


def test_task_snapshot_supports_unknown_progress_and_cooperative_cancel():
    snap = TaskSnapshot("task", "Offline fixture", state=TaskState.RUNNING,
                        progress=None, can_cancel=True)
    assert snap.progress is None and snap.can_cancel
    assert TaskSnapshot("task", "Finished", state=TaskState.CANCELLED).state is TaskState.CANCELLED
    with pytest.raises(ValueError):
        TaskSnapshot("task", "Done", state=TaskState.SUCCEEDED, can_cancel=True)
    with pytest.raises(ValueError):
        TaskSnapshot("task", "Error", state=TaskState.RUNNING, error="a fault")


def test_viewmodel_moves_workspace_clears_selection_and_keeps_failures_visible():
    vm = NavigationViewModel()
    assert vm.workspace is WorkspaceId.PROJECTS
    vm.select_entity(SelectionRef("project", "project-1"))
    res = vm.select_workspace("inspect3d")
    assert res.status is CommandStatus.SUCCEEDED
    assert vm.workspace is WorkspaceId.INSPECT3D
    assert vm.selection is None
    assert vm.last_outcome == res
    failed = vm.select_workspace("invalid")
    assert failed.status is CommandStatus.FAILED
    assert vm.workspace is WorkspaceId.INSPECT3D


def test_viewmodel_is_framework_agnostic_on_clean_python_import():
    code = (
        "import sys; from scantopath.ui.viewmodels import NavigationViewModel; "
        "from scantopath.application.services import CommandService; "
        "assert not any(n.startswith(('PySide6', 'vtk', 'open3d', 'pyorbbecsdk')) "
        "for n in sys.modules); "
        "assert NavigationViewModel().workspace.value == 'projects'"
    )
    run = subprocess.run([sys.executable, "-c", code], text=True,
                         capture_output=True, timeout=20, check=False)
    assert run.returncode == 0, run.stdout + run.stderr
