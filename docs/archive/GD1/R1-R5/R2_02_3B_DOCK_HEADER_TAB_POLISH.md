# R2.2.3B — Compact Task Dock: header, tabs and height

**Baseline:** `feat/gd1-desktop-ui` at `9385c82` **with uncommitted R2.2.3A Final already applied**. UX change requested 26 Oct 2026. This is a scoped presentation patch, not a new execution engine or renderer.

## Decisions

- Native Dock title bar: **38 logical px** (was 34), with a visible 1px bottom separator; preserve independent **minus / maximize-restore square / close** controls.
- Task tabs: compact **18px minimum content height**, `2px 10px` insets, 6px selected radius, light-blue active fill + outline to match main workspace navigation. The selected tab remains legible at Windows DPI 100%, 125%, 150%.
- Normal expanded Task Dock: **160–204 logical px** based on main-window height, typically ~184px at 768px height. This replaces 248px from R2.2.3A Final and keeps workspace canvas visible.
- Explicit maximize action: caps to about **46% of the main-window height** (with space reserved for workspace); the square remains independent and reversible.
- Collapsed dock: 38px title strip. Tasks, notifications, SQLite audit and their Qt object names remain intact.

## Strict scope

Runtime: only `ui/shell/task_dock_chrome.py` and `ui/theme/hmi_panel.qss`. Existing Qt tests asserting the old 34px contract change accordingly, and one focused visual-geometry test is added. `main_window.py`, Project/SQLite/RAW, C++ and VTK are untouched. No new runtime widget or dependency is introduced.

## Acceptance

1. On a normal maximized Windows desktop, clicking minus opens a short bottom panel **without hiding the center workspace**. Clicking minus again restores the title-only strip.
2. The title, tab selector and data view are separated. The header is slightly taller, tabs are slimmer and resemble the existing workspace navigation in shape and active fill.
3. Three title actions have distinct behavior. The square may expand more than the normal drawer but should not cover almost the entire workspace; square again restores.
4. Audit table still fills the available content region with readable UTC column. UI events/tasks remain retained through dock collapse.
5. Qt focused and full pytest regressions must pass with **no new unexpected skips**, as must architecture and quality gates. Native acquisition and CTest are unaffected by this presentation-only change and are not gate-blockers for this scoped polish.
6. No auto-publish. Record full Windows GUI verification before commit.

## Not in this patch

R2.3 center workspace frame, panel persistence, task duration/progress formatting, actual RGB-D replay or renderer replacement.
