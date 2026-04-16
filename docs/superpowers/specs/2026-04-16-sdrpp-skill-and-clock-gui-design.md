# SDR++ Skill + Clock Source GUI Design

**Date:** 2026-04-16
**Scope:** New sdr-tools:sdrpp plugin skill, x411_source clock source GUI, plugin updates, memory cleanup

---

## Deliverable 1: `sdr-tools:sdrpp` Skill

New skill in the sdr-tools plugin providing SDR++ development knowledge portable across machines.

### File structure

```
skills/sdrpp/
├── SKILL.md
└── runtime-environment.md
```

### SKILL.md scope

- **Identity:** What SDR++ is (one-line, agent-friendly)
- **Build system:** cmake options (`OPT_BUILD_X411_SOURCE`, etc.), `build-x411/` convention, `build-x411.sh` script, how module `.so` files are discovered and loaded
- **Module lifecycle:** `_INIT_` / `_CREATE_INSTANCE_` / `_DELETE_INSTANCE_` / `_END_` exports. `SourceHandler` callbacks: `selectHandler`, `deselectHandler`, `menuHandler`, `startHandler`, `stopHandler`, `tuneHandler`. When each fires and what it should do.
- **Config system:** `ConfigManager`, `config.acquire()` / `config.release(true)` pattern, config rewrites on exit (manual edits are transient), default generation from `_INIT_`, per-module config file path (`x411_config.json`)
- **SmGui patterns:** `LeftLabel` / `FillWidth` / `Combo` / `InputText` / `Button`, `BeginDisabled` / `EndDisabled` for running-state guards, `ForceSync` before interactive widgets, `CONCAT` macro for unique ImGui IDs
- **Key scripts:** `build-x411.sh` (full cmake + make), `run-x411.sh` (launch with RT scheduling), `run-x411-debug.sh` (gdb with signal catch + backtrace logging). What they do, not full contents.
- **Cross-references:** `sdr-tools:x411` for hardware, `sdr-tools:b210` for B210

### runtime-environment.md scope

- **RtAudio backend selection:** Must use `LINUX_ALSA` explicitly via constructor initializer list. The `#ifdef __LINUX_ALSA__` guard does not work (macro only defined inside librtaudio's own build). In-class brace initializer compiled to `UNSPECIFIED` even when the ifdef was active (confirmed by disassembly). Default `RtAudio()` constructor triggers JACK -> PulseAudio fallback -> SIGSEGV in `collectDeviceInfo()` on systems without hardware ALSA sound cards.
- **PulseAudio via PipeWire:** `~/.asoundrc` routes ALSA `default` device to PulseAudio socket at `/run/user/1000/pulse/native`. This is how audio works on VM/XRDP systems with no hardware sound cards (`aplay -l` returns "no soundcards found").
- **XRDP considerations:** No hardware ALSA sound cards. PulseAudio provides audio over XRDP. Audio sink must use LINUX_ALSA backend which routes through the asoundrc -> PulseAudio path.
- **RT scheduling:** `run-x411.sh` applies `chrt -f -p 50` after launch. Significantly improves IO handling. SDR++ runs as current user (required for PulseAudio + X11 access), then RT priority is applied to the process.

---

## Deliverable 2: Clock Source GUI in x411_source

Modify `source_modules/x411_source/src/main.cpp` to add clock source selection and reference lock indicator.

### New state

| Member | Type | Default | Persisted |
|--------|------|---------|-----------|
| `clockSources` | `OptionList<std::string, std::string>` | populated from device | No |
| `csId` | `int` | 0 | Via `clockSource` string |
| `clockSource` | `std::string` | `"mboard"` | Yes (`clock_source` key) |
| `refLocked` | `bool` (atomic) | `false` | No |
| `sensorThread` | `std::thread` | — | No |
| `sensorRunning` | `bool` (atomic) | `false` | No |

### Config changes

New key in `x411_config.json`:
```json
{
  "clock_source": "mboard"
}
```

Default is `mboard` (safe fallback). User changes to `external` via GUI; persisted across sessions.

### Clock source dropdown

- Populated from `dev->get_clock_sources(0)` at connection time (in `start()` after `tryConnect()`)
- Filtered: remove `gpsdo` (no GPS hardware on ZCU111)
- Labels capitalized to match usrp_source convention ("Mboard", "External")
- Placed in menuHandler after Channel combo, inside the `BeginDisabled`/`EndDisabled` block (only changeable when stopped)
- On change: persist to config

### Lock indicator

- Green "LOCKED" / red "UNLOCKED" text next to the dropdown
- "---" when stopped (no device connected)
- Updated by background sensor poll thread (~1 second interval)
- Thread spawned in `startStream()`, joined in `stopStream()`
- Reads `dev->get_mboard_sensor("ref_locked", 0)`
- Exception-safe: if sensor read fails/times out, display "---" and log warning once
- Uses `std::atomic<bool>` for thread-safe GUI reads

### applySettings() change

```cpp
// Before:
dev->set_clock_source("internal");

// After:
dev->set_clock_source(clockSource);
```

UHD API note: `get_clock_sources()` returns `"mboard"` for internal. The runtime API `set_clock_source()` accepts both `"internal"` and `"mboard"`. We use `"mboard"` consistently to match what the device reports.

### Risk: ref_locked sensor timeout

The `ref_locked` sensor timed out during Python testing (along with GPS sensors). If it consistently fails in C++, the lock indicator degrades to showing "---" always. The dropdown is the primary deliverable; the indicator is best-effort.

---

## Deliverable 3: Plugin Updates

### x411 SKILL.md

**Clock reference section:**
- Default changes from `clock_source=mboard` to `clock_source=external`
- Guidance inverted: "If no external reference is connected, use `clock_source=mboard`"
- New subsection documenting naming differences:
  - Device args: `mboard` / `external`
  - UHD C++ `set_clock_source()`: accepts `internal` / `external` (and `mboard`)
  - `get_clock_sources(0)` returns: `['mboard', 'external', 'gpsdo']`
  - `gpsdo` inherited from X4xx framework; no GPS hardware present

**Reference Material section:**
- New entry: "SDR++ source module" -> `sdr-tools:sdrpp`

### rx SKILL.md

**Clock source defaults:**
- X411 default changes from `clock_source=mboard` to `clock_source=external`
- Fallback note: "Omit if no external reference is connected"

---

## Deliverable 4: Memory Cleanup

| Memory file | Action | Reason |
|-------------|--------|--------|
| `project_sdrpp_environment.md` | Delete | Superseded by sdrpp skill (build paths, scripts, config root, environment notes all covered) |
| `project_audio_sink_fix.md` | Delete | Root cause and fix moving to sdrpp skill's `runtime-environment.md` |
| `project_nas_performance.md` | Update | Clarify: X411 data path is 10GbE point-to-point to host. NAS is still 1GbE. 10GbE switch arriving 2026-04-17 will connect host SFP+ and ZCU111 SFPs to switched LAN. |
| `MEMORY.md` | Update | Remove deleted entries, update NAS entry description |

---

## Execution Order

1. Write sdrpp skill (SKILL.md + runtime-environment.md)
2. Implement clock source GUI + lock indicator in x411_source
3. Update plugin files (x411 SKILL.md, rx SKILL.md)
4. Clean up memories
5. Test: build, launch SDR++, verify clock dropdown and lock indicator
