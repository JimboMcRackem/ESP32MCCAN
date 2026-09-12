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
- **ONE 12 V feed** behind a single **10 A** fuse (spec 4.4). The loads never coincide
  (spec 2.4): daytime 3.9 A (39%), **night 7.8 A (78% — the governing case)**, with a
  seconds-long 10.5 A flash-to-pass transient that a blade fuse ignores. The second
  feed exists only as unpopulated board footprints.
  They are never paralleled — only a Schottky OR joins them, and only onto
  the logic rail.
- Passive defaults are all **fail-safe when floating**: `EN_BOOST` and
  `EN_3V3SW` pull down, `CAN_STB` pulls up (forces standby), all 14 `PWM_*`
  pull down, `MUX_S0`–`S3` pull down. Floating = safe/off.
- **Hardware-enforced listen-only:** the transceiver's TXD runs through a DNP
  0 Ω link, pulled recessive. The firmware cannot put a frame on the bus even
  if it tries.

---

## Stage 1: Rails only — MCU and output-stage parts NOT populated

Purpose: prove the power path and its passive safe-state defaults before any
active logic exists to get it wrong. If ICs downstream of a given net are not
yet populated, probe the net directly at the pull-up/pulldown resistor.

Current-limit the bench supply (e.g. ≤ 100 mA) for the reverse-polarity rows
so a protection failure doesn't cascade into real damage.

| Check | Expected | Measured | Pass |
|---|---|---|---|
| Feed current with no load | < 5 mA | | |
| `+3V3_ALW` | 3.30 V ± 3% | | |
| `+5V` rail (mandatory, TJA1042 VCC) | within 4.5–5.5 V, nominal 5.0 V | | |
| `+24V` with `EN_BOOST` high | 24.0 V ± 5% | | |
| `+24V` with `EN_BOOST` floating | ~VBAT (boost FET body diode; see rails sheet note) | | |
| `+3V3_SW` with `EN_3V3SW` floating | 0 V (pulldown) | | |
| `CAN_STB` net with nothing driving it | pulled high, ≥ 3.0 V (forces transceiver standby) | | |
| All 14 `PWM_*` nets with nothing driving them | 0 V (pulldown) | | |
| `MUX_S0`–`S3` nets with nothing driving them | 0 V (pulldown — channel 0 selected) | | |
| Reverse-polarity test: reverse the feed | No current, no damage | | |
| Confirm the DNP second-feed stage is unpopulated and isolated | No populated path; no voltage present | | |

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
| Total, with `EN_BOOST`/`EN_3V3SW` floating and transceiver held in standby | Predicted (part-selection roll-up, **revised 2026-09-12**): **99–122 µA**<br>Pass (design requirement): **< 200 µA**<br>Hard fail (ceiling): **> 500 µA** | | |

These are three different numbers doing three different jobs, and the row
keeps all three on purpose:

- **99–122 µA** is the *prediction* — what the datasheet roll-up in
  `hardware/docs/part-selection.md` says this board should draw. **It supersedes an
  earlier 87–117 µA figure that omitted the boost controller entirely** (C3), and it
  holds only if the boost UVLO divider and the P-FET gate network are both ≥ 1 MΩ.
- **< 200 µA** is the *pass criterion* — the design requirement the product
  must meet for the parking/sleep strategy to make sense.
- **> 500 µA** is the *hard fail* — the ceiling past which the sleep
  strategy does not work at all.

A reading **between 122 µA and 200 µA passes** — it is inside the design
requirement — but should still be investigated per contributor against the
roll-up (ESP32 deep sleep + EXT0 RTC domain ~10 µA, CAN transceiver standby
≤19 µA, buck quiescent 21 µA typ/50 µA max for both instances, PROFET
standby ≤0.6 µA, RGB FET leakage ≤12 µA, P-FET gate divider ≤24 µA by
design). It means some part is drawing more than its own datasheet figure,
which is worth understanding even though the board isn't failing. Only a
reading above 200 µA is an actual fail; only a reading above 500 µA is a
hard fail requiring the parking/sleep strategy itself to be reconsidered.

## Stage 4: MCU populated

| Check | Expected | Measured | Pass |
|---|---|---|---|
| Flash over the programming header with a plain USB-UART adapter | Succeeds with **no manual BOOT hold** (DTR/RTS auto-reset pair) | | |
| Module identifies as 8 MB flash | 8 MB | | |

The DTR/RTS auto-reset pair exists specifically because the dev board's
auto-reset was unreliable and required holding BOOT through esptool's
handshake. If this stage needs a manual BOOT hold, the auto-reset circuit is
the first thing to re-check — that is a regression, not a quirk to work around.

## Stage 4b: Real deep-sleep current, MCU populated and running

**ADDED 2026-09-12 (project review I14).** Stage 3 measures *simulated* sleep with the
MCU unpopulated and the rails held off by their pulldowns. That cannot see two of the
defects this design actually risks: a floating `IGN_SENSE` waking the board (C2), or the
boost's UVLO divider drawing current it should not (C3). Without this stage, both would
first surface as a bad 7-day vehicle result in Stage 9 - a week per iteration.

| Check | Expected | Measured | Pass |
|---|---|---|---|
| Firmware enters `esp_deep_sleep_start()`, measure feed current | Predicted **99-122 uA**<br>Pass **< 200 uA**<br>Hard fail **> 500 uA** | | |
| `IGN_SENSE` (GPIO 36) DC level in sleep | **0 V**, held by its populated pulldown - not floating | | |
| Board stays asleep for 10 min undisturbed, bus quiet | No spurious wake | | |
| Boost UVLO divider current (measure across the divider) | **~14 uA**, consistent with a >= 1 MOhm divider. **~207 uA means the datasheet's example values were fitted - C3** | | |
| `+5V` rail in sleep | **0 V** - gated off with `+3V3_SW` (I10) | | |
| Wake on bus activity, then re-enter sleep | Returns to the same current | | |

A reading near 250-350 uA with everything else nominal points at the UVLO divider;
random wakes point at `IGN_SENSE`.

## Stage 5: Buses

| Check | Expected | Measured | Pass |
|---|---|---|---|
| PCA9685 responds at its I²C address | ACK | | |
| Mux steps through all 16 channels | `RGB_ISNS` follows the selected channel | | |
| **Mux address maps to the RIGHT channel** — for each k in 0..11: drive channel k to 100%%, confirm **address k reads ~140 mV and every other address reads ~0 mV** | All 12 correct | | |
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
| Open-load detection, one channel disconnected | Fault reported (part-selection **Section 1a**, the discrete-FET rows — *not* the superseded appendix row 1.1, which documents the octal-switch design that failed) | | |
| Short a return to chassis with the channel commanded OFF | **Reads as "open" (~0 mV) while the LED is STUCK ON at full brightness.** This is the documented limitation, not a defect - the shunt is bypassed (spec 5.1, C5). Confirm the behaviour matches the documentation so nobody later reports it as a detection bug | | |
| Short a return to +24 V upstream of the strip | Saturated reading, reported as a fault | | |
| Internally shorted strip (simulate with a low-value load) | Saturated reading, reported as a fault | | |

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
| **Same run, but with the enclosure at its hot internal temperature (58–65 °C)** | **No PTC trips.** This is the C4 case: 0.42 A per string is sustained for hours in daytime mode, and a PTC sized at 23 °C holds only ~0.25–0.30 A when hot. A bench run at room ambient will NOT reproduce it | | |
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
| The Experia peripheral outlet sustains the night load | **7.8 A continuous (78% of its 10 A rating)** without voltage sag or a warm connector, on a warm night | | |
| Fuse temperature after a sustained night ride | Warm but not hot; no nuisance opening. **78% is the top of good practice** — if it opens, drop the Denali maximum level in the web app (90% gives 7.2 A / 72%) | | |
| Internal enclosure temperature after a sustained ride | < 65 °C at 40 °C ambient | | |
| Parked quiescent drain over 7 days | Predicted: **17–21 mAh** over 7 days (99–122 µA × 168 h)<br>Pass: **< 34 mAh** (the <200 µA requirement × 168 h)<br>Hard fail: **> 84 mAh** (the 500 µA ceiling) | | |
| Does the CAN bus actually go quiet when parked? | Bus idles → board enters deep sleep | | |
| Corner mapping verified by the installation self-test | All four corners correct (FL, FR, RL, RR) | | |

Express the 7-day drain as charge rather than current, because that is what a meter on a parked
bike actually integrates. Same three-tier reading as Stage 3: the **predicted** figure is what
this board should draw, **< 34 mAh** is the pass criterion (the design requirement sustained over
a week), and **> 84 mAh** means the parking strategy does not work. A result between 20 and
34 mAh passes but indicates a contributor above its datasheet figure — worth chasing even though
the board is inside requirement.

For scale: 34 mAh over a week is negligible against a motorcycle's 12 V battery (typically
8–20 Ah), which is the whole reason the CAN-wake strategy is viable.

The CAN-idle check is the one the entire sleep strategy depends on and is
currently unconfirmed — if the bus never goes quiet, the board never sleeps
and the 99–122 µA figure from Stage 3 is academic. If this fails, the
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
