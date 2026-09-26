# MCCAN Hardware

KiCad 10.0.2 project for the ESP32 MCCAN lighting controller.
Spec: `../docs/superpowers/specs/2026-09-11-esp32-mccan-pcb-hardware-design.md`
Plan: `../docs/superpowers/plans/2026-09-11-esp32-mccan-pcb-hardware.md`

## kicad-cli is not on PATH

Bash:       "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" <args>
PowerShell: & "C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" <args>

## Verification gates

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
| power_input | Single feed: 10 A fuse, P-FET, TVS, pi+CM filter -> VBAT. Second feed + Schottky OR as DNP footprints |
| rails | Sync boost, low-Iq buck, 3V3 load switch |
| mcu_can | ESP32 module, TJA1042, programming header, status LED |
| outputs | PCA9685, **12x MOSFET + 1 ohm shunt (2512, >=1 W), 12x 10k series + clamp, ADG706 16:1 mux**, dual PROFET, PTCs, connectors |

## Net naming contract

Sheets connect ONLY through these names. See the plan's Global Constraints for the
full list and for the mandatory passive-default biasing table.

**Pin assignment — use exactly these**

| Net | GPIO | Constraint |
|---|---|---|
| `CAN_RXD` | 35 | Input-only **and RTC-capable** — EXT0 wake |
| `IGN_SENSE` | 36 | RTC-capable — EXT1 `ANY_HIGH` wake |
| `CAN_TXD` | 17 | |
| `CAN_STB` | 14 | RTC-capable |
| `I2C_SDA` / `I2C_SCL` | 21 / 22 | |
| `PWM_DEN_A` / `PWM_DEN_B` | 18 / 19 | LEDC |
| `RGB_ISNS` (mux output) | 32 | **ADC1_CH4** — RGB sense chain |
| `MUX_S0` / `S1` / `S2` / `S3` | 23 / 4 / 16 / 5 | GPIO 5 is a strapping pin — pulldown mandatory |
| `ISNS_DEN` (**one** multiplexed output) | 34 | **ADC1 only** — ADC2 fails while WiFi is active |
| `DEN_DSEL` — PROFET channel select | 33 | **ADDED (C1)** — the BTS7008-2EPA has ONE `IS` output |
| `EN_BOOST` | 25 | |
| `EN_3V3SW` | 26 | |
| `EN_DIAG` | 27 | |
| `LED_STAT` | 13 | |
| Programming | 0, 1, 3, EN | Reserved |

Spare: GPIO 2, 12, 15, **39**. Never use GPIO 6–11 (flash).

**GPIO 37 and 38 do not exist on WROOM-32 modules** — they are not bonded out. Leave GPIO 12
unused: it selects flash voltage at boot.

**Passive-default biasing — mandatory on every one of these nets**

| Net | Bias | Floating state |
|---|---|---|
| `EN_BOOST` | pulldown to GND | Boost off |
| `EN_3V3SW` | pulldown to GND | Peripheral rail off |
| `CAN_STB` | pull-up to VIO | Transceiver in standby |
| All 14 `PWM_*` | pulldown to GND | All outputs off |
| **`IGN_SENSE`** | **pulldown, ALWAYS POPULATED** | **Defined low.** GPIO 34–39 have NO internal pulls and EXT1 `ANY_HIGH` is armed here — floating, it wakes the board on noise (C2) |
| `DEN_DSEL` | pulldown to GND | Defined channel selection |
| **`EN_DIAG`** (GPIO 27) | **pulldown to GND** | PROFET Sleep mode needs ALL of `INn`/`DEN`/`DSEL` low; GPIO 27 is not RTC-capable so it floats in sleep |
| `MUX_S0`–`S3` | pulldown to GND | Defined channel; **required on GPIO 5** (strapping pin) |

**Net naming contract** — sheets connect only through these names. Use them exactly.

```
Power:    VBAT  VLOGIC_IN  +3V3_ALW  +3V3_SW  +5V  +24V  GND
          (VBAT_B exists only on the DNP second-feed footprints — spec 4.4)
Per-str:  +24V_FL  +24V_FR  +24V_RL  +24V_RR          (after each PTC)
RGB PWM:  PWM_FL_R PWM_FL_G PWM_FL_B PWM_FR_R PWM_FR_G PWM_FR_B
          PWM_RL_R PWM_RL_G PWM_RL_B PWM_RR_R PWM_RR_G PWM_RR_B
RGB ret:  RET_FL_R RET_FL_G RET_FL_B RET_FR_R RET_FR_G RET_FR_B
          RET_RL_R RET_RL_G RET_RL_B RET_RR_R RET_RR_G RET_RR_B
Denali:   PWM_DEN_A PWM_DEN_B  DEN_A_OUT DEN_B_OUT  ISNS_DEN  DEN_DSEL
Control:  EN_BOOST EN_3V3SW EN_DIAG LED_STAT IGN_SENSE
          (EN_3V3SW gates BOTH +3V3_SW and +5V — one enable, no extra GPIO)
Bus:      I2C_SDA I2C_SCL
Sense:    SENSE_FL_R SENSE_FL_G SENSE_FL_B SENSE_FR_R SENSE_FR_G SENSE_FR_B
          SENSE_RL_R SENSE_RL_G SENSE_RL_B SENSE_RR_R SENSE_RR_G SENSE_RR_B
          MUX_S0 MUX_S1 MUX_S2 MUX_S3  RGB_ISNS
CAN:      CAN_TXD CAN_RXD CAN_STB CANH CANL
Prog:     UART_TX UART_RX BOOT_N EN_MCU
```

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
