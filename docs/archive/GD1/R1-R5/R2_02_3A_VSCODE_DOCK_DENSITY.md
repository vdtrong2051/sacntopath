# R2.2.3A — VS Code-inspired task dock density polish

**Baseline:** `feat/gd1-desktop-ui` commit `9385c82e0c71ad681cffeea145c5f89b5065dd7f` (R2.2.2 already committed).

## Scope and UX decisions

- Task Dock chrome: native Qt title widget remains, 34 logical-pixel tall; use **three independent actions**: minus (collapse/expand), square (maximize within application/restore) and close (hide/reopen via View). Remove unused float/attach behavior; no extra Qt dock handle.
- Short, quiet title summary of running tasks remains. No second big status row below the title.
- Tabs: scoped compact typography/padding. No global restyling of Project/Inspector/Viewer.
- Tasks: empty state `Chưa có tác vụ.`; actual task rows, progress and cancellation are unchanged.
- UI notifications: hide the explanatory `event_hint` QLabel but retain its test/API hook. Empty state `Chưa có thông báo.`; on events, show the existing `uiEventList` and hide the empty label. Its provenance remains the same.
- SQLite timeline: hide the redundant `audit_hint` *visually*, retain its information and object for API use. Remove audit page margins and inner box stroke so table occupies the entire content area. UTC column 240px; Level 92px; event column stretches; Object 220px. Users may resize interactive columns.
- Expanded bottom dock target ~248 logical px for normal-height displays (205 at shorter heights), collapsed title 34px; square temporarily maximizes the dock inside the main window. The rest of the application, splitter behavior and global dock toggles are unchanged.
- Style: monochrome/flat, no extra nested rounded frames; targeted QSS selectors under `#taskAndEventPanel` and `#taskDockTitleBar` only. No external font/icon dependencies.

## Intentional contract updates

The old tests `test_gd1_r2_2_1_task_dock.py` and `test_gd1_r2_2_2_chrome_polish.py` asserted that the **float icon is visible**. That directly contradicts the approved R2.2.3A change. Only the relevant assertions are changed to require the independently functional maximize control; all other test behavior remains. Do not weaken any Project, RAW, native or CTest gate.

## Gate

1. Python AST parse, Git status/baseline guard and SHA-256 manifest integrity.
2. R2.2.3A Qt scenarios (title buttons, event empty/content, audit page geometry, task empty state); legacy task dock and architecture tests.
3. Full Python/Qt regression (`pytest -q`), architecture and quality gates, CTest 2/2 Release and native self-test.
4. Windows HMI: fullscreen, expand/collapse; titles and tabs visually inspect; Task tab still shows running snapshot; audit fits height and UTC title is visible; closing/reopening works.
5. Commit/push **only** after operator confirms visuals; no merge main.

**Out of scope:** R2.2.3B (task progress table richer controls), Workspace center redesign R2.3, Project/SQLite schema, RAW, VTK, camera.
