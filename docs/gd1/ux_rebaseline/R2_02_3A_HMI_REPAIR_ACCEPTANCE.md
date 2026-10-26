# R2.2.3A HMI Repair — Task Dock visual hierarchy and reliable Windows gates

**Base:** `feat/gd1-desktop-ui@9385c82`, after R2.2.3A applied but uncommitted. **Reason:** R2.2.3A removed a useful boundary between title, tabs, and content, hid a requested independent title action, centered empty text within unused space, and shipped a PowerShell gate using a reserved `$args` variable with fragile `2>&1` handling.

## Accepted scope

- Three **distinct** right title controls (left to right): **minus** `−` = collapse/reopen task content; **square** `□` = maximize task dock height inside the main window / restore; **cross** `×` = hide dock (reopen through View menu). The square no longer floats or undocks. Each has independent hit area 28×26 logical pixels, vector icon, tooltip and accessible name. Collapsing does not delete task rows, notifications, audit items or running workers.
- Title widget 34 px with 1px bottom separator; tab strip has its own selected indicator, subtle vertical dividers and pane-top separator; actual data surface is white with fine border. Avoid nested rounded cards; retain approved cobalt color.
- Default expanded task height ~248 px (large desktop), 205 px (short screens), or a temporary ~62% main-window-height mode when the square is activated. Collapsed dock is header-only 34 px; Qt may clamp geometry to window/splitter constraints.
- Empty task/notification labels are top-anchored via growing blank spacers; list/table occupies available space when populated. Do not reintroduce permanent prose for audit or UI events. Audit table retains first UTC column 240px and stretchable event column.
- No changes to Project, SQLite, RAW, camera, C++ or Viewer/VTK; no new mock data or removal of actual task engine.

## Explicit revised Qt contracts

The earlier R2.2.1/2.2.2/2.2.3A test expectations of a **visible floating icon** or **only two icons** have been superseded by the operator's explicit three-action request. Those three tests are updated **only on UI contract assertions**. All Project, task cancellation, snapshot, Qt threading, architecture, full Python, native and CTest gates remain enabled. New HMI tests check independent behavior, spacing, title-pane borders, proper empty state and data-list usage.

## Verification gate

`verify.ps1` launches **one Python gate runner without pipeline redirection or reserved PowerShell `$args`**. The Python runner executes each gate in a child process with captured stdout/stderr, durable logs, and *return-code* checks; `ctest -C Release` is required. `verify.ps1` is not allowed to report PASS before full pytest, architecture, quality, compile, CTest/native and final source verification all succeed. The two historical Windows symlink-privilege skips are recorded and not represented as passes.

1. `apply.ps1`: exact Git HEAD and allowed-file guard; R2.2.3A content verification before mutation; deterministic idempotence; no commit/push.
2. `verify.ps1`: all automated gates; **cannot claim visual PASS**.
3. Manual Windows HMI: three separate controls and behaviors, compact tab title separation, table fills audit, full screen and smaller size, no overlap or clipping, task while running/cancel check.
4. Commit/push only after these conditions are accepted; no merge main.
