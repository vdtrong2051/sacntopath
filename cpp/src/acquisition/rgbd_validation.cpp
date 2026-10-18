#include "scantopath/acquisition/orbbec_camera_source.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

namespace scantopath::acquisition {
std::uint64_t RgbdCapture::timestamp_delta_us() const noexcept {
    return color.timestamp_us >= depth.timestamp_us
        ? color.timestamp_us - depth.timestamp_us
        : depth.timestamp_us - color.timestamp_us;
}

bool validate_raw_capture(const RgbdCapture &v, std::string *error) {
    const auto fail = [error](const char *message) {
        if(error) *error = message;
        return false;
    };
    if(v.device.name.empty() || v.device.firmware.empty())
        return fail("Device identity incomplete");
    if(!v.align_disabled) return fail("Expected unaligned/raw RGB-D data");
    if(v.color.encoding != PixelEncoding::Mjpeg || v.depth.encoding != PixelEncoding::Y16)
        return fail("Expected original MJPG color and Y16 depth encoding");
    if(v.color.width == 0 || v.color.height == 0 || v.depth.width == 0 || v.depth.height == 0)
        return fail("Empty frame dimensions");
    if(v.color.timestamp_us == 0 || v.depth.timestamp_us == 0)
        return fail("Missing device timestamps");
    if(v.color.bytes.empty()) return fail("Empty MJPG payload");
    const std::uint64_t depth_bytes = static_cast<std::uint64_t>(v.depth.width) * v.depth.height * 2U;
    if(depth_bytes != v.depth.bytes.size()) return fail("Y16 payload length does not match dimensions");
    if(!(std::isfinite(v.depth_scale_m_per_unit) && v.depth_scale_m_per_unit > 0))
        return fail("Depth scale must be finite and positive, in meters per unit");
    const auto intrinsic_ok = [](const CameraIntrinsics &k, const FrameData &f) {
        return k.width == f.width && k.height == f.height
            && std::isfinite(k.fx) && std::isfinite(k.fy)
            && std::isfinite(k.cx) && std::isfinite(k.cy)
            && k.fx > 0 && k.fy > 0;
    };
    if(!intrinsic_ok(v.color_intrinsics, v.color) || !intrinsic_ok(v.depth_intrinsics, v.depth))
        return fail("Stream intrinsics mismatch or invalid focal length");
    const auto finite = [](double d) { return std::isfinite(d); };
    if(!std::all_of(v.depth_to_color.rotation.begin(), v.depth_to_color.rotation.end(), finite)
       || !std::all_of(v.depth_to_color.translation_mm.begin(), v.depth_to_color.translation_mm.end(), finite))
        return fail("Non-finite extrinsic calibration");
    if(!std::all_of(v.color_distortion.k1_k6_p1_p2.begin(), v.color_distortion.k1_k6_p1_p2.end(), finite)
       || !std::all_of(v.depth_distortion.k1_k6_p1_p2.begin(), v.depth_distortion.k1_k6_p1_p2.end(), finite))
        return fail("Non-finite distortion calibration");
    if(error) error->clear();
    return true;
}
} // namespace scantopath::acquisition
