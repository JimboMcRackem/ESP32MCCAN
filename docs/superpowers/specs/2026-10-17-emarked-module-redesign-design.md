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
| Feed A | 2 | aux circuit +, − — logic, the ten signal channels, `AUX_L` |
| Feed B | 2 | aux circuit +, − — `AUX_R` only (§4.1.1) |

### 3.2 Boot safety

**A floating or strapping-pin GPIO at reset must not light a lamp.** Every switch input carries
a hard pull-down, and the chosen parts must be off with their input open. This constrains part
selection and is not negotiable: an indicator that lights itself at every reset is a safety
defect.

---

## 4. Hardware architecture

```
 FEED A --[4 A]--+   1 of 2 available aux circuits (5 A each). 2.77 A @ 12 V
                 v
       +------------------+
       | INPUT PROTECTION |  LTC4380 + 2 FETs, rev. polarity + overcurrent
       | 24 V TVS, pi+CM  |
       +--------+---------+
             VBAT_A (~12 V)
        +--------+---------+------------------+
        v                  v                  v
 +-------------+   +-----------------+  +------------------+
 | 3V3 BUCK    |   | QUAD SMART HS   |  | SMART HS  AUX_L  |
 | +3V3_ALW    |   | x2 -> 10 ch     |  | limit 3.0-3.5 A: |
 | + 5V gated  |   | 125 mA each     |  | MUST trip before |
 +------+------+   +-----------------+  | feed A's 4 A fuse|
        |                  ^ 10 GPIO    +------------------+
        |     +------------+------------+        ^ 1 GPIO
        +---->| ESP32-WROOM-32E-N8      |--------+
              | 12 GPIO out, pulled dn  |
              | deep sleep <- EXT1 wake |
              +--+--------+----------+--+
                 | TWAI              | 1 GPIO
        +--------+-----+             v
        | TJA1042T/3   |     +------------------+
        | listen-only, |     | SMART HS  AUX_R  |
        | HW-enforced  |     +--------+---------+
        +------+-------+              ^ VBAT_B
               |                 +----+----+
               v                 | rev pol |
          CAN H / L              | 24V TVS |
                                 +----+----+
                                      ^
                       FEED B --[3 A]-+  2.17 A @ 12 V

 Two power domains. VBAT_A and VBAT_B are NEVER diode-OR'd: joining them puts
 both pods back through one 5 A fuse (see 4.1.1). Returns common at a single
 star point; pod L's 2.17 A return does not share copper with the logic pour.
 A third aux circuit exists but is occupied -- if freed, pod L moves to it and
 feed A drops to 0.60 A, so keep AUX_L's switch on its own domain island.
```

### 4.1 Load budget

| Load | Current @ 12 V |
|---|---|
| 2 × Oxford pod @ 26 W | 4.33 A |
| 4 × signal module @ 1.5 W | 0.50 A |
| Logic | ~0.10 A |
| **Total** | **~5.0 A** |

That total is for reference only: **it does not run on one feed.** The previous design's feed
was 7.0 A continuous / 7.8 A transient behind a 10 A panel fuse, and an earlier draft of this
section carried a 7.5 A board fuse on the same reasoning. Both are withdrawn — the Experia
supplies 5 A aux circuits of which **two are available**, and this load exceeds any one of them
while fitting across two. §4.1.1 is the binding version of this budget.

**The Experia provides 5 A per aux circuit, and one circuit cannot carry this board.** The
feed is a 5 A fuse, not a 60 W power limit -- it passes 5 A at any voltage, which is 60 W at
12 V and 72 W at 14.4 V. That distinction decides which end of the voltage range is dangerous,
and the answer is the opposite of what a wattage limit would imply.

**The pods are constant-power, so their current rises as the voltage falls.** At 26 W a pod
draws 1.81 A at 14.4 V but 2.48 A at 10.5 V. The resistor-ballasted 2835 signal modules (2.1)
move the other way, drawing more as voltage climbs, but at ~6 W total they are a minor term
against the pods' 52 W. The pods therefore dominate, and the worst case for the fuse is a
**sagging battery, not charging voltage** -- cranking, or a long idle with the lights on.

Everything on one 5 A circuit, computed rather than estimated:

| Condition | Pods | Signals | Logic | Total | % of 5 A | % of derated 3.75 A |
|---|---|---|---|---|---|---|
| 14.4 V charging | 3.61 A | ~0.70 A | 0.08 A | 4.39 A | 88% | 117% |
| 12.0 V nominal | 4.33 A | 0.50 A | 0.10 A | **4.93 A** | **99%** | **132%** |
| 10.5 V sag | 4.95 A | ~0.38 A | 0.11 A | **5.44 A** | **109%** | **145%** |

A 5 A fuse wants no more than 75% of its rating continuously, so 3.75 A is the usable figure.
This load is 117-145% of that and crosses the absolute rating outright below about 11.5 V. It
is not a tight fit to be managed; it does not fit. Note too that the **pods alone** need = 10.4 V
to stay under 5 A and = 13.9 V to stay inside the derated 3.75 A, so a circuit dedicated to both
pods together is no answer either.

### 4.1.1 Two feeds: pod R alone, everything else together

The Experia has three 5 A aux circuits but **one is already in use, so two are available.** Two
is the minimum this load needs, and it only works in one arrangement: both pods together draw
4.33 A at 12 V and 4.95 A at 10.5 V, so a circuit dedicated to the pair is no better than a
single feed. One pod has to ride with the logic and signals.

| Condition | Feed A: pod L + signals + logic | Feed B: pod R |
|---|---|---|
| 14.4 V charging | 2.59 A (52% / 69% derated) | 1.81 A (36%) |
| 12.0 V nominal | 2.77 A (55% / 74% derated) | 2.17 A (43%) |
| 10.5 V sag | 2.97 A (59% / 79% derated) | 2.48 A (50%) |

Worst case is 59% of a circuit's absolute rating and 79% of the 3.75 A it carries continuously.
Fuse each feed below its circuit, at 125% of its own worst-case load: **4 A on feed A** (74% of
the fuse at 2.97 A) and **3 A on feed B**. A board fuse rated above the upstream 5 A could never
act, since the bike's fuse would always trip first.

**The fault-containment problem, and where it is solved.** Sharing feed A between a pod and the
logic rail means a pod fault that blew feed A's fuse would take the controller and every signal
lamp with it -- the rider would lose indicators because an auxiliary light failed. With only two
circuits available this cannot be solved by splitting, so **it moves into part selection:**

> **The `AUX_L` channel's smart high-side switch must current-limit and latch off below feed A's
> 4 A fuse rating.** The pod draws 2.48 A at worst, so the switch's limit belongs between those
> two figures -- roughly 3.0-3.5 A -- and its I2t must beat a 4 A blade fuse comfortably. A pod
> short is then contained by the switch, which the firmware can report (§6.3), and the fuse never
> sees it. This is a hard requirement on the part, not a preference.

What remains uncontainable is a fault *upstream* of that switch -- a short on feed A's own copper,
or the switch failing closed -- which the fuse must clear and which does take the logic rail down.
That residue is unavoidable with two circuits and is accepted.

**Consequences for the board:**

- **Two feeds.** §3.1's harness grows from 2 pins to 4. Feed A takes the full §4.2 protection
  chain -- LTC4380 + FETs, 24 V TVS, pi + common-mode filter, 3V3 buck, gated +5V -- because it
  feeds the logic rail. Feed B powers the `AUX_R` switch alone and needs reverse-polarity
  protection and a 24 V TVS, but no buck, no filter and no LTC4380: its switch already provides
  the current limit and thermal protection on that channel.
- **Never diode-OR the feeds.** Joining them puts both pods' current back through one fuse and
  undoes the split entirely.
- **The returns common at one star point, and pod L's return never shares copper with the logic
  reference.** Both circuits return to battery negative, so a single-point star ground at the
  board is correct and necessary -- the switch channels need the MCU's reference. But pod L's
  2.17 A return sits in the same domain as the logic ground, so routing it through the logic pour
  would modulate the MCU's reference. This is the ground-separation constraint the board's gates
  already check by counting connections between pours, and on feed A it is now load-bearing
  rather than routine.
- **Pod inrush is worse on feed A than feed B**, because feed A's surge lands on top of 0.60 A of
  signals and logic rather than on an idle circuit. §4.4's inrush measurement should be taken
  against feed A's budget, not a bare pod's.
- **The firmware is unaffected.** `AUX_L` and `AUX_R` are already separate channels carrying the
  same value (§3, §5.5), so the split needs no behavioural change -- only that the two channels'
  switches sit in different power domains, which is a layout constraint rather than a logical one.

**If the occupied third circuit is ever freed**, moving pod L onto it restores the fault
containment described above and drops feed A to 0.60 A. The board should therefore keep pod L's
switch on its own power domain island, so that change is a harness change and not a respin.

**Still to confirm on the bike** (§9.3.4a): whether the two available circuits are independently
fused or share a feed upstream of their individual 5 A fuses, and whether either is switched with
the ignition rather than permanently live. The second decides whether the quiescent budget matters
at all: if feed A dies with the ignition, the board is simply off when the bike is off and §4.2's
deep-sleep path stops being load-bearing.

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
   **Confirmed on the bike: CAN is off when the bike is off.** So a dead bus is not an ambiguous
   signal to be interpreted — it *is* the off state, and the two consequences are load-bearing.
   First, bus activity is a sufficient wake source on its own: the board needs no separate
   ignition sense, no accessory-line sense, and no voltage threshold to decide whether the bike
   is awake, which is what makes the plan3 EXT1 scheme correct here rather than merely
   convenient. Second, stale-means-dark is a fail-safe with no false-positive cost — there is no
   legitimate riding condition in which the bus falls quiet for 500 ms while the bike expects
   lamps lit, so the rule can be unconditional and needs no grace period beyond the threshold
   itself. A stale bus is therefore not a fault to report; it is the normal resting state, and
   §6.3's fault reporting must not treat it as an error condition.
   This is a distinct condition from §5.2's "Run clear" row, which keeps indicators and hazards
   live: Run-clear means *the bus is alive and reporting the bike parked*, whereas CAN-stale
   means there is no information at all. The CAN-off-with-bike-off fact narrows open item §9.3.5
   without closing it: it rules out any always-on-bus reading of Run-clear, so the row is
   reachable only in a key-on-but-not-ready-to-ride state, if the Experia has one. Confirm on
   the bike whether such a state exists and what Run reads in it.
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

4a. ~~**How many aux circuits does the Experia provide?**~~ **ANSWERED: three at 5 A each, but
   one is already in use — two are available.** §4.1.1 therefore puts pod R on its own feed and
   everything else, pod L included, on the other; the fault containment a third circuit would
   have bought moves into the `AUX_L` switch's current limit instead. **Still open:** whether the three are independently fused or share a feed upstream of their individual
   5 A fuses, and whether any is switched with the ignition rather than permanently live. The
   second question decides whether the quiescent budget matters at all: if the logic feed dies
   with the ignition, the board is off whenever the bike is off and §4.2's deep-sleep path stops
   being load-bearing.

5. ~~**Is the Experia's CAN bus alive with the ignition off?**~~ **ANSWERED: it is not — CAN is
   off when the bike is off.** So bus activity alone is a sufficient wake source (no ignition
   sense, no voltage threshold), and stale-means-dark has no false-positive cost, which is why
   §6.2 can apply it unconditionally and §6.3 must not report a stale bus as a fault. It does
   not fully settle parked hazards: §5.2's "Run clear" row is now reachable only in a
   key-on-but-not-ready-to-ride state, if the Experia has one. **Still to check:** whether such
   a state exists and what the Run bit reads in it.
6. The CAN-mapping open questions from the original firmware spec §9 (Run bit, day/night bit,
   `0x400` bit 16, bit-numbering convention) are **unchanged and still open**. Note that
   day/night no longer drives anything, so that one has dropped from blocking to cosmetic.
7. **Spot-latch auto-latch on high-beam-hold** — still deferred, still needs the bus states
   confirmable on the bike.

### 9.4 Inherited housekeeping

8. ~~`plan3-pcb-hardware` carries **uncommitted regenerated gerbers**~~ **RESOLVED: parked in
   `git stash`** (labelled "plan3 gerber regeneration ... parked by SDD Task 0"). `git stash pop`
   on the plan3 line recovers them; nothing was committed, because that board is being
   redesigned from scratch regardless.
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
