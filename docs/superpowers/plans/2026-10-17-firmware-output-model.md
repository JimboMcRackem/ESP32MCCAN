# Firmware Output Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the firmware's 14-channel RGB/PWM output model with twelve on/off high-side
outputs driving bought E-marked lighting modules and two Oxford 4K aux pods.

**Architecture:** `OutputIntent` becomes a single 12-bit word; the behavior engine stays a pure
function of `(LogicalState, Config, nowMs, EngineState)`; the `IPwm`/PCA9685 HAL is replaced by
an `IOutputs`/GPIO HAL. Everything colour-related is deleted. The CAN input layer, config
storage, test mode and the web app's other screens are kept and adapted.

**Tech Stack:** C++17, PlatformIO, Arduino framework, ESP32-WROOM-32E, Unity test framework,
ArduinoJson 7, vanilla JS web app on LittleFS.

**Spec:** `docs/superpowers/specs/2026-10-17-emarked-module-redesign-design.md`

## Global Constraints

Exact values, copied from the spec. Every task's requirements implicitly include this section.

- **There is no PWM anywhere in this design.** All twelve outputs are on/off.
- `OUT_COUNT` is **12**, in this order: `FL_DRL, FL_IND, FR_DRL, FR_IND, RL_DRL, RL_IND,
  RL_BRK, RR_DRL, RR_IND, RR_BRK, AUX_L, AUX_R`. The order is the harness order and is mirrored
  by the GPIO pin table and the web app's test tab — it must not be reordered without changing
  both.
- Behavior priority: **indicator/hazard → brake → DRL**.
- **The same-side DRL is de-asserted while that indicator is requested** (ECE R48), keyed off
  the request, never off the flash phase.
- **On an indicating rear corner, both `*_DRL` and `*_BRK` are de-asserted** — forced, because
  the rear module ORs DRL and brake onto one light engine.
- Aux = `highBeam || spotLatch`, gated by Run. Both pods always carry the same value.
- `blinkPeriodMs` default **340** (on-time == off-time); `spotHoldMs` default **800**;
  `testMaxMs` default **600000**.
- `flashSource` default **`auto`**; the auto fallback threshold is **1200 ms**.
- CAN stale threshold **500 ms** → every logical input reads false.
- Boot: **all twelve outputs off** before anything else runs.
- Config retains exactly: CAN mappings, `blinkPeriodMs`, `spotHoldMs`, `flashSource`,
  `testMaxMs`. All appearance settings are deleted.
- **Native tests:** `python -m platformio test -e native` (PlatformIO is not on PATH; default
  `python` is 3.14.6).
- **ESP32 build:** `py -3.13 -m platformio run -e esp32` (the espressif32 platform refuses
  Python 3.14).
- **Unity 2.6.1 gotcha:** every test translation unit must define `void setUp(void) {}` and
  `void tearDown(void) {}`, even empty, or linking fails with `undefined reference to setUp`.

## Review Focus

Five conditions the spec implies that no task's happy-path tests would exercise. Each has its
test assigned to the task that owns the code.

1. **`millis()` rollover** in the flash-follow watchdog and the spot-hold timer — every elapsed
   comparison must be unsigned subtraction, so a wrap at ~49.7 days must not latch spot mode or
   freeze an indicator. → Task 3, Step 7.
2. **A config written by the previous firmware** — contains `colors`/`denali` keys and no
   `flashSource`. It must load, keep its CAN mappings, and default only the missing field,
   not fall back wholesale to the built-in profile. → Task 2, Step 9.
3. **`blinkPeriodMs` of 0** — reaches a `%` operator; must not divide by zero and must fall
   back to 340 ms. → Task 2, Step 1 (`test_zero_blink_period_falls_back_to_340ms`).
4. **An unknown `flashSource` string** in JSON (e.g. `"follow-ish"`, or a number) must resolve
   to `auto`, not to an undefined enum value. → Task 3, Step 9.
5. **The bus going stale while test mode holds the outputs** — a test session must survive an
   all-false real `LogicalState` rather than dropping the lights mid-test. → Task 5, Step 7.

---

### Task 0: Branch setup

This plan's work happens on a branch off **`main`**, not off the PCB line. `main` and
`plan3-pcb-hardware` diverged at `730beb8`, and `main` carries `src/domain/test_mode.{h,cpp}`,
`gamma_table.h` and two extra test suites that this plan builds on. Branching off the PCB line
would rewrite a stale firmware and discard the test-mode work.

**Files:** none modified; this task only moves commits.

- [x] **Step 1: Deal with the dirty working tree**

`plan4-emarked-modules` carries uncommitted regenerated gerbers under `hardware/output/`
(extension-style files renamed to `.gbr`, plus three now-distinct GND planes). They block a
branch switch. **Ask the user which they want** before doing either:

```bash
# Option A - keep them as a labelled commit on the PCB-line branch:
git checkout plan4-emarked-modules
git add hardware/output hardware/mccan.kicad_pro
git commit -m "hw(fab): regenerated gerber package from 1f1ff87"

# Option B - discard them:
git checkout plan4-emarked-modules
git checkout -- hardware/output hardware/mccan.kicad_pro
git clean -fd hardware/output/gerbers
```

- [x] **Step 2: Cut the firmware branch off main and carry the docs across**

Both doc commits currently sit on `plan4-emarked-modules`, which was cut from the PCB line
before the divergence was measured. Carry both across:

```bash
git checkout main
git checkout -b plan4-firmware-outputs
# Range, not a fixed list: every doc commit on that branch, whatever it ends at.
git cherry-pick bb78428^..plan4-emarked-modules
git log --oneline -5
ls src/domain/test_mode.h        # must exist: proves we are on main's line
```

Expected: both docs present, `src/domain/test_mode.h` exists. Once this lands,
`plan4-emarked-modules` holds nothing unique and can be deleted — the user's call, not the
implementer's.

- [x] **Step 3: Verify the inherited baseline is green before changing anything**

```bash
python -m platformio test -e native
```

Expected: PASS. Record the test count — it is the baseline every later task compares against.

- [x] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-10-17-firmware-output-model.md
git commit -m "docs(plan): firmware output model implementation plan"
```

---

### Task 1: Output model and the `IOutputs` seam

Introduces the new types alongside the old ones so the tree stays green. The old PWM path is
deleted in Task 2.

**Files:**
- Create: `src/domain/outputs.h`
- Create: `src/hal/ioutputs.h`
- Create: `src/domain/output_map.h`, `src/domain/output_map.cpp`
- Test: `test/test_output_map/test_output_map.cpp`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `enum OutputIndex` with `OUT_COUNT == 12`; `struct OutputIntent { uint16_t on; bool
  isOn(OutputIndex) const; void set(OutputIndex, bool); }` with `==`/`!=`;
  `constexpr uint16_t outMask(...)`; `class IOutputs { virtual void setOutput(uint8_t, bool) = 0; }`;
  `void applyIntent(IOutputs&, const OutputIntent&)`.

- [x] **Step 1: Write the failing test**

Create `test/test_output_map/test_output_map.cpp`:

```cpp
#include <unity.h>
#include "domain/output_map.h"

void setUp(void) {}
void tearDown(void) {}

class FakeOutputs : public IOutputs {
public:
  bool state[OUT_COUNT] = {false};
  int  writes = 0;
  void setOutput(uint8_t i, bool on) override {
    if (i < OUT_COUNT) state[i] = on;
    ++writes;
  }
};

void test_out_count_is_twelve() {
  TEST_ASSERT_EQUAL_INT(12, (int)OUT_COUNT);
}

void test_set_and_ison_round_trip() {
  OutputIntent o;
  TEST_ASSERT_FALSE(o.isOn(OUT_RL_BRK));
  o.set(OUT_RL_BRK, true);
  TEST_ASSERT_TRUE(o.isOn(OUT_RL_BRK));
  TEST_ASSERT_FALSE(o.isOn(OUT_RR_BRK));   // neighbours untouched
  o.set(OUT_RL_BRK, false);
  TEST_ASSERT_EQUAL_UINT16(0, o.on);
}

void test_outmask_builds_the_same_word_as_set() {
  OutputIntent o;
  o.set(OUT_FL_DRL, true);
  o.set(OUT_AUX_R, true);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_FL_DRL, OUT_AUX_R), o.on);
}

void test_apply_writes_every_output_exactly_once() {
  FakeOutputs fake;
  OutputIntent o;
  applyIntent(fake, o);
  TEST_ASSERT_EQUAL_INT(OUT_COUNT, fake.writes);
}

void test_apply_drives_only_the_set_bits() {
  FakeOutputs fake;
  OutputIntent o;
  o.on = outMask(OUT_FR_IND, OUT_AUX_L);
  applyIntent(fake, o);
  for (uint8_t i = 0; i < OUT_COUNT; ++i) {
    bool expect = (i == OUT_FR_IND || i == OUT_AUX_L);
    TEST_ASSERT_EQUAL_INT((int)expect, (int)fake.state[i]);
  }
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_out_count_is_twelve);
  RUN_TEST(test_set_and_ison_round_trip);
  RUN_TEST(test_outmask_builds_the_same_word_as_set);
  RUN_TEST(test_apply_writes_every_output_exactly_once);
  RUN_TEST(test_apply_drives_only_the_set_bits);
  return UNITY_END();
}
```

- [x] **Step 2: Run the test to verify it fails**

```bash
python -m platformio test -e native -f test_output_map
```

Expected: FAIL — `domain/output_map.h: No such file or directory`.

- [x] **Step 3: Write `src/domain/outputs.h`**

```cpp
#pragma once
#include <cstdint>

// One bit per physical output. This order is the harness order; it is mirrored
// by kOutputPins in the GPIO HAL and by the web app's test tab, so it must not
// be reordered without changing both.
enum OutputIndex : uint8_t {
  OUT_FL_DRL = 0, OUT_FL_IND,
  OUT_FR_DRL,     OUT_FR_IND,
  OUT_RL_DRL,     OUT_RL_IND, OUT_RL_BRK,
  OUT_RR_DRL,     OUT_RR_IND, OUT_RR_BRK,
  OUT_AUX_L,      OUT_AUX_R,
  OUT_COUNT   // = 12
};

// Every output is on or off: this design contains no PWM. The whole state is
// one word on purpose, so a test asserts it in a single comparison and fails
// when an output nobody considered is also energised.
struct OutputIntent {
  uint16_t on = 0;

  bool isOn(OutputIndex i) const { return ((on >> (uint8_t)i) & 1u) != 0u; }
  void set(OutputIndex i, bool v) {
    const uint16_t bit = (uint16_t)(1u << (uint8_t)i);
    if (v) on |= bit; else on &= (uint16_t)~bit;
  }
};

inline bool operator==(const OutputIntent& a, const OutputIntent& b) { return a.on == b.on; }
inline bool operator!=(const OutputIntent& a, const OutputIntent& b) { return !(a == b); }

// Mask literal helper, for expected values in tests and for presets.
constexpr uint16_t outMask() { return 0; }
template <typename... Rest>
constexpr uint16_t outMask(OutputIndex first, Rest... rest) {
  return (uint16_t)((1u << (uint8_t)first) | outMask(rest...));
}
```

- [x] **Step 4: Write `src/hal/ioutputs.h`**

```cpp
#pragma once
#include <cstdint>

// The seam between the domain and whatever drives real pins. Implementations
// must ignore an out-of-range index rather than fault.
class IOutputs {
public:
  virtual ~IOutputs() = default;
  virtual void setOutput(uint8_t index, bool on) = 0;
};
```

- [x] **Step 5: Write `src/domain/output_map.h`**

```cpp
#pragma once
#include "domain/outputs.h"
#include "hal/ioutputs.h"

// Writes the whole intent out, every output every call. Unconditional writes
// keep the driver stateless and make a missed update impossible.
void applyIntent(IOutputs& out, const OutputIntent& o);
```

- [x] **Step 6: Write `src/domain/output_map.cpp`**

```cpp
#include "domain/output_map.h"

void applyIntent(IOutputs& out, const OutputIntent& o) {
  for (uint8_t i = 0; i < (uint8_t)OUT_COUNT; ++i)
    out.setOutput(i, o.isOn((OutputIndex)i));
}
```

- [x] **Step 7: Run the test to verify it passes**

```bash
python -m platformio test -e native -f test_output_map
```

Expected: PASS, 5 tests.

- [x] **Step 8: Confirm nothing else regressed**

```bash
python -m platformio test -e native
```

Expected: PASS — the Task 0 baseline count plus 5.

- [x] **Step 9: Commit**

```bash
git add src/domain/outputs.h src/hal/ioutputs.h src/domain/output_map.h \
        src/domain/output_map.cpp test/test_output_map/test_output_map.cpp
git commit -m "feat(outputs): 12-bit output intent and the IOutputs seam"
```

---

### Task 2: Behavior engine on the new model, colour world deleted

Deliberately atomic: `OutputIntent`'s change of meaning, the engine, the config strip, the HAL
swap and `main.cpp` are one change in C++, and splitting them would leave a commit that does not
build. A reviewer gates this as one thing: "the firmware now speaks the new output model".

**Files:**
- Modify: `src/domain/behavior_engine.h`, `src/domain/behavior_engine.cpp`
- Modify: `src/domain/config.h`, `src/domain/config_json.cpp`
- Modify: `src/domain/test_mode.h` (include only), `src/main.cpp`, `platformio.ini`
- Create: `src/hal/outputs_gpio.h`, `src/hal/outputs_gpio.cpp`
- Delete: `src/domain/output_intent.h`, `src/domain/channel_map.h`,
  `src/domain/channel_map.cpp`, `src/domain/color.h`, `src/domain/gamma_table.h`,
  `src/hal/ipwm.h`, `src/hal/pwm_pca9685.h`, `src/hal/pwm_pca9685.cpp`,
  `test/test_channel_map/`, `test/test_color_level/`
- Test: `test/test_behavior_engine/test_behavior_engine.cpp` (rewrite),
  `test/test_config_defaults/test_config_defaults.cpp`,
  `test/test_config_json/test_config_json.cpp`, `test/test_types/test_types.cpp`,
  `test/test_smoke/test_smoke.cpp`

**Interfaces:**
- Consumes: `OutputIndex`, `OutputIntent`, `outMask()`, `IOutputs`, `applyIntent()` from Task 1.
- Produces: `OutputIntent computeOutputs(const LogicalState&, const Config&, uint32_t nowMs,
  EngineState&)` returning the new type; `struct EngineState { bool spotLatched; bool flashPrev;
  uint32_t flashRisingMs; }`; `Config` without any colour or denali field;
  `class GpioOutputs : public IOutputs { GpioOutputs(const uint8_t* pins, uint8_t count); bool
  begin(); void setOutput(uint8_t, bool) override; }`.

- [x] **Step 1: Write the failing engine test**

Replace `test/test_behavior_engine/test_behavior_engine.cpp` entirely:

```cpp
#include <unity.h>
#include "domain/behavior_engine.h"

void setUp(void) {}
void tearDown(void) {}

// nowMs = 0 is inside the first ON half of the blink cycle, so a requested
// indicator reads as lit. PHASE_OFF lands in the dark half.
static const uint32_t PHASE_ON  = 0;
static const uint32_t PHASE_OFF = 400;   // > 340 ms, < 680 ms

static uint16_t run(LogicalState s, uint32_t nowMs) {
  Config cfg = defaultConfig();
  EngineState est;
  return computeOutputs(s, cfg, nowMs, est).on;
}

void test_default_lights_four_drl() {
  LogicalState s; s.run = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FL_DRL, OUT_FR_DRL, OUT_RL_DRL, OUT_RR_DRL),
    run(s, PHASE_ON));
}

void test_left_indicator_drops_left_drl_and_flashes_both_left_corners() {
  LogicalState s; s.run = true; s.leftInd = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FR_DRL, OUT_RR_DRL, OUT_FL_IND, OUT_RL_IND),
    run(s, PHASE_ON));
}

void test_left_indicator_dark_phase_leaves_left_corners_fully_dark() {
  LogicalState s; s.run = true; s.leftInd = true;
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_FR_DRL, OUT_RR_DRL), run(s, PHASE_OFF));
}

void test_right_indicator_mirrors_left() {
  LogicalState s; s.run = true; s.rightInd = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FL_DRL, OUT_RL_DRL, OUT_FR_IND, OUT_RR_IND),
    run(s, PHASE_ON));
}

void test_hazards_flash_all_four_and_kill_every_drl() {
  LogicalState s; s.run = true; s.leftInd = true; s.rightInd = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FL_IND, OUT_FR_IND, OUT_RL_IND, OUT_RR_IND),
    run(s, PHASE_ON));
}

void test_brake_adds_both_rear_brakes_to_the_drls() {
  LogicalState s; s.run = true; s.frontBrake = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FL_DRL, OUT_FR_DRL, OUT_RL_DRL, OUT_RR_DRL,
            OUT_RL_BRK, OUT_RR_BRK),
    run(s, PHASE_ON));
}

void test_rear_brake_also_counts_as_brake() {
  LogicalState s; s.run = true; s.rearBrake = true;
  TEST_ASSERT_TRUE((run(s, PHASE_ON) & outMask(OUT_RL_BRK, OUT_RR_BRK)) != 0);
}

void test_brake_plus_left_indicator_kills_the_indicating_corners_brake() {
  LogicalState s; s.run = true; s.frontBrake = true; s.leftInd = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FR_DRL, OUT_RR_DRL, OUT_RR_BRK, OUT_FL_IND, OUT_RL_IND),
    run(s, PHASE_ON));
}

void test_brake_plus_right_indicator_mirrors_it() {
  LogicalState s; s.run = true; s.rearBrake = true; s.rightInd = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FL_DRL, OUT_RL_DRL, OUT_RL_BRK, OUT_FR_IND, OUT_RR_IND),
    run(s, PHASE_ON));
}

void test_brake_plus_hazards_is_indicators_only() {
  LogicalState s;
  s.run = true; s.frontBrake = true; s.leftInd = true; s.rightInd = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FL_IND, OUT_FR_IND, OUT_RL_IND, OUT_RR_IND),
    run(s, PHASE_ON));
}

void test_run_clear_keeps_indicators_and_drops_everything_else() {
  LogicalState s; s.leftInd = true; s.frontBrake = true; s.highBeam = true;
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_FL_IND, OUT_RL_IND), run(s, PHASE_ON));
}

void test_aux_follows_high_beam_and_is_gated_by_run() {
  LogicalState s; s.run = true; s.highBeam = true;
  TEST_ASSERT_TRUE((run(s, PHASE_ON) & outMask(OUT_AUX_L, OUT_AUX_R))
                   == outMask(OUT_AUX_L, OUT_AUX_R));
  s.run = false;
  TEST_ASSERT_EQUAL_UINT16(0, run(s, PHASE_ON) & outMask(OUT_AUX_L, OUT_AUX_R));
}

void test_spot_latch_holds_aux_on_after_a_long_flash_press() {
  Config cfg = defaultConfig();
  EngineState est;
  LogicalState s; s.run = true; s.flash = true;
  computeOutputs(s, cfg, 0, est);                       // rising edge
  OutputIntent o = computeOutputs(s, cfg, cfg.spotHoldMs, est);
  TEST_ASSERT_TRUE(o.isOn(OUT_AUX_L));
  s.flash = false;
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, cfg.spotHoldMs + 50, est).isOn(OUT_AUX_L));
  s.lowBeam = true;                                     // auto-drop
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, cfg.spotHoldMs + 100, est).isOn(OUT_AUX_L));
}

void test_zero_blink_period_falls_back_to_340ms() {
  Config cfg = defaultConfig();
  cfg.blinkPeriodMs = 0;
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 0, est).isOn(OUT_FL_IND));
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, 400, est).isOn(OUT_FL_IND));
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_default_lights_four_drl);
  RUN_TEST(test_left_indicator_drops_left_drl_and_flashes_both_left_corners);
  RUN_TEST(test_left_indicator_dark_phase_leaves_left_corners_fully_dark);
  RUN_TEST(test_right_indicator_mirrors_left);
  RUN_TEST(test_hazards_flash_all_four_and_kill_every_drl);
  RUN_TEST(test_brake_adds_both_rear_brakes_to_the_drls);
  RUN_TEST(test_rear_brake_also_counts_as_brake);
  RUN_TEST(test_brake_plus_left_indicator_kills_the_indicating_corners_brake);
  RUN_TEST(test_brake_plus_right_indicator_mirrors_it);
  RUN_TEST(test_brake_plus_hazards_is_indicators_only);
  RUN_TEST(test_run_clear_keeps_indicators_and_drops_everything_else);
  RUN_TEST(test_aux_follows_high_beam_and_is_gated_by_run);
  RUN_TEST(test_spot_latch_holds_aux_on_after_a_long_flash_press);
  RUN_TEST(test_zero_blink_period_falls_back_to_340ms);
  UNITY_END();
  return 0;
}
```

- [x] **Step 2: Run it to verify it fails**

```bash
python -m platformio test -e native -f test_behavior_engine
```

Expected: FAIL — `outMask` and `OUT_FL_DRL` are not visible through
`behavior_engine.h` yet, which still includes `output_intent.h`.

- [x] **Step 3: Rewrite `src/domain/behavior_engine.h`**

```cpp
#pragma once
#include "domain/logical_state.h"
#include "domain/outputs.h"
#include "domain/config.h"
#include <cstdint>

struct EngineState {
  bool     spotLatched   = false;
  bool     flashPrev     = false;
  uint32_t flashRisingMs = 0;
};

OutputIntent computeOutputs(const LogicalState& s, const Config& cfg,
                            uint32_t nowMs, EngineState& est);
```

- [x] **Step 4: Rewrite `src/domain/behavior_engine.cpp`**

```cpp
#include "domain/behavior_engine.h"

static bool flashIsOn(const Config& cfg, uint32_t nowMs) {
  const uint32_t period = cfg.blinkPeriodMs ? cfg.blinkPeriodMs : 340;
  return (nowMs % (2 * period)) < period;
}

OutputIntent computeOutputs(const LogicalState& s, const Config& cfg,
                            uint32_t nowMs, EngineState& est) {
  OutputIntent o;
  const bool phase = flashIsOn(cfg, nowMs);
  const bool li = s.leftInd, ri = s.rightInd;

  // Indicator/hazard beats brake beats DRL. An indicating corner shows ONLY
  // its indicator: the same-side DRL is off per ECE R48, and on the rear the
  // brake is off too, because the module ORs DRL and brake onto one light
  // engine -- leaving either asserted would light the corner through the dark
  // phase and destroy the flash contrast.
  //
  // Both the DRL drop and the brake drop key off the REQUEST (li / ri), never
  // off `phase`. Keying them off the phase would blink them back on in the
  // indicator's dark half, which is exactly what R48 forbids.
  o.set(OUT_FL_IND, li && phase);
  o.set(OUT_RL_IND, li && phase);
  o.set(OUT_FR_IND, ri && phase);
  o.set(OUT_RR_IND, ri && phase);

  if (s.run) {
    const bool brakeOn = s.brake();
    o.set(OUT_FL_DRL, !li);
    o.set(OUT_RL_DRL, !li);
    o.set(OUT_FR_DRL, !ri);
    o.set(OUT_RR_DRL, !ri);
    o.set(OUT_RL_BRK, brakeOn && !li);
    o.set(OUT_RR_BRK, brakeOn && !ri);
  }

  // --- Spot latch state machine (flash long-press) ---
  // NOTE: on the Energica Experia, flash / high beam / low beam are mutually
  // exclusive positions of ONE switch, so s.lowBeam and s.flash are never both
  // true. The sequential auto-drop-then-latch below is safe under that
  // assumption. Porting to a bike with independent flash and low-beam signals?
  // Gate the latch with `&& !s.lowBeam` (or use else-if).
  if (s.lowBeam) est.spotLatched = false;              // auto-drop on low beam
  if (s.flash && !est.flashPrev) est.flashRisingMs = nowMs;
  if (s.flash && (uint32_t)(nowMs - est.flashRisingMs) >= cfg.spotHoldMs)
    est.spotLatched = true;
  est.flashPrev = s.flash;

  // Aux pods: on/off only. Oxford's 5 brightness stages are a mechanical dial
  // on a switch this board replaces, so there is no level to select.
  const bool aux = s.run && (s.highBeam || est.spotLatched);
  o.set(OUT_AUX_L, aux);
  o.set(OUT_AUX_R, aux);
  return o;
}
```

- [x] **Step 5: Strip `src/domain/config.h`**

Remove `#include "domain/color.h"`, the six `ColorLevel` members
(`drlWhiteDay`, `drlWhiteNight`, `drlDimRedDay`, `drlDimRedNight`,
`indicatorOrange`, `brakeRed`) and the four `denali*` members. Keep `map`,
`blinkPeriodMs`, `spotHoldMs`, `testMaxMs` and the three free functions. The struct becomes:

```cpp
struct Config {
  FunctionMap map[(size_t)Function::COUNT];

  uint32_t blinkPeriodMs = 340;   // on-time == off-time
  uint32_t spotHoldMs    = 800;   // flash long-press threshold
  uint32_t testMaxMs     = 600000;   // absolute cap on a test-mode session
};
```

- [x] **Step 6: Strip `src/domain/config_json.cpp`**

Delete `colorTo`, `colorFrom` and the `colors` and `denali` blocks from both
`configToJson` and `configFromJson`. Leave the rest untouched. Unknown keys in an
inbound document are already ignored by ArduinoJson, which is what makes an old
config load (Step 9).

- [x] **Step 7: Point `src/domain/test_mode.h` at the new header**

Change `#include "domain/output_intent.h"` to `#include "domain/outputs.h"`. Nothing else in
that file changes: `TestMode::zones` is already an `OutputIntent`, so it becomes a 12-bit mask
for free.

- [x] **Step 8: Write the GPIO HAL**

Create `src/hal/outputs_gpio.h`:

```cpp
#pragma once
#include "hal/ioutputs.h"

// One GPIO per output, indexed in OutputIndex order. The pin table is passed in
// rather than baked in, so this class has no dependency on the domain enum and
// the board plan can change the pinout without touching the HAL.
class GpioOutputs : public IOutputs {
public:
  GpioOutputs(const uint8_t* pins, uint8_t count);
  // Sets every pin to OUTPUT and drives it LOW. Call before anything else.
  bool begin();
  void setOutput(uint8_t index, bool on) override;
private:
  const uint8_t* pins_;
  uint8_t        count_;
};
```

Create `src/hal/outputs_gpio.cpp`:

```cpp
#include "hal/outputs_gpio.h"
#include <Arduino.h>

GpioOutputs::GpioOutputs(const uint8_t* pins, uint8_t count)
  : pins_(pins), count_(count) {}

bool GpioOutputs::begin() {
  if (!pins_ || count_ == 0) return false;
  for (uint8_t i = 0; i < count_; ++i) {
    pinMode(pins_[i], OUTPUT);
    digitalWrite(pins_[i], LOW);   // every lamp dark before anything else runs
  }
  return true;
}

void GpioOutputs::setOutput(uint8_t index, bool on) {
  if (index >= count_) return;
  digitalWrite(pins_[index], on ? HIGH : LOW);
}
```

- [x] **Step 9: Add the old-config regression test (Review Focus 2)**

Append to `test/test_config_json/test_config_json.cpp`:

```cpp
void test_config_written_by_the_previous_firmware_still_loads() {
  // Shape the old firmware wrote: colours and denali present, no flashSource.
  const std::string old =
    "{\"maps\":{\"leftInd\":{\"combine\":0,"
    "\"bits\":[{\"id\":258,\"bit\":18}]}},"
    "\"blinkPeriodMs\":500,"
    "\"colors\":{\"brakeRed\":{\"hue\":[255,0,0],\"level\":255}},"
    "\"denali\":{\"day\":50,\"low\":128,\"high\":255,\"spot\":255}}";
  bool ok = false;
  Config c = configFromJson(old, ok);
  TEST_ASSERT_TRUE(ok);                      // not a wholesale fallback
  TEST_ASSERT_EQUAL_UINT32(500, c.blinkPeriodMs);
  const FunctionMap& fm = mapFor(c, Function::LeftInd);
  TEST_ASSERT_EQUAL_UINT8(1, fm.count);      // mappings survived
  TEST_ASSERT_EQUAL_UINT32(258, fm.bits[0].id);
  TEST_ASSERT_EQUAL_UINT8(18, fm.bits[0].bit);
}
```

Register it with `RUN_TEST(test_config_written_by_the_previous_firmware_still_loads);`.

- [x] **Step 10: Update the remaining stale tests and delete the dead suites**

```bash
git rm -r test/test_channel_map test/test_color_level
git rm src/domain/output_intent.h src/domain/channel_map.h src/domain/channel_map.cpp \
       src/domain/color.h src/domain/gamma_table.h \
       src/hal/ipwm.h src/hal/pwm_pca9685.h src/hal/pwm_pca9685.cpp
```

Then in `test/test_config_defaults/test_config_defaults.cpp` delete
`test_default_colors_and_denali_levels` and its `RUN_TEST` line, and the
`indicatorOrange` assertion at the top. In `test/test_config_json/test_config_json.cpp`
delete the `denaliSpot` and `indicatorOrange` round-trip assertions. In
`test/test_types/test_types.cpp` replace the `Rgb`/`denali` assertions with
`TEST_ASSERT_EQUAL_UINT16(0, OutputIntent{}.on);`. In `test/test_smoke/test_smoke.cpp`
replace the `Rgb` equality test with the same one-line default-state check.

- [x] **Step 11: Rewire `src/main.cpp`**

Replace the PCA9685/I2C block. Remove `#include <Wire.h>`,
`#include "hal/pwm_pca9685.h"`, `#include "domain/channel_map.h"`, `kI2cSda`, `kI2cScl`,
`kPca9685Addr`, `kPwmFreqHz`, the `g_pwm` definition, the `Wire.begin(...)` and
`g_pwm.begin(...)` calls. Add:

```cpp
#include "domain/output_map.h"
#include "hal/outputs_gpio.h"

// Provisional GPIO assignment in OutputIndex order - finalized against the PCB
// in the board plan. All twelve are plain outputs; none is a strapping pin that
// would float a lamp on at reset.
static const uint8_t kOutputPins[OUT_COUNT] = {
  13, 14,        // FL_DRL, FL_IND
  25, 26,        // FR_DRL, FR_IND
  27, 32, 33,    // RL_DRL, RL_IND, RL_BRK
  18, 19, 23,    // RR_DRL, RR_IND, RR_BRK
   4,  5,        // AUX_L, AUX_R
};
static GpioOutputs g_out(kOutputPins, OUT_COUNT);
```

In `setup()`, call `g_out.begin()` **before** `storage::begin()`, so the lamps are driven dark
at the earliest possible moment:

```cpp
  g_out.begin();   // all twelve outputs LOW before anything else
```

In `loop()`, change `applyIntent(g_pwm, o);` to `applyIntent(g_out, o);`.

- [x] **Step 12: Drop the PWM dependencies from `platformio.ini`**

Remove these two lines from `[env:esp32]` `lib_deps`:

```
    adafruit/Adafruit PWM Servo Driver Library@^3.0.0
    adafruit/Adafruit BusIO@^1.14
```

- [x] **Step 13: Run the full native suite**

```bash
python -m platformio test -e native
```

Expected: PASS. `test_behavior_engine` reports 14 tests; `test_channel_map` and
`test_color_level` are gone.

- [x] **Step 14: Verify the ESP32 build**

```bash
py -3.13 -m platformio run -e esp32
```

Expected: SUCCESS. Flash usage should fall against the last recorded figure — the PCA9685 and
BusIO libraries are gone.

- [x] **Step 15: Commit**

```bash
git add -A src test platformio.ini
git commit -m "feat(engine): drive twelve on/off outputs, delete the colour path"
```

---

### Task 3: `flashSource` tunable

**Files:**
- Modify: `src/domain/config.h`, `src/domain/config_json.cpp`
- Modify: `src/domain/behavior_engine.h`, `src/domain/behavior_engine.cpp`
- Test: `test/test_behavior_engine/test_behavior_engine.cpp`,
  `test/test_config_json/test_config_json.cpp`,
  `test/test_config_defaults/test_config_defaults.cpp`

**Interfaces:**
- Consumes: `computeOutputs`, `EngineState`, `Config` from Task 2.
- Produces: `enum class FlashSource : uint8_t { Auto = 0, Follow, Generate }`;
  `Config::flashSource` defaulting to `FlashSource::Auto`;
  `constexpr uint32_t kFlashFollowTimeoutMs = 1200`;
  `EngineState::leftTimer` / `rightTimer` of type `IndTimer { bool prev; uint32_t sinceMs; }`.

- [x] **Step 1: Write the failing tests**

Append to `test/test_behavior_engine/test_behavior_engine.cpp`:

```cpp
void test_follow_mirrors_the_bit_regardless_of_phase() {
  Config cfg = defaultConfig();
  cfg.flashSource = FlashSource::Follow;
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  // Both sampled in what would be the generated dark half: follow ignores it.
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, PHASE_OFF, est).isOn(OUT_FL_IND));
  s.leftInd = false;
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, PHASE_ON, est).isOn(OUT_FL_IND));
}

void test_generate_ignores_a_steady_bit_and_blinks() {
  Config cfg = defaultConfig();
  cfg.flashSource = FlashSource::Generate;
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, PHASE_ON, est).isOn(OUT_FL_IND));
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, PHASE_OFF, est).isOn(OUT_FL_IND));
}

void test_auto_follows_a_toggling_bit() {
  Config cfg = defaultConfig();   // Auto
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  // A toggling bit never stays true for 1.2 s, so auto stays in follow and
  // the lamp tracks the bit even in the generated dark half.
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, PHASE_OFF, est).isOn(OUT_FL_IND));
}

void test_auto_falls_back_to_generating_when_the_bit_sticks() {
  Config cfg = defaultConfig();   // Auto
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  computeOutputs(s, cfg, 1000, est);            // rising edge at t=1000
  // Still inside the 1.2 s window: following.
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 1000 + 400, est).isOn(OUT_FL_IND));
  // Past it: generating, and t=2600 lands in a dark half (2600 % 680 = 560).
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, 2600, est).isOn(OUT_FL_IND));
}

void test_auto_restarts_its_window_on_each_rising_edge() {
  Config cfg = defaultConfig();
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  computeOutputs(s, cfg, 0, est);
  s.leftInd = false;
  computeOutputs(s, cfg, 2000, est);            // falling edge clears the hold
  s.leftInd = true;
  computeOutputs(s, cfg, 3000, est);            // new rising edge at t=3000
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 3400, est).isOn(OUT_FL_IND));
}

void test_spot_hold_survives_millis_rollover() {
  Config cfg = defaultConfig();            // spotHoldMs == 800 == 0x320
  EngineState est;
  LogicalState s; s.run = true; s.flash = true;
  const uint32_t nearWrap = 0xFFFFFF00u;   // 256 ms short of the wrap
  computeOutputs(s, cfg, nearWrap, est);   // rising edge, pre-wrap
  TEST_ASSERT_FALSE(est.spotLatched);
  // 0x200 - 0xFFFFFF00 == 0x300 == 768 ms elapsed: still short of 800.
  computeOutputs(s, cfg, 0x200u, est);
  TEST_ASSERT_FALSE(est.spotLatched);
  // 0x220 - 0xFFFFFF00 == 0x320 == 800 ms exactly: latches.
  computeOutputs(s, cfg, 0x220u, est);
  TEST_ASSERT_TRUE(est.spotLatched);
}

void test_auto_watchdog_survives_millis_rollover() {
  Config cfg = defaultConfig();            // Auto, 1200 ms window, 340 ms blink
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  const uint32_t nearWrap = 0xFFFFFF00u;
  computeOutputs(s, cfg, nearWrap, est);   // rising edge, pre-wrap
  // 768 ms held: inside the window, so still following a (notionally) toggling
  // bit, and lit even though 0x200 % 680 == 512 is a generated dark half.
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 0x200u, est).isOn(OUT_FL_IND));
  // 0x500 - 0xFFFFFF00 == 0x600 == 1536 ms held: past the window, so
  // generating. 1280 % 680 == 600 >= 340, so this is a dark half.
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, 0x500u, est).isOn(OUT_FL_IND));
}
```

Register all seven with `RUN_TEST(...)` lines in `main`.

- [x] **Step 2: Run them to verify they fail**

```bash
python -m platformio test -e native -f test_behavior_engine
```

Expected: FAIL — `FlashSource` is not declared.

- [x] **Step 3: Add the enum and the field to `src/domain/config.h`**

Above `struct Config`:

```cpp
// Where an indicator's on/off phase comes from. `Auto` mirrors the CAN bit's
// edges so our lamps flash in phase with the bike's own -- which added
// indicators are required to do -- and falls back to generating when the bit
// turns out to be a steady request flag rather than a flasher.
enum class FlashSource : uint8_t { Auto = 0, Follow, Generate };

// Longer than any legal flash period, so a bit still true after this is a
// steady flag, not a flasher.
constexpr uint32_t kFlashFollowTimeoutMs = 1200;
```

And inside `struct Config`, after `spotHoldMs`:

```cpp
  FlashSource flashSource = FlashSource::Auto;
```

- [x] **Step 4: Add the per-side timers to `src/domain/behavior_engine.h`**

```cpp
// Tracks how long one indicator request has been continuously asserted.
struct IndTimer {
  bool     prev    = false;
  uint32_t sinceMs = 0;
};

struct EngineState {
  bool     spotLatched   = false;
  bool     flashPrev     = false;
  uint32_t flashRisingMs = 0;
  IndTimer leftTimer;
  IndTimer rightTimer;
};
```

- [x] **Step 5: Implement the phase selection in `src/domain/behavior_engine.cpp`**

Add above `computeOutputs`:

```cpp
// The on/off phase for one indicator side. Elapsed time is computed with
// unsigned subtraction, so it is correct across millis() rollover.
static bool indicatorPhase(bool bit, const Config& cfg, uint32_t nowMs,
                           IndTimer& t) {
  if (bit && !t.prev) t.sinceMs = nowMs;   // rising edge restarts the window
  t.prev = bit;
  if (!bit) return false;

  switch (cfg.flashSource) {
    case FlashSource::Follow:
      return true;
    case FlashSource::Generate:
      return flashIsOn(cfg, nowMs);
    case FlashSource::Auto:
    default:
      if ((uint32_t)(nowMs - t.sinceMs) >= kFlashFollowTimeoutMs)
        return flashIsOn(cfg, nowMs);
      return true;
  }
}
```

Then replace the four indicator lines in `computeOutputs`. Delete
`const bool phase = flashIsOn(cfg, nowMs);` and use:

```cpp
  const bool lp = indicatorPhase(li, cfg, nowMs, est.leftTimer);
  const bool rp = indicatorPhase(ri, cfg, nowMs, est.rightTimer);

  o.set(OUT_FL_IND, lp);
  o.set(OUT_RL_IND, lp);
  o.set(OUT_FR_IND, rp);
  o.set(OUT_RR_IND, rp);
```

The DRL and brake lines are unchanged: they already key off `li` / `ri`, not the phase.

- [x] **Step 6: Run the tests to verify they pass**

```bash
python -m platformio test -e native -f test_behavior_engine
```

Expected: PASS, 21 tests. (21 was correct when this step ran. The final fix dispatch later added
two tests to this suite — the R48 brake dark-phase case and a pre-wrap rollover sample — so
re-running it today gives 23.)

- [x] **Step 7: Confirm the rollover tests actually exercise the wrap**

A rollover test that would also pass under broken arithmetic proves nothing, so mutate the code
and watch the tests catch it.

> **Corrected (ruling R5).** An earlier draft of this step told you to swap both
> `(uint32_t)` casts for `(int32_t)`. That mutation is a **no-op** and the tests correctly keep
> passing: `nowMs` and `t.sinceMs` are both `uint32_t`, so the subtraction already wraps as
> unsigned *before* the outer cast runs; the wrapped results these tests produce (768 ms and
> 1536 ms) are small positives the cast leaves untouched; and comparing the `int32_t` against
> the `uint32_t` threshold promotes it straight back to unsigned. Use the mutation below
> instead — it is also the mistake a real author is likely to make.

Temporarily add a "sanity" guard to both elapsed comparisons — `(uint32_t)(nowMs - t.sinceMs)`
in `indicatorPhase` and `(uint32_t)(nowMs - est.flashRisingMs)` in the latch — so each reads:

```cpp
if (nowMs > t.sinceMs && (uint32_t)(nowMs - t.sinceMs) >= kFlashFollowTimeoutMs)
```

This is the classic "guard against a negative interval" reflex, and it is exactly wrong: across
the wrap `nowMs` is *smaller* than `sinceMs`, so the guard is false and the elapsed check never
runs. Then run:

```bash
python -m platformio test -e native -f test_behavior_engine
```

Expected: FAIL on `test_spot_hold_survives_millis_rollover` and
`test_auto_watchdog_survives_millis_rollover` — with `sinceMs = 0xFFFFFF00` and
`nowMs = 0x500`, 1536 ms has genuinely elapsed, but the guard suppresses the comparison so the
watchdog never falls back and the spot latch never releases. Remove the guards and confirm PASS.

> **Ticked.** The whole-branch reviewer ran the corrected `nowMs > sinceMs` guard mutation
> above: both rollover tests failed, and both passed with the guards removed.
>
> That mutation is only one of the two banned forms. The final fix dispatch found that neither
> rollover test discriminated against the other one, `now >= then + threshold`, because both
> sample only post-wrap, where the correct and the banned form agree.
> `test_auto_watchdog_does_not_fire_early_just_before_rollover` was added to close that: it
> samples pre-wrap, at a point whose generated phase is dark, which is the only kind of sample
> that separates them.

- [x] **Step 8: Serialize `flashSource` in `src/domain/config_json.cpp`**

Add to `configToJson`, after `doc["spotHoldMs"]`:

```cpp
  static const char* kFlashSourceNames[] = { "auto", "follow", "generate" };
  doc["flashSource"] = kFlashSourceNames[(uint8_t)c.flashSource];
```

And to `configFromJson`, alongside the other scalars:

```cpp
  // Unknown or non-string values resolve to Auto rather than to an undefined
  // enum value: an unreadable setting must not change how the bike signals.
  const char* fs = doc["flashSource"].as<const char*>();
  c.flashSource = FlashSource::Auto;
  if (fs) {
    if (!strcmp(fs, "follow"))        c.flashSource = FlashSource::Follow;
    else if (!strcmp(fs, "generate")) c.flashSource = FlashSource::Generate;
  }
```

Add `#include <cstring>` to the top of the file.

- [x] **Step 9: Write the config tests, including Review Focus 4**

Append to `test/test_config_json/test_config_json.cpp`:

```cpp
void test_flash_source_round_trips() {
  Config in = defaultConfig();
  in.flashSource = FlashSource::Generate;
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_EQUAL_INT((int)FlashSource::Generate, (int)out.flashSource);
}

void test_unknown_flash_source_resolves_to_auto() {
  bool ok = false;
  Config a = configFromJson("{\"flashSource\":\"follow-ish\"}", ok);
  TEST_ASSERT_EQUAL_INT((int)FlashSource::Auto, (int)a.flashSource);
  Config b = configFromJson("{\"flashSource\":7}", ok);
  TEST_ASSERT_EQUAL_INT((int)FlashSource::Auto, (int)b.flashSource);
  Config c = configFromJson("{}", ok);
  TEST_ASSERT_EQUAL_INT((int)FlashSource::Auto, (int)c.flashSource);
}
```

Append to `test/test_config_defaults/test_config_defaults.cpp`:

```cpp
void test_default_flash_source_is_auto() {
  TEST_ASSERT_EQUAL_INT((int)FlashSource::Auto, (int)defaultConfig().flashSource);
}
```

Register all three.

- [x] **Step 10: Run the full native suite**

```bash
python -m platformio test -e native
```

Expected: PASS.

- [x] **Step 11: Commit**

```bash
git add src/domain/config.h src/domain/config_json.cpp \
        src/domain/behavior_engine.h src/domain/behavior_engine.cpp test
git commit -m "feat(engine): flashSource tunable, auto-follow with a 1.2s watchdog"
```

---

### Task 4: CAN staleness

Spec §6.2 requires that after 500 ms without a frame every logical input reads false. Nothing
in the firmware implements this today: `CanState` holds no timestamp, so a bus that goes quiet
leaves the last frame's bits latched and the lamps lit on stale data indefinitely. This task
adds the clock to `CanState` rather than to `main.cpp`, so the rule is host-testable.

**Files:**
- Modify: `src/domain/can_state.h`, `src/domain/can_state.cpp`
- Modify: `src/main.cpp`
- Test: `test/test_can_state/test_can_state.cpp`

**Interfaces:**
- Consumes: `LogicalState`, `Config`, the existing `CanState`.
- Produces: `void CanState::update(uint32_t id, const uint8_t data[8], uint32_t nowMs)`;
  `LogicalState CanState::evaluate(const Config& cfg, uint32_t nowMs) const`;
  `bool CanState::stale(uint32_t nowMs) const`;
  `static constexpr uint32_t CanState::kStaleMs = 500`.
  **Both changed signatures take `nowMs` as a new trailing parameter** — every existing call
  site in `main.cpp` and in `test/test_can_state/` and `test/test_can_snapshot/` must be
  updated.

- [x] **Step 1: Write the failing tests**

Append to `test/test_can_state/test_can_state.cpp`:

```cpp
void test_a_fresh_state_is_stale_before_any_frame_arrives() {
  CanState cs;
  TEST_ASSERT_TRUE(cs.stale(0));
  TEST_ASSERT_TRUE(cs.stale(100000));
}

void test_a_frame_makes_it_fresh_then_it_goes_stale_at_500ms() {
  CanState cs;
  const uint8_t data[8] = {0};
  cs.update(0x102, data, 1000);
  TEST_ASSERT_FALSE(cs.stale(1000));
  TEST_ASSERT_FALSE(cs.stale(1499));
  TEST_ASSERT_TRUE(cs.stale(1500));
}

void test_evaluate_returns_all_false_when_stale() {
  // defaultConfig() already maps LeftInd to 0x102 bit 18, and this file
  // already has the setBit helper, so no hand-crafted byte layout is needed.
  CanState cs;
  uint8_t data[8] = {0};
  setBit(data, 18);
  cs.update(0x102, data, 1000);
  TEST_ASSERT_TRUE(cs.evaluate(defaultConfig(), 1000).leftInd);   // fresh
  TEST_ASSERT_FALSE(cs.evaluate(defaultConfig(), 1500).leftInd);  // stale
}

void test_stale_also_clears_the_unassigned_run_default() {
  // An unassigned Run normally evaluates TRUE so the bike works out of the box
  // (test_run_unassigned_is_true). Staleness must override even that, or a
  // quiet bus leaves the DRLs lit.
  CanState cs;
  const uint8_t data[8] = {0};
  cs.update(0x102, data, 1000);
  TEST_ASSERT_TRUE(cs.evaluate(defaultConfig(), 1000).run);
  TEST_ASSERT_FALSE(cs.evaluate(defaultConfig(), 1500).run);
}

void test_staleness_is_rollover_safe() {
  CanState cs;
  const uint8_t data[8] = {0};
  cs.update(0x102, data, 0xFFFFFF00u);
  // 0xFFFFFFF0 - 0xFFFFFF00 == 0xF0 == 240 ms: fresh.
  TEST_ASSERT_FALSE(cs.stale(0xFFFFFFF0u));
  // 0x100 - 0xFFFFFF00 == 0x200 == 512 ms, measured across the wrap: stale.
  TEST_ASSERT_TRUE(cs.stale(0x100u));
}
```

Then update **every existing call** in this file and in `test/test_can_snapshot/` to pass a
timestamp: `cs.update(id, data)` becomes `cs.update(id, data, 0)` and
`cs.evaluate(cfg)` becomes `cs.evaluate(cfg, 0)`. With a timestamp of 0 and a frame recorded at
0 the state is fresh, so existing assertions keep their meaning.

- [x] **Step 2: Run the tests to verify they fail**

```bash
python -m platformio test -e native -f test_can_state
```

Expected: FAIL — `stale` is not a member of `CanState`, and `update` takes 2 arguments.

- [x] **Step 3: Extend `src/domain/can_state.h`**

```cpp
class CanState {
public:
  // No frame for this long and every logical input reads false. A quiet bus
  // means the bike's own lamps are off too, so holding the last frame's bits
  // would light our modules on data nobody is sending any more.
  static constexpr uint32_t kStaleMs = 500;

  void update(uint32_t id, const uint8_t data[8], uint32_t nowMs);
  bool getBit(uint32_t id, uint8_t bit) const;
  LogicalState evaluate(const Config& cfg, uint32_t nowMs) const;
  bool stale(uint32_t nowMs) const;
  int snapshot(CanFrameSnapshot* out, int maxOut) const;

private:
  static constexpr int MAX_FRAMES = 16;
  struct Frame { uint32_t id = 0; uint8_t data[8] = {0}; bool seen = false; };
  Frame frames_[MAX_FRAMES];

  bool     anyRx_    = false;   // false until the first frame ever arrives
  uint32_t lastRxMs_ = 0;

  const Frame* find(uint32_t id) const;
  bool evalFunction(const FunctionMap& fm) const;
};
```

- [x] **Step 4: Implement in `src/domain/can_state.cpp`**

At the end of the existing `update`, record the arrival:

```cpp
  anyRx_    = true;
  lastRxMs_ = nowMs;
```

Add:

```cpp
bool CanState::stale(uint32_t nowMs) const {
  // Unsigned subtraction, so this is correct across millis() rollover.
  if (!anyRx_) return true;
  return (uint32_t)(nowMs - lastRxMs_) >= kStaleMs;
}
```

And gate `evaluate`'s existing body behind the check — the early return must come first, so a
stale bus cannot produce a partially-populated state:

```cpp
LogicalState CanState::evaluate(const Config& cfg, uint32_t nowMs) const {
  if (stale(nowMs)) return LogicalState{};
  // ... existing body unchanged ...
}
```

- [x] **Step 5: Update the two call sites in `src/main.cpp`**

```cpp
  while (g_bus.receive(id, data)) g_can.update(id, data, millis());
```

and, inside the 10 ms tick:

```cpp
    LogicalState s = g_can.evaluate(g_cfg, now);
```

- [x] **Step 6: Run the tests to verify they pass**

```bash
python -m platformio test -e native -f test_can_state
```

Expected: PASS.

- [x] **Step 7: Run the full native suite and the ESP32 build**

```bash
python -m platformio test -e native
py -3.13 -m platformio run -e esp32
```

Expected: both PASS/SUCCESS. If `test_can_snapshot` fails to compile, a call site there was
missed in Step 1.

- [x] **Step 8: Commit**

```bash
git add src/domain/can_state.h src/domain/can_state.cpp src/main.cpp test
git commit -m "feat(can): a bus quiet for 500ms reads as all inputs false"
```

---

### Task 5: Test mode and web protocol v3

**Files:**
- Modify: `src/domain/web_protocol.h`, `src/domain/web_protocol.cpp`
- Modify: `src/domain/test_mode.cpp` (scenario presets only)
- Test: `test/test_web_protocol/test_web_protocol.cpp`,
  `test/test_test_mode/test_test_mode.cpp`

**Interfaces:**
- Consumes: `OutputIntent`, `outMask()`, `OUT_COUNT` (Task 1); `Config`, `FlashSource` (Tasks
  2–3); the existing `TestMode`, `TestKind`, `resolveOutputs`, `testExpired`,
  `scenarioByName`, `kScenarioNames`, `kScenarioCount`.
- Produces: `constexpr int kProtocolVersion = 3`; `configMessage` emitting `flashSource` and no
  colour or denali keys; `testStateMessage` emitting `zones` as a numeric mask;
  `handleRequest` accepting `{"type":"test","mode":"zones","zones":<mask>}`.

**Note the existing message shape before writing anything:** the test request keys the sub-type
on **`"mode"`**, not `"kind"` (`web_protocol.cpp:47`), and the file reports failures by assigning
`act.error` and returning `act` — there is no `error()` helper. Match both.

- [x] **Step 1: Write the failing protocol tests**

Append to `test/test_web_protocol/test_web_protocol.cpp`:

```cpp
void test_protocol_version_is_three() {
  TEST_ASSERT_EQUAL_INT(3, kProtocolVersion);
}

void test_config_message_carries_flash_source_and_no_colours() {
  Config c = defaultConfig();
  c.flashSource = FlashSource::Follow;
  const std::string m = configMessage(c);
  TEST_ASSERT_NOT_NULL(strstr(m.c_str(), "\"flashSource\":\"follow\""));
  TEST_ASSERT_NULL(strstr(m.c_str(), "colors"));
  TEST_ASSERT_NULL(strstr(m.c_str(), "denali"));
}

void test_zones_request_parses_a_twelve_bit_mask() {
  const unsigned want = (unsigned)outMask(OUT_RL_BRK, OUT_AUX_L);
  char buf[128];
  snprintf(buf, sizeof buf,
           "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":%u}", want);
  ProtocolAction a = handleRequest(buf);
  TEST_ASSERT_TRUE(a.setTest);
  TEST_ASSERT_TRUE(a.error.empty());
  TEST_ASSERT_EQUAL_INT((int)TestKind::Zones, (int)a.testOut.kind);
  TEST_ASSERT_EQUAL_UINT16((uint16_t)want, a.testOut.zones.on);
}

void test_zones_request_rejects_bits_above_the_output_count() {
  ProtocolAction a = handleRequest(
    "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":65535}");
  TEST_ASSERT_FALSE(a.error.empty());   // must not silently truncate
}

void test_test_state_message_reports_the_zone_mask() {
  TestMode t;
  t.kind = TestKind::Zones;
  t.zones.on = outMask(OUT_FR_IND);
  char want[64];
  snprintf(want, sizeof want, "\"zones\":%u", (unsigned)outMask(OUT_FR_IND));
  const std::string m = testStateMessage(t, defaultConfig(), 0);
  TEST_ASSERT_NOT_NULL(strstr(m.c_str(), want));
}
```

Add `#include <cstring>` and `#include <cstdio>` to the test file if absent, and register all
five.

- [x] **Step 2: Run them to verify they fail**

```bash
python -m platformio test -e native -f test_web_protocol
```

Expected: FAIL — `kProtocolVersion` is still 2.

- [x] **Step 3: Bump the protocol version**

In `src/domain/web_protocol.h`, change `constexpr int kProtocolVersion = 2;` to `3`, and extend
the comment to say that v3 removed the colour and denali blocks and changed `zones` from
per-corner colours to a 12-bit output mask.

- [x] **Step 4: Update `configMessage` and `handleRequest`**

> **Ticked with provenance (Task 7 docs review).** This step's `handleRequest` mask-parsing
> change landed early, in Task 2's commit (60987e9) — that commit's own message says so:
> "web_protocol.cpp and two of its test suites were updated here, not in the later protocol
> task," because pointing `test_mode.h` at `outputs.h` broke them and Task 2 was required to
> leave the native suite green. `configMessage`'s colour/denali removal and `flashSource`
> addition needed no direct edit here at all: it forwards `configToJson(c)` verbatim, so Task 2's
> strip of `config.h`/`config_json.cpp` and Task 3's `flashSource` serialization already cover
> it. The deliverable described below is real; this task's own commit (1feb9c4) only tightened
> the mask-parse's handling of a missing `zones` field.

In `src/domain/web_protocol.cpp`, delete every `colors` and `denali` field from
`configMessage` (they now reference members that no longer exist, so this is also what makes the
file compile). Add `flashSource` using the same three names as `config_json.cpp`.

In the `"test"` branch of `handleRequest` (`web_protocol.cpp:60`), replace the whole
`m == "zones"` block — the `JsonArrayConst zs`, the `zs.size() != 4` check, the `Rgb* dst[4]`
table and the loop over triples — with:

```cpp
    } else if (m == "zones") {
      const uint32_t mask = doc["zones"] | 0u;
      // Reject rather than truncate: a client sending a bit we do not have is
      // out of sync with the firmware, and silently dropping it would make the
      // test tab lie about what it just energised.
      if (mask >= (1u << (uint32_t)OUT_COUNT)) {
        act.error = "zones mask has bits above OUT_COUNT";
        return act;
      }
      tm.zones.on = (uint16_t)mask;
      tm.kind = TestKind::Zones;
```

`tm` is the local `TestMode` the surrounding branch already declares at
`web_protocol.cpp:49`; keep using it rather than writing to `act.testOut` directly, because the
code after the if-chain is what copies `tm` into the action.

- [x] **Step 5: Update `testStateMessage`**

> **Ticked with provenance (Task 7 docs review).** `doc["zones"] = t.zones.on;` was already
> landed, along with test coverage, by the review-finding commit f80573f ("test(protocol): cover
> the zones mask parse, assert whole-word outputs") — raised and fixed between Task 2 and Task
> 3 because the old 4-rgb-triple tests had been deleted without replacement coverage for the new
> mask parse. Same situation as Step 4: the deliverable is real, landed early to keep the branch's
> test coverage honest rather than in this task's own commit.

Emit `zones` as the raw mask:

```cpp
  doc["zones"] = t.zones.on;
```

Delete the per-corner colour serialization and the denali field.

- [x] **Step 6: Review the scenario presets**

Open `src/domain/test_mode.cpp` and check each entry of the scenario table. The presets are
`LogicalState` values, so they are unaffected by the output-model change — but any preset that
existed to exercise a colour or a denali level should be removed, and the table should cover the
nine rows of the behavior matrix. Keep `kScenarioNames` and `kScenarioCount` consistent.

- [x] **Step 7: Write the test-mode tests, including Review Focus 5**

Append to `test/test_test_mode/test_test_mode.cpp`:

```cpp
void test_zones_mode_emits_the_mask_verbatim() {
  Config cfg = defaultConfig();
  EngineState est, testEst;
  TestMode t;
  t.kind = TestKind::Zones;
  t.zones.on = outMask(OUT_RL_BRK, OUT_RR_BRK);
  LogicalState real; real.run = true;          // would light four DRL
  OutputIntent o = resolveOutputs(real, t, cfg, 0, est, testEst);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_RL_BRK, OUT_RR_BRK), o.on);
}

void test_a_stale_bus_does_not_disturb_a_held_test_session() {
  Config cfg = defaultConfig();
  EngineState est, testEst;
  TestMode t;
  t.kind = TestKind::Zones;
  t.zones.on = outMask(OUT_AUX_L, OUT_AUX_R);
  // CAN stale: every logical input reads false. The override must survive it,
  // or the lights drop out mid-test for no reason the rider can see.
  LogicalState stale;
  OutputIntent o = resolveOutputs(stale, t, cfg, 5000, est, testEst);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_AUX_L, OUT_AUX_R), o.on);
}

void test_scenario_mode_never_touches_the_real_engine_state() {
  Config cfg = defaultConfig();
  EngineState est, testEst;
  TestMode t;
  t.kind = TestKind::Scenario;
  t.scenario.run = true;
  t.scenario.flash = true;
  resolveOutputs(LogicalState{}, t, cfg, 0, est, testEst);
  resolveOutputs(LogicalState{}, t, cfg, cfg.spotHoldMs + 10, est, testEst);
  TEST_ASSERT_TRUE(testEst.spotLatched);
  TEST_ASSERT_FALSE(est.spotLatched);     // the real latch is untouched
}
```

Register all three.

- [x] **Step 8: Run the full native suite**

```bash
python -m platformio test -e native
```

Expected: PASS.

- [x] **Step 9: Verify the ESP32 build**

```bash
py -3.13 -m platformio run -e esp32
```

Expected: SUCCESS.

- [x] **Step 10: Commit**

```bash
git add src/domain/web_protocol.h src/domain/web_protocol.cpp src/domain/test_mode.cpp test
git commit -m "feat(protocol): v3 drops colour, zones become a 12-bit output mask"
```

---

### Task 6: Web app

No native test harness covers `data/`, so this task's verification is the device itself. Treat
the protocol version banner as the gate: a mismatch means the app and the firmware disagree.

**Files:**
- Modify: `data/index.html`, `data/app.js`, `data/style.css`

**Interfaces:**
- Consumes: protocol v3 from Task 5 — `configMessage` with `flashSource` and no colour keys;
  `testStateMessage` with a numeric `zones`; `{"type":"test","mode":"zones","zones":<mask>}`.
- Produces: no code interface; the UI surface the spec's §5.6 describes.

- [x] **Step 1: Remove the Appearance tab from `data/index.html`**

Delete the `<button data-tab="appearance">Appearance</button>` nav entry and the whole
`<section id="tab-appearance">` block, including the `previewToggle` checkbox and the `#colors`
host. Delete the `<div id="denali"></div>` from the Tunables section.

- [x] **Step 2: Add the flash-source control to Tunables**

Inside `<section id="tab-tunables">`, after the `spotHoldMs` label:

```html
      <label>Indicator flash source
        <select id="flashSource">
          <option value="auto">Auto (follow the bike, fall back to 340 ms)</option>
          <option value="follow">Follow the bike's indicator signal</option>
          <option value="generate">Generate our own flash</option>
        </select>
      </label>
```

- [x] **Step 3: Rebuild the Test tab for twelve outputs**

Replace the contents of `<section id="tab-test">` after the `<p><small>...</small></p>` note:

```html
      <h3>Scenarios</h3>
      <div id="scenarios" class="scenarios"></div>
      <h3>Outputs</h3>
      <p><small>One wire per checkbox. Walking these one at a time confirms
      every module is on the pin the firmware thinks it is.</small></p>
      <div id="testOutputs" class="outputs"></div>
```

The `testDenali` slider and its `testDenaliPct` label are deleted — the pods are on/off and
appear as two of the twelve checkboxes.

- [x] **Step 4: Strip the colour machinery from `data/app.js`**

Delete the `COLORS` array, `renderDenali()`, `renderColors()` (or whatever builds `#colors`),
`hexToRgb()`, `rgbToHex()` if present, the `previewToggle` handler, and every reference to
`cfg.colors` and `cfg.denali`. Remove the `renderDenali()` call from the render path.

- [x] **Step 5: Add the output names table and the checkbox renderer**

```js
// Must match OutputIndex in src/domain/outputs.h, in order. The firmware's
// enum is authoritative; this mirrors it only for labels.
const OUTPUT_NAMES = [
  "Front L - DRL",  "Front L - indicator",
  "Front R - DRL",  "Front R - indicator",
  "Rear L - DRL",   "Rear L - indicator", "Rear L - brake",
  "Rear R - DRL",   "Rear R - indicator", "Rear R - brake",
  "Aux pod L",      "Aux pod R",
];

let testMask = 0;

function renderTestOutputs() {
  const host = document.getElementById("testOutputs");
  host.innerHTML = "";
  OUTPUT_NAMES.forEach((name, i) => {
    const lab = document.createElement("label");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = (testMask & (1 << i)) !== 0;
    box.onchange = () => {
      if (box.checked) testMask |= (1 << i);
      else             testMask &= ~(1 << i);
      send({ type: "test", mode: "zones", zones: testMask });
    };
    lab.appendChild(box);
    lab.appendChild(document.createTextNode(" " + name));
    host.appendChild(lab);
  });
}
```

Use the file's own existing `send()` helper rather than introducing a new one; match its name.

- [x] **Step 6: Reflect inbound test state**

Where the app handles the `testState` message, set `testMask = msg.zones | 0;` and call
`renderTestOutputs()` so a second client taking the mode updates this one's checkboxes.

- [x] **Step 7: Wire `flashSource` into load and save**

In the config-load path, `document.getElementById("flashSource").value = cfg.flashSource ||
"auto";`. In the save path, read it back into `cfg.flashSource`. Follow the pattern the existing
`blinkPeriodMs` field uses.

- [x] **Step 8: Remove the dead CSS**

In `data/style.css`, delete the colour-picker and swatch rules that no longer have markup. Add a
rule for the new checkbox grid:

```css
.outputs { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.outputs label { display: flex; align-items: center; gap: 6px; }
```

- [x] **Step 9: Verify there are no stale references**

```bash
grep -rn "denali\|colors\|hexToRgb\|previewToggle\|testDenali" data/
```

Expected: no output.

- [x] **Step 10: Commit**

```bash
git add data
git commit -m "feat(app): twelve-output test tab, flash source, Appearance gone"
```

- [ ] **Step 11: On-device check — needs the user, and both images**

> **Left unticked (Task 7 docs review).** This is a user action over a COM port no agent can
> reach. Outstanding.

The firmware and the LittleFS image are separate flashes. Ask the user to run both, in their own
shell, because the assistant's tools cannot reach host COM ports:

```powershell
powershell -NoProfile -Command "$env:PYTHONIOENCODING='utf-8'; py -3.13 -m platformio run -e esp32 -t upload --upload-port COM4"
powershell -NoProfile -Command "$env:PYTHONIOENCODING='utf-8'; py -3.13 -m platformio run -e esp32 -t uploadfs --upload-port COM4"
```

Hold the BOOT button through "Connecting......". Then join `MCCAN-Setup`, open
`http://192.168.4.1/`, and confirm: no version-mismatch banner, no Appearance tab, twelve
checkboxes on the Test tab, and the flash-source select showing `auto`.

---

### Task 7: Documentation catch-up

**Files:**
- Modify: `docs/superpowers/specs/2026-07-29-esp32-mccan-lighting-firmware-design.md`
- Modify: `docs/superpowers/specs/2026-09-21-test-mode-and-brightness-design.md`
- Modify: `docs/superpowers/plans/2026-10-17-firmware-output-model.md` (tick the boxes)

- [x] **Step 1: Mark the superseded sections of the 2026-07-29 firmware spec**

Add a banner under its `**Status:**` line:

```markdown
> **SUPERSEDED IN PART, 2026-10-17.** Sections 4.1 (corner colour matrix), 4.2 (Denali levels),
> 5's appearance block and 7 (PWM channel count) are replaced by
> `2026-10-17-emarked-module-redesign-design.md`: the lighting modules are now bought,
> E-marked and on/off, so there is no colour and no PWM. Sections 1-3, 6 and 8 — the CAN
> mapping model, connectivity and the testing approach — remain current.
```

- [x] **Step 2: Mark the brightness half of the test-mode spec superseded**

Add the equivalent banner naming which of its sections survive: test mode, the single-holder
override and the version banner survive; everything about brightness, gamma and the hue/level
split does not, because nothing dims any more.

- [x] **Step 3: Record the measured outcome**

Append a short section to the new spec recording what the firmware actually came out at: the
native test count, and the ESP32 flash figure from Task 2 Step 14 against the 84.3% the previous
firmware used. Measured figures, not estimates.

Also record the protocol version bump (2 → 3) and what changed in it, since the app and the
LittleFS image are separate flashes and the version banner is the only thing that catches a
mismatch.

- [x] **Step 4: Tick this plan's checkboxes**

Mark every completed step. An unticked box in a committed plan is a lie about what was done.

- [x] **Step 5: Commit**

```bash
git add docs
git commit -m "docs: mark the colour and brightness specs superseded in part"
```

---

## What this plan does not cover

**The board.** It needs its own plan, off `plan3-pcb-hardware`, and it is blocked on the Oxford
kit arriving: spec §9.1 (the Plug C/D pinout and the measured pod inrush) decides the output
stage's part selection, and no amount of planning substitutes for the connector. The firmware's
`kOutputPins` table in `main.cpp` is the one seam between the two plans, and it is deliberately
a single array so the board plan can set it in one edit.

**Switch-fault handling and lamp-out reporting** (spec §6.3 and §6.4). Both read a diagnostic
pin or sense output whose behavior is a property of a part nobody has chosen yet, and lamp-out
may be dropped entirely if the open-load threshold cannot resolve 125 mA. Writing them now would
be writing against an imagined datasheet. They belong to the board plan, which is also where the
decision to keep or drop lamp-out gets made.

**Deep sleep and the quiescent budget.** Carried over from plan3 unchanged by this plan, but the
wake path depends on the board's final CAN-transceiver domain wiring, so verifying it belongs
with the hardware.
