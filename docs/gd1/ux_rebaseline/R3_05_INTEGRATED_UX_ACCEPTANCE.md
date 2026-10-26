# R3.5 — Integrated UX Acceptance (Project/Inspector/Processing)

**Execution baseline:** `feat/gd1-desktop-ui@5bf8df0d389be7bfe2d348c335f5171106a2042c` (R3.4, 2026-10-26). **Scope:** R3.1 Recent Stores + R3.2 Project Dashboard + R3.2.1 Workspace Header Density + R3.3 Contextual Inspector + R3.4 read-only ProcessingRun. The detailed R3.5 gate complements, and does not replace, `docs/ROADMAP.md` sessions 06–08, R1.4 design matrix, R6.2 full UX/3D gate or the eventual 08.06.6 final acceptance.

## Scope freeze

- R3.2.1 is operator-accepted: **no further interface/style/source edits** in this patch. R3.3/R3.4 are present on GitHub at commits `4bef07c`/`5bf8df0`; this gate does not recommit their code.
- R3.5 adds **acceptance tests, a reproducible Windows gate command and this evidence matrix only**. No SQLite schema update, implicit store creation, RAW mutation, sensor access, VTK renderer change, mock ProcessingRun, background algorithm or changed UI labels.
- An automated offscreen Qt PASS proves contracts, not typography/high-DPI on physical Windows monitors. No agent may mark visual acceptance PASS without operator evidence.

## Automated acceptance matrix

| ID | End-to-end behavior | Evidence/test | Requirement |
| --- | --- | --- | --- |
| R35-A01 | Startup without store: chooser visible, dashboard/Inspector/Processing truthfully empty; no DB created | `test_r35_launch_is_explicit_empty_without_phantom_data` | PASS required |
| R35-A02 | Real v2 SQLite + synthetic RAW → dashboard Project/Capture → one authoritative Explorer selection → context Inspector | `test_r35_real_capture_to_processing_selection_and_read_only_provenance` | PASS required |
| R35-A03 | Switch to Processing → real run row → Inspector/run selection; missing output stays an *unverified reference* | same test | PASS required |
| R35-A04 | Presentation/read actions do not alter SQLite or audit records; RAW is not verified until explicitly requested | same test + 07.8 tests | PASS required |
| R35-A05 | Invalid replacement root removes old Project, Inspector and Processing data; no implicit directory/DB created | `test_r35_changing_to_missing_store_clears_all_presentations` | PASS required |
| R35-A06 | v1 Project remains read-only; Processing has honest empty state; no v1→v2 migration | `test_r35_v1_remains_read_only_across_project_and_processing` | PASS required |
| R35-A07 | Recent-store shortcut explicitly reopens same store and rebuilds DTO-derived views | `test_r35_recent_store_reopen_retains_project_and_processing_truth` | PASS required |
| R35-A08 | Preserve R3.1–R3.4 focused tests, 07.8 integration, 07.12 architecture/Qt | `scripts/verify_gd1_r3_5.ps1` | PASS required |
| R35-A09 | Full Python regression, no unexpected failure/skip; architecture/quality checks where required by active project gates | `-FullRegression` plus existing 07.12/Quality gate and project test evidence | PASS required |

All fixtures use **temporary stores**; no measurements, pose, geometry accuracy, output existence or camera hardware are certified. Tests assert that capture RAW is **not** implicitly verified. Baseline historical Windows symlink skips must be reported and assessed separately; do not mask or increase skips without disposition.

## Manual Windows HMI gate (operator; mandatory)

1. Launch on real Windows at **100%, 125%, 150% display scale**; repeat at 1366×768 logical target and maximized view as feasible. Record OS/Qt version, monitor resolution/scale and screenshots for each distinct layout.
2. Verify the common heading uses R3.2.1 compact spacing, no redundant eyebrow; Project chooser and dashboard have visible, **non-overlapping 1px separators**, no truncation over control boundaries or large dead header area.
3. Load a real existing SQLite v2 store. Select Project, Specimen, Session, Capture and ProcessingRun through Explorer and center lists; confirm right Inspector identity, metadata and **context-appropriate action buttons**. Check focus/tooltips and docking at narrow widths.
4. Switch Project ⇄ Processing; select a ProcessingRun row, verify synchronized Explorer/Inspector and filters, scrolling, detail split, error text, output-reference disclaimer. The row list must not be replaced by SQLite audit events.
5. Check v1 store read-only, empty v2 store, invalid/moved store, recent reopen and rapid switching. No stale entity selection, phantom run, hidden migration or automatically created SQLite.
6. Inspect Explorer/Inspector/Task Dock visibility and Reset Layout. Verify four workspace navigation controls; Acquisition remains explicitly unimplemented at this stage and Viewer is not silently declared R5-complete.
7. Close/reopen ScanToPath, check worker shutdown and no visual crash. Collect a visible screen recording or annotated screenshots and a short operator verdict.

## Reproducible Windows execution

From repo `E:\1_BigProject\scantopath\scantopath-software` on branch `feat/gd1-desktop-ui`:

```powershell
& .\scripts\verify_gd1_r3_5.ps1 -ProjectRoot (Get-Location).Path -FullRegression
```

Reports are written outside the repository to the sibling `_setup/ScanToPath_GD1_R3_05_Acceptance/` directory, or an explicitly supplied `-EvidenceDir`. Attach the two JUnit XML files, Qt/full regression summary, any separate Architecture/Quality/CTest evidence required by the active GĐ1 gate, HMI screenshots, and commit ID to the acceptance record. The runner does **not** commit, push, migrate or self-certify UI PASS.

## Gate decision / release record

| Gate | Current evidence in this change | Result |
| --- | --- | --- |
| Design/source scope frozen | Test + script + documentation only | READY FOR REVIEW |
| Focused offscreen Qt & integration regression on Windows | Not executed in this connector environment | **NOT_RUN** |
| Full local Windows Python/Architecture/Quality/Native checks | No Windows run log supplied for R3.5 | **NOT_RUN** |
| Manual Windows HMI 100/125/150% | No operator screenshots or signed verdict supplied for R3.5 | **NOT_RUN** |
| **R3.5 final acceptance** | Requires all mandatory gates PASS | **PENDING — DO NOT CLOSE** |

**Closure rule:** only mark `R3.5 — PASS` after actual Windows automated/full regression evidence **and** operator HMI approval. Then preserve commit/hash and proceed to R4.* / R5.* according to R1.4; do not conflate R3.5 with R6.2 or 08.06.6.
