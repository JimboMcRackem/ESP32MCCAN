# ESP32 MCCAN Core Firmware Implementation Plan (Plan 1 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working ESP32 lighting controller that reads the motorcycle CAN bus and drives 4 RGB corner strings + 2 Denali channels correctly, using a baked-in Energica Experia default profile.

**Architecture:** Four layers — a CAN Input Layer (frames → logical function states via a configurable `(ID, bit)` mapping), a pure Behavior Engine (`logical states + config → per-channel output intents`, host-testable), an Output/Driver Layer (intents → 14 PWM channels behind a small interface), and boot wiring in `main.cpp`. Connectivity/web app is Plan 2. All correctness-critical logic lives in pure, host-tested C++ with no Arduino dependencies.

**Tech Stack:** C++17, PlatformIO, Arduino-ESP32 framework, ESP32 TWAI (CAN), LEDC (PWM), LittleFS (storage), ArduinoJson (config), Unity (unit tests, `native` env).

## Global Constraints

- **Target board:** classic ESP32 (WROOM/WROVER) — has 16 LEDC PWM channels; 14 are used. (An external PWM driver is an alternative decided in the future PCB plan; this plan drives channels natively.)
- **Channel count:** 14 PWM outputs = 4 RGB corners × 3 (R,G,B) + 2 Denali. Both Denali channels are driven with the **same** value.
- **Bit-numbering convention (canonical):** a mapping bit index `b` refers to `byte = b / 8`, `bitInByte = b % 8`, **LSB-first** within the byte. Bit value = `(data[byte] >> bitInByte) & 1`. Example: `0x102` bit 18 → byte 2, bit 2. This is the assumed convention (spec Open Question #5); verify against real bus data during hardware bring-up.
- **Domain code** (`src/domain/`) must not include any Arduino/ESP32 headers, so it compiles and tests on the host `native` environment. Hardware code lives only in `src/hal/` and `src/main.cpp`.
- **Unassigned functions** evaluate to `false`, **except `Run`**: if `Run` is unmapped, it evaluates `true` (fail-safe: lights operate out-of-box until the Run bit is discovered — spec Open Question #1).
- **Startup/fallback defaults:** blink period 340 ms, full-orange indicators, baked-in Experia map.
- **Commit** after every task's tests pass.

---

## File Structure

```
platformio.ini
src/
  domain/                    # pure C++, host-testable, no Arduino headers
    color.h                  # Rgb type
    logical_state.h          # LogicalState struct (+ hazards()/brake())
    output_intent.h          # OutputIntent struct
    config.h / config.cpp    # Config struct, Function enum, defaultConfig()
    config_json.h / .cpp     # Config <-> JSON (ArduinoJson), corrupt fallback
    can_state.h / .cpp       # frame cache + evaluate(Config) -> LogicalState
    behavior_engine.h / .cpp # computeOutputs(state, config, now, EngineState)
    channel_map.h / .cpp     # applyIntent(IPwm&, OutputIntent) -> 14 channels
  hal/                       # ESP32-only wrappers
    ipwm.h                   # IPwm interface (shared with domain channel_map)
    pwm_ledc.h / .cpp        # LEDC implementation of IPwm
    can_bus.h / .cpp         # TWAI init + non-blocking receive
    storage.h / .cpp         # LittleFS read/write config string
  main.cpp                   # boot: load config, init HAL, run loop
test/
  test_native/               # Unity tests run under `pio test -e native`
    test_can_state.cpp
    test_behavior_engine.cpp
    test_config_json.cpp
    test_channel_map.cpp
```

`IPwm` lives in `src/hal/ipwm.h` but is a pure abstract interface with no Arduino headers, so `channel_map` (domain) can depend on it and still build on `native`.

---

## Task 1: Project scaffold + host test harness

**Files:**
- Create: `platformio.ini`
- Create: `src/domain/color.h`
- Test: `test/test_native/test_smoke.cpp`

**Interfaces:**
- Produces: `struct Rgb { uint8_t r, g, b; };` with `operator==`, in `src/domain/color.h`.

- [ ] **Step 1: Create `platformio.ini`**

```ini
[env:esp32]
platform = espressif32
board = esp32dev
framework = arduino
build_flags = -std=gnu++17
build_unflags = -std=gnu++11
lib_deps =
    bblanchon/ArduinoJson@^7.0.0
monitor_speed = 115200

[env:native]
platform = native
build_flags = -std=gnu++17 -I src
lib_deps =
    bblanchon/ArduinoJson@^7.0.0
```

- [ ] **Step 2: Create `src/domain/color.h`**

```cpp
#pragma once
#include <cstdint>

struct Rgb {
  uint8_t r = 0, g = 0, b = 0;
};

inline bool operator==(const Rgb& a, const Rgb& b) {
  return a.r == b.r && a.g == b.g && a.b == b.b;
}
inline bool operator!=(const Rgb& a, const Rgb& b) { return !(a == b); }
```

- [ ] **Step 3: Write the smoke test** — `test/test_native/test_smoke.cpp`

```cpp
#include <unity.h>
#include "domain/color.h"

void test_rgb_equality() {
  Rgb a{255, 80, 0};
  Rgb b{255, 80, 0};
  Rgb c{0, 0, 0};
  TEST_ASSERT_TRUE(a == b);
  TEST_ASSERT_TRUE(a != c);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_rgb_equality);
  return UNITY_END();
}
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `pio test -e native`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add platformio.ini src/domain/color.h test/test_native/test_smoke.cpp
git commit -m "chore: scaffold PlatformIO project with native test harness"
```

---

## Task 2: Logical state & output intent types

**Files:**
- Create: `src/domain/logical_state.h`
- Create: `src/domain/output_intent.h`
- Test: `test/test_native/test_types.cpp`

**Interfaces:**
- Produces: `struct LogicalState` with bool fields `run, leftInd, rightInd, frontBrake, rearBrake, lowBeam, highBeam, flash, night, kickstand`, plus `bool hazards() const` (= leftInd && rightInd) and `bool brake() const` (= frontBrake || rearBrake).
- Produces: `struct OutputIntent { Rgb frontL, frontR, rearL, rearR; uint8_t denali; };`

- [ ] **Step 1: Create `src/domain/logical_state.h`**

```cpp
#pragma once

struct LogicalState {
  bool run = false;
  bool leftInd = false;
  bool rightInd = false;
  bool frontBrake = false;
  bool rearBrake = false;
  bool lowBeam = false;
  bool highBeam = false;
  bool flash = false;       // momentary high-beam flash/pass button
  bool night = false;       // day/night mode: true = night
  bool kickstand = false;

  bool hazards() const { return leftInd && rightInd; }
  bool brake() const { return frontBrake || rearBrake; }
};
```

- [ ] **Step 2: Create `src/domain/output_intent.h`**

```cpp
#pragma once
#include "domain/color.h"
#include <cstdint>

struct OutputIntent {
  Rgb frontL, frontR, rearL, rearR;
  uint8_t denali = 0;   // 0-255 duty, applied to both Denali channels
};
```

- [ ] **Step 3: Write the test** — `test/test_native/test_types.cpp`

```cpp
#include <unity.h>
#include "domain/logical_state.h"
#include "domain/output_intent.h"

void test_hazards_requires_both_indicators() {
  LogicalState s;
  s.leftInd = true;
  TEST_ASSERT_FALSE(s.hazards());
  s.rightInd = true;
  TEST_ASSERT_TRUE(s.hazards());
}

void test_brake_is_front_or_rear() {
  LogicalState s;
  TEST_ASSERT_FALSE(s.brake());
  s.rearBrake = true;
  TEST_ASSERT_TRUE(s.brake());
  s.rearBrake = false;
  s.frontBrake = true;
  TEST_ASSERT_TRUE(s.brake());
}

void test_output_intent_defaults_dark() {
  OutputIntent o;
  TEST_ASSERT_TRUE((o.frontL == Rgb{0, 0, 0}));
  TEST_ASSERT_EQUAL_UINT8(0, o.denali);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_hazards_requires_both_indicators);
  RUN_TEST(test_brake_is_front_or_rear);
  RUN_TEST(test_output_intent_defaults_dark);
  return UNITY_END();
}
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `pio test -e native`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/domain/logical_state.h src/domain/output_intent.h test/test_native/test_types.cpp
git commit -m "feat: add LogicalState and OutputIntent domain types"
```

---

## Task 3: Config model + baked-in Experia default profile

**Files:**
- Create: `src/domain/config.h`
- Create: `src/domain/config.cpp`
- Test: `test/test_native/test_config_defaults.cpp`

**Interfaces:**
- Produces: `enum class Function : uint8_t { Run, LeftInd, RightInd, FrontBrake, RearBrake, LowBeam, HighBeam, HighBeamFlash, DayNight, KickStand, COUNT };`
- Produces: `enum class Combine : uint8_t { Single, And, Or };`
- Produces: `struct BitRef { uint32_t id; uint8_t bit; };`
- Produces: `struct FunctionMap { Combine combine; BitRef bits[4]; uint8_t count; };` (count 0 = unassigned)
- Produces: `struct Config { FunctionMap map[(size_t)Function::COUNT]; uint32_t blinkPeriodMs; uint32_t spotHoldMs; Rgb drlWhiteDay, drlWhiteNight, drlDimRedDay, drlDimRedNight, indicatorOrange, brakeRed; uint8_t denaliDay, denaliLow, denaliHigh, denaliSpot; };`
- Produces: `Config defaultConfig();` and `FunctionMap& mapFor(Config&, Function);`

- [ ] **Step 1: Create `src/domain/config.h`**

```cpp
#pragma once
#include "domain/color.h"
#include <cstdint>
#include <cstddef>

enum class Function : uint8_t {
  Run, LeftInd, RightInd, FrontBrake, RearBrake,
  LowBeam, HighBeam, HighBeamFlash, DayNight, KickStand,
  COUNT
};

enum class Combine : uint8_t { Single, And, Or };

struct BitRef { uint32_t id = 0; uint8_t bit = 0; };

struct FunctionMap {
  Combine combine = Combine::Single;
  static constexpr uint8_t MAX_BITS = 4;
  BitRef bits[MAX_BITS];
  uint8_t count = 0;   // 0 = unassigned
};

struct Config {
  FunctionMap map[(size_t)Function::COUNT];

  uint32_t blinkPeriodMs = 340;   // on-time == off-time
  uint32_t spotHoldMs    = 800;   // flash long-press threshold

  Rgb drlWhiteDay    = {255, 255, 255};
  Rgb drlWhiteNight  = {120, 120, 120};
  Rgb drlDimRedDay   = {120, 0, 0};
  Rgb drlDimRedNight = {60, 0, 0};
  Rgb indicatorOrange = {255, 80, 0};
  Rgb brakeRed        = {255, 0, 0};

  uint8_t denaliDay  = 50;
  uint8_t denaliLow  = 128;
  uint8_t denaliHigh = 255;
  uint8_t denaliSpot = 255;
};

Config defaultConfig();
FunctionMap& mapFor(Config& c, Function f);
const FunctionMap& mapFor(const Config& c, Function f);
```

- [ ] **Step 2: Create `src/domain/config.cpp`** (baked-in Experia profile from the spec)

```cpp
#include "domain/config.h"

FunctionMap& mapFor(Config& c, Function f) { return c.map[(size_t)f]; }
const FunctionMap& mapFor(const Config& c, Function f) { return c.map[(size_t)f]; }

static FunctionMap single(uint32_t id, uint8_t bit) {
  FunctionMap m;
  m.combine = Combine::Single;
  m.bits[0] = {id, bit};
  m.count = 1;
  return m;
}

Config defaultConfig() {
  Config c;  // colors/timing use struct defaults above

  // Energica Experia map (spec section 3). Run and DayNight left unassigned
  // (count 0) until discovered; Run unassigned is treated as always-true.
  mapFor(c, Function::LeftInd)   = single(0x102, 18);
  mapFor(c, Function::RightInd)  = single(0x102, 19);
  mapFor(c, Function::FrontBrake)= single(0x102, 21);
  mapFor(c, Function::RearBrake) = single(0x102, 22);
  mapFor(c, Function::LowBeam)   = single(0x102, 7);
  mapFor(c, Function::HighBeamFlash) = single(0x102, 16);
  mapFor(c, Function::KickStand) = single(0x102, 13);

  // High beam = bit 6 AND bit 16 (spec section 3).
  FunctionMap hb;
  hb.combine = Combine::And;
  hb.bits[0] = {0x102, 6};
  hb.bits[1] = {0x102, 16};
  hb.count = 2;
  mapFor(c, Function::HighBeam) = hb;

  return c;
}
```

- [ ] **Step 3: Write the test** — `test/test_native/test_config_defaults.cpp`

```cpp
#include <unity.h>
#include "domain/config.h"

void test_default_timing_and_colors() {
  Config c = defaultConfig();
  TEST_ASSERT_EQUAL_UINT32(340, c.blinkPeriodMs);
  TEST_ASSERT_EQUAL_UINT32(800, c.spotHoldMs);
  TEST_ASSERT_TRUE((c.indicatorOrange == Rgb{255, 80, 0}));
}

void test_experia_indicator_mapping() {
  Config c = defaultConfig();
  const FunctionMap& left = mapFor(c, Function::LeftInd);
  TEST_ASSERT_EQUAL_UINT8(1, left.count);
  TEST_ASSERT_EQUAL_HEX32(0x102, left.bits[0].id);
  TEST_ASSERT_EQUAL_UINT8(18, left.bits[0].bit);
}

void test_experia_highbeam_is_and_of_two_bits() {
  Config c = defaultConfig();
  const FunctionMap& hb = mapFor(c, Function::HighBeam);
  TEST_ASSERT_EQUAL(Combine::And, hb.combine);
  TEST_ASSERT_EQUAL_UINT8(2, hb.count);
  TEST_ASSERT_EQUAL_UINT8(6, hb.bits[0].bit);
  TEST_ASSERT_EQUAL_UINT8(16, hb.bits[1].bit);
}

void test_run_and_daynight_unassigned() {
  Config c = defaultConfig();
  TEST_ASSERT_EQUAL_UINT8(0, mapFor(c, Function::Run).count);
  TEST_ASSERT_EQUAL_UINT8(0, mapFor(c, Function::DayNight).count);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_default_timing_and_colors);
  RUN_TEST(test_experia_indicator_mapping);
  RUN_TEST(test_experia_highbeam_is_and_of_two_bits);
  RUN_TEST(test_run_and_daynight_unassigned);
  return UNITY_END();
}
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `pio test -e native`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/domain/config.h src/domain/config.cpp test/test_native/test_config_defaults.cpp
git commit -m "feat: add Config model with baked-in Experia default profile"
```

---

## Task 4: CAN state cache + logical-function evaluation

**Files:**
- Create: `src/domain/can_state.h`
- Create: `src/domain/can_state.cpp`
- Test: `test/test_native/test_can_state.cpp`

**Interfaces:**
- Consumes: `Config`, `FunctionMap`, `Function`, `Combine` (Task 3); `LogicalState` (Task 2).
- Produces: `class CanState` with `void update(uint32_t id, const uint8_t data[8]); bool getBit(uint32_t id, uint8_t bit) const; LogicalState evaluate(const Config& cfg) const;`
- Bit convention per Global Constraints: `byte = bit/8`, `pos = bit%8`, LSB-first.

- [ ] **Step 1: Write the failing test** — `test/test_native/test_can_state.cpp`

```cpp
#include <unity.h>
#include "domain/can_state.h"
#include "domain/config.h"

static void setBit(uint8_t data[8], uint8_t bit) {
  data[bit / 8] |= (uint8_t)(1u << (bit % 8));
}

void test_getbit_reads_lsb_first() {
  CanState cs;
  uint8_t data[8] = {0};
  setBit(data, 18);              // byte 2, bit 2
  cs.update(0x102, data);
  TEST_ASSERT_TRUE(cs.getBit(0x102, 18));
  TEST_ASSERT_FALSE(cs.getBit(0x102, 17));
  TEST_ASSERT_FALSE(cs.getBit(0x400, 18));   // unseen id -> false
}

void test_single_bit_function_maps_to_state() {
  CanState cs;
  uint8_t data[8] = {0};
  setBit(data, 18);              // left indicator
  setBit(data, 21);              // front brake
  cs.update(0x102, data);
  LogicalState s = cs.evaluate(defaultConfig());
  TEST_ASSERT_TRUE(s.leftInd);
  TEST_ASSERT_FALSE(s.rightInd);
  TEST_ASSERT_TRUE(s.frontBrake);
  TEST_ASSERT_TRUE(s.brake());
}

void test_and_combine_needs_all_bits() {
  CanState cs;
  uint8_t data[8] = {0};
  setBit(data, 6);               // only one of the two high-beam bits
  cs.update(0x102, data);
  TEST_ASSERT_FALSE(cs.evaluate(defaultConfig()).highBeam);
  setBit(data, 16);              // now both bits 6 and 16
  cs.update(0x102, data);
  TEST_ASSERT_TRUE(cs.evaluate(defaultConfig()).highBeam);
}

void test_run_unassigned_is_true() {
  CanState cs;
  uint8_t data[8] = {0};
  cs.update(0x102, data);
  TEST_ASSERT_TRUE(cs.evaluate(defaultConfig()).run);  // Run unmapped -> true
}

void test_daynight_unassigned_is_false() {
  CanState cs;
  uint8_t data[8] = {0};
  cs.update(0x102, data);
  TEST_ASSERT_FALSE(cs.evaluate(defaultConfig()).night);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_getbit_reads_lsb_first);
  RUN_TEST(test_single_bit_function_maps_to_state);
  RUN_TEST(test_and_combine_needs_all_bits);
  RUN_TEST(test_run_unassigned_is_true);
  RUN_TEST(test_daynight_unassigned_is_false);
  return UNITY_END();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pio test -e native -f test_can_state`
Expected: FAIL (can_state.h not found / undefined).

- [ ] **Step 3: Create `src/domain/can_state.h`**

```cpp
#pragma once
#include "domain/config.h"
#include "domain/logical_state.h"
#include <cstdint>

class CanState {
public:
  void update(uint32_t id, const uint8_t data[8]);
  bool getBit(uint32_t id, uint8_t bit) const;
  LogicalState evaluate(const Config& cfg) const;

private:
  static constexpr int MAX_FRAMES = 16;
  struct Frame { uint32_t id = 0; uint8_t data[8] = {0}; bool seen = false; };
  Frame frames_[MAX_FRAMES];

  const Frame* find(uint32_t id) const;
  bool evalFunction(const FunctionMap& fm) const;
};
```

- [ ] **Step 4: Create `src/domain/can_state.cpp`**

```cpp
#include "domain/can_state.h"
#include <cstring>

const CanState::Frame* CanState::find(uint32_t id) const {
  for (const auto& f : frames_) {
    if (f.seen && f.id == id) return &f;
  }
  return nullptr;
}

void CanState::update(uint32_t id, const uint8_t data[8]) {
  for (auto& f : frames_) {                 // update existing
    if (f.seen && f.id == id) {
      std::memcpy(f.data, data, 8);
      return;
    }
  }
  for (auto& f : frames_) {                 // insert into free slot
    if (!f.seen) {
      f.seen = true;
      f.id = id;
      std::memcpy(f.data, data, 8);
      return;
    }
  }
  // table full: ignore new ids (16 distinct ids is ample for this use).
}

bool CanState::getBit(uint32_t id, uint8_t bit) const {
  const Frame* f = find(id);
  if (!f) return false;
  return (f->data[bit / 8] >> (bit % 8)) & 0x01;
}

bool CanState::evalFunction(const FunctionMap& fm) const {
  if (fm.count == 0) return false;          // unassigned
  switch (fm.combine) {
    case Combine::Single:
      return getBit(fm.bits[0].id, fm.bits[0].bit);
    case Combine::And:
      for (uint8_t i = 0; i < fm.count; ++i)
        if (!getBit(fm.bits[i].id, fm.bits[i].bit)) return false;
      return true;
    case Combine::Or:
      for (uint8_t i = 0; i < fm.count; ++i)
        if (getBit(fm.bits[i].id, fm.bits[i].bit)) return true;
      return false;
  }
  return false;
}

LogicalState CanState::evaluate(const Config& cfg) const {
  LogicalState s;
  s.leftInd    = evalFunction(mapFor(cfg, Function::LeftInd));
  s.rightInd   = evalFunction(mapFor(cfg, Function::RightInd));
  s.frontBrake = evalFunction(mapFor(cfg, Function::FrontBrake));
  s.rearBrake  = evalFunction(mapFor(cfg, Function::RearBrake));
  s.lowBeam    = evalFunction(mapFor(cfg, Function::LowBeam));
  s.highBeam   = evalFunction(mapFor(cfg, Function::HighBeam));
  s.flash      = evalFunction(mapFor(cfg, Function::HighBeamFlash));
  s.night      = evalFunction(mapFor(cfg, Function::DayNight));
  s.kickstand  = evalFunction(mapFor(cfg, Function::KickStand));

  // Run: unassigned means always-running (fail-safe, spec Open Question #1).
  const FunctionMap& runMap = mapFor(cfg, Function::Run);
  s.run = (runMap.count == 0) ? true : evalFunction(runMap);
  return s;
}
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `pio test -e native -f test_can_state`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/domain/can_state.h src/domain/can_state.cpp test/test_native/test_can_state.cpp
git commit -m "feat: add CAN frame cache and logical-function evaluation"
```

---

## Task 5: Behavior engine — corner matrix + flash timing

**Files:**
- Create: `src/domain/behavior_engine.h`
- Create: `src/domain/behavior_engine.cpp`
- Test: `test/test_native/test_behavior_engine.cpp`

**Interfaces:**
- Consumes: `LogicalState` (Task 2), `Config` (Task 3), `OutputIntent`/`Rgb` (Tasks 1-2).
- Produces: `struct EngineState { bool spotLatched; bool flashPrev; uint32_t flashRisingMs; };`
- Produces: `OutputIntent computeOutputs(const LogicalState& s, const Config& cfg, uint32_t nowMs, EngineState& est);`
- This task implements the corner RGB logic + flash timing; Task 6 extends the same function with Denali/spot logic. Denali is set to 0 in this task and finalized in Task 6.

- [ ] **Step 1: Write the failing test** — `test/test_native/test_behavior_engine.cpp`

```cpp
#include <unity.h>
#include "domain/behavior_engine.h"
#include "domain/config.h"

static Config cfg;
static const Rgb OFF{0, 0, 0};

void setUp(void) { cfg = defaultConfig(); }
void tearDown(void) {}

// nowMs = 0 is within the "on" half of the blink cycle.
static uint32_t FLASH_ON = 0;
static uint32_t flashOffTime() { return cfg.blinkPeriodMs; }  // start of off-half

void test_drl_default_day() {
  LogicalState s; s.run = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((o.frontL == cfg.drlWhiteDay));
  TEST_ASSERT_TRUE((o.frontR == cfg.drlWhiteDay));
  TEST_ASSERT_TRUE((o.rearL == cfg.drlDimRedDay));
  TEST_ASSERT_TRUE((o.rearR == cfg.drlDimRedDay));
}

void test_drl_default_night_uses_night_colors() {
  LogicalState s; s.run = true; s.night = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((o.frontL == cfg.drlWhiteNight));
  TEST_ASSERT_TRUE((o.rearL == cfg.drlDimRedNight));
}

void test_left_indicator_flashes_left_corners_on_phase() {
  LogicalState s; s.run = true; s.leftInd = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((o.frontL == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((o.rearL == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((o.frontR == cfg.drlWhiteDay));   // right side unaffected
  TEST_ASSERT_TRUE((o.rearR == cfg.drlDimRedDay));
}

void test_indicator_off_phase_is_fully_dark() {
  LogicalState s; s.run = true; s.leftInd = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, flashOffTime(), est);
  TEST_ASSERT_TRUE((o.frontL == OFF));
  TEST_ASSERT_TRUE((o.rearL == OFF));
}

void test_hazards_flash_all_four() {
  LogicalState s; s.run = true; s.leftInd = true; s.rightInd = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((o.frontL == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((o.frontR == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((o.rearL == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((o.rearR == cfg.indicatorOrange));
}

void test_brake_lights_both_rears_full_red() {
  LogicalState s; s.run = true; s.rearBrake = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((o.rearL == cfg.brakeRed));
  TEST_ASSERT_TRUE((o.rearR == cfg.brakeRed));
  TEST_ASSERT_TRUE((o.frontL == cfg.drlWhiteDay));
}

void test_brake_plus_left_indicator_priority() {
  LogicalState s; s.run = true; s.frontBrake = true; s.leftInd = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((o.rearL == cfg.indicatorOrange));  // indicator wins on left
  TEST_ASSERT_TRUE((o.rearR == cfg.brakeRed));         // right rear brakes
  TEST_ASSERT_TRUE((o.frontL == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((o.frontR == cfg.drlWhiteDay));
}

void test_brake_plus_left_indicator_off_phase_left_is_dark() {
  LogicalState s; s.run = true; s.frontBrake = true; s.leftInd = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, flashOffTime(), est);
  TEST_ASSERT_TRUE((o.rearL == OFF));       // fully dark, brake suppressed
  TEST_ASSERT_TRUE((o.rearR == cfg.brakeRed));
}

void test_not_run_drl_off_but_indicator_works() {
  LogicalState s; s.run = false; s.leftInd = true;
  EngineState est{};
  OutputIntent on = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((on.frontL == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((on.rearL == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((on.frontR == OFF));     // non-indicating corners dark
  TEST_ASSERT_TRUE((on.rearR == OFF));
}

void test_not_run_brake_ignored() {
  LogicalState s; s.run = false; s.rearBrake = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((o.rearL == OFF));
  TEST_ASSERT_TRUE((o.rearR == OFF));
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_drl_default_day);
  RUN_TEST(test_drl_default_night_uses_night_colors);
  RUN_TEST(test_left_indicator_flashes_left_corners_on_phase);
  RUN_TEST(test_indicator_off_phase_is_fully_dark);
  RUN_TEST(test_hazards_flash_all_four);
  RUN_TEST(test_brake_lights_both_rears_full_red);
  RUN_TEST(test_brake_plus_left_indicator_priority);
  RUN_TEST(test_brake_plus_left_indicator_off_phase_left_is_dark);
  RUN_TEST(test_not_run_drl_off_but_indicator_works);
  RUN_TEST(test_not_run_brake_ignored);
  return UNITY_END();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pio test -e native -f test_behavior_engine`
Expected: FAIL (behavior_engine.h not found).

- [ ] **Step 3: Create `src/domain/behavior_engine.h`**

```cpp
#pragma once
#include "domain/logical_state.h"
#include "domain/output_intent.h"
#include "domain/config.h"
#include <cstdint>

struct EngineState {
  bool spotLatched = false;
  bool flashPrev = false;
  uint32_t flashRisingMs = 0;
};

OutputIntent computeOutputs(const LogicalState& s, const Config& cfg,
                            uint32_t nowMs, EngineState& est);
```

- [ ] **Step 4: Create `src/domain/behavior_engine.cpp`** (Denali set to 0 here; finalized in Task 6)

```cpp
#include "domain/behavior_engine.h"

static const Rgb OFF{0, 0, 0};

static bool flashIsOn(const Config& cfg, uint32_t nowMs) {
  uint32_t period = cfg.blinkPeriodMs ? cfg.blinkPeriodMs : 340;
  return (nowMs % (2 * period)) < period;
}

OutputIntent computeOutputs(const LogicalState& s, const Config& cfg,
                            uint32_t nowMs, EngineState& est) {
  OutputIntent o;
  const bool on = flashIsOn(cfg, nowMs);
  const Rgb orange = cfg.indicatorOrange;
  const Rgb white  = s.night ? cfg.drlWhiteNight : cfg.drlWhiteDay;
  const Rgb dimRed = s.night ? cfg.drlDimRedNight : cfg.drlDimRedDay;
  const Rgb flashCol = on ? orange : OFF;

  if (!s.run) {
    // DRL & brake off; indicators/hazards still function.
    o.frontL = s.leftInd  ? flashCol : OFF;
    o.frontR = s.rightInd ? flashCol : OFF;
    o.rearL  = s.leftInd  ? flashCol : OFF;
    o.rearR  = s.rightInd ? flashCol : OFF;
  } else {
    const bool brakeOn = s.brake();
    o.frontL = s.leftInd  ? flashCol : white;
    o.frontR = s.rightInd ? flashCol : white;
    o.rearL  = s.leftInd  ? flashCol : (brakeOn ? cfg.brakeRed : dimRed);
    o.rearR  = s.rightInd ? flashCol : (brakeOn ? cfg.brakeRed : dimRed);
  }

  o.denali = 0;  // finalized in Task 6
  return o;
}
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `pio test -e native -f test_behavior_engine`
Expected: PASS (10 tests).

- [ ] **Step 6: Commit**

```bash
git add src/domain/behavior_engine.h src/domain/behavior_engine.cpp test/test_native/test_behavior_engine.cpp
git commit -m "feat: add behavior engine corner matrix and flash timing"
```

---

## Task 6: Behavior engine — Denali modes + spot latch

**Files:**
- Modify: `src/domain/behavior_engine.cpp` (replace the `o.denali = 0` line with real logic)
- Modify: `test/test_native/test_behavior_engine.cpp` (add Denali/spot tests + register them)

**Interfaces:**
- Consumes/Produces: same `computeOutputs` signature and `EngineState` from Task 5. This task fills in `EngineState.spotLatched`, `flashPrev`, `flashRisingMs` behavior and the `o.denali` value.

- [ ] **Step 1: Add failing Denali/spot tests** to `test/test_native/test_behavior_engine.cpp` (add these functions and register each with `RUN_TEST` in `main`)

```cpp
void test_denali_off_when_not_run() {
  LogicalState s; s.run = false;
  EngineState est{};
  TEST_ASSERT_EQUAL_UINT8(0, computeOutputs(s, cfg, 0, est).denali);
}

void test_denali_daytime_level() {
  LogicalState s; s.run = true;              // day, no beams
  EngineState est{};
  TEST_ASSERT_EQUAL_UINT8(cfg.denaliDay, computeOutputs(s, cfg, 0, est).denali);
}

void test_denali_low_when_night_or_lowbeam() {
  LogicalState s; s.run = true; s.lowBeam = true;
  EngineState est{};
  TEST_ASSERT_EQUAL_UINT8(cfg.denaliLow, computeOutputs(s, cfg, 0, est).denali);
}

void test_denali_high_beam_level() {
  LogicalState s; s.run = true; s.highBeam = true;
  EngineState est{};
  TEST_ASSERT_EQUAL_UINT8(cfg.denaliHigh, computeOutputs(s, cfg, 0, est).denali);
}

void test_spot_latches_after_hold_then_persists() {
  LogicalState s; s.run = true; s.highBeam = true; s.flash = true;
  EngineState est{};
  // t=0 flash pressed (rising edge), not yet held long enough
  TEST_ASSERT_EQUAL_UINT8(cfg.denaliHigh, computeOutputs(s, cfg, 0, est).denali);
  // t=spotHoldMs: held long enough -> latches to spot level
  TEST_ASSERT_EQUAL_UINT8(cfg.denaliSpot,
                          computeOutputs(s, cfg, cfg.spotHoldMs, est).denali);
  // release flash, still high beam -> spot stays latched
  s.flash = false;
  TEST_ASSERT_EQUAL_UINT8(cfg.denaliSpot,
                          computeOutputs(s, cfg, cfg.spotHoldMs + 500, est).denali);
}

void test_spot_auto_drops_on_low_beam() {
  LogicalState s; s.run = true; s.highBeam = true; s.flash = true;
  EngineState est{};
  computeOutputs(s, cfg, 0, est);
  computeOutputs(s, cfg, cfg.spotHoldMs, est);       // latched
  TEST_ASSERT_TRUE(est.spotLatched);
  // rider selects low beam -> spot drops
  LogicalState low; low.run = true; low.lowBeam = true;
  OutputIntent o = computeOutputs(low, cfg, cfg.spotHoldMs + 100, est);
  TEST_ASSERT_FALSE(est.spotLatched);
  TEST_ASSERT_EQUAL_UINT8(cfg.denaliLow, o.denali);
}

void test_short_flash_press_does_not_latch() {
  LogicalState s; s.run = true; s.highBeam = true; s.flash = true;
  EngineState est{};
  computeOutputs(s, cfg, 0, est);                    // rising edge
  computeOutputs(s, cfg, cfg.spotHoldMs - 50, est);  // released early below
  s.flash = false;
  computeOutputs(s, cfg, cfg.spotHoldMs - 40, est);
  TEST_ASSERT_FALSE(est.spotLatched);
}
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `pio test -e native -f test_behavior_engine`
Expected: FAIL (Denali still 0; spot never latches).

- [ ] **Step 3: Replace the Denali line in `src/domain/behavior_engine.cpp`**

Remove `o.denali = 0;  // finalized in Task 6` and insert before `return o;`:

```cpp
  // --- Spot latch state machine (flash long-press) ---
  if (s.lowBeam) {
    est.spotLatched = false;                 // auto-drop on low beam
  }
  if (s.flash && !est.flashPrev) {
    est.flashRisingMs = nowMs;               // rising edge: start hold timer
  }
  if (s.flash && (nowMs - est.flashRisingMs) >= cfg.spotHoldMs) {
    est.spotLatched = true;
  }
  est.flashPrev = s.flash;

  // --- Denali level selection ---
  if (!s.run) {
    o.denali = 0;
  } else if (est.spotLatched) {
    o.denali = cfg.denaliSpot;
  } else if (s.highBeam) {
    o.denali = cfg.denaliHigh;
  } else if (s.lowBeam || s.night) {
    o.denali = cfg.denaliLow;
  } else {
    o.denali = cfg.denaliDay;
  }
```

- [ ] **Step 4: Run all behavior tests, verify they pass**

Run: `pio test -e native -f test_behavior_engine`
Expected: PASS (all corner + Denali/spot tests).

- [ ] **Step 5: Commit**

```bash
git add src/domain/behavior_engine.cpp test/test_native/test_behavior_engine.cpp
git commit -m "feat: add Denali mode selection and spot-latch state machine"
```

---

## Task 7: Config JSON serialization + corrupt fallback

**Files:**
- Create: `src/domain/config_json.h`
- Create: `src/domain/config_json.cpp`
- Test: `test/test_native/test_config_json.cpp`

**Interfaces:**
- Consumes: `Config`, `Function`, `Combine`, `FunctionMap`, `BitRef` (Task 3).
- Produces: `std::string configToJson(const Config& c);` and `Config configFromJson(const std::string& json, bool& ok);` — on parse failure `ok=false` and the return is `defaultConfig()`.
- Uses ArduinoJson (works on the `native` env via `lib_deps`).

- [ ] **Step 1: Write the failing test** — `test/test_native/test_config_json.cpp`

```cpp
#include <unity.h>
#include "domain/config_json.h"
#include "domain/config.h"

void test_roundtrip_preserves_mapping_and_tunables() {
  Config in = defaultConfig();
  in.blinkPeriodMs = 500;
  in.denaliSpot = 200;
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_EQUAL_UINT32(500, out.blinkPeriodMs);
  TEST_ASSERT_EQUAL_UINT8(200, out.denaliSpot);
  const FunctionMap& hb = mapFor(out, Function::HighBeam);
  TEST_ASSERT_EQUAL(Combine::And, hb.combine);
  TEST_ASSERT_EQUAL_UINT8(2, hb.count);
  TEST_ASSERT_EQUAL_UINT8(16, hb.bits[1].bit);
  const FunctionMap& left = mapFor(out, Function::LeftInd);
  TEST_ASSERT_EQUAL_HEX32(0x102, left.bits[0].id);
  TEST_ASSERT_EQUAL_UINT8(18, left.bits[0].bit);
}

void test_roundtrip_preserves_colors() {
  Config in = defaultConfig();
  in.indicatorOrange = {250, 90, 5};
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE((out.indicatorOrange == Rgb{250, 90, 5}));
}

void test_corrupt_json_falls_back_to_default() {
  bool ok = true;
  Config out = configFromJson("{not valid json", ok);
  TEST_ASSERT_FALSE(ok);
  TEST_ASSERT_EQUAL_UINT32(340, out.blinkPeriodMs);       // default
  TEST_ASSERT_EQUAL_UINT8(1, mapFor(out, Function::LeftInd).count);
}

void test_empty_string_falls_back_to_default() {
  bool ok = true;
  Config out = configFromJson("", ok);
  TEST_ASSERT_FALSE(ok);
  TEST_ASSERT_EQUAL_UINT32(340, out.blinkPeriodMs);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_roundtrip_preserves_mapping_and_tunables);
  RUN_TEST(test_roundtrip_preserves_colors);
  RUN_TEST(test_corrupt_json_falls_back_to_default);
  RUN_TEST(test_empty_string_falls_back_to_default);
  return UNITY_END();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pio test -e native -f test_config_json`
Expected: FAIL (config_json.h not found).

- [ ] **Step 3: Create `src/domain/config_json.h`**

```cpp
#pragma once
#include "domain/config.h"
#include <string>

std::string configToJson(const Config& c);
Config configFromJson(const std::string& json, bool& ok);
```

- [ ] **Step 4: Create `src/domain/config_json.cpp`**

```cpp
#include "domain/config_json.h"
#include <ArduinoJson.h>

static const char* kFuncNames[(size_t)Function::COUNT] = {
  "run", "leftInd", "rightInd", "frontBrake", "rearBrake",
  "lowBeam", "highBeam", "highBeamFlash", "dayNight", "kickStand"
};

static void rgbTo(JsonArray a, const Rgb& c) { a.add(c.r); a.add(c.g); a.add(c.b); }
static Rgb rgbFrom(JsonArrayConst a, Rgb def) {
  if (a.size() != 3) return def;
  return Rgb{ (uint8_t)a[0].as<int>(), (uint8_t)a[1].as<int>(), (uint8_t)a[2].as<int>() };
}

std::string configToJson(const Config& c) {
  JsonDocument doc;

  JsonObject maps = doc["maps"].to<JsonObject>();
  for (size_t i = 0; i < (size_t)Function::COUNT; ++i) {
    const FunctionMap& fm = c.map[i];
    JsonObject m = maps[kFuncNames[i]].to<JsonObject>();
    m["combine"] = (int)fm.combine;
    JsonArray bits = m["bits"].to<JsonArray>();
    for (uint8_t b = 0; b < fm.count; ++b) {
      JsonObject br = bits.add<JsonObject>();
      br["id"] = fm.bits[b].id;
      br["bit"] = fm.bits[b].bit;
    }
  }

  doc["blinkPeriodMs"] = c.blinkPeriodMs;
  doc["spotHoldMs"] = c.spotHoldMs;

  JsonObject col = doc["colors"].to<JsonObject>();
  rgbTo(col["drlWhiteDay"].to<JsonArray>(), c.drlWhiteDay);
  rgbTo(col["drlWhiteNight"].to<JsonArray>(), c.drlWhiteNight);
  rgbTo(col["drlDimRedDay"].to<JsonArray>(), c.drlDimRedDay);
  rgbTo(col["drlDimRedNight"].to<JsonArray>(), c.drlDimRedNight);
  rgbTo(col["indicatorOrange"].to<JsonArray>(), c.indicatorOrange);
  rgbTo(col["brakeRed"].to<JsonArray>(), c.brakeRed);

  JsonObject den = doc["denali"].to<JsonObject>();
  den["day"] = c.denaliDay;
  den["low"] = c.denaliLow;
  den["high"] = c.denaliHigh;
  den["spot"] = c.denaliSpot;

  std::string out;
  serializeJson(doc, out);
  return out;
}

Config configFromJson(const std::string& json, bool& ok) {
  JsonDocument doc;
  if (deserializeJson(doc, json) != DeserializationError::Ok) {
    ok = false;
    return defaultConfig();
  }
  ok = true;
  Config c = defaultConfig();   // start from defaults, override present fields

  JsonObjectConst maps = doc["maps"];
  if (!maps.isNull()) {
    for (size_t i = 0; i < (size_t)Function::COUNT; ++i) {
      JsonObjectConst m = maps[kFuncNames[i]];
      if (m.isNull()) continue;
      FunctionMap fm;
      fm.combine = (Combine)(m["combine"] | 0);
      JsonArrayConst bits = m["bits"];
      uint8_t n = 0;
      for (JsonObjectConst br : bits) {
        if (n >= FunctionMap::MAX_BITS) break;
        fm.bits[n].id = br["id"] | 0u;
        fm.bits[n].bit = (uint8_t)(br["bit"] | 0);
        ++n;
      }
      fm.count = n;
      c.map[i] = fm;
    }
  }

  c.blinkPeriodMs = doc["blinkPeriodMs"] | c.blinkPeriodMs;
  c.spotHoldMs = doc["spotHoldMs"] | c.spotHoldMs;

  JsonObjectConst col = doc["colors"];
  if (!col.isNull()) {
    c.drlWhiteDay = rgbFrom(col["drlWhiteDay"], c.drlWhiteDay);
    c.drlWhiteNight = rgbFrom(col["drlWhiteNight"], c.drlWhiteNight);
    c.drlDimRedDay = rgbFrom(col["drlDimRedDay"], c.drlDimRedDay);
    c.drlDimRedNight = rgbFrom(col["drlDimRedNight"], c.drlDimRedNight);
    c.indicatorOrange = rgbFrom(col["indicatorOrange"], c.indicatorOrange);
    c.brakeRed = rgbFrom(col["brakeRed"], c.brakeRed);
  }

  JsonObjectConst den = doc["denali"];
  if (!den.isNull()) {
    c.denaliDay = (uint8_t)(den["day"] | c.denaliDay);
    c.denaliLow = (uint8_t)(den["low"] | c.denaliLow);
    c.denaliHigh = (uint8_t)(den["high"] | c.denaliHigh);
    c.denaliSpot = (uint8_t)(den["spot"] | c.denaliSpot);
  }

  return c;
}
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `pio test -e native -f test_config_json`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/domain/config_json.h src/domain/config_json.cpp test/test_native/test_config_json.cpp
git commit -m "feat: add Config JSON serialization with corrupt-file fallback"
```

---

## Task 8: Channel map (OutputIntent → 14 PWM channels)

**Files:**
- Create: `src/hal/ipwm.h`
- Create: `src/domain/channel_map.h`
- Create: `src/domain/channel_map.cpp`
- Test: `test/test_native/test_channel_map.cpp`

**Interfaces:**
- Produces: `class IPwm { public: virtual ~IPwm() = default; virtual void setDuty(uint8_t channel, uint8_t duty) = 0; };` in `src/hal/ipwm.h` (no Arduino headers, host-safe).
- Produces: channel index constants and `void applyIntent(IPwm& pwm, const OutputIntent& o);` in `channel_map.h`.
- Channel layout: `0..2` frontL RGB, `3..5` frontR RGB, `6..8` rearL RGB, `9..11` rearR RGB, `12` Denali A, `13` Denali B (both written with `o.denali`).

- [ ] **Step 1: Write the failing test** — `test/test_native/test_channel_map.cpp`

```cpp
#include <unity.h>
#include "domain/channel_map.h"

class FakePwm : public IPwm {
public:
  uint8_t duty[14] = {0};
  void setDuty(uint8_t ch, uint8_t d) override { if (ch < 14) duty[ch] = d; }
};

void test_applies_all_corners_and_both_denali() {
  OutputIntent o;
  o.frontL = {1, 2, 3};
  o.frontR = {4, 5, 6};
  o.rearL  = {7, 8, 9};
  o.rearR  = {10, 11, 12};
  o.denali = 200;
  FakePwm pwm;
  applyIntent(pwm, o);
  TEST_ASSERT_EQUAL_UINT8(1, pwm.duty[0]);   // frontL R
  TEST_ASSERT_EQUAL_UINT8(3, pwm.duty[2]);   // frontL B
  TEST_ASSERT_EQUAL_UINT8(4, pwm.duty[3]);   // frontR R
  TEST_ASSERT_EQUAL_UINT8(9, pwm.duty[8]);   // rearL B
  TEST_ASSERT_EQUAL_UINT8(12, pwm.duty[11]); // rearR B
  TEST_ASSERT_EQUAL_UINT8(200, pwm.duty[12]); // Denali A
  TEST_ASSERT_EQUAL_UINT8(200, pwm.duty[13]); // Denali B
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_applies_all_corners_and_both_denali);
  return UNITY_END();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pio test -e native -f test_channel_map`
Expected: FAIL (headers not found).

- [ ] **Step 3: Create `src/hal/ipwm.h`**

```cpp
#pragma once
#include <cstdint>

class IPwm {
public:
  virtual ~IPwm() = default;
  virtual void setDuty(uint8_t channel, uint8_t duty) = 0;
};
```

- [ ] **Step 4: Create `src/domain/channel_map.h`**

```cpp
#pragma once
#include "domain/output_intent.h"
#include "hal/ipwm.h"

enum ChannelIndex : uint8_t {
  CH_FRONTL_R = 0, CH_FRONTL_G, CH_FRONTL_B,
  CH_FRONTR_R,     CH_FRONTR_G, CH_FRONTR_B,
  CH_REARL_R,      CH_REARL_G,  CH_REARL_B,
  CH_REARR_R,      CH_REARR_G,  CH_REARR_B,
  CH_DENALI_A,     CH_DENALI_B,
  CH_COUNT   // = 14
};

void applyIntent(IPwm& pwm, const OutputIntent& o);
```

- [ ] **Step 5: Create `src/domain/channel_map.cpp`**

```cpp
#include "domain/channel_map.h"

static void applyRgb(IPwm& pwm, uint8_t baseCh, const Rgb& c) {
  pwm.setDuty(baseCh + 0, c.r);
  pwm.setDuty(baseCh + 1, c.g);
  pwm.setDuty(baseCh + 2, c.b);
}

void applyIntent(IPwm& pwm, const OutputIntent& o) {
  applyRgb(pwm, CH_FRONTL_R, o.frontL);
  applyRgb(pwm, CH_FRONTR_R, o.frontR);
  applyRgb(pwm, CH_REARL_R,  o.rearL);
  applyRgb(pwm, CH_REARR_R,  o.rearR);
  pwm.setDuty(CH_DENALI_A, o.denali);
  pwm.setDuty(CH_DENALI_B, o.denali);
}
```

- [ ] **Step 6: Run tests, verify they pass**

Run: `pio test -e native -f test_channel_map`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/hal/ipwm.h src/domain/channel_map.h src/domain/channel_map.cpp test/test_native/test_channel_map.cpp
git commit -m "feat: map OutputIntent to 14 PWM channels behind IPwm interface"
```

---

## Task 9: Hardware layer + boot wiring

This task has no host unit tests (it touches ESP32 peripherals). Its deliverable is a firmware image that builds for the ESP32 and passes the documented bench smoke test. Keep each HAL file thin — logic already lives in tested domain code.

**Files:**
- Create: `src/hal/pwm_ledc.h`, `src/hal/pwm_ledc.cpp`
- Create: `src/hal/can_bus.h`, `src/hal/can_bus.cpp`
- Create: `src/hal/storage.h`, `src/hal/storage.cpp`
- Create: `src/main.cpp`

**Interfaces:**
- `class LedcPwm : public IPwm` — constructs from a `const uint8_t pins[CH_COUNT]`, sets up one LEDC channel per pin (8-bit, 5 kHz), implements `setDuty`.
- `class CanBus { public: bool begin(uint32_t bitrateBps); bool receive(uint32_t& id, uint8_t data[8]); };` — non-blocking receive, returns false when no frame is pending.
- `namespace storage { std::string readConfig(); bool writeConfig(const std::string&); }` — LittleFS-backed `/config.json`.

- [ ] **Step 1: Create `src/hal/pwm_ledc.h` / `.cpp`**

`pwm_ledc.h`:
```cpp
#pragma once
#include "hal/ipwm.h"
#include "domain/channel_map.h"

class LedcPwm : public IPwm {
public:
  void begin(const uint8_t pins[CH_COUNT]);
  void setDuty(uint8_t channel, uint8_t duty) override;
};
```

`pwm_ledc.cpp`:
```cpp
#include "hal/pwm_ledc.h"
#include <Arduino.h>

// LEDC: 8-bit resolution (0-255 maps directly to duty), 5 kHz.
static constexpr uint32_t kFreqHz = 5000;
static constexpr uint8_t  kResBits = 8;

void LedcPwm::begin(const uint8_t pins[CH_COUNT]) {
  for (uint8_t ch = 0; ch < CH_COUNT; ++ch) {
    ledcSetup(ch, kFreqHz, kResBits);
    ledcAttachPin(pins[ch], ch);
    ledcWrite(ch, 0);
  }
}

void LedcPwm::setDuty(uint8_t channel, uint8_t duty) {
  if (channel < CH_COUNT) ledcWrite(channel, duty);
}
```

- [ ] **Step 2: Create `src/hal/can_bus.h` / `.cpp`** (ESP32 TWAI driver)

`can_bus.h`:
```cpp
#pragma once
#include <cstdint>

class CanBus {
public:
  // rxPin/txPin are the transceiver GPIOs; set in main.cpp (PCB-defined).
  bool begin(int rxPin, int txPin, uint32_t bitrateBps);
  bool receive(uint32_t& id, uint8_t data[8]);   // non-blocking
};
```

`can_bus.cpp`:
```cpp
#include "hal/can_bus.h"
#include "driver/twai.h"

bool CanBus::begin(int rxPin, int txPin, uint32_t bitrateBps) {
  twai_general_config_t g = TWAI_GENERAL_CONFIG_DEFAULT(
      (gpio_num_t)txPin, (gpio_num_t)rxPin, TWAI_MODE_LISTEN_ONLY);
  // Experia bus speed assumed 500 kbps (verify during bring-up).
  twai_timing_config_t t = TWAI_TIMING_CONFIG_500KBITS();
  (void)bitrateBps;  // hook for future configurable bitrate
  twai_filter_config_t f = TWAI_FILTER_CONFIG_ACCEPT_ALL();
  if (twai_driver_install(&g, &t, &f) != ESP_OK) return false;
  return twai_start() == ESP_OK;
}

bool CanBus::receive(uint32_t& id, uint8_t data[8]) {
  twai_message_t msg;
  if (twai_receive(&msg, 0) != ESP_OK) return false;   // 0 ticks = non-blocking
  id = msg.identifier;
  for (int i = 0; i < 8; ++i) data[i] = (i < msg.data_length_code) ? msg.data[i] : 0;
  return true;
}
```

Note: `TWAI_MODE_LISTEN_ONLY` — the controller only reads the bus and never transmits (correct for a lighting accessory).

- [ ] **Step 3: Create `src/hal/storage.h` / `.cpp`** (LittleFS)

`storage.h`:
```cpp
#pragma once
#include <string>

namespace storage {
  bool begin();
  std::string readConfig();               // "" if missing
  bool writeConfig(const std::string& json);
}
```

`storage.cpp`:
```cpp
#include "hal/storage.h"
#include <Arduino.h>
#include <LittleFS.h>

static const char* kPath = "/config.json";

namespace storage {

bool begin() { return LittleFS.begin(true); }   // format on first run

std::string readConfig() {
  File f = LittleFS.open(kPath, "r");
  if (!f) return "";
  std::string out;
  out.reserve(f.size());
  while (f.available()) out.push_back((char)f.read());
  f.close();
  return out;
}

bool writeConfig(const std::string& json) {
  File f = LittleFS.open(kPath, "w");
  if (!f) return false;
  f.print(json.c_str());
  f.close();
  return true;
}

}  // namespace storage
```

- [ ] **Step 4: Create `src/main.cpp`** (boot: load config, init HAL, run loop)

```cpp
#include <Arduino.h>
#include "domain/config.h"
#include "domain/config_json.h"
#include "domain/can_state.h"
#include "domain/behavior_engine.h"
#include "domain/channel_map.h"
#include "hal/pwm_ledc.h"
#include "hal/can_bus.h"
#include "hal/storage.h"

// GPIO assignments — provisional, finalized against the PCB (PCB plan).
static const uint8_t kPwmPins[CH_COUNT] = {
  // frontL R,G,B      frontR R,G,B
  13, 12, 14,          27, 26, 25,
  // rearL R,G,B       rearR R,G,B
  33, 32, 4,           16, 17, 5,
  // Denali A, B
  18, 19
};
static const int kCanRxPin = 21;
static const int kCanTxPin = 22;
static const uint32_t kCanBitrate = 500000;

static Config      g_cfg;
static CanState    g_can;
static EngineState g_engine;
static LedcPwm     g_pwm;
static CanBus      g_bus;

void setup() {
  Serial.begin(115200);

  storage::begin();
  bool ok = false;
  g_cfg = configFromJson(storage::readConfig(), ok);  // falls back to defaults
  if (!ok) Serial.println("config missing/corrupt -> using Experia defaults");

  g_pwm.begin(kPwmPins);
  if (!g_bus.begin(kCanRxPin, kCanTxPin, kCanBitrate))
    Serial.println("CAN init failed");
}

void loop() {
  // Drain all pending CAN frames into the state cache.
  uint32_t id;
  uint8_t data[8];
  while (g_bus.receive(id, data)) g_can.update(id, data);

  // Evaluate -> compute -> drive, on a ~10 ms tick.
  static uint32_t last = 0;
  uint32_t now = millis();
  if (now - last >= 10) {
    last = now;
    LogicalState s = g_can.evaluate(g_cfg);
    OutputIntent o = computeOutputs(s, g_cfg, now, g_engine);
    applyIntent(g_pwm, o);
  }
}
```

- [ ] **Step 5: Build for ESP32**

Run: `pio run -e esp32`
Expected: build succeeds (compiles and links).

- [ ] **Step 6: Bench smoke test (documented, manual)**

With the board flashed (`pio run -e esp32 -t upload`) and LEDs/logic-analyzer on the PWM pins:
1. Power on with no CAN connected → front corners show white DRL, rears show dim red (Run defaults true, day mode). Denali at daytime level.
2. Inject a CAN frame `0x102` with bit 18 set → front-left + rear-left flash orange ~1.5 Hz; off-phase fully dark.
3. Inject bit 21 (front brake) with no indicator → both rears full red.
4. Inject bits 18 + 21 together → rear-left flashes orange, rear-right solid red.
5. Confirm serial prints the config-source line on boot.

Record results in the commit message.

- [ ] **Step 7: Commit**

```bash
git add src/hal/ src/main.cpp
git commit -m "feat: add ESP32 HAL (LEDC/TWAI/LittleFS) and boot wiring"
```

---

## Self-Review (completed during authoring)

**Spec coverage:**
- Inputs / (ID,bit) mapping + AND/OR/single combos → Tasks 3, 4. ✓
- Hazards derived, brake OR → Task 2 (`hazards()`, `brake()`), tested Task 5. ✓
- Corner behavior matrix (all rows incl. brake+indicator priority, off-phase dark) → Task 5. ✓
- Run gating (DRL off, indicators still work, brake ignored) → Task 5. ✓
- Denali modes + spot latch + auto-drop + configurable hold → Task 6. ✓
- Config-driven tunables/colors/levels, 340 ms + full-orange startup defaults → Task 3. ✓
- Persist + load-at-boot + corrupt fallback → Tasks 7, 9. ✓
- Baked-in Experia default profile → Task 3. ✓
- 14-channel PWM output, both Denali identical → Tasks 8, 9. ✓
- Canonical bit-numbering convention → Global Constraints, Task 4. ✓
- **Deferred to Plan 2 (connectivity/web app):** SoftAP, HTTP/WebSocket, discovery mode, config UI, export/import. Not in this plan by design.

**Open questions carried from spec (non-blocking):** Run bit (handled via unassigned→true fail-safe), day/night bit (unassigned→false), "Back" @ 0x400 (not wired to a behavior yet — no output depends on it), CAN bitrate (assumed 500 kbps in Task 9, flagged), GPIO pin assignments (provisional in Task 9, finalized in PCB plan).

**Placeholder scan:** none — every step has concrete code or a concrete command.

**Type consistency:** `computeOutputs`, `EngineState`, `applyIntent`, `IPwm::setDuty`, `configFromJson(..., bool& ok)`, `mapFor`, `Function`/`Combine` names are consistent across tasks.
