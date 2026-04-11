#!/usr/bin/env bash
# Build SDR++ with X411 support.
# Links x411_source against /opt/uhd-x411/ (patched UHD 4.4.0.x411).
# Output: build-x411/sdrpp + build-x411/source_modules/x411_source/x411_source.so
#
# Run: ./build-x411.sh
set -e
cd "$(dirname "$0")"
mkdir -p build-x411
cd build-x411
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DOPT_BUILD_X411_SOURCE=ON \
    -DOPT_BUILD_USRP_SOURCE=ON \
    -DOPT_BUILD_BLADERF_SOURCE=ON \
    -DOPT_BUILD_RTL_SDR_SOURCE=ON \
    -DOPT_BUILD_AUDIO_SINK=ON \
    -DOPT_BUILD_FILE_SOURCE=ON
make -j"$(nproc)"
echo ""
echo "Build complete. Run with:"
echo "  ./build-x411/sdrpp --root <root-dir>"
