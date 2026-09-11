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
| **A** | RGB: 40 W at 24 V, via boost at ~92% | 43.5 W | 3.6 A | |
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

The low per-channel RGB current is what makes the smart-switch output stage thermally trivial
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
    │ 3V3 BUCK          │   │ 24 V SYNC BOOST      │   │ DUAL SMART HIGH-SIDE │
    │ low-Iq, ALWAYS ON │   │ LM5122-Q1 class      │   │ PROFET, Isense out   │
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
          │              │ 2× OCTAL SMART LOW-SIDE      │
          │              │ parallel PWM in │ SPI diag   │
          │              └──────┬───────────────┬───────┘
          │                12× PWM           SPI
          │              ┌──────┴───────┐        │
          ├─────────────▶│ PCA9685      │        │
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
                         │ standby + bus wake    │    (listen-only, HW-enforced)
                         └───────────────────────┘
```

**Three power domains, deliberately separated:**

1. **Always-on 3.3 V** — survives deep sleep, powers only the ESP32 and CAN transceiver
2. **Enable-gated 24 V boost** — draws nothing when parked; carries only the RGB load, so it
   is sized at 60 W rather than the full system power
3. **Raw protected 12 V from Feed B** — feeds the Denali high-side switches directly, so their
   6.6 A never passes through a converter

A **load switch splits the 3.3 V rail** into *always-on* (ESP32, transceiver) and *switched*
(PCA9685, switch-IC logic). Only two devices are powered in sleep, which is what makes the
sub-200 µA target realistic rather than aspirational.

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
quiescent draw. One stage per feed: ~0.08 W on Feed A (3.9 A) and ~0.22 W on Feed B (6.6 A),
~0.30 W combined. Splitting the current across two stages roughly halves the conduction loss a
single 10.5 A stage would have incurred.

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
| A | Boost → 24 V → RGB, plus logic | 3.9 A | 5.9 A (boost at its full 60 W design point) | 61% |
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

With the Schottky OR, the MCU keeps power while *either* feed lives, so it stays awake to report
the fault rather than going dark silently.

**Caveat, so the redundancy is not oversold:** both peripheral connectors almost certainly
originate from the same upstream circuit, so this protects against connector and wire faults,
not upstream failure.

---

## 5. Output stages

### 5.1 RGB — octal smart low-side switches

**2 × octal smart low-side switch in parallel-input mode.** Candidate families, to be verified:
ST **VNI8200XP**, Infineon **TLE8110ED** / **TLE8108EM**, NXP **MC33996**.

Selection criteria:

- ≥ 12 channels total
- ≥ 0.3 A continuous per channel (need 0.14 A)
- **Output rating ≥ 40 V** — the 24 V rail plus transients
- **Parallel PWM inputs** — see below
- SPI diagnostics (open load, short to battery, short to ground, overtemperature)
- Low standby current

**Why parallel-input mode matters:** these parts are switches with fault reporting, not PWM
generators. Driving 12 dimming channels purely over SPI would mean software PWM at ~50 kHz of
SPI traffic, which would wreck the firmware's 10 ms tick architecture. Parallel inputs take PWM
on dedicated pins; SPI is used **only to read diagnostics**.

**Go/no-go verification item:** open-load detection thresholds on these parts are often tens of
milliamps, and some detect open load only in the OFF state. At 0.14 A per channel this is close
enough to the threshold that it must be confirmed from the datasheet that a genuinely open
channel is distinguishable. **If it is not, the diagnostics do not deliver on the RGB side** and
the part choice must change.

### 5.2 RGB rail distribution — per-string PTC

All four strings share one +24 V rail, so a single crushed cable shorting that rail would drive
the boost into current limit and extinguish **all four corners simultaneously**. A resettable
PTC (~0.5 A hold) on each string's +24 V feed isolates the fault to one corner for a few cents.
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

Smart switches slew slowly on purpose (microseconds) for EMI reasons. Pushing RGB to the
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
| 24 V | **Synchronous** boost controller + external FETs (LM5122-Q1 class) | 60 W design point, 2.5 A | Enable-gated |

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
logic, the SPI diagnostics layer, and eventually OTA. The 8 MB module plus a custom partition
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
| Ignition sense (unpopulated) | **36** | RTC-capable — second wake source |
| CAN TX | 17 | Free (no PSRAM on WROOM-32E) |
| I²C SDA / SCL → PCA9685 | 21 / 22 | Conventional |
| SPI SCK / MOSI / MISO / CS | 18 / 23 / 19 / 5 | VSPI defaults; both switch ICs daisy-chained on one CS |
| Denali A / B PWM → PROFET | 32 / 33 | LEDC, per §5.4 |
| Denali A / B current sense | **34 / 39** | **ADC1 only** |
| Boost enable | 25 | |
| Peripheral 3.3 V load switch | 26 | |
| PROFET diagnostic enable | 27 | |
| Status LED | 13 | |
| Programming | 0, 1, 3, EN | Reserved for header |

17 signal pins used; GPIO 4, 12, 14, 15, 16, 38 spare. The comfortable margin is what justifies
retaining the PCA9685 rather than driving all 14 channels natively.

### 7.4 Programming and debug

- **6-pin internal header**: 3V3, GND, TXD0, RXD0, EN, IO0
- **Standard DTR/RTS two-transistor auto-reset pair** — directly addresses the development
  board's unreliable auto-reset, which required holding BOOT through esptool's
  "Connecting......". A plain USB-UART adapter will enter download mode unaided.
- BOOT and EN tactile buttons
- Test points on VBAT_PROT, 24 V, 3.3 V, I²C, SPI, CAN H/L

---

## 8. Sleep and wake

### 8.1 Mechanism

Config access policy: **the WiFi AP exists only while the CAN bus is alive.** Configuration is
done with the bike on. No wake button, no post-idle window.

1. Idle detected — no CAN frames for a configurable timeout (default 30 s)
2. Firmware disables the boost enable, opens the switched 3.3 V branch, puts the transceiver in
   standby
3. `esp_deep_sleep_start()` with **EXT1** armed on GPIO 35 (CAN RX) and GPIO 36 (ignition sense)
4. Bus activity → transceiver drives RXD low → ESP32 wakes, restores the transceiver to normal
   mode, re-enables both rails

### 8.2 Budget

Permanently battery-connected, so quiescent draw is a first-class requirement.

| Contributor | Target |
|---|---|
| ESP32 deep sleep | ~10 µA |
| CAN transceiver standby | ~20 µA |
| 3.3 V buck quiescent | 10–30 µA |
| P-FET gate + divider leakage | ~10 µA |
| Smart switches, standby | ~20 µA |
| **Total target** | **< 200 µA** (hard ceiling 500 µA) |

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

Both power feeds are populated (§4.4), bringing the panel to **nine penetrations**: four corners,
Denali, two power, CAN, and two fuse holders. Enclosure size is driven by this count more than by
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

**Plastic IP67 box with an aluminium heat-spreader plate sealed into one wall.** An off-the-shelf
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

**Mounting:** the aluminium plate bolts to a metal bracket with thermal compound, making the
bracket part of the heatsink; the **bracket** is rubber-isolated from the frame, preserving the
thermal path while decoupling vibration. Inductor and electrolytics staked with adhesive;
ceramic and polymer capacitors preferred where they will serve.

### 9.4 Thermal

| Source | Dissipation |
|---|---|
| Synchronous boost losses (40 W out, ~94%) | ~2.6 W |
| P-FET reverse protection, both feeds | ~0.30 W |
| Denali PROFET, both channels at 3.3 A | ~0.22 W |
| RGB low-side switches, all 12 | ~0.12 W |
| Buck and logic | ~0.4 W |
| **Total** | **~3.6 W** |

With the heat-spreader plate and bracket coupling, the target is a rise low enough to keep
internal temperature near 65 °C at 40 °C ambient — roughly 20 °C of margin on the ESP32's
85 °C maximum, and comfortable for 105 °C-rated capacitors.

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

1. **Open-load detection threshold** on the chosen low-side switch versus 0.14 A per channel
   (§5.1) — if it cannot resolve an open channel, the part changes
2. Low-side switch **output rating ≥ 40 V** and PWM capability at 400 Hz
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
5. I²C to PCA9685; SPI to switch ICs; diagnostics readback
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
| 1 | **Deep sleep + CAN wake** | Bus-idle timeout, EXT1 wake on GPIO 35/36, rail enable sequencing, minimum-awake period. No sleep logic exists today. |
| 2 | **Composite PWM HAL** | Route `IPwm` channels 0–11 to PCA9685, 12–13 to LEDC (§5.4). `ChannelIndex` unchanged. |
| 3 | **8 MB partition table** | Custom CSV replacing stock `default.csv` (§7.1). |
| 4 | **SPI diagnostics layer** | Read switch and PROFET faults; surface in the existing web app. |
| 5 | **Installation self-test** | Per-corner identification to catch mis-mated connectors (§9.2). Recommended. |
| 6 | *OTA updates* | Optional, later. Enabled by the 8 MB partition table. |

---

## 13. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Experia CAN bus may never idle → no sleep, battery drain | High | Unpopulated ignition-sense input; configurable idle timeout |
| Open-load detection threshold may exceed 0.14 A/channel | High | **Go/no-go on part selection** before BOM commit |
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
