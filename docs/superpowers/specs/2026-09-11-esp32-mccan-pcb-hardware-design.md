# ESP32 MCCAN — PCB / Hardware Design

**Status:** Design approved (2026-09-11)
**Scope:** Fab-ready custom PCB for the ESP32 MCCAN lighting controller — schematic, layout,
BOM — plus the enclosure, connector and harness requirements it depends on.
**Out of scope:** Firmware implementation (creates its own plans — see §12), harness
manufacture, detailed enclosure machining drawings.

**Depends on:** `2026-07-29-esp32-mccan-lighting-firmware-design.md` (§7 deferred the PWM
path, automotive power and connector decisions to this session).

---

## 1. Purpose and context

Plan 1 (core firmware) and Plan 2 (connectivity + config web app) are complete and merged.
The firmware currently runs on a development board. This spec defines the production
hardware it will ship on.

The firmware boundary is already fixed and tested, and constrains this design rather than
the reverse:

- `IPwm::setDuty(uint8_t channel, uint8_t duty)` — 8-bit duty, 14 channels
- `ChannelIndex` fixes channel order: 0–2 front-left RGB, 3–5 front-right, 6–8 rear-left,
  9–11 rear-right, 12–13 Denali A/B
- TWAI CAN, listen-only, assumed 500 kbps
- SoftAP + HTTP + WebSocket config app served from LittleFS

**Intent:** one unit for the author's Energica Experia now, designed with the rigor to
become a product later — manufacturability, testability, diagnosability and eventual EMC
compliance considered from the start.

---

## 2. Load definition and power budget

### 2.1 Loads

| Load | Type | Rail | Notes |
|---|---|---|---|
| 4 × RGB COB string | **24 V constant-voltage**, 4-wire common anode | 24 V | **BTF-LIGHTING COB RGB, 840 LED/m, 24 V, IP66.** ~6 cm per corner (12 cm if 6 proves too dim) |
| 2 × Denali aux light | Self-contained 12 V units, internal drivers | 12 V | Driven identically |

The RGB strings are constant-voltage with internal series resistors — **not** constant-current
emitters. This is why the output stage is switches rather than LED drivers (§5.1).

Common anode forces **low-side** switching on R/G/B. The Denali units are switched
**high-side**, so their return is the shared ground in their connector (§9.1).

### 2.2 Budget

Supply is **ONE** Experia peripheral connector rated **10 A** (decided 2026-09-12 — see below).

**Confirmed load: Denali D4 2.0 TriOptic** — four 10 W CREE XPL HI LEDs per pod, **80 W / 6.6 A
for the pair**, i.e. **40 W per light**. This is a measured manufacturer figure, not an
assumption.

Because the loads never coincide (§2.4), the budget is **per operating mode**, not a sum:

| Mode | RGB via boost @92% | Denali | Logic | **Feed current** | Loading on 10 A |
|---|---|---|---|---|---|
| **Daytime** | 9.6 W → 0.87 A | off | 0.3 A | **1.2 A** | **12%** |
| **Night** | ~2 W → 0.2 A | 80 W → 6.6 A | 0.3 A | **7.0 A** | **70%** |
| *Flash-to-pass in daylight (seconds)* | 0.87 A | 6.6 A | 0.3 A | *7.8 A* | *78%* |

> **REVISED 2026-09-13 — the RGB load was overstated by roughly 4×.** The design assumed
> 20 W/m × 0.5 m = 10 W per corner. The actual strip is **~6 cm per corner** (12 cm if 6 proves too
> dim), so on a conservative 20 W/m basis a corner draws **2.4 W**, and all four **9.6 W** — against
> the 40 W previously budgeted. Every downstream figure moves with it: the boost design point, the
> feed current, the thermal budget and the plate size. **The flash-to-pass transient no longer
> exceeds the feed at all** (7.8 A, 78%), so the 105% overload case is gone.

**Night remains the governing case at 70%**, comfortably inside good practice for a sustained
automotive load and no longer the tight spot it was at 78%. It is now dominated almost entirely by
the Denali pair; the RGB contribution is negligible.

**If the fuse ever nuisance-blows,** the escape hatch needs no hardware: the Denali maximum level is
already a web-app tunable, and 90% of full gives 6.0 A instead of 6.6 A, bringing the night total to
7.2 A (72%).

**Why one feed suffices — the history matters here, because this reversed twice.** An early revision
assumed Denali ≤ 25 W each and specified one feed. The confirmed D4 2.0 figure of 40 W each then made
the *arithmetic sum* 10.5 A, which exceeds one connector, so the design moved to two feeds with a
domain split. **What was missing was how the bike is actually ridden** (§2.4, confirmed by the owner
2026-09-12): daytime runs the corners with the Denali lights off, night runs the Denali lights with
the front DRLs off. The 10.5 A sum is an **envelope that no steady state occupies.** The real maximum
is the night mode's **7.8 A**, which one 10 A feed carries. **Decision 2026-09-12: single feed.**

**What the single feed gives up.** The domain split's only real benefit was that a Feed B failure
left the RGB corners (and therefore the indicators) alive. Note it never protected the indicators
against a Feed A failure — they were always on Feed A — so the loss is narrower than it first looks:
a feed fault now also takes the Denali lights. Against that, there is one less connector, one less
fuse and one less cable run to fail, which on a motorcycle harness is a real reliability gain.

**No provision for a second feed is carried on the board** (§4.4, amended 2026-09-18). An earlier
revision retained the second feed's footprints unpopulated; that retention was dropped once the
design moved on — J1 became a **3-way** carrying `IGN_IN` for the topology-B battery-feed case
(§8.1a), which is a better and already-built answer to "what if the supply arrangement changes",
and the board's area is thermally constrained by the ≥ 150 cm² heat-spreader plate (§9.4).
Restoring the domain split would need a respin.

**The RGB figure remains assumed, not measured** — 20 W/m × 0.5 m × 4 strings. Re-verify when the
strips are measured. The daytime load is only 39% of the feed, so a higher real figure is absorbed
comfortably; note it is **night** that sits at 78%, and night runs the corners at a fraction of full
white.

### 2.3 Per-channel current

| | Value |
|---|---|
| Per RGB string, all three colors full (white) | **0.10 A** (was 0.42 A) |
| **Per RGB channel** (R, G or B) | **~33 mA** (was ~140 mA) |
| Per Denali channel | **3.3 A** (D4 2.0 at 40 W) |

### 2.4 Operating modes — the loads never all coincide

**Confirmed by the owner 2026-09-12.** This is load-defining and it governs the thermal design:

| Mode | Denali | RGB corners | Feed current | Board dissipation |
|---|---|---|---|---|
| **Daytime** | **OFF** | All four on (white DRL) | **1.2 A** | ~1.4 W |
| **Night** | On (80 W) | Fronts **off**, indicating only; rears on | **7.0 A** | **~1.9 W — governs** |

**Consequences:**

- **"Full-white RGB *and* both Denali at maximum" is not a reachable steady state.** It occurs only
  during a flash-to-pass in daylight — seconds at a time, absorbed by thermal mass.
- **The thermal worst case is now NIGHT, not daytime (revised 2026-09-13).** Once the RGB load fell
  from 40 W to 9.6 W the boost stopped dominating, and the **P-FET conduction loss at the Denali
  pair 7.0 A became the largest single term** (0.98 W of a ~1.9 W total). Daytime is now the
  *lighter* case at ~1.4 W. This reverses the earlier conclusion, which held only while the RGB load
  was believed to be 4x larger.
- **The single feed is now comfortable rather than marginal.** Daytime draws 1.2 A (12%); night
  7.0 A (70%). Even the flash-to-pass transient, at 7.8 A, no longer exceeds the feed — the 105%
  overload case that drove the fuse discussion has disappeared entirely.
- **C4 (the PTC) is confirmed as a real sustained condition, not a corner case:** daytime runs all
  four corners at full white continuously, so each string holds 0.42 A for hours at the enclosure's
  hot internal temperature. That is precisely the case the original 0.5 A PTC would have tripped on.

**Design basis:** 20 W/m × 12 cm = 2.4 W per corner. This deliberately covers the worst plausible
case — the strip's rating should be confirmed from the reel (12–20 W/m is the plausible band for
24 V COB RGB) and 12 cm is the longer of the two lengths under consideration. At 6 cm and 12 W/m the
figures are a quarter of this.

The per-channel current is now **33 mA**, which makes the discrete-FET output stage thermally
irrelevant — but it **breaks the sense-chain sizing** and is why §5.1's shunt changed from 1 Ω to
10 Ω.

---

## 3. Architecture

```
 SINGLE FEED ──[10 A panel fuse]──┐      (2nd feed: footprints only, DNP — §4.4)
 12 V: 1.2 A day / 7.0 A night     ▼
                   ┌──────────────────┐
                   │ INPUT PROTECTION │
                   │ LTC4380 + 2 FETs │
                   │ rev.pol + o/c    │
                   │ 24 V TVS, pi+CM  │
                   └────────┬─────────┘
                         VBAT (~12 V)
                ┌───────────┴──┬──────────────────────┐
                ▼              ▼                        ▼
    ┌───────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
    │ 3V3 BUCK +3V3_ALW │   │ 24 V SYNC BOOST      │   │ DUAL SMART HIGH-SIDE │
    │ + 5V REG (gated)  │   │ LM51571-Q1, int. sw  │   │ PROFET, 1x IS + DSEL │
    │ ~1 A              │   │ enable-gated, 12 W   │   │ enable-gated         │
    └─────┬─────────────┘   └──────────┬───────────┘   └──────────┬───────────┘
          │                            │                          │
          │                  +24 V, 4× PTC per string      2× switched 12 V
          │                            ▼                          ▼
          │                  4× RGB COB STRING             2× DENALI
          │                            │
          │                  12× R/G/B returns
          │                            ▼
          │              ┌──────────────────────────────┐
          │              │ 12× DISCRETE N-MOSFET        │
          │              │ + 1Ω shunt in each source    │
          │              └──────┬───────────────┬───────┘
          │                12× PWM        12× sense
          │                     │                ▼
          │                     │         ┌──────────────┐
          │                     │         │ 16:1 ANALOG  │
          │                     │         │ MUX  (S0-S3) │
          │                     │         └──────┬───────┘
          │              ┌──────┴───────┐        │ RGB_ISNS
          ├─────────────▶│ PCA9685      │        │ → ADC1_CH4
          │              │ ch 0-11, I2C │        │
          │              └──────┬───────┘        │
          │                     │                │
          │              ┌──────┴────────────────┴───────┐
          ├─────────────▶│ ESP32-WROOM-32E-N8            │
          │              │ LEDC ch → Denali PWM          │
          │              │ deep sleep ← EXT1 wake        │
          │              └──────┬────────────────────────┘
          │                     │ TWAI
          │              ┌──────┴────────────────┐
          └─────────────▶│ TJA1042T/3            │──▶ CAN H / L
                         │ VIO=+3V3_ALW (wake)   │    (listen-only, HW-enforced)
                         │ VCC=+5V (gated, normal)│
                         └───────────────────────┘
```

**FOUR power domains, deliberately separated** (updated 2026-09-12 — an earlier revision said three
and predated the mandatory 5 V rail):

1. **Always-on 3.3 V (`+3V3_ALW`)** — survives deep sleep. Powers **only the ESP32 and the CAN
   transceiver's VIO**, which is all that bus-activity wake detection requires (§6).
2. **Switched 3.3 V (`+3V3_SW`)** — gated by `EN_3V3SW`. Powers the **PCA9685 and the ADG706 mux**,
   both unpowered in sleep.
3. **Switched 5 V (`+5V`)** — gated by the **same enable**, no extra GPIO. Supplies the TJA1042's
   **VCC** for normal mode only; off in sleep (§6, §8.2).
4. **Enable-gated 24 V boost (`+24V`)** — `EN_BOOST`. Carries only the RGB load, so it is sized at
   60 W rather than the full system power.

Plus **raw protected 12 V (`VBAT`)** straight to the Denali high-side switches, so their 6.6 A never
passes through a converter.

In deep sleep only **two devices** are powered — the ESP32 and the transceiver's VIO domain — which is
what makes the sub-200 µA budget in §8.2 achievable.

**Which rail feeds what, stated explicitly** because §8.2's roll-up depends on it: PCA9685 and ADG706
on `+3V3_SW`; TJA1042 VIO on `+3V3_ALW` and its VCC on `+5V`; ESP32 on `+3V3_ALW`.

---

## 4. Input stage

### 4.1 Fusing

**REVISED 2026-09-19: a BOARD-MOUNTED eFUSE, not a panel-mount blade holder.** Board-mount,
resettable, no consumable, and it removes a panel penetration. Requirements — and the reason a
polyfuse cannot do this job — are in `hardware/docs/part-selection.md`, "F1 — eFuse
requirements". **No part is selected yet.**

> **STALE FIGURES CORRECTED 2026-09-19.** This section carried **7.8 A night / 10.5 A
> flash-to-pass** and reasoned from a "105% overload". Those are pre-correction numbers.
> §2.2 and §2.4 have read **7.0 A / 7.8 A** since 2026-09-13, and §2.2 states plainly that
> "the flash-to-pass transient no longer exceeds the feed at all (7.8 A, 78%), so the 105%
> overload case is gone." The figures below are §2.2's. This matters: the stale pair would
> have forced the eFuse limit above the connector's 10 A rating, and the real pair does not.

| | Current | % of a 10 A feed | Note |
|---|---|---|---|
| Daytime | **1.2 A** | 12% | |
| **Night — the governing case** | **7.0 A** | **70%** | Sets the continuous rating |
| Flash-to-pass, seconds | **7.8 A** | 78% | Sets the current-limit setpoint |

**The limit sits at 9–10 A**: above the 7.8 A flash-to-pass transient with ~15% margin, and
**at or below the peripheral connector's 10 A rating** — so §4.1's original constraint, that
a fuse must not exceed the connector rating, still holds. Nothing has to be traded.

**But the setpoint cannot simply be 7.8 A or lower**, and the reason is worth keeping. The
blade fuse tolerated a transient *above* its own rating purely because it is **slow** —
"blade fuses need roughly 135% sustained for minutes". An eFuse current-limits in
microseconds and has no such inertia, so a setpoint at or under the transient would **chop
flash-to-pass**: a functional regression that no ERC, DRC or netlist check would reveal, and
which would present as "the high beam flickers when I flash." Discrimination between the
transient and a genuine fault belongs to the eFuse's **programmable fault timer**, not to its
current limit.

**Auto-retry, not latch-off, and this is not a preference.** F1 is the first device after the
connector, so the MCU is powered *downstream of it*. If the eFuse latched, the MCU would be
unpowered and could not command a reset. Under topology A the latch would clear on the next
ignition cycle; under topology B (permanent battery) it would be permanent until someone
disconnected the battery.

**Documented residual risk (unchanged, accepted by the author):** a fuse protects the *cable
upstream of itself*. F1 on the board leaves the battery-to-box run unprotected, so a
chafe-through along that run is not interrupted. Partially offset by a short run,
abrasion-resistant loom, routing clear of chafe points and a booted ring terminal. A
battery-end inline fuse can be added later with **no board change**.

**Open item (unchanged):** if the Experia's peripheral outlet proves to be individually fused
by the bike, ask whether F1 is redundant. Verify on the vehicle.

### 4.2 Reverse polarity AND overcurrent — one pass element, LTC4380 + back-to-back N-FETs

**REWRITTEN 2026-09-19. This section previously specified a lone P-FET doing reverse polarity,
with §4.1's fuse as a separate part. Those two functions are now merged into one conduction
path.** The reasoning, the routes rejected and the thermal arithmetic are in
`hardware/docs/part-selection.md` ("F1 — eFuse requirements" onward).

**Q1 (SQJ461EP P-FET) and the blade fuse are both deleted.** In their place:

| Ref | Part | Role |
|---|---|---|
| **U10** | **ADI LTC4380HMS-2#TRPBF** | Surge stopper + overcurrent controller. Auto-retry (`-2`), MSOP-10, H-grade −40…125 °C |
| **Q10** | **Infineon IPT008N06NM5LF** | Pass FET, **input side** — drain to the feed |
| **Q11** | **Infineon IPT008N06NM5LF** | Pass FET, **output side** — drain to the load |
| **R88** | **5.6 mΩ, 1%, ≥ 1 W** | Current-limit sense. 4-terminal (Kelvin) part preferred |
| **R89** | R<sub>DRN</sub> — **[TO CALCULATE]** | Drain-sense for the SOA multiplier |
| **R90** | **10 Ω** | Gate series damping |
| **C49** | C<sub>TMR</sub> — **[TO CALCULATE]** | Fault timer |
| **C50** | **100 nF** | V<sub>CC</sub> decoupling |

#### Why one element does both, and why that is cheaper than it sounds

A blade fuse plus a P-FET meant **two** conduction losses. The P-FET alone was **0.78 W at 7.0 A**,
the largest single term on the board (§9.4), and bolting any eFuse in front of it only added more —
the assessed TPS1686 would have taken the board to **70 °C** against a 65 °C target.

The LTC4380 drives **back-to-back** FETs, so the same silicon blocks reverse current *and*
limits forward current. With the IPT008N06NM5LF at **0.8 mΩ max** the pair contributes
**0.12 W hot**:

| | R | Loss at 7.0 A |
|---|---|---|
| Q10 + Q11, hot (0.8 mΩ max, ×1.5 at 125 °C) | 2.4 mΩ | 0.12 W |
| R88 sense | 5.6 mΩ | **0.27 W** |
| **Total** | **8.0 mΩ** | **0.39 W** |
| *Replaced: Q1 P-FET* | *16 mΩ* | *0.78 W* |

**Night falls from 2.70 W to 2.31 W and the board lands at ~60 °C — three degrees cooler than the
present design, while gaining protection it does not currently have.**

> **R88 is now 69% of the pass-element loss.** The FETs have become negligible and the sense
> resistor is the dominant term. It needs its own copper area and a **Kelvin connection**; the
> datasheet's layout note is explicit that "1 oz copper exhibits a sheet resistance of about
> 530 µΩ/square. Small resistances can cause large errors in high current applications." **R88 is
> not on the heat-spreader plate** and must be thermally provisioned separately.

#### Topology — COMMON SOURCE, drains outward. This is the error ERC cannot catch.

```
   FEED_P ──┬── D:Q10 :S ──┬── S: Q11 :D ──┬── R88 ──┬── VBAT_PROT
            │              │               │  5.6mΩ  │
            │            (MID)             │         │
            │              │             SNS│      OUT│
          R89              │                │         │
        (R_DRN)            │                │         │
            │        R90 ──┴── both gates   │         │
            │        10Ω        tied        │         │
          DRN        GATE ──────┘         SNS       OUT
                         U10 LTC4380
          VCC ── C50 100nF        SEL ── GND    TMR ── C49 ── GND
          ON  ── open (internal pull-up)        GND ── GND
          FLT ── open drain, see below
```

**Sources tied together in the middle, drains facing outward.** Both body diodes then point
*inward* to the mid-node, so:

- **Forward:** Q10's body diode (anode MID, cathode FEED) blocks FEED→MID, so forward current
  requires Q10's channel to be on — which it is in normal operation.
- **Reverse:** Q11's body diode (anode MID, cathode VBAT_PROT) blocks VBAT_PROT→MID. **That is
  the reverse-polarity block**, and it holds with the part off and unpowered.

**Common source is not a preference, it is forced by the single GATE pin.** The LTC4380 specifies
ΔV<sub>GATE</sub> as **GATE − OUT**, one driver for both devices. With the sources common and
both FETs on, MID ≈ OUT, so GATE − OUT is the true V<sub>GS</sub> for both. A **common-drain**
arrangement (sources outward) also blocks reverse, but puts the two sources at different
potentials, so one gate pin cannot drive both. **Do not "simplify" it that way.**

> **This is precisely the class of defect that got through twice already on this board** — the
> CM-choke pin numbering (Task 7) and the RGB-FET clamp path (F6). **ERC passes a back-to-back
> pair wired the wrong way round, DRC passes it, and the pad count matches either way.** The
> netlist must be read by hand after generation, specifically checking which terminal of Q10 and
> Q11 carries the shared MID node.

#### Component values, and what is not yet settled

**R88 = 5.6 mΩ** gives a **9.0 A nominal** limit (ΔV<sub>SNS</sub> = 50 mV typ). With the IC's
45–55 mV spread and a 1% resistor the real window is **8.0–10.0 A** — above §4.1's 7.8 A
flash-to-pass transient, at or below the connector's 10 A. **Both ends pass and neither has room
to spare**, so R88 must be 1% or better. Dissipation at the 9.9 A worst-case limit is **0.55 W**,
hence the ≥ 1 W rating.

> **R89 (R<sub>DRN</sub>) and C49 (C<sub>TMR</sub>) are [TO CALCULATE] and must be computed
> together.** They set how long the part rides through a fault before shutting off, scaled by
> actual FET stress: the DRN current and ΔV<sub>SNS</sub> are multiplied internally to produce
> the TMR current. **Getting them wrong fails in both directions** — too short nuisance-trips on
> inrush, too long violates the FETs' SOA. Constraints already known:
> - **R<sub>DRN</sub> must limit I<sub>DRN</sub> to ≤ 1 mA at peak input** (datasheet, DRN pin).
>   At the SMBJ24A's 50.6 V worst case against a ~27 V clamped output that is **≥ 23.6 kΩ**.
> - **The timer must outlast inrush.** C3's 220 µF charging at the 9 A limit is
>   220 µF × 12 V / 9 A ≈ **0.29 ms**, plus downstream bulk.
> - **It must expire well inside the SOA.** At 12 V the 10 ms line allows ~50 A (~34 A derated to
>   a 65 °C case) against the 7 A clamp current, so 10 ms is comfortable — the FET is not the
>   binding side here.
>
> Work these from the datasheet's TMR section before the schematic is frozen. **Do not carry
> Figure 5's 220 nF across unexamined** — it belongs to a 5 A, 250 V design, not this one.

#### What is deliberately omitted from the datasheet's Figure 5

Figure 5 is an **overvoltage protector for a 250 V surge** and carries an auxiliary gate network
(Q3 2N3904, D3/D4 1N4148, R5 10 k, R6 240 k) plus a **68 V Zener on V<sub>CC</sub>**. **None of
that is carried over**, because our input cannot reach those voltages: §4.3's SMBJ24A clamps at
**38.9 V (10/1000 µs) / 50.6 V (8/20 µs)**, and the LTC4380's V<sub>CC</sub> is rated
**−60 to +80 V**. The Zener exists to keep V<sub>CC</sub> under 80 V during a 150–250 V event we
do not have.

> **CONFIRM BEFORE FREEZING.** This is a deliberate simplification of a vendor reference design,
> made from the voltage ratings. It has **not** been confirmed that the Q3/D4 network plays no
> role at more ordinary voltages — Figure 5 also routes M2's gate through it while M1's goes
> through R3, with a 1 MΩ bridging the two, which is more structure than a plain shared gate.
> **Re-read the Applications Information around Figure 5 before committing the schematic**, and
> if in doubt keep R90 and add the 1 MΩ bridge rather than dropping to a bare common gate.

#### Two things this buys that were not asked for

**`FLT` can reach the MCU.** It is an open-drain fault output. With a pull-up to `+3V3_SW` and a
spare GPIO, the board could report an overcurrent event rather than merely surviving it —
addressing §4.1's weakness that a hard fault kills the MCU before it can log anything. **Needs a
free GPIO confirmed against §7.3 before it is drawn.**

**Quiescent current is negligible.** 8 µA typ / 12 µA max operating, 6 µA in shutdown, against
§8.2's ~100 µA sleep budget. The P-FET it replaces was ~0 µA, so this costs ~12 µA of a budget
with room — and unlike the ideal-diode controllers rejected in the original §4.2 for drawing
"tens of microamps continuously", this one earns its keep by removing 0.39 W.

#### What is unchanged

**The residual risk in §4.1 still stands**: a fuse protects the cable *upstream* of itself, and
U10 sits on the board, so the battery-to-box run remains unprotected. Mitigations and the option
of a battery-end inline fuse are unchanged.

### 4.3 Transient protection — sized for an EV

The Experia has **no alternator**, so the classic ISO 7637-2 load-dump pulse from a collapsing
alternator field does not apply; the 12 V rail comes from a well-behaved DC-DC off the traction
pack. What remains is real but milder: inductive kick from relays and solenoids, and the
possibility of a jump start or charger on the rail.

- TVS clamp, **~24 V standoff** — survives a 24 V double-battery jump without conducting
- **All front-end parts rated ≥ 40 V**
- **Both switchers rated 40–60 V input**, so the clamp voltage can never exceed what is
  downstream
- Input **π filter and common-mode choke** — conducted-emissions suppression designed in, not
  retrofitted

**Front-end ordering (decided 2026-09-12), and it is not arbitrary:**

```
connector -> fuse -> reverse-polarity FET -> TVS -> CM choke -> pi filter -> bulk -> load
```

- **Fuse first**, so everything downstream including the choke is protected.
- **Reverse FET before the TVS, not after.** The SMBJ24A is *unidirectional*, so in reverse polarity
  it is simply a forward-biased diode: placed ahead of the FET, a reversed battery drives enormous
  current through it and destroys it. This ordering is mandatory, not preferential.
- **TVS before the choke.** Surge clamping degrades with series inductance between the entry point
  and the clamp — inductance causes the clamp voltage to overshoot. A choke is deliberately
  inductive, so putting it ahead of the TVS undermines the clamp.
- **Choke before the π filter.** The noise being blocked originates *inside* the board (the boost
  converter), so the choke must sit between the switcher and the harness. The π filter's capacitors
  belong downstream of it.

**The CM choke splits the ground net, and this is the part that gets broken.** Both the positive
conductor and the return pass through the choke, so the connector-side return (`GND_IN`) and the
board ground (`GND`) are **separate nets joined only through choke winding B**.

> **Nothing else may bridge `GND_IN` and `GND`** — no wire, no capacitor, and on the PCB no
> ground-plane copper (a layout constraint for §10, not only a schematic one).
>
> **The usual failure is capacitive, not a wire.** A decoupling capacitor from the upstream node to
> the downstream ground bridges winding A's input to winding B's output, giving high frequencies a
> path straight around the choke. The circuit then works perfectly and filters nothing — and **no ERC
> or DRC check will flag it.**

Consequently: the **TVS anode and U10's `GND` pin reference `GND_IN`** (the protection group must
reference the ground the surge actually arrives on, and **the controller must reference the return
the battery is connected to — it is what holds the pass FETs off under reverse polarity**), while
**everything from the π filter onward references `GND`**.

> **UPDATED 2026-09-19 with §4.2's rewrite.** This used to read "the P-FET gate resistor
> references `GND_IN`". R1 and the P-FET are deleted; **U10's ground pin inherits that
> requirement, and inherits it more strongly** — a gate resistor referencing the wrong return
> merely biased a FET badly, whereas a controller referencing the wrong return misjudges both the
> reverse-polarity decision and the sense voltage.

**Build option:** fit **either** the choke **or** two 0 Ω links that short its windings. Links give
the simple tied-ground case for the first prototype, while the footprint is present either way — so
fitting a real choke after EMI measurement needs no board revision. The footprint must be placed now
regardless, because adding it later is a layout change.

### 4.4 Single feed

**One** power connector with its own P-FET reverse-polarity stage, transient clamp and fuse
(§4.1). **Decided 2026-09-12**, superseding the dual-feed arrangement, once §2.4 established that the
loads never coincide. The connector is **3-way**, not 2-way — the third cavity carries `IGN_IN`
(§8.1a).

> **Amended 2026-09-18 (schematic review, F5).** This section previously required the second feed's
> footprints — connector position, P-FET stage and a Schottky OR pair — to be **retained unpopulated**
> so the domain split could be restored by stuffing parts rather than respinning. **That requirement
> is withdrawn, and the board carries no second-feed provision.** Three reasons:
>
> 1. **The load analysis has held through two reversals.** Night, the governing case, draws **7.0 A
>    of a 10 A feed**, and §2.4's operating modes are owner-confirmed rather than assumed. The
>    contingency the footprints insured against has not become more likely; it has become less so.
> 2. **The design already has a better answer.** J1 is now a 3-way carrying `IGN_IN` for the
>    topology-B battery-feed case (§8.1a). "What if the supply arrangement changes" is handled by a
>    populated pin, not by dormant copper.
> 3. **Board area is thermally constrained.** §9.4 requires a ≥ 150 cm² flat heat-spreader plate,
>    and the single-feed front end already carries L1 and L2 at the full 7.0 A. A second
>    high-current connector footprint and P-FET stage that will never be populated on the reference
>    bike costs area the thermal design needs.
>
> The **Schottky OR** likewise reduces to what is built: **D3, a single Schottky** feeding
> `VLOGIC_IN` from `VBAT`. There is no second diode and no `VBAT_B` net.
>
> The domain-split material below is **retained as design rationale only** — it records why the dual
> feed was retired and what restoring it would entail. **Restoring it requires a board respin.**

**Single-feed P-FET note:** one stage now carries the whole load, so at the 20 mΩ ceiling it
dissipates **0.30 W in daytime and 1.22 W at night** (§9.4). Night's higher figure does not govern
the thermal design, because night's total is only ~2.9 W against daytime's ~4.5 W.

---

**If a second feed were ever added** — which now requires a respin, see the amendment above — the
arrangement below would apply. It is a **domain split, not a parallel share:**

**Split by domain, never paralleled.** Paralleling two feeds divides current by path resistance
(wire gauge, length, contact resistance), giving something like 8 A / 4 A rather than 5 A / 5 A;
and ORing them through ideal diodes is worse still, since the slightly-higher-voltage feed
supplies nearly everything — that is source selection, not sharing, and one connector would sit
over its rating while the other idles. A domain split gives each feed a deterministic, bounded
load that cannot divide unevenly:

| Feed | Powers | Current | Ceiling | Margin on 10 A |
|---|---|---|---|---|
| A | Boost → 24 V → RGB, plus logic | 1.0 A | 1.4 A (boost at its full 12 W design point) | 90% nominal / **86% at the ceiling** |
| B | Denali D4 2.0 pair via PROFET | 6.6 A | 6.6 A (fixed load) | 34% |

**The Schottky OR on the logic rail** costs cents and means the MCU keeps power while *either*
feed lives — so it stays awake to report the fault rather than going dark silently. Feed A and
Feed B are interchangeable if mis-mated, since both are 12 V and both resulting loads stay under
10 A; no keying is needed between them.

**Failure behaviour:** losing Feed B extinguishes the Denali lights only. Losing Feed A
extinguishes the RGB corners, **including the indicators** — the firmware detects this via the
logic rail staying up and must report it prominently in the web app. A cross-tie allowing Feed B
to back up the RGB domain was considered and rejected as disproportionate; it would require a
~6 A switch and a firmware load-shedding state.

**Caveat, so the redundancy is not oversold:** both peripheral connectors almost certainly
originate from the same upstream circuit, so this protects against connector and wire faults,
not upstream failure.

---

## 5. Output stages

### 5.1 RGB — discrete low-side MOSFETs with per-channel current sense

**DECISION 2026-09-11 — supersedes the smart-switch design.** Task 2b datasheet verification
established that **ON-state open-load detection does not exist in the multichannel smart low-side
switch category.** TLE8110ED's diagnosis code `01` is defined verbatim as "Open Load in OFF-Mode";
its ON-mode codes cover only overload, short and overtemperature. Detection is a **VDS comparator**
(VDSol 2.00/2.60/3.20 V with a 50/90/150 mA injected pull-down), so there is **no load-current
threshold at all** — 0.14 A is unspecified rather than out of range. Two further rows failed:
short-to-battery and overtemperature share one 2-bit code, and standby current is 20 µA max at
85 °C with zero margin (60 µA at 150 °C, plus ~36 µA leakage).

Since the integrated parts were chosen *for* those diagnostics, and the OFF-state detection they do
offer is marginal anyway (the injected pull-down reaches 150 mA while a healthy channel sources only
~140 mA at the then-assumed current, and just 27 mA at the real one — so a working channel would read
as open), the RGB stage is now **12 discrete
logic-level N-MOSFETs plus a purpose-built diagnostic chain** that does what the ICs could not.

**Switching:** one logic-level N-channel MOSFET per channel, gate driven directly from a PCA9685
output. Requirements: **Vds ≥ 40 V** (the 24 V rail plus transients), **Id ≥ 1 A**, and
the output-characteristic curve showing **Id ≥ 0.5 A at Vgs ≤ 3.3 V**.

> **No Vgs(th) threshold is imposed (corrected 2026-09-12).** An earlier revision of this paragraph
> required `Vgs(th) max ≤ 2.0 V`. That gate was an arbitrary proxy and it **rejects the selected
> PMV60ENEA** (Vgs(th) max 2.5 V), which at 3.3 V drive still has 0.8 V of overdrive — plainly enough
> at 0.14 A. `part-selection.md` §1a withdrew it by name; this paragraph now agrees.

> **Note on gate drive (2026-09-11).** An earlier revision demanded the FET be "fully enhanced at
> 3.3 V". No MOSFET in this class publishes Rds(on) below 4.5 V Vgs, and the requirement was wrong
> anyway: at **0.14 A** (and far more so at the real **26.7 mA**), even a pessimistic 1 Ω Rds(on)
> costs 140 mV and 20 mW on a rail with 24 V of headroom — and the design **deliberately adds a sense
> resistor in the same leg** (now 10 Ω), so a fraction
> of an ohm from the FET is the same order as a part chosen on purpose. The strip's internal
> resistors (~171 Ω) set the current, so 1–2 Ω of series resistance shifts it under 1%. Nothing here
> needs low Rds: not heat, not headroom, not current accuracy, not switching speed.

**Diagnostics:** a **10 Ω sense resistor in each FET's source leg**, all 12 sense nodes feeding a
**16-channel analog multiplexer** whose output drives one ESP32 **ADC1** input.

> **SHUNT RESIZED 1 Ω → 10 Ω, 2026-09-13 — at 1 Ω the diagnostics would not have worked.** The chain
> was sized for 140 mA per channel. The real strip draws **10–33 mA**, which across 1 Ω is
> **10–33 mV** — down among the ADC's offset and noise, where "open" and "working" are
> indistinguishable. The feature would have appeared to function and silently mis-classified.
> At 10 Ω the signal is **100–330 mV**, back in the same working range the design was validated for.
> Dissipation *falls* to **1–11 mW** per channel (from 20 mW), so the ≥1 W 2512 requirement is
> withdrawn — an 0805 at 1% suffices.

- Sense is **ground-referenced** (low-side), so no differential or high-side amplifier is needed
- 10 Ω × 33 mA = **330 mV** at full channel current (100 mV at the 6 cm / 12 W/m end); **0.13 W**
  total across 12 channels at full white
- ADC at **0 dB attenuation** (0–1.1 V range), so 140 mV is ~13% of full scale — ample to separate
  open (≈0 mV), working (≈140 mV) and shorted (saturated)
- 10 Ω chosen to restore the validated ~100–330 mV window at the real load, at negligible power
- **The mux must be specified for 3.3 V operation** — ADG706-class. Note its real figures at the rail
  actually used: **2.7–5.5 V supply, RON 6 Ω typ / 11–12 Ω max at 3 V** (the often-quoted ~2.5 Ω is the
  5 V column). The buffer capacitor below makes the difference immaterial.
  CD74HC4067 is excluded: HC on-resistance rises steeply below 4.5 V and is uncharacterised at 3.3 V
- **A ~10 nF buffer capacitor at the ADC input** supplies the SAR sample-and-hold charge locally, so
  mux on-resistance cannot corrupt the reading. Belt and braces with the part choice above.
- **SETTLING TIME IS A REAL CONSTRAINT (added 2026-09-12).** The I15 series resistor (10 kΩ) and this
  buffer capacitor form an RC: **τ = 100 µs**, so a step must settle for **≥ 500 µs (5τ)** before the
  ADC samples. This — not the mux's own ~45 ns transition — is what bounds the sweep. Sample a channel
  1 τ after a 140 mV neighbour and it still carries ~51 mV of residual, which sits **inside** the band
  between "open (≈0 mV)" and "working (≈140 mV)" and would misclassify. The cap is deliberately 10 nF
  rather than 100 nF for this reason: at 100 nF, τ would be 1 ms and the whole 12-channel sweep would
  need tens of milliseconds. **Firmware must wait ≥ 500 µs per step**; §12's diagnostic sweep carries
  the requirement.
- Fallback if 140 mV proves noisy on the bench: a 2.2 Ω shunt (308 mV, 0.5 W) or an op-amp gain stage

**I15 — THE SENSE PATH MUST SURVIVE THE FAULT IT EXISTS TO DETECT (added 2026-09-12).** The design
classifies a "shorted" channel, but nothing protected the sense path in that state. With the boost
limiting at 2.5 A, a shorted channel puts **2.5 V on the sense node** — 2.3× the ADC's 0–1.1 V range,
and above the ADG706's 3.3 V supply rail once transients are included — and **6.25 W in a 1 Ω
resistor**. Required, and previously absent from every net contract and sheet brief:

| Measure | Value | Why |
|---|---|---|
| Series resistor, each sense node → mux input | **10 kΩ** | Limits mux input current to well under its rating in the fault case. Harmless to the reading: the ADC buffer capacitor supplies the sample-and-hold charge, so a 10 kΩ source is invisible |
| Clamp diode, each mux input → `+3V3_SW` | Schottky or dual-diode array | Bounds the input to a rail the mux tolerates |
| Sense resistor power rating | **2512, ≥ 1 W** | Survives the fault until the per-string PTC opens |
| Ordering requirement | The per-string **PTC must trip below the boost's 2.5 A limit** (§5.2, C4) | The PTC, not the shunt, is what clears the fault |

Without the PTC ordering requirement the shunt is the weakest element in the path and fails first,
which would turn a detectable fault into an open circuit plus a scorched board.

**What this delivers that the smart switches could not:** genuine **ON-state open-load detection**,
**over-current detection through the intended path**, and real per-channel current telemetry.

> **C5 — CLAIM NARROWED 2026-09-12. A return shorted to chassis is NOT detectable, and leaves the
> channel stuck on.** The shunt sits in the FET **source** leg, so a `RET_xx_y` net shorted to chassis
> conducts +24 V → strip → short → ground, **bypassing both the FET and its shunt**. The sense node
> reads ~0 mV, which the classifier maps to **"open"** — while the LED is at full brightness and
> uncommandable, with the per-string PTC nowhere near tripping at 0.14 A. An earlier revision claimed
> "short detection" unqualified, and bring-up Stage 6 asserted "fault reported, channel protected",
> **an outcome this topology cannot produce.** On an indicator channel that is a safety issue
> presented as a handled fault.
>
> **Detected:** an open circuit (~0 mV when commanded on); excess current through the FET — an
> internally shorted strip, or a return shorted to +24 V upstream of the strip (both read saturated).
> **Not detected:** any fault path bypassing the shunt, chiefly a return shorted to chassis. The rider
> sees a stuck-on corner; the firmware sees "open".
> **Optional future fix, not designed in:** a high-side sense on each per-string +24 V feed would
> catch current flowing while all three of that corner's channels are commanded off.

On cost: roughly **$19 at qty 1 / ~$8 in volume** (ADG706BRUZ ~$9.73 1-off, 12 × 1 Ω 2512,
12 × PMV60ENEA) against $8–12 for two ICs that delivered none of the diagnostics. **The diagnostics
justify the redesign; cost does not** — an earlier revision claimed "$3–6 in passives", wrong in the
figure and in calling a mux a passive.

**Sampling is on-demand, not continuous.** A sense voltage exists only while its channel is ON, and
channels are PWM'd at 400 Hz. Rather than synchronise the ADC to PWM phase, firmware runs a
**diagnostic sweep**: drive one channel to 100% for a few milliseconds, sample, advance. This
doubles as the **installation self-test** (§12) — the same sweep that measures each channel lights
each corner in turn for the installer to confirm against mis-mated connectors.

**Per-channel protection now rests on the per-string PTCs (§5.2) and the boost's current limit,**
not on switch intelligence. A FET rated ≥1 A shrugs off a short the boost limits to 2.5 A, and the
PTC isolates the fault to one corner. This is the protection the design already had.

**SPI is no longer required anywhere on the board** — the switch ICs were its only devices. Four
GPIO are freed, which is what makes the sense chain fit (§7.3).

### 5.2 RGB rail distribution — per-string PTC

All four strings share one +24 V rail, so a single crushed cable shorting that rail would drive
the boost into current limit and extinguish **all four corners simultaneously**. A resettable
PTC on each string's +24 V feed isolates the fault to one corner for a few cents.

> **C4 — CORRECTED 2026-09-12. The PTC must be sized at the enclosure's internal temperature, not at
> 23 °C.** An earlier revision specified ~0.5 A hold against a 0.42 A load and called the margin
> adequate. PPTC hold current derates steeply with ambient: at this enclosure's own design target of
> 58–65 °C internal (§9.4), a device rated 0.5 A at 23 °C holds only ~0.25–0.30 A — **below the
> 0.42 A load.** The corners would cut out during sustained full white on a warm day and recover when
> cool: an intermittent fault **in the indicator path**, which no bench test at room ambient
> reproduces.
>
> **RESOLVED 2026-09-13 — the load fell and the failure dissolved.** The requirement was
> ≥ 0.42 A at 65 °C, which no 1206L part rated for 24 V could meet. The real per-string load is
> **0.10 A**, and the original candidate **1206L050/24 holds 0.31 A at 65 °C — a 3.1× margin.**
> It passes comfortably. The hard FAIL below is retained as the record of why it was raised.
>
> *Superseded requirement:* hold current ≥ 0.42 A at 65 °C, i.e. a nominal ≥ 0.75 A at 23 °C.
> **The Littelfuse 1206L family could not meet THAT, and no replacement was selected (2026-09-12).**
> Measured against the datasheet's own derating table, the best 24 V-rated part (1206L050/24) holds
> **0.31 A at 65 °C** — 26% short of the load — and every 1206L part rated ≥ 0.75 A hold is limited to
> Vmax ≤ 16 V. A **larger package family** is required: 1812L, Bourns MF-SMD or TE miniSMDC. Note this
> part is load-bearing for §5.1's I15 protection, where the PTC (not the 1 Ω shunt) must clear a
> shorted channel — so the shunt's survival in that state is unproven until the PTC is chosen.
Cheap insurance on an exposed, vibration-loaded cable run.

### 5.3 Denali — dual PROFET high-side

One **BTS7008-2EPA-class dual high-side switch** covers both channels: ~10 mΩ per channel,
integrated current sense for diagnostics, 3.3 V logic compatible. **~0.11 W per channel at
3.3 A** (D4 2.0), so ~0.22 W for the pair. Confirm the chosen part's continuous per-channel
rating exceeds 3.3 A with margin, and that its current-sense ratio resolves a 3.3 A load.

High-side switching means the lights return through the shared ground in their connector
(§8.2) rather than relying on chassis bonding, avoiding corrosion and ground-offset faults.

**Verification item:** PWM-ing the supply of lights that contain their own drivers can cause
flicker or audible buzz. The D4 2.0 ships with **DataDim** dimming technology, which confirms
these lights are designed to be dimmed — but it also means each pod contains its own dimming
electronics that could interact with supply PWM in ways a passive light would not. A soak test
across the full duty range is required, checking for flicker, audible buzz, and non-monotonic
brightness. If interaction proves problematic, the fallback is driving the pods at full supply
and dimming via their native DataDim input instead.

### 5.4 PWM generation — and the PCA9685 prescaler constraint

**The PCA9685 has a single global prescaler** — one PWM frequency for all 16 outputs. The two
stages want different frequencies, so they are driven from different sources:

| Channels | Source | Frequency | Rationale |
|---|---|---|---|
| 0–11 (RGB) | PCA9685, I²C | **400 Hz** | 8-bit step = ~10 µs, comfortably longer than the switch slew time, keeping low-end dimming linear and color-matched |
| 12–13 (Denali) | **ESP32 LEDC** | **150 Hz** | Gentler on the lights' internal drivers; matches DialDim-like practice |

**Rationale updated 2026-09-12:** the original argument here was that *smart switches* slew slowly
(microseconds) for EMI reasons. A SOT-23 PMV60ENEA driven from a PCA9685 switches in well under a
microsecond, so that argument no longer applies — but the conclusion still holds on resolution
grounds alone, and 400 Hz also keeps output emissions low. Pushing RGB to the
PCA9685's 1526 Hz ceiling would shrink each 8-bit step to ~2.5 µs — comparable to the slew
time — making the bottom of the dimming range nonlinear and mismatched between colors.

This requires a **composite `IPwm`** routing channels 0–11 to the PCA9685 and 12–13 to LEDC.
`ChannelIndex` is unchanged. See §12.

### 5.5 PCA9685 channel assignment — fixed by firmware

| PCA9685 output | Function |
|---|---|
| LED0–2 | Front-left R, G, B |
| LED3–5 | Front-right R, G, B |
| LED6–8 | Rear-left R, G, B |
| LED9–11 | Rear-right R, G, B |
| LED12–15 | **Unused** (Denali moved to LEDC per §5.4) |

This ordering is mandated by `ChannelIndex` in `src/domain/channel_map.h` and is a hard wiring
constraint, not a layout convenience.

---

## 6. Rails

| Rail | Topology | Spec | Notes |
|---|---|---|---|
| 3.3 V | Buck, **low quiescent** (LM5164 class) | ~1 A | Always on; must supply ESP32 WiFi TX peaks (~500 mA) |
| **5 V** | Low-quiescent regulator, **enable-gated (off in sleep)** | ~100 mA | Shares `EN_3V3SW`; feeds TJA1042 **VCC** only — see below |
| 24 V | **TI LM51571-Q1** — non-synchronous boost, **integrated 50 V / 4.33 A switch** | **12 W design point, 0.5 A** (7.7 W actual) | Enable-gated, direct from `EN_BOOST` |

**The 5 V rail is mandatory, but it is ENABLE-GATED, not always-on (corrected 2026-09-12, I10).** Task 2b established that the **TJA1042's VCC is
4.5–5.5 V**; the "/3" suffix provides a **VIO pin for 3.3 V logic levels, it does not make VCC
3.3 V**. An earlier revision of this spec powered the transceiver from `+3V3_ALW`, which would not
have worked. CAN transceivers with microamp standby and bus wake-up are essentially all 5 V parts,
because the bus itself is a 5 V differential standard — so this rail cannot be designed away by
part substitution. **It is gated off in deep sleep, alongside `+3V3_SW`, using the same enable** — no extra GPIO.
An earlier revision claimed it had to stay powered "since the transceiver has to stay powered in deep
sleep to detect bus activity". **That is contradicted by the datasheet**, which states the low-power
receiver "is supplied by VIO" and "is capable of detecting CAN bus activity even if VIO is the only
supply voltage available". VCC is needed for **normal mode**, not for wake detection. Gating it
recovers 10–25 µA from a sleep budget that §8.2 shows is tighter than previously believed.

§3 accordingly describes **four** power domains.

**Boost part changed 2026-09-13: LM5122-Q1 → LM51571-Q1**, verified from the primary datasheet held
locally at `hardware/datasheets/lm51571-q1.pdf`. The RGB load fell from 40 W to ~8 W, which made a
controller-plus-external-FETs topology the wrong shape. Every criterion improved:

| | LM5122-Q1 | **LM51571-Q1** |
|---|---|---|
| Switch | 2 external FETs + gate loops | **Integrated 50 V / 4.33 A** (5.4× the ~0.8 A peak) |
| Input rating | needed checking vs the ~39 V TVS clamp | **2.9–45 V op, 50 V abs, transient to 50 V** |
| Shutdown IQ | 9 µA typ / **17 µA max** | **≤ 2.6 µA** |
| Spread spectrum | **none** — §10's criterion had to be *relaxed* | **Dual random, built in** |
| Qualification | -Q1 | **AEC-Q100 grade 1** |
| Package | controller + 2 FETs | **WQFN-16, 3 × 3 mm** + 1 Schottky |

**The input rating is the criterion that eliminated the obvious alternatives.** The SMBJ24A clamps at
up to ~39 V, so anything downstream must survive that — which rules out TPS55340 (32 V max) and
TPS61170 (18 V), the parts one would otherwise reach for at this power.

**Non-synchronous, so it needs one external Schottky rectifier.** At 320 mA out that diode costs
~64 mW — against two FETs, their gate drive and the switch-node layout care a synchronous stage
demands. At 8 W the synchronous argument that justified the LM5122 no longer pays for itself.

**Enable: `EN_UVLO_SYNC` (pin 6) is driven DIRECTLY from `EN_BOOST`, with no divider.** That pin
combines enable, programmable line UVLO and sync. Driving it straight from the GPIO:
- keeps "floating = boost off" via the mandatory `EN_BOOST` pulldown;
- **removes ~14 µA of continuous divider current** from the sleep budget (§8.2) — that divider drew
  current across the battery rail whether the boost was enabled or not;
- **removes one of the two ≥ 1 MΩ conditions** the sleep budget's PASS depended on.

What is given up is *programmable* line UVLO; the part's internal lockout remains. Acceptable here —
the Experia's 12 V rail is DC-DC fed, there is no crank dip to ride out on an EV, and the board sleeps
when the bus idles. Combined with the enclosure's heat-spreader plate (§9) this gives large
thermal margin, and the topology brings EMC headroom. The cost is a controller with external
FETs, a current-sense resistor, compensation network, bootstrap, and careful gate-loop layout.

**Known behaviour, benign:** a boost converter has a conduction path from input to output
through the high-side FET's body diode, so the 24 V rail sits near 12 V when the boost is
disabled. Harmless — with the low-side switches off there is no return path, so no current
flows and no glow occurs.

Boost requirements: shielded inductor, spread-spectrum dither, soft start, tightly controlled
switch-node loop area, enable from GPIO.

---

## 7. MCU, CAN and pin allocation

### 7.1 Module — ESP32-WROOM-32E-N8 (8 MB)

Not the stock 4 MB. The current build reports 83.8% flash, which is 83.8% of the 1.25 MB `app0`
partition in the default 4 MB table — about **212 KB free**. Into that must fit deep-sleep
logic, the diagnostic-sweep layer, and eventually OTA. The 8 MB module plus a custom partition
table (2 × 2 MB app slots, ~3 MB LittleFS) costs about a dollar and removes the constraint
permanently.

Onboard antenna (not the U.FL `-32UE` variant), which requires the enclosure to be plastic
apart from the heat-spreader plate (§9).

### 7.2 CAN interface

**TJA1042T/3** (3.3 V VIO variant), supporting standby mode with bus wake-up.

**Hardware-enforced listen-only.** The firmware sets TWAI to listen-only, but that is a software
promise — a bug, crash or future refactor could transmit onto a moving motorcycle's CAN bus. The
transceiver's TXD is routed through an **unpopulated 0 Ω link** with TXD pulled to VIO
(recessive) by default, making the board **physically incapable of transmitting**. Populate the
link only for deliberate bench TX.

**No 120 Ω terminator** — the vehicle bus is already terminated and a third terminator would
unbalance it. An unpopulated footprint is provided for standalone bench use.

CAN-line ESD protection and a common-mode choke are required; a tapped stub on a vehicle bus
sees more abuse than a point-to-point link.

### 7.3 Pin allocation

Three hard constraints drive this, not convenience:

- **EXT0/EXT1 deep-sleep wake works only on RTC-capable GPIOs**
- **ADC2 is unusable while WiFi is active** — sense inputs must be on ADC1 (GPIO 32–39)
- GPIO 6–11 are flash; 0/2/12/15 are strapping pins

| Function | GPIO | Why |
|---|---|---|
| CAN RX | **35** | Input-only **and RTC-capable** — required for wake |
| Ignition sense (divider unpopulated) | **36** | RTC-capable — second wake source. **Pulldown is POPULATED regardless** — see C2 note below |
| CAN TX | 17 | Free (no PSRAM on WROOM-32E) |
| I²C SDA / SCL → PCA9685 | 21 / 22 | Conventional |
| Denali A / B PWM → PROFET | 18 / 19 | LEDC, per §5.4 (moved off 32/33 — see below) |
| Denali current sense, **multiplexed** | **34** | **ADC1 only.** The BTS7008-2EPA has ONE `IS` output shared by both channels |
| **`DEN_DSEL`** — PROFET channel select | **33** | **ADDED 2026-09-12 (C1).** Selects which channel `IS` reports |
| **RGB sense, mux output** | **32** | **ADC1_CH4** — the §5.1 diagnostic chain |
| **Mux select S0–S3** | **23 / 4 / 16 / 5** | Freed by dropping SPI; GPIO 5 is a strapping pin, pulldown mandatory |
| Boost enable | 25 | |
| Peripheral 3.3 V load switch (`EN` of the DML3017LDC) | 26 | Active-high with an internal pulldown — no inverter stage needed |
| PROFET diagnostic enable | 27 | |
| Status LED | 13 | |
| **CAN transceiver STB** | **14** | RTC-capable; required to enter/leave transceiver standby |
| Programming | 0, 1, 3, EN | Reserved for header |

19 signal pins used; **GPIO 2, 12, 15, 39 spare**. (GPIO 33 now carries `DEN_DSEL`; GPIO 39 was
released because the PROFET has only one sense output, not two — see the C1 note.)

> **C1 — CORRECTED 2026-09-12.** An earlier revision allocated **two** ADC inputs for Denali current
> sense (GPIO 34 and 39) and no channel-select line. The chosen **BTS7008-2EPA has a single `IS`
> output multiplexed between channels by a `DSEL` input**, which appeared in no pin table, net
> contract or bias table. As written, channel B's current sense could never have worked and an ADC1
> pin was reserved that could not be used. `DEN_DSEL` is now on GPIO 33 and GPIO 39 is free.

> **C2 — CORRECTED 2026-09-12.** `IGN_SENSE` sits on GPIO 36 with **EXT1 `ANY_HIGH` armed on it**
> (§8.1), and its divider is deliberately unpopulated (§8.3). But **GPIO 34–39 have no internal
> pull-up or pull-down**, so that combination is a floating high-impedance node acting as a wake
> source: the board would wake on injected noise, or never stay asleep. The pulldown is therefore
> **populated in all builds**, divider or not. Note the symptom this prevents is indistinguishable
> from "the CAN bus never idles" (§8.3's top risk), so it would have been misdiagnosed.

> **CORRECTION 2026-09-11:** an earlier revision listed GPIO 38 as spare. **GPIO 37 and 38 are not
> bonded out on WROOM-32 modules** and do not exist as usable pins. That mattered, because every
> one of the six ADC1 pins reachable on the module (32, 33, 34, 35, 36, 39) was already allocated,
> leaving no input for the §5.1 sense chain. Dropping SPI freed 18/19/23/5; Denali PWM moved to
> 18/19, which released **GPIO 32 (ADC1_CH4)** for the mux output.

**Strapping-pin care:** GPIO 5 (mux S3) and GPIO 12/15 (spare) are strapping pins. GPIO 12 selects
flash voltage at boot and is deliberately left unused. GPIO 5 only affects boot-log polarity and is
safe with the mandatory pulldown below.

**Passive defaults must equal the sleep state.** Rather than relying on `gpio_hold_en()` to
freeze pad levels through deep sleep, every enable is pulled to its safe state in hardware:

| Net | Passive bias | Effect when the pad floats |
|---|---|---|
| `EN_BOOST` | pulldown to GND | Boost disabled |
| `EN_3V3SW` | pulldown to GND | Peripheral rail off |
| `CAN_STB` | pull-up to VIO | Transceiver in standby (STB is active-high) |
| `PWM_*` (14) | pulldown to GND | All outputs off |
| `MUX_S0`–`S3` | pulldown to GND | Defined mux channel; **required on GPIO 5**, a strapping pin |
| **`IGN_SENSE`** | **pulldown to GND, ALWAYS POPULATED** | **Defined low.** GPIO 34–39 have **no internal pulls**, and EXT1 `ANY_HIGH` is armed on this pin — left floating it wakes the board on noise (see below) |
| `DEN_DSEL` | pulldown to GND | Defined PROFET channel selection |
| **`EN_DIAG`** (GPIO 27 → PROFET `DEN`) | **pulldown to GND** | **ADDED 2026-09-12.** The PROFET reaches its 0.6 µA Sleep mode only when **all** digital inputs (`INn`, `DEN`, `DSEL`) are low. GPIO 27 is **not** RTC-capable, so it floats in deep sleep; with `DEN` high the part sits in Stand-by at a higher, unquantified current and the §8.2 budget's PROFET line stops holding |

This makes the sleep state the *unpowered* state, so a crash, brownout or reset can never leave
the lights on or the rails up.

### 7.4 Programming and debug

- **6-pin internal header**: 3V3, GND, TXD0, RXD0, EN, IO0
- **Standard DTR/RTS two-transistor auto-reset pair** — directly addresses the development
  board's unreliable auto-reset, which required holding BOOT through esptool's
  "Connecting......". A plain USB-UART adapter will enter download mode unaided.
- BOOT and EN tactile buttons
- Test points on `VBAT`, `VLOGIC_IN`, 24 V, 5 V, 3.3 V (both branches), I²C, `RGB_ISNS`, CAN H/L

---

## 8. Sleep and wake

### 8.1 Mechanism

Config access policy: **the WiFi AP exists only while the CAN bus is alive.** Configuration is
done with the bike on. No wake button, no post-idle window.

1. Idle detected — no CAN frames for a configurable timeout (default 30 s)
2. Firmware disables the boost enable, opens the switched 3.3 V branch, puts the transceiver in
   standby
3. `esp_deep_sleep_start()` with **EXT0** armed on GPIO 35 (CAN RX, **wake on level 0**) and
   **EXT1 `ANY_HIGH`** armed on GPIO 36 (ignition sense)

   **Why two mechanisms rather than one:** bus wake drives RXD **low**, while ignition sense is
   **high** when present. The classic ESP32's EXT1 supports only `ALL_LOW` or `ANY_HIGH` — never
   mixed polarity, and `ANY_LOW` does not exist — so a single EXT1 cannot cover both. EXT0 takes
   the active-low CAN line; EXT1 takes the active-high ignition line. **Cost:** EXT0 requires the `RTC_PERIPH` power
   domain to stay on. **This is NOT an increment on top of the deep-sleep figure** — §8.2 budgets a
   single combined row of ~10 µA, because the datasheet's "Deep-sleep / RTC timer + RTC memory" figure
   already covers the same RTC power domain that EXT0 wake depends on. An earlier revision of this
   sentence implied an extra ~10 µA and was double-counting.
4. Bus activity → transceiver drives RXD low → ESP32 wakes, restores the transceiver to normal
   mode, re-enables both rails

> **PREMISE CORRECTED 2026-09-14.** This section previously read *"Permanently battery-connected,
> so quiescent draw is a first-class requirement."* **That is not true of the Experia.** The user
> confirms the Experia's peripheral connector is **ignition-switched**: it supplies the unit when the
> bike is on and nothing when it is off. On the reference bike the board is therefore **unpowered**
> when parked, not asleep, and the quiescent budget below does not apply to it at all.
>
> The budget is retained in full because it governs the **other** supported topology, and because
> the hardware that serves it costs nothing when unused.

### 8.1a Two supported supply topologies

| | **A — switched feed (the Experia)** | **B — battery feed + ignition sense** |
|---|---|---|
| PWR connector | +12 V **switched**, GND | +12 V **permanent**, GND, **`IGN_IN`** |
| Parked draw | **zero — the board is unpowered** | 85–100 µA (the budget below) |
| Sleep / wake | not used | deep sleep, EXT0 bus wake + EXT1 ignition wake |
| `IGN_SENSE` divider (R37/R38) | **DNP**, third cavity plugged | **POPULATED** |
| Run condition | being powered *is* the signal | `IGN_SENSE` high |

The board is a **superset** serving both. In topology A the sleep path simply never executes, the
switched rails stay enabled, and `IGN_SENSE` rests low behind its populated pulldown (R39). Nothing
has to be removed, and nothing is wasted: the always-on/switched rail split, the TJA1042 VIO/VCC
split and the `VLOGIC_IN` diode-OR all exist for topology B and are inert in A.

**This is what `IGN_IN` is for.** It is not a contingency against the CAN bus never idling — that was
the original framing and it understated it. It is the signal that makes topology B possible at all,
because a permanently-fed board has no other way to know the bike has been switched off.

### 8.1b Consequences of topology A that do NOT apply to B

These follow from the board losing power outright, and are firmware and bring-up items:

1. **There is no graceful shutdown.** Power disappears mid-instruction when the rider switches off.
   Anything that must survive to the next ride has to be committed to NVS **when it changes**, not
   on the way down. Do not design a save-on-shutdown path — there is nowhere to hang it.
2. **Cold boot happens on every ride, and the rider sees it.** Topology B wakes from deep sleep in
   hundreds of milliseconds; topology A pays a full boot, including Wi-Fi bring-up, every ignition
   cycle. **Measure cold-boot-to-lights-on and treat it as a UX figure**, not just a number. If it
   is slow, bring the lighting outputs up before the network stack rather than after.
3. **The input stage is power-cycled on every ride** rather than a handful of times in its life.
   Inrush into the bulk capacitance is repeated thousands of times: confirm at bring-up that it
   neither nuisance-trips the 10 A fuse nor stresses the reverse-polarity P-FET. Soft-start already
   exists on every downstream converter (LM5164 internal, boost `SS` via C25, DML3017LDC), so the
   exposure is the input bulk, not the rails.

### 8.2 Budget

Applies to **topology B only** (see §8.1a). Under topology A the parked draw is zero.

| Contributor | Target |
|---|---|
| ESP32 deep sleep + EXT0 `RTC_PERIPH` domain (§8.1) | ~10 µA |
| CAN transceiver standby | ≤19 µA |
| 3.3 V buck quiescent (LM5164) — **ONE instance; the 5 V regulator is gated off** | 10.5 µA typ / 25 µA max |
| **5 V regulator** | **0 µA — enable-gated off in sleep (see §6)** |
| PROFET standby | ≤0.6 µA |
| RGB MOSFET off-state leakage, 12 × ≤1 µA at 24 V | ≤12 µA |
| P-FET gate + divider leakage — **requires a ≥ 1 MΩ network** | ≤24 µA |
| **Boost shutdown (LM51571-Q1)** | **≤ 2.6 µA** |
| ~~Boost UVLO divider~~ **REMOVED** — direct GPIO enable (§6) | **0 µA** |
| **3.3 V buck feedback divider (≥ 500 kΩ)** | **~6.6 µA** |
| **Revised total (2026-09-13)** | **~85 µA typ / ~100 µA max** |
| **Target / ceiling** | **< 200 µA / 500 µA hard** |

**This PASS is CONDITIONAL on two schematic decisions, not assumptions.** Both are Task 3/4 sizing
jobs, and getting either wrong silently breaks the budget:

1. ~~The boost UVLO divider must be ≥ 1 MΩ~~ — **condition removed 2026-09-13**; there is no divider.
2. **The P-FET gate/Zener network must be ≥ 1 MΩ** — still a design target, not a chosen value.
   **This is now the only remaining condition.**
3. The 3.3 V buck's **feedback divider must be ≥ 500 kΩ** — the LM5164's quoted IQ excludes it, and a
   conventional 275 kΩ divider would add ~12 µA unbudgeted.

> **C3 — CORRECTED 2026-09-12. The earlier figure of "~87–117 µA, confirmed PASS" was wrong.**
> Two contributors were missing and one was actively harmful:
>
> 1. **The boost had no row at all.** LM5122-Q1 shutdown current is 9 µA typ / **17 µA max**.
> 2. **The justification for omitting it was false.** The verification record excused it on the
>    grounds that §4.2's P-FET "cuts the boost off from the battery in deep sleep". That P-FET is a
>    **passive, self-biased reverse-polarity device** — gate resistor and Zener clamp, no enable
>    input, no control net, no GPIO. **Nothing disconnects the boost input from the battery.**
> 3. **The documented enable scheme was a continuous ~207 µA load.** The worked UVLO divider
>    (RUV2 = 49.9 kΩ, RUV1 = 8.06 kΩ ≈ 58 kΩ across 12 V) draws ~207 µA continuously, ~240 µA with
>    the enable transistor shunting RUV1 — **the divider alone exceeded the entire 200 µA target.**
>
> **Resolution:** the UVLO divider is scaled to **≥ 1 MΩ total** (~14 µA at 12 V), retaining line
> undervoltage sensing at 1/15th the current; the boost shutdown current is now budgeted; and the 5 V
> rail is enable-gated (§6, I10) rather than always-on, which recovers a further 10–25 µA. A board
> built to the old text would have drawn ~250–350 µA parked — under the 500 µA ceiling, so it would
> have passed as "working" while running at 2–3× the predicted drain.

At 200 µA, a month parked costs ~0.15 Ah — negligible against the Experia's 12 V battery. Each
contributor to be verified against its datasheet.

### 8.3 Failure modes designed against

| Failure | Mitigation |
|---|---|
| **Bus never idles** → board never sleeps, battery drains | **Topology A is immune** — the feed is switched, so the board cannot drain anything when parked. Under topology B, populate the ignition-sense divider (GPIO 36) and use the configurable idle timeout |
| **Topology B wired but `IGN_IN` left unconnected** | Safe but **silently non-functional**: GPIO 36 sits low on R38∥R39 = 24.8 kΩ, EXT1 never fires and the board never wakes on ignition. Reads like a firmware fault. Covered by a continuity check at install |
| **Wake thrashing** — bus chirps every few seconds | Minimum awake period (a few seconds) so each wake does useful work |

---

## 9. Connectors, enclosure and mechanical

### 9.1 Panel

**REVISED 2026-09-19. TE Superseal is a wire-to-wire series — it has no panel-mount
board-side housing, so the "panel connectors" this section used to describe could not have
been built.** Every circuit now leaves the box as a **soldered wire tail through a cable
gland**, and the Superseal joints live **out on the harness**, where each one can be placed
wherever the bike has room instead of all seven crowding one wall.

**Eight penetrations** (was nine: F1 moved onto the board as an eFuse, §4.1).

```
        ┌──────────────── PANEL ─────────────────┐
        │  (FL)   (FR)   (RL)   (RR)             │  4× M12 gland, 4-core 22 AWG
        │                                        │
        │  (DENALI)   (PWR)    (CAN)    (VENT)   │  Denali, PWR: M16   CAN: M12
        └────────────────────────────────────────┘
        opposite wall: aluminium heat-spreader plate
```

| # | Penetration | Gland | Cable |
|---|---|---|---|
| 1–4 | Corners FL, FR, RL, RR | M12 (3–6.5 mm) | 4-core 22 AWG, ~5.2 mm OD → SS1.0 4-way on the harness |
| 5 | Denali | M16 (5–10 mm) | 2 × 18 AWG + 1 × 16 AWG, ~6.2 mm → SS1.5 3-way |
| 6 | Power | M16 (5–10 mm) | 2 × 16 AWG + 1 × 22 AWG, ~6.6 mm → SS1.5 3-way |
| 7 | CAN | M12 (3–6.5 mm) | 22 AWG twisted pair, ~4.5 mm → SS1.0 2-way |
| 8 | Pressure-equalisation vent | — | §9.3 |

**A gland seals on one round jacket.** Loose wires through a gland is not IP67, so every run
must be a **sheathed multi-core cable**, not a bundle. That is a harness requirement, not a
detail — see `hardware/docs/harness.md`.

**Board side is soldered, with strain relief.** J1 and J3–J8 are `SolderWire` *_Relief*
footprints: each conductor gets a plated hole and a second unplated one to thread the wire
back through. That second hole is the mechanical restraint — nothing else holds these wires,
and without it a pulled cable lifts a pad.

**What this costs.** The box can no longer be unplugged and set aside; it comes off with
seven tails, unplugged at their far ends, and a board swap means re-terminating 24
conductors. Leave a service loop inside so the board can be lifted clear with the glands
slackened.

**Power and CAN stay on separate cables and separate glands** — a switched high-current path
and a differential bus sharing a run invites coupling, and the bus tap should be separable
from the power feed.

**Denali cable carries a shared ground** (two switched positives, one return sized for the
pair at 6.6 A) rather than relying on chassis return.

**Enclosure size is now driven by the gland field plus the plate**, not by connector mating
depth — see `hardware/docs/enclosure.md` §2.

### 9.2 Corner connector mis-mating — a safety issue

The four corner runs end in identical Superseal 1.0 4-way joints and **can be mis-mated**.
Swapping front-left with front-right makes the indicators signal the wrong way, which is
unsafe, and the firmware cannot detect it.

**Improved 2026-09-19 by the move to glands (§9.1).** There used to be *two* places the swap
could happen — at the box and at the strip. The box end is now **soldered at assembly**, so
the easy one is gone: four identical shells side by side on a panel no longer exists. What
remains is a swap out on the bike, which cable length and routing make much harder.

Two mitigations, both still required:

1. **Colour-coded or mechanically keyed** connector variants, one per corner
2. **Installation self-test in the web app** — light one corner at a time so the installer
   confirms each mapping (§12)

### 9.3 Enclosure

**Plastic IP67 box with a FINNED aluminium heat-spreader plate sealed into one wall.**
**(DECIDED 2026-09-12 — finned, not flat; see §9.4 for why a flat plate fails.)** An off-the-shelf
polycarbonate enclosure (Hammond 1554/1555, Fibox, Bopla class) with one wall machined for a
gasketed aluminium plate. The boost FETs, inductor and P-FET couple to the plate through a
silicone gap pad. Remaining walls stay RF-transparent so the onboard antenna works.

Rejected alternatives: extruded aluminium with plastic end caps (off-the-shelf sealed versions
claim IP54–IP65, not IP67); diecast aluminium (best thermally but forces a U.FL antenna and an
extra penetration); thermally conductive filled plastics (custom moulding, not viable at this
volume).

**Conformal coating** on the board. Not potting — the IP67 box and sealed connectors already
handle moisture, the Experia has no engine vibration, and coating preserves serviceability,
USB flashing and the cheaper onboard-antenna module.

**Pressure-equalisation vent** (Gore-type breathable membrane). Sealed enclosures that heat and
cool develop pressure differentials and eventually draw moisture *through* their seals; the vent
is what makes an IP67 rating hold over years.

**Mounting (RESOLVED 2026-09-12).** An earlier revision of this section contradicted itself: it made
the bracket "part of the heatsink" *and* rubber-isolated it from the frame. **Rubber is a thermal
insulator** — the isolation destroys the conduction path the thermal argument relied on. Both could
not hold.

The resolution is that **the finned plate carries the entire thermal load on its own**, so the frame
is no longer needed as a heatsink and the vibration isolation survives intact:

- **Plate → bracket: metal-to-metal**, with thermal compound. The bracket adds spreading area as
  *bonus margin*, not as a requirement the design depends on.
- **Bracket → frame: rubber isolators.** Vibration decoupling is preserved, and nothing thermal is
  lost by it.

**Fin orientation is an installation requirement, not a preference.** The fins must run **vertically**
in the installed attitude so natural convection can form a chimney between them. Mounted with fins
horizontal, they trap air and a large fraction of the added area stops working. Inductor and electrolytics staked with adhesive;
ceramic and polymer capacitors preferred where they will serve.

### 9.4 Thermal

**Rewritten 2026-09-13** after the RGB load turned out to be ~4× smaller than assumed (§2.2). The
governing case has **changed from daytime to night**: with the boost no longer dominating, the
conduction loss in the input feed path at the Denali pair's 7.0 A now dominates the board.
**Since §4.2's rewrite on 2026-09-19 the largest single term is L2**, the input common-mode
choke, not the pass element — the P-FET that used to hold that place has been replaced by a pair
of 0.8 mΩ FETs and is no longer significant.

| Source | **Daytime** (corners white, Denali off) | **Night** (Denali on, front DRLs off) |
|---|---|---|
| Synchronous boost losses (92%, conservative) | 0.83 W (9.6 W of RGB) | ~0.20 W |
| **Pass element** (§4.2, rewritten 2026-09-19): Q10 + Q11 **IPT008N06NM5LF** at 2.4 mΩ hot, plus **R88 sense 5.6 mΩ** | ~0.01 W (1.0 A) | **0.39 W (7.0 A)** — *was 0.78 W as a lone SQJ461EP P-FET* |
| Denali PROFET, 150 °C max | 0 W — Denali off | 0.35 W |
| RGB sense resistors, 12 × 10 Ω | 0.13 W | ~0.03 W |
| RGB discrete FETs, all 12 | ~0 W | ~0 W |
| Buck and logic | 0.40 W | 0.40 W |
| **Input π-filter inductor L1** (1.5 µH) | 0.01 W | **0.28 W** |
| **Input CM choke L2**, both windings (Würth 7448031002) | 0.02 W | **0.78 W — now the largest single term** |
| **Total** | ~1.4 W | **~2.31 W — governs** |

> **PASS ELEMENT REPLACED 2026-09-19, and the night total FALLS.** §4.2 was rewritten to merge
> reverse polarity and overcurrent into one conduction path (LTC4380 + back-to-back
> IPT008N06NM5LF). The lone P-FET's **0.78 W** — the largest single term on this table — becomes
> **0.39 W** for the pair *plus the sense resistor*, so **night goes 2.70 → 2.31 W** even though
> the board has gained overcurrent protection it did not have. At 150 cm² that is **~19.7 K →
> ~60 °C**, about 3 K better than the previous design and the first real margin this table has
> had. **L2 is now the largest single term at 0.78 W.**
>
> *Note R88, the 5.6 mΩ sense resistor, is **0.27 W of that 0.39 W** and is **not** coupled to the
> heat-spreader plate — it needs its own copper (§4.2).*

> **L1 and L2 ADDED 2026-09-19.** They were missing from this table entirely — the gap raised
> as finding **F4** in the Task 7 schematic review. Both sit in the main feed path and carry the
> **full 7.0 A**, so at the selected parts' DCR they contribute **0.90 W between them**, which
> is a third of the night budget and includes a term equal to the P-FET's. The plan's Task 8
> Step 3 was corrected for this (commit `9fa0fea`); this table had not been. The old
> **~1.8 W** figure is simply this one minus L1 and L2 — **1.8 + 0.90 = 2.70** — so anything
> still quoting 1.8 W is quoting a budget with the input filter left out.

*Flash-to-pass transient adds the boost and Denali terms together briefly — still under 3.4 W, and
seconds at a time.*

**Plate sizing — now at 2.31 W.** The table below was computed at **1.9 W**, i.e. before L1 and
L2 were counted. The night figure went to 2.70 W when they were added, then back to **2.31 W**
when §4.2's rewrite replaced the P-FET. Scaling the table: **150 cm² gives ~19.7 K → ~60 °C** at
40 °C ambient, against a 65 °C target; **200 cm² gives ~14 K → 54 °C**.

**A flat plate works with real margin again — about 5 K.** That margin was ~2 K at 2.70 W and is
the direct return on merging the fuse and the reverse-polarity FET into one pass element.
**≥ 150 cm² remains the floor.**

> **One term in the 2.31 W is NOT on the plate**: R88, the 5.6 mΩ sense resistor, contributes
> 0.27 W and couples to the board rather than to the heat-spreader (§4.2). The plate figures above
> are therefore slightly conservative for the plate itself and slightly optimistic for the board
> around R88 — Task 8 must give it its own copper.

Original table, at 1.9 W:

| Effective area | Rise | Internal at 40 °C ambient |
|---|---|---|
| 80 cm² (a flat 100 × 80 mm plate) | 30 K | 70 °C |
| **100 cm²** | 24 K | **64 °C** — meets the 65 °C target |
| **150 cm² — recommended** | **16 K** | **56 °C** — comfortable |
| 200 cm² | 12 K | 52 °C |

**Requirement: a flat aluminium plate of ≥ 150 cm² effective area.** A finned extrusion is no longer
necessary — it was required only when the budget stood at 4.5 W and needed ≥ 300 cm². Fins remain a
harmless option if a suitable profile is convenient, and they would buy a further ~10 K.

> **What this reverses, and why.** §9.3 and earlier revisions of this section required a **finned**
> plate of ≥ 300 cm², derived from a 4.5 W budget that rested on the RGB load being 40 W. The real
> load is 9.6 W, so total dissipation fell to ~1.9 W and the requirement fell with it. The
> fins-vertical installation constraint and the finned/antenna wall separation become moot if a flat
> plate is used; the **metal-to-metal plate-to-bracket and rubber-at-the-frame mounting still
> stands**, since it costs nothing and preserves margin.

**Conservative inputs retained.** Boost efficiency is still taken at 92% (the datasheet's ≥94% is
UNVERIFIED), the P-FET at its 20 mΩ ceiling rather than the better gate-drive case, and the PROFET at
its 150 °C maximum. The design basis for the RGB load is likewise the worst plausible case —
20 W/m × 12 cm — against a strip that may well be 12 W/m at 6 cm, which would be a quarter of it.

**The gap pad is not the bottleneck.** The thermal group is now the boost stage plus the single
P-FET — under 1 W in either mode. Across 1000 mm² of 1.5 mm, 2 W/mK material that is well under 1 K.

---

## 10. PCB and EMC

**Stackup:** 4 layers — signal / GND / power / signal — with **2 oz outer copper**. The input
path needs roughly **5–6 mm width at 2 oz** for a 10 °C rise at the single feed's **7.8 A continuous**
(10.5 A transient), carried as a polygon rather
than a trace, with via stitching. Four layers is not luxury: a solid ground plane is what makes
the synchronous boost's gate loops and the EMC behaviour tractable.

**EMC measures:**

- Input π filter and common-mode choke (ordering and the GND_IN/GND split: §4.3)
- Boost: spread-spectrum dither, shielded inductor, minimised switch-node loop area
- CAN: common-mode choke and ESD protection
- Output snubber footprints, unpopulated, in case the long corner runs need taming
- Low PWM frequencies (400 Hz / 150 Hz) and slow-slewing switches keep output emissions low

**Certification:** the pre-certified module means the radio itself needs no re-certification. A
product would still need unintentional-radiator testing (FCC Part 15B / EN 55032), and CISPR 25
to claim automotive compliance. Designing for it now costs little; retrofitting costs a respin.

---

## 11. Verification and bring-up

**Go/no-go items to resolve before committing the BOM:**

1. ~~Open-load detection threshold~~ **RESOLVED by Task 2b: FAILED category-wide** → §5.1 now uses
   discrete FETs with a dedicated sense chain. Remaining check: **Vds ≥ 40 V**, and the
   output-characteristic curve shows **Id ≥ 0.5 A at Vgs ≤ 3.3 V**. (The earlier wording here demanded
   "full enhancement at 3.3 V" — **withdrawn**; see §5.1's note. Applied as a go/no-go it rejects the
   selected PMV60ENEA and re-opens a closed question.)
2. **Analog mux** on-resistance and leakage are low enough not to corrupt a 140 mV reading, and it
   is rated for 3.3 V operation
3. Every quiescent-current contributor in §8.2, from datasheets
4. Buck capable of ESP32 WiFi TX peaks (~500 mA) while retaining low quiescent draw
5. PROFET continuous per-channel rating exceeds **3.3 A** with margin, and its current-sense
   ratio resolves a 3.3 A load (§5.3)
6. **THE THREE OPEN PART ITEMS — all three block a BOM commit** (added 2026-09-12; an earlier revision
   of this list omitted them entirely, which made the BOM gate silent on the only hard FAIL in the set):
   - **PTC — hard FAIL, no part selected.** The 1206L family cannot meet 0.42 A at 65 °C (§5.2).
     Needs an 1812L / Bourns MF-SMD / TE miniSMDC datasheet and a re-selection.
   - **TVS — UNVERIFIED** after nine failed fetch attempts. Neither file in `hardware/datasheets/`
     named for the TVS is actually an SMBJ24A datasheet. Needs a human browser download.
   - **RGB MOSFET ×12 — zero stock, 30-week lead** (next batch 18-Jan-2027), and the qualified second
     source PMV30ENEA is **also** backordered. This is a commodity part class, so the action is a
     stock-filtered parametric search, which also needs a human browser.
7. **The chosen Experia peripheral outlet sustains 7.8 A** (78% of its 10 A rating) without voltage
   sag or a warm connector — confirm on the vehicle. This is the tight spot of the single-feed
   design (§4.1)

**Staged bring-up:**

1. Rails only, MCU unpopulated — verify 3.3 V and 24 V under dummy loads
2. Boost under full dummy load — efficiency, ripple, thermal rise
3. Quiescent-current measurement in simulated sleep
4. MCU populated — programming header, auto-reset, flash
5. I²C to PCA9685; mux select lines stepped and `RGB_ISNS` read on ADC1; PROFET sense readback
6. Outputs into dummy resistive loads — all 14 channels, PWM linearity at low duty
7. CAN on a bench bus — receive, then standby wake
8. Real strips and Denali lights — soak test for flicker and buzz (§5.3)
9. Full vehicle install — thermal soak, quiescent drain over days parked

---

## 12. Firmware this hardware creates

The first three are **required** — the board does not function as designed without them. Each
gets its own plan.

| # | Work | Why |
|---|---|---|
| 1 | **Deep sleep + CAN wake** | Bus-idle timeout, **EXT0 on GPIO 35 (level 0) plus EXT1 `ANY_HIGH` on GPIO 36** (§8.1 — one mechanism cannot do both polarities), rail enable sequencing, minimum-awake period. No sleep logic exists today. |
| 2 | **Composite PWM HAL** | Route `IPwm` channels 0–11 to PCA9685, 12–13 to LEDC (§5.4). `ChannelIndex` unchanged. |
| 3 | **8 MB partition table** | Custom CSV replacing stock `default.csv` (§7.1). |
| 4 | **Diagnostic sweep + mux scan** | Drive one channel to 100%, step the mux, **wait ≥ 500 µs for the 10 kΩ/10 nF RC to settle (§5.1)**, read ADC1; classify open/working/shorted; read PROFET sense. Surface in the existing web app. Replaces the SPI diagnostics layer — there is no SPI on the board. |
| 5 | **Installation self-test** | Falls out of item 4's sweep at near-zero extra cost: light each corner in turn to catch mis-mated connectors (§9.2). |
| 6 | *OTA updates* | Optional, later. Enabled by the 8 MB partition table. |

---

## 13. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| ~~Experia CAN bus may never idle → no sleep, battery drain~~ **RISK RETIRED 2026-09-14** | — | The Experia's peripheral feed is **ignition-switched** (§8.1a), so the board is unpowered when parked and cannot drain the battery however the bus behaves. The risk survives only for topology B installs, where the ignition-sense divider is populated |
| ~~Open-load detection threshold~~ **CLOSED: failed category-wide (Task 2b)** | — | Redesigned — §5.1 discrete FETs + 1 Ω shunt + mux + ADC1 |
| 140 mV sense signal may be noisy near the ESP32 ADC's accuracy floor | Medium | 0 dB attenuation, averaging, on-demand sweep at 100% duty; classification is open/working/shorted, not precision metering |
| ~~Real Denali wattage unknown~~ **RESOLVED**: D4 2.0 confirmed at 40 W each / 6.6 A per pair | — | Absorbed by a **single** feed once §2.4 established the loads never coincide; night peaks at 7.8 A (78%) |
| RGB strip power assumed, not measured (40 W) | Medium | Power path oversized; re-verify on measurement |
| D4 2.0 contains DataDim electronics that may interact with supply PWM | Medium | Full-range soak test (§5.3); fallback is full supply + native DataDim input |
| Corner connectors mis-mateable → indicators reversed | Medium | Keying/colour coding **and** web app self-test |
| Cable run unfused upstream of the box | Medium | Accepted by author; documented. Short loomed run, booted terminal; a battery-end fuse is addable with no board change |
| Experia peripheral connector part number unidentified | Medium | Identify the part number, and confirm the outlet sustains **7.8 A** before harness build |
| Thermal estimate based on assumed enclosure area | Low | Measure rise at bring-up stage 2; plate area adjustable |

---

## 14. Open questions carried from the firmware spec

These remain unresolved and need CAN bus access on the vehicle. This hardware is what makes
that access practical, so they are expected to close during bring-up:

1. Run bit at `0x102` not yet identified
2. Day/night bit exists but is unidentified
3. "Back" at `0x400` bit 16 — confirm what it drives
4. Brake OR-logic — confirm front OR rear
5. Canonical bit-numbering convention (endianness / bit order within a frame)
6. Duplicate "Run" entries (bit 14 vs bit 11)
7. Spot-latch behaviour — whether a held high beam should latch spot (see
   `spot-latch-deferred` note)
