# R3.4 — Processing Workspace / Read-only ProcessingRun

Baseline: `4bef07c09f39e90a041eb4f39f80ebc23dff6fe1` (`feat/gd1-desktop-ui`, R3.3 accepted).

## Scope and information architecture

Replace the **visible** 06.3 Processing placeholder with a compact, bordered ProcessingRun list and metadata details. The legacy `workspacePanel` and `workspacePrimaryAction` **remain in the widget tree** for 07.9 compatibility, but the placeholder is hidden from operators.

The workspace consists of four distinct sections:

1. Header: **LẦN XỬ LÝ**, actual count and SQLite schema.
2. Filter strip: project and recorded run state.
3. Runs table: numbered public code, stage, state, session, timestamp. Flexible rows, tooltips for long text.
4. Context details: algorithm/version, input Capture IDs, output file **references**, JSON parameters, timestamps, error. Three physical `QFrame` dividers, compact spacing, no overlapping border paint.

## Data flow and invariants

`ProjectLoadController.loaded(ProjectLoadBundle)` → `ProcessingWorkspacePresenter` → `flatten_processing_runs(bundle.trees)` → `ProcessingWorkspace` (Qt read-only view).

`ProjectExplorer.selection_changed` → table highlight and context detail. A user row selection → `ProjectExplorer.tree.setCurrentItem()` → existing Inspector/Navigation. Do not maintain a second authoritative selection.

- SQLite v1/v2 handled by existing loader; no second open/query, schema migration or write.
- No camera activation, RAW verification, algorithm run, output-file existence check, path resolution or measurement claims.
- An output path in SQLite is a *reference*, not evidence a file exists.
- No demo/fake ProcessingRuns; empty and filtering states are explicit.
- Loading a different or invalid store clears prior rows **as soon as busy begins**.
- Unrelated Project Dashboard, Task Dock and Viewer files remain untouched.

## Files

- `src/scantopath/modules/project_workspace/presentation/controller.py` — feature-local presenter initialization after loaders/writer/capture checker already exist.
- `src/scantopath/modules/project_workspace/presentation/processing_workspace.py` — new read-only Qt pane and presenter.
- `src/scantopath/ui/theme/hmi_panel.qss` — Processing-only CSS, appended with separate selectors.
- `tests/test_gd1_r3_4_processing_workspace.py` — real Qt + disposable SQLite, selection/filters/stale-store/geometry cases.

## Windows HMI acceptance

1. Launch ScanToPath without selecting a store: Processing pane is empty, no SQLite created.
2. Open existing v1 and v2 stores with real ProcessingRun records; filtering works and count matches DTO tree.
3. Select a row: Explorer and Inspector select the same immutable `SelectionRef`.
4. Check long input/output/error values via tooltip; never report references as verified outputs.
5. Switch to an empty store or invalid root: old rows and details disappear.
6. Verify clear header/filter/table/details separation at full screen, no overlapping text and no dead-space placeholder.
7. Regression and startup smoke must pass before `publish.ps1 -ManualVisualAccepted`.

Automation PASS is not the same as Windows HMI acceptance.
