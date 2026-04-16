# SDR++ Skill + Clock Source GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `sdr-tools:sdrpp` plugin skill, add clock source GUI with lock indicator to x411_source, update stale plugin files, and clean up project memories.

**Architecture:** Four independent deliverables executed in order: (1) new sdrpp skill files in the plugin marketplace, (2) clock source dropdown + ref_locked indicator added to x411_source module, (3) text updates to x411 and rx plugin skills, (4) memory file cleanup. The sdrpp skill is pure documentation. The clock GUI modifies one C++ file and one JSON default.

**Tech Stack:** Markdown (skills), C++17/UHD/ImGui (clock GUI), JSON (config)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `~/.claude/plugins/marketplaces/distributed-radio-tools/plugins/sdr-tools/skills/sdrpp/SKILL.md` | Create | Main sdrpp skill |
| `~/.claude/plugins/marketplaces/distributed-radio-tools/plugins/sdr-tools/skills/sdrpp/runtime-environment.md` | Create | RtAudio/PulseAudio/RT scheduling reference |
| `source_modules/x411_source/src/main.cpp` | Modify | Clock source dropdown + lock indicator |
| `~/.claude/plugins/marketplaces/distributed-radio-tools/plugins/sdr-tools/skills/x411/SKILL.md` | Modify | Flip clock default, add naming docs, add SDR++ cross-ref |
| `~/.claude/plugins/marketplaces/distributed-radio-tools/plugins/sdr-tools/skills/rx/SKILL.md` | Modify | Flip X411 clock default |
| `~/.claude/projects/-home-steve-git-sdrplusplus/memory/project_nas_performance.md` | Modify | Update 10GbE status |
| `~/.claude/projects/-home-steve-git-sdrplusplus/memory/project_sdrpp_environment.md` | Delete | Superseded by sdrpp skill |
| `~/.claude/projects/-home-steve-git-sdrplusplus/memory/project_audio_sink_fix.md` | Delete | Superseded by runtime-environment.md |
| `~/.claude/projects/-home-steve-git-sdrplusplus/memory/MEMORY.md` | Modify | Remove deleted entries, update NAS description |

---

## Task 1: Create `sdr-tools:sdrpp` SKILL.md

**Files:**
- Create: `~/.claude/plugins/marketplaces/distributed-radio-tools/plugins/sdr-tools/skills/sdrpp/SKILL.md`

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p ~/.claude/plugins/marketplaces/distributed-radio-tools/plugins/sdr-tools/skills/sdrpp
```

- [ ] **Step 2: Write SKILL.md**

Write the following to `~/.claude/plugins/marketplaces/distributed-radio-tools/plugins/sdr-tools/skills/sdrpp/SKILL.md`:

```markdown
---
name: sdrpp
description: "SDR++ development: module architecture, build system, config persistence, SmGui GUI patterns, convenience scripts. Consult when modifying or debugging SDR++ modules."
---

# SDR++ Development Knowledge Base

SDR++ is a cross-platform, open-source SDR receiver application with a modular plugin
architecture. This skill covers what you need to modify existing modules.

## Build System

### Build directories

Separate build directories per device configuration:

- `build-x411/` — includes x411_source module, links against `/opt/uhd-x411/`
- `build/` — standard build with system UHD (for USRP/BladeRF/RTL-SDR only)

### Key cmake options

| Option | Purpose |
|--------|---------|
| `OPT_BUILD_X411_SOURCE` | X411 RFSoC source module (requires `/opt/uhd-x411/`) |
| `OPT_BUILD_USRP_SOURCE` | Generic USRP source (system UHD) |
| `OPT_BUILD_BLADERF_SOURCE` | BladeRF source |
| `OPT_BUILD_RTL_SDR_SOURCE` | RTL-SDR source |
| `OPT_BUILD_AUDIO_SINK` | Audio output via RtAudio |
| `OPT_BUILD_FILE_SOURCE` | IQ file playback |

### Convenience scripts

| Script | Purpose |
|--------|---------|
| `build-x411.sh` | Full cmake configure + make for build-x411/ |
| `run-x411.sh [root_dir]` | Launch sdrpp as current user, then apply `chrt -f -p 50` for RT scheduling. Default root: `/tmp/sdrpp_x411_test` |
| `run-x411-debug.sh [root_dir]` | Launch under gdb with `catch signal SIGSEGV/SIGABRT`, backtrace logged to `/tmp/sdrpp_crash.log` |

### Module .so discovery

SDR++ loads module `.so` files listed in `config.json` under the `"modules"` array. Paths can
be absolute or relative to the binary. When running from the build tree, modules are at
`build-x411/source_modules/<name>/<name>.so`.

### x411_source RPATH

The x411_source CMakeLists sets `BUILD_RPATH` and `INSTALL_RPATH` to `/opt/uhd-x411/lib`,
so `x411_source.so` always loads the patched UHD 4.4.0.x411 regardless of system UHD version
or `LD_LIBRARY_PATH`. The generic usrp_source links system UHD. Both modules can coexist in
the same build.

## Module Lifecycle

Source modules export four C functions:

| Export | When called | Purpose |
|--------|-------------|---------|
| `_INIT_()` | Module .so loaded | Set config path, load defaults, `config.enableAutoSave()` |
| `_CREATE_INSTANCE_(name)` | SDR++ creates the module | Construct module object, register source with `sigpath::sourceManager` |
| `_DELETE_INSTANCE_(ptr)` | SDR++ unloads module | Stop streaming, unregister source, delete object |
| `_END_()` | SDR++ shutting down | `config.disableAutoSave()`, `config.save()` |

### SourceHandler callbacks

Set in the constructor via `handler.xxxHandler = staticFunc`:

| Callback | Fires when | Typical action |
|----------|-----------|----------------|
| `selectHandler` | User selects this source in dropdown | `core::setInputSampleRate()` |
| `deselectHandler` | User switches away from this source | Log only |
| `startHandler` | User clicks Play | Connect to device, apply settings, start streaming thread |
| `stopHandler` | User clicks Stop | Stop stream, join worker thread, release device |
| `tuneHandler` | User changes frequency | NCO-only or PLL retune depending on hop size |
| `menuHandler` | Every GUI frame | Draw controls in the source panel |

All callbacks are `static void fn(void* ctx)` — cast `ctx` back to your module class.

## Config System

### ConfigManager pattern

```cpp
config.acquire();                          // lock mutex
config.conf["key"] = value;                // read/write nlohmann::json
config.release(true);                      // unlock + mark dirty (true = save needed)
```

- `config.acquire()` / `config.release()` bracket all config access
- Pass `true` to `release()` when you've written changes
- `config.enableAutoSave()` in `_INIT_()` enables periodic flush
- `config.save()` in `_END_()` ensures final state is written

### Config file behavior

- Path set in `_INIT_()`: `config.setPath(core::args["root"].s() + "/x411_config.json")`
- If the file does not exist, `config.load(defaults)` creates it from the `json` defaults object
- **SDR++ rewrites config on exit** — manual edits to config files while SDR++ is running are overwritten on shutdown. Edit while SDR++ is stopped, or use the GUI.
- Config defaults in `_INIT_()` must produce a valid, launchable configuration. SDR++ crash-loops if a module fails to initialize from default config.

### Loading persisted values

In the constructor, after building option lists:

```cpp
config.acquire();
if (config.conf.contains("key")) {
    value = config.conf["key"].get<Type>();
    // validate: check option list membership, clamp ranges
}
config.release();
```

Always validate loaded values — the config file may contain stale or invalid entries from
a previous version.

## SmGui Patterns

SDR++ uses SmGui (a wrapper around ImGui) for module UIs rendered in the source panel.

### Common widgets

```cpp
SmGui::LeftLabel("Label");           // Left-aligned label
SmGui::FillWidth();                  // Next widget fills remaining width
SmGui::ForceSync();                  // Required before Combo/InputText/Button
SmGui::Combo(id, &index, list.txt);  // Dropdown from OptionList
SmGui::InputText(id, buf, size);     // Text input
SmGui::Button(id);                   // Button, returns true on click
SmGui::SameLine();                   // Next widget on same line
SmGui::Text("string");               // Static text
SmGui::TextColored(color, "text");   // Colored text (ImVec4)
```

### Unique IDs

Every widget needs a unique ImGui ID. Use the `CONCAT` macro:

```cpp
#define CONCAT(a, b) ((std::string(a) + b).c_str())
SmGui::Combo(CONCAT("##x411_sr_", name), &srId, samplerates.txt);
```

### Running-state disable pattern

Controls that must not change while streaming are wrapped:

```cpp
if (running) SmGui::BeginDisabled();
// ... address fields, channel selector, etc.
if (running) SmGui::EndDisabled();
```

Controls that CAN change while running (clock source, gain) go after `EndDisabled` and
include a `if (running) { dev->set_xxx(); }` call to apply immediately.

### OptionList

```cpp
OptionList<KeyType, ValueType> list;
list.define(key, "Display Name", value);  // add entry
list.key(index);    // key at index
list[index];        // value at index
list.keyExists(k);  // check if key exists
list.keyId(k);      // index of key
list.txt;           // null-separated string for Combo widget
list.size();        // entry count
```

## Reference Material

- **X411 hardware:** see `sdr-tools:x411` — device args, RF ports, sample rates, gain model
- **B210 hardware:** see `sdr-tools:b210` — USB config, gain, clock reference
- **Runtime environment (VM/XRDP/audio):** see [runtime-environment.md](runtime-environment.md)
```

- [ ] **Step 3: Verify the file was written correctly**

```bash
head -5 ~/.claude/plugins/marketplaces/distributed-radio-tools/plugins/sdr-tools/skills/sdrpp/SKILL.md
```

Expected: frontmatter with `name: sdrpp` and description.

---

## Task 2: Create `runtime-environment.md`

**Files:**
- Create: `~/.claude/plugins/marketplaces/distributed-radio-tools/plugins/sdr-tools/skills/sdrpp/runtime-environment.md`

- [ ] **Step 1: Write runtime-environment.md**

Write the following to `~/.claude/plugins/marketplaces/distributed-radio-tools/plugins/sdr-tools/skills/sdrpp/runtime-environment.md`:

```markdown
---
name: SDR++ runtime environment
description: "RtAudio ALSA backend requirement, PulseAudio-via-PipeWire routing, XRDP audio, RT scheduling for SDR++. Consult when audio crashes or performance issues occur on VM/headless systems."
parent_skill: sdr-tools:sdrpp
---

# SDR++ Runtime Environment

## RtAudio Backend Selection — LINUX_ALSA Required

On systems without hardware ALSA sound cards (VMs, XRDP sessions, containers), the default
`RtAudio()` constructor (`UNSPECIFIED` backend) triggers a fallback chain:
JACK (not running) -> PulseAudio -> **SIGSEGV** in `RtApiPulse::collectDeviceInfo()`.

This is a bug in rtaudio 5.2's PulseAudio backend when no hardware sound cards exist
(`aplay -l` returns "no soundcards found").

### The fix

In `sink_modules/audio_sink/src/main.cpp`, the `RtAudio` member must be initialized via the
**constructor initializer list** with the `LINUX_ALSA` backend:

```cpp
AudioSink(SinkManager::Stream* stream, std::string streamName) : audio(RtAudio::LINUX_ALSA) {
```

The member declaration is just `RtAudio audio;` with no in-class initializer.

### Why not `#ifdef __LINUX_ALSA__`?

The original code used:
```cpp
#ifdef __LINUX_ALSA__
    RtAudio audio{RtAudio::LINUX_ALSA};
#else
    RtAudio audio;
#endif
```

This fails for two reasons:
1. `__LINUX_ALSA__` is only defined inside librtaudio's own build — not in SDR++'s compilation
   units. The `#ifdef` branch is never taken.
2. Even when forced active, the in-class brace initializer compiled to `xor %esi, %esi`
   (`UNSPECIFIED=0`) instead of `mov $0x1, %esi` (`LINUX_ALSA=1`). Confirmed by disassembly.
   The constructor initializer list produces the correct machine code.

### Audio routing path

```
SDR++ audio_sink
  -> RtAudio (LINUX_ALSA backend)
    -> ALSA "default" device
      -> ~/.asoundrc PCM redirect
        -> PulseAudio socket (/run/user/1000/pulse/native)
          -> PipeWire (PulseAudio compatibility layer)
            -> XRDP audio output
```

The `~/.asoundrc` file routes the ALSA `default` device to PulseAudio:
```
pcm.!default { type pulse }
ctl.!default { type pulse }
```

## RT Scheduling

`run-x411.sh` launches SDR++ as the current user (required for PulseAudio + X11 access),
then applies RT scheduling:

```bash
sudo chrt -f -p 50 "$SDRPP_PID"
```

This significantly improves IO handling — without RT priority, the streaming thread competes
with other processes for CPU time, causing buffer underruns at higher sample rates.

SDR++ must run as the current user (not root) because:
- PulseAudio rejects connections from other users
- X11/XRDP display access requires the session user's credentials

## Debugging Crashes

`run-x411-debug.sh` launches SDR++ under gdb with automatic signal catching:
- Catches SIGSEGV and SIGABRT
- Prints backtrace (50 frames), thread list, and frame 0 locals
- Mirrors all output to `/tmp/sdrpp_crash.log`

Usage: reproduce the crash in the GUI, then check `/tmp/sdrpp_crash.log`.
```

- [ ] **Step 2: Verify the file was written correctly**

```bash
head -5 ~/.claude/plugins/marketplaces/distributed-radio-tools/plugins/sdr-tools/skills/sdrpp/runtime-environment.md
```

Expected: frontmatter with `parent_skill: sdr-tools:sdrpp`.

- [ ] **Step 3: Reload plugins to verify skill is discovered**

Run `/reload-plugins` in Claude Code. Expected: sdrpp appears in the skill list.

---

## Task 3: Add clock source dropdown to x411_source

**Files:**
- Modify: `source_modules/x411_source/src/main.cpp`

- [ ] **Step 1: Add clock source state members**

In the members section (after `int subdevId = 0;`, around line 333), add:

```cpp
    std::string clockSource = "mboard";
    int csId = 0;
    OptionList<std::string, std::string> clockSources;
```

- [ ] **Step 2: Add clock_source to config defaults in `_INIT_()`**

In the `_INIT_()` function, after `def["subdev"] = 0;` (line 367), add:

```cpp
    def["clock_source"] = "mboard";
```

- [ ] **Step 3: Load clock_source from config in constructor**

In the constructor, after the `subdev` config loading block (after line 85), add:

```cpp
        if (config.conf.contains("clock_source")) {
            clockSource = config.conf["clock_source"].get<std::string>();
        }
```

- [ ] **Step 4: Populate clock sources and apply selection in `start()`**

In the `start()` static function, after `_this->dev = _this->tryConnect();` succeeds and before `_this->applySettings();` (between lines 148 and 151), add:

```cpp
        // Populate clock sources from device, filtering out gpsdo
        _this->clockSources.clear();
        try {
            auto sources = _this->dev->get_clock_sources(0);
            for (const auto& s : sources) {
                if (s == "gpsdo") continue;
                std::string label = s;
                label[0] = std::toupper(label[0]);
                _this->clockSources.define(s, label, s);
            }
            if (_this->clockSources.keyExists(_this->clockSource)) {
                _this->csId = _this->clockSources.keyId(_this->clockSource);
            }
        } catch (const std::exception& e) {
            flog::warn("X411: failed to query clock sources: {}", e.what());
            _this->clockSources.define("mboard", "Mboard", "mboard");
        }
```

- [ ] **Step 5: Change `applySettings()` to use selected clock source**

In `applySettings()` (line 203), change:

```cpp
        dev->set_clock_source("internal");
```

to:

```cpp
        dev->set_clock_source(clockSource);
```

- [ ] **Step 6: Add clock source combo to menuHandler**

In `menuHandler()`, after the `EndDisabled` on line 322 and before the closing `}` of `menuHandler`, add:

```cpp

        // Clock source — changeable while running (LMK04208 re-locks without reset)
        if (_this->clockSources.size() > 1) {
            SmGui::LeftLabel("Clock");
            SmGui::FillWidth();
            if (SmGui::Combo(CONCAT("##x411_clk_", _this->name),
                             &_this->csId, _this->clockSources.txt)) {
                _this->clockSource = _this->clockSources.key(_this->csId);
                if (_this->running) {
                    _this->dev->set_clock_source(_this->clockSource);
                }
                config.acquire();
                config.conf["clock_source"] = _this->clockSource;
                config.release(true);
            }
        }
```

- [ ] **Step 7: Build and verify**

```bash
cd /home/steve/git/sdrplusplus
cmake --build build-x411 --target x411_source -- -j$(nproc) 2>&1 | tail -5
echo "Exit: $?"
```

Expected: exit 0, no errors.

- [ ] **Step 8: Commit**

```bash
cd /home/steve/git/sdrplusplus
git add source_modules/x411_source/src/main.cpp
git commit -m "feat(x411_source): add clock source dropdown (external/mboard)"
```

---

## Task 4: Add ref_locked indicator to x411_source

**Files:**
- Modify: `source_modules/x411_source/src/main.cpp`

- [ ] **Step 1: Add sensor polling state members**

At the top of the file, add include:

```cpp
#include <atomic>
```

In the members section, after the `clockSources` OptionList, add:

```cpp
    std::atomic<bool> refLocked{false};
    std::atomic<bool> sensorRunning{false};
    std::atomic<int> sensorStatus{0};  // 0=unknown, 1=locked, 2=unlocked, -1=error
    std::thread sensorThread;
```

- [ ] **Step 2: Write the sensor polling function**

In the private section, after `worker()`, add:

```cpp
    void sensorWorker() {
        bool warnedOnce = false;
        while (sensorRunning.load()) {
            try {
                auto sensor = dev->get_mboard_sensor("ref_locked", 0);
                sensorStatus.store(sensor.to_bool() ? 1 : 2);
            } catch (const std::exception& e) {
                if (!warnedOnce) {
                    flog::warn("X411: ref_locked sensor read failed: {}", e.what());
                    warnedOnce = true;
                }
                sensorStatus.store(-1);
            }
            // Sleep ~1 second in 100ms increments so we can exit promptly
            for (int i = 0; i < 10 && sensorRunning.load(); i++) {
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
            }
        }
    }
```

- [ ] **Step 3: Start sensor thread in `startStream()`**

In `startStream()`, after spawning `workerThread` (after line 218), add:

```cpp
        sensorRunning.store(true);
        sensorThread = std::thread(&X411SourceModule::sensorWorker, this);
```

- [ ] **Step 4: Stop sensor thread in `stopStream()`**

In `stopStream()`, at the very beginning (before `stream.stopWriter()`), add:

```cpp
        sensorRunning.store(false);
        if (sensorThread.joinable()) sensorThread.join();
        sensorStatus.store(0);
```

- [ ] **Step 5: Add lock indicator to menuHandler**

In `menuHandler()`, immediately after the clock source combo block (after the closing `}` of the `clockSources.size() > 1` block), add:

```cpp

        // Ref lock indicator
        {
            SmGui::SameLine();
            int status = _this->sensorStatus.load();
            if (status == 1) {
                SmGui::TextColored(ImVec4(0.0f, 1.0f, 0.0f, 1.0f), "LOCKED");
            } else if (status == 2) {
                SmGui::TextColored(ImVec4(1.0f, 0.0f, 0.0f, 1.0f), "UNLOCKED");
            } else {
                SmGui::Text("---");
            }
        }
```

- [ ] **Step 6: Build and verify**

```bash
cd /home/steve/git/sdrplusplus
cmake --build build-x411 --target x411_source -- -j$(nproc) 2>&1 | tail -5
echo "Exit: $?"
```

Expected: exit 0, no errors.

- [ ] **Step 7: Commit**

```bash
cd /home/steve/git/sdrplusplus
git add source_modules/x411_source/src/main.cpp
git commit -m "feat(x411_source): add ref_locked indicator with sensor polling"
```

---

## Task 5: Integration test — clock source GUI

**Files:** No source changes — runtime test.

- [ ] **Step 1: Build full project**

```bash
cd /home/steve/git/sdrplusplus
cmake --build build-x411 -- -j$(nproc) 2>&1 | tail -3
```

- [ ] **Step 2: Delete stale config to test default generation**

```bash
rm -f /tmp/sdrpp_x411_test/x411_config.json
```

- [ ] **Step 3: Launch SDR++ and verify default config is created**

```bash
./run-x411.sh /tmp/sdrpp_x411_test
```

After launch, verify the config was created with the new default:

```bash
cat /tmp/sdrpp_x411_test/x411_config.json | python3 -m json.tool
```

Expected: `"clock_source": "mboard"` present in the JSON.

- [ ] **Step 4: GUI verification checklist**

With X411 powered on:

1. Select X411 source, click Start
2. Clock dropdown appears with "Mboard" and "External" options (no "Gpsdo")
3. Lock indicator shows "LOCKED" or "UNLOCKED" or "---" (not a crash)
4. Switch clock to "External" while running — no crash, indicator should update
5. Switch back to "Mboard" — no crash
6. Stop, then Start again — clock source persists from previous selection
7. Stop SDR++. Check `x411_config.json` contains the last-selected clock source.

With X411 powered off:

1. Click Start — fails gracefully (error logged, no crash)
2. Clock dropdown is empty or shows fallback "Mboard" — no crash

- [ ] **Step 5: Commit any fixes found during testing**

```bash
cd /home/steve/git/sdrplusplus
git add -u
git commit -m "fix(x411_source): integration test fixes for clock source GUI"
```

Only commit if fixes were needed. Skip if test passed clean.

---

## Task 6: Update x411 plugin skill

**Files:**
- Modify: `~/.claude/plugins/marketplaces/distributed-radio-tools/plugins/sdr-tools/skills/x411/SKILL.md`

- [ ] **Step 1: Update clock reference section**

In the x411 SKILL.md, find the `### Clock reference` section and replace it with:

```markdown
### Clock reference
- **Default: `clock_source=external`** — uses 10 MHz SMA input on J109. Frequency accuracy
  ~5 ppb at 2140 MHz.
- **Fallback: `clock_source=mboard`** — uses internal 12.8 MHz OCXO if no external reference
  is connected. Frequency accuracy ~91 ppb at 2140 MHz.
- If the user doesn't specify, use `clock_source=external`. Only omit or use `clock_source=mboard`
  when the user confirms no external reference is connected.

#### Clock source naming

| Context | Internal OCXO | External 10 MHz | GPS (not present) |
|---------|--------------|-----------------|-------------------|
| UHD device args (`-A "..."`) | `clock_source=mboard` | `clock_source=external` | `clock_source=gpsdo` |
| UHD C++ `set_clock_source()` | `"internal"` or `"mboard"` | `"external"` | `"gpsdo"` |
| UHD C++ `get_clock_sources()` returns | `"mboard"` | `"external"` | `"gpsdo"` |
| SDR++ x411_source config | `"mboard"` | `"external"` | filtered out |

`get_clock_sources(0)` returns `['mboard', 'external', 'gpsdo']`. The `gpsdo` option is
inherited from the X4xx UHD framework — there is no GPS hardware on the ZCU111. The SDR++
x411_source module filters it out of the GUI dropdown.
```

- [ ] **Step 2: Add SDR++ cross-reference to Reference Material section**

In the `## Reference Material` section, after the last entry, add:

```markdown

**SDR++ source module:** Build, run, debug, module architecture, GUI patterns
→ [sdr-tools:sdrpp](../sdrpp/SKILL.md)
```

- [ ] **Step 3: Verify the edits**

```bash
grep -A 3 "Default.*clock_source" ~/.claude/plugins/marketplaces/distributed-radio-tools/plugins/sdr-tools/skills/x411/SKILL.md
```

Expected: `clock_source=external` appears as the default.

---

## Task 7: Update rx plugin skill

**Files:**
- Modify: `~/.claude/plugins/marketplaces/distributed-radio-tools/plugins/sdr-tools/skills/rx/SKILL.md`

- [ ] **Step 1: Update X411 clock source default**

In the rx SKILL.md, find the `### Clock source defaults` section. Change the X411 bullet from:

```markdown
- **X411:** default `clock_source=mboard` (internal OCXO). Only add `clock_source=external`
  when the user confirms a 10 MHz reference is connected to J109.
```

to:

```markdown
- **X411:** default `clock_source=external` (10 MHz reference on J109). Use `clock_source=mboard`
  only if no external reference is connected.
```

- [ ] **Step 2: Verify the edit**

```bash
grep "X411.*clock_source" ~/.claude/plugins/marketplaces/distributed-radio-tools/plugins/sdr-tools/skills/rx/SKILL.md
```

Expected: `clock_source=external` appears as the default.

---

## Task 8: Clean up project memories

**Files:**
- Delete: `~/.claude/projects/-home-steve-git-sdrplusplus/memory/project_sdrpp_environment.md`
- Delete: `~/.claude/projects/-home-steve-git-sdrplusplus/memory/project_audio_sink_fix.md`
- Modify: `~/.claude/projects/-home-steve-git-sdrplusplus/memory/project_nas_performance.md`
- Modify: `~/.claude/projects/-home-steve-git-sdrplusplus/memory/MEMORY.md`

- [ ] **Step 1: Delete superseded memory files**

```bash
rm ~/.claude/projects/-home-steve-git-sdrplusplus/memory/project_sdrpp_environment.md
rm ~/.claude/projects/-home-steve-git-sdrplusplus/memory/project_audio_sink_fix.md
```

- [ ] **Step 2: Update NAS performance memory**

Replace the content of `project_nas_performance.md` with:

```markdown
---
name: NAS capture performance (/mnt/capture)
description: Measured write throughput to NAS and IQ sample rate limits per format; 10GbE switch status
type: project
---
/mnt/capture is a Synology NAS (`//syn/Capture`) mounted via SMB 3.1.1 (CIFS) at `192.168.7.4`. Currently on **1GbE** — measured sustained sequential write: **114 MB/s** (direct I/O, 4 MB blocks), the 1GbE wire ceiling.

X411 data path (SFP0/SFP1) is 10GbE point-to-point to host. NAS is still on 1GbE.

**10GbE switch arriving 2026-04-17** — will connect host SFP+ and all ZCU111 SFPs to switched LAN. Once active, NAS will also be on 10GbE.

**IQ capture limits at 114 MB/s (1GbE, current NAS path):**
- cf32 (8 B/sample): ~14.3 Msps
- cs16 (4 B/sample): ~28.5 Msps
- cs8 (2 B/sample): ~57 Msps

**IQ capture limits at ~1.25 GB/s (10GbE, once switched):**
- cf32: ~156 Msps
- cs16: ~312 Msps (covers X411's full 245.76 Msps range)
- cs8: ~625 Msps

**How to apply:** For broadband IQ recording to /mnt/capture on 1GbE, use cs16 or cs8. cf32 only viable below ~14 Msps on current network. Re-measure after 10GbE switch is installed.
```

- [ ] **Step 3: Update MEMORY.md index**

Replace the content of `MEMORY.md` with:

```markdown
# Memory Index

- [NAS capture performance (/mnt/capture)](project_nas_performance.md) — 114 MB/s on 1GbE; 10GbE switch arriving 2026-04-17; IQ rate limits per format
```

- [ ] **Step 4: Verify cleanup**

```bash
ls ~/.claude/projects/-home-steve-git-sdrplusplus/memory/
```

Expected: `MEMORY.md` and `project_nas_performance.md` only.

---

## Task 9: Reload plugins and final verification

- [ ] **Step 1: Reload plugins**

Run `/reload-plugins` in Claude Code. Verify sdrpp skill appears in the skill list.

- [ ] **Step 2: Test skill invocation**

Invoke `/sdr-tools:sdrpp` and verify the skill content loads correctly.

- [ ] **Step 3: Invoke `/sdr-tools:x411` and verify clock default is updated**

Check that the clock reference section shows `external` as default.

---

## Self-Review

### Spec coverage

| Spec requirement | Task |
|-----------------|------|
| sdrpp SKILL.md (architecture, build, config, SmGui) | Task 1 |
| runtime-environment.md (RtAudio, PulseAudio, XRDP, RT) | Task 2 |
| Clock source dropdown (filtered, no gpsdo) | Task 3 |
| ref_locked indicator (best-effort, graceful degradation) | Task 4 |
| Config persistence with mboard default | Task 3 (steps 2-3) |
| applySettings uses selected clock source | Task 3 (step 5) |
| x411 SKILL.md: flip default, naming docs, cross-ref | Task 6 |
| rx SKILL.md: flip default | Task 7 |
| Delete project_sdrpp_environment.md | Task 8 |
| Delete project_audio_sink_fix.md | Task 8 |
| Update project_nas_performance.md (10GbE) | Task 8 |
| Integration test | Task 5 |

### Placeholder scan

No TBDs, TODOs, or vague steps found.

### Type consistency

- `clockSource` (std::string) used consistently across config load (Task 3 step 3), `applySettings()` (Task 3 step 5), combo handler (Task 3 step 6)
- `clockSources` (OptionList) populated in start() (Task 3 step 4), read in menuHandler (Task 3 step 6)
- `sensorStatus` (atomic<int>) written in sensorWorker (Task 4 step 2), read in menuHandler (Task 4 step 5) — values 0/1/2/-1 consistent
- `csId` (int) used with clockSources OptionList consistently
