#include "scantopath/acquisition/orbbec_camera_source.hpp"
#include <cassert>
#include <string>

using namespace scantopath::acquisition;

int main() {
    RgbdCapture v;
    v.device.name = "Orbbec Gemini 2";
    v.device.firmware = "1.4.98";
    v.color.encoding = PixelEncoding::Mjpeg;
    v.color.width = 1920; v.color.height = 1080;
    v.color.bytes = {0xff, 0xd8, 0xff, 0xd9};
    v.color.timestamp_us = 100'000;
    v.depth.encoding = PixelEncoding::Y16;
    v.depth.width = 4; v.depth.height = 2;
    v.depth.bytes.resize(16);
    v.depth.timestamp_us = 116'107;
    v.color_intrinsics = {1920, 1080, 1030.94, 1031.01, 965.81, 537.89};
    v.depth_intrinsics = {4, 2, 2., 2., 2., 1.};
    v.depth_to_color.rotation = {1,0,0,0,1,0,0,0,1};
    v.depth_scale_m_per_unit = 0.001;
    std::string reason;
    if(!validate_raw_capture(v, &reason)) return 1;
    if(v.timestamp_delta_us() != 16'107) return 2;

    v.depth.bytes.resize(15);  // Invalid buffer must be rejected.
    if(validate_raw_capture(v, &reason) || reason.empty()) return 3;
    v.depth.bytes.resize(16);
    v.depth_scale_m_per_unit = 0.0;
    if(validate_raw_capture(v, &reason)) return 4;
    v.depth_scale_m_per_unit = 0.001;
    v.depth_intrinsics.width = 1280;
    if(validate_raw_capture(v, &reason)) return 5;
    v.depth_intrinsics.width = 4;
    v.align_disabled = false;
    if(validate_raw_capture(v, &reason)) return 6;
    v.align_disabled = true;
    if(!validate_raw_capture(v, &reason) || !reason.empty()) return 7;
    return 0;
}
