# Architecture: desktop product first, acquisition integrated later

## Agreed tech baseline (not a new architecture proposal)

- Desktop Qt6/PySide6. Python 3.12 for application/orchestration.
- C++20 native geometry/processing, CMake + MSVC x64 + vcpkg, Eigen / Open3D C++ / OpenCV C++, pybind11 bindings.
- 3D viewer VTK+Qt; SQLite / SQLAlchemy metadata; Pydantic I/O contracts.
- Modular monolith; one owner for each data contract; no microservice or web UI requirement.

```
Qt/PySide6: project | scan | geometry | quality | features | replica | export
       |                         |                  |
Python app services: project/service | processing jobs | traceability
       |                         |                  |
       +------------ port/adapters and typed contracts ----------+
                 |                                   |
       Python data/model layer                pybind11 bridge
       SQLite/project/raw files               C++20 geometry core
                 |                         Eigen/Open3D/OpenCV/PCL optional
                 +--------+--------------------------+
                          |
                Orbbec capture provider
          [offline fixture / hardware Gemini 2]
                          |
          future RasPi capture-coordinator + ESP32
```

## Physical deployment — two explicit modes

A. Desktop **direct-connect** proof: Gemini 2 via USB 3.0 to Windows PC; collect raw RGB-D, timestamp, intrinsics, scale; perform geometry on desktop. This is a software MVP/testing mode, not the final rig.

B. Integrated rig per agreed team interface: *fixed* Gemini 2 USB3 to Raspberry Pi 4 4GB; ESP32 handles real-time motion, encoders, safety; Pi handles SDK/capture/synchronization/durable local storage; desktop handles heavy processing, viewer, metrology, features. Pi ↔ desktop over network. Do not deploy bulky model checkpoints to Pi 4GB.

## Pose / metric contract

Intrinsic camera model (depth optical frame, meters): X=(u-cx)*z/fx; Y=(v-cy)*z/fy; Z=z. Raw depth uint16 multiplied by calibrated meters-per-unit.

Transform ownership convention, to be calibrated before multi-view fusion:

`p_object = inv(T_world_object(theta,phi)) * T_world_camera * p_depth_camera`.

The camera is fixed; **the object moves**. `T_world_camera` is constant after calibration; encoder angles and stage geometry determine `T_world_object`. Axis intersection, signs, homing offsets, angle definitions and transform order require measured calibration. ICP is a constrained refinement, not a substitute for known stage pose.

## Dataset/provenance

`project -> specimen -> scan_session -> capture -> processing_run -> derived_artifacts -> feature -> relation -> replica`. A capture records intrinsic/distortion, RGB/depth registration, depth scale, device/firmware/SDK IDs, timestamp, stage pose source/quality, measured vs inferred. Track raw immutable files separately from derived point clouds and meshes. Don't automatically mark inferred geometry as measured.

`COMMITTED` per capture in this reference means data files and schema were validated and renamed as a set. A future Pi implementation must also verify controller `REACHED/STABLE`, file integrity, durable manifest and recovery across power loss before acknowledging CAPTURE_COMMIT to desktop.

## Processing pipeline

Frame acquisition -> RGB/Depth alignment -> invalid-depth filtering -> segmentation ROI -> metric unprojection -> frame transforms -> encoder-initialized registration -> geometric ICP refinement + quality gates -> fusion (point cloud / optional TSDF) -> normals/curvature -> feature fitting (RANSAC/least squares) -> per-feature confidence/provenance -> engineering replica -> technical export.

Confidence is not raw model softmax; it is a calibrated, task-dependent score and must be supported by error/coverage/provenance. Never silently fill missing surfaces and call them observed.

## Implementation boundary

This package implements the *offline reference slice* only: capture contract, synthetic source, atomic write and read, minimal Qt shell, C++ metric backprojection/rigid transform and tests. Native SDK integration is not implemented or tested. Production stage/frame synchronization, calibration, D2C alignment, GPU rendering, registration and meshing are future tasks.
