# X411 Source Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `x411_source` SDR++ plugin that streams IQ samples from the ZCU111/X411 via the patched UHD at `/opt/uhd-x411/`, with X411-specific UI (static sample rates, NCO-aware tuning, subdev selection, no gain/bandwidth controls).

**Architecture:** A new `source_modules/x411_source/` module sits alongside `usrp_source` and is built only when `-DOPT_BUILD_X411_SOURCE=ON`. It links exclusively against `/opt/uhd-x411/` via RPATH so it never loads system UHD. Device args (mgmt_addr, addr, num_recv_frames, recv_buff_size) live in `x411_config.json` with sensible defaults. Tuning uses NCO-only (`rf_freq_policy=MANUAL`) within ±128.75 MHz of the current LO; larger hops stop the stream, retune the PLL, and restart.

**Tech Stack:** C++17, UHD 4.4.0.x411 (`/opt/uhd-x411/`), CMake 3.13+, SDR++ module API (ImGui/SmGui), nlohmann/json (via SDR++ core)

---

## Scope note

This plan covers two independent deliverables that should be built in order:

1. **Task 1–2:** Base SDR++ build (`build/`) with USRP, BladeRF, RTL-SDR, PulseAudio support — proves the build system works before touching X411.
2. **Tasks 3–10:** `x411_source` module and `build-x411/` — the actual feature.

Run the three Python prototypes (Tasks 3–5) before writing any C++ — their output directly informs implementation decisions.

---

## Pre-requisite: Python prototype environment

Before any task, verify prototypes can run:

```bash
source /opt/uhd-x411/setup_env.sh
python3 --version   # expect 3.12
python3 -c "import uhd; print(uhd.__version__)"   # expect 4.4.0.x411
```

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `CMakeLists.txt` | Modify | Add `OPT_BUILD_X411_SOURCE` option and `add_subdirectory` |
| `source_modules/x411_source/CMakeLists.txt` | Create | Build x411_source.so against `/opt/uhd-x411/`, set RPATH |
| `source_modules/x411_source/src/main.cpp` | Create | Full module implementation |
| `source_modules/x411_source/proto/capability_probe.py` | Already exists | Run before implementing |
| `source_modules/x411_source/proto/query_rates.py` | Already exists | Run before implementing |
| `source_modules/x411_source/proto/retune_test.py` | Already exists | Run before implementing |

---

## Task 1: Base SDR++ build (`build/`)

Install dependencies and confirm a working baseline build with the modules needed for day-to-day use. This build uses system UHD.

**Files:**
- No source changes — build system only

- [ ] **Step 1: Install build dependencies**

```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential cmake git pkg-config \
    libfftw3-dev libglfw3-dev libgl1-mesa-dev \
    libpulse-dev \
    libuhd-dev \
    libbladerf-dev \
    librtlsdr-dev \
    libasound2-dev
```

Expected: no errors. If `libuhd-dev` conflicts with `/opt/uhd-x411/`, that is fine — they install to different prefixes.

- [ ] **Step 2: Create build directory and configure**

```bash
cd /home/steve/git/sdrplusplus
mkdir -p build && cd build
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DOPT_BUILD_USRP_SOURCE=ON \
    -DOPT_BUILD_BLADERF_SOURCE=ON \
    -DOPT_BUILD_RTL_SDR_SOURCE=ON \
    -DOPT_BUILD_AUDIO_SINK=ON \
    -DOPT_BUILD_FILE_SOURCE=ON
```

Expected: `-- Configuring done` and `-- Build files have been written to: .../build`

If any `find_package` fails, install the missing package and re-run cmake.

- [ ] **Step 3: Build**

```bash
make -j$(nproc) 2>&1 | tee /tmp/sdrpp_build.log
echo "Exit: $?"
```

Expected: `[100%] Built target sdrpp` and exit code 0. Check `/tmp/sdrpp_build.log` for errors if it fails.

- [ ] **Step 4: Smoke-test the binary**

```bash
./sdrpp --help 2>&1 | head -5
```

Expected: usage/version output, no crash.

- [ ] **Step 5: Commit**

```bash
cd /home/steve/git/sdrplusplus
git add -A  # only if any files changed; likely nothing
git status  # confirm clean or only build artifacts
```

No commit needed if no source files changed — build directory is gitignored.

---

## Task 2: Add `OPT_BUILD_X411_SOURCE` option to top-level CMakeLists

Wire the new module into the build system before writing any module code.

**Files:**
- Modify: `CMakeLists.txt` (lines 39–41 area, after `OPT_BUILD_USRP_SOURCE`)

- [ ] **Step 1: Add the option declaration**

In `CMakeLists.txt`, after line 39 (`option(OPT_BUILD_USRP_SOURCE ...)`), add:

```cmake
option(OPT_BUILD_X411_SOURCE "Build X411 Source Module (requires /opt/uhd-x411/)" OFF)
```

- [ ] **Step 2: Add the conditional subdirectory**

After the existing USRP block (around line 241):

```cmake
if (OPT_BUILD_X411_SOURCE)
add_subdirectory("source_modules/x411_source")
endif (OPT_BUILD_X411_SOURCE)
```

- [ ] **Step 3: Create the module directory**

```bash
mkdir -p /home/steve/git/sdrplusplus/source_modules/x411_source/src
```

- [ ] **Step 4: Create a stub CMakeLists to prove wiring**

Create `source_modules/x411_source/CMakeLists.txt`:

```cmake
cmake_minimum_required(VERSION 3.13)
project(x411_source)

message(STATUS "X411 source: stub (not yet implemented)")
```

- [ ] **Step 5: Verify cmake accepts the option without errors**

```bash
cd /home/steve/git/sdrplusplus/build
cmake .. -DOPT_BUILD_X411_SOURCE=ON 2>&1 | grep -E "X411|error|Error"
```

Expected: `X411 source: stub (not yet implemented)` — no errors.

- [ ] **Step 6: Commit**

```bash
cd /home/steve/git/sdrplusplus
git add CMakeLists.txt source_modules/x411_source/CMakeLists.txt
git commit -m "build: add OPT_BUILD_X411_SOURCE cmake option (stub)"
```

---

## Task 3: Run `capability_probe.py` — understand UHD API responses

**Do not skip this task.** The results determine which UHD calls to use in the C++ module.

**Files:** `source_modules/x411_source/proto/capability_probe.py` (already written)

- [ ] **Step 1: Power on X411 and wait for boot**

```bash
python3 ~/git/srs-iq/tools/x411_power.py on
# Wait for "ready" message (~90 seconds)
ping -c 3 192.168.7.162
```

- [ ] **Step 2: Run the probe**

```bash
source /opt/uhd-x411/setup_env.sh
cd /home/steve/git/sdrplusplus
python3 source_modules/x411_source/proto/capability_probe.py 2>&1 | tee /tmp/capability_probe.txt
cat /tmp/capability_probe.txt
```

- [ ] **Step 3: Record findings — update this plan**

After running, fill in the following table with actual values:

| API | Returns |
|-----|---------|
| `get_rx_freq_range()` | TBD — fill from output |
| `get_rx_rates()` | TBD — continuous range or discrete? |
| `get_rx_bandwidth_range()` | TBD |
| `get_rx_gain_range()` | TBD — expect 0–0 (no gain) |
| `get_rx_gain_names()` | TBD |
| `get_rx_agc_supported()` | TBD — expect False |
| `get_rx_antennas()` | TBD — expect ["RX2"] or similar |
| `get_clock_sources()` | TBD — expect ["internal"] |
| `get_mboard_sensor_names()` | TBD |
| `uhd.find_devices()` with mgmt_addr hint | TBD — does it return the device? |

Key question: if `get_rx_gain_range()` returns 0–0, we can confirm no gain slider is needed. If it returns a non-zero range, investigate before hiding the widget.

---

## Task 4: Run `query_rates.py` — confirm sample rate enumeration

**Files:** `source_modules/x411_source/proto/query_rates.py` (already written)

- [ ] **Step 1: Run**

```bash
source /opt/uhd-x411/setup_env.sh
python3 source_modules/x411_source/proto/query_rates.py 2>&1 | tee /tmp/query_rates.txt
cat /tmp/query_rates.txt
```

- [ ] **Step 2: Confirm hardcoded list is correct**

Expected: UHD returns a continuous range (e.g. `start=0.96 stop=245.76 step=0.0`), confirming that dynamic enumeration would flood the UI. Our hardcoded list of 9 rates is the correct approach.

If UHD returns discrete rates instead, update `VALID_SAMPLE_RATES` in Task 6 accordingly.

The 9 rates to hardcode (unless probe shows otherwise):

```
245.76, 122.88, 61.44, 30.72, 15.36, 7.68, 3.84, 1.92, 0.96  (all in Msps)
```

---

## Task 5: Run `retune_test.py` — confirm LO retune strategy

**Files:** `source_modules/x411_source/proto/retune_test.py` (already written)

- [ ] **Step 1: Run**

```bash
source /opt/uhd-x411/setup_env.sh
python3 source_modules/x411_source/proto/retune_test.py 2>&1 | tee /tmp/retune_test.txt
cat /tmp/retune_test.txt
```

- [ ] **Step 2: Evaluate results and update plan**

Three questions from the output:

**Q1: NCO-only retune time** — expect <1 ms. If >10 ms, something is wrong with the tune_request policy.

**Q2: Hot PLL retune** — if pre/post RMS are similar and no UHD exception is thrown, hot retune may be viable. If UHD throws or RMS spikes badly, confirm stop/restart is required.

**Q3: Stop/restart PLL retune time** — expect 100–300 ms. This is the gap users will see on large frequency hops.

If hot retune is safe (Q2), update the `tune()` implementation in Task 8 to use hot retune instead of stop/restart. Default plan assumes stop/restart.

- [ ] **Step 3: Commit prototype results**

```bash
cd /home/steve/git/sdrplusplus
git add source_modules/x411_source/proto/
git commit -m "proto: add X411 capability and retune prototype scripts"
```

---

## Task 6: Write the x411_source CMakeLists

The real CMakeLists — replaces the stub. Links against `/opt/uhd-x411/`, sets RPATH.

**Files:**
- Modify: `source_modules/x411_source/CMakeLists.txt`

- [ ] **Step 1: Write the CMakeLists**

Replace the stub with:

```cmake
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

# Bake RPATH so the .so always finds the patched libuhd at runtime,
# regardless of LD_LIBRARY_PATH or system UHD installation.
set_target_properties(x411_source PROPERTIES
    INSTALL_RPATH "${UHD_X411_ROOT}/lib"
    BUILD_RPATH   "${UHD_X411_ROOT}/lib"
)
```

- [ ] **Step 2: Create an empty src/main.cpp so cmake can build**

```cpp
// x411_source stub — implementation follows in Task 7
```

- [ ] **Step 3: Configure and build to verify linkage**

```bash
cd /home/steve/git/sdrplusplus
mkdir -p build-x411 && cd build-x411
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DOPT_BUILD_X411_SOURCE=ON \
    -DOPT_BUILD_USRP_SOURCE=ON \
    -DOPT_BUILD_BLADERF_SOURCE=ON \
    -DOPT_BUILD_RTL_SDR_SOURCE=ON \
    -DOPT_BUILD_AUDIO_SINK=ON \
    -DOPT_BUILD_FILE_SOURCE=ON
make x411_source 2>&1 | tail -5
```

Expected: builds successfully (empty .so). Confirm correct UHD is linked:

```bash
ldd source_modules/x411_source/x411_source.so | grep uhd
```

Expected: `libuhd.so => /opt/uhd-x411/lib/libuhd.so`

If it points to `/usr/lib/...` instead, the RPATH is not set correctly — re-check CMakeLists.

- [ ] **Step 4: Commit**

```bash
cd /home/steve/git/sdrplusplus
git add source_modules/x411_source/CMakeLists.txt source_modules/x411_source/src/main.cpp
git commit -m "build: x411_source CMakeLists with RPATH to /opt/uhd-x411"
```

---

## Task 7: Implement module scaffold and config

The module skeleton: registers with SDR++, loads/saves config, shows address fields in UI, Refresh button triggers a timed connection attempt.

**Files:**
- Modify: `source_modules/x411_source/src/main.cpp`

- [ ] **Step 1: Write the full scaffold**

```cpp
#include <utils/flog.h>
#include <module.h>
#include <gui/gui.h>
#include <signal_path/signal_path.h>
#include <core.h>
#include <gui/style.h>
#include <config.h>
#include <gui/smgui.h>
#include <utils/optionlist.h>
#include <uhd/usrp/multi_usrp.hpp>
#include <uhd/device.hpp>
#include <thread>
#include <atomic>
#include <cstring>

#define CONCAT(a, b) ((std::string(a) + b).c_str())

SDRPP_MOD_INFO{
    /* Name:        */ "x411_source",
    /* Description: */ "X411 RFSoC source module for SDR++",
    /* Author:      */ "",
    /* Version:     */ 0, 1, 0,
    /* Max instances*/ 1
};

ConfigManager config;

// Valid sample rates: integer decimations of 245.76 MHz MCR
static const double VALID_RATES[] = {
    245.76e6, 122.88e6, 61.44e6, 30.72e6,
     15.36e6,   7.68e6,  3.84e6,  1.92e6,  0.96e6
};
static const int N_RATES = sizeof(VALID_RATES) / sizeof(VALID_RATES[0]);
static const double NCO_RANGE = 128.75e6;  // Max DDC offset from LO

// Subdev specs — static list, dead channels excluded from UI
struct SubdevEntry { const char* label; const char* spec; bool useSecondAddr; };
static const SubdevEntry SUBDEVS[] = {
    { "A:0 (J4)", "A:0", false },
    { "A:1 (J3)", "A:1", false },
    { "B:0 (J33)", "B:0", true  },
    { "B:1 (J34)", "B:1", true  },
};
static const int N_SUBDEVS = sizeof(SUBDEVS) / sizeof(SUBDEVS[0]);

class X411SourceModule : public ModuleManager::Instance {
public:
    X411SourceModule(std::string name) : name(name) {
        handler.ctx            = this;
        handler.selectHandler  = menuSelected;
        handler.deselectHandler= menuDeselected;
        handler.menuHandler    = menuHandler;
        handler.startHandler   = start;
        handler.stopHandler    = stop;
        handler.tuneHandler    = tune;
        handler.stream         = &stream;

        // Build sample rate option list
        for (int i = 0; i < N_RATES; i++) {
            char buf[32];
            snprintf(buf, sizeof(buf), "%.2f Msps", VALID_RATES[i] / 1e6);
            samplerates.define((int)(VALID_RATES[i]), buf, VALID_RATES[i]);
        }

        // Build subdev option list
        for (int i = 0; i < N_SUBDEVS; i++) {
            subdevs.define(i, SUBDEVS[i].label, i);
        }

        sigpath::sourceManager.registerSource("X411", &handler);
    }

    ~X411SourceModule() {
        stop(this);
        sigpath::sourceManager.unregisterSource("X411");
    }

    void postInit() {}
    void enable()  { enabled = true; }
    void disable() { enabled = false; }
    bool isEnabled() { return enabled; }

private:
    // ── Helpers ──────────────────────────────────────────────────────────────

    std::string buildDeviceArgs() {
        std::string args = "mgmt_addr=" + mgmtAddr
                         + ",addr=" + dataAddr
                         + ",type=x4xx"
                         + ",num_recv_frames=" + std::to_string(numRecvFrames)
                         + ",recv_buff_size=" + std::to_string(recvBufSize);
        if (SUBDEVS[subdevId].useSecondAddr && !secondAddr.empty()) {
            args += ",second_addr=" + secondAddr;
        }
        return args;
    }

    // Attempt connection with a 3-second timeout. Returns nullptr on failure.
    uhd::usrp::multi_usrp::sptr tryConnect() {
        try {
            uhd::device_addr_t args(buildDeviceArgs() + ",timeout=3");
            return uhd::usrp::multi_usrp::make(args);
        } catch (const std::exception& e) {
            flog::warn("X411: connection failed: {}", e.what());
            return nullptr;
        }
    }

    // ── SDR++ callbacks ──────────────────────────────────────────────────────

    static void menuSelected(void* ctx) {
        X411SourceModule* _this = (X411SourceModule*)ctx;
        core::setInputSampleRate(_this->sampleRate);
        flog::info("X411SourceModule '{}': Menu Select", _this->name);
    }

    static void menuDeselected(void* ctx) {
        flog::info("X411SourceModule '{}': Menu Deselect", ((X411SourceModule*)ctx)->name);
    }

    static void start(void* ctx) {
        X411SourceModule* _this = (X411SourceModule*)ctx;
        if (_this->running) return;

        _this->dev = _this->tryConnect();
        if (!_this->dev) {
            flog::error("X411: failed to connect at start");
            return;
        }

        _this->applySettings();
        _this->startStream();

        _this->running = true;
        flog::info("X411SourceModule '{}': Start", _this->name);
    }

    static void stop(void* ctx) {
        X411SourceModule* _this = (X411SourceModule*)ctx;
        if (!_this->running) return;
        _this->running = false;

        _this->stopStream();
        _this->dev.reset();
        flog::info("X411SourceModule '{}': Stop", _this->name);
    }

    static void tune(double freq, void* ctx) {
        X411SourceModule* _this = (X411SourceModule*)ctx;
        _this->freq = freq;
        if (!_this->running) return;

        double delta = freq - _this->rfLo;
        if (std::fabs(delta) <= NCO_RANGE) {
            // NCO-only retune — instantaneous, no stream interruption
            uhd::tune_request_t tr(freq);
            tr.rf_freq         = _this->rfLo;
            tr.rf_freq_policy  = uhd::tune_request_t::POLICY_MANUAL;
            tr.dsp_freq_policy = uhd::tune_request_t::POLICY_AUTO;
            _this->dev->set_rx_freq(tr, 0);
        } else {
            // PLL retune — stop stream, retune, restart
            _this->stopStream();
            uhd::tune_result_t result = _this->dev->set_rx_freq(freq, 0);
            _this->rfLo = result.actual_rf_freq;
            _this->startStream();
        }
        flog::info("X411SourceModule '{}': Tune {:.3f} MHz (LO {:.3f} MHz)",
                   _this->name, freq / 1e6, _this->rfLo / 1e6);
    }

    // ── Stream control ────────────────────────────────────────────────────────

    void applySettings() {
        dev->set_rx_subdev_spec(uhd::usrp::subdev_spec_t(SUBDEVS[subdevId].spec), 0);
        dev->set_rx_rate(sampleRate, 0);
        dev->set_clock_source("internal");

        uhd::tune_result_t result = dev->set_rx_freq(freq, 0);
        rfLo = result.actual_rf_freq;
    }

    void startStream() {
        uhd::stream_args_t sargs;
        sargs.channels    = {0};
        sargs.cpu_format  = "fc32";
        sargs.otw_format  = "sc16";
        streamer = dev->get_rx_stream(sargs);
        streamer->issue_stream_cmd(uhd::stream_cmd_t::STREAM_MODE_START_CONTINUOUS);

        stream.clearWriteStop();
        workerThread = std::thread(&X411SourceModule::worker, this);
    }

    void stopStream() {
        stream.stopWriter();
        if (streamer) {
            streamer->issue_stream_cmd(uhd::stream_cmd_t::STREAM_MODE_STOP_CONTINUOUS);
        }
        if (workerThread.joinable()) workerThread.join();
        stream.clearWriteStop();
        streamer.reset();
    }

    void worker() {
        int bufSize = (int)(sampleRate / 200);  // 5ms chunks
        uhd::rx_metadata_t meta;
        try {
            while (true) {
                int len = streamer->recv(stream.writeBuf, bufSize, meta, 1.0);
                if (len <= 0) break;
                if (!stream.swap(len)) break;
            }
        } catch (const std::exception& e) {
            flog::error("X411: recv error: {}", e.what());
        }
    }

    // ── Menu UI ───────────────────────────────────────────────────────────────

    static void menuHandler(void* ctx) {
        X411SourceModule* _this = (X411SourceModule*)ctx;

        // Address fields — only when stopped
        if (_this->running) SmGui::BeginDisabled();

        SmGui::LeftLabel("Mgmt addr");
        SmGui::FillWidth();
        if (SmGui::InputText(CONCAT("##x411_mgmt_", _this->name),
                             _this->mgmtAddrBuf, sizeof(_this->mgmtAddrBuf))) {
            _this->mgmtAddr = _this->mgmtAddrBuf;
            config.acquire();
            config.conf["mgmt_addr"] = _this->mgmtAddr;
            config.release(true);
        }

        SmGui::LeftLabel("Data addr");
        SmGui::FillWidth();
        if (SmGui::InputText(CONCAT("##x411_addr_", _this->name),
                             _this->dataAddrBuf, sizeof(_this->dataAddrBuf))) {
            _this->dataAddr = _this->dataAddrBuf;
            config.acquire();
            config.conf["addr"] = _this->dataAddr;
            config.release(true);
        }

        SmGui::LeftLabel("Second addr");
        SmGui::FillWidth();
        if (SmGui::InputText(CONCAT("##x411_addr2_", _this->name),
                             _this->secondAddrBuf, sizeof(_this->secondAddrBuf))) {
            _this->secondAddr = _this->secondAddrBuf;
            config.acquire();
            config.conf["second_addr"] = _this->secondAddr;
            config.release(true);
        }

        SmGui::FillWidth();
        SmGui::ForceSync();
        if (SmGui::Button(CONCAT("Refresh##x411_", _this->name))) {
            auto probe = _this->tryConnect();
            _this->deviceFound = (probe != nullptr);
        }
        SmGui::SameLine();
        SmGui::Text(_this->deviceFound ? "Device OK" : "Device not found");

        // Sample rate
        SmGui::FillWidth();
        SmGui::ForceSync();
        if (SmGui::Combo(CONCAT("##x411_sr_", _this->name),
                         &_this->srId, _this->samplerates.txt)) {
            _this->sampleRate = _this->samplerates[_this->srId];
            core::setInputSampleRate(_this->sampleRate);
            config.acquire();
            config.conf["samplerate"] = _this->samplerates.key(_this->srId);
            config.release(true);
        }

        // Subdev
        SmGui::LeftLabel("Channel");
        SmGui::FillWidth();
        SmGui::ForceSync();
        if (SmGui::Combo(CONCAT("##x411_ch_", _this->name),
                         &_this->subdevId, _this->subdevs.txt)) {
            config.acquire();
            config.conf["subdev"] = _this->subdevId;
            config.release(true);
        }

        if (_this->running) SmGui::EndDisabled();
    }

    // ── Members ───────────────────────────────────────────────────────────────

    std::string name;
    bool enabled    = true;
    bool running    = false;
    bool deviceFound= false;
    double freq     = 100e6;
    double sampleRate = 30.72e6;
    double rfLo     = 0.0;
    int srId        = 3;   // Default: 30.72 Msps (index 3 in VALID_RATES)
    int subdevId    = 0;   // Default: A:0 (J4)

    std::string mgmtAddr   = "192.168.7.162";
    std::string dataAddr   = "192.168.200.2";
    std::string secondAddr = "192.168.201.2";
    int numRecvFrames = 2048;
    int recvBufSize   = 33554432;

    char mgmtAddrBuf[64]   = "192.168.7.162";
    char dataAddrBuf[64]   = "192.168.200.2";
    char secondAddrBuf[64] = "192.168.201.2";

    dsp::stream<dsp::complex_t> stream;
    SourceManager::SourceHandler handler;
    uhd::usrp::multi_usrp::sptr dev;
    uhd::rx_streamer::sptr streamer;
    std::thread workerThread;

    OptionList<int, double>      samplerates;
    OptionList<int, int>         subdevs;
};

MOD_EXPORT void _INIT_() {
    json def = json::object();
    def["mgmt_addr"]       = "192.168.7.162";
    def["addr"]            = "192.168.200.2";
    def["second_addr"]     = "192.168.201.2";
    def["num_recv_frames"] = 2048;
    def["recv_buff_size"]  = 33554432;
    def["samplerate"]      = (int)(30.72e6);
    def["subdev"]          = 0;

    config.setPath(core::args["root"].s() + "/x411_config.json");
    config.load(def);
    config.enableAutoSave();
}

MOD_EXPORT ModuleManager::Instance* _CREATE_INSTANCE_(std::string name) {
    return new X411SourceModule(name);
}

MOD_EXPORT void _DELETE_INSTANCE_(ModuleManager::Instance* instance) {
    delete (X411SourceModule*)instance;
}

MOD_EXPORT void _END_() {
    config.disableAutoSave();
    config.save();
}
```

- [ ] **Step 2: Load config values in the constructor**

In the constructor body, after building the option lists, add:

```cpp
// Load persisted settings
config.acquire();
if (config.conf.contains("mgmt_addr"))    mgmtAddr   = config.conf["mgmt_addr"];
if (config.conf.contains("addr"))         dataAddr   = config.conf["addr"];
if (config.conf.contains("second_addr"))  secondAddr = config.conf["second_addr"];
if (config.conf.contains("num_recv_frames")) numRecvFrames = config.conf["num_recv_frames"];
if (config.conf.contains("recv_buff_size"))  recvBufSize   = config.conf["recv_buff_size"];
if (config.conf.contains("samplerate")) {
    int sr = config.conf["samplerate"];
    if (samplerates.keyExists(sr)) {
        srId = samplerates.keyId(sr);
        sampleRate = samplerates[srId];
    }
}
if (config.conf.contains("subdev")) {
    int sd = config.conf["subdev"];
    if (sd >= 0 && sd < N_SUBDEVS) subdevId = sd;
}
config.release();

// Sync UI buffers with loaded strings
strncpy(mgmtAddrBuf,   mgmtAddr.c_str(),   sizeof(mgmtAddrBuf) - 1);
strncpy(dataAddrBuf,   dataAddr.c_str(),   sizeof(dataAddrBuf) - 1);
strncpy(secondAddrBuf, secondAddr.c_str(), sizeof(secondAddrBuf) - 1);
```

- [ ] **Step 3: Build**

```bash
cd /home/steve/git/sdrplusplus/build-x411
make x411_source -j$(nproc) 2>&1 | tee /tmp/x411_build.log
echo "Exit: $?"
```

Expected: exit 0. If compile errors, fix them — common issues:
- Missing `#include <cmath>` for `std::fabs`
- UHD type differences between x411 UHD and system UHD headers — confirm includes resolve from `/opt/uhd-x411/include`

Confirm correct UHD:
```bash
ldd source_modules/x411_source/x411_source.so | grep uhd
# Expected: /opt/uhd-x411/lib/libuhd.so
```

- [ ] **Step 4: Commit**

```bash
cd /home/steve/git/sdrplusplus
git add source_modules/x411_source/src/main.cpp
git commit -m "feat: x411_source module scaffold with config, UI, stream skeleton"
```

---

## Task 8: Integration test — load module in SDR++

Load the compiled module into the `build-x411` SDR++ binary and verify it appears as a source.

**Files:** No source changes — runtime test only.

- [ ] **Step 1: Build the full build-x411**

```bash
cd /home/steve/git/sdrplusplus/build-x411
make -j$(nproc) 2>&1 | tee /tmp/x411_full_build.log
echo "Exit: $?"
```

- [ ] **Step 2: Create a test root directory**

```bash
mkdir -p /tmp/sdrpp_x411_root
cp -r /home/steve/git/sdrplusplus/root/* /tmp/sdrpp_x411_root/
```

- [ ] **Step 3: Launch SDR++ with the x411 module**

```bash
cd /home/steve/git/sdrplusplus/build-x411
./sdrpp --root /tmp/sdrpp_x411_root 2>&1 &
```

- [ ] **Step 4: Verify module is listed as source**

In the SDR++ UI:
1. Open the Source menu (top bar)
2. Confirm "X411" appears in the source dropdown
3. Select "X411" — the menu panel should show Mgmt addr / Data addr / Second addr text fields and a Refresh button

- [ ] **Step 5: Test Refresh with X411 online**

With X411 powered on:
1. Click "Refresh" — expect "Device OK" within 3 seconds
2. Confirm sample rate dropdown shows 9 rates from 245.76 to 0.96 Msps
3. Confirm Channel dropdown shows A:0 (J4), A:1 (J3), B:0 (J33), B:1 (J34)
4. Click Start — waterfall should show live spectrum
5. Tune within ±128.75 MHz of current frequency — should retune instantly
6. Tune more than 128.75 MHz away — brief gap, then spectrum at new frequency

- [ ] **Step 6: Test Refresh with X411 offline**

With X411 powered off:
1. Click "Refresh" — expect "Device not found" after ~3 seconds
2. No crash, UI remains responsive

- [ ] **Step 7: Commit**

```bash
cd /home/steve/git/sdrplusplus
git commit -m "feat: x411_source integration tested and working" --allow-empty
# (or commit any fixups found during testing)
```

---

## Task 9: Verify USRP source is unaffected in `build-x411`

Confirm the `build-x411` build includes the standard USRP source (for other USRPs) and that it links system UHD correctly — the two UHD libraries must not interfere.

**Files:** No source changes — verification only.

- [ ] **Step 1: Check USRP source links system UHD**

```bash
ldd /home/steve/git/sdrplusplus/build-x411/source_modules/usrp_source/usrp_source.so | grep uhd
# Expected: /usr/lib/.../libuhd.so  (system UHD, NOT /opt/uhd-x411/)
```

- [ ] **Step 2: Check X411 source links patched UHD**

```bash
ldd /home/steve/git/sdrplusplus/build-x411/source_modules/x411_source/x411_source.so | grep uhd
# Expected: /opt/uhd-x411/lib/libuhd.so
```

- [ ] **Step 3: Confirm both sources appear in SDR++ UI**

With SDR++ running from `build-x411`:
1. Source dropdown should show both "USRP" and "X411"
2. Switching between them should not crash

- [ ] **Step 4: Commit**

```bash
git commit -m "verify: usrp_source and x411_source coexist with independent UHD libraries" --allow-empty
```

---

## Task 10: Update `build-x411` build script / notes

Document the build commands so repeatable builds are one command.

**Files:**
- Create: `build-x411.sh`

- [ ] **Step 1: Write the build script**

```bash
#!/usr/bin/env bash
# Build SDR++ with X411 support.
# Links x411_source against /opt/uhd-x411/ (patched UHD).
# Output: build-x411/sdrpp + build-x411/source_modules/x411_source/x411_source.so
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
```

- [ ] **Step 2: Make executable and test**

```bash
chmod +x /home/steve/git/sdrplusplus/build-x411.sh
/home/steve/git/sdrplusplus/build-x411.sh 2>&1 | tail -10
```

- [ ] **Step 3: Commit**

```bash
cd /home/steve/git/sdrplusplus
git add build-x411.sh
git commit -m "build: add build-x411.sh convenience script"
```

---

## Self-Review

### Spec coverage

| Requirement (from Claude.md) | Covered by |
|------------------------------|-----------|
| Bandwidths/rates as MCR integer division | Task 4 (verified), Task 7 (hardcoded list) |
| Subdev selection A:0/A:1/B:0/B:1 | Task 7 (static list + `set_rx_subdev_spec`) |
| No gain controls | Task 7 (no gain widget in menuHandler) |
| 10GbE streaming, SFP auto-selected | Task 7 (`buildDeviceArgs()` + `useSecondAddr`) |
| DFE NCO centre frequency | Task 7 (`tune()` NCO path) |
| ±128.75 MHz DDC tuning, instantaneous | Task 7 (`tune()` split, NCO_RANGE constant) |
| Internal clock only | Task 7 (`set_clock_source("internal")`) |
| Never link against system UHD | Task 6 (CMakeLists RPATH + explicit path) |
| USRP/BladeRF/RTL-SDR/PulseAudio/FileIO support | Task 1 (base build) |
| build-x411 separate build directory | Task 6 + Task 10 |
| Prototypes before implementation | Tasks 3–5 |

### Pending items (feed into next iteration)

- **SFP routing assumption** (Task 9): verify B:0/B:1 actually need `second_addr`. If the FPGA switch fabric routes any frontend to any SFP, simplify `buildDeviceArgs()`.
- **Retune test results** (Task 5): if hot PLL retune is safe, update `tune()` to skip stop/restart for large hops.
- **Capability probe results** (Task 3): if `get_rx_gain_range()` returns non-zero, investigate before hiding the gain widget.
- **15 MHz / 23.04 Msps gap**: not in the hardcoded rate list. If users need it, the workaround (30.72 Msps + 2048pt FFT) should be documented in UI tooltip.
