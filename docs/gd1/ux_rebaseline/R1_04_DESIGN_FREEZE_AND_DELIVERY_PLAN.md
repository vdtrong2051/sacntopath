# R1.4 — UX wireframes, UI ownership contracts, change matrix and rollout gates

**State:** R1 implementation-ready proposal awaiting operator design approval + local Windows audit receipt. **Baseline:** `feat/gd1-desktop-ui@359e0156a6f11154a416c9ea6888c2840d343a0f`. Do not run 08.06.6 final freeze before rebaseline R2–R6 passes. History of 08.06.1–08.06.5 remains valid for its original scope; waiver TC-11/TC-12 is NOT_RUN, AR-03 remains OPEN.

## Final workspace mock layouts — content, not cosmetic placeholders

### Dự án (R3)

```text
┌ [Kho: GD1_07_5_TEST ▾]  [Đổi kho] [Tạo dự án]  [Tìm kiếm…] ──────────────┐
│ P0001 · Hộp giảm tốc V2                              [Mở thư mục] [Sửa]  │
│ Mô tả: ... | Schema v2 | Đường dẫn: logic/đã tạo | RAW: theo xác minh   │
├──────────────────────────────────────────────────────────────────────────┤
│ Vật mẫu (1)           Phiên quét (1)         Bản thu (n)      Lần xử lý  │
│ ┌─────────────┐     ┌────────────────┐     ┌────────────┐    ┌────────┐ │
│ │ S0001       │     │ T0001 · OPEN   │     │ C0001 ...  │    │ R...   │ │
│ │ Trục vít A  │     │ [Xem][Đóng]    │     │ status RAW │    │ state  │ │
│ └─────────────┘     └────────────────┘     └────────────┘    └────────┘ │
│ [Thêm vật mẫu]       [Tạo phiên quét]       Không có? → empty state     │
└──────────────────────────────────────────────────────────────────────────┘
```

- The **center** provides context and actions, Explorer still displays the full hierarchy, and Inspector handles selected detailed metadata. Center list and Explorer have distinct information density, not two duplicate trees.
- `Đổi kho` shows remembered local store path shortcuts plus `Mở kho khác…`, not a new SQLite per Project. Invalid paths are visible and removable in preferences; never auto-create on read.
- `Mở thư mục` only enabled when registry resolves an existing safe directory; for `not_materialized`, reveal store root or show precise pending path without creating directories.

### Thu nhận RGB-D (R2 shows honest reserved state; 09 implements)

```text
┌ Thu nhận RGB-D · Phiên 09 — chưa có trình phát lại ──────────────────────┐
│ Nguồn dữ liệu: [chọn Capture thuộc session đã mở / disabled until 09]  │
│ [Color frame placeholder]       [Depth frame placeholder]              │
│ Chưa mở camera / Không ghi dữ liệu mới                                 │
└──────────────────────────────────────────────────────────────────────────┘
```

No dummy footage, no fictitious measurements. The source capture list may link to Project, but RAW decode/scrub only from 09.

### Kiểm tra 3D (R5)

```text
┌ [Tên tệp/model ▾] [Mở PLY/OBJ] [Fit]  [Chế độ: Points/Surface] [⋯] ─────┐
│┌──┐                                                                    │
││⌖ │ Select point/face, native picker                                    │
││↻ │ Orbit (also left drag)                                             │
││✋│ Pan   (also right/middle drag per mapped policy)                    │
││＋│ Zoom                                                               │
││⌂ │ Fit to view                                                        │
││xyz│ Axes                                                              │
││◉ │ Layers                                                             │
│└──┘                                                                    │
│                    LIVE SCENE (points / mesh)                          │
│                                                                         │
│ [Ready/Loading/Error]  1,000,000 pts · RGB? · frame unknown             │
└─────────────────────────────────────────────────────────────────────────┘
```

The tools overlay uses square icons and tooltips; **no line of permanent technical narration under viewport**. Scene tree left, model/point/face/bounds/source/right Inspector, progress/log bottom only on request/errors. One scene may include multiple actors only when implemented. No fake layer UI.

### Xử lý (R3 read-only view; 13+ create process results)

```text
┌ [Lần xử lý] [Tất cả / Đang chạy / Lỗi] [Lọc session] ───────────────────┐
│ R0001 | Stage: xyz | Succeeded | Input C0001 | Outputs (2) | [Chi tiết] │
│ R0002 | Stage: abc | Failed    | Error summary                 [Chi tiết] │
│ Nếu chưa có: 'Chưa có lần xử lý trong kho được chọn.'                   │
└──────────────────────────────────────────────────────────────────────────┘
```

This displays *persisted ProcessingRun* as already supported by metadata. It must not silently run an algorithm. `Nhật ký SQLite` stays available in the lower Events panel as an audit source, never confused with the main ProcessingRun list.

## UI component responsibility contracts

| Component | Owns | Does NOT own |
|---|---|---|
| `MainWindow/Shell` | nav, dock visibility/persistence, common status, dependency composition | SQLite query, PLY parse, VTK native state, business state |
| `WorkspaceHost` | common rounded frame, breadcrumb, per-workspace lifecycle, responsive density | native workflow decisions |
| `ProjectFeature` | project read/write actions through use-cases, displayed summary DTO | its own SQLite session inside QWidget |
| `Explorer` | hierarchical navigation and current selection | folder renaming outside registry, DB creation |
| `InspectorHost` | selection routing, property presenter based on DTO type | invent units, read RAW directly, remove validation |
| `TaskCenter` | real job status/events + Problems/log drawer | run fictitious demo in user mode, replace Processing center |
| `ViewerFeature` | scene lifecycle, camera commands, pick/actor visibility, state | direct SQLite/RAW writes, native VTK in Qt shell |
| `RenderHost` | native VTK scene, geometry load, render, pick, GPU resource ownership | Project identity, SQLite or user workflow |

**Selection contract:** `SelectionRef` from Project and `SceneSelectionRef` from Viewer are different typed domains. An Inspector host acts as a presentation router but the application data provider remains feature-local. Do not treat raw IDs or provenance from external PLY as Project-owned artifacts. Workspace switch keeps active store and project context; point selection may clear when scene changes.

**ObjectName/Test contract:** Existing Qt objectName values including `workspaceToolbar`, `workspaceStack`, `explorerDock`, `inspectorDock`, `taskDock`, `projectExplorer`, `propertyInspector`, `taskEventTabs`, `workspacePrimaryAction`, `viewer3dPreview`, `viewer3dOpenPlyButton`, nav IDs, etc. are baseline test hooks. Any rename/removal requires an explicit compatibility mapping and affected-test rewrite in the same small patch, never silent renames to bypass tests.

## Concrete R2/R3/R4/R5/R6 execution matrix

| Patch | Exact intention | Source categories | Verification gate |
|---|---|---|---|
| R2.1 | Shell navigation density, overflow, no clip | shell + theme | Qt responsive/min-width and keyboard nav tests |
| R2.2 | Dock/bottom task compact and reset layout; Dev-only demo UI | shell + task panel + theme | events/task regression; 100/125/150% Windows HMI |
| R2.3 | Shared central workspace frame and density contract | workspaces/pages + shell | screenshot HMI; no overlapping rounded borders |
| R3.1 | Recent stores and active store banner via app preferences | Project feature + preferences adapter + UI | explicit open only; no auto create/DB write; missing root recovery |
| R3.2 | Real project dashboard, selected entity overview, direct create P/S/T | Project feature UI/application, Inspector | SQLite v1 read-only, v2 real CRUD, code mapping, legacy RAW unaffected |
| R3.3 | Contextual Inspector and read-only ProcessingRun center | Inspector + processing view DTO | source IDs, output existence vs verified distinction |
| R4.1 | Standalone persistent render host (no Qt embedding) | prototype/bench tools ONLY | continuous camera and native memory/IPC; no app changes |
| R4.2 | Standalone embedded Qt VTK comparator and crash reproduction | prototype ONLY | actual Windows driver failure/cleanup; remains opt-in |
| R4.3 | ADR decision based on A/B numbers and safe fallback | documentation | recorded p50/p95/fps/crash/cleanup, accept architecture |
| R5.1 | SceneSource contracts / PLY faces + OBJ readers | Viewer app/infra + tests | point/mesh fixture and counts/bounds/pick correctness |
| R5.2 | New resident viewport + input and resource lifecycle | Viewer presentation/infra | HMI continuous drag, safe close while busy, no stale frame |
| R5.3 | Overlay tools, layers, selection Inspector bridge | Viewer presentation + shared Inspector | no lost functionality, no text consuming viewport height |
| R6.1 | Caller-driven compatibility cleanup only if proven safe | exact approved candidates | AST/dynamic references plus full regression |
| R6.2 | Full Windows UX/3D/performance acceptance | all changed features, no GĐ0 edits | pytest/Qt/CTest, bounded memory, actual OBJ/mesh, high-DPI |
| R6.3 | Amend acceptance scope/risks and R1 design traceability | docs | no false full HMI pass; 08.06.6 only afterward |

## Hard release gates

1. `git` HEAD pinned before apply; branch `feat/gd1-desktop-ui`; no reset, checkout or force-push by scripts. Each patch manifest, allowed file list, source diff, hash guard. R1 itself adds **four docs** only; external inventory tool remains in `_setup`.
2. Full regression floor = last user observed 08.06.2 **471 collected, 469 PASS + 2 allowed Windows symlink SKIP**; collected count may change after new tests, but zero failures and no new unapproved skips. Architecture/07.12 quality and CTest 2/2 remain mandatory on runtime changes.
3. No RAW/SQLite mutation in R1/R2/R4; R3 database writes occur only on explicit create/edit with same schema/transaction contract; no schema migrations by UX action.
4. Renderer replacement requires actual polygon mesh/OBJ tests and close-while-busy HMI, not a waiver disguised as proof. AR-02 performance is reopened, AR-03 remains OPEN until verified.
5. Keep selected view states and user dock layout through reopening only if persistence is implemented and tested. Do not assume native `QDockWidget` border radius alone draws correctly on Windows; validate visual result.
6. R1 is accepted with audit inventory + four design files + operator design review. R2 begins only after acceptance. No self-approval or claim final 08.06.6.

## Proposal approval checklist

- [ ] Agreement: compact top workspace strip + 3 docks (Explorer, Inspector, Task drawer), rounded central frame.
- [ ] Agreement: Project center dashboard + recent-store shortcuts and explicit store creation/open policy.
- [ ] Agreement: view point/mesh as native 3D with persistent isolated render host target; A/B PoC mandatory before production selection.
- [ ] Agreement: Context Inspector; viewer status compact; no permanent oversized local text rows.
- [ ] Agreement: Processing center is meaningful read-only run list now, algorithm execution later.
- [ ] Agreement: no deleting compatibility or later-stage code without R6 dependency check.

**No UI/renderer implementation is shipped by R1.** This document is the implementation agreement for R2–R5 after user review.
