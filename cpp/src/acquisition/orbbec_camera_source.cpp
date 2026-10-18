#include "scantopath/acquisition/orbbec_camera_source.hpp"

#include <libobsensor/ObSensor.hpp>
#include <stdexcept>
#include <utility>

namespace scantopath::acquisition {
namespace {
CameraIntrinsics convert_intrinsics(const OBCameraIntrinsic &k) {
    return {static_cast<std::uint32_t>(k.width), static_cast<std::uint32_t>(k.height),
            k.fx, k.fy, k.cx, k.cy};
}

DistortionCoefficients convert_distortion(const OBCameraDistortion &d) {
    return {static_cast<std::int32_t>(d.model),
            {d.k1, d.k2, d.k3, d.k4, d.k5, d.k6, d.p1, d.p2}};
}

DepthToColorExtrinsics convert_extrinsics(const OBExtrinsic &e) {
    DepthToColorExtrinsics result;
    for(std::size_t i = 0; i < result.rotation.size(); ++i) result.rotation[i] = e.rot[i];
    for(std::size_t i = 0; i < result.translation_mm.size(); ++i) result.translation_mm[i] = e.trans[i];
    return result;
}

FrameData copy_frame(const std::shared_ptr<ob::VideoFrame> &frame, PixelEncoding encoding) {
    if(!frame || !frame->getData() || frame->getDataSize() == 0)
        throw std::runtime_error("Camera returned null or empty frame");
    FrameData packet;
    packet.encoding = encoding;
    packet.width = frame->getWidth();
    packet.height = frame->getHeight();
    packet.frame_index = frame->getIndex();
    packet.timestamp_us = frame->getTimeStampUs();
    const auto *data = frame->getData();
    packet.bytes.assign(data, data + frame->getDataSize()); // OWNED COPY
    return packet;
}
} // namespace

struct OrbbecCameraSource::Impl {
    std::unique_ptr<ob::Pipeline> pipeline;
    DeviceIdentity identity;
    bool started = false;
};

OrbbecCameraSource::OrbbecCameraSource() : impl_(std::make_unique<Impl>()) {}
OrbbecCameraSource::~OrbbecCameraSource() noexcept {
    try { close(); } catch(...) { /* never throw from a destructor */ }
}

bool OrbbecCameraSource::is_open() const noexcept {
    return impl_ && impl_->pipeline && impl_->started;
}

void OrbbecCameraSource::open() {
    if(is_open()) throw std::logic_error("Camera source already open");
    // The default Orbbec pipeline selects the first available camera.
    // This phase deliberately supports exactly one connected Gemini 2.
    auto pipeline = std::make_unique<ob::Pipeline>();
    auto info = pipeline->getDevice()->getDeviceInfo();
    DeviceIdentity identity{info->getName(), info->getFirmwareVersion(),
                            info->getConnectionType(), info->getPid()};
    if(identity.name != "Orbbec Gemini 2")
        throw std::runtime_error("Expected Orbbec Gemini 2 (non-L/XL), got: " + identity.name);
    auto config = std::make_shared<ob::Config>();
    config->enableVideoStream(OB_STREAM_COLOR, 1920, 1080, 30, OB_FORMAT_MJPG);
    config->enableVideoStream(OB_STREAM_DEPTH, 1280, 800, 30, OB_FORMAT_Y16);
    config->setAlignMode(ALIGN_DISABLE);
    config->setFrameAggregateOutputMode(OB_FRAME_AGGREGATE_OUTPUT_ALL_TYPE_FRAME_REQUIRE);
    pipeline->enableFrameSync(); // Request only, not measured sync guarantee.
    pipeline->start(config);
    impl_->identity = std::move(identity);
    impl_->pipeline = std::move(pipeline);
    impl_->started = true;
}

DeviceIdentity OrbbecCameraSource::device() const {
    if(!is_open()) throw std::logic_error("Call open() before device()");
    return impl_->identity;
}

RgbdCapture OrbbecCameraSource::read_next(std::uint32_t per_attempt_timeout_ms,
                                           std::uint32_t max_attempts) {
    if(!is_open()) throw std::logic_error("Call open() before read_next()");
    if(per_attempt_timeout_ms == 0 || max_attempts == 0 || max_attempts > 100)
        throw std::invalid_argument("Timeout and attempt count must be positive; max_attempts <= 100");

    for(std::uint32_t attempt = 0; attempt < max_attempts; ++attempt) {
        auto frameset = impl_->pipeline->waitForFrameset(per_attempt_timeout_ms);
        if(!frameset) continue;
        auto color = frameset->getColorFrame();
        auto depth = frameset->getDepthFrame();
        if(!color || !depth || !color->getData() || !depth->getData()) continue;
        if(color->getFormat() != OB_FORMAT_MJPG || color->getWidth() != 1920 || color->getHeight() != 1080)
            throw std::runtime_error("Unexpected color format/resolution (expected 1920x1080 MJPG)");
        if(depth->getFormat() != OB_FORMAT_Y16 || depth->getWidth() != 1280 || depth->getHeight() != 800)
            throw std::runtime_error("Unexpected depth format/resolution (expected 1280x800 Y16)");

        // Retrieve calibration FROM THE ACTUAL FRAMES, never from hard-coded INI constants.
        const auto color_profile = color->getStreamProfile()->as<ob::VideoStreamProfile>();
        const auto depth_profile = depth->getStreamProfile()->as<ob::VideoStreamProfile>();
        RgbdCapture out;
        out.device = impl_->identity;
        out.color = copy_frame(std::static_pointer_cast<ob::VideoFrame>(color), PixelEncoding::Mjpeg);
        out.depth = copy_frame(std::static_pointer_cast<ob::VideoFrame>(depth), PixelEncoding::Y16);
        out.color_intrinsics = convert_intrinsics(color_profile->getIntrinsic());
        out.depth_intrinsics = convert_intrinsics(depth_profile->getIntrinsic());
        out.color_distortion = convert_distortion(color_profile->getDistortion());
        out.depth_distortion = convert_distortion(depth_profile->getDistortion());
        out.depth_to_color = convert_extrinsics(depth_profile->getExtrinsicTo(color_profile));
        out.depth_scale_m_per_unit = static_cast<double>(depth->getValueScale()) * 0.001; // SDK value in mm/unit.
        out.align_disabled = true;
        out.frame_sync_requested = true;

        std::string error;
        if(!validate_raw_capture(out, &error))
            throw std::runtime_error("Invalid RGB-D packet: " + error);
        return out; // Byte buffers remain valid after stop/destruction.
    }
    throw std::runtime_error("No complete RGB-D frameset received within bounded timeout");
}

void OrbbecCameraSource::close() {
    if(!is_open()) return;
    // Move out first, so camera is closed even if SDK stop throws.
    auto pipeline = std::move(impl_->pipeline);
    impl_->started = false;
    impl_->identity = {};
    pipeline->stop();
}
} // namespace scantopath::acquisition
