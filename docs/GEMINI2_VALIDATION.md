# Gemini 2 first-connection evidence checklist

Device is Orbbec **Gemini 2**, NOT Gemini 2 XL, Femto Bolt or Astra Mini Pro. Orbbec official docs describe Gemini 2 as **Active Stereo IR**, not a ToF camera. Official OrbbecSDK v2 compatibility list says Gemini 2 minimum FW 1.4.92, recommended FW 1.4.98 at the time consulted; check the release actually installed.

## Required before marking driver verified

[ ] Report connected USB bus speed (prefer USB 3), Windows version, OrbbecSDK v2 exact tag, firmware version, device serial (store locally; redact in public reports).
[ ] Use official OrbbecViewer to enumerate device/color/depth stream modes and depth work mode supported by this exact FW.
[ ] Select depth & RGB resolution, FPS, pixel formats; save immutable capture configuration.
[ ] Check device camera intrinsics and distortion, color/depth extrinsics, alignment semantics; test hardware/software D2C if supported.
[ ] Read **frame-specific depth scale** and sensor timestamps. Avoid assuming values from a sample.
[ ] Save raw uint16 depth and RGB for same frameset; verify shapes and units after roundtrip.
[ ] Test unplug/replug, timeout, dropped frames, sensor startup stabilization, no busy UI blocking.
[ ] Ground-truth flat board/cylinder: repeated captures at fixed geometry and changed distance, report mm errors and % invalid pixels (do not use mirror-paper RMSE as Gemini 2 performance claim).
[ ] Check Windows direct capture first; then repeat on Pi 4 4GB ARM64 if supported SDK artifact and USB bandwidth have been validated on that hardware.
[ ] Record confidence/valid-mask data if device and SDK expose it; otherwise treat confidence as unknown rather than 1.0.
[ ] For full integrated capture: ESP32 REACHED/STABLE event must precede frame acceptance; Pi commits files and emits capture_id before motion proceeds.

Evidence for each checked row: file path, SDK/firmware, date, sample ID, test command, observed result.

Official sources: https://github.com/orbbec/OrbbecSDK_v2 ; https://github.com/orbbec/OrbbecSDK_v2/releases ; https://www.orbbec.com/products/structured-light-camera/gemini-2/
