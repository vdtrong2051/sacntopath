# ScanToPath — Architecture baseline (PRE-01, 2026-10-18)

## 1. Stack and module boundaries

Baseline stack remains: Qt 6/PySide6 desktop; Python 3.12 orchestration; C++20 native geometry and acquisition; CMake + MSVC x64 + pybind11; planned Eigen / Open3D C++ / OpenCV C++ / VTK+Qt; SQLite/SQLAlchemy metadata and Pydantic contracts. **Planned** dependencies are not claimed as implemented. The current repository contains a minimal C++ geometry core, Python storage/domain, C++ Orbbec source, pybind11 bridge and a placeholder PySide6 shell; no working VTK viewer or SQLite application service yet.

```text
Desktop PySide6 (current: shell only; future: project / acquisition / 3D viewer)
          |
Python services and typed contracts
  |                               |
  +-- Capture Store (v1 synthetic) +-- pybind11 native bridge (tested)
          |                               |
   Local raw files                    C++20 OrbbecCameraSource
                                          |
                                   OrbbecSDK v2 / Gemini 2 USB3

Future: Project/Specimen/Session/ProcessingRun metadata in SQLite;
        VTK+Qt 3D viewer; native multi-view geometry pipeline.
```

**Ownership:** native SDK frames are copied into application-owned C++ data; pybind11 returns separately owned Python `bytes`/NumPy arrays. Importing the Python loader does not automatically open the device. UI must not run blocking camera acquisition or heavy geometry work on its main thread once integrated.

## 2. Active acquisition mode: handheld RGB-D

The present **hardware setup is one handheld Orbbec Gemini 2**. The operator moves the camera around a specimen. **No motor/turntable/encoder/ESP32/Raspberry Pi or other actuator is part of the current acceptance baseline.** Older fixed-camera/rotating-object architectural notes describe a *possible future rig*, not a current dependency.

Functional requirements for later milestones, **not yet implemented**:

1. Plan a constrained/structured **handheld scan trajectory** and guide the operator visibly. Planning the path is mandatory for the intended handheld workflow.
2. Show **live object recognition/detection overlays** (e.g. moving 2D boxes or masks) and maintain object tracking where useful. Detection, tracking and segmentation remain separate concepts, and a 2D box is not a metric 3D surface.
3. Estimate/check the **actual time-varying camera pose** from measurements/registration or suitable visual/depth tracking. A planned trajectory is *not* observed trajectory or known frame transforms.
4. Acquire multiple RGB-D views and reconstruct geometry only after frame/time/pose/quality gates are designed and verified.

The exact algorithms and interaction design belong to future functional increments; PRE-01 introduces **no** new camera perception, trajectory, UI or reconstruction feature.

## 3. Geometry and frame contract

- Depth optical frame: `p_depth = ((u-cx) z/fx, (v-cy) z/fy, z)` where `z = raw_depth * depth_scale_m_per_unit` in **meters**. Respect invalid depth pixels and calibrated camera model when implementing a real geometry pipeline.
- Handheld mode: `T_world_depth_camera(t)` varies with time and is currently **unknown**. No fixed `T_world_camera` and no encoder-derived `T_world_object(theta, phi)` can be assumed for present captures.
- Transform estimates must carry their frame convention, timestamp, source and uncertainty/quality. A plan to move the camera is not measured pose; do not silently substitute nominal poses.
- Gemini 2 baseline reads **RAW, unaligned** Color MJPG 1920×1080 and Depth Y16 1280×800. Separate camera intrinsics/distortion; Depth→Color SDK extrinsics with translation in **millimeters**. SDK depth scale is stored in **meters/unit**.
- A requested frame-sync mode or a single observed timestamp delta does not prove exposure synchronization or metrological accuracy.

A future fixed-camera/actuated rig, if separately approved, may add additional poses/transform providers through adapters; do not make it a dependency of handheld data contracts.

## 4. Data model and persistence truth

Target provenance chain:

```text
Project → Specimen → ScanSession → RawCapture → ProcessingRun → DerivedArtifacts
                                             → Quality/Features/Relations → Replica
```

**Implemented now:** Pydantic v1 `CaptureMetadata`, `ProcessingRun` schema, `SyntheticSource`, `SessionStore` synthetic atomic staging/commit and read-back; native `RgbdCapture` packet and pybind11 loader. **Not implemented now:** persistent Project/Specimen/ProcessingRun services, SQLite metadata store, real RAW `RgbdCapture` → storage adapter, v2 RGB-D schema and manifest/checksums.

The v1 `SessionStore` assumes `rgb: uint8[H,W,3]` **already matching** `depth: uint16[H,W]` and sets `rgb_registered_to_depth=True`; this is valid for its synthetic fixture, **not for Gemini 2 unaligned RAW**. No code should pass native RAW to this contract without an explicit v2 schema and storage migration (PRE-02/03). Preserve existing v1 read compatibility. No invented pose, D2C alignment or measurement confidence.

A capture-level `COMMITTED` marker follows staging and an in-filesystem rename. This does not itself guarantee durable metadata transactions or complete power-loss recovery; these claims require separate tests.

## 5. Roadmap boundaries

- PRE-01: baseline/repository/docs only, no application logic changes.
- PRE-02: RAW RGB-D v2 contract (separate streams/calibration/time/unknown pose).
- PRE-03: raw storage + v1 compatibility, integrity and read-back.
- PRE-04: native-to-storage adapter and one-shot real hardware capture/replay.
- PRE-05: close GĐ0 Project/Specimen/Session/ProcessingRun/logging metadata lifecycle.
- PRE-06: full regression, integrated acceptance and updated evidence.
- **Only then**: formal GĐ1 functional core (sessions 06–08: point cloud import/model, VTK viewer, coordinate frames/basic measurement).

Later GĐ2+ will address RGB-D to point clouds, actual multi-view pose, filtering, registration/fusion, and handheld trajectory guidance/object perception by separately approved work packages. Do not pull actuator control into GĐ0/GĐ1.

Engineering trust remains evidence-based: sensor measurement ≠ validated geometry ≠ inferred/reconstructed geometry. Preserve source, calibration, parameters and error/provenance for later verification.
