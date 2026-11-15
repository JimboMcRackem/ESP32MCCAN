# Bring-Up Procedure

**Board:** the plan4 board, 140 × 100 mm, 8 layers, fully assembled by JLCPCB (README "Board
status"). **Rewritten 2026-11-15** against `output/netlist.net`, the redesign spec
(`docs/superpowers/specs/2026-10-17-emarked-module-redesign-design.md`), the aux-stage spec
(`2026-11-13-aux-stage-design.md`) and `harness.md`. The earlier version described the retired
plan3 board (RGB MOSFETs, analog mux, 24 V boost, Denali pods) and is in git history.

Work the stages **in order**. A failed stage stops the process: do not move on with an
unexplained result. Every expected value is written down before the board exists. Fill in
"Measured" at the bench; a number written first is what stops "close enough" afterwards.

## What this board is

- **Two feeds, never joined.** Feed A (J1) runs the logic and the ten signal lamps through U10, an
  LTC4380 surge stopper with back-to-back FETs Q10/Q11. Its current limit is **1.36–1.67 A**
  (R100, 33 mΩ). Feed B (J9) runs the two Oxford pods only, through the parallel reverse-polarity
  P-FETs Q13/Q14 and the SMBJ18A clamp D25. The returns meet only at the net tie NT1.
- **Two rails.** `+3V3_ALW` (U1, always on, from `VLOGIC_IN` = `VBAT` through Schottky D3) and
  `+5V` (U2, enabled by `EN_5V` on GPIO4, 100 k pull-down R19). `+5V` feeds the CAN
  transceiver and the yellow-wire buffers.
- **Ten signal outputs** on three TPS4HC120A quad switches (U11–U13; U13 has two spare channels).
  Each channel limits at **0.25 A (0.19–0.32 A)** and latches off after a thermal fault until its
  input toggles. Each chip's current-sense line reaches the ADC (`SNS_A/B/C` on GPIO 34/36/39),
  but the firmware holds `DIAG_EN` low and does not read them yet.
- **Two pod outputs** on U14, a BTS7008-2EPA dual switch on `VBAT_B`. Each pod's yellow brightness
  wire is a 5 V, 150 Hz PWM from GPIO13 through U15/U16 (74AHCT1G126), enabled only while that
  pod's output is on.
- **CAN is listen-only in hardware.** The TJA1042's TXD is pulled up by R24 and no GPIO reaches it.
  The 120 Ω terminator R26 is not fitted.
- **Fail-safe defaults.** Every switch input has a 47 k pull-down, `DIAG_EN` and `EN_5V` pull down,
  and `CAN_STB` pulls up (transceiver in standby). A blank or resetting MCU lights nothing.
- **No sleep current to measure.** All feeds are ignition-switched and the bus is dead when the bike
  is off (spec §6, item 2), so the board is unpowered when parked. Ignition sense was deleted.

**Test pads:** TP1 `VBAT`, TP2 `VBAT_B`, TP3 `GND_B`, TP4 `+3V3_ALW`, TP5 `+5V`, TP6 `GND`,
TP7 `AUX_PWM`, TP8/TP9 `YEL_L`/`YEL_R`, TP10/TP11 `POD_L_P`/`POD_R_P`, TP12–TP14 `SNS_A`–`SNS_C`,
TP15/TP16 `CANH`/`CANL`, TP17–TP26 the ten lamp outputs (`FL_DRL` … `RR_BRK`), TP27 `VLOGIC_IN`,
TP28 `EN_5V`, TP29 `CAN_RXD`, TP30 `GND_IN`. Each label is on the silkscreen.

Measure every rail against TP6 (`GND`) unless the row says otherwise.

---

## Stage 0: Before ordering, and on arrival

| Check | Expected | Measured | Pass |
|---|---|---|---|
| **Before ordering:** current of each EL360 function (running light, indicator, brake) at 14.4 V on the bench, steady and peak | **Steady ≤ ~0.13 A per function.** The channels now limit at 0.19 A minimum (R62–R64, 56.2 k). The spec still budgets 0.167 A per function (2 W, unmeasured), and a lamp that steady near the limit runs the switch in current limit and latches it off. If any function exceeds ~0.13 A, return R62–R64 to 43.2 k (0.5 A) before ordering | | |
| JLCPCB placement preview: every row of `output/jlcpcb/rotation-review.txt` (39 parts) | Pin 1 and polarity match the assembly drawing (`fabrication.md` §8) | | |
| On arrival, under a loupe: D2, D25 (SMB clamps), D3, D21, D23, D24, D26/D27 | Cathode bands as on `assembly.pdf` | | |
| J2 and L2 fitted (THT); R26 not fitted | As stated | | |
| Resistance `VBAT` (TP1) to `GND`, unpowered | Not a short (> 1 kΩ once the capacitors charge from the meter) | | |
| Resistance `VBAT_B` (TP2) to `GND_B` (TP3), and `+3V3_ALW` / `+5V` to `GND` | Not a short | | |

## Stage 1: Feed A only, blank module

The WROOM module arrives unflashed, so this stage proves the passive safe state with no firmware.
Feed B is not connected. Set the bench supply to 12.0 V, **current limit 200 mA**.

| Check | Expected | Measured | Pass |
|---|---|---|---|
| Feed A current, steady | Record. Tens of mA: the module's ROM boot loop plus U1 | | |
| `VBAT` (TP1) | Supply minus the drop across L2, Q10/Q11 and R100 (well under 0.1 V) | | |
| `VLOGIC_IN` (TP27) | `VBAT` minus one Schottky drop (~0.2–0.4 V) | | |
| `+3V3_ALW` (TP4) | 3.30 V ± 3 % | | |
| `EN_5V` (TP28) | 0 V (R19 pull-down) | | |
| `+5V` (TP5) | 0 V: U2 is disabled until firmware enables it | | |
| `GND_IN` (TP30) to `GND` (TP6) | ~0 mV (joined through L2's return winding) | | |
| All ten lamp outputs (TP17–TP26) | 0 V | | |
| `SNS_A`–`SNS_C` (TP12–TP14) | ~0 V | | |
| `AUX_PWM`, `YEL_L`, `YEL_R` (TP7–TP9) | 0 V | | |
| GPIO12 at R36 | 0 V (strap pull-down: 3.3 V flash) | | |
| Supply at 10.5 V, then 14.4 V | `+3V3_ALW` stays 3.30 V ± 3 % | | |
| **Reverse feed A** (limit 100 mA) | No current beyond leakage, no heat, board works again when corrected | | |

## Stage 2: Feed B

Keep feed A connected at 12 V. Connect a second supply to J9, **current limit 500 mA**, no pods.

| Check | Expected | Measured | Pass |
|---|---|---|---|
| `VBAT_B` (TP2) to `GND_B` (TP3) | Feed B minus a few mV (Q13/Q14 on) | | |
| `GND_B` (TP3) to `GND_IN` (TP30) | ~0 mV (NT1) | | |
| `POD_L_P`, `POD_R_P` (TP10/TP11) | 0 V: U14 inputs pulled down | | |
| Feed B current, no pods | Under 5 mA (U14 standby plus capacitor leakage) | | |
| **Reverse feed B with feed A disconnected** (limit 100 mA) | No current, no damage | | |

**Never reverse one feed while the other is connected.** That drives fault current through NT1
until the reversed feed's fuse clears (`harness.md` §4). It is a harness hazard, not a test.

## Stage 3: Flash and first boot

| Check | Expected | Measured | Pass |
|---|---|---|---|
| Flash over J2 with the MCCAN programmer board (or a plain USB-UART adapter with its DTR and RTS **swapped**: adapter DTR → J2.6, adapter RTS → J2.5) | Succeeds with **no manual BOOT hold** (DTR/RTS auto-reset pair Q2/Q3) | | |
| J2 cable | MCCAN programmer only. J2 is 3V3 GND TX RX DTR RTS, **not** the FTDI order (a generic FTDI cable puts GND on 3V3 and 5 V on TXD0) | | |
| Module identifies as 8 MB flash | 8 MB | | |
| After boot: `EN_5V` (TP28) | 3.3 V (firmware drives GPIO4 high) | | |
| After boot: `+5V` (TP5) | 5.0 V ± 3 % | | |
| GPIO12 at R36, firmware running and CAN started | ~0 V (released to input with pull-down by `CanBus::begin`) | | |
| `SNS_A`–`SNS_C` | ~0 V (firmware holds `DIAG_EN` low) | | |
| All lamp outputs and pod outputs, no CAN connected | 0 V: a dead bus is "everything off" (spec §6, item 2) | | |
| Press SW2 (EN) and watch TP17–TP26 on a scope | No output pulses high during reset or boot | | |
| WiFi access point and web app | Reachable; the Status screen loads | | |
| Feed A current with firmware running, WiFi up | Record (logic budget ≈ 0.1 A) | | |

The DTR/RTS pair exists because the dev board's auto-reset was unreliable. If this stage needs a
manual BOOT hold, re-check the auto-reset circuit: that is a regression, not a quirk.

**J2's `DTR`/`RTS` are named for the transistor pair, not for an adapter.** Q2 (EN) has its
emitter on `DTR`, the reverse of Espressif's dev-board circuit. esptool's reset step drives an
adapter's DTR *pin* high and RTS *pin* low (the modem lines are active low), so a straight
adapter pulses IO0 when esptool means to reset, and flashing fails without the buttons. The
programmer board (`hardware/programmer/`) crosses the pair on its own copper; any other adapter
needs adapter DTR → J2.6 and adapter RTS → J2.5.

## Stage 4: Signal outputs into dummy loads

Load each of the ten lamp tails with a **150 Ω, 2 W** resistor to its return (≈ 80 mA at 12 V).
Use the web app's **test mode** to walk the outputs one at a time.

| Check | Expected | Measured | Pass |
|---|---|---|---|
| Each output, one at a time | Only that tail goes to `VBAT`; every other stays at 0 V | | |
| Output-to-tail mapping | J3: 1 `FL_DRL`, 2 `FL_IND`, 3 `FR_DRL`, 4 `FR_IND`, 5 return. J4: 1 `RL_DRL`, 2 `RL_IND`, 3 `RL_BRK`, 4 return. J5: 1 `RR_DRL`, 2 `RR_IND`, 3 `RR_BRK` | | |
| All ten on: feed A current | Record. Under 1.0 A, well below U10's 1.36 A minimum limit | | |
| Feed A current at switch-on (scope, all ten commanded on together) | Peak below 1.36 A, so U10 never limits at start-up (aux spec A10) | | |
| `SNS_x` with `DIAG_EN` low | ~0 V; diagnostics are off by design | | |
| **Short one lamp output to its return, all others on** | The board keeps running (WiFi stays up, no reboot), only the shorted channel goes dark, and feed A stays under the U10 limit (≈ 1.24 A) | | |
| Remove the short and toggle that output | It recovers: version A latches off until its input toggles | | |

Two outputs shorted at once can still trip U10 and reset the board. Reading `SNS_x` in firmware
would close that gap; it is not built yet.

## Stage 5: Pods

First with dummy loads, then with the real pods. Raise the feed B supply limit to 8 A.

| Check | Expected | Measured | Pass |
|---|---|---|---|
| `POD_L_P` / `POD_R_P` with a 4.7 Ω, 50 W load (≈ 2.6 A) | Output follows its command; `VBAT_B` minus under 0.1 V | | |
| `YEL_L` / `YEL_R` (TP8/TP9) while that pod is **off** | 0 V: the buffer is disabled and R86/R87 hold it low | | |
| `YEL_x` while that pod is **on** | 5 V PWM at **150 Hz ± 5 %**, duty as commanded (night Low default 15 %) | | |
| `AUX_PWM` (TP7) | 3.3 V PWM at 150 Hz, the same duty | | |
| Real pod inrush (`docs/bench/2026-11-13-pod-inrush-procedure.md`, with U14 switching) | U14 does not trip (overload trip 77–99 A); record the peak | | |
| Yellow input current, 5 V drive | Record. It confirms or resizes R82–R85 (provisional) | | |
| Both pods at full beam: feed B current | ≈ 6.4 A (3.2 A per pod, measured 2026-11-12) | | |
| Blue wire (J10.4/J11.4) | Not connected on the board. Record its role if measured | | |

## Stage 6: CAN on the bench

Use a bench CAN tool at **500 kbps** on J8, with the tool's own 120 Ω termination fitted (R26 is
not).

| Check | Expected | Measured | Pass |
|---|---|---|---|
| `CAN_STB` with firmware running | 0 V (normal mode; R25 pulls it up only when undriven) | | |
| Frames from the tool | Decoded; the web app's CAN discovery shows them | | |
| **Two-node bus: the tool and the board only** | The tool reports **ACK errors**: the board never drives the bus, not even an ACK bit. This is the proof that firmware cannot transmit | | |
| `CANH`/`CANL` (TP15/TP16), bus idle | ~2.5 V each | | |
| Stop the tool | Every output goes dark within ~0.5 s (CAN stale, `kStaleMs`) | | |
| Mapped indicator bit toggling | The matching `*_IND` outputs flash in phase with the bit (`flashSource` = auto) | | |

## Stage 7: Soak

All ten lamp channels on dummy loads and both pods at full beam, 30 min, the board in its box with
the lid on.

| Check | Expected | Measured | Pass |
|---|---|---|---|
| Q13 and Q14 temperature rise above ambient | Record. Predicted ≈ 17 K each (0.26 W × 65 °C/W, `enclosure.md` §9); at 85 °C ambient that is ≈ 102 °C | | |
| U14 temperature rise | Record. Predicted ≈ 10 K | | |
| U1 temperature rise | Record. Predicted under 18 K | | |
| No output drops out, no reset | None | | |

## Stage 8: On the bike

| Check | Expected | Measured | Pass |
|---|---|---|---|
| Both feeds with the bike off | **0 V**: each feed is ignition-switched, so the board is unpowered when parked. If either stays live, stop: the board would drain the battery (it has no sleep mode in use) | | |
| Bus bit rate | 500 kbps; frames decode | | |
| Cold boot to lights-on, from ignition-on | Record. Topology A pays a full boot every ride | | |
| Ignition on and off 20 times | No fuse trip, no U10 limit event, board boots every time | | |
| Installation self-test (test mode) | Every corner and function lights where expected (`harness.md` §3) | | |
| Feed A current on a night ride | Record, against the ≈ 0.87 A budget and the ≈ 2 A harness fuse | | |
| Feed B current, both pods at full beam | Record, against 6.4 A and the 10 A harness fuse | | |
| Box temperature after a long ride on a warm day | Record, against the 85 °C design ambient | | |
| Fuse and circuit ratings | Confirm aux 3 is 15 A and feed A's circuit is 5 A (`harness.md` §4) | | |

---

## Open questions to close during bring-up

Bring-up is the first point live bus access exists, so resolve these against the real vehicle:

1. The Run bit at `0x102`: not yet identified.
2. The day/night bit: exists but is unidentified.
3. "Back" at `0x400` bit 16: confirm what it actually drives.
4. Brake OR-logic: confirm front OR rear.
5. The canonical bit-numbering convention (byte order and bit order within a frame).
6. The duplicate "Run" entries (bit 14 vs bit 11).
7. Whether the Experia has a key-on-but-not-ready state, and what Run reads in it (spec §6).
