# GĐ1 — 07.7: Opt-in Legacy RAW Migration (copy-first)

**Baseline:** `feat/gd1-desktop-ui`, commit `6d236e48ca97a45773ee06493a36f1f80a8bb482` (07.6 accepted). This is a **separate CLI, not an application startup or an Inspector action**. No camera, VTK, 3D pipeline or RAW regeneration.

## Scope & invariants

- Only **registered** RAW captures in SQLite **schema v2** whose mapping still has `layout_version=1`, with safe original path `sessions/<session_id>/captures/<capture_id>`. It supports both historical RAW payload formats: schema v1 (`depth.npy`, `rgb.npy`, `metadata.json`, `COMMITTED`) and schema v2 (`color.mjpg`, `depth.y16`, `metadata.json`, `manifest.json`, `COMMITTED`).
- Numbered aliases `P/S/T/C` **must already exist** in the 07.2 registry (`python -m scantopath.storage.numbered_cli --root ROOT assign-all` is a **separate, explicit write**).
- Dry-run only reads: validates metadata identity/shape, SHA-256 manifest where available, actual RAW file hashes, database consistency and destination collision. No directory creation, code assignment, backup or SQLite write.
- Apply is **copy-first**: copies bytes unchanged into a sibling `.partial` directory, verifies per-file SHA-256 against originals, renames the complete directory into `01_PROJECTS/P.../01_SPECIMENS/S.../01_SESSIONS/T.../01_CAPTURES/C...`. Original directories remain untouched.
- Before altering SQLite, `00_INDEX/07_07_migrations/<id>/metadata-before.sqlite3` is created with the SQLite backup API, and a `manifest.json` journal stores original paths and file digests. SQLite acquires the write lock **before taking its backup snapshot**, then updates `captures` AND `storage_captures` atomically in the same `BEGIN IMMEDIATE` write transaction. `layout_version` becomes 2 **for storage layout only**, while the actual RAW `captures.schema_version` remains 1 or 2 unchanged.
- The 07.2 triggers `storage_captures_move` and `storage_captures_immutable` block intentional path changes. 07.7 drops and recreates **exactly those two triggers inside the same SQL transaction**, checks foreign keys, then commits. Any error prior to commit rolls back the path updates AND trigger DDL. All other mapping IDs, numeric codes and constraints are unaffected.
- Rollback (explicit) checks original **AND** copied file hashes against its journal and ensures SQLite still references the expected capture, then atomically returns paths to the original legacy layout and layout_version to 1. Audit events for both transitions remain. The numbered copies are **retained** for forensic review; there is no automatic destructive cleanup. A rolled-back capture cannot be migrated again until its retained numbered copy is manually investigated and safely removed by the operator.
- Copy/rename is atomic within one filesystem but the operation **does not promise power-loss durability** on every filesystem. If power loss leaves `status=prepared` or an orphan copied directory, do **not** delete data manually without reviewing its manifest and checking SQLite; `rollback` can reconcile the known journal in ordinary recoverable cases.

## Mandatory operating conditions

1. Close ScanToPath GUI, camera acquisition, SQLite viewers and any process capable of writing the database or RAW.
2. Create an **independent external backup** of the whole data root before touching valued data; the tool's SQLite backup and retained legacy RAW are additional safeguards, not replacements for an external backup.
3. Work on a dedicated synthetic store or a copied dataset **first**. If the SQLite schema is v1, run the existing 07.2 schema migration separately and review its backup before attempting 07.7.
4. Explicitly assign missing codes through 07.2 if needed; 07.7 itself never invokes `assign-all`.
5. Review `dry-run` and disk-space availability before `apply --confirm`. The command fails closed on missing/extra files, linked paths, invalid identities, wrong versions, colliding numbered directories or insufficient free space.

## Operator commands (PowerShell)

```powershell
$root = 'E:\1_BigProject\scantopath\_setup\_test_data\GD1_07_7_TEST'
$py = '.\.venv\Scripts\python.exe'

# In the EXTRACTED patch folder, creates a BRAND NEW synthetic store once:
& $py 'E:\1_BigProject\scantopath\_setup\ScanToPath_GD1_07_7\scripts\create_demo_store.py' --root $root

& $py -m scantopath.storage.legacy_migration_cli --root $root dry-run
& $py -m scantopath.storage.legacy_migration_cli --root $root apply --confirm
& $py -m scantopath.storage.legacy_migration_cli --root $root dry-run

# Obtain migration_id from the apply JSON output; check Inspector on C0001.
& $py -m scantopath.storage.legacy_migration_cli --root $root rollback --migration-id 'PASTE_REAL_ID_HERE' --confirm
```

**Never run `apply` or `rollback` against the production data root during the 07.7 acceptance test.** Each invocation names its root explicitly; no default path. `rollback --confirm` does not restore a global SQLite snapshot (which might erase newer data), only the specific journaled capture references.

## Acceptance

- Unit: no-write dry-run, blocked v1 DB/unmapped records, v1/v2 bytes bit-for-bit, SHA for v2, malformed/missing RAW rejection, collision handling, interrupted copy recovery, rollback, schema triggers preserved, audit events.
- Integration: 07.2 resolver, 07.3 services, 07.6 RAW Inspector verification work after migration and rollback. All operations on temporary synthetic SQLite/RAW.
- Windows: `verify.ps1` runs dedicated tests plus full Python/Qt offscreen regression, CTest and native self-test. Test physical HMI on the synthetic store, close GUI before apply/rollback and reopen to confirm `C0001` and path changes. Check that legacy files persist, backup file exists and source hashes remain unchanged. Confirm rollback on a NEW standalone test store.
- 07.8 is reserved for full session-07 acceptance; do not merge into `main` at 07.7.
