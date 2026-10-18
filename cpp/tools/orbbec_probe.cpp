// ScanToPath native probe v0.1.1 - diagnostic only (no SessionStore writes).
// OrbbecSDK_v2 API usage modeled after official enumerate/sync_align examples.
#include <libobsensor/ObSensor.hpp>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <exception>
#include <iomanip>
#include <iostream>
#include <memory>
#include <string>

namespace {
void show_usage() {
    std::cout << "Usage: scantopath_orbbec_probe --info | --capture\n"
              << "  --info     Device identity and supported Color/Depth profiles (no stream)\n"
              << "  --capture  RGB-D frameset diagnostic: unaligned 1920x1080 MJPG + "
                 "1280x800 Y16 at 30 fps\n";
}

void print_intrinsic(const char *label, const OBCameraIntrinsic &k) {
    std::cout << label << ".width=" << k.width << "\n"
              << label << ".height=" << k.height << "\n"
              << label << ".fx=" << k.fx << "\n"
              << label << ".fy=" << k.fy << "\n"
              << label << ".cx=" << k.cx << "\n"
              << label << ".cy=" << k.cy << "\n";
}

void print_profiles(ob::Pipeline &pipe, OBSensorType sensor, const char *label) {
    auto profiles = pipe.getStreamProfileList(sensor);
    std::cout << "SUPPORTED " << label << " profiles: " << profiles->getCount() << "\n";
    for(uint32_t i = 0; i < profiles->getCount(); ++i) {
        auto p = profiles->getProfile(i)->as<ob::VideoStreamProfile>();
        std::cout << "  " << label << " " << p->getWidth() << "x" << p->getHeight()
                  << " @" << p->getFps() << " format=" << static_cast<int>(p->getFormat()) << "\n";
    }
}

int run(const bool capture) {
    // Create one SDK device owner. OrbbecViewer must be fully closed before this.
    ob::Pipeline pipe;
    auto info = pipe.getDevice()->getDeviceInfo();
    std::cout << "device.name=" << info->getName() << "\n"
              << "device.firmware=" << info->getFirmwareVersion() << "\n"
              << "device.usb=" << info->getConnectionType() << "\n"
              << "device.pid=" << info->getPid() << "\n";
    // Intentionally exclude camera serial number from default logs.
    if(!capture) {
        print_profiles(pipe, OB_SENSOR_COLOR, "color");
        print_profiles(pipe, OB_SENSOR_DEPTH, "depth");
        return EXIT_SUCCESS;
    }

    auto config = std::make_shared<ob::Config>();
    config->enableVideoStream(OB_STREAM_COLOR, 1920, 1080, 30, OB_FORMAT_MJPG);
    config->enableVideoStream(OB_STREAM_DEPTH, 1280, 800, 30, OB_FORMAT_Y16);
    config->setAlignMode(ALIGN_DISABLE); // Preserve original optical frames.
    config->setFrameAggregateOutputMode(OB_FRAME_AGGREGATE_OUTPUT_ALL_TYPE_FRAME_REQUIRE);
    pipe.enableFrameSync();
    pipe.start(config);

    // Starting streams may yield several incomplete framesets; wait for both.
    std::shared_ptr<ob::DepthFrame> depth;
    std::shared_ptr<ob::ColorFrame> color;
    for(int i=0; i<20; ++i) {
        auto set = pipe.waitForFrameset(2000);
        if(!set) continue;
        depth = set->getDepthFrame();
        color = set->getColorFrame();
        if(depth && color && depth->getData() && color->getData()) break;
    }
    if(!depth || !color || !depth->getData() || !color->getData()) {
        pipe.stop();
        std::cerr << "ERROR: no complete Color+Depth frameset within timeout\n";
        return EXIT_FAILURE;
    }
    const auto depth_profile = depth->getStreamProfile()->as<ob::VideoStreamProfile>();
    const auto color_profile = color->getStreamProfile()->as<ob::VideoStreamProfile>();
    const auto depth_k = depth_profile->getIntrinsic();
    const auto color_k = color_profile->getIntrinsic();
    const auto d2c = depth_profile->getExtrinsicTo(color_profile);
    const auto mm_per_unit = static_cast<double>(depth->getValueScale());
    const auto meters_per_unit = mm_per_unit * 0.001;
    const auto expected_depth_size = static_cast<uint64_t>(depth->getWidth()) * depth->getHeight() * sizeof(uint16_t);

    std::cout << std::fixed << std::setprecision(6)
              << "align.mode=DISABLE\n"
              << "frameset.color.format=" << static_cast<int>(color->getFormat()) << "\n"
              << "frameset.color.width=" << color->getWidth() << "\n"
              << "frameset.color.height=" << color->getHeight() << "\n"
              << "frameset.color.bytes=" << color->getDataSize() << "\n"
              << "frameset.color.frame_index=" << color->getIndex() << "\n"
              << "frameset.color.timestamp_us=" << color->getTimeStampUs() << "\n"
              << "frameset.depth.format=" << static_cast<int>(depth->getFormat()) << "\n"
              << "frameset.depth.width=" << depth->getWidth() << "\n"
              << "frameset.depth.height=" << depth->getHeight() << "\n"
              << "frameset.depth.bytes=" << depth->getDataSize() << "\n"
              << "frameset.depth.frame_index=" << depth->getIndex() << "\n"
              << "frameset.depth.timestamp_us=" << depth->getTimeStampUs() << "\n"
              << "frameset.depth.value_scale_mm_per_unit=" << mm_per_unit << "\n"
              << "frameset.depth.scale_m_per_unit=" << meters_per_unit << "\n";
    print_intrinsic("intrinsic.color", color_k);
    print_intrinsic("intrinsic.depth", depth_k);
    for(int i=0;i<9;++i) std::cout << "extrinsic.d2c.rot" << i << "=" << d2c.rot[i] << "\n";
    for(int i=0;i<3;++i) std::cout << "extrinsic.d2c.trans_mm" << i << "=" << d2c.trans[i] << "\n";
    // No RGB-to-depth registration claim: image dimensions are different.
    bool ok = (depth->getWidth()==1280 && depth->getHeight()==800
               && color->getWidth()==1920 && color->getHeight()==1080
               && color->getFormat()==OB_FORMAT_MJPG && depth->getFormat()==OB_FORMAT_Y16
               && expected_depth_size == depth->getDataSize()
               && depth->getTimeStampUs() > 0 && color->getTimeStampUs() > 0
               && std::isfinite(meters_per_unit) && meters_per_unit > 0
               && depth_k.fx > 0 && depth_k.fy > 0 && color_k.fx > 0 && color_k.fy > 0);
    std::cout << "diagnostic.raw_formats_and_scale_valid=" << (ok ? "true" : "false") << "\n";
    // SDK owns the frame memory; never use it after pipeline shutdown.
    depth.reset(); color.reset();
    pipe.stop();
    return ok ? EXIT_SUCCESS : EXIT_FAILURE;
}
} // namespace

int main(int argc, char **argv) {
    if(argc != 2 || (std::string(argv[1]) != "--info" && std::string(argv[1]) != "--capture")) {
        show_usage();
        return EXIT_FAILURE;
    }
    try { return run(std::string(argv[1]) == "--capture"); }
    catch(const ob::Error &e) {
        std::cerr << "OrbbecSDK ERROR: " << e.what() << "\n";
        return EXIT_FAILURE;
    }
    catch(const std::exception &e) {
        std::cerr << "ERROR: " << e.what() << "\n";
        return EXIT_FAILURE;
    }
}
