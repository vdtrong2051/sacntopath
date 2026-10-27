# 07.10 — ScanToPath Modular Monolith / MVC

Baseline: feat/gd1-desktop-ui @ 5b416e4 (07.9B accepted); no UI/RAW/SQLite schema migration in this change.

## Decision

A **single offline-first desktop executable/process** with feature-oriented bounded contexts and a native C++ core. Each feature may contain domain model, application use cases, presentation controller/ViewModel, infrastructure adapters. Reusable technical infrastructure remains shared; **do not duplicate SQLite, RAW contracts or camera drivers per feature**. Qt widgets form Views; presentation Qt controller adapts signals; application DTO/services provide use cases; infrastructure owns persistence/device I/O. This is MVC within modular monolith, not strict global MVC folders.

## Module map (implemented vs reserved)

- `modules/project_workspace/application/`: *implemented* typed models, service and narrow read/write/audit/capture ports. `ProjectWorkspaceService` is a v1-compatible façade: persistence factories are injectable; default concrete adapters intentionally remain for legacy compatibility, so DIP is **partial**.
- `modules/project_workspace/presentation/`: *implemented* feature `ProjectWorkspaceController` plus Qt dialog, DTO presenter, validated form commands. Shell no longer directly coordinates project load/write/integrity. Existing QThread controllers remain under `ui/projects` temporarily to retain test monkeypatch hooks and public imports.
- `modules/project_workspace/domain/`: intentionally empty for now; don't move persistence DTOs here or invent domain logic.
- `modules/project_workspace/infrastructure/`: reserved; actual `MetadataStore`, `NumberedStorageRegistry`, `SessionStore` stay in tested shared infrastructure until adapter migration can be independently proven.
- `application/projects/models.py`, `application/projects/service.py`, `ui/projects/forms_contract.py`, `ui/projects/presentation.py`, `ui/projects/edit_dialog.py`: **compatibility re-exports**. Existing imports and tests keep working. New feature code should use `modules.project_workspace.*`.
- `ui/shell/main_window.py`: main-process composition, dock/menu/workspace, status and safe close. Compatibility delegates are temporary until external callers migrate.
- `acquisition/`, `domain/raw_rgbd.py`, `storage/`, `metadata/`: preserved exactly; no forced move, no fake Capture or camera I/O.
- `modules/capture`, `modules/processing`, `modules/inspect3d`: **not implemented**; do not scaffold empty packages before their first real feature slice. Session 08 remains out of scope.

## Import boundaries (enforced)

1. domain and application may not import PySide6/Qt or `scantopath.ui`.
2. infrastructure (`metadata`, `storage`) may not import Qt/UI presentation.
3. module application cannot import its own presentation layer.
4. feature presenter cannot import metadata/storage directly (access through worker/service ports).
5. shell may import project presentation, but may not directly use persistence/RAW APIs.
6. Exceptions must be explicit, reviewed and accompanied by integration tests — not hidden ignore globs.

Run: `python scripts/check_architecture_boundaries.py --project-root .`

## SOLID evidence & remaining debt

| Principle | State after 07.10 | Limitation / next step |
|---|---|---|
| SRP | Improved | Project UI orchestration extracted (~316 lines) from MainWindow; service/metadata still large. |
| OCP | Partial | Ports permit new implementations; UI form action mapping still switches explicitly. |
| LSP | Not demonstrated | Protocol contracts exist; substitute testing with independent adapters needed. |
| ISP | Improved | Separate project read/write/audit/integrity Protocols; existing façade remains broad for compatibility. |
| DIP | Partial | Inject factories into service; default concrete SQLite/numbered dependencies still retained. |

## Follow-on backlog (NOT executed)

1. ARC-03: create SQLite/numbered adapter implementation in feature infrastructure with end-to-end transaction boundary tests and explicit composition injection; remove default concrete fallback **only after** other importers migrate.
2. ARC-04: move `ui/projects` Qt worker controllers into feature package with stable patch injection seam; then remove old paths in a major compatibility release.
3. ARC-05: split `ProjectWorkspaceService` into query/command/audit use-case implementations behind ports, keeping current façade for legacy.
4. ARC-06: split large `MetadataStore` and numbered registry by repository responsibility without changing SQLite schema/transaction semantics; benchmark thousands of captures before adding pagination.
5. ARC-07: next actual feature module for Session 08; do not pre-implement VTK or device control.

## Acceptance

- Full existing GĐ0–07.9B Python+Qt regression, CTest 2/2, native self-test `hardware_access=false`.
- Unit boundary guards plus façade identity, injected fake repository, GUI no-autoload and safe close tests.
- GUI renders same 07.9B theme and navigation; v1 read-only; v2 CRUD; integrity/audit/rollback behavior unchanged.
- No SQLite migration, no RAW writes, no new native device access, no branch or merge to `main`.
