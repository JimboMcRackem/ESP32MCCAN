# MCCAN Programmer Board — Design

**Date:** 2026-11-14
**Branch:** `programmer-board` (a sub-project; main is not touched until the owner says so)
**Owner's words in bold where they set a requirement.** Everything marked *(builder's call)* or
*(my call)* was not decided by the owner and may be changed by the builder with a reason.

---

## 1. Why this exists

The MCCAN board (plan4, `hardware/`) has a 6-pin programming header, J2, and the auto-reset
transistors (Q2/Q3, R28/R29) that let `esptool` put the ESP32 into its bootloader by toggling DTR
and RTS. It has no USB-to-serial chip. The owner has only ever flashed ESP32 dev boards, which
carry that chip, and has no USB-serial adapter.

J2 is needed at least once: the first flash, which also installs the OTA signing key (the key in
`src/domain/update_pubkey.h` is still the all-zero placeholder, so OTA refuses every update until
a keyed build is flashed over J2). After that J2 is the recovery path when OTA cannot be used.

The owner asked for **a lead to program from the bench**, as **a small programmer board**,
working **from USB alone, like a dev board**, on **a short cable**.

## 2. What success looks like

On the bench, with nothing but a laptop:

1. Plug a USB-C cable from the laptop into the programmer.
2. Plug the programmer's cable onto the MCCAN board's J2.
3. `py -3.13 -m platformio run -t upload` flashes the ESP32 with no button presses.
4. The serial monitor (`platformio device monitor`) shows the firmware's log.
5. The ESP32 boots and its WiFi access point comes up, so the web app can be used on the bench.

No bench supply, no jumper wiring, no adapter to choose.

## 3. Goals

1. **USB-C in, J2's six signals out**, with TX and RX crossed on the board so the cable is
   straight-through.
2. **Powers the MCCAN board's 3.3 V rail from USB** through J2 pin 1, enough for flashing and for
   the ESP32 with WiFi running.
3. **Never drives against a powered MCCAN board.** If the MCCAN board's own supply (bench or bike)
   is present, no current may flow backwards into the programmer, and the programmer must never
   pull the rail away from the board's regulator. Sharing the load is acceptable (*my call*, §6.3).
4. **Survives a reversed or misplugged cable** without damage to either board (§6.4).
5. **Built like the main board:** generated from scripts in the repo, checked by gates, every part
   from JLCPCB's own stock, assembled by JLCPCB, top side only, no hand soldering.
6. **Ordered with the MCCAN boards:** 5 pieces (JLCPCB's minimum), in the same order.

## 4. Non-goals

- No 5 V or battery-voltage supply to the MCCAN board. On USB power only the 3.3 V rail is alive:
  the lights, the pod outputs and the CAN bus stay dead. This is deliberate: a bench session must
  not be able to switch on a 3 A pod output.
- Not a general-purpose ESP32 programmer. It fits J2's pinout; other targets are not a goal.
- No JTAG, no CAN interface, no enclosure.
- No change to the MCCAN board. J2, its pinout and its reset circuit stay as they are.

## 5. Anti-goals (a failure even if it works)

- Anything the owner must hand-solder. (The cable is bought, not built: §7.)
- A programmer that back-powers or fights the MCCAN board when both are powered.
- A design that needs a bench supply to flash.

## 6. The design as decided

### 6.1 The interface it must match: J2 on the MCCAN board

J2 is a 1×6 vertical pin header, 2.54 mm pitch (`PinHeader_1x06_P2.54mm_Vertical`), on the top
side near SW1/SW2, reachable with the enclosure lid off.

| J2 pin | Net on the MCCAN board | Meaning |
|---|---|---|
| 1 | `+3V3_ALW` | the board's always-on 3.3 V rail |
| 2 | `GND` | logic ground |
| 3 | `UART_TX` | ESP32 TX (U0TXD, GPIO1): the ESP32 transmits here |
| 4 | `UART_RX` | ESP32 RX (U0RXD, GPIO3): the ESP32 receives here |
| 5 | `DTR` | into the auto-reset pair (Q2 emitter; via R29 to Q3's base) |
| 6 | `RTS` | into the auto-reset pair (Q3 emitter; via R28 to Q2's base) |

The auto-reset pair is the standard cross-coupled circuit from Espressif's dev boards, so the
programmer passes the USB-serial chip's raw DTR and RTS outputs straight through, at 3.3 V logic.
Source of truth: `hardware/output/netlist.net` and `hardware/scripts/gen_mcu_can.py`.

### 6.2 Programmer-side connector and cable

- The programmer carries a **1×6, 2.54 mm pin header with J2's pin order** (*my call*), so a plain
  **straight-through 6-way female-to-female jumper cable, 10–20 cm**, joins the two pin 1 to
  pin 1. **The owner chose a short cable** over a board that plugs directly onto J2.
- TX/RX cross on the programmer: the USB-serial chip's RXD goes to header pin 3, its TXD to pin 4.
- Pin 1 is marked on the silk at the header, and the header is labelled with the six net names.

### 6.3 Power path

USB-C VBUS (5 V) → 3.3 V regulator → reverse-current-blocking switch → header pin 1.

- **Why feeding the MCCAN rail is safe** (checked against the netlist and the LM5164 datasheet,
  2026-11-14):
  - `+3V3_ALW` carries the ESP32 (U5), the TJA1042's VIO (U6.5), pull-ups (R22, R24, R25), the
    3V3 buck's feedback divider (R5) and clamp diodes D8–D10 (cathodes on the rail).
  - It is made by U1, an LM5164 buck, through L4. Fed from outside, current flows back through L4
    and U1's high-side body diode into `VLOGIC_IN`, charging its capacitors (C5–C7) to about
    2.6 V and then stopping. LM5164's absolute maxima are referred to ground only (SW −1.5 to
    100 V, FB to 5.5 V); none is approached. U1 stays off: VIN is far below its 6 V minimum.
  - D3 blocks `VLOGIC_IN` from the battery side, so VBAT and the 5 V rail stay unpowered.
  - The ESP32's pins into unpowered parts are safe: the 74AHCT1G126 pod buffers (U15/U16) have
    overvoltage-tolerant inputs, and the output-switch inputs are high-voltage parts.
- **Current:** at least **600 mA** continuous at 3.3 V (*my call*): flashing draws a few hundred
  mA, and WiFi start-up peaks near 500 mA. Bulk capacitance at the output for those peaks
  *(value: builder's call)*.
- **USB-C:** a USB 2.0 device. CC1 and CC2 each pulled down with 5.1 kΩ, so any USB-C source
  provides default USB power. No USB-PD.
- **Reverse blocking (goal 3):** when the MCCAN board's own rail is up, the programmer's output must
  not conduct backwards into its regulator. An ideal diode or a load switch with reverse-current
  blocking meets this *(part: builder's call)*. A plain Schottky is not acceptable if it leaves the
  rail below 3.0 V at full load (the ESP32's minimum), counting the cable's drop.
- **Both powered: load sharing is accepted** (*my call*). U1 holds the rail at about 3.24–3.34 V
  (R5 348k / R6 200k on a 1.2 V reference), which overlaps any 3.3 V regulator's tolerance, so
  "supplies exactly nothing" would need the output set below about 3.2 V or a presence detector.
  Neither is worth it: the ideal diode lets whichever source is higher carry the load, nothing
  flows backwards into either, and the LM5164 simply stops switching while the rail sits above its
  set point. No harm either way.
- **Short-circuit:** the output must survive a short to ground indefinitely (current limit and
  thermal shutdown in the regulator or the switch).

### 6.4 Signals, protection and the unpowered case

- **Series resistors** on TX, RX, DTR and RTS *(values: builder's call)*. They protect both chips
  if the cable goes on backwards, and limit current when one board is powered and the other is not.
- **Programmer unplugged from USB, MCCAN board powered:** the ESP32's TX line and the auto-reset
  pull-ups must not back-power the USB-serial chip through its I/O pins beyond what the series
  resistors limit to a harmless leakage. The builder confirms this against the chosen chip's
  datasheet.
- **Reversed cable**, traced on the MCCAN side: the programmer's 3.3 V output lands on `RTS`, its
  GND on `DTR`, its RTS on `+3V3_ALW`, its DTR on `GND`. Q3's base-emitter sees 3.3 V reversed,
  inside a small-signal BJT's 5–6 V rating; Q2 conducts through R28 and holds EN low. Nothing on
  the MCCAN board exceeds a rating; the ESP32 is simply held in reset. The programmer side must
  likewise survive having its outputs tied to ground or to 3.3 V (the current limit and the series
  resistors cover this).

### 6.5 USB-to-serial chip

- **A USB CDC-ACM part, so Windows' built-in driver runs it with nothing to install** (*my
  call*): for example the CH343P or the CH9102F, whichever JLCPCB stocks. CP2102N and CH340 both
  need a vendor driver, which Windows Update usually fetches when online; either is the fallback
  if no CDC-ACM part is in stock, recorded with the reason.
- Whichever part: TXD, RXD, DTR and RTS at 3.3 V logic, working with `esptool` at up to 921 600
  baud.
- The chip's own supply comes from USB, not from the MCCAN board.

### 6.6 Indicators

- **Power LED** (3.3 V output present) and **TX/RX activity LEDs** (*my call*), so the owner can
  see it working.

### 6.7 Board

- **2 layers**, 1.6 mm, all parts on the top side, JLCPCB standard assembly (*my call*).
- **About 20 × 40 mm** *(builder's call)*, USB-C at one end, the 6-pin header at the other.
- **Silkscreen:** pin 1 and the six net names at the header, "MCCAN PROG" and the board revision.
- **ESD:** a USB ESD protection part on D+/D− *(builder's call)*.

### 6.8 How it is made

- **Generated, like the main board** (`hardware/README.md`, `hardware/docs/`): the schematic,
  board, BOM and placement files come from scripts; nothing is hand-edited.
- **Where it lives** *(builder's call)*: a separate KiCad project, for example
  `hardware/programmer/`, so the MCCAN project's files and gates are untouched. Reuse the main
  board's scripts and libraries (`lcsc.py`-style part table, `check_stock.py`, `gen_fab.py`
  patterns) where they fit.
- **Gates**, mirroring the main board: ERC 0, a netlist check that asserts the J2 pinout and the
  TX/RX crossover of §6.1–6.2, DRC 0 at all severities, a fab-package check, and a stock check for
  5 boards from JLCPCB's own stock.

## 7. Bought, not made

- The **6-way female-to-female straight-through jumper cable**, 10–20 cm, 2.54 mm housings.
  JLCPCB does not supply it. A few spare cables are worth buying.
- A **USB-C cable**, which the owner likely has.

## 8. Acceptance (on the bench, when the boards arrive)

1. USB only: the power LED lights, and the laptop sees a serial port with no driver install (a
   vendor driver from Windows Update only if the CP2102N/CH340 fallback was used).
2. Programmer on an MCCAN board, USB only: `platformio run -t upload` flashes with no button
   presses; the serial monitor shows the boot log; the WiFi access point appears.
3. MCCAN board on its bench supply, programmer plugged in: no current flows back into the
   programmer (measure at its output; it may be supplying part of the load), the rail stays between
   3.2 and 3.4 V, and flashing still works.
4. Cable reversed at one end, USB connected, for 10 s: neither board is damaged; the ESP32 is held
   in reset; with the cable put right, step 2 passes again.
5. Output shorted to ground for 10 s: the programmer recovers when the short is removed.

## 9. Left to the builder

The exact parts (regulator, reverse-blocking switch, USB-serial chip per §6.5,
ESD part, LEDs, resistor values), the board size and placement, the project's location in the
repo, and which main-board scripts to reuse. Each choice that departs from a *my call* above is
recorded with its reason.

## 10. Ordering (owner, 2026-11-14)

**The MCCAN board order waits until the programmer is ready**, so both go to JLCPCB in one order.
The programmer is therefore built with its full gate suite (§6.8) before anything is ordered. The
cable (§7) is a separate purchase.
