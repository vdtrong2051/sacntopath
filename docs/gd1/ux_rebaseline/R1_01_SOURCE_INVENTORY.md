# R1.1 — Source inventory, ownership, dependency and deletion policy

**Revision:** R1 / 2026-10-25. **Repository:** `vdtrong2051/sacntopath`, `feat/gd1-desktop-ui`, immutable review baseline `359e0156a6f11154a416c9ea6888c2840d343a0f`. **Status:** design/inventory only; no source deletion, runtime refactor, database or RAW change.

## Evidence and limits

GitHub recursive tree for the exact baseline: **284 entries including directories, 234 tracked blobs, 111 Python source files under `src/`, 49 test files, 53 documentation Markdown files and 11 files in `cpp/`**. Checked code: `ui/shell/main_window.py` (482 lines), `ui/workspaces/pages.py` (183), `ui/components/{project_explorer,property_inspector,task_event_panel}.py`, `ui/theme/hmi_panel.qss` (222), Viewer controller (409), Viewer view (295), `render_ply.py`, `pick_point.py`, Project read/write coordinators, storage resolver/codes, schemas, architectural docs. Windows benchmark/HMI evidence from accepted 08.06.1–08.06.5 is historical, not a realtime UX benchmark.

**A GitHub tree + focused imports does not prove that a file is unreferenced**. The external `inventory.py` shipped with this R1 package checks local AST import edges for all tracked Python files when applied on Windows; it outputs a reproducible *candidate inventory*, never an automatic deletion list. Reflection, dynamic import, plugin APIs, monkeypatch targets, CLI entrypoints, and external clients require manual review.

## Decision codes

- `KEEP_ACTIVE`: used now by desktop or GĐ0/07/08 use cases; do not delete.
- `KEEP_FUTURE`: required by sessions 09–20+ or integration substrate; unused by GUI today does **not** mean redundant.
- `CHANGE_R2/R3/R5`: active code with a UX/interface responsibility to restructure in a specific patch.
- `COMPAT_AUDIT_R6`: thin compatibility forwarding symbol; remove only after exact caller graph, negative import probe, Qt/CLI regression and public API review.
- `REPLACE_PLACEHOLDER`: current page is a stub whose user value is insufficient; replace the page's content, not necessarily delete its module.
- `DEV_MODE_ONLY`: current demonstration controls should disappear from normal UX while underlying task engine remains.

## Source-owned inventory (verified)

| Source path(s) | Classification | Evidence/decision | Planned migration |
|---|---|---|---|
| `src/scantopath/acquisition/**`, `src/scantopath/domain/raw_rgbd.py` | KEEP_ACTIVE+FUTURE | Gemini 2 acquisition + RAW contracts. Outside R2–R5 editing scope. | 09+ reuse for replay and reconstruction |
| `src/scantopath/metadata/**`, `src/scantopath/storage/**` | KEEP_ACTIVE+FUTURE | Schema, RAW reader, storage registry `P/S/T/C/R`; SQLite authoritative. | R3 calls only existing typed service; no schema rewrite |
| `cpp/**` | KEEP_ACTIVE+FUTURE | C++20 acquisition/geometry/native tests. | No removal or build changes |
| `src/scantopath/modules/project_workspace/application/**` | KEEP_ACTIVE | Typed DTO, commands, queries, and services. | R3 adds UI read models/adapters only as needed |
| `src/scantopath/modules/project_workspace/presentation/**` | CHANGE_R3 | Read/write/capture workflows already control real projects. | Preserve API, move main Project interactions into center page |
| `src/scantopath/ui/projects/{controller,write_controller,inspection_controller}.py` | KEEP_ACTIVE | Explicit imported Qt workers from feature coordinators. **Not dead code**. | Potential relocation only after separate compatibility migration |
| `src/scantopath/ui/projects/{edit_dialog,forms_contract,presentation}.py` | COMPAT_AUDIT_R6 | Thin `import *` re-exports of feature-native modules; active importers may still require them. | Deprecation/caller audit; no delete in R1 |
| `src/scantopath/application/projects/{models,service}.py` | COMPAT_AUDIT_R6 | Thin re-exports of `modules.project_workspace.application.*`. | Keep until full caller migration and tests |
| `src/scantopath/modules/project_workspace/presentation/workflows/base.py` | CHANGE_R3 | Dynamic `__getattr__`/`__setattr__` forwarding hides dependency ownership. | Consider explicit small contracts in R3, preserve existing behavior |
| `src/scantopath/ui/shell/main_window.py` | CHANGE_R2 | Toolbar + 3 global QDockWidgets + 20+ delegate adapters; not a permanent feature host. | Extract shell layout policy/presentation from composition root |
| `src/scantopath/ui/workspaces/pages.py` | REPLACE_PLACEHOLDER | Projects and Processing center cards redirect users to docks; Capture placeholder is intentional until 09. | R2 common frame; R3 real Projects center; Processing read-only overview staged for R3/R6 |
| `src/scantopath/ui/components/project_explorer.py` | CHANGE_R3 | Functional tree, read/write actions and selection signal. | Contextual Explorer; store selector not duplicated |
| `src/scantopath/ui/components/property_inspector.py` | CHANGE_R3/R5 | Currently Project/RAW DTO and buttons; Viewer inspector lives in center instead. | Single contextual right Inspector; no source conflation |
| `src/scantopath/ui/components/task_event_panel.py` | CHANGE_R2 | UI events, SQLite audit, task snapshots are distinct data. Large fixture task controls. | Collapsible bottom dock; Dev-only fixture button |
| `src/scantopath/ui/tasks/controller.py`, `src/scantopath/application/tasks/**` | KEEP_ACTIVE+FUTURE | Qt task bridge and cancellation engine, no deletion. | R2 only hides demo UI, leaves task contracts |
| `src/scantopath/ui/theme/hmi_panel.qss` | CHANGE_R2 | `QTabBar` 9x14 padding, toolbar 36px buttons, native dock/central border inconsistent. | Compact tokens and high-DPI responsive visual contract |
| `src/scantopath/modules/viewer3d/{application,domain}/**` | KEEP_ACTIVE | Camera/Ply/pick typed contracts; source identity/unit policy. | R5 add typed `SceneSource/GeometryKind` without breaking contracts |
| `src/scantopath/modules/viewer3d/infrastructure/{render_*,pick_point,camera_scene,fixture_scene,ply_header}.py` | CHANGE_R4/R5 | VTK child launched per import/orbit/pick, `vtkVertexGlyphFilter` renders points-only, PNG. | Keep tested as fallback until resident prototype passes acceptance |
| `src/scantopath/modules/viewer3d/presentation/{view,controller}.py` | CHANGE_R5 | QLabel preview, many buttons and text, 409-line QProcess controller. | Scene controller + viewport/overlays/inspector signals |
| `src/scantopath/ui/viewmodels/navigation.py`, `src/scantopath/application/contracts/**` | KEEP_ACTIVE | Navigation contract and immutable selection identity. | R2 adapts layout not command semantics |
| `tests/**`, `scripts/check_*`, `docs/**`, archived roadmap | KEEP_ACTIVE | Baselines, regression, safety gates and provenance history. | Never classify historical tests/docs as runtime bloat |

## Direct code findings and source proof

1. `main_window.py` creates brand `minimumWidth(126)`, four text QPushButtons with `minimumHeight(36)`, and adds `explorerDock`, `inspectorDock`, `taskDock` without per-workspace layouts. `_navigate` clears Explorer/Inspector selection on every workspace change; the center pages are not feature-owning.
2. `pages.py` creates a general purpose feature card for PROJECTS/PROCESSING and a large empty-state text. `main_window._connect_workspace_actions()` wires Projects to `_choose_project_store()` and Processing to `_open_audit_panel()`; these duplicate side-dock capabilities.
3. `task_event_panel.py` has 3 tabs (tasks, UI notices, SQLite audit), `Chạy tác vụ KIỂM THỬ` and cancel buttons even when no real job is running. The domain TaskManager is real and retained.
4. Viewer `view.py` uses `NavigationPreview(QLabel)` with pixmaps; `mouseReleaseEvent()` emits the orbit/pan gesture, not continuous pointer movement. `controller._start_job()` constructs `QProcess` on every navigation/picking job; renderer outputs PNG. `render_ply.py` passes PLY data through `vtkVertexGlyphFilter`; polygon faces are not rendered as mesh; dialog accepts `.ply` only.
5. Storage registry uses `metadata.sqlite3` at *one store root* and numbered public-code hierarchy `P/S/T/C/R`. A logical code path may be `not_materialized`; do not make up folders/paths from display labels. `ui/components/project_explorer.py` currently exposes `Mở kho…`, `Tải lại`, `＋ Thêm…`; no recent-store picker.

## Delete gate R6 (mandatory)

For each compatibility candidate: (1) static import edges source+tests and CLI; (2) literal references in tests/docs + monkeypatch hooks; (3) reflection/runtime dynamic imports; (4) API migration/deprecation table; (5) staged removal patch on feature branch; (6) full pytest, Qt, architecture/quality, CTest, RAW hash baseline; (7) Windows HMI. **Zero files are approved for deletion by R1.**

## Traceability

Live input tree: https://github.com/vdtrong2051/sacntopath/tree/359e0156a6f11154a416c9ea6888c2840d343a0f . Related: `docs/architecture/07_10_MODULAR_MONOLITH_TARGET.md`, `docs/decisions/ADR_002_NUMBERED_STORAGE_LAYOUT.md`, `docs/gd1/08_06_5_DEFECT_DISPOSITION_AND_HMI_WAIVER.md`.
