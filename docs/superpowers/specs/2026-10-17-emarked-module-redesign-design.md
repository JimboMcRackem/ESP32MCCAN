# ESP32 MCCAN — Redesign for E-Marked Lighting Modules

**Status:** Design approved (2026-10-17)
**Supersedes:** the output stage of `2026-09-11-esp32-mccan-pcb-hardware-design.md` and
`2026-09-23-pcb-relayout-8layer-design.md`, and the output model of
`2026-07-29-esp32-mccan-lighting-firmware-design.md`. Those documents remain the record of the
CAN input layer, the config/web architecture and the generator toolchain, all of which carry
forward.
**Scope:** new hardware spec and new board, generated from scratch; firmware output model
rewritten.
**Out of scope:** the CAN input layer, the config/storage layer, the web app's Mapping,
Tunables, Backup and Status screens, and `hardware/scripts/` — all reused.

---

## 1. Why this redesign exists

Indicators fitted to a road vehicle in Europe must be **E-marked**. Hand-built LED assemblies
cannot be, so the previous design — four self-built 3-channel RGB COB strings driven at 24 V
through twelve current-sensed low-side MOSFETs — was not legal to fit, however well it worked.

The replacement is **bought, E-marked modules** that contain their own LEDs, their own current
regulation and their own optics. The controller stops being an LED driver and becomes a **12 V
load switch**.

This is a larger simplification than it sounds. It deletes the 24 V boost domain, the twelve
discrete FETs, the twelve current-sense shunts, the 16:1 analog mux, the PCA9685, an entire
power domain, every trace of colour from the firmware, and the machined aluminium thermal base
plate. It is also a capability loss, taken deliberately: with bought modules there is nothing
left to dim.

---

## 2. The parts this design is built around

### 2.1 Signal modules (indicators / DRL / brake)

Bought E-marked 12 V modules, one per corner, taking a **steady switched 12 V** per function —
**no PWM**.

| | Wires | Functions |
|---|---|---|
| Front (×2) | 3 | ground, DRL, indicator |
| Rear (×2) | 4 | ground, DRL, indicator, brake |

- **1.5 W per module**, total, in whichever mode it is in → **125 mA at 12 V**.
- **DRL and brake are OR'd internally** on the rear module: they drive one light engine, and
  the module handles the combination. No sequencing is required of the firmware — but see
  §5.3, where this fact *forces* a behavioral rule.
- **Emitters are 2835 SMD** — discrete mid-power packages, not COB and not a single high-power
  emitter. At 1.5 W a module is therefore on the order of six to eight of them. A 12 V module
  built this way is normally resistor-ballasted or linearly regulated rather than fed by a
  switching converter, which matters for §4.4: **the signal channels should present no
  meaningful turn-on inrush and no bulk capacitance.** Confirm against the datasheet once the
  part is chosen; it is an expectation here, not a measurement.
- Specific part not yet selected. The figures above are the design basis; §9 carries the
  verification items.

### 2.2 Auxiliary pods — Oxford 4K (EL385)

4480 lm pair, **6–26 W per pod**, 8–32 V DC, E-marked, IPX7.

At 12 V, 26 W is **2.17 A per pod, 4.33 A for the pair**. The wide input range means each pod
contains a switching converter, which has two consequences: it presents a **capacitive inrush**
at turn-on, and it cannot be dimmed from the supply side.

The kit ships as a complete system — battery ring leads, a relay in its own harness, an
`ACC RUN Light` substitute line, an `ACC HIGH BEAM` substitute line, a 5-stage handlebar switch
whose stages are a **mechanical dial**, and a switch-delete blank. Fitting methods A (switch)
and B (high-beam trigger) are documented in the EL385 user information sheet, pages 2–4.

**Decision: bypass Oxford's harness and drive the pods directly from this board.**

The alternative — driving Oxford's two trigger lines and leaving their harness intact — was
considered and rejected by the user. It would have kept Oxford's relay, fuse and integrated DRL,
and reduced our aux path to two signal-level outputs, but it would have fixed brightness at
whatever the dial or the switch-delete selects and left the firmware with only on/off.

Direct drive has a **known unknown**: the manual gives no pinout for the pod connector
(Plug C/D), no wire colours past the battery ring leads and no fuse rating. If Plug C/D proves
to be a plain +/− pair, direct drive yields **one brightness and no integrated DRL** — less
capability than the trigger approach would have given. The design therefore treats the pinout
as something to be **established, not assumed** (§9.1), and carries an unpopulated `AUX_MODE`
provision (§3) so a mode input can be used if one exists.

---

## 3. Interface contract

**Twelve outputs, every one a plain on/off high-side 12 V switch.** No PWM anywhere in the
design.

| Output | Load | Why it is a separate output |
|---|---|---|
| `FL_DRL`, `FR_DRL` | 125 mA | must drop independently when that side indicates (§5.3) |
| `RL_DRL`, `RR_DRL` | 125 mA | as above |
| `FL_IND`, `FR_IND` | 125 mA | left/right independent |
| `RL_IND`, `RR_IND` | 125 mA | as above |
| `RL_BRK`, `RR_BRK` | 125 mA | matrix requires brake on the *non*-indicating side only |
| `AUX_L`, `AUX_R` | 2.17 A | per-pod, for fault isolation and future asymmetry |
| `AUX_MODE` | — | **unpopulated provision**, fitted only if Plug C/D exposes a mode input |

Every one of the ten signal outputs is justified by a row of §5.2. None exists for symmetry.

### 3.1 Harness

Module grounds are tied at the board connector rather than run individually, which takes the
loom from 14 wires to 12.

| Connector | Pins | Contents |
|---|---|---|
| Front | 5 | 2× DRL, 2× IND, 1 shared return (250 mA worst case) |
| Rear | 7 | 2× DRL, 2× IND, 2× BRK, 1 shared return (250 mA worst case) |
| Pods | 4 (+1) | per-pod +12 V and return; pod returns do **not** share with signal returns |
| CAN | 2 | CAN H / CAN L |
| Feed | 2 | battery +, battery − |

### 3.2 Boot safety

**A floating or strapping-pin GPIO at reset must not light a lamp.** Every switch input carries
a hard pull-down, and the chosen parts must be off with their input open. This constrains part
selection and is not negotiable: an indicator that lights itself at every reset is a safety
defect.

---

## 4. Hardware architecture

```
 FEED ──[7.5 A fuse]──┐        12 V: ~0.6 A signals only / ~5.0 A with pods on
                      ▼
            ┌──────────────────┐
            │ INPUT PROTECTION │  LTC4380 + 2 FETs, rev. polarity + overcurrent
            │ 24 V TVS, pi+CM  │
            └────────┬─────────┘
                  VBAT (~12 V)
        ┌────────────┼─────────────────────┬──────────────────┐
        ▼            ▼                     ▼
 ┌─────────────┐ ┌─────────────────┐ ┌──────────────────┐
 │ 3V3 BUCK    │ │ QUAD SMART HS   │ │ DUAL SMART HS    │
 │ +3V3_ALW    │ │ x2 -> 10 ch     │ │ 2.17 A + inrush  │
 │ + 5V gated  │ │ 125 mA each     │ │ -> 2x AUX POD    │
 └──────┬──────┘ └─────────────────┘ └──────────────────┘
        │               ▲ 10 GPIO           ▲ 2 GPIO
        │        ┌──────┴───────────────────┴───┐
        └───────▶│ ESP32-WROOM-32E-N8           │
                 │ 12 GPIO out, all pulled down │
                 │ deep sleep <- EXT1 wake      │
                 └──────┬───────────────────────┘
                        │ TWAI
                 ┌──────┴──────────────┐
                 │ TJA1042T/3          │──▶ CAN H / L
                 │ listen-only, HW-enf.│
                 └─────────────────────┘
```

### 4.1 Load budget

| Load | Current @ 12 V |
|---|---|
| 2 × Oxford pod @ 26 W | 4.33 A |
| 4 × signal module @ 1.5 W | 0.50 A |
| Logic | ~0.10 A |
| **Total** | **~5.0 A** |

Feed fuse **7.5 A**. The previous design's feed was 7.0 A continuous / 7.8 A transient with a
10 A panel fuse; the load is comparable, but almost all of it now leaves the board through a
switch rather than being converted on it.

### 4.2 Carried forward from plan3

Proven, and reused without redesign: **LTC4380 + 2 FETs** input protection (reverse polarity,
overcurrent), **24 V TVS**, **π + common-mode filter**, **3V3 buck** producing `+3V3_ALW`,
**gated `+5V`**, **TJA1042T/3** with hardware-enforced listen-only, and **deep sleep with EXT1
wake on bus activity**.

**MCU stays the classic ESP32-WROOM-32E-N8.** The original reason for choosing it — 16 LEDC
channels for 14 PWM outputs — is now irrelevant, because the design contains **no PWM at all**.
12 GPIO outputs plus 2 for TWAI fit WROOM-32 comfortably, so there is no I/O expander and no
PCA9685. Re-opening the MCU choice would buy nothing and cost a retested pin map.

### 4.3 Deleted

The 24 V sync boost and its commutation loop; the 4 per-string PTCs; the 12 discrete
N-MOSFETs; the 12 source shunts; the 16:1 analog mux (ADG706); the PCA9685; and with the last
two, the **entire `+3V3_SW` domain**, since they were its only loads. Four power domains become
three: `+3V3_ALW`, gated `+5V`, and raw protected `VBAT`.

### 4.4 Output stage

**Multi-channel smart high-side switches** — two quad-channel parts for the ten signal outputs,
one dual-channel part for the pods. Chosen over discrete P-FETs because each channel brings
short-circuit protection, thermal shutdown and open-load detection in silicon, which replaces
the stage the previous design built by hand out of twelve shunts and a mux — the subsystem that
generated more review findings than any other in plan3.

**Pod inrush is the hard constraint — and it is confined to the aux channel.** A wide-input
converter looks like a discharged capacitor at turn-on, and a smart high-side switch answers
that by hitting its current limit and latching off. The **dual-channel** part must therefore be
selected for **capacitive-load / inrush capability specifically**, not merely for 2.17 A steady
state. If no suitable part exists, the fallback is deliberate gate slew-rate limiting. This is
expected to be the largest datasheet effort in the build, and it is the same part whose sense
output would provide pod lamp-out.

The **quad** parts carrying the ten signal outputs are not under that constraint: 2835-based
modules (§2.1) are resistive rather than capacitive loads, so those channels can be chosen on
steady-state 125 mA and protection alone. The absence of bulk capacitance also helps the
lamp-out nice-to-have, since there is no charging current to confuse an open-load threshold —
though whether any threshold resolves 125 mA is still the open question.

**Lamp-out detection is a nice-to-have, not a requirement.** It influences part selection only
as a tiebreaker and is dropped without ceremony if the open-load threshold cannot resolve
125 mA. It is report-only (§6) so it can never become a failure mode.

### 4.5 Board and enclosure

- **4 layers**: F.Cu signal / In1.Cu GND / In2.Cu VBAT plane / B.Cu signal.
- The feed is carried by a **poured plane**, not tracks, and its effective width is **measured
  with `check_plane_width.py`**, not derived in a comment.
- **Board dissipation ~1.2 W** (two pod switches ~0.3 W each, input FETs ~0.25 W, the buck) —
  to be measured, not trusted. The previous board's worst case was 2.31 W and needed a
  2174 mm² gap pad onto a machined aluminium base plate. **That entire thermal structure is
  deleted** and the enclosure becomes an ordinary sealed box. This is the largest single cost
  and complexity saving in the redesign.
- **Board size is an outcome of placement, not a target.** Part count is roughly a third of
  plan3's, so expect well under half its 200 × 140 mm area, but the figure comes from the
  density gate.

---

## 5. Firmware

### 5.1 Output model

`domain/color.h` and `Rgb` are deleted. `OutputIntent` becomes a single 12-bit word:

```cpp
enum OutputIndex : uint8_t {
  OUT_FL_DRL = 0, OUT_FL_IND, OUT_FR_DRL, OUT_FR_IND,
  OUT_RL_DRL, OUT_RL_IND, OUT_RL_BRK,
  OUT_RR_DRL, OUT_RR_IND, OUT_RR_BRK,
  OUT_AUX_L,  OUT_AUX_R,
  OUT_COUNT  // = 12
};
struct OutputIntent { uint16_t on = 0; };   // one bit per OutputIndex
```

`IPwm` / `setChannel(id, duty)` becomes `IOutputs` / `setOutput(id, bool)`. The PCA9685 HAL is
replaced by a GPIO HAL. The interface is retained so host tests keep using a fake.

The bitmask is not merely compact: it lets a test assert the **whole** output state in one
comparison, so a test fails when an output nobody thought about is also energised. That is
exactly the bug class this design is exposed to — "did the DRL stay on through the flash?" — and
the previous four-colours-plus-duty struct made it easy to miss.

`LogicalState` is unchanged.

### 5.2 Behavior matrix

Run set. "flash" means alternating with **all** of that corner's wires dark.

| Condition | Energised |
|---|---|
| Default | 4× DRL |
| Left indicator | `FR_DRL`, `RR_DRL`; flash `FL_IND` + `RL_IND` |
| Right indicator | `FL_DRL`, `RL_DRL`; flash `FR_IND` + `RR_IND` |
| Hazards | flash all 4 `*_IND` |
| Brake | 4× DRL, `RL_BRK`, `RR_BRK` |
| Brake + left indicator | `FR_DRL`, `RR_DRL`, `RR_BRK`; flash `FL_IND` + `RL_IND` |
| Brake + right indicator | `FL_DRL`, `RL_DRL`, `RL_BRK`; flash `FR_IND` + `RR_IND` |
| Brake + hazards | flash all 4 `*_IND` |
| Run clear (parked) | indicators / hazards only; DRL off, brake ignored |

Priority is unchanged from the original design: **indicator/hazard → brake → DRL**.

### 5.3 Two rules that are forced, not chosen

**The same-side DRL is de-asserted while that indicator flashes.** ECE R48 requires a DRL to be
switched off or reduced while the direction indicator on the same side operates. In the previous
design this fell out of the colour matrix for free; with separate wires it is an explicit rule.
It also sidesteps an untestable unknown: energising a single-engine module's DRL and indicator
wires simultaneously has undefined behavior, and the part does not yet exist to test it on.

**On an indicating rear corner, both `*_DRL` and `*_BRK` are de-asserted.** Previously this was
a style choice ("indicator wins, goes fully dark"). It is now **forced by the hardware**: the
rear module ORs DRL and brake internally onto one light engine, so leaving either asserted would
keep the corner lit through the indicator's dark phase and destroy the flash contrast.

### 5.4 Flash timing

A tunable, `flashSource`, with three values:

| Value | Behavior |
|---|---|
| `auto` (**default**) | Mirror the CAN bit's edges. If the bit stays continuously true for more than **1.2 s** — longer than any legal flash period — it is a steady "indicator requested" flag rather than a flasher, so fall back to generating 340 ms. |
| `follow` | Always mirror the bit's edges. Note that on a bus whose indicator bit is a steady flag rather than a flasher, this holds the lamps continuously on — an override the user is choosing deliberately. |
| `generate` | Always generate the configured period (default 340 ms), as the original design did. |

Mirroring matters because added indicators are required to flash **in phase** with the vehicle's
own. `auto` reaches the right answer on an unknown bus without anyone having to stand behind the
bike; the explicit overrides exist because the user asked for the choice to be settable.

### 5.5 Auxiliary pods

`AUX_L` / `AUX_R` = `highBeam || spotLatch`, gated by Run.

The existing long-press-to-latch and auto-drop-on-low-beam logic survives unchanged; it now sets
a boolean instead of selecting a level.

**Deleted:** the day/night aux levels and the four-level aux ladder (daytime / low / high /
spot). Direct drive gives one brightness and there is no mechanism to synthesise more. If
`AUX_MODE` proves real (§9.1), a second state can be added then.

### 5.6 Config

Shrinks to **CAN mappings, blink period, spot hold threshold, `flashSource`**.

All appearance settings are deleted — colours, per-corner brightness, per-mode aux levels — and
with them the brightness half of the completed test-mode-and-brightness work. The web app's
**Appearance screen disappears**; Mapping (with CAN discovery), Tunables, Backup, Status and
test mode are unchanged.

---

## 6. Fail-safe and diagnostics

In priority order:

1. **Reset / boot** — all 12 outputs off, held there by the §3.2 pull-downs before firmware
   runs at all.
2. **CAN stale** (no frames for > 500 ms) — treat every logical input as false. Everything goes
   dark, which is correct: a quiet bus means the bike's own lamps are off too. A longer idle
   drops to deep sleep with EXT1 wake, unchanged from plan3.
   This is a distinct condition from §5.2's "Run clear" row, which keeps indicators and hazards
   live: Run-clear means *the bus is alive and reporting the bike parked*, whereas CAN-stale
   means there is no information at all. Whether the parked case is even reachable on the
   Experia is open item §9.3.5.
3. **Switch fault** (overcurrent latch-off reported by the part) — log, retry with backoff,
   surface on the Status screen. A shorted harness neither blows a fuse nor takes the controller
   down.
4. **Lamp-out**, where resolvable — **report only**, never alters behavior.

**Test mode becomes a harness-verification tool.** Walking the 12 outputs one at a time
energises exactly one wire per step, which confirms that every module and every function is on
the pin the design thinks it is, before the bike moves.

---

## 7. Testing

**Native (the primary correctness surface):**

- all nine rows of §5.2, with **whole-word** output assertions
- the R48 same-side DRL dropout (§5.3)
- the forced brake-off on an indicating rear corner (§5.3)
- spot latch set and auto-drop; Run gating
- all three `flashSource` modes, including the 1.2 s `auto` fallback edge
- CAN decode (table-driven) and config round-trip / corrupt-file fallback — both carried over
  unchanged

**Hardware gates** — the six from plan3 carry over as-is, being output-stage-agnostic, which is
why the toolchain was kept: density, silk-as-hard-gate, ground separation, via placement, zone
islands, plane width, plus `gen_pcb.py`'s own refusal to write a board with a short hand-route
clearance.

**Board authoring rules are unchanged:** the board and all sheets are **generated** from
`hardware/scripts/`, never hand-edited; `gen_pcb.py` is never run in the background; DRC runs
against `hardware/mccan.kicad_pcb` at its real path.

---

## 8. Migration

| | |
|---|---|
| **Reused** | `hardware/scripts/` generators and all six gates; the external router chain; CAN input layer; config + storage; web app bar one screen; `LogicalState`; the priority model |
| **Rewritten** | `OutputIntent`, `ChannelMap` → output map, `IPwm` → `IOutputs`, the PWM HAL → GPIO HAL, the behavior engine's output half, every schematic sheet, the whole board |
| **Deleted** | `color.h`; appearance config and the Appearance screen; the brightness half of test mode; the boost, RGB and sense hardware of §4.3; the thermal plate and gap pad |

**Git — corrected 2026-10-17 after measuring, and it changes the branch bases.**
`main` and `plan3-pcb-hardware` have **diverged** at merge-base `730beb8`. `main` is no longer
an ancestor of `plan3-pcb-hardware`: the test-mode-and-brightness work was cherry-picked onto
`main` and never reached the PCB branch, which leaves `main` roughly **1140 lines ahead on the
firmware** — `src/domain/test_mode.{h,cpp}`, `src/domain/gamma_table.h`, hue+level colour
editing, and the `test_color_level` and `test_web_protocol` suites.

Consequently the two halves of this redesign take **different parents**:

- **Firmware work branches off `main`**, because it must build on `test_mode.{h,cpp}` and the
  current `web_protocol`. Branching it off the PCB line would rewrite a stale firmware and
  silently discard the test-mode work this spec says to keep.
- **Board work branches off `plan3-pcb-hardware`**, to inherit `hardware/scripts/` and the six
  gates.

Both land on `main` by **cherry-pick, never merge**. The no-merge rule still holds, for the
original reason inverted: merging the PCB line into `main` would drag roughly 200 abandoned
board commits with it.

---

## 9. Open items

These are verification items, not assumptions. Each names who or what can settle it.

### 9.1 Blocking the output stage

1. **Plug C/D pinout on the Oxford pods** — conductor count, and what each pin sits at in run
   mode, in high-beam mode and across the dial's 5 stages. Settles whether `AUX_MODE` gets
   populated and whether direct drive loses the integrated DRL. **Needs the kit in hand.**
2. **Pod inrush** — measured, against the candidate dual-channel switch's current limit and
   capacitive-load rating (§4.4). **Needs the kit in hand.**

### 9.2 Blocking the signal modules

3. **Module part selection**, then confirm against its datasheet: inrush, whether the indicator
   wire expects a steady switched 12 V or a flasher-relay feed, and the per-mode power split.
4. **Is the rear brake brighter than the rear running light?** The stated 1.5 W-in-any-mode
   figure implies they are equal, which cannot be right for a stop lamp and would not meet
   type approval. Most likely 1.5 W is the maximum across modes. Changes nothing in this design
   — we switch a wire either way — but decides whether the install is legal.

### 9.3 Bike questions

5. **Is the Experia's CAN bus alive with the ignition off?** Decides whether parked hazards
   work at all. If the bus is dead, the bits never arrive and §5.2's "Run clear" row is
   unreachable however the board is powered.
6. The CAN-mapping open questions from the original firmware spec §9 (Run bit, day/night bit,
   `0x400` bit 16, bit-numbering convention) are **unchanged and still open**. Note that
   day/night no longer drives anything, so that one has dropped from blocking to cosmetic.
7. **Spot-latch auto-latch on high-beam-hold** — still deferred, still needs the bus states
   confirmable on the bike.

### 9.4 Inherited housekeeping

8. `plan3-pcb-hardware` carries **uncommitted regenerated gerbers** (extension-style files
   renamed to `.gbr`, including the three now-distinct GND planes). These must be committed or
   discarded before new board work starts.
9. The latent `gen_pcb.py` defect where In1/In3/In6 all carry the user-facing layer name "GND",
   which collapses three ground planes into one gerber filename, is **fixed by this redesign
   incidentally** — a 4-layer board has one internal ground plane. The underlying naming bug in
   the generator should still be fixed rather than outgrown.

---

## 10. Decisions taken, with reasoning

| Decision | Reasoning |
|---|---|
| Bought E-marked modules, not self-built | E-marking is a legal requirement for indicators in Europe and cannot be obtained for a hand-built assembly |
| **Bypass Oxford's harness, drive pods directly** | User's call, made against the stated alternative. Accepts the §9.1 pinout risk in exchange for the controller owning the pods |
| New spec + new board, **keep the toolchain** | The generators, six gates and routing pipeline took most of plan3 to get right and are output-stage-agnostic. The board geometry is abandoned; the machinery that produced it is not |
| MCU stays classic ESP32-WROOM-32E-N8 | The constraint that justified it is gone, but so is any reason to change; a new pin map would cost a full retest for nothing |
| Multi-channel smart high-side switches | Protection, thermal shutdown and open-load detection in silicon, replacing plan3's hand-built twelve-shunt-plus-mux sense stage |
| Lamp-out is a **nice-to-have** | Must not drive part selection or block the design; report-only so it cannot become a failure mode |
| `flashSource` is a config switch, default `auto` | User asked for the choice to be settable; `auto` still reaches the right answer on an unknown bus without intervention |
| 4 layers, no thermal plate | ~1.2 W board dissipation does not justify either the eighth layer or a machined base |
