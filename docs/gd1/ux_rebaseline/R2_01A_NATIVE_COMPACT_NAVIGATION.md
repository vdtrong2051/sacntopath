# R2.1A — Compact native Qt navigation (reimplementation after failed R2.1)

Baseline: `feat/gd1-desktop-ui@c063a45c1d48fb04b416d1ff411489c137889802` (R1 accepted). Scope: top toolbar only. No import of camera/VTK/SQLite; no RAW read/write, project state change, data migration or Dock/Workspace redesign.

## Design decision

- Keep the **native** `QToolBar` and **four ordinary** `QPushButton` objects, including `nav_<workspace>`, `nav_buttons`, checkable/auto-exclusive behavior and existing click callbacks.
- No custom `ResponsiveWorkspaceToolbar`, manual `QWidgetAction.setVisible`, or overridden `QPushButton.click`/`clicked.emit`. Retain existing menu and `Ctrl+1..4` actions for accessibility.
- Remove the 126-pixel forced minimum brand width, keep the brand legible and reduce toolbar/pushbutton padding and divider width.
- Keep `toolbar_context` compatibility attribute but leave its `GĐ1 · Desktop` label **hidden and outside QToolBar layout**. This frees space before any command is crowded.
- After applying QSS, give each navigation button a minimum width at least `max(sizeHint.width, fontMetrics.horizontalAdvance(text) + 22)`. Qt owns native layout and any extreme-width overflow. A *visible* button may never be horizontally elided.
- User-designed future full command palette/overflow belongs a separate measured patch; do not build a bespoke responsive engine for four tabs.

## Acceptance / rollback

1. Focused Qt offscreen tests: 06.3, 07.9, 07.9B and R2.1A. New Qt tests must execute (no skip). Full test suite, architecture & quality guards, CTest and native self-test required before publish.
2. Real Windows HMI: normal + narrow window, `Thu nhận RGB-D` fully readable; 100/125/150% DPI when available; 4 tabs and `Ctrl+1..4`; no overlapping labels; project and Viewer unchanged. Qt offscreen tests are not evidence of DPI/HMI quality.
3. Retain operator manual acceptance: only `publish.ps1 -ManualVisualAccepted` after review, no automatic merge `main`.
4. If the compact 720 logical px case still cannot fit 4 tabs on particular font/Windows theme, record exact font/DPI/width/screenshot and implement a separate native overflow feasibility test. Do **not** hide buttons with QWidgetAction or manufacture click events.

Rollback from worktree before commit (only after copying your own new changes): `git restore --worktree -- src/scantopath/ui/shell/main_window.py src/scantopath/ui/theme/hmi_panel.qss`, then remove the two R2.1A new files. No `reset --hard`.

## Not in R2.1A

R2.2: Dock and Task Panel density; R2.3: rounded central workspace; R3: Project UX; R4/R5: resident 3D rendering and mesh.
