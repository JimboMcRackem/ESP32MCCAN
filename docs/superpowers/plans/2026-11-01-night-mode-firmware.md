# Night Mode Firmware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the bike day and night front lighting, a flash-switch night toggle and full-length generated indicator flashes, with low aux held off until the Oxford kit shows how to dim it.

**Architecture:** All behaviour stays in the host-tested `computeOutputs`. `OutputIntent` gains a per-pod `AuxLevel`, and its existing 12-bit word stays what the HAL drives: an aux bit is set only at `Full`, so `Low` is off without any HAL change.

**Tech Stack:** C++ on ESP32 (Arduino, PlatformIO), Unity native tests, ArduinoJson, vanilla JS web app.

**Spec:** `docs/superpowers/specs/2026-11-01-aux-night-mode-design.md`

## Global Constraints

- Branch: `plan6-night-mode`. Stage files by name. Never use `git add -A`: `hardware/` is untracked and this repo is public.
- Native tests: `python -m platformio test -e native`. ESP32 build: `py -3.13 -m platformio run -e esp32`.
- Every test file must define `setUp` and `tearDown`.
- Elapsed time is always `(uint32_t)(now - then) >= threshold`. Choose rollover samples by the asserted value under correct and banned arithmetic (project memory: `timing-test-sample-points`).
- Tests assert the whole `.on` word, plus `auxL` and `auxR` where aux matters.
- A pod must never light at full because low was requested.
- Hold time default 800 ms. Blink default 340 ms. `FunctionMap.count == 0` means unassigned.

**Out of scope, kit-gated:** `auxLowStage`, the `AUX_MODE` output and any HAL dimming. `auxLowStage` is left out because it would be a web control that does nothing.

## Review Focus

1. Steady high beam held for minutes: night mode must not change. Pinned in Task 2.
2. A bus dropout during a held flash: the press restarts and does not toggle early. Pinned in Task 2.
3. Indicator cancelled and re-applied quickly: a new full on-phase starts. Pinned in Task 1.
4. One side indicating, then hazards pressed: the running side's rhythm is undisturbed. Pinned in Task 1.
5. An imported config with `nightHoldMs: 0`: a short flash must not toggle night mode. Pinned in Task 2.

---

### Task 0: Bring in the phone-updates branch

`plan5-updates` is unmerged, changes `main.cpp`, `web_protocol`, `data/*` and test files, and already takes the protocol to version 4. Merging first avoids two different version 4s.

**Files:** merge only.

- [ ] **Step 1: Merge.** Run `git merge --no-ff plan5-updates`. Expected: clean, or a conflict limited to `docs/superpowers/specs/2026-10-17-emarked-module-redesign-design.md`; keep both changes.
- [ ] **Step 2: Baseline.** Run `python -m platformio test -e native` and `python scripts/check_app_mirrors.py`. Expected: all pass, and `PROTOCOL_VERSION=4`. Stop if not.

### Task 1: Generated flash starts with a full on-phase

**Files:**
- Modify: `src/domain/config.h`, `src/domain/config_json.cpp`, `src/domain/behavior_engine.h`, `src/domain/behavior_engine.cpp`
- Test: `test/test_behavior_engine/test_behavior_engine.cpp`, `test/test_config_defaults/test_config_defaults.cpp`, `test/test_config_json/test_config_json.cpp`, `test/test_test_mode/test_test_mode.cpp`

**Interfaces:**
- Produces: `EngineState::flashAnchorMs` (`uint32_t`, default 0); `Config::flashSource` default `FlashSource::Generate`.

- [ ] **Step 1: Write the failing tests** in `test_behavior_engine.cpp`, registered in `main`. All use default config unless stated.

```cpp
void test_generate_first_on_phase_is_full_from_any_start_time() {
  // 500 % 680 is a dark half under a free-running phase, so it must not matter.
  Config cfg = defaultConfig(); EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 500, est).isOn(OUT_FL_IND));
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 500 + 339, est).isOn(OUT_FL_IND));
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, 500 + 340, est).isOn(OUT_FL_IND));
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 500 + 680, est).isOn(OUT_FL_IND));
}

void test_reapplied_indicator_gets_a_new_full_on_phase() {
  Config cfg = defaultConfig(); EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  computeOutputs(s, cfg, 0, est);
  s.leftInd = false; computeOutputs(s, cfg, 400, est);
  s.leftInd = true;                        // elapsed from 0 would be dark
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 410, est).isOn(OUT_FL_IND));
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 410 + 339, est).isOn(OUT_FL_IND));
}

void test_hazards_starting_one_tick_apart_stay_in_phase() {
  Config cfg = defaultConfig(); EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  computeOutputs(s, cfg, 500, est);
  s.rightInd = true;
  computeOutputs(s, cfg, 510, est);
  OutputIntent o = computeOutputs(s, cfg, 500 + 345, est);  // both dark
  TEST_ASSERT_FALSE(o.isOn(OUT_FL_IND));
  TEST_ASSERT_FALSE(o.isOn(OUT_FR_IND));
  o = computeOutputs(s, cfg, 500 + 680, est);               // both lit
  TEST_ASSERT_TRUE(o.isOn(OUT_FL_IND));
  TEST_ASSERT_TRUE(o.isOn(OUT_FR_IND));
}

void test_adding_a_side_does_not_disturb_the_running_side() {
  Config cfg = defaultConfig(); EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  computeOutputs(s, cfg, 0, est);
  s.rightInd = true;
  computeOutputs(s, cfg, 400, est);        // joins during the dark half
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, 500, est).isOn(OUT_FL_IND));
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, 500, est).isOn(OUT_FR_IND));
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 680, est).isOn(OUT_FL_IND));
}

void test_generate_phase_survives_millis_rollover() {
  // Elapsed 768 -> lit. A free-running 0x200 % 680 == 512 would read dark.
  Config cfg = defaultConfig(); EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  computeOutputs(s, cfg, 0xFFFFFF00u, est);
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 0x200u, est).isOn(OUT_FL_IND));
}
```

Also change `test_default_flash_source_is_auto` to `test_default_flash_source_is_generate`, and `test_unknown_flash_source_resolves_to_auto` to `test_unknown_flash_source_resolves_to_generate`, asserting `FlashSource::Generate` for all three inputs. Add to `test_flash_source_round_trips` a second round trip of `FlashSource::Auto`.

- [ ] **Step 2: Fix existing tests for the new default.** In `test_behavior_engine.cpp`, set `cfg.flashSource = FlashSource::Auto;` in every `test_auto_*` test. In the two dark-phase tests, add `computeOutputs(s, cfg, 0, est);` before the `PHASE_OFF` sample, because the phase now starts at the first request. Replace the "default Auto" comments there and in `test_test_mode.cpp` with a one-line note that the phase starts at the request.

- [ ] **Step 3: Run tests.** Run `python -m platformio test -e native -f test_behavior_engine -f test_config_defaults -f test_config_json`. Expected: FAIL on the new tests.

- [ ] **Step 4: Implement.**
  - `config.h`: default `FlashSource::Generate`. Reword the enum comment: `Generate` is the default because the board drives all four corners.
  - `config_json.cpp`: start from `FlashSource::Generate`; map `"auto"` and `"follow"`. Update the comment.
  - `computeOutputs`, before the phases are computed:

```cpp
const bool stillFlashing = (est.leftTimer.prev && li) || (est.rightTimer.prev && ri);
const bool starting = (li && !est.leftTimer.prev) || (ri && !est.rightTimer.prev);
if (starting && !stillFlashing) est.flashAnchorMs = nowMs;
```

  - Pass `est.flashAnchorMs` to `indicatorPhase`. `Generate` uses `((uint32_t)(nowMs - anchorMs) % (2 * period)) < period`. `Auto`'s fallback keeps `flashIsOn`, whose rollover tests are unchanged.

- [ ] **Step 5: Run all native tests.** Run `python -m platformio test -e native`. Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add src/domain/config.h src/domain/config_json.cpp src/domain/behavior_engine.h src/domain/behavior_engine.cpp test/test_behavior_engine/test_behavior_engine.cpp test/test_config_defaults/test_config_defaults.cpp test/test_config_json/test_config_json.cpp test/test_test_mode/test_test_mode.cpp
git commit -m "feat: generated flash starts with a full on-phase, and is the default"
```

### Task 2: Night mode, aux levels and removing the spot latch

**Files:**
- Modify: `src/domain/outputs.h`, `src/domain/config.h`, `src/domain/config_json.cpp`, `src/domain/behavior_engine.h`, `src/domain/behavior_engine.cpp`, `src/domain/test_mode.h`, `src/domain/test_mode.cpp`
- Test: `test/test_behavior_engine/test_behavior_engine.cpp`, `test/test_test_mode/test_test_mode.cpp`, `test/test_config_defaults/test_config_defaults.cpp`, `test/test_config_json/test_config_json.cpp`, `test/test_web_protocol/test_web_protocol.cpp`, `test/test_types/test_types.cpp` if it compares intents

**Interfaces:**
- Consumes: `EngineState::flashAnchorMs` from Task 1.
- Produces:
  - `enum class AuxLevel : uint8_t { Off, Low, Full };` in `outputs.h`
  - `OutputIntent::auxL`, `OutputIntent::auxR`, default `AuxLevel::Off`, included in `operator==`
  - `Config::nightHoldMs` (800), `Config::auxDarkenOnIndicate` (false); `Config::spotHoldMs` removed
  - `EngineState::nightToggled`, `EngineState::pressUsed` (both `bool`); `spotLatched` removed

- [ ] **Step 1: Write the failing tests** in `test_behavior_engine.cpp`. Delete `test_spot_latch_holds_aux_on_after_a_long_flash_press` and `test_spot_hold_survives_millis_rollover`, and their `RUN_TEST` lines. Add these helpers and tests, and register them:

```cpp
static Config mappedNight() {
  Config c = defaultConfig();
  mapFor(c, Function::DayNight).count = 1;
  return c;
}
static void hold(LogicalState s, const Config& c, uint32_t from, uint32_t ms, EngineState& e) {
  for (uint32_t t = 0; t <= ms; t += 10) computeOutputs(s, c, from + t, e);
}
```

| Test | State | Expected |
|---|---|---|
| `test_night_drops_front_white_and_puts_pods_at_low` | run, night, mapped | `.on` is `RL_DRL, RR_DRL`; `auxL` and `auxR` `Low` |
| `test_day_has_pods_off` | run, mapped, not night | `.on` is four DRLs; both `Off` |
| `test_high_beam_day_is_full_with_front_white` | run, highBeam | `.on` is four DRLs, `AUX_L`, `AUX_R`; both `Full` |
| `test_high_beam_night_is_full_without_front_white` | run, night, highBeam, mapped | `.on` is `RL_DRL`, `RR_DRL`, `AUX_L`, `AUX_R`; both `Full` |
| `test_low_never_sets_an_aux_bit` | run, night, mapped | `.on & outMask(OUT_AUX_L, OUT_AUX_R)` is 0 |
| `test_night_indicator_shows_amber_only_and_pods_stay_low` | run, night, leftInd, mapped, at t=0 | `.on` is `RR_DRL`, `FL_IND`, `RL_IND`; both `Low` |
| `test_run_clear_at_night_turns_pods_off` | night, mapped, not run | both `Off` |
| `test_short_flash_leaves_pods_alone` | run, flash, t=0 | both `Off`, `.on` is four DRLs |
| `test_darken_turns_off_the_indicating_pod_only` | darken on, run, night, leftInd, mapped | `auxL` `Off`, `auxR` `Low` |
| `test_darken_follows_the_request_not_the_phase` | as above, sampled after 345 ms (dark half) | `auxL` still `Off` |
| `test_darken_skips_hazards` | darken on, both indicators | both `Low` |
| `test_darken_skips_high_beam` | darken on, leftInd, highBeam | both `Full` |
| `test_darken_is_off_by_default` | no setting, night, leftInd | both `Low` |

Long-press tests, which use default config unless stated:

```cpp
void test_long_flash_toggles_night_once_per_press() {
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  hold(s, c, 0, 790, e);
  TEST_ASSERT_FALSE(e.nightToggled);
  hold(s, c, 800, 3000, e);                // still held: exactly one toggle
  TEST_ASSERT_TRUE(e.nightToggled);
  s.flash = false; computeOutputs(s, c, 4000, e);
  s.flash = true;  hold(s, c, 4010, 800, e);
  TEST_ASSERT_FALSE(e.nightToggled);
}

void test_toggle_sets_low_pods_on_the_same_tick() {
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  computeOutputs(s, c, 0, e);
  TEST_ASSERT_EQUAL_INT((int)AuxLevel::Low, (int)computeOutputs(s, c, 800, e).auxL);
}

void test_steady_high_beam_never_toggles() {
  // HighBeam = bit 6 AND bit 16, HighBeamFlash = bit 16: flash reads true too.
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.flash = true; s.highBeam = true;
  hold(s, c, 0, 120000, e);
  TEST_ASSERT_FALSE(e.nightToggled);
}

void test_high_beam_at_any_point_cancels_the_press() {
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  hold(s, c, 0, 400, e);
  s.highBeam = true;  computeOutputs(s, c, 410, e);
  s.highBeam = false; hold(s, c, 420, 2000, e);  // flash never released
  TEST_ASSERT_FALSE(e.nightToggled);
}

void test_toggled_press_moving_to_high_beam_does_not_toggle_back() {
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  hold(s, c, 0, 800, e);
  TEST_ASSERT_TRUE(e.nightToggled);
  s.highBeam = true; hold(s, c, 810, 2000, e);
  TEST_ASSERT_TRUE(e.nightToggled);
}

void test_mapped_daynight_ignores_the_long_press() {
  Config c = mappedNight(); EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  hold(s, c, 0, 2000, e);
  TEST_ASSERT_FALSE(e.nightToggled);
  TEST_ASSERT_EQUAL_INT((int)AuxLevel::Off, (int)computeOutputs(s, c, 2010, e).auxL);
}

void test_bus_dropout_restarts_the_press() {
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  hold(s, c, 0, 700, e);
  computeOutputs(LogicalState{}, c, 710, e);  // stale bus reads all false
  hold(s, c, 720, 700, e);                    // 700 ms since the restart
  TEST_ASSERT_FALSE(e.nightToggled);
}

void test_zero_hold_falls_back_to_800ms() {
  Config c = defaultConfig(); c.nightHoldMs = 0; EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  hold(s, c, 0, 790, e);
  TEST_ASSERT_FALSE(e.nightToggled);
  hold(s, c, 800, 0, e);
  TEST_ASSERT_TRUE(e.nightToggled);
}

void test_night_hold_survives_millis_rollover() {
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  computeOutputs(s, c, 0xFFFFFF00u, e);
  // `now >= then + 800` compares with 0x220 and fires here, 16 ms in.
  computeOutputs(s, c, 0xFFFFFF10u, e);
  TEST_ASSERT_FALSE(e.nightToggled);
  computeOutputs(s, c, 0x200u, e);            // 768 ms
  TEST_ASSERT_FALSE(e.nightToggled);
  computeOutputs(s, c, 0x220u, e);            // 800 ms
  TEST_ASSERT_TRUE(e.nightToggled);
}
```

In `test_test_mode.cpp`, replace `test_scenario_cannot_corrupt_the_real_engine_state`:

```cpp
void test_scenario_cannot_corrupt_the_real_engine_state(void) {
  LogicalState real;
  TestMode t;
  TEST_ASSERT_TRUE(scenarioByName("lowBeam", t.scenario));   // night scenario
  t.kind = TestKind::Scenario;
  t.scenario.flash = true;
  for (uint32_t ms = 0; ms <= cfg.nightHoldMs + 100; ms += 10) {
    resolveOutputs(real, t, cfg, ms, est, testEst);
  }
  TEST_ASSERT_TRUE_MESSAGE(testEst.nightToggled, "the scenario runs at night");
  TEST_ASSERT_FALSE_MESSAGE(est.nightToggled, "the real engine must stay in day");
  TEST_ASSERT_FALSE(est.flashPrev);
}

void test_night_scenario_shows_night_with_daynight_unassigned(void) {
  LogicalState real;
  TestMode t;
  TEST_ASSERT_TRUE(scenarioByName("lowBeam", t.scenario));
  t.kind = TestKind::Scenario;
  OutputIntent o = resolveOutputs(real, t, cfg, 0, est, testEst);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_RL_DRL, OUT_RR_DRL), o.on);
  TEST_ASSERT_EQUAL_INT((int)AuxLevel::Low, (int)o.auxL);
}
```

In config tests: rename `spotHoldMs` to `nightHoldMs`. Add `test_old_spot_hold_key_is_honoured`: `{"spotHoldMs":1234}` gives 1234. Add `test_new_hold_key_wins`: both keys present, `nightHoldMs` wins. Add `test_aux_darken_round_trips`, and assert the default is false. In `test_web_protocol.cpp`, rename the field at both uses.

- [ ] **Step 2: Run tests.** Run `python -m platformio test -e native`. Expected: compile failure on the new names.

- [ ] **Step 3: Implement the types and config.** In `outputs.h`, add `AuxLevel` and the two fields, and reword the "no PWM" comment: `on` is what the HAL drives, and an aux bit is set only at `Full`. Add `Config::nightHoldMs` and `auxDarkenOnIndicate`, removing `spotHoldMs`. In `config_json.cpp`, write the new keys, and read the hold with `doc["nightHoldMs"] | (doc["spotHoldMs"] | c.nightHoldMs)`.

- [ ] **Step 4: Implement `computeOutputs`.** Remove the spot-latch block and its comment. In the `s.run` block, `FL_DRL` and `FR_DRL` become `!li && !night` and `!ri && !night`. `night` must be resolved first, so run the press logic above that block:

```cpp
const bool dayNightMapped = mapFor(cfg, Function::DayNight).count != 0;
const uint32_t hold = cfg.nightHoldMs ? cfg.nightHoldMs : 800;
if (s.flash && !est.flashPrev) { est.flashRisingMs = nowMs; est.pressUsed = false; }
if (s.highBeam) est.pressUsed = true;   // s.flash is also true on high beam
if (s.flash && !est.pressUsed && s.run && !dayNightMapped &&
    (uint32_t)(nowMs - est.flashRisingMs) >= hold) {
  est.nightToggled = !est.nightToggled;
  est.pressUsed = true;
}
est.flashPrev = s.flash;
const bool night = dayNightMapped ? s.night : est.nightToggled;

const AuxLevel base = !s.run ? AuxLevel::Off
                    : s.highBeam ? AuxLevel::Full
                    : night ? AuxLevel::Low : AuxLevel::Off;
const bool darken = cfg.auxDarkenOnIndicate && base == AuxLevel::Low && li != ri;
o.auxL = (darken && li) ? AuxLevel::Off : base;
o.auxR = (darken && ri) ? AuxLevel::Off : base;
o.set(OUT_AUX_L, o.auxL == AuxLevel::Full);
o.set(OUT_AUX_R, o.auxR == AuxLevel::Full);
```

Keep the existing Experia note on mutually exclusive switch positions, attached to the press logic. Note there that the bike's real flash and high-beam bit states are unconfirmed.

- [ ] **Step 5: Implement test mode.** In `resolveOutputs`' `Scenario` case, set `testEst.nightToggled = t.scenario.night;` before calling `computeOutputs`, so a night scenario works with DayNight unassigned. Update the comment at `test_mode.h:34-35` to name `nightToggled`. Replace the `lowBeam` scenario comment in `test_mode.cpp`: it is now the night preset.

- [ ] **Step 6: Run all native tests.** Run `python -m platformio test -e native`. Expected: PASS.

- [ ] **Step 7: Commit.** Stage the files listed above by name, then:

```bash
git commit -m "feat: day and night front lighting, flash long-press night toggle, aux levels"
```

### Task 3: Web app and protocol version

**Files:**
- Modify: `src/domain/web_protocol.h`, `data/index.html`, `data/app.js`
- Test: `test/test_web_protocol/test_web_protocol.cpp`

**Interfaces:**
- Consumes: JSON keys `nightHoldMs` and `auxDarkenOnIndicate` from Task 2.

- [ ] **Step 1: Write the failing test.** Rename the version test to `test_protocol_version_is_five` and assert 5 in both places that pin the version. Add `test_config_message_carries_the_night_settings`: `configMessage(defaultConfig())` contains `"nightHoldMs":800` and `"auxDarkenOnIndicate":false`.
- [ ] **Step 2: Run it.** Run `python -m platformio test -e native -f test_web_protocol`. Expected: FAIL on the version.
- [ ] **Step 3: Implement.**
  - `web_protocol.h`: `kProtocolVersion = 5`, and add to the history comment: "Version 5 renamed spotHoldMs to nightHoldMs and added auxDarkenOnIndicate."
  - `index.html`: replace the spot field with `Night mode hold (ms)`, id `nightHoldMs`, same limits. Add a checkbox, id `auxDarkenOnIndicate`, labelled `Turn off the indicating side's aux pod at night`.
  - `app.js`: `PROTOCOL_VERSION = 5`; render and collect both fields; `cfg.flashSource || "generate"`.
  - In the `flashSource` select, list `generate` first, labelled as the default.
- [ ] **Step 4: Verify.** Run `python -m platformio test -e native -f test_web_protocol` and `python scripts/check_app_mirrors.py`. Expected: PASS, and `PROTOCOL_VERSION=5, 12 outputs`. Search `data/` for `spot`. Expected: no matches.
- [ ] **Step 5: Commit.**

```bash
git add src/domain/web_protocol.h data/index.html data/app.js test/test_web_protocol/test_web_protocol.cpp
git commit -m "feat(app): night hold and aux darkening settings, protocol v5"
```

### Task 4: Track 64 CAN IDs

Today a 17th distinct ID is dropped, so a mapped ID may never be seen on a busy bus.

**Files:**
- Modify: `src/domain/can_state.h`, `src/domain/can_state.cpp`, `src/main.cpp`
- Test: `test/test_can_snapshot/test_can_snapshot.cpp`

**Interfaces:**
- Produces: `CanState::MAX_FRAMES` public, value 64.

- [ ] **Step 1: Write the failing test** `test_tracks_64_ids_and_ignores_the_65th`: update IDs 1 to 65 with `data[0] = 1`. Assert `getBit(64, 0)` is true, `getBit(65, 0)` is false and `snapshot(out, CanState::MAX_FRAMES)` returns 64.
- [ ] **Step 2: Run it.** Run `python -m platformio test -e native -f test_can_snapshot`. Expected: compile failure on the private constant.
- [ ] **Step 3: Implement.** Make `MAX_FRAMES` public and 64. Update the "16 distinct ids" comment. In `main.cpp`, size `fr` with `CanState::MAX_FRAMES`, pass that to `snapshot`, and change the Discovery interval from 100 ms to 250 ms, because the message is up to four times larger.
- [ ] **Step 4: Run all native tests, then the ESP32 build.** Run `python -m platformio test -e native` and `py -3.13 -m platformio run -e esp32`. Expected: both succeed.
- [ ] **Step 5: Commit.**

```bash
git add src/domain/can_state.h src/domain/can_state.cpp src/main.cpp test/test_can_snapshot/test_can_snapshot.cpp
git commit -m "feat: track 64 CAN IDs so a busy bus cannot hide a mapped signal"
```

### Task 5: On-device check

The user flashes the board, because the session cannot reach COM ports. Tick these on the desk rig before the bike.

- [ ] **Step 1: Flash.** Upload the firmware, and also `uploadfs` if this build still has the separate LittleFS image.
- [ ] **Step 2: Saved config.** Confirm the hold time carried over. Set `Indicator flash source` to `generate`, because a saved board keeps `auto`.
- [ ] **Step 3: Test tab.** Run `lowBeam`: rear running lights only, with front white and pods off. Run `highBeam`: pods energised.
- [ ] **Step 4: Discovery tab.** Confirm it stays usable on a phone with many IDs showing. If it lags, record that for a separate fix.
- [ ] **Step 5: On the bike, once fitted.** Find the day/night bit. Confirm flash reads bit 16 without bit 6. Confirm a held high beam never toggles night mode. Check the sweep fits inside `blinkPeriodMs`.
