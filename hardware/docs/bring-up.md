# Bring-Up Procedure

Work the stages **in order**. A failed stage stops the process — do not proceed
to the next stage with an unexplained result.

Every check below has an expected value written before any board exists. The
"Measured" and "Pass" columns are intentionally blank — they get filled in at
the bench, not now. A wrong reading is easy to rationalise as "close enough"
after the fact; writing the number down first is what stops that.

Current design baseline this procedure checks against (spec
`2026-09-11-esp32-mccan-pcb-hardware-design.md` and `hardware/docs/part-selection.md`):

- RGB output is **12 discrete SOT-23 MOSFETs** (PMV60ENEA class), each with a
  **1 Ω shunt** in its source leg. **There is no SPI on this board** and no
  smart low-side switches for RGB — any earlier reference to either is void.
- Diagnostics are **shunt → 16:1 analog mux (ADG706) → ADC1 GPIO 32**, mux
  select `MUX_S0`–`S3` on GPIO 23/4/16/5. A channel at full current reads
  **~140 mV**; the ADC runs at **0 dB attenuation** (0–1.1 V range).
  Classification is open (~0 mV) / working (~140 mV) / shorted (saturated) —
  not precision metering.
- Denali (D4 2.0 pair) uses a separate **dual PROFET high-side** stage with
  its own current-sense readback, independent of the RGB shunt/mux chain.
- Four rails: `+3V3_ALW`, `+3V3_SW`, **`+5V` (always on, mandatory — the
  TJA1042 transceiver's VCC needs 4.5–5.5 V)**, and `+24V` (boost, enable-gated).
- **Two independent 12 V feeds, domain-split**: Feed A (boost + logic) is
  3.9 A behind a 7.5 A fuse; Feed B (Denali pair) is 6.6 A behind a 10 A fuse.
  They are never paralleled — only a Schottky OR joins them, and only onto
  the logic rail.
- Passive defaults are all **fail-safe when floating**: `EN_BOOST` and
  `EN_3V3SW` pull down, `CAN_STB` pulls up (forces standby), all 14 `PWM_*`
  pull down, `MUX_S0`–`S3` pull down. Floating = safe/off.
- **Hardware-enforced listen-only:** the transceiver's TXD runs through a DNP
  0 Ω link, pulled recessive. The firmware cannot put a frame on the bus even
  if it tries.

---

## Stage 1: Rails only — MCU and switch ICs NOT populated

Purpose: prove the power path and its passive safe-state defaults before any
active logic exists to get it wrong. If ICs downstream of a given net are not
yet populated, probe the net directly at the pull-up/pulldown resistor.

Current-limit the bench supply (e.g. ≤ 100 mA) for the reverse-polarity rows
so a protection failure doesn't cascade into real damage.

| Check | Expected | Measured | Pass |
|---|---|---|---|
| Feed A current with no load | < 5 mA | | |
| `+3V3_ALW` | 3.30 V ± 3% | | |
| `+5V` rail (mandatory, TJA1042 VCC) | within 4.5–5.5 V, nominal 5.0 V | | |
| `+24V` with `EN_BOOST` high | 24.0 V ± 5% | | |
| `+24V` with `EN_BOOST` floating | ~VBAT_A (boost FET body diode; see rails sheet note) | | |
| `+3V3_SW` with `EN_3V3SW` floating | 0 V (pulldown) | | |
| `CAN_STB` net with nothing driving it | pulled high, ≥ 3.0 V (forces transceiver standby) | | |
| All 14 `PWM_*` nets with nothing driving them | 0 V (pulldown) | | |
| `MUX_S0`–`S3` nets with nothing driving them | 0 V (pulldown — channel 0 selected) | | |
| Reverse-polarity test: reverse Feed A | No current, no damage | | |
| Reverse-polarity test: reverse Feed B | No current, no damage | | |

## Stage 2: Boost under full dummy load

| Check | Expected | Measured | Pass |
|---|---|---|---|
| 24 V into 2.5 A dummy load | 24.0 V ± 5%, stable | | |
| Efficiency at 40 W out | ≥ 94% | | |
| Output ripple | < 200 mV pk-pk | | |
| Boost group temperature rise after 30 min | consistent with ~2.6 W dissipated | | |

## Stage 3: Quiescent current in simulated sleep

| Check | Expected | Measured | Pass |
|---|---|---|---|
| Total, with `EN_BOOST`/`EN_3V3SW` floating and transceiver held in standby | **87–117 µA** design target (hard ceiling **500 µA**) | | |

If the reading misses the target, isolate per contributor against the sleep
budget roll-up in `hardware/docs/part-selection.md` (ESP32 deep sleep +
EXT0 RTC domain ~10 µA, CAN transceiver standby ≤19 µA, buck quiescent
21 µA typ/50 µA max for both instances, PROFET standby ≤0.6 µA, RGB FET
leakage ≤12 µA, P-FET gate divider ≤24 µA by design) rather than treating the
total as a single opaque number.

## Stage 4: MCU populated

| Check | Expected | Measured | Pass |
|---|---|---|---|
| Flash over the programming header with a plain USB-UART adapter | Succeeds with **no manual BOOT hold** (DTR/RTS auto-reset pair) | | |
| Module identifies as 8 MB flash | 8 MB | | |

The DTR/RTS auto-reset pair exists specifically because the dev board's
auto-reset was unreliable and required holding BOOT through esptool's
handshake. If this stage needs a manual BOOT hold, the auto-reset circuit is
the first thing to re-check — that is a regression, not a quirk to work around.

## Stage 5: Buses

| Check | Expected | Measured | Pass |
|---|---|---|---|
| PCA9685 responds at its I²C address | ACK | | |
| Mux steps through all 16 channels | `RGB_ISNS` follows the selected channel | | |
| Open channel vs. working channel at 100% duty | ~0 mV vs. ~140 mV, clearly distinguishable | | |
| PROFET diagnostic (Denali) readable | Sense output tracks load | | |

## Stage 6: All 14 outputs into dummy resistive loads

| Check | Expected | Measured | Pass |
|---|---|---|---|
| Each of 12 RGB channels switches independently | Correct channel, no crosstalk | | |
| Channel-to-corner mapping matches `ChannelIndex` | FL, FR, RL, RR, in that order | | |
| RGB PWM frequency | 400 Hz ± 5% | | |
| Denali PWM frequency | 150 Hz ± 5% | | |
| Low-duty linearity, all 12 channels | Monotonic from duty 1; colours matched across channels | | |
| Open-load detection, one channel disconnected | Fault reported (part-selection row 1.1) | | |
| Short-to-ground detection | Fault reported, channel protected | | |

## Stage 7: CAN

| Check | Expected | Measured | Pass |
|---|---|---|---|
| Receive frames from a bench bus | Frames decoded correctly | | |
| TXD link DNP: attempt to transmit | **Nothing appears on the bus** (hardware-enforced listen-only) | | |
| Standby mode entered (`CAN_STB` high) | Transceiver current drops | | |
| Bus activity drives RXD low in standby | Wake signal observed on GPIO 35 | | |
| Deep sleep → EXT0 wake (GPIO 35, level 0) on bus activity | Board wakes and resumes | | |
| Deep sleep → EXT1 wake (GPIO 36, `ANY_HIGH`) on ignition sense | Board wakes and resumes | | |

The DNP-link test is the load-bearing check in this stage: it is the proof
that a firmware bug cannot put a frame on the bus, not just a functional
nicety. Do not skip it even if RX-only testing looks sufficient.

## Stage 8: Real loads, soak test

| Check | Expected | Measured | Pass |
|---|---|---|---|
| Four real RGB strings, full white, 30 min | No flicker; thermal rise acceptable | | |
| Denali D4 pair, swept across the full duty range (0–100%) | No flicker, no audible buzz, monotonic brightness | | |
| Measured RGB string power vs. the 40 W assumption | Record actual (spec §2.2 assumed 40 W) | | |
| Measured Denali draw vs. 6.6 A assumption | Record actual (3.3 A/channel assumed) | | |

The D4 2.0 contains its own DataDim electronics, which may interact with
supply-side PWM at 150 Hz — that interaction is exactly what this soak test
is for, across the full duty range, not just at one setpoint. If the pair
buzzes or flickers under supply PWM, the documented fallback is full supply
voltage plus the pods' native DataDim input (spec §5.3) — record which mode
is used going forward.

## Stage 9: Vehicle install

| Check | Expected | Measured | Pass |
|---|---|---|---|
| Both Experia peripheral outlets confirmed independent 10 A circuits | Independent, not branches of one 10 A circuit | | |
| Internal enclosure temperature after a sustained ride | < 65 °C at 40 °C ambient | | |
| Parked quiescent drain over 7 days | Consistent with the Stage 3 figure (87–117 µA, ceiling 500 µA) | | |
| Does the CAN bus actually go quiet when parked? | Bus idles → board enters deep sleep | | |
| Corner mapping verified by the installation self-test | All four corners correct (FL, FR, RL, RR) | | |

The CAN-idle check is the one the entire sleep strategy depends on and is
currently unconfirmed — if the bus never goes quiet, the board never sleeps
and the 87–117 µA figure from Stage 3 is academic. If this fails, the
mitigation already designed in is the unpopulated ignition-sense input
(GPIO 36, EXT1) plus a configurable idle timeout, tuned once real bus
behaviour is observed — not a hardware change.

---

## Open questions to close during bring-up (spec §14)

Bring-up is the first point live bus access exists, so resolve these against
the real vehicle rather than leaving them as firmware-spec assumptions:

1. The Run bit at `0x102` — not yet identified.
2. The day/night bit — exists but is unidentified.
3. "Back" at `0x400` bit 16 — confirm what it actually drives.
4. Brake OR-logic — confirm front OR rear.
5. The canonical bit-numbering convention (endianness / bit order within a frame).
6. The duplicate "Run" entries (bit 14 vs. bit 11).
7. The spot-latch decision — whether a held high beam should auto-latch spot
   (see the `spot-latch-deferred` note); this has been deferred pending
   exactly the kind of confirmable CAN bus state this hardware now provides.
