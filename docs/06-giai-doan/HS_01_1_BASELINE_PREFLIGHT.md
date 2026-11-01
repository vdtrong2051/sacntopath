# HS-01.1 — Baseline & Live Streaming Preflight

**Scope:** source/environment verification and focused offline smoke. **No auto-keyframe selection, camera changes, data migrations, or registration.**

**Source baseline reviewed:** `main@60c60e62fbf7685a8994ab2c66054bceb7eda0e5` (2026-11-01). Verify the operator's actual local HEAD and uncommitted changes independently.

## 1. Windows operator — offline gate

From the local repository, with the project venv active:

```powershell
$repo = 'E:\1_BigProject\scantopath\scantopath-software'
Set-Location $repo
$env:PYTHONUTF8 = '1'
$env:QT_QPA_PLATFORM = 'offscreen'
& .\.venv\Scripts\python.exe -X utf8 scripts\hs_01_1_preflight.py --smoke
```

Expected: `HS_01_1_PREFLIGHT=PASS_OFFLINE`, with no `FAIL`. The preflight never opens the camera; `hardware=NOT_TESTED` even when offline tests pass. `SDK_BIN` is `UNVERIFIED` if it is not configured. If `worktree_dirty=true`, inspect your local changes before any branch switch or patch application; the diagnostic itself never changes Git.

For a permanent receipt, add `--json-out 'E:\1_BigProject\scantopath\_setup\HS_01_1\evidence\baseline.json'`. The file must not already exist and must be **outside** the source repository.

## 2. Windows operator — real hardware gate (explicit; sequential)

Connect Gemini 2 via USB3, close OrbbecViewer or any other camera owner. If the SDK is not located through an existing installation path, configure the directory **containing** `OrbbecSDK.dll`:

```powershell
$env:SCANTOPATH_ORBBEC_SDK_BIN = 'E:\1_BigProject\scantopath\_sdk\OrbbecSDK_v2.10.6\bin'  # adjust to actual SDK path
```

The following pre-existing scripts are **not** automatically executed by the offline preflight:

```powershell
# RGB-D live service / worker; no RAW or DB writes
& .\.venv\Scripts\python.exe -X utf8 scripts\gd2_09_05_live_probe.py --seconds 15

# Real Qt capture workspace, live preview + ROI analysis, stop/reopen cycles
# --output must point to a new filename outside the repository.
& .\.venv\Scripts\python.exe -X utf8 scripts\gd2_09_07_3_hardware_probe.py --cycles 2 --seconds 5 --output 'E:\1_BigProject\scantopath\_setup\HS_01_1\evidence\ui_cycles.json'
```

The UI lifecycle probe does **not** verify whether the bounding box correctly encloses the actual object: perform that visual check yourself and record it separately. Both probes report no RAW persisted. Do not open multiple camera owners simultaneously.

The historical RAW persistence/replay hardware probe exists at `scripts/gd2_09_08_3_hardware_probe.py`; it creates a **new isolated store**, not an existing operator store. Run it only if explicitly testing RAW storage and give `--keep-root` a non-existing path; this is **not required for HS-01.1**, whose scope is live-stack preflight.

## 3. Acceptance and limitations

| ID | Pass condition | Evidence |
|---|---|---|
| `HS01.1-OFFLINE` | Python/dependencies/imports, Git/source inventory, focused tests PASS | preflight output + optional JSON |
| `HS01.1-LIVE` | Real Gemini 2 live frames with positive frame count, no camera errors | `GD2_09_05_DEVICE_PROBE=PASS` |
| `HS01.1-UI` | Qt live preview, ROI analysis, safe close/reopen across two cycles | `GD2_09_07_3_HARDWARE_UI=PASS` + JSON |
| `HS01.1-HUMAN` | Operator confirms actual live image and ROI behavior on the physical scene | manual observation |

**Closure:** `PASS` only after Windows hardware/UI evidence and operator observation. Offline-only results are `PASS_OFFLINE / HARDWARE_NOT_TESTED`, never HS-01.1 final PASS. The existing full regression timeout is outside this focused gate and remains an unresolved exception.

**Next checkpoint:** HS-01.2 — Keyframe Selection Service. No auto-capture was implemented here.
