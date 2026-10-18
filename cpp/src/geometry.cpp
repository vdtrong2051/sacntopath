#include "scantopath/geometry.hpp"
#include <cmath>
#include <stdexcept>
namespace scantopath {
Point3 unproject(double u, double v, double z, const Intrinsics& K) {
    if (!(K.fx > 0 && K.fy > 0 && std::isfinite(z) && z > 0))
        throw std::invalid_argument("Invalid intrinsics or metric depth");
    return {(u-K.cx)*z/K.fx, (v-K.cy)*z/K.fy, z};
}
Point3 transform(const Point3& p, const std::array<double,16>& T) {
    return {T[0]*p[0]+T[1]*p[1]+T[2]*p[2]+T[3],
            T[4]*p[0]+T[5]*p[1]+T[6]*p[2]+T[7],
            T[8]*p[0]+T[9]*p[1]+T[10]*p[2]+T[11]};
}
}
