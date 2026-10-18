# MCCAN Hardware

KiCad 10.0.2 project for the ESP32 MCCAN lighting controller.
Spec: `../docs/superpowers/specs/2026-09-11-esp32-mccan-pcb-hardware-design.md`
Plan: `../docs/superpowers/plans/2026-09-11-esp32-mccan-pcb-hardware.md`

## kicad-cli is not on PATH

Bash:       "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" <args>
PowerShell: & "C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" <args>

## Verification gates

ERC applies to the current schematic. The DRC commands below apply to the abandoned plan3 board
until the layout phase produces a new one.

ERC (must exit 0):
  "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch erc \
    --severity-error --exit-code-violations \
    -o output/erc.rpt mccan.kicad_sch

DRC — run BOTH severities, and read the counts in the report body, not the exit code:

  "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" pcb drc \
    --severity-error --schematic-parity --exit-code-violations \
    --refill-zones -o output/drc.rpt mccan.kicad_pcb

  "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" pcb drc \
    --severity-all --schematic-parity --exit-code-violations \
    --refill-zones -o output/drc-all.rpt mccan.kicad_pcb

`--severity-error` alone is NOT the gate, and was the whole of it until Task 10. It discards
every finding whose rule sits at `warning`, and KiCad's stock project file puts 29 of its 62
rules there. On the board committed before `80fe282` that gate printed "Found 0 violations"
while `--severity-all` printed 28 — 15 `connection_width` and 13 `via_dangling`, one of the
`connection_width` findings a 0.059 mm neck at an eFuse gate pad. Every "DRC: 0 errors" on
this branch before that commit was measured through that filter.

`scripts/gen_netclasses.py` now promotes the seven rules that can fail THIS board to `error`
(see its `SEVERITIES`), so today the two runs agree. That agreement is a property of the
current KiCad rule set, not of the gate: a KiCad upgrade that adds a rule defaulting to
`warning` would make the `--severity-error` run blind again with no signal at all. Hence both.

Neither run's exit code is the pass/fail signal on its own — `kicad-cli` exits 5 whenever any
unconnected pad exists, and this board carries 11 accepted ones. The gate is the count in the
report body: it must match the accepted residual, currently 9 violations (all `via_dangling`),
11 unconnected pads, 0 footprint errors, at BOTH severities.

## Board setup decisions

Minimum connection width is 0.20 mm, tied to minimum track width.

  This section used to read "0.15 mm, not 0.25 mm ... minimum track width stays 0.25 mm",
  which was the six-layer board's setting and is three wrong figures now: both rules are
  0.20 mm today (`scripts/gen_netclasses.py`'s `RULES`, and `mccan.kicad_pro`).

  The two ARE tied on purpose. min_connection is the narrowest copper that may carry a
  connection, so setting it above the thinnest track the board permits makes every
  legitimately necked track a violation of a rule the same file grants -- two 0.20 mm
  tracks meeting at 45 degrees neck to 0.20 * cos(22.5) = 0.185 mm at the joint. The
  earlier note reached for the fabricator's limit instead, which is what the SCOPED
  plane-pour exception in `mccan.kicad_dru` is for, not what this rule is for. See the
  long `min_connection` note in `scripts/gen_netclasses.py`.

Reference designators are on F.Fab, except J*, F*, TP*, U*, Q*, D* and L*.

  233 parts on 140 x 100 mm leaves no room for 1 mm text: all 398 silkscreen warnings were
  Reference fields over a pad, over a neighbour's outline, or over another Reference, and
  none was between two real silk graphics.  Value was already on F.Fab, so the assembly
  drawing carries a fully labelled copy either way.  What stays on the silkscreen is what
  someone has to find on a finished board by eye -- connectors, fuses, test points and the
  semiconductors worth probing -- plus the outlines, pin-1 dots and polarity marks.

## Sheet responsibilities

| Sheet | Contents |
|---|---|
| power_input | Feed A (J1): LTC4380 U10 surge stopper with Q10/Q11 (no board fuse; the fuse is in the harness), 24 V TVS, pi + CM filter -> `VBAT`. Feed B (J9): SQJ461EP P-FET Q13 for reverse polarity, 15 V gate zener D24, 24 V TVS D25 -> `VBAT_B`, no filter, no LTC4380. `GND_B` meets `GND` only at net-tie NT1 |
| rails | Low-Iq buck -> `+3V3_ALW`, gated `+5V` (`EN_5V`). No boost and no `+3V3_SW` |
| mcu_can | ESP32-WROOM-32E, TJA1042T/3 (listen-only, TXD pulled up, no MCU link), programming header, status LED, 4.7 k series resistors on the diagnostic lines |
| outputs | Three TPS4H160-Q1 quads U11-U13 (D1: 12 channels, 10 used, 2 spare), harness tails J3 (front, 5), J4 + J5 (rear, 4 + 3), CAN tail J8. The aux/pod switch is **not drawn**: it waits on the Oxford kit |

The pin map and net names are the generators' (`scripts/gen_*.py`, `scripts/quadpins.py`) and the
netlist `output/netlist.net`. The plan3 pin tables that used to be here (PCA9685, mux, ignition
sense, PWM nets) described a board that no longer exists and have been removed.

### ESP32 pin rules that still hold

- GPIO 6-11 are the module's flash and are unusable. GPIO 37 and 38 are not bonded out.
- GPIO 34-39 are input-only and have **no internal pulls**. Here: 34 `SNS_A`, 35 `CAN_RXD`
  (RTC, EXT1 wake), 36 `SNS_B`, 39 `SNS_C`.
- ADC2 fails while Wi-Fi is up, so the sense inputs are all ADC1.
- Strapping pins, and what this board ties them to:
  - GPIO 0 is `BOOT_N`: the BOOT button SW1 and the auto-reset transistor Q3.
  - GPIO 2 is `DIAG_EN`: 4.7 k series, with R33 10 k pull-down on the chip side. It must be low
    for download, and the same pull-down holds the switches' `DIAG_EN` low.
  - GPIO 5 and 15 are `DIAG_SEL0` / `DIAG_SEL1`: 4.7 k series, **no pull** (their level is
    irrelevant while `DIAG_EN` is low, and a pull-down on GPIO 15 would mute the boot log).
  - GPIO 12 is `IO12_STRAP`: R36 10 k to GND (flash voltage select; also the firmware's TWAI TX pin).
- No lamp output sits on a strapping pin or on GPIO 14.

## Phase-A board status (2026-10-18)

The **schematic** is complete except the kit-gated aux/pod switch. The **layout has not started**.

- `mccan.kicad_pcb` and `output/gerbers/` are the **abandoned plan3 board**. They no longer match
  the schematic and must not be fabricated or used as a layout starting point. The DRC commands
  and counts under "Verification gates" describe that board.
- `scripts/layout_*.py` and `scripts/route_*` (also `routes_signal.json`) still reference plan3
  parts that phase A deleted -- `layout_pcb.py` lists refs such as U7, U8, U9, J6 and J7 -- and
  must be reworked in the layout phase. Do not run them, or `gen_pcb.py`, until then.

### Layout-phase notes

- **U10 (LTC4380) `ON` is deliberately left open** on its internal 1 Mohm pull-up. The layout must
  keep that pin's leakage to ground under 1 uA (LTC4380 Rev. C, Pin Functions): no flux-prone
  gap, guard or close ground copper beside the pad.
- `NT1` is the deliberate `GND_B` / `GND` star point; place it deliberately (spec §4.1.1).
- `R100` sets about 9 A behind a 4 A fuse and is re-sized once pod inrush is measured (spec §9.1 item 2a).

> The two sections below, "Project status (Task 1)" and the 2026-09-11 revision, are plan3 history
> kept for the record; the phase-A status above supersedes them.

## Project status (Task 1)

Hierarchical sheets ARE wired: the root schematic (`mccan.kicad_sch`) places four
`(sheet ...)` instances (`power_input`, `rails`, `mcu_can`, `outputs`), each pointing at
its file under `sheets/`. This was authored as text — no KiCad GUI session was available —
and verified structurally sound by running `kicad-cli sch erc`, whose report walked into
all four child sheets (`Sheet /power_input/`, `Sheet /mcu_can/`, `Sheet /rails/`,
`Sheet /outputs/`) with 0 errors. No components are placed on any sheet yet; that begins
in Task 3.

There is no `mccan.kicad_pcb` yet, so the DRC gate above cannot be run until PCB layout
(Task 8) creates one. The command is documented here now because the net naming and
sheet contracts it will check are fixed as of this task.

## Verified gate: ERC (Task 1, empty project)

Command:
```
cd hardware && "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch erc \
  --severity-error --exit-code-violations -o output/erc.rpt mccan.kicad_sch
```

Result: `exit=0`, "Found 0 violations". Report saved at `output/erc.rpt`. This is expected
at this stage — it proves the gate command and the hierarchical project structure work,
not that any design is correct (there is no design yet).

## REVISION 2026-09-11 — RGB output stage redesigned

Datasheet verification failed the octal smart low-side switches: ON-state open-load detection does
not exist in that part category (TLE8110ED's open-load code is OFF-mode only, and it is a VDS
comparator with no load-current threshold at all). The RGB stage is now:

- **12 discrete logic-level N-MOSFETs**, gates driven straight from PCA9685 LED0-11
- **1 ohm shunt in each FET source leg** -> 12 `SENSE_*` nets
- **16:1 analog mux** (`MUX_S0`-`S3`) -> `RGB_ISNS` -> GPIO 32 (ADC1_CH4)
- 140 mV at full channel current; ADC at 0 dB attenuation (0-1.1 V range)
- Classification is open / working / shorted, not precision metering
- Sampling is on-demand: drive a channel to 100%, step the mux, read, advance

**There is no SPI on this board** — the switch ICs were its only devices. Dropping it freed the
GPIO that made the sense chain fit.

**A 5 V rail is mandatory**: TJA1042 VCC is 4.5-5.5 V. The "/3" suffix provides VIO for 3.3 V logic
levels; it does not make VCC 3.3 V. **It is ENABLE-GATED off in sleep**, sharing `EN_3V3SW` with
`+3V3_SW` — the transceiver's low-power receiver detects bus activity on **VIO alone**, so VCC is
needed only for normal mode. VIO stays on `+3V3_ALW`.

Authority: `../docs/superpowers/specs/2026-09-11-esp32-mccan-pcb-hardware-design.md` sections 5.1,
6 and 7.3.
