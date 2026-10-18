cmake_minimum_required(VERSION 3.22)
project(ScanToPathCore VERSION 0.1.0 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_library(scantopath_core STATIC src/geometry.cpp)
target_include_directories(scantopath_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
include(CTest)
if(BUILD_TESTING)
  add_executable(scantopath_core_smoke tests/smoke.cpp)
  target_link_libraries(scantopath_core_smoke PRIVATE scantopath_core)
  add_test(NAME core_smoke COMMAND scantopath_core_smoke)
endif()

# GÄ1.2.3.1 - opt-in Gemini 2 SDK C++ probe
option(SCANTOPATH_BUILD_ORBBEC_PROBE "Build Gemini 2 diagnostic" OFF)
if(SCANTOPATH_BUILD_ORBBEC_PROBE)
  find_package(OrbbecSDK CONFIG REQUIRED)
  if(NOT TARGET ob::OrbbecSDK)
    message(FATAL_ERROR "OrbbecSDK package missing target ob::OrbbecSDK")
  endif()
  add_executable(scantopath_orbbec_probe tools/orbbec_probe.cpp)
  target_link_libraries(scantopath_orbbec_probe PRIVATE ob::OrbbecSDK)
endif()

# GĐ1.2.3.2.1: vendor-neutral RGB-D packet contract (no hardware dependency).
add_library(scantopath_rgbd_contract STATIC src/acquisition/rgbd_validation.cpp)
target_include_directories(scantopath_rgbd_contract PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
if(BUILD_TESTING)
  add_executable(scantopath_rgbd_contract_smoke tests/rgbd_packet_contract.cpp)
  target_link_libraries(scantopath_rgbd_contract_smoke PRIVATE scantopath_rgbd_contract)
  add_test(NAME rgbd_contract_smoke COMMAND scantopath_rgbd_contract_smoke)
endif()

# GĐ1.2.3.2.1: optional Orbbec-specific CameraSource, OFF by default.
option(SCANTOPATH_BUILD_ORBBEC_SOURCE "Build Orbbec Gemini 2 CameraSource" OFF)
if(SCANTOPATH_BUILD_ORBBEC_SOURCE)
  find_package(OrbbecSDK CONFIG REQUIRED)
  if(NOT TARGET ob::OrbbecSDK)
    message(FATAL_ERROR "OrbbecSDK package missing target ob::OrbbecSDK")
  endif()
  add_library(scantopath_orbbec_source STATIC src/acquisition/orbbec_camera_source.cpp)
  target_include_directories(scantopath_orbbec_source PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
  target_link_libraries(scantopath_orbbec_source PUBLIC scantopath_rgbd_contract PRIVATE ob::OrbbecSDK)
  add_executable(scantopath_orbbec_source_smoke tools/orbbec_source_smoke.cpp)
  target_link_libraries(scantopath_orbbec_source_smoke PRIVATE scantopath_orbbec_source)
  # Do not register the camera-dependent smoke as a mandatory CTest.
  # Run it manually once OrbbecViewer has been closed.
endif()

# GĐ1.2.3.2.2: optional pybind11 extension; OFF unless explicitly enabled.
option(SCANTOPATH_BUILD_PYTHON_BINDINGS "Build Gemini 2 pybind11 native Python module" OFF)
if(SCANTOPATH_BUILD_PYTHON_BINDINGS)
  if(NOT SCANTOPATH_BUILD_ORBBEC_SOURCE)
    message(FATAL_ERROR "Python bindings require SCANTOPATH_BUILD_ORBBEC_SOURCE=ON")
  endif()

  # Explicitly bind to the interpreter selected by -DPython3_EXECUTABLE=...
  find_package(Python3 3.12 COMPONENTS Interpreter Development.Module REQUIRED)
  set(PYBIND11_FINDPYTHON ON)
  find_package(pybind11 CONFIG REQUIRED)

  set_target_properties(scantopath_rgbd_contract scantopath_orbbec_source
    PROPERTIES POSITION_INDEPENDENT_CODE ON)
  pybind11_add_module(_scantopath_native MODULE NO_EXTRAS python/orbbec_bindings.cpp)
  if(MSVC)
      target_compile_definitions(
          _scantopath_native
          PRIVATE _DISABLE_CONSTEXPR_MUTEX_CONSTRUCTOR
      )
  endif()
  target_link_libraries(_scantopath_native PRIVATE scantopath_orbbec_source)
  target_include_directories(_scantopath_native PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)

  # Editable Python project: import from src/scantopath without manual .pyd copy.
  get_filename_component(_scan_package_dir "${CMAKE_CURRENT_SOURCE_DIR}/../src/scantopath" ABSOLUTE)
  foreach(_config "DEBUG" "RELEASE" "RELWITHDEBINFO" "MINSIZEREL")
    set_target_properties(_scantopath_native PROPERTIES
      "LIBRARY_OUTPUT_DIRECTORY_${_config}" "${_scan_package_dir}"
      "RUNTIME_OUTPUT_DIRECTORY_${_config}" "${_scan_package_dir}")
  endforeach()
  set_target_properties(_scantopath_native PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${_scan_package_dir}"
    RUNTIME_OUTPUT_DIRECTORY "${_scan_package_dir}")

  if(BUILD_TESTING)
    target_compile_definitions(_scantopath_native PRIVATE SCANTOPATH_BINDING_SELF_TESTS=1)
  endif()
endif()
