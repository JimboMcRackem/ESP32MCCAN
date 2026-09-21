# Test Mode and Brightness Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the web app drive any lighting zone on demand for bench and on-bike testing, and tune brightness as a gamma-corrected level that is separate from hue, without changing how the bike's lights look today.

**Architecture:** Config colours gain a `{hue, level}` split where gamma applies to the level only, which makes the upgrade duty-preserving for every existing value. A new `src/domain/test_mode.h/.cpp` unit sits between `computeOutputs` and `applyIntent`: when test mode is off it calls the real engine unchanged, when a scenario is selected it calls the real engine against a *separate* `EngineState`, and when zones are set it passes the override through verbatim. Test mode is released by explicit exit, owner WebSocket disconnect, or an absolute time cap.

**Tech Stack:** C++17 (`-std=gnu++17`), Arduino framework on ESP32, PlatformIO, ArduinoJson v7, Unity test framework (native env), vanilla JS/HTML/CSS served from LittleFS.

**Spec:** `docs/superpowers/specs/2026-09-21-test-mode-and-brightness-design.md`

## Global Constraints

- **Test mode holds unconditionally.** A real brake or indicator does **not** reclaim its zone. This is a deliberate user decision, compensated by a persistent warning banner. Do not add preemption.
- **The warning banner lives in `<header>`, outside the tab system.** It must not be possible to navigate away from it while lights are overridden.
- `test_state` is **broadcast**, never sent only to the controlling client.
- **Migration is duty-preserving.** Every existing colour must resolve to the duty it produces today. Verified numerically: all six shipped defaults migrate with **zero** delta.
- **Gamma applies to the level only, never per channel.** Per-channel gamma would shift the hue of every non-neutral colour.
- `denaliDay/Low/High/Spot` stay **raw 0-255 duty**. No gamma, no `ColorLevel`.
- **The colour entry set stays at six:** `drlWhiteDay`, `drlWhiteNight`, `drlDimRedDay`, `drlDimRedNight`, `indicatorOrange`, `brakeRed`.
- `kProtocolVersion = 2`. The shipped protocol is version 1 and does not send the field, so a missing value reads as 1.
- **Unknown messages must degrade, not break.** Firmware answers an unrecognised `type` with an `error` response; the web app must silently ignore message types it does not know.
- `cfg.testMaxMs` default `600000` (10 minutes). Expiry is `nowMs - t.startedMs >= cap` — unsigned, rollover-safe.
- Scenarios run against a **separate `EngineState`**, reset on entry, so test mode structurally cannot corrupt the spot latch.
- No OTA. No changes to CAN decoding, the mapping UI, or discovery.
- Native tests: `python -m platformio` (the 3.14 install). ESP32 build: `py -3.13 -m platformio`.
- Unity's `setUp`/`tearDown` must be defined in **every** new suite file, or the link fails.

### Correction to the spec's stated tolerance

The spec says migration round-trip tests assert ±1. That was verified before writing this plan and is only partly right. Use these bounds:

| Case | Bound | Why |
|---|---|---|
| The six shipped defaults | **exact equality** | Each divides evenly; measured delta is 0 |
| A `(r,0,0)` ramp over all 256 values | **±1** | Single gamma round-trip rounding |
| Arbitrary non-neutral triples | **±2** | Hue normalisation rounds too; worst measured case is `(162,121,0)` → `(161,119,0)` |

Amend the spec to match as part of Task 1.

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/gen_gamma.py` | **New.** Generates the gamma tables. Run by hand; output is committed. |
| `src/domain/gamma_table.h` | **New, generated.** `kGammaEncode[256]`, `kGammaDecode[256]`. Never hand-edited. |
| `src/domain/color.h` | `Rgb` (unchanged) plus `ColorLevel`, `resolveColor`, `colorFromRgb`. |
| `src/domain/config.h`, `config.cpp` | Six colour entries become `ColorLevel`; add `testMaxMs`. |
| `src/domain/config_json.cpp` | Serialize `{hue, level}`; migrate bare `[r,g,b]` triples. |
| `src/domain/behavior_engine.cpp` | Resolve `ColorLevel` to `Rgb` at the top of `computeOutputs`. Logic otherwise untouched. |
| `src/domain/test_mode.h`, `test_mode.cpp` | **New.** `TestKind`, `TestMode`, scenario table, `resolveOutputs`, `testExpired`. |
| `src/domain/web_protocol.h`, `.cpp` | `test` inbound, `test_state` outbound, `protocolVersion` on `config`. |
| `src/hal/web_server.h`, `.cpp` | `onDisconnect` callback. |
| `src/main.cpp` | Owns `g_test` and `g_testEngine`; wires override, expiry, disconnect, 1 s broadcast. |
| `data/index.html`, `app.js`, `style.css` | Banners, test tab, level sliders, appearance preview. |
| `test/test_color_level/` | **New suite.** |
| `test/test_test_mode/` | **New suite.** |
| `test/test_web_protocol/`, `test_config_json/`, `test_config_defaults/`, `test_behavior_engine/` | Updated. |

**Dependency order:** Task 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. Task 2 is the only one that must change several files at once: the `Config` type change breaks `behavior_engine.cpp` and `config_json.cpp` compilation, so they travel together to keep the build green at every commit.

---

### Task 1: Gamma tables and the `ColorLevel` type

**Files:**
- Create: `scripts/gen_gamma.py`
- Create: `src/domain/gamma_table.h` (generated by the script)
- Modify: `src/domain/color.h`
- Modify: `docs/superpowers/specs/2026-09-21-test-mode-and-brightness-design.md:150` and `:342`
- Test: `test/test_color_level/test_color_level.cpp`

**Interfaces:**
- Consumes: nothing — this is the foundation task.
- Produces:
  - `struct ColorLevel { Rgb hue; uint8_t level; }` with `operator==` / `operator!=`
  - `Rgb resolveColor(const ColorLevel& c)`
  - `ColorLevel colorFromRgb(const Rgb& c)`
  - `constexpr uint8_t kGammaEncode[256]`, `kGammaDecode[256]`

Nothing else in the tree changes in this task, so the build and all existing suites stay green throughout.

- [ ] **Step 1: Write the generator**

The spec says the table is built at compile time. A `constexpr` C++ implementation of `x^2.2` needs either floating point (`std::pow` is not `constexpr`) or an integer approximation nobody will want to review. Generating a committed header instead matches the house convention already used for the hardware sheets — artefacts are generated from a script and never hand-edited — and it keeps floating point off the device entirely.

Create `scripts/gen_gamma.py`:

```python
#!/usr/bin/env python3
"""Generate src/domain/gamma_table.h - the 8-bit gamma tables.

Run from the repository root; the output is committed:
    python scripts/gen_gamma.py

The device never computes these. No floating point, no <cmath>, no startup cost.
"""
import os

GAMMA = 2.2

def table(name, comment, values):
    lines = ["// " + comment, "constexpr uint8_t %s[256] = {" % name]
    for i in range(0, 256, 16):
        lines.append("  " + " ".join("%3d," % v for v in values[i:i + 16]))
    lines.append("};")
    return "\n".join(lines)

enc = [round(255 * (v / 255) ** GAMMA) for v in range(256)]
dec = [round(255 * (d / 255) ** (1 / GAMMA)) for d in range(256)]

body = """#pragma once
// GENERATED by scripts/gen_gamma.py - do not edit by hand.
// Gamma %s.
#include <cstdint>

%s

%s
""" % (GAMMA,
       table("kGammaEncode", "perceptual level -> PWM duty", enc),
       table("kGammaDecode", "PWM duty -> perceptual level (migration only)", dec))

out = os.path.join("src", "domain", "gamma_table.h")
with open(out, "w", newline="\n") as f:
    f.write(body)
print("wrote %s" % out)
```

- [ ] **Step 2: Run the generator**

Run: `python scripts/gen_gamma.py`
Expected: `wrote src\domain\gamma_table.h`

Sanity-check the output — `kGammaEncode` must start `0, 0, 0, ...` and end `..., 255,`; `kGammaDecode` must start `0, 21, 28, ...`:

Run: `head -8 src/domain/gamma_table.h && sed -n '26,28p' src/domain/gamma_table.h`

- [ ] **Step 3: Write the failing test**

Create `test/test_color_level/test_color_level.cpp`:

```cpp
#include <unity.h>
#include "domain/color.h"

void setUp(void) {}
void tearDown(void) {}

void test_gamma_endpoints_are_exact(void) {
  TEST_ASSERT_EQUAL_UINT8(0, kGammaEncode[0]);
  TEST_ASSERT_EQUAL_UINT8(255, kGammaEncode[255]);
  TEST_ASSERT_EQUAL_UINT8(0, kGammaDecode[0]);
  TEST_ASSERT_EQUAL_UINT8(255, kGammaDecode[255]);
}

void test_gamma_encode_is_monotonic(void) {
  for (int i = 0; i < 255; ++i) {
    TEST_ASSERT_TRUE_MESSAGE(kGammaEncode[i] <= kGammaEncode[i + 1],
                             "kGammaEncode must be non-decreasing");
  }
}

void test_resolve_at_full_level_is_the_hue(void) {
  ColorLevel c{ Rgb{255, 80, 0}, 255 };
  TEST_ASSERT_TRUE((resolveColor(c) == Rgb{255, 80, 0}));
}

void test_resolve_at_zero_level_is_off(void) {
  ColorLevel c{ Rgb{255, 80, 0}, 0 };
  TEST_ASSERT_TRUE((resolveColor(c) == Rgb{0, 0, 0}));
}

void test_resolve_scales_channels_by_one_gamma_corrected_level(void) {
  // gamma8(128) == 56, so {255,128,0} at level 128 -> {56, 128*56/255, 0}.
  TEST_ASSERT_EQUAL_UINT8(56, kGammaEncode[128]);
  ColorLevel c{ Rgb{255, 128, 0}, 128 };
  TEST_ASSERT_TRUE((resolveColor(c) == Rgb{56, 28, 0}));
}

void test_hue_ratio_is_preserved_across_levels(void) {
  // The point of levelwise gamma: dimming must not drift the hue. The ratio
  // green/red stays at 128/255 (within one count) at every level.
  const Rgb hue{255, 128, 0};
  for (int lvl = 8; lvl <= 255; ++lvl) {
    Rgb out = resolveColor(ColorLevel{hue, (uint8_t)lvl});
    int expectG = (128 * kGammaEncode[lvl]) / 255;
    TEST_ASSERT_EQUAL_UINT8(expectG, out.g);
    TEST_ASSERT_EQUAL_UINT8(0, out.b);
  }
}

void test_from_rgb_normalizes_hue_and_extracts_level(void) {
  ColorLevel c = colorFromRgb(Rgb{120, 0, 0});
  TEST_ASSERT_TRUE((c.hue == Rgb{255, 0, 0}));
  TEST_ASSERT_EQUAL_UINT8(kGammaDecode[120], c.level);
}

void test_from_rgb_black_keeps_a_usable_hue(void) {
  // Black has no hue to recover; default to white at level 0 so a user who
  // raises the level from a black entry gets white, not another black.
  ColorLevel c = colorFromRgb(Rgb{0, 0, 0});
  TEST_ASSERT_TRUE((c.hue == Rgb{255, 255, 255}));
  TEST_ASSERT_EQUAL_UINT8(0, c.level);
}

void test_migration_is_exact_for_every_shipped_default(void) {
  // The six values Config ships today. Migration must not change the bike.
  const Rgb shipped[6] = {
    {255, 255, 255},  // drlWhiteDay
    {120, 120, 120},  // drlWhiteNight
    {120, 0, 0},      // drlDimRedDay
    {60, 0, 0},       // drlDimRedNight
    {255, 80, 0},     // indicatorOrange
    {255, 0, 0},      // brakeRed
  };
  for (int i = 0; i < 6; ++i) {
    Rgb back = resolveColor(colorFromRgb(shipped[i]));
    TEST_ASSERT_TRUE_MESSAGE((back == shipped[i]),
                             "a shipped default did not migrate exactly");
  }
}

void test_migration_round_trip_on_a_red_ramp_is_within_one(void) {
  for (int r = 0; r <= 255; ++r) {
    Rgb src{(uint8_t)r, 0, 0};
    Rgb back = resolveColor(colorFromRgb(src));
    int err = (int)back.r - r;
    if (err < 0) err = -err;
    TEST_ASSERT_TRUE_MESSAGE(err <= 1, "red ramp round trip drifted by >1");
  }
}

void test_migration_round_trip_on_arbitrary_triples_is_within_two(void) {
  // Hue normalisation rounds as well as gamma, so a non-neutral triple can
  // land 2 counts out. Worst measured case: (162,121,0) -> (161,119,0).
  for (int r = 0; r <= 255; ++r) {
    const int gs[3] = {0, r / 2, r};
    for (int gi = 0; gi < 3; ++gi) {
      Rgb src{(uint8_t)r, (uint8_t)gs[gi], (uint8_t)(r / 3)};
      Rgb back = resolveColor(colorFromRgb(src));
      const int d[3] = {(int)back.r - src.r, (int)back.g - src.g, (int)back.b - src.b};
      for (int k = 0; k < 3; ++k) {
        int e = d[k] < 0 ? -d[k] : d[k];
        TEST_ASSERT_TRUE_MESSAGE(e <= 2, "arbitrary triple drifted by >2");
      }
    }
  }
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_gamma_endpoints_are_exact);
  RUN_TEST(test_gamma_encode_is_monotonic);
  RUN_TEST(test_resolve_at_full_level_is_the_hue);
  RUN_TEST(test_resolve_at_zero_level_is_off);
  RUN_TEST(test_resolve_scales_channels_by_one_gamma_corrected_level);
  RUN_TEST(test_hue_ratio_is_preserved_across_levels);
  RUN_TEST(test_from_rgb_normalizes_hue_and_extracts_level);
  RUN_TEST(test_from_rgb_black_keeps_a_usable_hue);
  RUN_TEST(test_migration_is_exact_for_every_shipped_default);
  RUN_TEST(test_migration_round_trip_on_a_red_ramp_is_within_one);
  RUN_TEST(test_migration_round_trip_on_arbitrary_triples_is_within_two);
  return UNITY_END();
}
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `python -m platformio test -e native -f test_color_level`
Expected: compile error — `'ColorLevel' was not declared in this scope`.

- [ ] **Step 5: Extend `color.h`**

Append to `src/domain/color.h`, after the existing `Rgb` operators:

```cpp
#include "domain/gamma_table.h"

// A colour split into a normalized hue (brightest channel is 255) and a
// separate perceptual level. Gamma applies to the LEVEL ONLY — applying it
// per channel would shift the hue of every non-neutral colour, which is
// exactly what this split exists to prevent.
struct ColorLevel {
  Rgb     hue   = {255, 255, 255};
  uint8_t level = 255;            // 0-255; shown in the UI as 0-100%
};

inline bool operator==(const ColorLevel& a, const ColorLevel& b) {
  return a.hue == b.hue && a.level == b.level;
}
inline bool operator!=(const ColorLevel& a, const ColorLevel& b) { return !(a == b); }

// hue * gamma8(level) / 255, per channel. The result is PWM duty.
inline Rgb resolveColor(const ColorLevel& c) {
  const int g = kGammaEncode[c.level];
  return Rgb{ (uint8_t)((c.hue.r * g) / 255),
              (uint8_t)((c.hue.g * g) / 255),
              (uint8_t)((c.hue.b * g) / 255) };
}

// Inverse, used to migrate configs written before the split. Duty-preserving:
//   resolveColor(colorFromRgb(x)) == x   for every colour this project ships.
inline ColorLevel colorFromRgb(const Rgb& c) {
  const uint8_t m = c.r > c.g ? (c.r > c.b ? c.r : c.b)
                              : (c.g > c.b ? c.g : c.b);
  if (m == 0) return ColorLevel{ Rgb{255, 255, 255}, 0 };
  return ColorLevel{ Rgb{ (uint8_t)((c.r * 255 + m / 2) / m),
                          (uint8_t)((c.g * 255 + m / 2) / m),
                          (uint8_t)((c.b * 255 + m / 2) / m) },
                     kGammaDecode[m] };
}
```

Move the `#include "domain/gamma_table.h"` up next to `#include <cstdint>` at the top of the file rather than leaving it mid-file.

- [ ] **Step 6: Run the test to verify it passes**

Run: `python -m platformio test -e native -f test_color_level`
Expected: PASS, 11 tests.

- [ ] **Step 7: Run the whole native suite — nothing else may have moved**

Run: `python -m platformio test -e native`
Expected: all suites PASS.

- [ ] **Step 8: Correct the spec's tolerance claim**

In `docs/superpowers/specs/2026-09-21-test-mode-and-brightness-design.md`, replace the final sentence of the "Known imprecision" paragraph (line 150):

```
Tests assert a tolerance of ±1, not equality.
```

with:

```
Tests assert equality for the six shipped defaults (measured delta is zero),
±1 for a single-channel ramp, and ±2 for arbitrary non-neutral triples, where
hue normalization rounds as well as the gamma round trip.
```

And in the `test_color_level` row of the Testing table (line 342), replace `within ±1 for all six defaults and a swept set of triples` with `exact for all six defaults, ±1 on a ramp, ±2 on a swept set of triples`.

- [ ] **Step 9: Commit**

```bash
git add scripts/gen_gamma.py src/domain/gamma_table.h src/domain/color.h \
        test/test_color_level/test_color_level.cpp \
        docs/superpowers/specs/2026-09-21-test-mode-and-brightness-design.md
git commit -m "feat(color): split colour into hue and gamma-corrected level

Gamma applies to the level only, so dimming cannot drift the hue. The
tables are generated by scripts/gen_gamma.py and committed, keeping
floating point off the device. colorFromRgb/resolveColor round-trip
every shipped default exactly, which makes the config migration in the
next commit invisible on the bike.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: `Config` adopts `ColorLevel`

**Files:**
- Modify: `src/domain/config.h:29-40`
- Modify: `src/domain/behavior_engine.cpp:14-17,29-30`
- Modify: `src/domain/config_json.cpp:9-13,34-40,85-93`
- Test: `test/test_config_json/test_config_json.cpp:23-29`
- Test: `test/test_config_defaults/test_config_defaults.cpp:8`
- Test: `test/test_behavior_engine/test_behavior_engine.cpp` (24 assertion lines)

**Interfaces:**
- Consumes: `ColorLevel`, `resolveColor`, `colorFromRgb` from Task 1.
- Produces:
  - `Config` colour fields are now `ColorLevel`, defaults chosen so `resolveColor` yields today's exact duties
  - `uint32_t Config::testMaxMs = 600000`
  - JSON colour shape `{"hue":[r,g,b],"level":n}`, with bare `[r,g,b]` still accepted and migrated

The type change breaks compilation in `behavior_engine.cpp` and `config_json.cpp`, so all three move in one commit. The build is green before and after, never in between.

- [ ] **Step 1: Write the failing tests**

Replace `test_roundtrip_preserves_colors` in `test/test_config_json/test_config_json.cpp` (lines 23-29) with:

```cpp
void test_roundtrip_preserves_colors() {
  Config in = defaultConfig();
  in.indicatorOrange = ColorLevel{ Rgb{255, 90, 5}, 200 };
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_TRUE((out.indicatorOrange == ColorLevel{Rgb{255, 90, 5}, 200}));
}

void test_roundtrip_preserves_test_cap() {
  Config in = defaultConfig();
  in.testMaxMs = 120000;
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_EQUAL_UINT32(120000, out.testMaxMs);
}

void test_old_rgb_triples_migrate_duty_preserving() {
  // A config written by the shipped firmware: colours are bare [r,g,b].
  const char* legacy =
    "{\"colors\":{\"drlWhiteDay\":[255,255,255],"
    "\"drlWhiteNight\":[120,120,120],"
    "\"drlDimRedDay\":[120,0,0],"
    "\"drlDimRedNight\":[60,0,0],"
    "\"indicatorOrange\":[255,80,0],"
    "\"brakeRed\":[255,0,0]}}";
  bool ok = false;
  Config c = configFromJson(legacy, ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_TRUE((resolveColor(c.drlWhiteDay)    == Rgb{255, 255, 255}));
  TEST_ASSERT_TRUE((resolveColor(c.drlWhiteNight)  == Rgb{120, 120, 120}));
  TEST_ASSERT_TRUE((resolveColor(c.drlDimRedDay)   == Rgb{120, 0, 0}));
  TEST_ASSERT_TRUE((resolveColor(c.drlDimRedNight) == Rgb{60, 0, 0}));
  TEST_ASSERT_TRUE((resolveColor(c.indicatorOrange) == Rgb{255, 80, 0}));
  TEST_ASSERT_TRUE((resolveColor(c.brakeRed)       == Rgb{255, 0, 0}));
  // ...and the hue really was normalized, not left as the raw triple.
  TEST_ASSERT_TRUE((c.drlDimRedNight.hue == Rgb{255, 0, 0}));
}

void test_unknown_color_shape_falls_back_to_default() {
  bool ok = false;
  Config c = configFromJson("{\"colors\":{\"brakeRed\":\"scarlet\"}}", ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_TRUE((c.brakeRed == defaultConfig().brakeRed));
}
```

Add `#include "domain/color.h"` to that file's includes, and register the three new tests in `main`:

```cpp
  RUN_TEST(test_roundtrip_preserves_test_cap);
  RUN_TEST(test_old_rgb_triples_migrate_duty_preserving);
  RUN_TEST(test_unknown_color_shape_falls_back_to_default);
```

In `test/test_config_defaults/test_config_defaults.cpp`, replace line 8:

```cpp
  TEST_ASSERT_TRUE((c.indicatorOrange == Rgb{255, 80, 0}));
```

with an assertion on the resolved duty plus the new tunable — the default must still *look* like today's orange:

```cpp
  TEST_ASSERT_TRUE((resolveColor(c.indicatorOrange) == Rgb{255, 80, 0}));
  TEST_ASSERT_EQUAL_UINT32(600000, c.testMaxMs);
```

- [ ] **Step 2: Update the behaviour-engine assertions**

Every colour assertion in `test/test_behavior_engine/test_behavior_engine.cpp` compares an `OutputIntent`'s `Rgb` against a config entry that is now a `ColorLevel`. They all need wrapping in `resolveColor`. This is mechanical:

```bash
sed -i -E 's/== (cfg\.(drlWhiteDay|drlWhiteNight|drlDimRedDay|drlDimRedNight|indicatorOrange|brakeRed))\)/== resolveColor(\1))/g' \
  test/test_behavior_engine/test_behavior_engine.cpp
grep -c "resolveColor" test/test_behavior_engine/test_behavior_engine.cpp
```

Expected: `24`. If the count differs, inspect the file rather than re-running the sed.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m platformio test -e native -f test_config_json`
Expected: compile error — no `testMaxMs` member in `Config`, and `configFromJson` returns `Rgb` where `ColorLevel` is expected.

- [ ] **Step 4: Change the `Config` type**

In `src/domain/config.h`, replace lines 29-39 with:

```cpp
  // Levels are gamma-decoded from the duties this project shipped before the
  // hue/level split, so these defaults resolve to exactly the old values:
  // level 181 -> duty 120, level 132 -> duty 60.
  ColorLevel drlWhiteDay     = { {255, 255, 255}, 255 };
  ColorLevel drlWhiteNight   = { {255, 255, 255}, 181 };
  ColorLevel drlDimRedDay    = { {255, 0, 0},     181 };
  ColorLevel drlDimRedNight  = { {255, 0, 0},     132 };
  ColorLevel indicatorOrange = { {255, 80, 0},    255 };
  ColorLevel brakeRed        = { {255, 0, 0},     255 };

  // Denali stays raw duty: single-colour, already tuned against real beam
  // output, no hue to separate. Gamma here would silently re-level the beams.
  uint8_t denaliDay  = 50;
  uint8_t denaliLow  = 128;
  uint8_t denaliHigh = 255;
  uint8_t denaliSpot = 255;

  uint32_t testMaxMs = 600000;   // absolute cap on a test-mode session (10 min)
```

`config.cpp` needs no change — `defaultConfig()` builds a `Config c;` and relies on these in-class initializers.

- [ ] **Step 5: Resolve colours in the behaviour engine**

In `src/domain/behavior_engine.cpp`, replace lines 14-17 with:

```cpp
  const Rgb orange   = resolveColor(cfg.indicatorOrange);
  const Rgb white    = resolveColor(s.night ? cfg.drlWhiteNight : cfg.drlWhiteDay);
  const Rgb dimRed   = resolveColor(s.night ? cfg.drlDimRedNight : cfg.drlDimRedDay);
  const Rgb brakeRed = resolveColor(cfg.brakeRed);
  const Rgb flashCol = on ? orange : OFF;
```

and in lines 29-30 use the local instead of the config field:

```cpp
    o.rearL  = s.leftInd  ? flashCol : (brakeOn ? brakeRed : dimRed);
    o.rearR  = s.rightInd ? flashCol : (brakeOn ? brakeRed : dimRed);
```

No other logic changes. The resolution happens once per call, not per zone.

- [ ] **Step 6: Serialize and migrate in `config_json.cpp`**

Replace the `rgbTo` / `rgbFrom` helpers (lines 9-13) with:

```cpp
static void colorTo(JsonObject o, const ColorLevel& c) {
  JsonArray h = o["hue"].to<JsonArray>();
  h.add(c.hue.r); h.add(c.hue.g); h.add(c.hue.b);
  o["level"] = c.level;
}

// Accepts both shapes:
//   {"hue":[r,g,b],"level":n}   current
//   [r,g,b]                     written before the hue/level split
// The bare triple is migrated duty-preserving, so upgrading does not change
// how the bike looks. Serialization always writes the new shape, so the
// first save completes the upgrade.
static ColorLevel colorFrom(JsonVariantConst v, ColorLevel def) {
  if (v.is<JsonArrayConst>()) {
    JsonArrayConst a = v.as<JsonArrayConst>();
    if (a.size() != 3) return def;
    return colorFromRgb(Rgb{ (uint8_t)a[0].as<int>(),
                             (uint8_t)a[1].as<int>(),
                             (uint8_t)a[2].as<int>() });
  }
  if (v.is<JsonObjectConst>()) {
    JsonObjectConst o = v.as<JsonObjectConst>();
    JsonArrayConst a = o["hue"];
    if (a.size() != 3) return def;
    ColorLevel c;
    c.hue = Rgb{ (uint8_t)a[0].as<int>(),
                 (uint8_t)a[1].as<int>(),
                 (uint8_t)a[2].as<int>() };
    c.level = (uint8_t)(o["level"] | 255);
    return c;
  }
  return def;
}
```

Replace the colour block in `configToJson` (lines 34-40):

```cpp
  JsonObject col = doc["colors"].to<JsonObject>();
  colorTo(col["drlWhiteDay"].to<JsonObject>(),     c.drlWhiteDay);
  colorTo(col["drlWhiteNight"].to<JsonObject>(),   c.drlWhiteNight);
  colorTo(col["drlDimRedDay"].to<JsonObject>(),    c.drlDimRedDay);
  colorTo(col["drlDimRedNight"].to<JsonObject>(),  c.drlDimRedNight);
  colorTo(col["indicatorOrange"].to<JsonObject>(), c.indicatorOrange);
  colorTo(col["brakeRed"].to<JsonObject>(),        c.brakeRed);
```

Add the new tunable next to the existing two (after line 32):

```cpp
  doc["testMaxMs"] = c.testMaxMs;
```

Replace the colour block in `configFromJson` (lines 87-92):

```cpp
    c.drlWhiteDay     = colorFrom(col["drlWhiteDay"], c.drlWhiteDay);
    c.drlWhiteNight   = colorFrom(col["drlWhiteNight"], c.drlWhiteNight);
    c.drlDimRedDay    = colorFrom(col["drlDimRedDay"], c.drlDimRedDay);
    c.drlDimRedNight  = colorFrom(col["drlDimRedNight"], c.drlDimRedNight);
    c.indicatorOrange = colorFrom(col["indicatorOrange"], c.indicatorOrange);
    c.brakeRed        = colorFrom(col["brakeRed"], c.brakeRed);
```

And read the tunable next to the existing two (after line 83):

```cpp
  c.testMaxMs = doc["testMaxMs"] | c.testMaxMs;
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m platformio test -e native`
Expected: all suites PASS, including the four new `test_config_json` cases and the 24 rewritten behaviour-engine assertions.

- [ ] **Step 8: Confirm the device build still links**

Run: `py -3.13 -m platformio run -e esp32`
Expected: SUCCESS. (`main.cpp` and the HAL are excluded from the native env, so this is the only check that they still compile.)

- [ ] **Step 9: Commit**

```bash
git add src/domain/config.h src/domain/behavior_engine.cpp src/domain/config_json.cpp \
        test/test_config_json/ test/test_config_defaults/ test/test_behavior_engine/
git commit -m "feat(config): colours become hue plus level; add testMaxMs

The six colour entries are now ColorLevel. Defaults are gamma-decoded
from the duties shipped today, and configs written by the old firmware
are migrated on load, so the bike looks identical after the upgrade
and the UI shows honest current levels rather than defaults.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Test-mode core

**Files:**
- Create: `src/domain/test_mode.h`
- Create: `src/domain/test_mode.cpp`
- Test: `test/test_test_mode/test_test_mode.cpp`

**Interfaces:**
- Consumes: `Config::testMaxMs` (Task 2), `computeOutputs` / `EngineState` (existing).
- Produces:
  - `enum class TestKind : uint8_t { Off, Scenario, Zones }`
  - `struct TestMode { TestKind kind; LogicalState scenario; OutputIntent zones; uint8_t owner; uint32_t startedMs; }`
  - `bool scenarioByName(const char* name, LogicalState& out)`
  - `const char* const kScenarioNames[]`, `const int kScenarioCount`
  - `OutputIntent resolveOutputs(const LogicalState& real, const TestMode& t, const Config& cfg, uint32_t nowMs, EngineState& est, EngineState& testEst)`
  - `bool testExpired(const TestMode& t, const Config& cfg, uint32_t nowMs)`

- [ ] **Step 1: Write the failing test**

Create `test/test_test_mode/test_test_mode.cpp`:

```cpp
#include <unity.h>
#include "domain/test_mode.h"

static Config cfg;
static EngineState est;
static EngineState testEst;

void setUp(void) {
  cfg = defaultConfig();
  est = EngineState{};
  testEst = EngineState{};
}
void tearDown(void) {}

// Time at which the blink phase is ON (nowMs % (2*period) < period).
static const uint32_t kOn = 0;

void test_off_passes_the_real_state_through(void) {
  LogicalState real; real.run = true;
  TestMode t;                                  // kind defaults to Off
  OutputIntent got  = resolveOutputs(real, t, cfg, kOn, est, testEst);
  EngineState ref;
  OutputIntent want = computeOutputs(real, cfg, kOn, ref);
  TEST_ASSERT_TRUE((got.frontL == want.frontL));
  TEST_ASSERT_TRUE((got.rearL == want.rearL));
  TEST_ASSERT_EQUAL_UINT8(want.denali, got.denali);
}

void test_scenario_ignores_the_real_state(void) {
  LogicalState real;                            // bike is off
  TestMode t;
  t.kind = TestKind::Scenario;
  TEST_ASSERT_TRUE(scenarioByName("brake", t.scenario));

  OutputIntent o = resolveOutputs(real, t, cfg, kOn, est, testEst);
  TEST_ASSERT_TRUE((o.rearL == resolveColor(cfg.brakeRed)));
  TEST_ASSERT_TRUE((o.rearR == resolveColor(cfg.brakeRed)));
  TEST_ASSERT_TRUE((o.frontL == resolveColor(cfg.drlWhiteDay)));
}

void test_scenario_blinks_at_the_configured_rate(void) {
  LogicalState real;
  TestMode t;
  t.kind = TestKind::Scenario;
  TEST_ASSERT_TRUE(scenarioByName("hazards", t.scenario));

  // On-phase and off-phase of one blink cycle at the configured period.
  OutputIntent on  = resolveOutputs(real, t, cfg, 0, est, testEst);
  OutputIntent off = resolveOutputs(real, t, cfg, cfg.blinkPeriodMs, est, testEst);
  TEST_ASSERT_TRUE((on.frontL == resolveColor(cfg.indicatorOrange)));
  TEST_ASSERT_TRUE((on.rearR == resolveColor(cfg.indicatorOrange)));
  TEST_ASSERT_TRUE((off.frontL == Rgb{0, 0, 0}));
  TEST_ASSERT_TRUE((off.rearR == Rgb{0, 0, 0}));
}

void test_zones_pass_through_verbatim(void) {
  LogicalState real; real.run = true; real.rearBrake = true;
  TestMode t;
  t.kind = TestKind::Zones;
  t.zones.frontL = Rgb{1, 2, 3};
  t.zones.frontR = Rgb{4, 5, 6};
  t.zones.rearL  = Rgb{7, 8, 9};
  t.zones.rearR  = Rgb{10, 11, 12};
  t.zones.denali = 77;

  OutputIntent o = resolveOutputs(real, t, cfg, kOn, est, testEst);
  TEST_ASSERT_TRUE((o.frontL == Rgb{1, 2, 3}));
  TEST_ASSERT_TRUE((o.frontR == Rgb{4, 5, 6}));
  TEST_ASSERT_TRUE((o.rearL == Rgb{7, 8, 9}));
  TEST_ASSERT_TRUE((o.rearR == Rgb{10, 11, 12}));
  TEST_ASSERT_EQUAL_UINT8(77, o.denali);
}

void test_scenario_cannot_corrupt_the_real_engine_state(void) {
  // A held 'flash' latches the spot lights. Run it as a scenario for well
  // past spotHoldMs and the REAL EngineState must be untouched, or exiting
  // test mode would leave the bike's spots latched on.
  LogicalState real;
  TestMode t;
  t.kind = TestKind::Scenario;
  t.scenario.run = true;
  t.scenario.flash = true;

  for (uint32_t ms = 0; ms <= cfg.spotHoldMs + 100; ms += 10) {
    resolveOutputs(real, t, cfg, ms, est, testEst);
  }
  TEST_ASSERT_TRUE_MESSAGE(testEst.spotLatched, "the test engine should latch");
  TEST_ASSERT_FALSE_MESSAGE(est.spotLatched, "the real engine must NOT latch");
  TEST_ASSERT_FALSE(est.flashPrev);
}

void test_expiry_is_false_when_off(void) {
  TestMode t;                                   // Off
  TEST_ASSERT_FALSE(testExpired(t, cfg, 0xFFFFFFFFu));
}

void test_expiry_at_the_cap(void) {
  TestMode t;
  t.kind = TestKind::Zones;
  t.startedMs = 1000;
  TEST_ASSERT_FALSE(testExpired(t, cfg, 1000 + cfg.testMaxMs - 1));
  TEST_ASSERT_TRUE(testExpired(t, cfg, 1000 + cfg.testMaxMs));
}

void test_expiry_survives_millis_rollover(void) {
  TestMode t;
  t.kind = TestKind::Zones;
  t.startedMs = 0xFFFFF000u;                    // ~4 s before rollover
  TEST_ASSERT_FALSE(testExpired(t, cfg, 0x00000100u));   // 4352 ms elapsed
  TEST_ASSERT_TRUE(testExpired(t, cfg, 0xFFFFF000u + cfg.testMaxMs));
}

void test_scenario_lookup_rejects_unknown_names(void) {
  LogicalState s;
  TEST_ASSERT_FALSE(scenarioByName("nope", s));
  TEST_ASSERT_FALSE(scenarioByName("", s));
}

void test_every_advertised_scenario_name_resolves(void) {
  // kScenarioNames is what the UI mirrors; a name in the list that does not
  // resolve would be a dead button.
  TEST_ASSERT_EQUAL_INT(10, kScenarioCount);
  LogicalState s;
  for (int i = 0; i < kScenarioCount; ++i) {
    TEST_ASSERT_TRUE_MESSAGE(scenarioByName(kScenarioNames[i], s),
                             "an advertised scenario name did not resolve");
  }
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_off_passes_the_real_state_through);
  RUN_TEST(test_scenario_ignores_the_real_state);
  RUN_TEST(test_scenario_blinks_at_the_configured_rate);
  RUN_TEST(test_zones_pass_through_verbatim);
  RUN_TEST(test_scenario_cannot_corrupt_the_real_engine_state);
  RUN_TEST(test_expiry_is_false_when_off);
  RUN_TEST(test_expiry_at_the_cap);
  RUN_TEST(test_expiry_survives_millis_rollover);
  RUN_TEST(test_scenario_lookup_rejects_unknown_names);
  RUN_TEST(test_every_advertised_scenario_name_resolves);
  return UNITY_END();
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m platformio test -e native -f test_test_mode`
Expected: compile error — `domain/test_mode.h: No such file or directory`.

- [ ] **Step 3: Write the header**

Create `src/domain/test_mode.h`:

```cpp
#pragma once
#include "domain/logical_state.h"
#include "domain/output_intent.h"
#include "domain/behavior_engine.h"
#include "domain/config.h"
#include <cstdint>

enum class TestKind : uint8_t { Off, Scenario, Zones };

// A held override of the lighting outputs. Single-holder, last-writer-wins:
// a second client taking it is not an error, and only the current owner's
// disconnect releases it.
struct TestMode {
  TestKind     kind      = TestKind::Off;
  LogicalState scenario;        // used when kind == Scenario
  OutputIntent zones;           // used when kind == Zones
  uint8_t      owner     = 0;   // WebSocket client id holding the mode
  uint32_t     startedMs = 0;
};

// Firmware-side scenario presets. This table is authoritative; the web app
// mirrors the names only for its buttons.
extern const char* const kScenarioNames[];
extern const int         kScenarioCount;

// Looks up a preset by name. Returns false for an unknown name and leaves
// `out` untouched — an unknown scenario must be an error, not a silent no-op.
bool scenarioByName(const char* name, LogicalState& out);

// The single seam between the behaviour engine and the PWM outputs.
//   Off      -> computeOutputs(real, ..., est)        exactly today's path
//   Scenario -> computeOutputs(t.scenario, ..., testEst)
//   Zones    -> t.zones verbatim
// Scenarios drive `testEst`, never `est`, so test mode is structurally unable
// to leave the real spot latch set after it exits.
OutputIntent resolveOutputs(const LogicalState& real, const TestMode& t,
                            const Config& cfg, uint32_t nowMs,
                            EngineState& est, EngineState& testEst);

// Absolute cap. Unsigned subtraction, so this is correct across millis()
// rollover. Always false when the mode is Off.
bool testExpired(const TestMode& t, const Config& cfg, uint32_t nowMs);
```

- [ ] **Step 4: Write the implementation**

Create `src/domain/test_mode.cpp`:

```cpp
#include "domain/test_mode.h"
#include <cstring>

namespace {

// Built through a constexpr helper rather than seven positional bools per
// row, which would be unreadable and easy to mis-review.
constexpr LogicalState mk(bool run, bool night, bool left, bool right,
                          bool brake, bool low, bool high) {
  LogicalState s{};
  s.run       = run;
  s.night     = night;
  s.leftInd   = left;
  s.rightInd  = right;
  s.rearBrake = brake;
  s.lowBeam   = low;
  s.highBeam  = high;
  return s;
}

//                        run    night  left   right  brake  low    high
constexpr LogicalState kScenarios[] = {
  /* allOff     */ mk(false, false, false, false, false, false, false),
  /* drlDay     */ mk(true,  false, false, false, false, false, false),
  /* drlNight   */ mk(true,  true,  false, false, false, false, false),
  /* leftInd    */ mk(true,  false, true,  false, false, false, false),
  /* rightInd   */ mk(true,  false, false, true,  false, false, false),
  /* hazards    */ mk(true,  false, true,  true,  false, false, false),
  /* brake      */ mk(true,  false, false, false, true,  false, false),
  /* brakeNight */ mk(true,  true,  false, false, true,  false, false),
  /* lowBeam    */ mk(true,  true,  false, false, false, true,  false),
  /* highBeam   */ mk(true,  true,  false, false, false, false, true ),
};

}  // namespace

// Index-aligned with kScenarios above. test_every_advertised_scenario_name
// _resolves is what keeps the two in step if either is edited.
const char* const kScenarioNames[] = {
  "allOff", "drlDay", "drlNight", "leftInd", "rightInd",
  "hazards", "brake", "brakeNight", "lowBeam", "highBeam",
};
const int kScenarioCount =
    (int)(sizeof(kScenarioNames) / sizeof(kScenarioNames[0]));

static_assert(sizeof(kScenarios) / sizeof(kScenarios[0]) ==
                  sizeof(kScenarioNames) / sizeof(kScenarioNames[0]),
              "kScenarios and kScenarioNames must stay index-aligned");

bool scenarioByName(const char* name, LogicalState& out) {
  if (!name || !*name) return false;
  for (int i = 0; i < kScenarioCount; ++i) {
    if (std::strcmp(name, kScenarioNames[i]) == 0) {
      out = kScenarios[i];
      return true;
    }
  }
  return false;
}

OutputIntent resolveOutputs(const LogicalState& real, const TestMode& t,
                            const Config& cfg, uint32_t nowMs,
                            EngineState& est, EngineState& testEst) {
  switch (t.kind) {
    case TestKind::Scenario:
      return computeOutputs(t.scenario, cfg, nowMs, testEst);
    case TestKind::Zones:
      return t.zones;
    case TestKind::Off:
    default:
      return computeOutputs(real, cfg, nowMs, est);
  }
}

bool testExpired(const TestMode& t, const Config& cfg, uint32_t nowMs) {
  if (t.kind == TestKind::Off) return false;
  return (nowMs - t.startedMs) >= cfg.testMaxMs;
}
```

`static_assert` plus the name-resolution test are the two guards keeping the
parallel arrays honest; the first catches a length mismatch at compile time,
the second catches a reordering.

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m platformio test -e native -f test_test_mode`
Expected: PASS, 10 tests.

- [ ] **Step 6: Run the whole native suite**

Run: `python -m platformio test -e native`
Expected: all suites PASS.

- [ ] **Step 7: Commit**

```bash
git add src/domain/test_mode.h src/domain/test_mode.cpp test/test_test_mode/
git commit -m "feat(test-mode): the override seam between engine and outputs

Scenarios route back through the real computeOutputs so what the tester
sees is what the engine does, but against a separate EngineState, so a
held-flash scenario cannot leave the bike's spot latch set after exit.
Expiry uses unsigned subtraction and is correct across millis rollover.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Protocol — `test` inbound, `test_state` outbound, version field

**Files:**
- Modify: `src/domain/web_protocol.h`
- Modify: `src/domain/web_protocol.cpp:44` (before the `unknown type` fallthrough) and `:50-57`
- Test: `test/test_web_protocol/test_web_protocol.cpp`

**Interfaces:**
- Consumes: `TestMode`, `TestKind`, `scenarioByName` (Task 3); `Config::testMaxMs` (Task 2).
- Produces:
  - `constexpr int kProtocolVersion = 2`
  - `ProtocolAction::setTest` (bool), `ProtocolAction::testOut` (`TestMode`)
  - `std::string testStateMessage(const TestMode& t, const Config& cfg, uint32_t nowMs)`
  - `configMessage` now emits `protocolVersion`

- [ ] **Step 1: Write the failing test**

Add to `test/test_web_protocol/test_web_protocol.cpp`, before `main`:

```cpp
void test_test_off_is_accepted(void) {
  ProtocolAction a = handleRequest("{\"type\":\"test\",\"mode\":\"off\"}");
  TEST_ASSERT_TRUE(a.setTest);
  TEST_ASSERT_TRUE(a.error.empty());
  TEST_ASSERT_TRUE(a.testOut.kind == TestKind::Off);
}

void test_test_scenario_resolves_the_preset(void) {
  ProtocolAction a = handleRequest(
      "{\"type\":\"test\",\"mode\":\"scenario\",\"scenario\":\"hazards\"}");
  TEST_ASSERT_TRUE(a.setTest);
  TEST_ASSERT_TRUE(a.error.empty());
  TEST_ASSERT_TRUE(a.testOut.kind == TestKind::Scenario);
  TEST_ASSERT_TRUE(a.testOut.scenario.leftInd);
  TEST_ASSERT_TRUE(a.testOut.scenario.rightInd);
}

void test_unknown_scenario_is_an_error(void) {
  ProtocolAction a = handleRequest(
      "{\"type\":\"test\",\"mode\":\"scenario\",\"scenario\":\"disco\"}");
  TEST_ASSERT_FALSE(a.setTest);
  TEST_ASSERT_FALSE(a.error.empty());
}

void test_test_zones_parse_in_corner_order(void) {
  ProtocolAction a = handleRequest(
      "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":"
      "[[255,80,0],[0,0,0],[255,0,0],[1,2,3]],\"denali\":128}");
  TEST_ASSERT_TRUE(a.setTest);
  TEST_ASSERT_TRUE(a.error.empty());
  TEST_ASSERT_TRUE(a.testOut.kind == TestKind::Zones);
  TEST_ASSERT_TRUE((a.testOut.zones.frontL == Rgb{255, 80, 0}));
  TEST_ASSERT_TRUE((a.testOut.zones.frontR == Rgb{0, 0, 0}));
  TEST_ASSERT_TRUE((a.testOut.zones.rearL == Rgb{255, 0, 0}));
  TEST_ASSERT_TRUE((a.testOut.zones.rearR == Rgb{1, 2, 3}));
  TEST_ASSERT_EQUAL_UINT8(128, a.testOut.zones.denali);
}

void test_test_zones_denali_defaults_to_zero(void) {
  ProtocolAction a = handleRequest(
      "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":"
      "[[1,1,1],[1,1,1],[1,1,1],[1,1,1]]}");
  TEST_ASSERT_TRUE(a.setTest);
  TEST_ASSERT_EQUAL_UINT8(0, a.testOut.zones.denali);
}

void test_test_zones_reject_wrong_length(void) {
  ProtocolAction a = handleRequest(
      "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":[[1,1,1],[2,2,2]]}");
  TEST_ASSERT_FALSE(a.setTest);
  TEST_ASSERT_FALSE(a.error.empty());
}

void test_test_zones_reject_out_of_range_values(void) {
  ProtocolAction hi = handleRequest(
      "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":"
      "[[256,0,0],[0,0,0],[0,0,0],[0,0,0]]}");
  TEST_ASSERT_FALSE(hi.setTest);
  TEST_ASSERT_FALSE(hi.error.empty());

  ProtocolAction lo = handleRequest(
      "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":"
      "[[0,-1,0],[0,0,0],[0,0,0],[0,0,0]]}");
  TEST_ASSERT_FALSE(lo.setTest);
  TEST_ASSERT_FALSE(lo.error.empty());
}

void test_test_zones_reject_a_short_triple(void) {
  ProtocolAction a = handleRequest(
      "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":"
      "[[1,1],[0,0,0],[0,0,0],[0,0,0]]}");
  TEST_ASSERT_FALSE(a.setTest);
  TEST_ASSERT_FALSE(a.error.empty());
}

void test_test_rejects_an_unknown_mode(void) {
  ProtocolAction a = handleRequest("{\"type\":\"test\",\"mode\":\"strobe\"}");
  TEST_ASSERT_FALSE(a.setTest);
  TEST_ASSERT_FALSE(a.error.empty());
}

void test_config_message_carries_the_protocol_version(void) {
  std::string msg = configMessage(defaultConfig());
  JsonDocument doc;
  TEST_ASSERT_TRUE(deserializeJson(doc, msg) == DeserializationError::Ok);
  TEST_ASSERT_EQUAL_INT(kProtocolVersion, doc["protocolVersion"].as<int>());
  TEST_ASSERT_EQUAL_INT(2, kProtocolVersion);
}

void test_test_state_message_shape(void) {
  Config cfg = defaultConfig();
  TestMode t;
  t.kind = TestKind::Zones;
  t.startedMs = 1000;

  JsonDocument doc;
  std::string msg = testStateMessage(t, cfg, 1000 + 11000);
  TEST_ASSERT_TRUE(deserializeJson(doc, msg) == DeserializationError::Ok);
  TEST_ASSERT_EQUAL_STRING("test_state", doc["type"].as<const char*>());
  TEST_ASSERT_TRUE(doc["active"].as<bool>());
  TEST_ASSERT_EQUAL_STRING("zones", doc["kind"].as<const char*>());
  TEST_ASSERT_EQUAL_UINT32(cfg.testMaxMs - 11000, doc["remainingMs"].as<uint32_t>());
}

void test_test_state_message_when_off(void) {
  Config cfg = defaultConfig();
  TestMode t;                                   // Off
  JsonDocument doc;
  std::string msg = testStateMessage(t, cfg, 500000);
  TEST_ASSERT_TRUE(deserializeJson(doc, msg) == DeserializationError::Ok);
  TEST_ASSERT_FALSE(doc["active"].as<bool>());
  TEST_ASSERT_EQUAL_STRING("off", doc["kind"].as<const char*>());
  TEST_ASSERT_EQUAL_UINT32(0, doc["remainingMs"].as<uint32_t>());
}

void test_test_state_remaining_clamps_at_zero(void) {
  Config cfg = defaultConfig();
  TestMode t;
  t.kind = TestKind::Scenario;
  t.startedMs = 0;
  JsonDocument doc;
  std::string msg = testStateMessage(t, cfg, cfg.testMaxMs + 5000);
  TEST_ASSERT_TRUE(deserializeJson(doc, msg) == DeserializationError::Ok);
  TEST_ASSERT_EQUAL_UINT32(0, doc["remainingMs"].as<uint32_t>());
}
```

Register all thirteen in `main`:

```cpp
  RUN_TEST(test_test_off_is_accepted);
  RUN_TEST(test_test_scenario_resolves_the_preset);
  RUN_TEST(test_unknown_scenario_is_an_error);
  RUN_TEST(test_test_zones_parse_in_corner_order);
  RUN_TEST(test_test_zones_denali_defaults_to_zero);
  RUN_TEST(test_test_zones_reject_wrong_length);
  RUN_TEST(test_test_zones_reject_out_of_range_values);
  RUN_TEST(test_test_zones_reject_a_short_triple);
  RUN_TEST(test_test_rejects_an_unknown_mode);
  RUN_TEST(test_config_message_carries_the_protocol_version);
  RUN_TEST(test_test_state_message_shape);
  RUN_TEST(test_test_state_message_when_off);
  RUN_TEST(test_test_state_remaining_clamps_at_zero);
```

`test_unknown_type_is_error` already exists in this file and must keep passing — it is the "unknown messages degrade, not break" guarantee. Do not remove it.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m platformio test -e native -f test_web_protocol`
Expected: compile error — `'TestKind' was not declared`, `'kProtocolVersion' was not declared`.

- [ ] **Step 3: Extend the protocol header**

Replace `src/domain/web_protocol.h` entirely:

```cpp
#pragma once
#include "domain/config.h"
#include "domain/can_state.h"
#include "domain/test_mode.h"
#include <cstdint>
#include <string>

// Bumped whenever a message shape changes incompatibly. The app and the
// LittleFS image are separate flashes and can diverge; the app compares this
// and refuses rather than half-working. Version 1 did not send the field, so
// a missing value reads as 1.
constexpr int kProtocolVersion = 2;

struct ProtocolAction {
  bool        sendConfig   = false;
  bool        applyConfig  = false;
  bool        setDiscovery = false;
  bool        discoveryOut = false;
  bool        setTest      = false;
  Config      cfgOut;
  TestMode    testOut;
  std::string error;
};

// Parse one inbound WebSocket text message into an action. Never throws.
ProtocolAction handleRequest(const std::string& json);

// Outbound message builders.
std::string configMessage(const Config& c);
std::string framesMessage(const CanFrameSnapshot* frames, int count);
std::string errorMessage(const std::string& msg);
std::string testStateMessage(const TestMode& t, const Config& cfg, uint32_t nowMs);
```

- [ ] **Step 4: Implement the `test` branch**

In `src/domain/web_protocol.cpp`, insert before the `act.error = "unknown type";` line:

```cpp
  if (t == "test") {
    const char* modeStr = doc["mode"] | "";
    std::string m = modeStr;
    TestMode tm;

    if (m == "off") {
      tm.kind = TestKind::Off;
    } else if (m == "scenario") {
      const char* name = doc["scenario"] | "";
      if (!scenarioByName(name, tm.scenario)) {
        act.error = std::string("unknown scenario: ") + name;
        return act;
      }
      tm.kind = TestKind::Scenario;
    } else if (m == "zones") {
      JsonArrayConst zs = doc["zones"];
      if (zs.size() != 4) {
        act.error = "test zones must be 4 rgb triples";
        return act;
      }
      // ChannelIndex corner order: front L, front R, rear L, rear R.
      Rgb* dst[4] = { &tm.zones.frontL, &tm.zones.frontR,
                      &tm.zones.rearL,  &tm.zones.rearR };
      int zi = 0;
      for (JsonArrayConst z : zs) {
        if (z.size() != 3) {
          act.error = "test zone must be an rgb triple";
          return act;
        }
        int v[3];
        for (int k = 0; k < 3; ++k) {
          v[k] = z[k] | -1;
          if (v[k] < 0 || v[k] > 255) {
            act.error = "test zone value out of range";
            return act;
          }
        }
        *dst[zi++] = Rgb{ (uint8_t)v[0], (uint8_t)v[1], (uint8_t)v[2] };
      }
      const int den = doc["denali"] | 0;
      if (den < 0 || den > 255) {
        act.error = "test denali out of range";
        return act;
      }
      tm.zones.denali = (uint8_t)den;
      tm.kind = TestKind::Zones;
    } else {
      act.error = "test mode must be off, scenario or zones";
      return act;
    }

    act.setTest = true;
    act.testOut = tm;
    return act;
  }
```

- [ ] **Step 5: Add the version field and the `test_state` builder**

In `configMessage`, add the version line after `doc["type"] = "config";`:

```cpp
  doc["protocolVersion"] = kProtocolVersion;
```

Append the new builder at the end of `src/domain/web_protocol.cpp`:

```cpp
std::string testStateMessage(const TestMode& t, const Config& cfg, uint32_t nowMs) {
  JsonDocument doc;
  doc["type"] = "test_state";
  doc["active"] = (t.kind != TestKind::Off);
  doc["kind"] = t.kind == TestKind::Scenario ? "scenario"
              : t.kind == TestKind::Zones    ? "zones"
                                             : "off";
  uint32_t remaining = 0;
  if (t.kind != TestKind::Off) {
    const uint32_t elapsed = nowMs - t.startedMs;     // rollover-safe
    remaining = elapsed >= cfg.testMaxMs ? 0u : (cfg.testMaxMs - elapsed);
  }
  doc["remainingMs"] = remaining;
  std::string out;
  serializeJson(doc, out);
  return out;
}
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `python -m platformio test -e native -f test_web_protocol`
Expected: PASS, 22 tests (9 existing + 13 new).

- [ ] **Step 7: Run the whole native suite**

Run: `python -m platformio test -e native`
Expected: all suites PASS.

- [ ] **Step 8: Commit**

```bash
git add src/domain/web_protocol.h src/domain/web_protocol.cpp test/test_web_protocol/
git commit -m "feat(protocol): test messages, test_state, and a version field

Bad zone lengths, out-of-range values and unknown scenario names are
errors that leave test mode untouched, never silent no-ops. configMessage
now carries protocolVersion so a stale LittleFS image announces itself
instead of producing a UI whose buttons quietly do nothing.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: `WebServerHal::onDisconnect`

**Files:**
- Modify: `src/hal/web_server.h:10-16`
- Modify: `src/hal/web_server.cpp:12-18`, and append one definition

**Interfaces:**
- Consumes: nothing new.
- Produces: `WebServerHal::DisconnectCb` (`std::function<void(uint8_t clientId)>`) and `void WebServerHal::onDisconnect(DisconnectCb cb)`.

The HAL is excluded from the native build (`build_src_filter = +<*> -<main.cpp> -<hal/>`), so this task has no unit test. Its gate is that the ESP32 build compiles and that the on-hardware check in Task 6 sees the callback fire. This is why it is a small task of its own rather than folded into Task 6: a reviewer can approve the HAL change independently of the wiring decisions.

- [ ] **Step 1: Declare the callback**

In `src/hal/web_server.h`, add below the `MessageCb` alias:

```cpp
  using DisconnectCb = std::function<void(uint8_t clientId)>;
```

and below `void onMessage(MessageCb cb);`:

```cpp
  // Fires when a WebSocket client goes away. Test mode uses this so a phone
  // that walks out of range cannot leave the lights latched.
  void onDisconnect(DisconnectCb cb);
```

- [ ] **Step 2: Implement it**

In `src/hal/web_server.cpp`, add the storage next to `s_cb` (line 12):

```cpp
static WebServerHal::DisconnectCb s_disc;
```

Replace `onWsEvent` (lines 14-18) with:

```cpp
static void onWsEvent(uint8_t num, WStype_t type, uint8_t* payload, size_t length) {
  if (type == WStype_TEXT && s_cb) {
    s_cb(num, std::string(reinterpret_cast<char*>(payload), length));
  } else if (type == WStype_DISCONNECTED && s_disc) {
    s_disc(num);
  }
}
```

Append next to the existing `onMessage` definition:

```cpp
void WebServerHal::onDisconnect(DisconnectCb cb) { s_disc = cb; }
```

- [ ] **Step 3: Verify it compiles**

Run: `py -3.13 -m platformio run -e esp32`
Expected: SUCCESS.

- [ ] **Step 4: Commit**

```bash
git add src/hal/web_server.h src/hal/web_server.cpp
git commit -m "feat(web): surface WebSocket disconnects to the app layer

onWsEvent already received WStype_DISCONNECTED and discarded it. Test
mode needs it so a dropped phone releases the override.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Wire test mode into `main.cpp`

**Files:**
- Modify: `src/main.cpp:5` (include), `:24-31` (globals), `:49-66` (message handler), `:68` (disconnect wiring), `:74-100` (loop)

**Interfaces:**
- Consumes: `resolveOutputs`, `testExpired`, `TestMode`, `TestKind` (Task 3); `testStateMessage`, `ProtocolAction::setTest` (Task 4); `WebServerHal::onDisconnect` (Task 5).
- Produces: nothing other tasks consume. This is the top of the firmware stack.

`main.cpp` is excluded from the native build, so the gate here is the ESP32 build plus the on-hardware checks in Step 6.

- [ ] **Step 1: Add the include and the globals**

In `src/main.cpp`, add after `#include "domain/behavior_engine.h"`:

```cpp
#include "domain/test_mode.h"
```

and after `static EngineState g_engine;`:

```cpp
static TestMode    g_test;         // lighting override held by the web app
static EngineState g_testEngine;   // scenarios run against THIS, never g_engine
```

- [ ] **Step 2: Handle `setTest` and release helpers**

Add above `void setup()`:

```cpp
// Drop any active override and tell every client. Called on explicit exit,
// owner disconnect, and cap expiry.
static void releaseTest(uint32_t now) {
  g_test = TestMode{};
  g_testEngine = EngineState{};
  g_web.broadcast(testStateMessage(g_test, g_cfg, now));
}
```

Inside the `g_web.onMessage` lambda, after the `act.setDiscovery` block:

```cpp
    if (act.setTest) {
      const uint32_t now = millis();
      if (act.testOut.kind == TestKind::Off) {
        releaseTest(now);
      } else {
        // Last writer wins: a second client taking the mode is not an error.
        g_test = act.testOut;
        g_test.owner = client;
        g_test.startedMs = now;
        g_testEngine = EngineState{};
        // Broadcast, not sendTo: a second phone must not be unaware the
        // lights are held.
        g_web.broadcast(testStateMessage(g_test, g_cfg, now));
      }
    }
```

- [ ] **Step 3: Wire the disconnect release**

Immediately after the `g_web.onMessage(...)` call in `setup()`:

```cpp
  g_web.onDisconnect([](uint8_t client) {
    if (g_test.kind != TestKind::Off && g_test.owner == client) {
      releaseTest(millis());
    }
  });
```

- [ ] **Step 4: Route the outputs and broadcast the state**

In `loop()`, replace the compute line (line 89):

```cpp
    OutputIntent o = computeOutputs(s, g_cfg, now, g_engine);
```

with:

```cpp
    OutputIntent o = resolveOutputs(s, g_test, g_cfg, now, g_engine, g_testEngine);
```

Add the cap check immediately after `uint32_t now = millis();` (line 82), before the 10 ms tick — so an expired mode releases on the same iteration it is noticed:

```cpp
  if (testExpired(g_test, g_cfg, now)) releaseTest(now);
```

And add the 1 s state tick after the discovery block, mirroring its shape:

```cpp
  // Keep the app's countdown honest, and re-announce the override to any
  // client that connected after it was set.
  static uint32_t lastTest = 0;
  if (g_test.kind != TestKind::Off && now - lastTest >= 1000) {
    lastTest = now;
    g_web.broadcast(testStateMessage(g_test, g_cfg, now));
  }
```

- [ ] **Step 5: Verify it compiles**

Run: `py -3.13 -m platformio run -e esp32`
Expected: SUCCESS.

- [ ] **Step 6: Commit**

```bash
git add src/main.cpp
git commit -m "feat(main): hold the test override and its three release paths

Explicit exit, owner disconnect and the absolute cap all funnel through
releaseTest, so every release resets the scenario EngineState and
broadcasts. Scenarios drive g_testEngine, never g_engine.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

On-hardware verification waits until Task 8, when the UI exists to drive it. The checklist is in "Hardware verification" at the end of this plan.

---

### Task 7: Web app — banners and the test tab

**Files:**
- Modify: `data/index.html:10-21` (header and nav), `:24-32` (tunables), add a test section
- Modify: `data/style.css` (append)
- Modify: `data/app.js:1-36` (consts, state, `onMessage`), `:39-46` (`render`), `:159-163` (`collect`), `:193-212` (wiring)

**Interfaces:**
- Consumes: the `test`, `test_state` and `protocolVersion` protocol from Task 4; the scenario names from Task 3.
- Produces: `PROTOCOL_VERSION`, `SCENARIOS`, `ZONES`, `testState`, `scheduleSend`, `gamma8Js`, `resolveJs`, `normalizeHue` — Task 8 reuses the last four.

There is no JS test harness in this repo, so these two tasks are verified by reading the diff and by the hardware checklist. Keep them small for that reason.

- [ ] **Step 1: Restructure the header and add the test tab**

In `data/index.html`, replace the `<header>` block (lines 10-13) with:

```html
  <header>
    <div class="hrow">
      <h1>MCCAN Lighting</h1>
      <span id="status" class="status off">disconnected</span>
    </div>
    <!-- Both banners live in the header, outside the tab system, so they
         cannot be navigated away from while the lights are overridden. -->
    <div id="versionBanner" class="banner warn" hidden></div>
    <div id="testBanner" class="banner danger" hidden>
      <span id="testBannerText"></span>
      <button id="testExitBtn">Exit</button>
    </div>
  </header>
```

Add a nav entry after the Appearance button (line 17):

```html
    <button data-tab="test">Test</button>
```

Add the tunable input inside `#tab-tunables`, after the `spotHoldMs` label (line 30):

```html
      <label>Test mode auto-exit (ms)
        <input type="number" id="testMaxMs" min="10000" max="3600000" step="10000">
      </label>
```

Add the test section after `#tab-appearance` (line 36):

```html
    <section id="tab-test" class="tab">
      <p><small>Test mode overrides the lights until you exit it. The bike's
      own brake and indicator signals are ignored while it is active.</small></p>
      <h3>Scenarios</h3>
      <div id="scenarios" class="scenarios"></div>
      <h3>Zones</h3>
      <div id="testZones"></div>
      <label>Denali <span id="testDenaliPct">0%</span>
        <input type="range" id="testDenali" min="0" max="100" value="0">
      </label>
    </section>
```

- [ ] **Step 2: Add the styles**

Append to `data/style.css`:

```css
/* The UA's [hidden] rule loses to .banner's display, so restate it. */
[hidden] { display: none !important; }

header { flex-direction: column; align-items: stretch; }
.hrow { display: flex; align-items: center; gap: .75rem; }
.banner { display: flex; align-items: center; gap: .5rem; margin-top: .5rem;
          padding: .5rem .6rem; border-radius: .4rem; font-size: .85rem; }
.banner span { flex: 1; }
.banner button { padding: .35rem .7rem; border: none; border-radius: .3rem;
                 background: #fff; color: #111; font-size: .8rem; }
.banner.danger { background: #a11; color: #fff; }
.banner.warn { background: #7a5b00; color: #fff; }

input[type=range] { width: 100%; margin-top: .25rem; }
.row input[type=range] { flex: 2; margin-top: 0; }
.row .pct { flex: 0 0 3rem; text-align: right; font-variant-numeric: tabular-nums; }

.zone { border: 1px solid #333; border-radius: .4rem; padding: .5rem; margin: .5rem 0; }
.zone h4 { margin: 0 0 .3rem; font-size: .9rem; }
.scenarios { display: flex; flex-wrap: wrap; gap: .4rem; margin-bottom: .8rem; }
.scenarios button { padding: .5rem .7rem; border: none; border-radius: .4rem;
                    background: #2e3340; color: #eee; font-size: .85rem; }
.scenarios button.active { background: #4b8bff; color: #fff; }
```

- [ ] **Step 3: Add the constants, state and helpers**

In `data/app.js`, after the `MAX_BITS` const (line 10):

```js
const PROTOCOL_VERSION = 2;   // must match kProtocolVersion in web_protocol.h
// Must match kScenarioNames in test_mode.cpp — the firmware table is
// authoritative and rejects anything it does not know.
const SCENARIOS = ["allOff","drlDay","drlNight","leftInd","rightInd",
                   "hazards","brake","brakeNight","lowBeam","highBeam"];
// ChannelIndex corner order.
const ZONES = ["front L","front R","rear L","rear R"];
```

After `let ws = null;` (line 13):

```js
let testState = { active: false, kind: "off", remainingMs: 0 };
let activeScenario = null;
let testZoneState = [0, 0, 0, 0].map(() => ({ hue: [255, 255, 255], level: 0 }));
let testDenali = 0;
```

Append to the helpers section, after `hexToRgb` (line 191):

```js
// Mirrors resolveColor()/colorFromRgb() in color.h. Zone overrides are sent
// as raw duty, so the app applies gamma itself.
function gamma8Js(level) { return Math.round(255 * Math.pow(level / 255, 2.2)); }

function normalizeHue(rgb) {
  const m = Math.max(rgb[0], rgb[1], rgb[2]);
  return m ? rgb.map((c) => Math.round((c * 255) / m)) : [255, 255, 255];
}

function resolveJs(hue, level) {
  const g = gamma8Js(level);
  return normalizeHue(hue).map((c) => Math.floor((c * g) / 255));
}

function pctToLevel(p) { return Math.round((Number(p) * 255) / 100); }
function levelToPct(l) { return Math.round((l * 100) / 255); }

// One send per animation frame, so dragging a slider cannot flood the socket.
let pendingSend = null, rafId = 0;
function scheduleSend(fn) {
  pendingSend = fn;
  if (rafId) return;
  rafId = requestAnimationFrame(() => {
    rafId = 0;
    const f = pendingSend; pendingSend = null;
    if (f) f();
  });
}
```

- [ ] **Step 4: Handle the new messages**

Replace `onMessage` (lines 32-36):

```js
function onMessage(msg) {
  if (msg.type === "config") { checkVersion(msg.protocolVersion); cfg = msg.config; render(); }
  else if (msg.type === "frames") { renderFrames(msg.frames); }
  else if (msg.type === "test_state") { testState = msg; renderTestBanner(); }
  else if (msg.type === "error") { alert("Device error: " + msg.message); }
  // Anything else is ignored on purpose: a newer firmware broadcasting a
  // message this app does not know must be inert, not fatal.
}

function checkVersion(v) {
  v = (v === undefined) ? 1 : v;    // v1 firmware did not send the field
  const el = document.getElementById("versionBanner");
  if (v === PROTOCOL_VERSION) { el.hidden = true; return; }
  el.textContent = v < PROTOCOL_VERSION
    ? "Firmware is older than this web app (device v" + v + ", app v" + PROTOCOL_VERSION +
      "). Reflash the firmware: py -3.13 -m platformio run -e esp32 -t upload"
    : "This web app is older than the firmware (device v" + v + ", app v" + PROTOCOL_VERSION +
      "). Reflash the web files: py -3.13 -m platformio run -e esp32 -t uploadfs";
  el.hidden = false;
}
```

- [ ] **Step 5: Render the banner and the test tab**

Add after `renderColors` (line 73):

```js
function renderTestBanner() {
  const el = document.getElementById("testBanner");
  el.hidden = !testState.active;
  if (!testState.active) {
    activeScenario = null;
    renderScenarios();
    return;
  }
  const s = Math.max(0, Math.round(testState.remainingMs / 1000));
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  document.getElementById("testBannerText").textContent =
    "TEST MODE — lights overridden, CAN input ignored · " +
    testState.kind + " · auto-exit in " + mm + ":" + ss;
}

// The device broadcasts test_state once a second; tick locally between
// broadcasts so the countdown does not look stalled.
setInterval(() => {
  if (!testState.active) return;
  testState.remainingMs = Math.max(0, testState.remainingMs - 1000);
  renderTestBanner();
}, 1000);

function exitTest() { send({ type: "test", mode: "off" }); }

function renderScenarios() {
  const host = document.getElementById("scenarios");
  host.innerHTML = "";
  SCENARIOS.forEach((name) => {
    const b = document.createElement("button");
    b.textContent = name;
    if (name === activeScenario) b.classList.add("active");
    b.onclick = () => {
      activeScenario = name;
      send({ type: "test", mode: "scenario", scenario: name });
      renderScenarios();
    };
    host.appendChild(b);
  });
}

function sendTestZones() {
  activeScenario = null;
  scheduleSend(() => send({
    type: "test",
    mode: "zones",
    zones: testZoneState.map((z) => resolveJs(z.hue, z.level)),
    denali: testDenali,
  }));
}

function renderTestZones() {
  const host = document.getElementById("testZones");
  host.innerHTML = "";
  ZONES.forEach((label, i) => {
    const z = testZoneState[i];
    const box = document.createElement("div"); box.className = "zone";
    const h = document.createElement("h4"); h.textContent = label; box.appendChild(h);

    const row = document.createElement("div"); row.className = "row";
    const picker = document.createElement("input");
    picker.type = "color"; picker.value = rgbToHex(z.hue);
    const level = document.createElement("input");
    level.type = "range"; level.min = 0; level.max = 100;
    level.value = levelToPct(z.level);
    const pct = document.createElement("span");
    pct.className = "pct"; pct.textContent = level.value + "%";

    const update = () => {
      z.hue = normalizeHue(hexToRgb(picker.value));
      z.level = pctToLevel(level.value);
      pct.textContent = level.value + "%";
      sendTestZones();
      renderScenarios();     // a zone edit clears the active scenario
    };
    picker.oninput = update;
    level.oninput = update;

    row.appendChild(picker); row.appendChild(level); row.appendChild(pct);
    box.appendChild(row); host.appendChild(box);
  });
}
```

- [ ] **Step 6: Wire it up**

Add to `render()` (after `renderColors();`, line 44):

```js
  document.getElementById("testMaxMs").value = cfg.testMaxMs;
  renderScenarios();
  renderTestZones();
```

Add to `collect()` (after the `spotHoldMs` line, 161):

```js
  cfg.testMaxMs = clamp(document.getElementById("testMaxMs").value, 10000, 3600000);
```

Append to the wiring section at the bottom of the file, before `connect();`:

```js
document.getElementById("testExitBtn").onclick = exitTest;
document.getElementById("testDenali").oninput = (e) => {
  testDenali = pctToLevel(e.target.value);
  document.getElementById("testDenaliPct").textContent = e.target.value + "%";
  sendTestZones();
};
```

- [ ] **Step 7: Check the file parses**

Run: `node --check data/app.js`
Expected: no output (success). If `node` is unavailable, open the page in a browser with the console visible and confirm there is no `SyntaxError`.

- [ ] **Step 8: Commit**

```bash
git add data/index.html data/app.js data/style.css
git commit -m "feat(app): test tab, override banner, and version mismatch banner

Both banners render inside <header>, outside the tab system, so the
override warning cannot be navigated away from while the lights are
lying about brake and indicator state. Unknown message types are
ignored rather than thrown on.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Web app — level editing and appearance preview

**Files:**
- Modify: `data/app.js:61-73` (`renderColors`), plus a `PREVIEW_ZONES` const and a `previewEntry` function
- Modify: `data/index.html:34-36` (`#tab-appearance`)

**Interfaces:**
- Consumes: `resolveJs`, `normalizeHue`, `pctToLevel`, `levelToPct`, `scheduleSend` from Task 7; the `{hue, level}` config shape from Task 2.
- Produces: nothing downstream. This is the last task.

- [ ] **Step 1: Add the preview toggle to the markup**

In `data/index.html`, replace the appearance section (lines 34-36):

```html
    <section id="tab-appearance" class="tab">
      <label><input type="checkbox" id="previewToggle">
        Preview on the bike's lights while editing</label>
      <div id="colors"></div>
    </section>
```

- [ ] **Step 2: Add the preview mapping**

In `data/app.js`, after the `ZONES` const:

```js
// Which zones each appearance entry drives while Preview is on. Preview is an
// ordinary zones override whose contents the UI computes — the firmware needs
// no concept of it.
const PREVIEW_ZONES = {
  drlWhiteDay:     [0, 1],
  drlWhiteNight:   [0, 1],
  drlDimRedDay:    [2, 3],
  drlDimRedNight:  [2, 3],
  brakeRed:        [2, 3],
  indicatorOrange: [0, 1, 2, 3],
};
```

And next to the other module state:

```js
let previewOn = false;
```

- [ ] **Step 3: Rewrite `renderColors` with hue plus level**

Replace `renderColors` (lines 61-73):

```js
function renderColors() {
  const host = document.getElementById("colors");
  host.innerHTML = "";
  COLORS.forEach((k) => {
    const e = cfg.colors[k];
    const row = document.createElement("div");
    row.className = "row";

    const name = document.createElement("span"); name.textContent = k;
    const picker = document.createElement("input");
    picker.type = "color"; picker.value = rgbToHex(e.hue);
    const level = document.createElement("input");
    level.type = "range"; level.min = 0; level.max = 100;
    level.value = levelToPct(e.level);
    const pct = document.createElement("span");
    pct.className = "pct"; pct.textContent = level.value + "%";

    const update = () => {
      // The stored hue is always normalized so brightness lives entirely in
      // the level. The picker's own value is deliberately NOT written back:
      // snapping the swatch mid-drag fights the user, and the level slider
      // already shows the brightness the normalization moved there.
      e.hue = normalizeHue(hexToRgb(picker.value));
      e.level = pctToLevel(level.value);
      pct.textContent = level.value + "%";
      if (previewOn) previewEntry(k, e);
    };
    picker.oninput = update;
    level.oninput = update;

    row.appendChild(name); row.appendChild(picker);
    row.appendChild(level); row.appendChild(pct);
    host.appendChild(row);
  });
}

function previewEntry(k, e) {
  const zones = [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]];
  const duty = resolveJs(e.hue, e.level);
  (PREVIEW_ZONES[k] || []).forEach((i) => { zones[i] = duty; });
  scheduleSend(() => send({ type: "test", mode: "zones", zones, denali: 0 }));
}
```

- [ ] **Step 4: Wire the toggle**

Append to the wiring section:

```js
document.getElementById("previewToggle").onchange = (e) => {
  previewOn = e.target.checked;
  // Turning preview off releases the override rather than leaving the last
  // previewed colour latched on the bike.
  if (!previewOn) send({ type: "test", mode: "off" });
};
```

And keep the checkbox honest when the device releases the mode on its own — add to `renderTestBanner`, inside the `if (!testState.active)` branch, before `renderScenarios();`:

```js
    previewOn = false;
    document.getElementById("previewToggle").checked = false;
```

- [ ] **Step 5: Check the file parses**

Run: `node --check data/app.js`
Expected: no output.

- [ ] **Step 6: Run the full native suite one last time**

Run: `python -m platformio test -e native`
Expected: all suites PASS.

- [ ] **Step 7: Commit**

```bash
git add data/index.html data/app.js
git commit -m "feat(app): edit colours as hue plus level, with live preview

Preview reuses the zones override, so the firmware needs no preview
concept. Turning it off, or the device releasing the mode, both clear
the toggle rather than leaving a previewed colour latched.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Hardware verification

Native tests cover the domain layer. `main.cpp` and `src/hal/` are excluded from that build, so the wiring in Tasks 5-8 is only proven on the board. Run this after Task 8, with both images flashed:

```bash
py -3.13 -m platformio run -e esp32 -t upload
py -3.13 -m platformio run -e esp32 -t uploadfs
```

Flash **both**. Flashing only one is exactly the mismatch the version banner exists to catch — if the banner appears, the other image is stale.

- [ ] Join `MCCAN-Setup`, open `http://192.168.4.1/`. No version banner.
- [ ] Test tab → `hazards`. All four corners blink orange. Banner appears with a counting-down timer.
- [ ] Navigate to every other tab. The banner stays visible on all of them.
- [ ] Test tab → `brake`. Both rear corners go red, fronts stay white.
- [ ] Zone controls: set front L to pure red at 100%, everything else to 0. Confirm **only** the front-left R channel lights — this is bring-up Stage 6's channel-to-corner check. Repeat for G and B and for each of the four corners: 12 channels, each verified alone.
- [ ] Denali slider drives both Denali channels together.
- [ ] Banner Exit button → lights return to CAN-driven behaviour immediately.
- [ ] Turn WiFi off on the phone mid-override. Lights return to normal within a few seconds (owner disconnect).
- [ ] Set `testMaxMs` to 20000 on Tunables, save, start a scenario, wait. Lights release on their own and the banner clears.
- [ ] Two phones: set a scenario on A, confirm B's banner appears too. Disconnect B; A's override survives. Disconnect A; the override releases.
- [ ] Appearance tab: enable Preview, drag `drlDimRedNight`'s level. The rear lights follow the drag smoothly. Disable Preview; lights return to normal.
- [ ] Save & apply, power-cycle the board, reconnect. Levels and hues come back as saved.
- [ ] With a config saved by the **old** firmware still on the device: boot the new firmware and confirm the lights look unchanged and the Appearance tab shows levels of 100%, 71%, 71%, 52%, 100%, 100% (the migrated values), not all 100%.

---

## Notes for the executor

- **Do not "fix" the brake-behind-indicator behaviour.** `behavior_engine.cpp:18` makes the brake light vanish on the indicating side during the blink off-phase. It is a known, separately-decided question and is out of scope here. Task 2 touches those exact lines; keep the logic identical.
- `src/domain/gamma_table.h` is generated. If a value looks wrong, change `scripts/gen_gamma.py` and re-run it; never hand-edit the header.
- Task 2 is the only task that leaves the tree uncompilable partway through. Do all six of its edit steps before running the build.
- The scenario name list exists twice — `kScenarioNames` in `test_mode.cpp` and `SCENARIOS` in `app.js`. The firmware is authoritative; an unknown name from the app produces an error response, not a silent no-op. `test_every_advertised_scenario_name_resolves` guards the firmware half.
