# GĐ1 — 07.11: Architecture hardening / Service decomposition

**Baseline:** `feat/gd1-desktop-ui` commit `f85cae4c09be5785acd5380f488265d4c0c4476e` (07.10 accepted). **No schema, RAW, Qt theme, Orbbec/native or public DTO changes.**

## Architectural decision (implemented)

Keep an **offline-first modular monolith**, with MVC/presenter in feature UI, and narrow application use cases. Do not build a second global MVC tree or duplicate SQLite/RAW drivers inside every feature. The process/UI composition root remains Qt; persisted identities and storage layout remain unchanged.

```text
modules/project_workspace/
  application/
    service.py       public compatibility façade / wiring (99 lines)
    context.py       scoped store context, schema v2 write guard
    records.py       persistence record -> immutable DTO mapper
    queries.py       list/get/tree/audit reads; no code allocation
    commands.py      explicit v2 writes, code assignment & recovery
    inspection.py    opt-in structural/RAW checksum inspection
    errors.py        stable exception identity across legacy imports
    ports.py         small read/write/audit/inspection protocols
    models.py        unchanged immutable DTO definitions
  infrastructure/
    sqlite_backend.py   existing-store read-only schema probe;
                        GĐ0/07.2 concrete adapter selection and safe path
  presentation/
    controller.py    existing MVC Qt feature controller (unchanged)

application/projects/* and ui/projects/* remain compatibility aliases.
```

**Runtime:** `ProjectWorkspaceService(root)` (same public signature) only builds context when user explicitly opens a store; its `__init__` is a **documented legacy composition exception** that lazily references feature infrastructure. Module imports themselves do not import the SQLite adapter or Qt. New use cases should accept narrow ports; future composition roots should inject adapters explicitly rather than expanding this exception. A full DIP claim is **not** justified yet.

## Non-negotiable contracts retained

- SQLite `metadata.sqlite3` is opened only from an existing path; schema v1 read-only and v2 explicit writes; no automatic v1→v2 migration.
- Reads (`list_projects`, `get_project_tree`, `get_capture`, `list_events`, etc.) never issue public codes or materialize RAW directories.
- Write `create_*` operations allocate numbered alias **after** metadata commit, with the exact existing `NumberingPendingError` and recovery ID semantics. Do not retry `create_*` after partial alias failure.
- Immutable DTO classes and exceptions preserve original import identity through `application.projects`; `ProjectWorkspaceService` public signatures remain stable.
- RAW inspection does not persist checksums, repair files, or assert geometric accuracy; v1 structure vs v2 SHA-256 remain distinct.
- Qt continues to run SQLite operations in a worker. No UI code, camera SDK or renderer in feature application.
- Legacy RAW migration is opt-in and reversible; this change does not modify it.

## Automated architectural gates

`python scripts/check_architecture_boundaries.py --project-root .` analyzes absolute **and relative** imports, including imports in function bodies and nested scopes. Guards are generic for future `modules/<feature>/application`, `domain`, `infrastructure`, and `presentation`; forbid application/domain dependencies on Qt/UI, concrete storage/metadata/SQLite and presentation. The single exact `application/service.py -> infrastructure/sqlite_backend` compatibility seam is explicitly constrained. Existing outer layers also may not import inward Qt/UI.

`tests/test_gd1_07_11_clean_architecture.py` checks public API and exception identity, read-only v1 behavior, v2 code-stability and close, component composition, lazy import and negative regression fixtures for relative/hidden cross-layer imports. `tests/test_gd1_07_10_architecture_report.py` is updated because the former `ProjectWorkspaceService` hotspot is **resolved**, and it must not be required to remain a hotspot. Other hotspots are still reported.

## Architecture acceptance and honest scope

| Concern | 07.11 result | Remaining work |
| --- | --- | --- |
| Project service SRP | Façade delegates to 4 focused units | `MetadataStore`, `NumberedStorageRegistry`, Qt feature controller still large |
| DIP | Concrete adapter imports moved to infrastructure; context injectable and legacy factory support preserved | `ProjectWorkspaceService.__init__` still bootstraps default adapter; deliberate compatibility exception |
| MVC clarity | Presentation/controller not mixed into application data or storage queries | Worker compatibility wrappers under `ui/projects` remain |
| OCP/ISP | Small read/write/inspection classes and existing Protocols | UI form action dispatch still switch-based |
| LSP | No inheritance assumptions added | Requires dedicated substitute contract suites for future backend implementation |
| Architecture regression protection | Absolute/relative/nested AST import checks + negative tests | AST alone cannot prove runtime contracts, threading safety, reflection or dynamic imports |

**Next debt, not automatically executed:** split `ProjectWorkspaceController` by selection/store lifecycle vs mutations; migrate Qt worker implementation ownership with compatibility tests; split `MetadataStore` repositories without changing SQL transactions; add tests for large captured sessions (performance/pagination) before Session 08. Avoid blind folder moves or duplication.

## Windows acceptance

1. Baseline HEAD `f85cae4`, clean worktree; `apply.ps1` (source-only).
2. `verify.ps1`: focused 07.11/07.10 contracts, complete GĐ0–GĐ1 Python/Qt suite, no hidden PySide6 skips, CTest 2/2, native hardware-free self-test, AST gate, compileall, git whitespace.
3. Visual UI confirmation: 07.9B appearance unchanged. Opt-in open v1 read-only / v2 edit; verify Capture, Audit and rollback behavior if needed using disposable synthetic stores.
4. Commit/push on `feat/gd1-desktop-ui` only after passing scripts and operator HMI approval. **No merge to main**, no SQLite or RAW migration.
