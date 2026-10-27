# GĐ1 07.12 — Consolidation & 07.11 acceptance repair

**Base commit:** `f85cae4c09be5785acd5380f488265d4c0c4476e`. This release **includes all 13 previously applied, unpublished 07.11 files** and 07.12 source/test/docs, as **one cohesive commit**. Do not attempt to publish the broken 07.11 package first.

## Implementation and ownership

| Public façade (stable import) | Implementation ownership | Explicit contract retained |
|---|---|---|
| `metadata.store.MetadataStore` | `metadata.schema`; `metadata.repos.{projects,captures,processing,audit}` | Shared SQLAlchemy Engine; each original transaction boundary; SQLite schema version 1/2; existing audit monkeypatch seam; no implicit upgrade |
| `storage.numbered.NumberedStorageRegistry` | `storage.numbered_contracts`; `storage.numbered_ops.{codes,resolve,capture,catalog,migration}` | `BEGIN IMMEDIATE`; durable reservation/RAW commit/DB registration order; idempotent code assignment; safe paths; v1→v2 opt-in-only migration with SQLite backup |
| `modules.project_workspace.presentation.controller.ProjectWorkspaceController` | `presentation.workflows.{reading,writing,capture}` | Single parent `QObject`, original worker ownership and signal flow, old callable entry points, 07.9B HMI retained |
| `modules.project_workspace.application.service.ProjectWorkspaceService` | Query/Command/Inspection from 07.11 | Same DTO, services, deferred provider bootstrap |

This is real responsibility separation rather than new folders containing duplicate implementations. Older callers keep the same class names, method signatures, return values, and read/write semantics. No DB migration, device access, RAW file movement or UI/theme rewrite is part of apply/verify.

### Transaction safety

- `MetadataStore`: each original `Session(self.engine)` scope and `db.begin()` remains inside the corresponding repository method; repository instances share **one Engine** owned/disposed by the stable facade. `metadata.store._log` remains a patchable audit hook (existing GĐ0 synthetic rollback tests depend on it).
- `NumberedStorageRegistry`: code assignment and capture registration retain the pre-existing `BEGIN IMMEDIATE` / rollback paths; SQLite connection handles remain owned and closed by the façade. Migration remains a **static explicit action** with verified backup. `write_reserved_capture` never silently registers or deletes RAW.
- Qt: the coordinator classes are Python objects, **not** `QObject` parents. `ProjectLoadController`, `ProjectWriteController` and `CaptureInspectionController` are parented to the existing feature `QObject`. The main window still owns that feature QObject.

## Defects located and fixed

| ID | Evidence / risk | Remediation | Gate |
|---|---|---|---|
| 0711-V01 | `verify.ps1` uses `python -c` with nested quotes; Windows PowerShell removes quoting and raises `SyntaxError`, after otherwise passing 379 tests. | Remove inline Python; call `scripts/check_qt_acceptance_xml.py --junit ...` as an actual file. No receipt if Qt acceptance is absent, failed or skipped. | Parser's three synthetic JUnit tests + Windows full Qt XML |
| 0711-V02 | Old `publish.ps1` has no receipt because verify correctly stopped; cannot safely bypass. | New combined 07.12 receipt created only after ALL gates succeed; publish is guarded. | Receipt hash + manifest check |
| 0712-R01 | Extracted CSV catalog implementation used `self._path_chain` on a class without that method. | Delegate to registry resolver; do not alter catalog format or CSV injection protection. | Original numbered catalog tests |
| 0712-Q01 | Extracted Qt workflow instantiated worker `QObject(parent=self)` where coordinator is plain Python. | Parent to `self._owner` feature QObject, retain signals and cleanup. | Two new Windows Qt tests + original 07.10 Qt tests |
| 0712-Q02 | Moving the read workflow changed the relative-import depth for `project_rows`, which would break the first real SQLite load on Qt. | Correct import to `..presenter` and add a headless regression check for the relative module path. | Static 07.12 import-contract test plus original Qt v1 project-loading test |
| 0712-M01 | Extracted repositories originally bypassed patchable `metadata.store._log`, risking undetected audit rollback failures. | Explicit backwards-compatible audit hook delegation. | Existing `test_gd0_metadata_transaction_rollback_keeps_raw_retryable` |
| 0712-P01 | Original 07.11 verify used fixed SDK path specific to one Windows workstation. | Use repository parent `_sdk` discovery, never require hardware, retain optional user SDK environment. | Native self-test prints `native.hardware_access=false` |
| 0712-G01 | Git pager/CRLF warnings can obscure terminal and tempt operator to bypass. | Disable Git pager in patch scripts and use `git -c core.pager=cat ...`; CRLF warnings are not treated as functional errors, nor used to waive tests. | `git diff --cached --check` and scope-hash checks |

## Residual hazards: explicitly NOT claimed fixed

1. **SQLite vs filesystem atomicity** — no ACID transaction can include a RAW directory commit and an independent SQLite database commit. Durable reservation, immutable RAW files and manual recovery are retained. A crash between stages can leave a reservation/RAW requiring explicit recovery. Do not silently delete or deduplicate it.
2. **Concurrent hardware/filesystem races** — pathname checks cannot formally eliminate symlink/junction time-of-check/time-of-use races across every Windows filesystem. Real-world threat modeling and privileged filesystem tests are separate from static analysis.
3. **Windows symlink privilege** — two existing tests may legitimately skip without Developer Mode/admin rights; this does NOT count as symlink protection tested on the user's machine. Any other skip fails release.
4. **Existing schema integrity** — the metadata constructor checks user_version and required tables; this does not validate every SQLite column/index against its reference definition. Migration stays manual and backed up.
5. **Cross-module SOLID proof** — SRP/ISP/DIP improvements are observable, while OCP/LSP remain design/review/contract questions, not mathematically proved by an AST script. Dynamic import, reflection, runtime plugin wiring and CI on additional OS images need further verification.
6. **Remaining hotspots** — GUI shell and task orchestration, `SessionStore`, and legacy migration may still concentrate responsibilities. The reproducible AST inventory lists hotspots; refactor them only when a measurable coupling/maintenance benefit is shown.

## SOLID traceability (evidence vs claims)

| Principle | 07.12 evidence | Limit |
|---|---|---|
| SRP | Metadata/Numbered/Qt façade method bodies delegate to dedicated operations; façade sizes are bounded by `check_07_12_quality.py`. | Size is a proxy, not a formal proof of responsibility. |
| OCP | Feature workflow composition and existing ports allow targeted new readers/commands. | New device/provider extensibility requires concrete implementation tests. |
| LSP | Old façades preserve public signatures and behavior; old integration suites are retained. | No exhaustive behavioral substitution proof for all future providers. |
| ISP | Distinct repository and worker use-cases; 07.11's read/write/integrity ports remain. | Some persistence context APIs are still broad. |
| DIP | Application and domain import rule forbids direct infrastructure/Qt; feature bootstrap exception remains documented. | A few compatibility imports are accepted at the composition boundary. |

## Acceptance checklist

- HEAD at base commit, branch `feat/gd1-desktop-ui`, **exactly 13 pending 07.11 files** matching its SHA-256 manifest; no unrelated edits.
- Apply combined patch once: validate hashes, write reviewed files; never reset/checkout, migrate DB, touch RAW or access camera.
- Run Windows full regression (`pytest tests`), 07.12-focused tests, architecture gate and quality gate, CTest and native self-test. All four required Qt test cases must actually execute and pass. Only two documented Windows symlink skips tolerated.
- Manually verify 07.9B theme, SQLite v1 read-only and v2 CRUD, RAW inspection/audit and closing a session using disposable test data.
- Commit/push only after verify receipt and manual HMI acceptance; one combined `07.11 + 07.12` commit; do not merge `main` or start 08.
