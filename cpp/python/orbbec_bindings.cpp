// ScanToPath GD1.2.3.2.2 - Python binding for already-tested native acquisition.
// This module does NOT start the camera at import time.
#include "scantopath/acquisition/orbbec_camera_source.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <bit>
#include <cstring>
#include <stdexcept>
#include <string>

namespace py = pybind11;
namespace acq = scantopath::acquisition;

namespace {
py::bytes owned_python_bytes(const acq::FrameData &frame) {
    // py::bytes copies from C++ storage; never exposes an OrbbecSDK frame pointer.
    return py::bytes(reinterpret_cast<const char *>(frame.bytes.data()),
                     static_cast<py::ssize_t>(frame.bytes.size()));
}

py::array_t<std::uint16_t> owned_depth_array(const acq::FrameData &depth) {
    if(depth.encoding != acq::PixelEncoding::Y16)
        throw std::invalid_argument("Depth frame is not Y16");
    if(std::endian::native != std::endian::little)
        throw std::runtime_error("Native Y16 converter requires little-endian host");
    const auto expected = static_cast<std::uint64_t>(depth.width) * depth.height * sizeof(std::uint16_t);
    if(!depth.width || !depth.height || expected != depth.bytes.size())
        throw std::invalid_argument("Invalid depth Y16 byte count");
    // py::array_t creates an OWNED NumPy allocation. No dangling native pointers.
    py::array_t<std::uint16_t> out({static_cast<py::ssize_t>(depth.height),
                                    static_cast<py::ssize_t>(depth.width)});
    std::memcpy(out.mutable_data(), depth.bytes.data(), depth.bytes.size());
    return out;
}
} // namespace

PYBIND11_MODULE(_scantopath_native, m) {
    m.doc() = "ScanToPath native Gemini 2 acquisition (RAW MJPG + Y16; no storage/UI)";
    m.attr("binding_stage") = "GD1.2.3.2.2";

    py::enum_<acq::PixelEncoding>(m, "PixelEncoding")
        .value("MJPEG", acq::PixelEncoding::Mjpeg)
        .value("Y16", acq::PixelEncoding::Y16);

    py::class_<acq::DeviceIdentity>(m, "DeviceIdentity")
        .def_readonly("name", &acq::DeviceIdentity::name)
        .def_readonly("firmware", &acq::DeviceIdentity::firmware)
        .def_readonly("usb_connection", &acq::DeviceIdentity::usb_connection)
        .def_readonly("pid", &acq::DeviceIdentity::pid);

    py::class_<acq::CameraIntrinsics>(m, "CameraIntrinsics")
        .def_readonly("width", &acq::CameraIntrinsics::width)
        .def_readonly("height", &acq::CameraIntrinsics::height)
        .def_readonly("fx", &acq::CameraIntrinsics::fx)
        .def_readonly("fy", &acq::CameraIntrinsics::fy)
        .def_readonly("cx", &acq::CameraIntrinsics::cx)
        .def_readonly("cy", &acq::CameraIntrinsics::cy);

    py::class_<acq::DistortionCoefficients>(m, "DistortionCoefficients")
        .def_readonly("sdk_model", &acq::DistortionCoefficients::sdk_model)
        .def_readonly("k1_k6_p1_p2", &acq::DistortionCoefficients::k1_k6_p1_p2);

    py::class_<acq::DepthToColorExtrinsics>(m, "DepthToColorExtrinsics")
        .def_readonly("rotation", &acq::DepthToColorExtrinsics::rotation)
        .def_readonly("translation_mm", &acq::DepthToColorExtrinsics::translation_mm);

    py::class_<acq::FrameData>(m, "FrameData")
        .def_readonly("encoding", &acq::FrameData::encoding)
        .def_readonly("width", &acq::FrameData::width)
        .def_readonly("height", &acq::FrameData::height)
        .def_readonly("frame_index", &acq::FrameData::frame_index)
        .def_readonly("timestamp_us", &acq::FrameData::timestamp_us)
        .def_property_readonly("bytes", &owned_python_bytes)
        .def("as_depth_u16", &owned_depth_array,
             "Return an OWNED NumPy uint16[height,width] copy of a Y16 frame");

    py::class_<acq::RgbdCapture>(m, "RgbdCapture")
        .def_readonly("device", &acq::RgbdCapture::device)
        .def_readonly("color", &acq::RgbdCapture::color)
        .def_readonly("depth", &acq::RgbdCapture::depth)
        .def_readonly("color_intrinsics", &acq::RgbdCapture::color_intrinsics)
        .def_readonly("depth_intrinsics", &acq::RgbdCapture::depth_intrinsics)
        .def_readonly("color_distortion", &acq::RgbdCapture::color_distortion)
        .def_readonly("depth_distortion", &acq::RgbdCapture::depth_distortion)
        .def_readonly("depth_to_color", &acq::RgbdCapture::depth_to_color)
        .def_readonly("depth_scale_m_per_unit", &acq::RgbdCapture::depth_scale_m_per_unit)
        .def_readonly("align_disabled", &acq::RgbdCapture::align_disabled)
        .def_readonly("frame_sync_requested", &acq::RgbdCapture::frame_sync_requested)
        .def("timestamp_delta_us", &acq::RgbdCapture::timestamp_delta_us)
        .def("depth_u16", [](const acq::RgbdCapture &cap) {
            return owned_depth_array(cap.depth);
        }, "Return an independently owned NumPy Y16 array")
        .def("validate", [](const acq::RgbdCapture &cap) {
            std::string error;
            if(!acq::validate_raw_capture(cap, &error))
                throw std::runtime_error("RGB-D contract failed: " + error);
            return true;
        });

    py::class_<acq::OrbbecCameraSource>(m, "OrbbecCameraSource")
        .def(py::init<>())
        .def("open", &acq::OrbbecCameraSource::open,
             py::call_guard<py::gil_scoped_release>(), "Start native RAW Gemini 2 stream")
        .def("is_open", &acq::OrbbecCameraSource::is_open)
        .def("device", &acq::OrbbecCameraSource::device)
        .def("read_next", &acq::OrbbecCameraSource::read_next,
             py::arg("per_attempt_timeout_ms") = 1000,
             py::arg("max_attempts") = 10,
             py::call_guard<py::gil_scoped_release>(),
             "Block until a complete RAW RGB-D pair arrives (bounded retries)")
        .def("close", &acq::OrbbecCameraSource::close,
             py::call_guard<py::gil_scoped_release>());

#ifdef SCANTOPATH_BINDING_SELF_TESTS
    // Clearly isolated diagnostic: synthetic data; NOT a measurement or camera capture.
    m.def("_test_copy_y16", []() {
        acq::FrameData synthetic;
        synthetic.encoding = acq::PixelEncoding::Y16;
        synthetic.width = 3;
        synthetic.height = 2;
        synthetic.bytes = {1, 0, 2, 0, 3, 0, 255, 255, 0, 1, 0, 0};
        return owned_depth_array(synthetic); // synthetic storage dies on return.
    });
#endif
}
