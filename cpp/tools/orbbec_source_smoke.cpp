// Phase 1.2.3.2.1: hardware smoke test. No files are persisted by design.
#include "scantopath/acquisition/orbbec_camera_source.hpp"

#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc, char **argv) {
    if(argc != 2 || std::string(argv[1]) != "--once") {
        std::cerr << "Usage: scantopath_orbbec_source_smoke --once\n";
        return 2;
    }
    try {
        scantopath::acquisition::OrbbecCameraSource camera;
        camera.open();
        const auto data = camera.read_next();
        camera.close(); // Validate that the copied data remains accessible.
        std::string error;
        const bool valid = scantopath::acquisition::validate_raw_capture(data, &error);
        const auto &c = data.color;
        const auto &d = data.depth;
        std::cout << std::fixed << std::setprecision(6)
                  << "device.name=" << data.device.name << "\n"
                  << "device.firmware=" << data.device.firmware << "\n"
                  << "device.usb=" << data.device.usb_connection << "\n"
                  << "color.width=" << c.width << "\n"
                  << "color.height=" << c.height << "\n"
                  << "color.payload_bytes=" << c.bytes.size() << "\n"
                  << "depth.width=" << d.width << "\n"
                  << "depth.height=" << d.height << "\n"
                  << "depth.payload_bytes=" << d.bytes.size() << "\n"
                  << "depth.scale_m_per_unit=" << data.depth_scale_m_per_unit << "\n"
                  << "depth.fx=" << data.depth_intrinsics.fx << "\n"
                  << "depth.fy=" << data.depth_intrinsics.fy << "\n"
                  << "depth.cx=" << data.depth_intrinsics.cx << "\n"
                  << "depth.cy=" << data.depth_intrinsics.cy << "\n"
                  << "extrinsic.d2c.tx_mm=" << data.depth_to_color.translation_mm[0] << "\n"
                  << "timing.color_timestamp_us=" << c.timestamp_us << "\n"
                  << "timing.depth_timestamp_us=" << d.timestamp_us << "\n"
                  << "timing.delta_us=" << data.timestamp_delta_us() << "\n"
                  << "framesync.requested=" << (data.frame_sync_requested ? "true" : "false") << "\n"
                  << "buffer.copy_survived_close=" << (!c.bytes.empty() && !d.bytes.empty() ? "true" : "false") << "\n"
                  << "diagnostic.raw_packet_valid=" << (valid ? "true" : "false") << "\n";
        if(!valid) std::cerr << "INVALID: " << error << "\n";
        return valid ? 0 : 1;
    } catch(const std::exception &e) {
        std::cerr << "OrbbecCameraSource ERROR: " << e.what() << "\n";
        return 1;
    }
}
