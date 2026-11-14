# Aux Pod PWM Firmware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drive the Oxford pods' main LEDs at a configurable PWM duty, so night Low and high-beam Full both work, instead of holding Low off.

**Architecture:** The behaviour engine already resolves `AuxLevel` per pod. This plan powers a pod's switch at Low as well as Full, adds one shared duty (`OutputIntent::auxDuty`, percent) chosen from two new config values, and writes that duty to a single LEDC channel *before* the switches on every tick. The web app gets two percentage inputs and the protocol goes to 6. Because the phase-A pin map has no free GPIO, the PWM takes GPIO 13 from the status LED, and the factory-reset gesture's feedback moves onto the indicator outputs.

**Tech Stack:** C++17, Arduino-ESP32 core 3.3.4 (`ledcAttach(pin, freq, bits)` / `ledcWrite(pin, duty)`), PlatformIO, Unity (native tests), ArduinoJson 7, vanilla JS web app.

**Spec:** `docs/superpowers/specs/2026-11-01-aux-night-mode-design.md` §6.1 (binding), with `docs/superpowers/specs/2026-10-17-emarked-module-redesign-design.md` §2.2.1 for the measurements.

## Global Constraints

- Branch: `plan7-aux-pwm`, cut from `plan6-night-mode` (PR #1 is not merged yet).
- Native tests: `python -m platformio test -e native`. ESP32 build: `py -3.13 -m platformio run -e esp32`. Mirror check: `python scripts/check_app_mirrors.py`.
- `auxLowDuty` default **15** (%), `auxFullDuty` default **100** (%), both `uint8_t`, both clamped to 0–100 wherever they enter.
- PWM frequency `kAuxPwmHz = 100`, a compile-time constant, not user config (spec: "about 100 Hz", exact value still to be measured).
- LEDC resolution 10 bits.
- **Duty is written before the switches**, every tick. A pod must never light at a higher duty than its level asks for, including for one tick.
- Low is never brighter than Full: the Low duty is `min(auxLowDuty, auxFullDuty)`.
- Every engine test asserts the whole output state (`on`, `auxL`, `auxR`, `auxDuty`), as the existing suite does.
- Web protocol version goes 5 → **6**: "Version 6 added auxLowDuty and auxFullDuty."
- **D1 (user decision, needed before Task 5):** the PWM pin is **GPIO 13**, freed by removing status LED D5. If the user picks another pin, only `kAuxPwmPin` and Task 5's LED removal change.

## Review Focus

1. **`auxLowDuty` set above `auxFullDuty`**: Low must not be brighter than Full. Test in Task 2.
2. **An imported or hand-edited config with 250 or -5 for a duty**: it must clamp to 100 or 0, never wrap a `uint8_t`. Test in Task 1.
3. **Reset and boot**: the PWM must be attached at duty 0 before any output can switch a pod on. Covered by the write order in Task 3 and the `setup()` order in Task 5.
4. **The test-mode output walk with an aux bit on**: the pod must light at the Low duty, never at Full. Test in Task 2.
5. **A config saved before this change, without the keys**: it must load 15 / 100. Test in Task 1.

---

### Task 1: Config values and JSON

**Files:**
- Modify: `src/domain/config.h`, `src/domain/config_json.cpp`
- Test: `test/test_config_defaults/test_config_defaults.cpp`, `test/test_config_json/test_config_json.cpp`

**Interfaces:**
- Produces: `Config::auxLowDuty` and `Config::auxFullDuty` (`uint8_t`, percent); `constexpr uint32_t kAuxPwmHz = 100;` in `config.h`.

- [ ] **Step 1: Create the branch**

```bash
git switch plan6-night-mode && git switch -c plan7-aux-pwm
```

- [ ] **Step 2: Write the failing tests**

In `test_config_defaults.cpp`, extend the defaults test:
```cpp
TEST_ASSERT_EQUAL_UINT8(15, c.auxLowDuty);
TEST_ASSERT_EQUAL_UINT8(100, c.auxFullDuty);
```
In `test_config_json.cpp` add and register:
```cpp
void test_aux_duties_round_trip() {
  Config in = defaultConfig(); in.auxLowDuty = 22; in.auxFullDuty = 80;
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_EQUAL_UINT8(22, out.auxLowDuty);
  TEST_ASSERT_EQUAL_UINT8(80, out.auxFullDuty);
}
void test_aux_duties_clamp_out_of_range() {
  bool ok = false;
  Config c = configFromJson("{\"auxLowDuty\":250,\"auxFullDuty\":-5}", ok);
  TEST_ASSERT_EQUAL_UINT8(100, c.auxLowDuty);
  TEST_ASSERT_EQUAL_UINT8(0, c.auxFullDuty);
}
void test_aux_duties_missing_keys_use_defaults() {
  bool ok = false;
  Config c = configFromJson("{\"blinkPeriodMs\":340}", ok);
  TEST_ASSERT_EQUAL_UINT8(15, c.auxLowDuty);
  TEST_ASSERT_EQUAL_UINT8(100, c.auxFullDuty);
}
```
Use whatever serialiser name the file already uses for `configToJson`.

- [ ] **Step 3: Run to verify they fail**

Run: `python -m platformio test -e native -f test_config_defaults -f test_config_json`
Expected: compile failure, `auxLowDuty` is not a member of `Config`.

- [ ] **Step 4: Implement**

`config.h`: add `uint8_t auxLowDuty = 15;` and `uint8_t auxFullDuty = 100;` to `Config` with a one-line comment each, and `kAuxPwmHz` beside the other constants. `config_json.cpp`: write both keys. Read each as `int` with the current value as fallback, then clamp to 0–100 before narrowing.

- [ ] **Step 5: Run to verify they pass**

Run: `python -m platformio test -e native -f test_config_defaults -f test_config_json`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/domain/config.h src/domain/config_json.cpp test/test_config_defaults test/test_config_json
git commit -m "feat: add auxLowDuty and auxFullDuty config, clamped to 0-100"
```

---

### Task 2: Engine powers pods at Low and sets one shared duty

**Files:**
- Modify: `src/domain/outputs.h`, `src/domain/behavior_engine.cpp:93-105`, `src/domain/test_mode.cpp:68-69`
- Test: `test/test_behavior_engine/test_behavior_engine.cpp`, `test/test_test_mode/test_test_mode.cpp`, `test/test_output_map/test_output_map.cpp`

**Interfaces:**
- Consumes: `Config::auxLowDuty`, `Config::auxFullDuty` (Task 1).
- Produces: `uint8_t OutputIntent::auxDuty` (percent, default 0, compared in `operator==`); `uint8_t auxDutyFor(AuxLevel level, const Config& cfg)` declared in `behavior_engine.h`. Off → 0, Low → `min(auxLowDuty, auxFullDuty)`, Full → `auxFullDuty`.

Rules this task implements:
- `OUT_AUX_L` / `OUT_AUX_R` are set when that pod's level is **not Off**. This replaces "set only at Full".
- `o.auxDuty = auxDutyFor(base)` when either pod is not Off, else 0. One duty is enough because every non-Off pod has level `base`; darkening only makes a pod Off.
- Test mode `Zones`: return `t.zones` with `auxDuty = auxDutyFor(AuxLevel::Low, cfg)` if either aux bit is set, else 0.
- Rewrite the comments in `outputs.h` that say an aux bit is set only at Full and that Low drives nothing.

- [ ] **Step 1: Write the failing tests**

In `test_behavior_engine.cpp`, using the file's existing night/high-beam setup helpers, add and register:
- `test_night_low_powers_both_pods_at_low_duty`: night, run, no high beam. Expect `o.on` includes `OUT_AUX_L` and `OUT_AUX_R`, `auxL == auxR == Low`, `auxDuty == 15`.
- `test_high_beam_full_duty`: expect both aux bits, `Full`, `auxDuty == 100`.
- `test_low_never_brighter_than_full`: `auxLowDuty = 90, auxFullDuty = 60`, night. Expect `auxDuty == 60`.
- `test_day_pods_off_duty_zero`: day, run. Aux bits clear, `auxDuty == 0`.
- `test_not_run_pods_off_duty_zero`: night, `run = false`. Aux bits clear, `auxDuty == 0`.
- `test_darken_unpowers_indicating_pod_only`: `auxDarkenOnIndicate = true`, night, left indicator. Expect `OUT_AUX_L` clear, `OUT_AUX_R` set, `auxDuty == 15`.

Then update every existing test that asserts a whole word at night Low: add the two aux bits to its expected mask and assert `auxDuty`.

In `test_test_mode.cpp` add `test_zones_aux_bit_lights_at_low_duty`: a Zones session with mask `outMask(OUT_AUX_L)` and default config resolves to `auxDuty == 15`; with mask `outMask(OUT_FL_DRL)` it resolves to `auxDuty == 0`.

In `test_output_map.cpp` add `test_intents_differing_only_in_duty_are_unequal`.

- [ ] **Step 2: Run to verify they fail**

Run: `python -m platformio test -e native -f test_behavior_engine -f test_test_mode -f test_output_map`
Expected: compile failure on `auxDuty`, then assertion failures on the aux bits at Low.

- [ ] **Step 3: Implement** the rules above in the listed files.

- [ ] **Step 4: Run the whole native suite**

Run: `python -m platformio test -e native`
Expected: all PASS (177 before this plan, plus the new tests).

- [ ] **Step 5: Commit**

```bash
git add src/domain test/test_behavior_engine test/test_test_mode test/test_output_map
git commit -m "feat: power aux pods at Low and carry one shared PWM duty"
```

---

### Task 3: Write the duty before the switches

**Files:**
- Create: `src/hal/iaux_pwm.h`, `src/domain/aux_pwm.h`
- Modify: `src/domain/output_map.h`, `src/domain/output_map.cpp`
- Test: `test/test_output_map/test_output_map.cpp`

**Interfaces:**
- Produces:
  - `class IAuxPwm { public: virtual ~IAuxPwm() = default; virtual void setDuty(uint8_t percent) = 0; };` in `hal/iaux_pwm.h`. Implementations clamp anything above 100.
  - `void applyIntent(IOutputs& out, IAuxPwm& pwm, const OutputIntent& o);` replaces the two-argument form. It calls `pwm.setDuty(o.auxDuty)` first, then every `setOutput`.
  - `constexpr uint32_t ledcDutyFor(uint8_t percent, uint8_t bits)` in `domain/aux_pwm.h`: `min(percent,100) * (1u << bits) / 100`, so 100% is `1 << bits` (LEDC's always-on value).

- [ ] **Step 1: Write the failing tests**

Give the file's fake a shared event log, and add a `FakePwm : IAuxPwm` that appends to it. Add and register:
- `test_apply_writes_duty_before_any_output`: the first logged event is the duty write, carrying `o.auxDuty`.
- `test_apply_writes_duty_every_call`: two calls, two duty writes.
- `test_ledc_duty_mapping`:
```cpp
TEST_ASSERT_EQUAL_UINT32(0,    ledcDutyFor(0, 10));
TEST_ASSERT_EQUAL_UINT32(153,  ledcDutyFor(15, 10));
TEST_ASSERT_EQUAL_UINT32(1024, ledcDutyFor(100, 10));
TEST_ASSERT_EQUAL_UINT32(1024, ledcDutyFor(250, 10));
```
Update the existing `applyIntent` tests to pass a `FakePwm`.

- [ ] **Step 2: Run to verify they fail**

Run: `python -m platformio test -e native -f test_output_map`
Expected: compile failure, no three-argument `applyIntent`.

- [ ] **Step 3: Implement** the interfaces above.

- [ ] **Step 4: Run to verify they pass**

Run: `python -m platformio test -e native`
Expected: all PASS. `main.cpp` does not compile on ESP32 yet; Task 5 fixes it.

- [ ] **Step 5: Commit**

```bash
git add src/hal/iaux_pwm.h src/domain/aux_pwm.h src/domain/output_map.* test/test_output_map
git commit -m "feat: applyIntent writes the aux PWM duty before the switches"
```

---

### Task 4: Web protocol 6 and the two brightness inputs

**Files:**
- Modify: `src/domain/web_protocol.h`, `data/index.html:40-43`, `data/app.js` (`render()` ~line 170, `collect()` ~line 327, `PROTOCOL_VERSION`)
- Test: `test/test_web_protocol/test_web_protocol.cpp`

**Interfaces:**
- Consumes: Task 1's keys, which `configToJson` already writes.

- [ ] **Step 1: Write the failing tests**

Rename `version_is_five` to `version_is_six` and assert 6. In the config-message test that checks `"nightHoldMs":800`, also assert `"auxLowDuty":15` and `"auxFullDuty":100`. In the round-trip test, set `auxLowDuty = 33` and assert it comes back.

- [ ] **Step 2: Run to verify they fail**

Run: `python -m platformio test -e native -f test_web_protocol`
Expected: FAIL on the version.

- [ ] **Step 3: Implement**

- `kProtocolVersion = 6`, with the version-6 sentence in the history comment.
- `index.html`: after the darken checkbox, add `Aux low brightness (%)` (`id="auxLowDuty"`) and `Aux full brightness (%)` (`id="auxFullDuty"`), both `type="number" min="0" max="100" step="1"`.
- `app.js`:
  - `render()` uses `cfg.auxLowDuty ?? 15` and `cfg.auxFullDuty ?? 100`.
  - `collect()` uses `clamp(value, 0, 100)`.
  - An empty field collects as its default (15 or 100), not 0, like `nightHoldMs`.
  - `PROTOCOL_VERSION = 6`.

- [ ] **Step 4: Verify**

Run: `python -m platformio test -e native -f test_web_protocol` → PASS.
Run: `python scripts/check_app_mirrors.py` → exit 0.

- [ ] **Step 5: Commit**

```bash
git add src/domain/web_protocol.h data/index.html data/app.js test/test_web_protocol
git commit -m "feat: web app sets aux low and full brightness; protocol 6"
```

---

### Task 5: LEDC HAL, GPIO 13 and reset feedback on the indicators

**Files:**
- Create: `src/hal/aux_pwm_ledc.h`, `src/hal/aux_pwm_ledc.cpp`, `src/domain/reset_feedback.h`, `src/domain/reset_feedback.cpp`, `test/test_reset_feedback/test_reset_feedback.cpp`
- Modify: `src/main.cpp` (pins ~line 32, `serviceLighting()` ~line 114, `serviceResetButton()` ~lines 136-158, `setup()` ~line 171)

**Interfaces:**
- Consumes: `IAuxPwm`, `ledcDutyFor`, three-argument `applyIntent` (Task 3); `kAuxPwmHz` (Task 1); `ResetPhase` from `domain/reset_sequence.h`.
- Produces:
  - `class LedcAuxPwm : public IAuxPwm { public: LedcAuxPwm(uint8_t pin, uint32_t freqHz); bool begin(); void setDuty(uint8_t percent) override; };`. `begin()` calls `ledcAttach(pin, freqHz, 10)` then writes duty 0. `setDuty` writes `ledcDutyFor(percent, 10)`.
  - `OutputIntent withResetFeedback(OutputIntent o, ResetPhase phase, uint32_t nowMs);` In `Armed`, the four `*_IND` bits are forced on when `((nowMs / 50) & 1) == 0` and off otherwise (10 Hz, as the LED did). In `Confirmed`, all four are forced on. In `Idle` and `Cancelled`, `o` is returned unchanged. Other bits are never touched.

**D1 must be confirmed by the user before this task.**

- [ ] **Step 1: Write the failing tests** in the new `test_reset_feedback.cpp`
- `test_idle_leaves_intent_unchanged`: any intent goes in and comes out equal.
- `test_armed_blinks_all_indicators_at_10hz`: an intent with `OUT_FL_DRL` set. At `nowMs = 0`, expect `outMask(OUT_FL_DRL, OUT_FL_IND, OUT_FR_IND, OUT_RL_IND, OUT_RR_IND)`. At `nowMs = 50`, expect `outMask(OUT_FL_DRL)`.
- `test_confirmed_holds_all_indicators_on`
- `test_feedback_never_touches_aux`: an intent with aux bits and `auxDuty = 15`, in `Armed`. Aux bits and duty unchanged.

- [ ] **Step 2: Run to verify they fail**

Run: `python -m platformio test -e native -f test_reset_feedback`
Expected: compile failure.

- [ ] **Step 3: Implement `withResetFeedback`, then run the native suite**

Run: `python -m platformio test -e native` → all PASS.

- [ ] **Step 4: Wire the ESP32 build**

In `main.cpp`:
- Replace `kLedStatPin` with `static const int kAuxPwmPin = 13;` and a comment: shared pod PWM; was status LED D5 (spec §6.1).
- Add `static LedcAuxPwm g_auxPwm(kAuxPwmPin, kAuxPwmHz);`.
- In `setup()`, call `g_auxPwm.begin()` **before** `g_out.begin()`.
- In `serviceLighting()`, apply `withResetFeedback(o, g_reset.phase(), now)` and the three-argument `applyIntent`.
- Delete every `digitalWrite(kLedStatPin, ...)` in `serviceResetButton()`, and update its header comment: feedback now shows on the indicators.

- [ ] **Step 5: Build for ESP32**

Run: `py -3.13 -m platformio run -e esp32`
Expected: `SUCCESS`.

- [ ] **Step 6: Commit**

```bash
git add src/hal/aux_pwm_ledc.* src/domain/reset_feedback.* src/main.cpp test/test_reset_feedback
git commit -m "feat: drive pod PWM on GPIO 13; reset feedback on the indicators"
```

**On-device checks, for the user** (not automated). Use the bench supply and one pod on the board:
- Yellow measures about 100 Hz at about 15% duty in night Low, and is flat at 100% on high beam.
- No pod output and 0 V on yellow from power-on until the first CAN frame.
- Holding BOOT 10 s blinks all four indicators.
- The hardware README's pin rules list GPIO 13 as `AUX_PWM`. That edit belongs to the schematic work on the plan4 worktree, not this branch.
