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
echo "Build complete."
echo ""
echo "To install x411_source.so to /usr/lib/sdrpp/plugins/ (one-time setup):"
echo "  sudo cp build-x411/source_modules/x411_source/x411_source.so /usr/lib/sdrpp/plugins/"
echo ""
echo "After install, SDR++ will auto-discover the plugin. Run with:"
echo "  sdrpp --root <root-dir>"
echo ""
echo "Or run directly from the build tree (no install needed):"
echo "  ./build-x411/sdrpp --root <root-dir>"
echo "  (requires absolute path in config.json 'modules' array)"
