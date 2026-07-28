# ESP32 MCCAN — Dynamic CAN-Driven Lighting Firmware

**Status:** Design approved (2026-07-29)
**Scope:** Firmware + configuration web app for the ESP32 lighting controller.
**Out of scope (future sessions):** PCB/hardware design, and app packaging beyond the self-hosted web app.

---

## 1. Overview

Software for an ESP32 that reads a motorcycle's CAN bus and drives vehicle lighting
dynamically based on the signals it receives. The reference vehicle is an **Energica
Experia** (electric adventure bike), but the CAN mapping is **configurable per bike** so
the same firmware works on other motorcycles.

The controller drives:
- **4 analog 3-channel RGB COB LED strings** — one per corner (front-left, front-right,
  rear-left, rear-right). Each string shows a single uniform color at a time, driven by 3
  PWM channels (R, G, B).
- **2 Denali auxiliary light channels** — white driving lights, PWM-dimmable, driven
  **identically** to each other.

Configuration is done from a phone via a **self-hosted web app** served by the ESP32 over
its own WiFi access point.

### Key design insight

Across different bikes, the **lighting behavior is identical** — only the CAN *source* of
each signal changes. A brake is a brake; what varies is which `(CAN ID, bit)` means
"brake" on one bike vs. another. Therefore the firmware **hardcodes the behavior** and
makes only the **CAN mapping and tunables configurable** (approved: Approach 1, a
config-driven mapping + fixed behavior engine — not a general programmable rule engine).

---

## 2. Architecture

Four layers, each with a single responsibility and a clean interface:

```
CAN bus → [1. CAN Input Layer] → logical function states
                                        ↓
                              [2. Behavior Engine]  ← config (mapping + tunables)
                                        ↓
                              output intents (per-channel color/brightness)
                                        ↓
                              [3. Output/Driver Layer] → 14 PWM channels

[4. Connectivity Layer]  (WiFi AP + web app + WebSocket)
      └── reads/writes config, streams CAN frames for discovery
```

1. **CAN Input Layer** — reads TWAI (ESP32 CAN) frames, applies the `(ID, bit)` mapping,
   and produces a clean set of boolean **logical function** states. Handles single-bit,
   multi-bit `AND`, and multi-bit `OR` combos.
2. **Behavior Engine** — the fixed, proven logic: corner priority matrix, flash timing,
   Denali mode selection, spot latch, Run gating. A **pure function** of
   `(logical states + config tunables) → per-channel output intents`. No hardware calls,
   so it is fully unit-testable on the host.
3. **Output/Driver Layer** — converts intents into PWM duty cycles across 14 channels,
   behind a small `setChannel(id, duty)` interface so the firmware is independent of the
   PCB's PWM implementation.
4. **Connectivity Layer** — SoftAP + HTTP (serves the web app) + WebSocket (live config
   apply/save + CAN discovery stream). Runs concurrently with lighting; config changes
   apply live without interrupting the lights.

---

## 3. Inputs — logical functions & CAN mapping

### Mapping model

Each logical function maps to one or more `(CAN ID, bit index)` conditions combined with a
rule:

```
function: high_beam
  match: AND
  bits: [ {id: 0x102, bit: 6}, {id: 0x102, bit: 16} ]
```

- Combine rules: **single-bit**, **AND** (e.g., high beam = bit 6 & bit 16),
  **OR** (e.g., brake = front brake OR rear brake).
- **Hazards are derived** (left_indicator AND right_indicator) — not separately mapped.
- **Bit index** is a position into the frame's data payload (byte = `bit ÷ 8`). A single
  canonical bit-numbering convention will be fixed and documented (resolves the
  "which bit is which" ambiguity permanently). See Open Questions.

### Logical function catalog

| Function | Default map (Experia) | Role |
|---|---|---|
| Run | `0x102` (bit TBD) | Master gate |
| Left indicator | `0x102` bit 18 | Corner flash |
| Right indicator | `0x102` bit 19 | Corner flash |
| Front brake | `0x102` bit 21 | Brake (OR) |
| Rear brake | `0x102` bit 22 | Brake (OR) |
| Low beam | `0x102` bit 7 | Denali night / low |
| High beam | `0x102` bit 6 AND bit 16 | Denali high |
| High-beam flash/pass | `0x102` bit 16 (momentary) | Spot trigger |
| Day/night mode | **unassigned** (discover) | Denali day vs. night |
| Kick stand | `0x102` bit 13 | Available, unwired |
| "Back" | `0x400` bit 16 | To clarify (see Open Questions) |

- The **Experia map ships as the built-in default profile**, so the firmware works
  out-of-box on the reference bike. Other bikes are remapped via discovery mode.
- **Unassigned functions** (e.g., day/night until discovered) simply do not fire.
- **Brake logic:** brake active = **front brake OR rear brake**.

---

## 4. Behavior Engine (fixed logic)

### 4.1 Corner behavior matrix (RGB strings)

Priority order: **Indicator/Hazard (highest) → Brake → DRL (default)**.
"orange/off" = flashing bright orange alternating with **fully dark** (clear on/off
contrast, no color shift).

| Condition | Front-L | Front-R | Rear-L | Rear-R |
|---|---|---|---|---|
| DRL (default) | white | white | dim red | dim red |
| Left indicator | orange/off | white | orange/off | dim red |
| Right indicator | white | orange/off | dim red | orange/off |
| Hazards | orange/off | orange/off | orange/off | orange/off |
| Brake (no indicator) | white | white | full red | full red |
| Brake + Left indicator | orange/off | white | orange/off | **full red** |
| Brake + Right indicator | white | orange/off | **full red** | orange/off |
| Brake + Hazards | orange/off | orange/off | orange/off | orange/off |

- A left indicator flashes **both** front-left and rear-left corners.
- When braking **and** indicating, the indicating corner flashes orange/off (indicator
  wins, goes fully dark on the off phase); the non-indicating rear corner shows full red.

### 4.2 Denali behavior (both channels identical)

| Experia state | Denali level (configurable) | Trigger |
|---|---|---|
| Daytime | daytime level | day/night mode = day |
| Nighttime | low-beam level | day/night mode = night (or low beam on) |
| High beam | high-beam level | high beam (bit 6 AND bit 16) |
| Spot / search | max level | long-press high-beam flash, latched |

- **Spot latch:** a long-press of the high-beam flash (bit 16 held beyond the configurable
  hold threshold) latches spot mode ON. It **auto-drops** when the rider selects low beam.
- Firmware computes **one** Denali value and writes it to **both** Denali outputs.

### 4.3 Run gating (master enable)

- **Run set:** full behavior (DRL, Denali, brake, indicators).
- **Run clear:** DRL **off**, Denali **off**, brake **ignored** — but **indicators and
  hazards remain fully functional** (parked-hazard safety).
- **Kick stand:** mapped and available in the app, but wired to no behavior by default.

### 4.4 Timing & tunables

- **Indicator flash period:** app-configurable; **default 340 ms on / 340 ms off**
  (~1.5 Hz).
- **Spot hold threshold:** app-configurable (e.g., default 800 ms).
- **Brightness/levels & colors:** app-configurable — DRL white level, dim-red level,
  day vs. night RGB corner levels, indicator orange, brake red, and Denali per-mode levels
  (daytime / low / high / spot).
- **Startup / unconfigured defaults:** **340 ms** blink, **full orange** indicators, and
  the baked-in Experia profile — so the bike always signals safely.

---

## 5. Config model & storage

A single JSON config document stored in **LittleFS** flash at `/config.json`, containing:

- **mappings** — the `(ID, bit, combine-rule)` per logical function.
- **tunables** — blink period, spot hold duration, related behavior flags.
- **appearance** — per-mode brightness levels and colors (DRL white, dim red, day/night
  RGB levels, indicator orange, brake red, Denali daytime/low/high/spot levels).

Lifecycle:

- **Boot:** load `/config.json` → apply → run. **All persisted settings are read and
  applied at boot time.**
- **Live edits:** when changed from the app, the file is written **and** applied
  immediately (no reboot required); the persisted file guarantees the same state on the
  next boot.
- **Fallback:** if the file is missing or corrupt, fall back to the **baked-in default
  profile** (Experia map, 340 ms, full orange).
- **Portability:** config is exportable/importable as a JSON file for backup and for
  sharing per-bike profiles.

---

## 6. Connectivity & web app

- **SoftAP** — the ESP32 hosts its own WiFi network; the phone joins it and a browser
  opens the served app (captive-portal redirect for convenience). Works on any phone
  (iOS + Android), no app store, one codebase (approved: Option A).
- **HTTP server** — serves the single-page web app (HTML/CSS/JS) from LittleFS.
- **WebSocket** — two jobs:
  1. **Live config** — read / apply / save.
  2. **Discovery mode** — streams decoded CAN frames to the browser so the user toggles a
     control on the bike, watches which bit flips, and assigns it to a function in a couple
     of taps. This turns "I don't know the bit" into a ~30-second learn step and is how
     unmapped functions (e.g., day/night) get assigned.
- **Web app screens:** Mapping (assign bits per function + discovery), Tunables
  (timing/hold), Appearance (colors/brightness per mode), Backup (export/import JSON),
  and a live Status/monitor view.
- Lighting keeps running while the AP is up; config sessions never interrupt the lights.

---

## 7. Output/driver layer & PWM constraint (carry into PCB phase)

- **Channel count:** 4 RGB corners × 3 (R, G, B) = **12** + 2 Denali = **14 PWM outputs**.
  Both Denali channels are driven identically (one computed value → two outputs, or
  paralleled in hardware — a PCB decision).
- **Constraint to resolve in the PCB session:** the classic **ESP32 (WROOM/WROVER) has 16
  LEDC PWM channels** — enough for 14 natively. **ESP32-S3/S2/C3 have only 8** — not
  enough. Two hardware paths:
  1. **Classic ESP32**, drive all 14 channels natively (simplest firmware; ties to the
     classic chip).
  2. **Any ESP32 + external PWM driver** (e.g., PCA9685, 16-channel I²C) — frees the MCU
     choice and offloads PWM, at the cost of an extra part.
- The driver layer sits behind a small `setChannel(id, duty)` interface, so the PWM path is
  a hardware decision that does not affect the behavior logic.
- **Automotive drive** (constant-current, 12 V input, load-dump protection) is a
  PCB-session topic; the firmware only outputs duty cycles.

---

## 8. Testing approach

- **Behavior Engine (host-testable, primary correctness surface):** unit-test the entire
  corner matrix (all 8 rows), brake+indicator priority, hazard derivation, spot latch
  on/auto-drop, Run gating, and timing — on the dev machine, no ESP32 required.
- **CAN Input Layer:** table-driven tests — feed synthetic frames, assert logical states
  (single-bit, AND, OR, multi-ID).
- **Config:** round-trip load/save; corrupt-file → default-profile fallback.
- **On-hardware smoke tests:** TWAI receive, PWM output on a bench, SoftAP + web app +
  discovery stream.

---

## 9. Open questions (resolve during review / discovery; non-blocking)

1. **Run bit** — exact `0x102` bit for the Run master gate not yet identified.
2. **Day/night bit** — dedicated bit exists on the Experia but is not yet identified
   (assign via discovery mode).
3. **"Back" @ `0x400` bit 16** — confirm what this function drives.
4. **Brake OR-logic** — confirm brake active = front brake OR rear brake.
5. **Canonical bit-numbering convention** — fix and document how bit index maps to
   byte/bit within a CAN frame (endianness / bit order).
6. **Duplicate "Run" entries** in the source doc (bit 14 and bit 11) — clarify which is the
   true Run signal.

---

## 10. Downstream (future sessions, separate specs)

- **PCB / hardware design** — ESP32 variant choice, CAN transceiver, automotive power
  (12 V, load-dump protection, buck regulation), constant-current LED drivers, PWM path,
  connectors.
- Each downstream subsystem gets its own spec → plan → implementation cycle.
