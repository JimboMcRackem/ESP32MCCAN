# Test mode and brightness control — design

**Date:** 2026-09-21
**Status:** approved, ready for implementation planning
**Scope:** firmware (`src/`) and web app (`data/`). No hardware changes.

---

## Problem

Two gaps in the shipped firmware, found while reviewing how per-zone intensity works.

**1. Brightness is not separable from colour.** A configured colour is a raw RGB triple used
directly as PWM duty (`Config::drlDimRedNight = {60,0,0}`, applied by `applyIntent` with only an
8-bit to 12-bit rescale in `pwm_pca9685.cpp:14`). The web app edits these as `<input type="color">`
swatches (`app.js:60-73`). Consequences:

- Dimming means eyeballing a darker swatch, which drifts the hue while you do it.
- There is no readable level. "Rear running at 25%" cannot be expressed or reported.
- Duty is linear with no gamma, so `{128,0,0}` reads far brighter than half.
- The useful range for a dim night rear light is roughly duty 20-80 — a thin, hard-to-resolve
  slice of a colour picker's travel.

**2. There is no way to drive an output directly.** `handleRequest` accepts exactly three inbound
types — `get_config`, `set_config`, `discovery` (`web_protocol.cpp:16,21,40`) — and
`ProtocolAction` carries no override field. The main loop is unconditional:

```cpp
LogicalState s = g_can.evaluate(g_cfg);
OutputIntent o = computeOutputs(s, g_cfg, now, g_engine);
applyIntent(g_pwm, o);
```

`main.cpp:88-90`. The only way to light a circuit is to make the bike assert the real CAN bit.
On a bench with no bus, nothing can be lit at all. This also blocks bring-up **Stage 6** of the PCB
plan, which requires verifying that each of the 12 RGB channels switches independently and that
channel-to-corner mapping matches `ChannelIndex`.

## Goals

- Drive any lighting zone on demand from the web app: named scenarios, per-zone colour, Denali level.
- Tune brightness as a level, with live feedback on the real lights.
- Preserve the existing tuned configuration exactly across the upgrade.
- Make it impossible for test mode to silently corrupt normal behaviour.

## Non-goals

- Splitting `indicatorOrange` into front/rear entries, or adding night variants for indicator and
  brake. Explicitly declined; the entry set stays at six.
- Raw per-channel control. A per-zone RGB control already reaches each of the 12 channels
  individually — setting rear-left to pure red drives only the rear-left R channel — so a raw mode
  would be a second way to do the same thing.
- Gamma on the Denali channels. See "Denali stays raw" below.
- Any change to CAN decoding, the mapping UI, or discovery.

---

## Decisions

Recorded with rationale, because several were close calls.

| Decision | Choice | Rationale |
|---|---|---|
| Where test mode intercepts | Override the `OutputIntent` | Serves both scenarios and per-zone from one seam; scenarios reuse the real engine rather than reimplementing it |
| Preemption by real CAN events | None — test mode holds until exit | User's call, with a mandatory persistent warning that CAN input is ignored |
| Lost link | Exit on WS disconnect, plus absolute cap | A dead phone must not leave lights latched |
| Brightness representation | Hue plus separate level, gamma on the level | Dimming cannot drift hue; levels are readable and repeatable |
| Where tuning happens | Appearance tab gains live preview | One place to edit a value; no copying between tabs |
| Control granularity | Scenarios, per-zone colour, Denali | Raw channels dropped as redundant |

### Safety posture

Test mode holds unconditionally: a real brake application or indicator does **not** reclaim its
zone. This was chosen deliberately over safety-signal preemption, in exchange for a persistent,
unmissable warning in the UI. The design compensates where it can:

- The warning banner lives in the header, outside the tab system, so it cannot be navigated away
  from while the lights are overridden.
- `test_state` is **broadcast**, not sent only to the controlling client, so a second phone cannot
  be unaware the lights are held.
- Two independent releases (socket drop, absolute cap) bound how long an unattended override lasts.

Anyone porting this to a bike used differently should revisit the preemption decision first.

---

## Design 1: the colour model

### Type

`Rgb` stays as the wire and duty primitive. Config entries become:

```cpp
struct ColorLevel {
  Rgb     hue   = {255, 255, 255};  // normalized: brightest channel is 255
  uint8_t level = 255;              // 0-255; displayed as 0-100%
};
```

The six entries change type. The set does not change:
`drlWhiteDay`, `drlWhiteNight`, `drlDimRedDay`, `drlDimRedNight`, `indicatorOrange`, `brakeRed`.

### Resolution

Gamma applies to the **level only**, never per channel:

```
duty_c = hue_c * gamma8(level) / 255          for c in {r, g, b}

gamma8(v)    = round(255 * (v/255)^2.2)       256-entry constant table
gammaInv(d)  = round(255 * (d/255)^(1/2.2))   used only for migration
```

Per-channel gamma would distort every non-neutral colour: indicator orange `[255,80,0]` would
resolve to a different hue than the one picked. Scaling a fixed hue ratio by one gamma-corrected
level moves brightness only, which is the separation the feature exists to provide.

The table is generated at build time as a `constexpr` array — no floating point on the device.

### Migration

For each old triple, with `m = max(r,g,b)`:

```
m == 0:  hue = {255,255,255}, level = 0
m >  0:  hue = rgb * 255 / m,  level = gammaInv(m)
```

This is duty-preserving. Substituting into the resolution formula:

```
duty_c = (c * 255/m) * gamma8(gammaInv(m)) / 255
       = (c * 255/m) * m / 255
       = c
```

Every existing colour resolves to the duty it produces today. The bike looks unchanged after the
upgrade, and the levels shown in the UI are the honest current values rather than defaults.

**Known imprecision, stated so test failures are not mistaken for bugs:** integer rounding can
shift a resolved duty by one count, and at the very bottom of the range (duty 1-2) the gamma curve
is steep enough that the `gammaInv` then `gamma8` round trip may land one off. Neither is visible.
Tests assert a tolerance of ±1, not equality.

Migration triggers on load when `config_json` sees an entry in the old shape (a bare 3-element
array rather than an object). Serialization always writes the new shape, so the first save
completes the upgrade.

### Denali stays raw

`denaliDay/Low/High/Spot` remain plain 0-255 duty. They are single-colour, already tuned against
real beam output, and have no hue to separate. Applying gamma would silently change beam levels on
upgrade and force re-tuning for no benefit the feature needs.

---

## Design 2: test-mode core

New unit `src/domain/test_mode.h/.cpp`.

```cpp
enum class TestKind : uint8_t { Off, Scenario, Zones };

struct TestMode {
  TestKind     kind = TestKind::Off;
  LogicalState scenario;      // when kind == Scenario
  OutputIntent zones;         // when kind == Zones
  uint8_t      owner = 0;     // WS client id holding it
  uint32_t     startedMs = 0;
};
```

Two free functions, both testable off-device. `testExpired` is pure; `resolveOutputs` mutates only
the `EngineState` it is handed, as `computeOutputs` already does today:

```cpp
OutputIntent resolveOutputs(const LogicalState& real, const TestMode& t,
                            const Config& cfg, uint32_t nowMs,
                            EngineState& est, EngineState& testEst);

bool testExpired(const TestMode& t, const Config& cfg, uint32_t nowMs);
```

Behaviour by kind:

| Kind | Result |
|---|---|
| `Off` | `computeOutputs(real, cfg, nowMs, est)` — exactly today's path |
| `Scenario` | `computeOutputs(t.scenario, cfg, nowMs, testEst)` |
| `Zones` | `t.zones` verbatim |

Routing scenarios back through the real `computeOutputs` means they blink at the configured rate in
the configured colours. What the tester sees is what the engine does, not a parallel implementation
that can drift from it.

### Scenario state isolation

Scenarios run against a **separate** `EngineState`, held by `main.cpp` and reset on entry to test
mode. Without this, a scenario asserting `flash` would drive the spot-latch state machine
(`behavior_engine.cpp:41-49`) against the real engine state and could leave `spotLatched` set after
exit, silently changing how the bike behaves afterwards. The separate state makes test mode
structurally unable to corrupt real behaviour.

### Scenario table

A firmware-side table of `LogicalState` presets, looked up by name:

`allOff`, `drlDay`, `drlNight`, `leftInd`, `rightInd`, `hazards`, `brake`, `brakeNight`,
`lowBeam`, `highBeam`

An unknown name is an error response, not a silent no-op.

### Exit paths

1. **Explicit** — a `test` message with `mode: "off"`.
2. **Owner disconnect** — the WS client that set test mode goes away. Tracked by client id so a
   second phone disconnecting does not cancel an active session.
3. **Absolute cap** — `cfg.testMaxMs`, default `600000` (10 minutes), configurable on the Tunables
   tab. Checked as `nowMs - t.startedMs >= cap`, which is rollover-safe in unsigned arithmetic and
   matches the idiom already used by the flash timer.

On any exit the mode returns to `Off`, `testEst` is reset, and `test_state` is broadcast.

---

## Design 3: protocol

One new inbound type alongside the existing three.

```json
{"type": "test", "mode": "off"}
{"type": "test", "mode": "scenario", "scenario": "hazards"}
{"type": "test", "mode": "zones",
 "zones": [[255,80,0],[0,0,0],[255,0,0],[255,0,0]], "denali": 128}
```

`zones` is exactly four RGB triples in `ChannelIndex` corner order: front L, front R, rear L,
rear R. Wrong length, out-of-range values, or an unknown scenario produce an `error` response and
leave test mode untouched. `denali` is optional and defaults to `0`, so a zones message concerned
only with the RGB corners does not have to carry it.

**Concurrent clients.** Test mode is single-holder and last-writer-wins: a `test` message from a
second client takes ownership, resets `startedMs`, and re-broadcasts. It is not an error. The
broadcast is what keeps the losing client honest — its banner keeps showing the true state rather
than what it last asked for. Only the current owner's disconnect releases the mode.

`ProtocolAction` gains:

```cpp
bool     setTest = false;
TestMode testOut;
```

Outbound, **broadcast** on every change and on a 1 s tick while active:

```json
{"type": "test_state", "active": true, "kind": "zones", "remainingMs": 589000}
```

The 1 s tick reuses the pattern of the existing discovery stream in `loop()`.

`WebServerHal` gains an `onDisconnect(std::function<void(uint8_t)>)`. `onWsEvent`
(`web_server.cpp:14`) already receives `WStype_DISCONNECTED` and discards everything but
`WStype_TEXT`; this adds a branch and a stored callback.

---

## Design 4: web app

### Warning banner

Rendered in `<header>`, outside the tab system, whenever `test_state.active` is true. Red,
persistent, carrying:

- "TEST MODE — lights overridden, CAN input ignored"
- the live countdown from `remainingMs`
- an Exit button

It sits outside the tabs deliberately: in the test tab it could be navigated away from while the
bike's lights are still lying about brake and indicator state.

### Test tab

New nav entry. Contains scenario buttons (from a JS const mirroring the firmware table, carrying
the same "must match" comment style as `FUNCS` at `app.js:4`), four zone controls of hue picker
plus level slider, and a Denali level slider.

### Appearance tab preview

A Preview toggle. While on, editing any entry sends a `zones` test built in JS from that entry,
mapped to the zones it affects:

| Entry | Zones driven |
|---|---|
| `drlWhiteDay`, `drlWhiteNight` | front L, front R |
| `drlDimRedDay`, `drlDimRedNight`, `brakeRed` | rear L, rear R |
| `indicatorOrange` | all four |

Preview therefore needs no new firmware concept — it is an ordinary zones override whose contents
the UI computes. Slider drags are throttled to one send per animation frame so a drag cannot flood
the socket.

Each entry renders as a hue picker plus a 0-100% level slider. The UI normalizes whatever the
colour input returns so the stored hue always has its brightest channel at 255.

---

## Testing

Native suites, run with `python -m platformio` (the 3.14 install). Per existing convention each
suite is its own directory under `test/`. Unity's `setUp`/`tearDown` must be defined in every new
suite file.

| Suite | Covers |
|---|---|
| `test_color_level` | Resolution math; gamma table monotonic and endpoint-exact; hue preserved across levels; migration round trip duty-preserving within ±1 for all six defaults and a swept set of triples |
| `test_test_mode` | `resolveOutputs` per kind; scenario blink follows `blinkPeriodMs`; zones passthrough verbatim; `testExpired` including a millis-rollover case; scenario `flash` leaves the real `EngineState` untouched |
| `test_web_protocol` | Parse of all three `test` shapes; rejection of bad zone length, out-of-range values, unknown scenario; `test_state` serialization |
| `test_config_json` | Round trip of the new schema; migration from the old schema; unknown fields ignored |

Existing suites must continue to pass unchanged except where the config type change forces an
update.

---

## Files

| File | Change |
|---|---|
| `src/domain/color.h` | Add `ColorLevel`, gamma table, resolution |
| `src/domain/config.h`, `config.cpp` | Six entries become `ColorLevel`; add `testMaxMs` |
| `src/domain/config_json.cpp` | Serialize new shape; migrate old |
| `src/domain/test_mode.h`, `test_mode.cpp` | New — types, `resolveOutputs`, `testExpired`, scenario table |
| `src/domain/behavior_engine.cpp` | Consume resolved colours |
| `src/domain/web_protocol.h`, `.cpp` | `test` inbound, `test_state` outbound |
| `src/hal/web_server.h`, `.cpp` | `onDisconnect` callback |
| `src/main.cpp` | Hold `TestMode` and `testEst`; call `resolveOutputs`; wire disconnect, expiry, broadcast |
| `data/index.html`, `app.js`, `style.css` | Banner, test tab, preview toggle, level sliders |
| `test/` | Two new suites, two updated |

## Risks

| Risk | Mitigation |
|---|---|
| Lights left latched on a real vehicle | Persistent banner outside tabs; broadcast state; two independent auto-releases |
| Upgrade visibly changes tuned colours | Duty-preserving migration, asserted by test across all defaults |
| Test mode corrupts the spot latch | Separate `EngineState` for scenarios |
| Preview floods the socket during a drag | Throttled to one send per animation frame |
| UI and firmware scenario lists drift | Single firmware table is authoritative; unknown name is an error, not a no-op |
