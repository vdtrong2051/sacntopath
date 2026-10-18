#pragma once
// Phase 1.2.3.2.1: vendor-isolated native RGB-D acquisition contract.
// Intentionally does NOT include OrbbecSDK headers. This interface is C++20 only.

#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace scantopath::acquisition {

enum class PixelEncoding : std::uint8_t { Mjpeg = 1, Y16 = 2 };

struct CameraIntrinsics {
    std::uint32_t width = 0;
    std::uint32_t height = 0;
    double fx = 0, fy = 0, cx = 0, cy = 0;
};

struct DistortionCoefficients {
    // Preserve the exact SDK model ID. Do not assume all models are OpenCV Brown-Conrady.
    std::int32_t sdk_model = 0;
    // Order: k1, k2, k3, k4, k5, k6, p1, p2.
    std::array<double, 8> k1_k6_p1_p2{};
};

struct DepthToColorExtrinsics {
    // SDK raw row-major rotation and millimeter translation (NOT meters).
    std::array<double, 9> rotation{};
    std::array<double, 3> translation_mm{};
};

struct FrameData {
    PixelEncoding encoding = PixelEncoding::Mjpeg;
    std::uint32_t width = 0;
    std::uint32_t height = 0;
    std::uint64_t frame_index = 0;
    std::uint64_t timestamp_us = 0; // Per-frame SDK device timestamp.
    std::vector<std::uint8_t> bytes; // Owned copy; safe after camera.close().
};

struct DeviceIdentity {
    std::string name;
    std::string firmware;
    std::string usb_connection;
    std::uint32_t pid = 0;
    // Serial number intentionally not collected into default diagnostic output.
};

struct RgbdCapture {
    DeviceIdentity device;
    FrameData color;
    FrameData depth;
    CameraIntrinsics color_intrinsics;
    CameraIntrinsics depth_intrinsics;
    DistortionCoefficients color_distortion;
    DistortionCoefficients depth_distortion;
    DepthToColorExtrinsics depth_to_color;
    double depth_scale_m_per_unit = 0;
    bool align_disabled = true;
    bool frame_sync_requested = false;
    // Timestamp separation is reported, not treated as proof of sync accuracy.
    std::uint64_t timestamp_delta_us() const noexcept;
};

// No dependency on OrbbecSDK; tested with synthetic C++ packets.
bool validate_raw_capture(const RgbdCapture &capture, std::string *error = nullptr);

// Single-device acquisition source, one-shot capture, fixed RAW profiles.
// Not thread-safe. Close OrbbecViewer before using this class.
class OrbbecCameraSource final {
public:
    OrbbecCameraSource();
    ~OrbbecCameraSource() noexcept;
    OrbbecCameraSource(const OrbbecCameraSource &) = delete;
    OrbbecCameraSource &operator=(const OrbbecCameraSource &) = delete;
    OrbbecCameraSource(OrbbecCameraSource &&) = delete;
    OrbbecCameraSource &operator=(OrbbecCameraSource &&) = delete;

    // Opens Gemini 2, requests color MJPG 1920x1080@30 + RAW depth Y16 1280x800@30.
    // Throws std::runtime_error / ob::Error on unsupported hardware or stream startup.
    void open();
    bool is_open() const noexcept;
    DeviceIdentity device() const; // Requires open().

    // Returns a complete pair from one SDK frameset; copies both buffers.
    // Throws on timeout, invalid dimensions/format or invalid SDK calibration.
    RgbdCapture read_next(std::uint32_t per_attempt_timeout_ms = 1000,
                          std::uint32_t max_attempts = 10);
    void close(); // Can be called repeatedly.

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace scantopath::acquisition
