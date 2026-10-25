# R2.2 — Compact Dock & Task Center (operator-first desktop)

**Baseline** `feat/gd1-desktop-ui @ bd1d5f80b48e73191dc89adb8d6dae8723ec4b04` (R2.1A). **Scope:** `main_window.py`, `task_event_panel.py`, `hmi_panel.qss`, one Qt regression file, this document. R1 blueprint governs UX. **No R2.3 workspace restructuring; no Project/RAW/SQLite/VTK changes.**

## Design and interaction contracts

- **Default full-screen workflow:** Explorer and Inspector remain native docks, Task dock remains open but **collapsed to a short summary strip** plus native QDock title. Central workspace gets the remaining height. The app does not force `showMaximized()` or change window policies.
- Compact summary reports **in-memory UI TaskSnapshot**, never a persisted `ProcessingRun`. The expand button toggles the *existing* `taskEventTabs` (Tasks / UI Events / SQLite Audit), preserving tab selection, running jobs, events, and audit rows. Click the Qt-native dock close control to fully hide; use **Hiển thị → Tác vụ và thông báo** to restore. Resizing only alters the bottom dock's requested vertical size, not Explorer/Inspector widths.
- **Open audit** action in Processing explicitly opens the task dock, expands it, and selects SQLite audit tab. This maintains 07.9 behavior; moving ProcessingRun into a real workspace remains R3.
- **Developer fixture:** Existing 06.5 `startFixtureTask` and `cancelSelectedTask` instances, signals, workers and tests are retained; fixture launch and obsolete explanation are visually hidden from operator mode. Developer explicitly opts in via **Trợ giúp → Công cụ kiểm thử UI (chế độ phát triển)**. This command reveals the fixture button and expands the dock; disable it to hide. It cannot initialize camera or SQLite.
- All existing Qt objectNames, three actions under **Hiển thị**, VTK lazy start and close-during-task worker contracts remain intact. No dock position persistence is claimed in this patch. Reset layout / layout presets can be discussed after R2.3.
- Theme changes target `#taskEventTabs` and new compact widgets only; existing global tabs remain unchanged.

## Windows HMI acceptance

| TC | Procedure | Required result |
|---|---|---|
| R2.2-01 | Open app at normal/maximized 100% scale | Bottom Task Center shows compact summary; no fixture launch button in operator mode |
| R2.2-02 | Click **Mở rộng** and **Thu gọn** | Original three tabs restored/hidden; selected tab and its data remain intact |
| R2.2-03 | Processing → **Xem nhật ký SQLite** | Dock opens even if closed, expanded, SQLite audit tab selected |
| R2.2-04 | Trợ giúp → **Công cụ kiểm thử UI** | Fixture button appears only after explicit opt-in, can be hidden again |
| R2.2-05 | Start/cancel the 06.5 fixture (developer mode only) | Task runs/cancels, UI stays interactive, safe close preserved |
| R2.2-06 | Dock close and Hiển thị → Tác vụ và thông báo | Dock can be reopened; no lost task/event/audit state |
| R2.2-07 | Switch four workspaces, open/close dock several times | No disabled navigation, no orphan worker or hidden crash |
| R2.2-08 | Resize / 125% / 150% DPI as available | No overlap/illegible compact row; full-screen use prioritized |

## Release gate

1. HEAD and Git-tree SHA guards, exact allowlist, CRC/SHA-256 payload verification.
2. Focused Qt test including historical GĐ1-06.4/06.5/07.9 and R2.2 cases; **zero skip**.
3. Full Python+Qt test: at least 471 collected, at most the two pre-existing Windows symlink skips, no new skip/failure; architecture/07.12 gates, CTest 2/2, native no-hardware self-test.
4. Manual Windows HMI. Publish only with audited acceptance receipts; do not merge `main`.

**Known future steps:** R2.3 central workspace frame, R3 Project and contextual Inspector, R4/5 renderer. Do not interpret more central height as solving the old R4 renderer gesture latency.
