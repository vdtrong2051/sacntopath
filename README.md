# ScanToPath 2026 — Software Foundation / Offline Slice

**Nature:** independent reference implementation, **not** a replacement for an existing ScanToPath repository. No Gemini 2, Raspberry Pi, or ESP32 was connected or tested here.

Scope achieved: software session/capture contracts, reproducible synthetic source, per-capture atomic directory commit, metadata validation, replay/verification, C++20 metric point unprojection/transformation smoke, optional PySide6 UI shell.

## Run

Required: Python 3.12+, CMake 3.22+, C++20 compiler. Windows target for official integration: MSVC x64 (not MinGW/MSYS2).

```sh
python -m pip install -e ".[test]"
python -m pytest -q
python -m scantopath.cli demo --output ./scantopath-data
python -m scantopath.cli verify --output ./scantopath-data
cmake -S cpp -B build -DBUILD_TESTING=ON
cmake --build build --config Release
ctest --test-dir build --output-on-failure -C Release
```

Optional desktop shell:

```sh
python -m pip install -e ".[ui]"
python -m scantopath.ui.main
```

This foundation **does not** implement a hardware Gemini 2 driver, live 3D viewer, RGB-to-depth hardware calibration, registration, TSDF fusion, or production machine control. Those are follow-on milestones; do not claim them as validated.

## Key invariants

- `depth.npy` raw `uint16`, scale `depth_scale_m_per_unit`, separate intrinsics.
- `coordinate_frame = depth_optical`; do **not** presume stage/world transforms exist.
- RGB array must be the same shape as depth and considered aligned for this test-only slice.
- Synthetic measurements are marked `measured=false` and `kind=synthetic`.
- Capture directory has `COMMITTED` only after complete writes; incomplete `.partial` folders aren't read.
- Native geometry uses meters; never silently mix millimeters and meters.
- No generated/inferred geometry can be automatically promoted to measured.

## Further information

Read `docs/ARCHITECTURE.md`, `docs/RESOURCE_MATRIX.md`, `docs/ROADMAP.md`, and `docs/GEMINI2_VALIDATION.md`.
