# PRE-03 — RAW Capture Storage v2 (offline, hardware-independent)

Status: **implemented as a patch; Windows regression and commit pending**.

## Baseline and branch discipline

- Source code basis: `vdtrong2051/sacntopath`, merged `main` HEAD `22da703907bbc40d93a7c3e8dbc070a80d59995c` (PRE-01 and PRE-02 present).
- Continue on the **existing** feature branch `feat/pre-02-raw-rgbd-contract`; fast-forward it to this `main` HEAD before applying. The PRE-03 script **never creates a branch, commits or pushes**.
- Modified: `src/scantopath/storage/session_store.py` only. New: this document and `tests/test_raw_storage.py`.
- No changes to PRE-02 `RawRgbdCapture`, the v1 `CaptureMetadata`, C++, CMake, pybind11, UI, native loader, SDK or CLI.

## File format (schema v2)

```text
scantopath-data/
└── sessions/<session_id>/captures/<capture_id>/
    ├── color.mjpg         # byte-for-byte compressed JPEG/MJPEG packet; NOT aligned
    ├── depth.y16          # byte-for-byte little-endian uint16[H,W]; not .npy
    ├── metadata.json      # RawRgbdCaptureMetadataV2 JSON
    ├── manifest.json      # SHA-256 + byte size for each payload and metadata
    └── COMMITTED          # written last, before sibling rename
```

`depth.y16` is intentionally **not** `depth.npy`: the PRE-02 contract specifies raw little-endian bytes and this format preserves them exactly. Use `RawRgbdCapture.depth_u16_copy()` to produce an owned NumPy `uint16[height,width]` when needed; no resize, alignment, deprojection or interpretation occurs on disk.

### API and compatibility

```python
from scantopath.storage.session_store import SessionStore
store = SessionStore("scantopath-data")
path = store.commit_raw(raw_capture)           # RawRgbdCapture (PRE-02)
reloaded = store.read_raw(path)                 # RawRgbdCapture (hash validated)
reloaded.depth_u16_copy()                       # optional NumPy copy
store.read_capture(path)                       # dispatch by schema_version v1/v2
store.read(v1_capture_path)                     # existing, unchanged v1 tuple API
```

The existing `commit(FrameBundle)`, `read(path)` and `list_committed(session_id)` remain unchanged. `list_committed` lists both versions; use `read_capture()` to open mixed-version session directories. Existing `scantopath.cli verify` uses v1 `read()` and is **not yet a general v2 verifier**; the v2 storage tests and `read_raw()` are the verification entry points for this milestone.

### Manifest contract

- `manifest_schema_version=1`, `capture_schema_version=2` and `capture_id` matching the directory.
- Exact file descriptors for `color.mjpg`, `depth.y16` and `metadata.json` only. Each has `size_bytes` and lowercase hex `sha256`.
- Reader rejects missing/extra files, invalid marker, symlinks, changed sizes, altered payload/metadata, bad manifest descriptors, wrong schema or mismatched directory/capture ID.
- `COMMITTED` is a valid capture marker only after every file has been written and flushed and the sibling `.partial` directory has been renamed. Incomplete `.partial` directories are never exposed by `list_committed()`.
- A repeated `capture_id` is rejected rather than overwritten. A failed write removes the staging directory.
- SHA-256 is **accidental-corruption detection, not authenticity/security**: an attacker able to replace both data and manifest can recompute the hashes. Atomic directory rename on a single filesystem does **not** guarantee power-loss durability; no database transaction or disk directory fsync guarantee is claimed.

### Handheld geometry invariants

RAW v2 preserves independent Color/Depth grids, device timestamp/frame index, separate intrinsic/distortion, Depth-to-Color extrinsic translation **in millimeters**, depth scale **meters/unit**, `alignment_mode="disabled"` and `camera_pose=None`. No stage, encoder or actuator is required. `measured=true` describes a real sensor source; it does not certify accuracy. No object recognition, trajectory guidance, 3D viewer or point-cloud processing is implemented here.

### Synthetic test fixtures vs hardware

All PRE-03 tests are **synthetic**, including the 1280×800 Y16 / 1920×1080 metadata case. The short MJPEG fixture begins with JPEG SOI but is not a genuine decodable image; tests deliberately assert persistence, not JPEG decoding. Gemini 2 adapter and camera+storage hardware roundtrip remain PRE-04.

## Windows regression commands

From the repo root, with `.venv` and `build-orbbec` already present:

```powershell
$pyExe = (Resolve-Path '.\.venv\Scripts\python.exe').Path
& $pyExe -m pytest -q .\tests
Write-Host "PythonExitCode=$LASTEXITCODE"  # Expected 37 passed, 0
ctest --test-dir .\build-orbbec -C Release --output-on-failure
Write-Host "CTestExitCode=$LASTEXITCODE"   # Expected 2/2 passed, 0
$env:SCANTOPATH_ORBBEC_SDK_BIN = 'E:\1_BigProject\scantopath\_sdk\OrbbecSDK_v2.10.6\bin'
& $pyExe -u -X faulthandler -m scantopath.acquisition.native --self-test
Write-Host "SelfTestExitCode=$LASTEXITCODE"  # Expected 0

git diff --check
git diff --stat
git status --short
```

## PRE-03 acceptance gate

1. `commit_raw()` persists Color MJPEG and Depth Y16 bytes unchanged and keeps complete v2 metadata.
2. `read_raw()` reopens and checks payload+metadata sizes, SHA-256 and directory identity.
3. Corrupted data, truncated file, forged manifest, partial capture, duplicate ID and simulated write failure are rejected safely.
4. Unmodified Capture v1 still commits, lists and reads correctly, even alongside v2 using `read_capture()`.
5. On user's Windows machine, pytest **37/37**, CTest **2/2**, native loader self-test exit **0**, and no unplanned source changes.
6. Do not claim real Gemini 2 on-disk capture or automatically proceed to PRE-04 before user acceptance.
