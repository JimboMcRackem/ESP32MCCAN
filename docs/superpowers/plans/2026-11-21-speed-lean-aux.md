# Speed- and Lean-Aware Aux Pods Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read speed and lean as numbers from configurable CAN signals, give each pod its own yellow PWM (left GPIO 13, right GPIO 12), and use them for speed-scaled high beam and a cornering boost/dim.

**Architecture:** A pure decoder turns a `NumSignal` definition into a value; `CanState::evaluate` fills new `LogicalState` fields with validity; `computeOutputs` computes a per-side duty target and slews toward it in `EngineState`; `applyIntent` writes two duties through a two-channel `IAuxPwm`. Settings flow through `Config` -> `config_json` -> web app as today.

**Tech Stack:** C++17, Arduino-ESP32 (LEDC, TWAI), ArduinoJson 7, Unity native tests, PlatformIO; web app in `data/` embedded by `tools/embed_web.py`.

**Spec:** `docs/superpowers/specs/2026-11-21-speed-lean-aux-design.md`

## Global Constraints

- Native tests: `python -m platformio test -e native`. ESP32 build: `py -3.13 -m platformio run -e esp32`. App mirrors: `python scripts/check_app_mirrors.py`.
- Every fallback (signal unmapped, stale > 500 ms, implausible, feature disabled) gives **exactly today's outputs**.
- Indicator rule unchanged and applied last; lean never relights an indicating side's pod.
- GPIO 12: attach its LEDC channel only after `g_bus.begin()`; never drive it before that.
- Both features default **disabled**. Defaults: `hbSlowKmh` 20, `hbFullKmh` 80, `hbSlowDuty` 50, `leanStartDeg` 10, `leanFullDeg` 30, `leanBoostDuty` 60, `leanDimDuty` 5.
- Plausible ranges: speed 0..400 km/h, lean -80..+80 deg. Lean positive = leaning right.
- `kAuxSlewPctPerS` = 250. Pod turning off is immediate; a pod turning on starts at its target.
- `kProtocolVersion` 7 -> 8 with one history line; app mirror updated.
- Commit only when the owner asks (owner preference overrides the per-task commit steps: stage nothing until told). Never push.
- `kAuxPwmHz` stays 100 on this branch (owner's 150 Hz lives in the main checkout).

## Review Focus

1. **Lean frame stops while the rest of the bus keeps going** -> lean invalid, pods as today (not frozen at the last angle). Test in Task 2.
2. **Lean direction** -> leaning right (+) boosts the RIGHT pod and dims the LEFT. Test in Task 5.
3. **Config saved by protocol-7 firmware** -> loads with both features off and signals unmapped. Test in Task 3.
4. **Hazards while leaning at night** -> both pods Off, lean does not relight either. Test in Task 5.
5. **millis() wrap during a slew** -> the step size stays rate x dt. Test in Task 5, anchor chosen per the rule below.

Rollover tests: pick the anchor so the **asserted value differs** between wrap-safe and naive arithmetic, never merely so a branch runs.

---

### Task 1: Numeric signal decoder

**Files:**
- Modify: `src/domain/config.h` (add `NumSignal`, before `struct Config`)
- Create: `src/domain/can_signal.h`, `src/domain/can_signal.cpp`
- Test: `test/test_can_signal/test_can_signal.cpp` (new suite)

**Interfaces:**
- Produces: `struct NumSignal { uint32_t id=0; uint8_t startBit=0; uint8_t length=0; bool bigEndian=false; bool isSigned=false; float scale=1.0f; float offset=0.0f; bool mapped() const { return length >= 1 && length <= 32; } };`
- Produces: `bool decodeRaw(const uint8_t data[8], const NumSignal& sig, int64_t& rawOut);` (false if unmapped or bits fall outside the 64-bit payload)
- Produces: `bool decodeSignal(const uint8_t data[8], const NumSignal& sig, float& valueOut);` (= raw * scale + offset)

Bit numbering, documented in `can_signal.h`: bit n = byte n/8, bit n%8, LSB = 0 (same as `BitRef`).
- Intel: `startBit` is the value's LSB; value bit i is payload bit `startBit + i`.
- Motorola (DBC convention): `startBit` is the value's MSB. Walk `length` bits from it: next bit is `b - 1` unless `b % 8 == 0`, in which case it is `b + 15` (bit 0 of byte k -> bit 7 of byte k+1). First bit walked is the value's MSB.
- Signed: two's complement at `length` bits.

- [ ] **Step 1: Write failing tests**

```
test_intel_byte_aligned_16:   data {0x34,0x12,...}, {start 0, len 16}            -> raw 0x1234
test_intel_unaligned_12:      data {0xF0,0xAB,...}, {start 4, len 12}            -> raw 0xABF
test_motorola_16:             data {0x12,0x34,...}, {start 7, len 16, be}        -> raw 0x1234
test_motorola_12_crosses:     data {0x0A,0xBC,...}, {start 3, len 12, be}        -> raw 0xABC
test_signed_negative:         data {0xFF,0xFF,...}, {start 0, len 16, signed}    -> raw -1
test_signed_8_min:            data {0x80,...},      {start 0, len 8, signed}     -> raw -128
test_unsigned_high_bit:       data {0x80,...},      {start 0, len 8}             -> raw 128
test_len_1:                   data {0x04,...},      {start 2, len 1}             -> raw 1
test_len_32:                  data {0x78,0x56,0x34,0x12,...}, {start 0, len 32}  -> raw 0x12345678
test_scale_offset:            raw 100, scale 0.1, offset -40                     -> value -30.0 (within 1e-4)
test_unmapped_len_0_fails:    length 0 -> false
test_len_33_fails:            length 33 -> false
test_intel_past_end_fails:    {start 60, len 8} -> false
test_motorola_past_end_fails: {start 63, len 16, be} -> false (walk leaves byte 7)
```

- [ ] **Step 2:** Run `python -m platformio test -e native -f test_can_signal` -> FAIL (missing header).
- [ ] **Step 3:** Implement the two functions in `can_signal.cpp` per the rules above.
- [ ] **Step 4:** Run the suite -> PASS; run all native tests -> PASS.

---

### Task 2: Speed and lean in `LogicalState`

**Files:**
- Modify: `src/domain/logical_state.h`, `src/domain/can_state.h`, `src/domain/can_state.cpp`, `src/domain/config.h` (add `NumSignal speedSignal, leanSignal;` to `Config`, default unmapped)
- Test: `test/test_can_state/test_can_state.cpp`

**Interfaces:**
- Consumes: `decodeSignal` (Task 1).
- Produces: `LogicalState` gains `float speedKmh = 0; bool speedValid = false; float leanDeg = 0; bool leanValid = false;`
- Produces: constants in `can_state.h`: `kSpeedMaxKmh = 400.0f`, `kLeanMaxDeg = 80.0f`.
- Produces: `CanState::Frame` gains `uint32_t lastMs`; `update` sets it.

Valid = mapped AND frame seen AND `(now - frame.lastMs) < kStaleMs` (unsigned) AND decoded AND in range (speed `0..400`, lean `-80..+80`, inclusive). Invalid leaves value 0. A globally stale bus still returns `LogicalState{}`.

- [ ] **Step 1: Write failing tests**

```
test_speed_decoded_and_valid:      map speed {0x200, start 0, len 16, scale 0.01}; frame 0x200 = 0x2710 -> speedKmh 100.0, speedValid
test_lean_negative_valid:          lean {0x201, start 0, len 16, signed, scale 0.1}; raw -235 -> leanDeg -23.5, leanValid
test_unmapped_signals_invalid:     default config -> speedValid false, leanValid false
test_signal_frame_never_seen:      mapped to 0x2FF, no such frame -> invalid
test_lean_frame_stale_bus_alive:   lean frame at t=0, other frame every 100 ms until t=600; evaluate at 600 -> leanValid false, other bits still evaluated  (Review Focus 1)
test_lean_frame_fresh_at_499:      same, evaluate at 499 -> leanValid true
test_speed_implausible:            decodes to 655.35 -> speedValid false, speedKmh 0
test_lean_out_of_range:            decodes to 81.0 -> leanValid false
test_lean_at_limit_valid:          decodes to -80.0 -> leanValid true
```

- [ ] **Step 2:** Run `-f test_can_state` -> FAIL.
- [ ] **Step 3:** Implement in `CanState::evaluate` with a private helper `bool readSignal(const NumSignal&, uint32_t nowMs, float lo, float hi, float& out) const`.
- [ ] **Step 4:** Suite and full native run -> PASS.

---

### Task 3: Settings and JSON

**Files:**
- Modify: `src/domain/config.h` (fields), `src/domain/config_json.cpp`
- Test: `test/test_config_defaults/test_config_defaults.cpp`, `test/test_config_json/test_config_json.cpp`

**Interfaces:**
- Produces in `Config`: `bool speedScaleEnable=false; uint16_t hbSlowKmh=20; uint16_t hbFullKmh=80; uint8_t hbSlowDuty=50; bool leanEnable=false; uint8_t leanStartDeg=10; uint8_t leanFullDeg=30; uint8_t leanBoostDuty=60; uint8_t leanDimDuty=5;`
- JSON keys: the field names above at top level; signals under `maps.speed` / `maps.lean` as `{"id","start","len","be","signed","scale","offset"}`. An absent signal = unmapped.
- Clamps (read wide, clamp, then narrow, as `clampPercent` does): kmh 0..300, `leanStartDeg` 0..60, `leanFullDeg` 1..70, duties 0..100, `len` 0..32 (out of range -> 0), `start` 0..63.

- [ ] **Step 1: Write failing tests**

```
test_new_defaults:                every default above; speedSignal/leanSignal !mapped()
test_round_trip_new_fields:       set all nine + both signals (bigEndian, signed, scale 0.1, offset -40) -> toJson -> fromJson equal
test_protocol7_config_loads:      JSON with only today's keys -> both enables false, signals unmapped  (Review Focus 3)
test_clamps:                      hbSlowKmh 999 -> 300; leanFullDeg 0 -> 1; leanBoostDuty 250 -> 100; leanDimDuty -5 -> 0; len 40 -> 0
test_signal_not_in_bit_maps:      maps.speed does not disturb the ten bit maps
```

- [ ] **Step 2:** Run both suites -> FAIL.
- [ ] **Step 3:** Implement. Note `kFuncNames` loops over `maps`; read `maps.speed`/`maps.lean` separately so the bit-map loop never sees them.
- [ ] **Step 4:** Suites and full native run -> PASS.

---

### Task 4: Per-side duty and the second PWM channel

**Files:**
- Modify: `src/domain/outputs.h`, `src/domain/output_map.{h,cpp}`, `src/hal/iaux_pwm.h`, `src/hal/aux_pwm_ledc.{h,cpp}`, `src/domain/behavior_engine.cpp` (fill both duties, same value as today), `src/domain/test_mode.cpp`, `src/main.cpp`, and any comment that still calls the duty "shared" (`config.h`, `iaux_pwm.h`, `outputs.h`)
- Test: `test/test_output_map/`, `test/test_behavior_engine/`, `test/test_test_mode/`, `test/test_reset_feedback/` (rename only)

**Interfaces:**
- Produces: `OutputIntent { uint16_t on; AuxLevel auxL, auxR; uint8_t auxDutyL = 0; uint8_t auxDutyR = 0; }`, `operator==` compares both.
- Produces: `IAuxPwm::setDuty(uint8_t left, uint8_t right)`.
- Produces: `LedcAuxPwm(uint8_t pinL, uint8_t pinR, uint32_t freqHz)`, `bool begin()` (left only, duty 0), `bool beginRight()` (right, duty 0; before it succeeds, right duties are dropped), `setDuty(l, r)`.
- `main.cpp`: `kAuxPwmPinR = 12`; `g_auxPwm.beginRight()` immediately after `g_bus.begin(...)`, logging on failure "right aux PWM attach failed: right pod's main LEDs stay dark". Comment the GPIO 12 rules (strap; after TWAI).

Behaviour is unchanged in this task: each side's duty = today's duty if that pod is lit, else 0.

- [ ] **Step 1:** Update tests first: fake PWM records `(left,right)`; `test_duty_written_before_switches` asserts both duties precede switches; engine tests assert `auxDutyL`/`auxDutyR` where they asserted `auxDuty`; add `test_indicating_side_duty_zero` (night, left indicating -> `auxDutyL` 0, `auxDutyR` 15); test-mode Zones: only AUX_R ticked -> `auxDutyL` 0, `auxDutyR` 15.
- [ ] **Step 2:** Native run -> compile FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Native run -> PASS. `py -3.13 -m platformio run -e esp32` -> SUCCESS.

---

### Task 5: Speed curve, lean boost/dim, slew

**Files:**
- Modify: `src/domain/behavior_engine.{h,cpp}`
- Test: `test/test_behavior_engine/test_behavior_engine.cpp`

**Interfaces:**
- Consumes: `LogicalState` speed/lean (Task 2), settings (Task 3), `auxDutyL/R` (Task 4).
- Produces: `constexpr float kAuxSlewPctPerS = 250.0f;` in `behavior_engine.h`.
- Produces: `EngineState` gains `float dutyL = 0, dutyR = 0; uint32_t dutyMs = 0; bool dutyInit = false;`
- Produces (pure, exported for tests): `float auxTargetDuty(AuxLevel level, bool insideOfLean, bool outsideOfLean, float k, const LogicalState& s, const Config& cfg);` and `float leanFactor(const LogicalState& s, const Config& cfg);` (0..1; 0 when disabled/invalid; `leanFullDeg <= leanStartDeg` -> step at `leanStartDeg`).

Rules (spec 5.3), per lit pod:
- base: Low -> `auxDutyFor(Low)`; Full -> speed curve if `speedScaleEnable && speedValid` (<= `hbSlowKmh`: `min(hbSlowDuty, auxFullDuty)`; >= `hbFullKmh`: `auxFullDuty`; linear between; `hbFullKmh <= hbSlowKmh` -> step at `hbSlowKmh`), else `auxFullDuty`.
- inside (lean > 0 -> right pod; lean < 0 -> left): `base + k*(boost - base)` with boost = `leanBoostDuty` on Low, `auxFullDuty` on Full; result `>= base`.
- outside: `base + k*(leanDimDuty - base)`; result `<= base`.
- all capped at `auxFullDuty`.
- slew: if pod Off -> 0 now; if pod was Off last tick or `!dutyInit` -> jump to target; else move by at most `kAuxSlewPctPerS * (uint32_t)(now - dutyMs) / 1000`. Output `uint8_t` via `lroundf`. A fresh `EngineState` jumps straight to target, so single-tick tests see the target.

- [ ] **Step 1: Write failing tests**

```
test_speed_off_is_today:          high beam, speedScaleEnable false, speed 10 valid -> both 100
test_speed_invalid_is_full:       enabled, speedValid false -> both 100
test_speed_slow_end:              enabled, 15 km/h -> both 50
test_speed_full_end:              90 km/h -> both 100
test_speed_middle:                50 km/h -> both 75
test_speed_slow_capped_by_full:   auxFullDuty 40, hbSlowDuty 50, 10 km/h -> 40
test_lean_off_is_today:           night, leanEnable false, lean 30 -> both 15
test_lean_right_night:            night, lean +30 -> R 60, L 5  (Review Focus 2)
test_lean_left_night:             lean -30 -> L 60, R 5
test_lean_middle_night:           lean +20 -> R 37.5->38 (rounded), L 10
test_lean_below_start:            lean +9 -> both 15
test_lean_high_beam_inside_full:  high beam, speed 15 (base 50), lean +30 -> R 100, L 5
test_boost_never_below_base:      night, leanBoostDuty 10 (< low 15), lean +30 -> R 15
test_dim_never_above_base:        night, leanDimDuty 40, lean +30 -> L 15
test_hazards_lean_night_both_off: night, hazards, lean +30 -> both Off, duties 0  (Review Focus 4)
test_indicate_inside_off:         night, right indicating, lean +30 -> R Off 0, L 5
test_lean_invalid_is_today:       leanEnable, leanValid false, lean 30 -> both 15
test_slew_limits_step:            tick night upright (fresh state jumps to 15), then lean +30 one tick 100 ms later -> R 40 (15 + max step 25), L 5 (gap 10 < 25)
test_slew_reaches_target:         same, after 200 ms more -> R 60
test_pod_on_jumps_to_target:      day (pods off) -> high beam at 90 km/h -> both 100 on the first tick
test_pod_off_immediate:           lit at 60, then left indicating -> L 0 on that tick
test_slew_across_millis_wrap:     first tick night upright at now = 0xFFFFFFF6 (jumps to 15), next tick lean +30 at now = 90 (dt 100 ms wrap-safe) -> R 40. Naive arithmetic gives a huge or negative dt and R 60 or 15, so the assertion separates them.  (Review Focus 5)
```

- [ ] **Step 2:** Suite -> FAIL.
- [ ] **Step 3:** Implement; `computeOutputs` keeps the indicator rule last and sets `auxDutyL/R` from the slewed values.
- [ ] **Step 4:** Suite and full native run -> PASS.

---

### Task 6: Protocol 8, live values, lean scenarios

**Files:**
- Modify: `src/domain/web_protocol.{h,cpp}`, `src/domain/test_mode.{h,cpp}`, `src/main.cpp`
- Test: `test/test_web_protocol/`, `test/test_test_mode/`

**Interfaces:**
- Produces: `kProtocolVersion = 8`; history: "Version 8 added speed/lean signals (maps.speed, maps.lean), the cornering and speed settings, and `signals` on `frames`."
- Produces: `std::string framesMessage(const CanFrameSnapshot* frames, int count, const LogicalState& live);` adds `"signals":{"speed":f,"speedValid":b,"lean":f,"leanValid":b}`. `main.cpp` passes `g_can.evaluate(g_cfg, now)`.
- Produces: scenarios `leanLeftNight` and `leanRightNight` appended after `highBeam`: run, night, low beam, `leanDeg` -30 / +30, `leanValid` true.

- [ ] **Step 1: Write failing tests**

```
test_frames_carry_signals:         leanDeg -23.5 valid, speed invalid -> JSON signals.lean -23.5, leanValid true, speedValid false
test_protocol_version_8:           device_info protocolVersion == 8
test_lean_scenarios_resolve:       scenarioByName("leanRightNight") -> leanDeg 30, leanValid, night, run
test_lean_scenario_obeys_setting:  leanEnable false -> both pods 15; true -> R 60, L 5
```
(`test_every_advertised_scenario_name_resolves` covers the new names automatically.)

- [ ] **Step 2:** Suites -> FAIL.
- [ ] **Step 3:** Implement. `mk()` stays seven bools; build the two lean scenarios from `mk(...)` then set the lean fields (a second constexpr helper).
- [ ] **Step 4:** Full native run -> PASS; ESP32 build -> SUCCESS.

---

### Task 7: Web app

**Files:**
- Modify: `data/index.html`, `data/app.js`, `data/style.css` (only if needed); `scripts/check_app_mirrors.py` only if its parse breaks

**Interfaces:**
- Consumes: protocol 8 config keys, `frames.signals`, scenario names.

Requirements:
- `PROTOCOL_VERSION = 8` in `app.js`; add `"leanLeftNight","leanRightNight"` to the scenario list (labels "Lean left (night)", "Lean right (night)").
- Mapping tab: after the bit maps, a "Number signals" block with rows Speed (km/h) and Lean (deg, + = right): inputs ID (hex like the bit maps), start bit, length, byte order (Intel/Motorola select), signed (checkbox), scale, offset, and a live readout (`speed.toFixed(1)` / `lean.toFixed(1)`, "—" when invalid). Length 0 or blank = unmapped (omit the key).
- Live readout: while the Mapping tab is open, send `discovery enable:true`; on leaving it, restore whatever `discToggle` says. `renderFrames` also updates the readouts from `msg.signals`.
- Tunables: two fieldsets, "High beam by speed" (`speedScaleEnable`, `hbSlowKmh`, `hbFullKmh`, `hbSlowDuty`) and "Cornering" (`leanEnable`, `leanStartDeg`, `leanFullDeg`, `leanBoostDuty`, `leanDimDuty`), inputs with the Task 3 ranges, filled and saved the way `auxLowDuty` is.

- [ ] **Step 1:** Implement.
- [ ] **Step 2:** `python scripts/check_app_mirrors.py` -> exit 0.
- [ ] **Step 3:** ESP32 build -> SUCCESS (regenerates `web_assets.h`).
- [ ] **Step 4:** Open `data/index.html` in the browser pane with a stubbed WebSocket (or by reading) to check both new blocks render at phone width; note in the hand-over that the live check needs the board.

---

### Task 8: Final verification and hand-over

- [ ] **Step 1:** `python -m platformio test -e native` -> all PASS (count reported).
- [ ] **Step 2:** `py -3.13 -m platformio run -e esp32` -> SUCCESS, flash/RAM % reported.
- [ ] **Step 3:** `python scripts/check_app_mirrors.py` -> 0.
- [ ] **Step 4:** Whole-branch review against the spec.
- [ ] **Step 5:** Owner review. On-bike checklist for the owner: map signals from the SavvyCAN log; live values match dash speed and lean direction; enable each feature and try it on the stand; GPIO 12 forced-restart test with the right pod lit.
