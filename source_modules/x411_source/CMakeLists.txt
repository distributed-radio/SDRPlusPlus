cmake_minimum_required(VERSION 3.13)
project(x411_source)

file(GLOB SRC "src/*.cpp")

include(${SDRPP_MODULE_CMAKE})

# Use the patched UHD at /opt/uhd-x411/ — never link system UHD
set(UHD_X411_ROOT "/opt/uhd-x411")

target_include_directories(x411_source PRIVATE
    "${UHD_X411_ROOT}/include"
)

target_link_directories(x411_source PRIVATE
    "${UHD_X411_ROOT}/lib"
)

target_link_libraries(x411_source PRIVATE uhd)

# Bake RPATH so the .so always finds the patched libuhd at runtime
set_target_properties(x411_source PROPERTIES
    INSTALL_RPATH "${UHD_X411_ROOT}/lib"
    BUILD_RPATH   "${UHD_X411_ROOT}/lib"
)
