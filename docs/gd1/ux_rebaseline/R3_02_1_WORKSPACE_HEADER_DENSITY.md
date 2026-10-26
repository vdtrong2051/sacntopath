# R3.2.1 — Workspace Header Density Polish

Scope: compact the **generic workspace header** used by all 06.3 pages while preserving the 4-workspace shell and the R3.1/R3.2 panel integration.

## Acceptance contract

- Hide the redundant `KHÔNG GIAN LÀM VIỆC` eyebrow from actual UI (keep Qt object for compatibility).
- Workspace content padding: `(left 24, top 10, right 24, bottom 16)`; vertical spacing 6, subtitle-to-card fixed spacer 4.
- Keep `workspaceHeading`, `workspaceSubtitle`, the original hidden placeholder frame and *all layout slots* unchanged; no new panels, duplicate actions, or QSS overrides.
- On Projects page R3.1 store stays at layout index 3, R3.2 dashboard at index 4; panel visual separators and borders unchanged.
- Other workspaces retain existing functionality/placeholder contracts; no automatic DB access or hardware operations.
- No modifications to SQLite, RAW, VTK, C++, native, main window, dashboard or task dock.

## Verification

Use `verify.ps1 -ProjectRoot <repo>` for scoped Qt, Architecture and Quality gates. For all Python regression, append `-FullRegression`. On Windows, inspect at 100–150% DPI and full screen. A passing automated gate does **not** replace HMI acceptance. No automatic commit/push/merge.
