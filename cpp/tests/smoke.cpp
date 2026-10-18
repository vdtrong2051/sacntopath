#include "scantopath/geometry.hpp"
#include <cassert>
#include <cmath>
#include <iostream>
int main() {
    using namespace scantopath;
    Intrinsics k{400,400,320,240};
    auto p=unproject(320,240,1.25,k);
    assert(std::abs(p[0])<1.e-10 && std::abs(p[1])<1.e-10 && std::abs(p[2]-1.25)<1.e-10);
    std::array<double,16> T={1,0,0,0.1, 0,1,0,0, 0,0,1,0, 0,0,0,1};
    auto q=transform(p,T);
    assert(std::abs(q[0]-0.1)<1.e-10 && std::abs(q[2]-1.25)<1.e-10);
    bool rejected=false;
    try { unproject(0,0,0,k); } catch(const std::invalid_argument&) {rejected=true;}
    assert(rejected);
    std::cout << "ScanToPath Core 0.1.0 — metric geometry smoke OK\n";
}
