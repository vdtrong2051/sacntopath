# ScanToPath — R2.2.3C Dock Header Visual Hierarchy

Baseline: `feat/gd1-desktop-ui` HEAD `9385c82`, after R2.2.3A/B and the measured dock-geometry correction.

## Operator requirement

The expanded task drawer has **three visually separated surfaces**: (1) 44 px titlebar, (2) 28–32 px tab strip, (3) white content region. Three independent buttons remain: **minimize/expand**, **maximize/restore**, **close**. A visible single-pixel titlebar separator is painted directly because QSS alone was not reliable on Windows. The tab/content boundary retains its own line.

## Geometry budget

- Collapsed dock: bounded at 52 px (`QDockWidget.maximumHeight`).
- Normally expanded dock: unchanged limit of 190 px.
- Square-button mode: unchanged limit of 310 px.
- Layout is not changed in `MainWindow`; no card, spacer, camera, SQLite, RAW, native or VTK changes.

## Verification and acceptance

The three previous header-height assertions change from 38 to 44 px, and the existing *measured* collapsed-dock thresholds change from 48 to 54 px to account for the new title height. None of the functional tests or their counts are reduced. New Qt tests verify independent controls, measured title/tab/dock sizes, and workspace preservation. Visual acceptance remains manual on Windows, and must explicitly confirm both separators and that the Task Dock does not push the workspace away. Do not publish merely because automated tests pass.

Use `ScanToPath_R2_2_3C_Dock_Header_Hierarchy.py verify --project-root <repo> --full` for the automated gate. No native camera/SDK test is necessary for this scoped visual change.
