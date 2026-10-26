# R3.1 — Recent Store Management & Project Workspace Header

Baseline: `feat/gd1-desktop-ui@2c84c83cee1f69cd415fdf99f71ab9502be2b57e`.

## Implementation contract

- The Project workspace now displays a real **Kho dữ liệu** region, with distinct title bar/separators, active store root/schema, recent shortcuts, **Mở kho khác…**, and explicit **Mở kho đã chọn** / **Bỏ khỏi danh sách**.
- Persist **only** the eight most recently **successfully loaded** roots in local `QSettings("ScanToPath", "ScanToPath")`, key `project_workspace/recent_store_roots`. This is application UI metadata **outside** project SQLite/RAW. Saving a shortcut is not permission to open it during launch. Qt `offscreen`/`minimal` test platforms use a separate per-process temporary settings file so synthetic test stores never pollute the operator's Windows preferences.
- Selecting a shortcut calls the existing `ProjectWorkspaceController._begin_project_load()` → `ProjectLoadController` → application validation. An invalid or moved folder must not create `metadata.sqlite3` or be forgotten automatically. `Path.is_dir()` is only a visual hint; it is **not** store validation.
- The legacy `workspacePrimaryAction` remains constructed, connected and identifiable for historical Qt contracts, but its redundant welcome card is hidden in the Project center. Explorer open/refresh/create actions and the project Inspector are still the existing implementations.
- Recent roots are **not** the source of truth for project IDs, public P/S/T/C/R numbering or filesystem materialization. SQLite schema and data remain owned by the existing project read/write services.
- No new-store initialization is implemented in R3.1: R1 requires a **separate explicit create-store wizard** with schema v2 bootstrap/rollback proof; blindly constructing `MetadataStore` on a chosen directory would violate this agreement. No migration or RAW writes.

## Layout and UX

The Project center retains its heading and description, followed by a **single bordered store management region**, separated internally by two physical 1 px rules:

```text
┌ KHO DỮ LIỆU                                       [Mở kho khác…] ┐
├─────────────────────────────────────────────────────────────────┤
│ Kho đang mở: <tên thư mục>                                        │
│ E:\...\root                                     SQLite v1/v2    │
├─────────────────────────────────────────────────────────────────┤
│ KHO ĐÃ MỞ GẦN ĐÂY                                              │
│ • <store1>                                                      │
│ • <store2> · Không còn tại đường dẫn cũ                        │
│ [Mở kho đã chọn]   [Bỏ khỏi danh sách]                          │
└─────────────────────────────────────────────────────────────────┘
```

No large instruction card or repeated global actions. Explorer keeps hierarchical selection, which is a different responsibility from the central store selector.

## Acceptance and caveats

1. Launch does not read/write any Project SQLite, create a store, open a camera or select a bookmark automatically.
2. A valid v1/v2 root can be loaded with the existing worker; it appears in recent list **after** success; another window can explicitly reopen it.
3. A missing/corrupt/schema-unsupported root is not bookmarked; a previously valid but moved root remains visible and removable.
4. No changes to `main_window.py` (the historical <500 line budget), GĐ0/RAW, C++, viewer, task dock or schema.
5. New Qt tests include stored preferences, explicit worker flow, invalid roots and visible separator widgets. Run focused/full pytest, 07.11, 07.12, CTest Release and native self-test with SDK path configured (when making runtime acceptance).
6. Windows HMI still needs manual check at full screen/125% DPI; automated Qt offscreen cannot guarantee readable appearance. No publish before verified tests and user acceptance.

R3.2 owns a real project dashboard (P/S/T direct creation in the central area). R3.1 intentionally does **not** build it or present fabricated Project counts.
