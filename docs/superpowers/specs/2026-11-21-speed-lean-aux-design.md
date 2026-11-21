# Speed- and lean-aware aux pods — design

Date: 2026-11-21. Status: draft for the owner's review.
Branch: `claude/firmware-options-2c34ae` (firmware session; board change is the main-board session's).

## 1. Intent

Two new pod behaviours, both driven by numbers read off the bike's CAN bus:

1. **Lean (cornering light).** When the bike leans, the pod on the inside of the
   lean (nearer the road) gets brighter to light the turn, and the outside pod
   (pointing up and across at oncoming traffic) dims so it does not dazzle drivers.
   Owner's words: "increase the brightness at night of the pod closest to the ground
   ... also allow dimming the highside aux pod so as not to blind cars."
2. **Speed (high beam).** With high beam on, pod brightness follows road speed.

Why: more useful light where the rider is looking in a corner, less glare for other
road users. Owner decisions so far:

- Lean on high beam: the **inside pod goes to full**.
- Each pod gets **its own brightness signal**: GPIO 12 becomes the right pod's PWM
  (owner: "Use GPIO 12"), so the outside pod can really dim, not just switch off.
- The CAN signals are found from a **SavvyCAN recording** made with the owner's
  reprogrammed MrDIY tool (`D:\Projects\ESP32CANBUSReader`, GVRET over USB). No
  record button in this firmware.

## 2. Goals, non-goals, anti-goals

Goals
- Read speed and lean as numbers from configurable CAN signals, with a live readout
  in the web app so the owner can confirm sign and scale on the bike.
- Independent left/right yellow duty.
- The two behaviours above, each with an on/off switch and a few settings.

Non-goals
- Recording or exporting CAN traffic (SavvyCAN does it).
- Any new indicator, brake or DRL behaviour.
- Making the outside pod dim on low beam in the *day* (pods are off in the day
  unless high beam is on; that stays).

Anti-goals (failure even if it "works")
- Anything that makes the lights worse than today when a signal is missing, wrong or
  stale. Every fallback is **exactly today's behaviour**.
- Breaking the indicator rule: an indicating side's pod still goes Off (always at
  Low, at Full when `auxOffOnIndicateHighBeam`). Lean never relights it.
- Driving GPIO 12 HIGH at or before reset (it is the MTDI flash-voltage strap).
- Visible flicker or stepping as the bike rolls into and out of a corner.

## 3. Constraints

- One pod brightness per side; pod power is the existing on/off switch per side
  (`OUT_AUX_L/R`), brightness is the yellow PWM duty.
- GPIO 12 rules (from the main-board session): attach its LEDC channel only
  **after** `g_bus.begin()` (TWAI briefly claims it as TX; `CanBus::begin` hands it
  back as input + pull-down); never drive it before reset; R36 stays as the strap
  pull-down. Bench check before riding: force restarts (watchdog, `ESP.restart`,
  brown-out) with the right pod lit and confirm it always boots.
- Behaviour stays pure in `behavior_engine.cpp` and is unit-tested natively.
- The CAN table holds 64 IDs; numeric signals read from it like bits do.
- Message shapes change, so `kProtocolVersion` 7 -> 8, and the app mirror
  (`scripts/check_app_mirrors.py`) must agree.

## 4. Approaches considered

**Recording.** (a) Record button in the web app saving the 4 Hz Discovery snapshots;
(b) firmware logs every frame; (c) owner's SavvyCAN tool. **Chosen: (c)** — owner
already has it, it logs every frame with timestamps, and it costs no firmware.

**Reading numbers.** (a) Generic signal definitions set in the web app (ID, start
bit, length, byte order, signed, scale, offset) with a live value; (b) hard-code the
decoded signals into firmware. **Chosen: (a)**, matching how bits are mapped today:
a wrong sign or scale is a settings change, not a firmware build.

**Brightness per side.** (a) Split PWM (second pin); (b) keep one shared duty and
switch the outside pod off. **Chosen: (a)**, board not yet ordered, owner approved.

## 5. Design

### 5.1 Numeric CAN signals

New config type:

```
struct NumSignal {
  uint32_t id = 0;
  uint8_t  startBit = 0;   // same bit numbering as BitRef: byte*8 + bit, LSB = 0
  uint8_t  length = 0;     // 1..32; 0 = unmapped
  bool     bigEndian = false;  // false = Intel (little-endian), true = Motorola
  bool     isSigned = false;
  float    scale = 1.0f;   // value = raw * scale + offset
  float    offset = 0.0f;
};
```

Two instances in `Config`: `speedSignal` (result in km/h) and `leanSignal` (result
in degrees, **positive = leaning right**; a wrong sign is fixed with a negative
scale). Motorola start bit uses the DBC convention (MSB position); the exact rule is
written into the decoder's comment and tests.

`CanState` gains a per-frame last-seen time. A signal is **valid** only when it is
mapped, its frame has been seen within `kStaleMs` (500 ms), and the decoded value is
plausible (speed 0..400 km/h, lean −80..+80°). `LogicalState` gains
`float speedKmh; bool speedValid; float leanDeg; bool leanValid;`.

### 5.2 Two PWM channels

- `OutputIntent::auxDuty` becomes `auxDutyL` and `auxDutyR`. `applyIntent` writes
  both duties before any switch, as today.
- `IAuxPwm::setDuty(uint8_t)` becomes `setDuty(uint8_t left, uint8_t right)`;
  `LedcAuxPwm` owns two LEDC channels at `kAuxPwmHz`, left on GPIO 13 attached in
  `setup()` first thing (as today), right on GPIO 12 attached by a separate
  `beginRight()` called straight after `g_bus.begin()`. Until then a right duty is
  ignored (the pin stays input/pull-down). A failed attach is logged; that pod's main
  LEDs stay dark (fails dark, as today).
- Test mode "Zones" lights each pod at the Low duty, per side.

### 5.3 Brightness rules (per pod, in `computeOutputs`)

Start from today's level per pod (Off / Low / Full) and today's indicator rule. Then,
for each pod that is not Off:

1. **Base duty.** Low -> `auxLowDuty`. Full -> `auxFullDuty`, or, when
   `speedScaleEnable` and speed is valid, the speed curve:
   - speed <= `hbSlowKmh`: `hbSlowDuty`
   - speed >= `hbFullKmh`: `auxFullDuty`
   - between: straight line.
   Speed invalid -> `auxFullDuty` (today's behaviour).
2. **Lean.** When `leanEnable`, lean valid and the pod is lit (night Low or high
   beam): `k` = 0 at |lean| <= `leanStartDeg`, 1 at |lean| >= `leanFullDeg`,
   straight line between.
   - Inside pod (right pod when leaning right): rises from base toward the boost
     target: on Low, `leanBoostDuty`; on Full, `auxFullDuty` (owner: "inside pod goes
     to full"). Never lower than base.
   - Outside pod: falls from base toward `leanDimDuty`. Never higher than base.
   - Lean invalid -> k = 0 (today's behaviour).
   - Speed gate (owner, 2026-11-21: "there should be a minimum speed - say
     20mph/40kmh"): when `leanMinKmh` > 0, k = 0 unless speed is valid and
     >= `leanMinKmh`, so walking the bike or the side stand's tilt does nothing.
     `leanMinKmh` 0 = no speed needed. Speed is in km/h; if the bike's signal is
     mph, the speed signal's scale converts it (x1.609).
3. **Indicator rule** unchanged and applied last: an indicating side's pod is Off.
4. **Smoothing.** Each side's duty moves toward its target at most `kAuxSlewPctPerS`
   (build constant, proposed 250 %/s: a full 0->100 swing takes 0.4 s). Turning a pod
   **off** is immediate (indicator rule, R48). A pod switching **on** starts at its
   target — it is not faded up from 0. The slew state lives in `EngineState`.

Everything is capped at `auxFullDuty`. Low is still capped at Full, as today.

### 5.4 New settings (Config, JSON, web app Tunables)

| Key | Default | Range | Meaning |
|---|---|---|---|
| `speedScaleEnable` | false | bool | high-beam brightness follows speed |
| `hbSlowKmh` | 20 | 0..300 | at or below this, high beam uses `hbSlowDuty` |
| `hbFullKmh` | 80 | 0..300 | at or above this, high beam is `auxFullDuty` |
| `hbSlowDuty` | 50 | 0..100 % | high-beam brightness at low speed |
| `leanEnable` | false | bool | cornering boost/dim |
| `leanStartDeg` | 10 | 0..60 | lean where the effect starts |
| `leanFullDeg` | 30 | 1..70 | lean where the effect is complete |
| `leanBoostDuty` | 60 | 0..100 % | inside pod target on night Low |
| `leanDimDuty` | 5 | 0..100 % | outside pod target (Low and high beam) |
| `leanMinKmh` | 40 | 0..300 | no cornering effect below this speed or with no valid speed; 0 = always |

Both features ship **disabled**, so flashing this firmware changes nothing until the
signals are mapped and checked. Bad combinations are tolerated, not rejected:
`hbFullKmh <= hbSlowKmh` or `leanFullDeg <= leanStartDeg` act as a step at the higher
value.

`speedSignal` and `leanSignal` live under `maps` in the JSON beside the bit maps, as
`{"id","start","len","be","signed","scale","offset"}`.

### 5.5 Web app

- **Mapping tab:** two new rows, Speed and Lean, each with the seven signal fields
  and a live value ("Lean: −23.4°", "—" when invalid).
- **Live values:** while Discovery streaming is on, the `frames` message also
  carries `signals: {speed, speedValid, lean, leanValid}`. The Mapping tab turns
  streaming on while it is open, so the readout works there.
- **Tunables tab:** the nine settings above, in two groups ("High beam by speed",
  "Cornering").
- **Test tab:** two new scenarios, `leanLeftNight` and `leanRightNight` (night, low
  beam, 30° lean), so the boost/dim can be checked on the bench with no signal mapped.
  Scenarios obey the current settings, so `leanEnable` must be on to see the effect:
  a scenario shows exactly what the bike would do.

### 5.6 Protocol

`kProtocolVersion` 8: config gains the two signals and nine settings; `frames` gains
`signals`. (`test_state` carries no duty today, so it is unchanged.) One history line.

## 6. Testing

Native Unity, written first:
- Signal decoder: Intel/Motorola, signed/unsigned, lengths 1/8/12/16/32, scale and
  offset, frame boundaries, unmapped, stale frame, implausible value.
- Engine: every row of 5.3 — speed curve ends and middle; lean start/full/middle on
  Low and Full, left and right; inside never below base, outside never above;
  indicator beats lean; invalid signals equal today's outputs exactly; slew limits
  and immediate off.
- JSON round trip and clamping for all new keys; old configs load with defaults.
- `applyIntent` writes both duties before switches.
- Existing tests updated for `auxDutyL/R`.

Done = native tests pass, `py -3.13 -m platformio run -e esp32` passes,
`scripts/check_app_mirrors.py` passes, owner has reviewed. Then the on-bike checks:
live values match the dash and the lean direction; GPIO 12 restart test.

## 7. Left to the builder

- Exact Motorola start-bit convention (document it, test it).
- File layout for the decoder (`can_signal.{h,cpp}` suggested).
- App layout details within the existing style.

## 8. Calls made by Claude (owner to check)

- Default values in 5.4, and that both features ship disabled.
- Outside pod dims to the same `leanDimDuty` on Low and on high beam.
- Lean works on high beam in the day too (pods are lit on high beam day or night).
- 250 %/s smoothing, turn-off immediate, turn-on not faded.
- Plausibility limits 0..400 km/h and ±80°.
- Speed signal lost on high beam -> full brightness (today's behaviour).
- Speed signal lost with `leanMinKmh` > 0 -> no cornering effect.
