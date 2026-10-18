#pragma once
#include <array>
#include <cstdint>
namespace scantopath {
struct Intrinsics {
    double fx, fy, cx, cy;
};
using Point3 = std::array<double,3>;
// Pixels are in DEPTH optical coordinates; depth provided in meters.
Point3 unproject(double u, double v, double depth_m, const Intrinsics& K);
Point3 transform(const Point3& p, const std::array<double,16>& row_major_T);
}
