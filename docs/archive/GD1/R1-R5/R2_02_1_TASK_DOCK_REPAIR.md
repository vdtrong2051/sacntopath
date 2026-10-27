# R2.2.1 — Task Dock Chrome and SRP repair

Baseline: `feat/gd1-desktop-ui` at `bd1d5f80b48e73191dc89adb8d6dae8723ec4b04`, after uncommitted R2.2 patch. Repair does not revert or overwrite other stage features.

## Root cause

Full regression reported `1 failed, 482 passed, 2 skipped`, at `tests/test_gd1_07_10_modular_architecture.py:78`. This test checks `len(main_window.py.splitlines()) < 500`. R2.2 placed task chrome orchestration in the already-large MainWindow, exceeding the existing architectural budget. This is an SRP violation, not a broken database, worker or renderer.

## UI decision (full-screen-first)

- Replace the duplicate bottom summary row with a **single task dock titlebar**: `Tác vụ và thông báo | 0/1… running/failed | [−/▢] [float] [×]`. The existing `taskPanelExpandToggle` button is moved into titlebar **without replacing its `.click()` or signal**, so old Qt test hooks work.
- Collapsed Task Dock retains only titlebar and a thin body. Expanded, the three original tabs show task list and progress, UI event history and SQLite audit. The titlebar status is bound to actual `TaskSnapshot` values, not persisted `ProcessingRun` data.
- In operator mode with no running tasks, **demo controls and the disabled cancel button are hidden**, and the Tasks tab shows a concise empty message. When there are snapshots, task rows appear, and Cancel remains available for an eligible selected task. Developer tools remain opt-in in Help.
- All original three **Hiển thị** menu actions remain, as do close/reopen, float, task cancellation and close lifecycle. No SQLite/RAW/VTK changes.
- Screen smaller than full-screen is not a layout-priority of R2.2.1; detailed central responsive redesign belongs to R2.3.

## Code ownership

`ui/shell/task_dock_chrome.py` owns task titlebar, display-mode sizing and developer tool toggle. `MainWindow` composes it and delegates. The R2.2.1 script checks **under 500 MainWindow lines** rather than relaxing the old test. The feature TaskAndEventPanel keeps `tabs`, `tasks`, `demo_button`, `cancel_button`, `compact_summary` and `expand_button` APIs.

## Acceptance

Automated: old R2.2 focused tests, 07.10 architecture test, all GĐ0/GĐ1 Python+Qt regression (0 FAIL, maximum original 2 Windows symlink skips), CTest, native self test. Manual Windows: full-screen initial collapsed one-line task bar; expand and see empty state; run a dev fixture and see task row, status/progress and cancel; audit action forces expand and tab 3; close/reopen via Hiển thị; float and dock again; verify no overlapping labels. Do not publish until all automated + manual tests pass.

The previous R2.2 patch **must remain uncommitted** when applying this repair; its documents and tests are retained and published together only after acceptance.
