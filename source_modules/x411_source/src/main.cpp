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
#include <thread>
#include <mutex>
#include <cmath>
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

static const double VALID_RATES[] = {
    245.76e6, 122.88e6, 61.44e6, 30.72e6,
     15.36e6,   7.68e6,  3.84e6,  1.92e6,  0.96e6
};
static const int N_RATES = sizeof(VALID_RATES) / sizeof(VALID_RATES[0]);
static const double NCO_RANGE = 128.75e6;

struct SubdevEntry { const char* label; const char* spec; bool useSecondAddr; };
static const SubdevEntry SUBDEVS[] = {
    { "A:0 (J4)",  "A:0", false },
    { "A:1 (J3)",  "A:1", false },
    { "B:0 (J33)", "B:0", true  },
    { "B:1 (J34)", "B:1", true  },
};
static const int N_SUBDEVS = sizeof(SUBDEVS) / sizeof(SUBDEVS[0]);

class X411SourceModule : public ModuleManager::Instance {
public:
    X411SourceModule(std::string name) : name(name) {
        handler.ctx             = this;
        handler.selectHandler   = menuSelected;
        handler.deselectHandler = menuDeselected;
        handler.menuHandler     = menuHandler;
        handler.startHandler    = start;
        handler.stopHandler     = stop;
        handler.tuneHandler     = tune;
        handler.stream          = &stream;

        // Build sample rate option list
        char buf[32];
        for (int i = 0; i < N_RATES; i++) {
            snprintf(buf, sizeof(buf), "%.2f Msps", VALID_RATES[i] / 1e6);
            samplerates.define((int)(VALID_RATES[i]), buf, VALID_RATES[i]);
        }

        // Build subdev option list
        for (int i = 0; i < N_SUBDEVS; i++) {
            subdevs.define(i, SUBDEVS[i].label, i);
        }

        // Load persisted settings
        config.acquire();
        if (config.conf.contains("mgmt_addr"))       mgmtAddr      = config.conf["mgmt_addr"].get<std::string>();
        if (config.conf.contains("addr"))             dataAddr      = config.conf["addr"].get<std::string>();
        if (config.conf.contains("second_addr"))      secondAddr    = config.conf["second_addr"].get<std::string>();
        if (config.conf.contains("num_recv_frames"))  numRecvFrames = config.conf["num_recv_frames"].get<int>();
        if (config.conf.contains("recv_buff_size"))   recvBufSize   = config.conf["recv_buff_size"].get<int>();
        if (config.conf.contains("samplerate")) {
            int sr = config.conf["samplerate"].get<int>();
            if (samplerates.keyExists(sr)) {
                srId = samplerates.keyId(sr);
                sampleRate = samplerates[srId];
            }
        }
        if (config.conf.contains("subdev")) {
            int sd = config.conf["subdev"].get<int>();
            if (sd >= 0 && sd < N_SUBDEVS) subdevId = sd;
        }
        config.release();

        // Sync text buffers
        strncpy(mgmtAddrBuf,   mgmtAddr.c_str(),   sizeof(mgmtAddrBuf)   - 1);
        strncpy(dataAddrBuf,   dataAddr.c_str(),   sizeof(dataAddrBuf)   - 1);
        strncpy(secondAddrBuf, secondAddr.c_str(), sizeof(secondAddrBuf) - 1);

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
    std::string buildDeviceArgs() {
        std::string args = "mgmt_addr=" + mgmtAddr
                         + ",addr=" + dataAddr
                         + ",type=x4xx"
                         + ",num_recv_frames=" + std::to_string(numRecvFrames)
                         + ",recv_buff_size=" + std::to_string(recvBufSize);
        if (SUBDEVS[subdevId].useSecondAddr && !secondAddr.empty())
            args += ",second_addr=" + secondAddr;
        return args;
    }

    uhd::usrp::multi_usrp::sptr tryConnect() {
        try {
            uhd::device_addr_t hint(buildDeviceArgs() + ",timeout=3");
            return uhd::usrp::multi_usrp::make(hint);
        } catch (const std::exception& e) {
            flog::warn("X411: connection failed: {}", e.what());
            return nullptr;
        }
    }

    static void menuSelected(void* ctx) {
        X411SourceModule* _this = (X411SourceModule*)ctx;
        core::setInputSampleRate(_this->sampleRate);
        flog::info("X411SourceModule '{}': Menu Select", _this->name);
    }

    static void menuDeselected(void* ctx) {
        flog::info("X411SourceModule '{}': Menu Deselect", ((X411SourceModule*)ctx)->name);
    }

    // Issue 2 + Issue 3: device leak fix and mutex protection
    static void start(void* ctx) {
        X411SourceModule* _this = (X411SourceModule*)ctx;
        std::lock_guard<std::mutex> lock(_this->streamMtx);
        if (_this->running) return;

        _this->dev = _this->tryConnect();
        if (!_this->dev) {
            flog::error("X411: failed to connect at start");
            return;
        }

        try {
            _this->applySettings();
            _this->startStream();
        } catch (const std::exception& e) {
            flog::error("X411: start failed: {}", e.what());
            _this->dev.reset();
            return;
        }

        _this->running = true;
        flog::info("X411SourceModule '{}': Start", _this->name);
    }

    // Issue 3: mutex protection for stop
    static void stop(void* ctx) {
        X411SourceModule* _this = (X411SourceModule*)ctx;
        std::lock_guard<std::mutex> lock(_this->streamMtx);
        if (!_this->running) return;
        _this->running = false;
        _this->stopStream();
        _this->dev.reset();
        flog::info("X411SourceModule '{}': Stop", _this->name);
    }

    // Issue 3: hold streamMtx across entire tune() to eliminate NCO/stop race
    static void tune(double freq, void* ctx) {
        X411SourceModule* _this = (X411SourceModule*)ctx;
        std::lock_guard<std::mutex> lock(_this->streamMtx);

        _this->freq = freq;
        if (!_this->running) return;

        double delta = freq - _this->rfLo;
        if (std::fabs(delta) <= NCO_RANGE) {
            // NCO-only retune — instantaneous
            uhd::tune_request_t tr(freq);
            tr.rf_freq         = _this->rfLo;
            tr.rf_freq_policy  = uhd::tune_request_t::POLICY_MANUAL;
            tr.dsp_freq_policy = uhd::tune_request_t::POLICY_AUTO;
            _this->dev->set_rx_freq(tr, 0);
        } else {
            // PLL retune: stop stream, retune, restart
            _this->stopStream();
            uhd::tune_result_t result = _this->dev->set_rx_freq(freq, 0);
            _this->rfLo = result.actual_rf_freq;
            _this->startStream();
        }
        flog::info("X411: Tune {:.3f} MHz (LO {:.3f} MHz)", freq / 1e6, _this->rfLo / 1e6);
    }

    void applySettings() {
        dev->set_rx_subdev_spec(uhd::usrp::subdev_spec_t(SUBDEVS[subdevId].spec), 0);
        dev->set_rx_rate(sampleRate, 0);
        dev->set_clock_source("internal");
        uhd::tune_result_t result = dev->set_rx_freq(freq, 0);
        rfLo = result.actual_rf_freq;
    }

    // Issue 1: compute and cap bufSize before spawning worker
    void startStream() {
        bufSize = std::min((int)(sampleRate / 200), STREAM_BUFFER_SIZE);
        uhd::stream_args_t sargs;
        sargs.channels   = {0};
        sargs.cpu_format = "fc32";
        sargs.otw_format = "sc16";
        streamer = dev->get_rx_stream(sargs);
        streamer->issue_stream_cmd(uhd::stream_cmd_t::STREAM_MODE_START_CONTINUOUS);
        stream.clearWriteStop();
        workerThread = std::thread(&X411SourceModule::worker, this);
    }

    void stopStream() {
        stream.stopWriter();
        if (streamer)
            streamer->issue_stream_cmd(uhd::stream_cmd_t::STREAM_MODE_STOP_CONTINUOUS);
        if (workerThread.joinable()) workerThread.join();
        stream.clearWriteStop();
        streamer.reset();
    }

    void worker() {
        uhd::rx_metadata_t meta;
        try {
            while (true) {
                int len = streamer->recv(stream.writeBuf, bufSize, meta, 1.0);
                if (len < 0) break;
                if (len == 0) {
                    flog::warn("X411: recv returned 0 (error_code={})", (int)meta.error_code);
                    continue;
                }
                if (meta.error_code == uhd::rx_metadata_t::ERROR_CODE_OVERFLOW)
                    flog::warn("X411: overflow — DSP pipeline too slow for {:.2f} Msps", sampleRate / 1e6);
                if (!stream.swap(len)) break;
            }
        } catch (const std::exception& e) {
            flog::error("X411: recv error: {}", e.what());
        }
    }

    static void menuHandler(void* ctx) {
        X411SourceModule* _this = (X411SourceModule*)ctx;

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

        if (_this->running) SmGui::EndDisabled();

        SmGui::FillWidth();
        SmGui::ForceSync();
        // Issue 4: guard Refresh against double-claim while streaming
        if (SmGui::Button(CONCAT("Refresh##x411_", _this->name))) {
            if (!_this->running) {
                auto probe = _this->tryConnect();
                _this->deviceFound = (probe != nullptr);
            }
        }
        SmGui::SameLine();
        SmGui::Text(_this->deviceFound ? "Device OK" : "Device not found");

        if (_this->running) SmGui::BeginDisabled();

        SmGui::LeftLabel("Sample rate");
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

    std::string name;
    bool enabled     = true;
    bool running     = false;
    bool deviceFound = false;
    double freq      = 100e6;
    double sampleRate = 30.72e6;
    double rfLo      = 0.0;
    int srId         = 3;    // 30.72 Msps default
    int subdevId     = 0;    // A:0 (J4) default

    std::string mgmtAddr   = "192.168.7.162";
    std::string dataAddr   = "192.168.200.2";
    std::string secondAddr = "192.168.201.2";
    int numRecvFrames = 2048;
    int recvBufSize   = 33554432;

    char mgmtAddrBuf[64]   = "192.168.7.162";
    char dataAddrBuf[64]   = "192.168.200.2";
    char secondAddrBuf[64] = "192.168.201.2";

    // Issue 1 + Issue 3: new member variables
    std::mutex streamMtx;
    int bufSize = 0;

    dsp::stream<dsp::complex_t> stream;
    SourceManager::SourceHandler handler;
    uhd::usrp::multi_usrp::sptr dev;
    uhd::rx_streamer::sptr streamer;
    std::thread workerThread;

    OptionList<int, double> samplerates;
    OptionList<int, int>    subdevs;
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
