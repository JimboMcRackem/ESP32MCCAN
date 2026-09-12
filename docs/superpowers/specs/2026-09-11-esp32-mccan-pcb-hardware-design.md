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
| 4 × RGB COB string | **24 V constant-voltage**, 4-wire common anode | 24 V | Owned; voltage is fixed |
| 2 × Denali aux light | Self-contained 12 V units, internal drivers | 12 V | Driven identically |

The RGB strings are constant-voltage with internal series resistors — **not** constant-current
emitters. This is why the output stage is switches rather than LED drivers (§5.1).

Common anode forces **low-side** switching on R/G/B. The Denali units are switched
**high-side**, so their return is the shared ground in their connector (§9.1).

### 2.2 Budget

Supply is **two** Experia peripheral connectors, each rated **10 A**. Each feed is derated to
**8.5 A continuous** (85%).

**Confirmed load: Denali D4 2.0 TriOptic** — four 10 W CREE XPL HI LEDs per pod, **80 W / 6.6 A
for the pair**, i.e. **40 W per light**. This is a measured manufacturer figure, not an
assumption.

| Feed | Item | Draw | Input current | Margin on 10 A |
|---|---|---|---|---|
| **A** | RGB: 40 W at 24 V, via boost at **92%** (conservative — §9.4) | 43.5 W | 3.6 A | |
| **A** | Logic (ESP32 peak WiFi TX, PCA9685, transceiver) | 4 W | 0.3 A | |
| | **Feed A total** | **47.5 W** | **3.9 A** | **61%** |
| **B** | Denali D4 2.0 pair | 80 W | 6.6 A | **34%** |
| | **System total** | **~128 W** | **10.5 A** | |

**Why two feeds are required, not optional.** The total is **10.5 A — above a single 10 A
connector.** An earlier revision of this spec assumed Denali ≤ 25 W each and specified one feed
with the second laid out unpopulated; the confirmed D4 figure of 40 W each invalidates that.
Both feeds are populated (§4.4).

**Single-feed fallback, if ever needed:** capping the Denali maximum level in the web app — an
existing tunable — to ~60% yields ~48 W and a 7.9 A total, which fits one feed. This sacrifices
light output and is a configuration workaround, not the design intent.

**The RGB figure remains assumed, not measured** — 20 W/m × 0.5 m × 4 strings. Re-verify when the
strips are measured. Feed A has 61% margin, so a higher real figure is absorbed comfortably.

### 2.3 Per-channel current

| | Value |
|---|---|
| Per RGB string, all three colors full (white) | 0.42 A |
| **Per RGB channel** (R, G or B) | **~0.14 A** |
| Per Denali channel | **3.3 A** (D4 2.0 at 40 W) |

### 2.4 Operating modes — the loads never all coincide

**Confirmed by the owner 2026-09-12.** This is load-defining and it governs the thermal design:

| Mode | Denali | RGB corners | Feed A | Feed B |
|---|---|---|---|---|
| **Daytime** | **OFF** | All four on (white DRL) | **3.9 A** | **~0 A** |
| **Night** | On (80 W) | Fronts **off**, indicating only; rears on | ~1.2 A | **6.6 A** |

**Consequences:**

- **"Full-white RGB *and* both Denali at maximum" is not a reachable steady state.** It occurs only
  during a flash-to-pass in daylight — seconds at a time, absorbed by thermal mass.
- The **steady-state thermal worst case is daytime: ~4.5 W** (§9.4), not the 5.7 W that combination
  implies.
- **The two feeds never peak together.** Daytime loads Feed A (3.9 A) with Feed B idle; night loads
  Feed B (6.6 A) with Feed A light. The 10.5 A system figure in §2.2 is an envelope, not an operating
  point.
- **C4 (the PTC) is confirmed as a real sustained condition, not a corner case:** daytime runs all
  four corners at full white continuously, so each string holds 0.42 A for hours at the enclosure's
  hot internal temperature. That is precisely the case the original 0.5 A PTC would have tripped on.

The low per-channel RGB current is what makes the discrete-FET output stage thermally trivial
(§5.1) — and it is the figure against which open-load detection must be verified (§11).

---

## 3. Architecture

```
 FEED A ──[7.5 A panel fuse]──┐          FEED B ──[10 A panel fuse]──┐
 12 V, 3.9 A                  ▼          12 V, 6.6 A                  ▼
                   ┌──────────────────┐              ┌──────────────────┐
                   │ INPUT PROTECT A  │              │ INPUT PROTECT B  │
                   │ P-FET rev. pol.  │              │ P-FET rev. pol.  │
                   │ 24 V TVS, pi+CM  │              │ 24 V TVS, pi+CM  │
                   └────────┬─────────┘              └────────┬─────────┘
                       VBAT_A (~12 V)                    VBAT_B (~12 V)
                ┌───────────┴──┬──────── Schottky OR ─────┬───┴──────────┐
                ▼              ▼                          ▼              ▼
    ┌───────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
    │ 3V3 BUCK +3V3_ALW │   │ 24 V SYNC BOOST      │   │ DUAL SMART HIGH-SIDE │
    │ + 5V REG (gated)  │   │ LM5122-Q1 class      │   │ PROFET, 1x IS + DSEL │
    │ ~1 A  (OR'd: A|B) │   │ enable-gated, 60 W   │   │ enable-gated         │
    │                   │   │      (from A)        │   │    (from B)          │
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

Plus **raw protected 12 V from Feed B** straight to the Denali high-side switches, so their 6.6 A
never passes through a converter.

In deep sleep only **two devices** are powered — the ESP32 and the transceiver's VIO domain — which is
what makes the sub-200 µA budget in §8.2 achievable.

**Which rail feeds what, stated explicitly** because §8.2's roll-up depends on it: PCA9685 and ADG706
on `+3V3_SW`; TJA1042 VIO on `+3V3_ALW` and its VCC on `+5V`; ESP32 on `+3V3_ALW`.

---

## 4. Input stage

### 4.1 Fusing

**Two panel-mount sealed ATO/ATC blade fuse holders**, IP67 when capped — one per feed:

| Feed | Load | Fuse |
|---|---|---|
| A | RGB + logic, 3.9 A | **7.5 A** |
| B | Denali D4 pair, 6.6 A | **10 A** |

Each fuse matches or sits below its peripheral connector's 10 A rating — a fuse above the
connector rating protects nothing the connector does not already limit. Feed A takes the smaller
7.5 A fuse because its load is bounded at 3.9 A, giving tighter protection than a blanket 10 A.

Both loads sit at **52–66% of fuse rating**, comfortably inside the derating band for sustained
current, so nuisance blowing is not expected.

**Documented residual risk (accepted by the author):** a fuse protects the *cable* upstream of
itself. Mounting it at the box leaves the battery-to-box run without overcurrent protection, so
a chafe-through anywhere along that run is not interrupted. Partially offset by: a short run,
abrasion-resistant loom, routing clear of chafe points, and a booted ring terminal. A
battery-end inline fuse can be added later with **no board change**.

**Open item:** if the Experia's peripheral connectors prove to be individually fused by the
bike, this holder is redundant and may be omitted — freeing panel space and removing a
consumable. Verify on the vehicle.

### 4.2 Reverse polarity — P-FET, not an ideal-diode controller

A P-channel MOSFET in the supply path with gate resistor and Zener clamp. Chosen over the
textbook ideal-diode controller (LM74700-class) because those draw tens of microamps
*continuously* — a significant share of the entire sleep budget, spent permanently to save a
fraction of a watt that only matters while the lights are on. The P-FET has essentially zero
quiescent draw. One stage per feed: at the specified **20 mΩ ceiling**, **~0.30 W on Feed A (3.9 A)
and ~0.87 W on Feed B (6.6 A), ~1.18 W combined** (§9.4). Splitting the current across two stages
roughly halves the conduction loss a single 10.5 A stage would have incurred.

> **CORRECTED 2026-09-12 (I4).** An earlier revision of this paragraph said "~0.08 W / ~0.22 W,
> ~0.30 W combined", which implies 5 mΩ — a part that was never selected — and contradicted §9.4.
> Anyone sizing copper or a gap pad from the old figure would have under-provisioned by ~4×.

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

### 4.4 Dual feed — domain split, both populated

Two 2-way power connectors, each with its own P-FET reverse-polarity stage, its own transient
clamp and its own fuse (§4.1), plus a **dual Schottky OR** feeding the 3.3 V buck from either
feed.

**Split by domain, never paralleled.** Paralleling two feeds divides current by path resistance
(wire gauge, length, contact resistance), giving something like 8 A / 4 A rather than 5 A / 5 A;
and ORing them through ideal diodes is worse still, since the slightly-higher-voltage feed
supplies nearly everything — that is source selection, not sharing, and one connector would sit
over its rating while the other idles. A domain split gives each feed a deterministic, bounded
load that cannot divide unevenly:

| Feed | Powers | Current | Ceiling | Margin on 10 A |
|---|---|---|---|---|
| A | Boost → 24 V → RGB, plus logic | 3.9 A | 5.9 A (boost at its full 60 W design point) | 61% nominal / **41% at the ceiling** |
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
offer is marginal at 0.14 A anyway (the injected pull-down reaches 150 mA while a healthy channel
sources only ~140 mA, so a working channel could read as open), the RGB stage is now **12 discrete
logic-level N-MOSFETs plus a purpose-built diagnostic chain** that does what the ICs could not.

**Switching:** one logic-level N-channel MOSFET per channel, gate driven directly from a PCA9685
output. Requirements: **Vds ≥ 40 V** (the 24 V rail plus transients), **Id ≥ 1 A**, and
**Vgs(th) max ≤ 2.0 V** with the output-characteristic curve showing Id ≥ 0.5 A at Vgs = 3.3 V.

> **Note on gate drive (2026-09-11).** An earlier revision demanded the FET be "fully enhanced at
> 3.3 V". No MOSFET in this class publishes Rds(on) below 4.5 V Vgs, and the requirement was wrong
> anyway: at **0.14 A**, even a pessimistic 1 Ω Rds(on) costs 140 mV and 20 mW on a rail with 24 V of
> headroom — and the design **deliberately adds a 1 Ω sense resistor in the same leg**, so a fraction
> of an ohm from the FET is the same order as a part chosen on purpose. The strip's internal
> resistors (~171 Ω) set the current, so 1–2 Ω of series resistance shifts it under 1%. Nothing here
> needs low Rds: not heat, not headroom, not current accuracy, not switching speed.

**Diagnostics:** a **1 Ω sense resistor in each FET's source leg**, all 12 sense nodes feeding a
**16-channel analog multiplexer** whose output drives one ESP32 **ADC1** input.

- Sense is **ground-referenced** (low-side), so no differential or high-side amplifier is needed
- 1 Ω × 0.14 A = **140 mV** at full channel current; **0.24 W** total across 12 channels at full white
- ADC at **0 dB attenuation** (0–1.1 V range), so 140 mV is ~13% of full scale — ample to separate
  open (≈0 mV), working (≈140 mV) and shorted (saturated)
- 1 Ω chosen deliberately over 2.2 Ω: the larger shunt would read a cleaner 308 mV but cost 0.5 W
- **The mux must be specified for 3.3 V operation** — ADG706-class (1.8–5.5 V, ~2.5 Ω on-resistance).
  CD74HC4067 is excluded: HC on-resistance rises steeply below 4.5 V and is uncharacterised at 3.3 V
- **A ~100 nF buffer capacitor at the ADC input** supplies the SAR sample-and-hold charge locally, so
  mux on-resistance cannot corrupt the reading. Belt and braces with the part choice above
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
> **Requirement:** hold current **≥ 0.42 A at 65 °C** with margin, which for typical PPTC derating
> means a nominal **≥ 0.75 A hold at 23 °C**. Trip current must still act before the boost's 2.5 A
> limit. Vmax ≥ 24 V. **The part must be re-selected with the derating table actually applied.**
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
| **5 V** | **Low-quiescent regulator, always on** | ~100 mA | **ADDED 2026-09-11 — see below** |
| 24 V | **Synchronous** boost controller + external FETs (LM5122-Q1 class) | 60 W design point, 2.5 A | Enable-gated |

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

Note that §3's "three power domains" becomes **four** once this rail is added.

**Why synchronous:** a non-synchronous boost loses ~6 W at this power; synchronous roughly
halves it to ~3 W. Combined with the enclosure's heat-spreader plate (§9) this gives large
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
| Peripheral 3.3 V load switch | 26 | |
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
> from "the CAN bus never idles" (§8.3's top risk), so it would have been misdiagnosed. Retaining the PCA9685 is what makes this fit.

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

This makes the sleep state the *unpowered* state, so a crash, brownout or reset can never leave
the lights on or the rails up.

### 7.4 Programming and debug

- **6-pin internal header**: 3V3, GND, TXD0, RXD0, EN, IO0
- **Standard DTR/RTS two-transistor auto-reset pair** — directly addresses the development
  board's unreliable auto-reset, which required holding BOOT through esptool's
  "Connecting......". A plain USB-UART adapter will enter download mode unaided.
- BOOT and EN tactile buttons
- Test points on VBAT_PROT, VBAT_A, VBAT_B, 24 V, 5 V, 3.3 V, I²C, `RGB_ISNS`, CAN H/L

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
   the active-low CAN line; EXT1 takes the active-high ignition line. **Cost:** EXT0 requires the
   `RTC_PERIPH` power domain to stay on, adding roughly 10 µA to the sleep budget (§8.2). That is
   accounted for and still inside the 200 µA target.
4. Bus activity → transceiver drives RXD low → ESP32 wakes, restores the transceiver to normal
   mode, re-enables both rails

### 8.2 Budget

Permanently battery-connected, so quiescent draw is a first-class requirement.

| Contributor | Target |
|---|---|
| ESP32 deep sleep + EXT0 `RTC_PERIPH` domain (§8.1) | ~10 µA |
| CAN transceiver standby | ≤19 µA |
| 3.3 V buck quiescent (LM5164) | 21 µA typ / 50 µA max |
| **5 V regulator** | **0 µA — enable-gated off in sleep (see §6)** |
| PROFET standby | ≤0.6 µA |
| RGB MOSFET off-state leakage, 12 × ≤1 µA at 24 V | ≤12 µA |
| P-FET gate + divider leakage | ≤24 µA |
| **Boost controller shutdown (LM5122-Q1)** | **9 µA typ / 17 µA max** |
| **Boost UVLO divider, ≥1 MΩ (see below)** | **~14 µA** |
| **Revised total** | **~110–147 µA** |
| **Target / ceiling** | **< 200 µA / 500 µA hard** |

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
| **Bus never idles** → board never sleeps, battery drains | Unpopulated ignition-sense input (GPIO 36); configurable idle timeout tunable once real bus behaviour is observed |
| **Wake thrashing** — bus chirps every few seconds | Minimum awake period (a few seconds) so each wake does useful work |

---

## 9. Connectors, enclosure and mechanical

### 9.1 Panel

```
        ┌──────────────── PANEL ─────────────────┐
        │  [FL]   [FR]   [RL]   [RR]             │  4× Superseal 1.0, 4-way
        │  4-way  4-way  4-way  4-way            │  (+24 V, R, G, B) — 0.42 A
        │                                        │
        │  [DENALI]   [PWR A]   [PWR B]   [CAN]   │  Denali: SS1.5 3-way
        │   3-way      2-way     2-way    2-way   │  Power:  2× SS1.5 2-way
        │          (FUSE A 7.5 A) (FUSE B 10 A)   │  CAN:    SS1.0 2-way
        └────────────────────────────────────────┘  Fuses:  2× sealed ATO
        opposite wall: aluminium heat-spreader plate
```

Both power feeds are populated (§4.4), bringing the panel to **eleven penetrations**: four corners,
Denali, two power, CAN, the pressure-equalisation vent (§9.3), and two fuse holders. (An earlier
revision said "nine" while listing ten items and omitting the vent — corrected 2026-09-12, I11.) Enclosure size is driven by this count more than by
the board.

**Power and CAN on separate connectors** — a switched high-current path and a differential bus
sharing one shell invites coupling, and the bus tap should be separable from the power feed.

**Denali connector carries a shared ground** (two switched positives, one ground sized for the
pair) rather than relying on chassis return.

### 9.2 Corner connector mis-mating — a safety issue

The four corner connectors are identical 4-way parts and **can be mis-mated**. Swapping
front-left with front-right makes the indicators signal the wrong way, which is unsafe, and the
firmware cannot detect it. Two mitigations, both required:

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

| Source | Dissipation |
|---|---|
| Synchronous boost losses (40 W out, **92% — conservative, see below**) | **~3.5 W** |
| P-FET reverse protection, both feeds | **~1.18 W** at the 20 mΩ ceiling (Feed A 0.30 W, Feed B 0.87 W) |
| Denali PROFET, both channels at 3.3 A (**150 °C max, not 25 °C typ**) | **~0.35 W** |
| RGB discrete FETs, all 12 | ~0.01 W |
| RGB sense resistors, 12 × 1 Ω at 0.14 A | ~0.24 W |
| Buck and logic | ~0.4 W |
| **Steady-state worst case (daytime, §2.4)** | **~4.5 W** |
| *Transient peak (flash-to-pass in daylight, seconds)* | *~5.7 W — not thermally sizing* |

**Revised again 2026-09-12** after the project review found the budget mixed typicals with maxima.
Three inputs are now taken at their worst case rather than their typical, which is the right basis for
sizing a heatsink that cannot be changed after fabrication:

| Input | Was | Now | Why |
|---|---|---|---|
| Load combination | full-white RGB **and** both Denali maxed | **the real modes in §2.4** | That combination is not a reachable steady state — daytime has Denali off, night has the front DRLs off |
| Boost efficiency | 94% (**UNVERIFIED** — no numeric figure appears in the datasheet text) | **92%**, the figure §2.2 already used | The two disagreed; the conservative one governs until measured at bring-up Stage 2 |
| P-FET Rds(on) | 14 mΩ (the V<sub>GS</sub> = −10 V column) | **20 mΩ**, the specified ceiling | 14 mΩ silently assumed a gate drive the schematic has not yet guaranteed |
| PROFET | 0.22 W (25 °C typ) | **0.35 W** (150 °C max) | Row 2.6 itself computes 0.349 W at max and fails its own 0.25 W criterion there |

Component figures stay conservative; only the **load combination** was corrected, and that correction
comes from how the bike is actually ridden rather than from an optimistic reading of a datasheet. If
bring-up also confirms 94% efficiency and a gate drive near −10 V, daytime falls to ~3.6 W (~55 °C at
300 cm²). The design does not rely on that.

### The plate must be finned — a flat plate of plausible size fails

**Computed 2026-09-12.** For natural convection (h ≈ 8 W/m²K), the area needed to shed 4.3 W is:

Recomputed 2026-09-12 against the **real operating modes** in §2.4, using conservative component
figures throughout (92% boost, 20 mΩ P-FET, PROFET at its 150 °C max):

| Effective area | Daytime, 4.5 W | Internal at 40 °C | Night, 2.6 W | Internal at 40 °C |
|---|---|---|---|---|
| 80 cm² (flat 100 × 80 mm plate) | 70 K | **110 °C** | 41 K | 81 °C | **Fails** |
| 215 cm² (the old "hard requirement") | 26 K | **66 °C** | 15 K | 55 °C | Marginal |
| **300 cm²** — **hard requirement** | **19 K** | **59 °C** | 11 K | 51 °C | Comfortable |
| 350 cm² — design target | 16 K | 56 °C | 9 K | 49 °C | Ample |

**Why 300 cm² is kept as the requirement even though 250 cm² would pass.** The margin is cheap in an
extruded profile, and three of the inputs above are still unverified or pessimistic in ways that could
move: boost efficiency is **UNVERIFIED** at 92–94% (I6), the P-FET figure assumes the 20 mΩ ceiling
rather than the better gate-drive case, and the PROFET line uses its 150 °C maximum. 300 cm² absorbs
all three moving the wrong way at once.

An earlier revision of this section claimed "~65 °C at 40 °C ambient" without checking it: that figure
silently assumed **~215 cm²**, roughly **three times** what a flat plate sized to fit this enclosure
actually provides.

**Requirements, therefore:**

| | Value |
|---|---|
| Plate footprint | ≥ 80 cm² (≈ 100 × 80 mm) |
| **Effective convective area — hard requirement** | **≥ 300 cm²** (fin multiplier ≥ 3.75×) → ~64 °C at worst case |
| **Effective convective area — design target** | **≥ 350 cm²** (fin multiplier ≥ 4.4×) → ~60 °C |
| Fin orientation | **Vertical in the installed attitude** (§9.3) |
| Plate thickness at the base | ≥ 3 mm, for flatness under fastener load and in-plane spreading |

Stated as an area requirement rather than a specific profile, so any extrusion meeting it qualifies.

**The gap pad is not the bottleneck:** ~2.1 K across 1200 mm² of 1.5 mm, 2 W/mK material at 3.4 W.
The constraint was always the plate's external convection.

**Worst case is rare but must still be survivable:** 4.3 W requires simultaneous full-white RGB *and*
both Denali at maximum. Typical draw is nearer 2 W, where even a flat plate would pass. The design
sizes for the worst case because the RGB stage is now discrete FETs with no thermal protection of
their own.

---

## 10. PCB and EMC

**Stackup:** 4 layers — signal / GND / power / signal — with **2 oz outer copper**. The input
paths need roughly 4–5 mm width at 2 oz for a 10 °C rise at 6.6 A (Feed B, the heavier), carried as polygons rather
than a trace, with via stitching. Four layers is not luxury: a solid ground plane is what makes
the synchronous boost's gate loops and the EMC behaviour tractable.

**EMC measures:**

- Input π filter and common-mode choke
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
6. **Two independent 10 A peripheral outlets exist on the Experia** and are not branches of one
   10 A circuit — confirm on the vehicle before committing to the dual-feed harness (§4.4)

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
| 4 | **Diagnostic sweep + mux scan** | Drive one channel to 100%, step the mux, read ADC1; classify open/working/shorted; read PROFET sense. Surface in the existing web app. Replaces the SPI diagnostics layer — there is no SPI on the board. |
| 5 | **Installation self-test** | Falls out of item 4's sweep at near-zero extra cost: light each corner in turn to catch mis-mated connectors (§9.2). |
| 6 | *OTA updates* | Optional, later. Enabled by the 8 MB partition table. |

---

## 13. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Experia CAN bus may never idle → no sleep, battery drain | High | Unpopulated ignition-sense input; configurable idle timeout |
| ~~Open-load detection threshold~~ **CLOSED: failed category-wide (Task 2b)** | — | Redesigned — §5.1 discrete FETs + 1 Ω shunt + mux + ADC1 |
| 140 mV sense signal may be noisy near the ESP32 ADC's accuracy floor | Medium | 0 dB attenuation, averaging, on-demand sweep at 100% duty; classification is open/working/shorted, not precision metering |
| ~~Real Denali wattage unknown~~ **RESOLVED**: D4 2.0 confirmed at 40 W each / 6.6 A per pair | — | Dual feed with domain split is now the baseline (§4.4), not an option |
| RGB strip power assumed, not measured (40 W) | Medium | Power path oversized; re-verify on measurement |
| D4 2.0 contains DataDim electronics that may interact with supply PWM | Medium | Full-range soak test (§5.3); fallback is full supply + native DataDim input |
| Corner connectors mis-mateable → indicators reversed | Medium | Keying/colour coding **and** web app self-test |
| Cable runs unfused upstream of the box (both feeds) | Medium | Accepted by author; documented. Short loomed runs, booted terminals; battery-end fuses addable with no board change |
| Experia peripheral connector part number unidentified; **two** outlets now needed | Medium | Identify part number and confirm two independent 10 A outlets exist before harness build |
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
