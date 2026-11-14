# MCCAN programmer board (rev A)

A bench programmer for the MCCAN board's J2 header: USB-C in, J2's six signals out.
It does for the MCCAN board what the USB chip on an ESP32 dev board does: one cable from the
laptop, `py -3.13 -m platformio run -t upload`, no buttons, no bench supply.

Spec: `docs/superpowers/specs/2026-11-14-programmer-board-design.md`.
Plan: `docs/superpowers/plans/2026-11-14-programmer-board.md`.

## What it does

- **USB-C device** (CC1/CC2 5.1 kΩ to GND, default USB power, no PD) into a **CH343P**, a USB
  CDC-ACM serial chip that Windows runs with its built-in driver: nothing to install.
- **Powers the MCCAN board's 3.3 V rail** (`+3V3_ALW`, J2 pin 1) from USB: VBUS → AMS1117-3.3 →
  LM66100 ideal diode → J2 pin 1. ≥ 600 mA. The ideal diode stops any current flowing back
  into the programmer when the MCCAN board's own supply is up; the two then share the load.
  Only the 3.3 V rail is powered: lights, pod outputs and CAN stay dead on the bench.
- **TX/RX crossed on the board**, so the cable is straight-through, pin 1 to pin 1.
- **DTR/RTS** go through a 74LVC2G125 buffer (powered from USB, I_off inputs/outputs) so an
  unplugged programmer cannot drag the MCCAN board's EN down and hold the ESP32 in reset.
- **Series resistors** on every signal, so a reversed cable damages nothing.
- **LEDs:** PWR (3.3 V output present), TX and RX activity.

J2 pinout, printed on the silk beside the header (pin 1 marked by an arrow):

| Pin | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Net | 3V3 | GND | TX (ESP32 transmits) | RX (ESP32 receives) | DTR | RTS |

## Regenerate and gate

Everything here is generated; never hand-edit `.kicad_sch`, `.kicad_pcb`, `.kicad_pro` or
`.kicad_dru`. From `hardware/programmer/`:

```bash
python scripts/gen_sch.py                     # schematic (then export the netlist, below)
"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch export netlist --format kicadsexpr \
    -o output/netlist.net prog.kicad_sch
python scripts/gen_pcb.py                     # board, ~35 s (deterministic router)
python scripts/gen_fab_prog.py                # output/jlcpcb/ (runs DRC first, refuses if dirty)
bash scripts/gate.sh                          # every gate; exit 0 only if all PASS
```

`gate.sh` prints one row per gate: `test_parts`, `test_netlist_prog`, `test_board`,
`test_fab_prog`, `erc` (and the committed netlist matches the schematic), `check_netlist_prog`
(J2 pinout, crossover, power and back-feed budgets), `drc` (0 violations, 0 unconnected,
0 parity, all severities), `check_board` (geometry DRC does not check), `fab_check`, `stock`
(5 boards, JLCPCB's own stock; needs the network).

## Budgets (from `check_netlist_prog.budget()`)

| Quantity | Value | Meaning |
|---|---|---|
| `v_at_mccan_min` | 3.057 V | rail at the MCCAN board at 600 mA, worst-case regulator, LM66100 and cable drop (ESP32 min 3.0 V) |
| `u3_watts` | 1.23 W | AMS1117 dissipation at 600 mA from 5.25 V |
| `u3_tj_c` | 111.1 °C | U3 junction at a 25 °C bench, θ 70 °C/W on the 200 mm² heatsink pour (limit 125 °C) |
| `misplug_ma` | R3 0.71, R4 7.11, R5 12.37, R6 12.37 mA | worst current through each series resistor with the cable reversed |
| `rxd_backfeed_ma` | 0.604 mA | ESP32 TX back into the unpowered CH343P's RXD |
| `en_hold_v` | 3.24 V | MCCAN EN with the programmer attached and unpowered (buffer outputs off) |
| `en_hold_v_without_buffer` | 2.235 V | what EN would sit at without U5: marginal, so U5 is there |

## Decided here

| Decision | Why |
|---|---|
| CH343P (C2846043), fallback CH9102F (C2858418) | CDC-ACM: no driver install (spec 6.5) |
| AMS1117-3.3 + LM66100 ideal diode | ≥ 600 mA; no back-current when both boards are powered (spec 6.3) |
| SN74LVC2G125 on DTR/RTS | unpowered programmer would otherwise hold EN at ~2.2 V (budget above) |
| USBLC6-2SC6 on D+/D− | USB ESD (spec 6.7) |
| R3 4.7k in ESP32 TX → CH343 RXD, R4 470 in CH343 TXD → ESP32 RX, R5/R6 270 on DTR/RTS | misplug and back-feed currents above; 270 not 220 keeps DTR/RTS ≤ 15 mA |
| PWR LED yellow-green KT-0603YG (C2289), RX LED yellow KT-0603Y (C2287) | the planned green/yellow were out of stock; pure green's 3.1 V Vf is too high for 3.3 V through 1k |
| 2 layers, 20 × 40 mm, all parts top | spec 6.7 |
| GND poured both sides; +3V3_USB heatsink 200 mm² on F+B with six thermal vias | U3's 1.23 W |
| USB pair hand-routed; other nets by an in-repo deterministic grid router | the router's output is graded by DRC and `check_board.py` like any copper |
| Power tracks 0.5 mm, necking to 0.3 mm only within 1.5 mm of a fine-pitch pin | `check_board.thin_power_tracks` |
| USB pair: ≤ 2 vias per line, skew ≤ 5 mm, length ≤ 30 mm (actual 19.2 / 22.4 mm) | full-speed USB (12 Mb/s, ≥ 4 ns edges): 3 mm of skew is ~20 ps |
| References on F.Fab; silk carries J2 net names, LED functions, "MCCAN PROG A" | spec 6.7 labels by function; `assembly.pdf` carries the references |
| DRU: J1 land pattern 0.12 mm; J1 silk may meet the edge; one thermal spoke allowed | the receptacle's pads and mouth are fixed by the part; C6/C7 GND pads each have their own via |
| CPL places J1 and J2 at their pad centres | KiCad's origin for both is not the body centre JLCPCB expects |

Every ruling made while building it, with what it costs if wrong, is in the branch's history
and the final report on the branch.

## Ordering (with the MCCAN boards, spec 10)

Upload `output/jlcpcb/gerbers.zip`, `bom.csv` and `cpl.csv` **in the same JLCPCB order as the
MCCAN boards** — the MCCAN order waits for this board.

- **5 pcs, 2 layers, 1.6 mm FR-4**, green mask, HASL or ENIG.
- **PCB assembly: standard, top side.** Add the **through-hole service for J2** (the 1×6 header).
- **Check EVERY row of `output/jlcpcb/rotation-review.txt` in JLCPCB's placement preview**
  before paying. No rotation offset has been checked against JLCPCB: U1–U5 pin 1, D1–D3 cathode
  (towards J1), J1 and J2 on their pads.
- **Re-run the stock check the day the order is placed:**
  `python scripts/check_stock_prog.py --boards 5` (the copy in `output/jlcpcb/stock.txt` is
  from when the package was cut).
- Read JLCPCB's DFM report before paying.

## Buy separately (spec 7)

- A **6-way female-to-female 2.54 mm jumper cable, straight-through, 10–20 cm**. Buy spares.
- A **USB-C cable** (data, not charge-only).

## Bench acceptance (when the boards arrive)

- [ ] USB only: the PWR LED lights, and the laptop sees a serial port with no driver install.
- [ ] Programmer on an MCCAN board, USB only: `py -3.13 -m platformio run -t upload` flashes
      with no button presses; the serial monitor shows the boot log; the WiFi access point
      appears.
- [ ] MCCAN board on its bench supply, programmer plugged in: no current flows back into the
      programmer (measure at its output; it may be supplying part of the load), the rail stays
      between 3.2 and 3.4 V, and flashing still works.
- [ ] Cable reversed at one end, USB connected, for 10 s: neither board is damaged; the ESP32
      is held in reset; with the cable put right, the flashing step passes again.
- [ ] Output shorted to ground for 10 s: the programmer recovers when the short is removed.
- [ ] Programmer attached, **USB unplugged**, MCCAN board on its bench supply: the ESP32 keeps
      running (no reset): plug USB back in and the serial log carries on with no new boot
      banner.

## First flash: install the real OTA key

The firmware's OTA public key (`src/domain/update_pubkey.h`) is still the all-zero
placeholder, so OTA refuses every update until a keyed build is flashed over J2. Make the
first flash over this programmer a build with the real key: run
`python tools/sign_update.py keygen`, keep the private key safe (not in git), build, and
upload over J2. After that, J2 is the recovery path when OTA cannot be used.
