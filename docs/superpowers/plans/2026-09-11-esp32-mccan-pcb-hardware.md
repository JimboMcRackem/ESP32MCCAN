# ESP32 MCCAN PCB / Hardware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a fab-ready 4-layer PCB — schematic, layout, BOM, fabrication outputs — plus
enclosure and harness documentation and a bring-up procedure, for the ESP32 MCCAN motorcycle
lighting controller.

**Architecture:** Dual 12 V feed with domain-split protection; synchronous boost to 24 V for four
common-anode RGB COB strings switched low-side through discrete MOSFETs with a shunt/mux/ADC
per-channel diagnostic chain;
Denali D4 2.0 pair switched high-side through a dual PROFET; ESP32-WROOM-32E-N8 with a PCA9685
generating RGB PWM and LEDC generating Denali PWM; deep sleep with wake on CAN bus activity.

**Tech Stack:** KiCad 10.0.2 (`kicad-cli` for automatable ERC/DRC/fab-output gates), markdown
design records committed alongside the design files.

**Spec:** `docs/superpowers/specs/2026-09-11-esp32-mccan-pcb-hardware-design.md`

---

## How this plan differs from a software plan

**There is no unit-test cycle for hardware.** Rather than pretend otherwise, every task below
ends in a **verification gate** that is either a real command (`kicad-cli ... --exit-code-violations`)
or an explicit written acceptance record committed to the repo. The TDD discipline is preserved in
substance: **write the acceptance criterion before doing the work, then prove it.** Where a step
says "record the measured value", a missing or failing value blocks the task exactly as a red test
would.

**Task 2 is a hard gate on the whole plan.** It verifies part datasheets against the spec's
requirements, including one genuine go/no-go (open-load detection threshold versus 0.14 A). If
that fails, **stop and revise the spec** — do not proceed to schematic capture with a part that
cannot deliver the diagnostics the design is built around.

---

## REVISION 2026-09-11 — read before any task

Task 2b's datasheet verification **failed the row 1.1 go/no-go category-wide**, and the spec was
revised in response (commit `99add32`). Three changes propagate through every later task:

1. **The RGB output stage is 12 discrete logic-level MOSFETs**, not octal smart low-side switches.
   Diagnostics come from a **1 Ω shunt in each FET source leg → 16:1 analog mux → one ADC1 input**.
2. **There is no SPI on this board.** The switch ICs were its only devices. Any step below that
   mentions SPI nets, daisy-chaining, or SPI diagnostics is void — follow the revised text.
3. **A 5 V rail is mandatory** (TJA1042 VCC is 4.5–5.5 V; the "/3" suffix is VIO only). Four power
   domains, not three.

Pin allocation changed accordingly: Denali PWM moved to 18/19, freeing **GPIO 32 (ADC1_CH4)** for
the mux output, with mux select on 23/4/16/5. **GPIO 37/38 do not exist on WROOM-32 modules** — an
earlier revision listed 38 as spare in error, which is what forced this reshuffle.

The spec (§5.1, §6, §7.3) is the authority. Where this plan's task text still reflects the old
design, the spec wins.

---

## Global Constraints

Copy these values verbatim; every task's requirements implicitly include this section.

**Toolchain**
- `kicad-cli` is NOT on PATH. Always invoke by full path:
  `"/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"` (Bash) or
  `& "C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"` (PowerShell)
- Repo root: `D:\Projects\ESP32MCCAN`. All hardware files live under `hardware/`.

**Electrical — exact values from the spec**
- Feed A: 12 V, **3.9 A** (boost + logic), **7.5 A** fuse, 61% margin on a 10 A outlet
- Feed B: 12 V, **6.6 A** (Denali D4 2.0 pair), **10 A** fuse, 34% margin
- System total **10.5 A / ~128 W**. Feeds are **domain-split, never paralleled**
- RGB rail: **24 V**, boost design point **60 W / 2.5 A**, actual load 40 W
- Per RGB channel: **0.14 A**. Per RGB string (white): **0.42 A**. Per Denali channel: **3.3 A**
- Sleep budget target **< 200 µA**, hard ceiling **500 µA**
- All input front-end parts rated **≥ 40 V**; both switchers rated **40–60 V** input
- TVS standoff **~24 V**; RGB MOSFET **Vds ≥ 40 V**, fully enhanced at **Vgs = 3.3 V**
- **5 V rail mandatory** (TJA1042 VCC is 4.5–5.5 V), always on and low quiescent
- RGB sense: **1 Ω** shunt per channel = **140 mV** at 0.14 A; ADC at **0 dB attenuation** (0–1.1 V)
- PWM: RGB **400 Hz** (PCA9685), Denali **150 Hz** (ESP32 LEDC)
- Total internal dissipation target **~3.6 W**
- Stackup: **4 layers**, signal / GND / power / signal, **2 oz outer copper**
- Feed B power polygon: **≥ 4–5 mm** width at 2 oz for a 10 °C rise at 6.6 A

**Firmware-imposed, non-negotiable**
- `ChannelIndex` (`src/domain/channel_map.h`) fixes PWM ordering. PCA9685 **LED0–11** =
  front-left RGB, front-right RGB, rear-left RGB, rear-right RGB **in that order**.
  PCA9685 LED12–15 **unused**.
- Denali PWM comes from **ESP32 LEDC**, not the PCA9685 — the PCA9685 prescaler is global and
  cannot serve 400 Hz and 150 Hz simultaneously.

**Pin assignment — use exactly these**

| Net | GPIO | Constraint |
|---|---|---|
| `CAN_RXD` | 35 | Input-only **and RTC-capable** — EXT0 wake |
| `IGN_SENSE` | 36 | RTC-capable — EXT1 `ANY_HIGH` wake |
| `CAN_TXD` | 17 | |
| `CAN_STB` | 14 | RTC-capable |
| `I2C_SDA` / `I2C_SCL` | 21 / 22 | |
| `PWM_DEN_A` / `PWM_DEN_B` | 18 / 19 | LEDC (moved off 32/33 — see REVISION note) |
| `ISNS_DEN_A` / `ISNS_DEN_B` | 34 / 39 | **ADC1 only** — ADC2 fails while WiFi is active |
| `RGB_ISNS` (mux output) | 32 | **ADC1_CH4** — the §5.1 diagnostic chain |
| `MUX_S0` / `S1` / `S2` / `S3` | 23 / 4 / 16 / 5 | GPIO 5 is a strapping pin — pulldown mandatory |
| `EN_BOOST` | 25 | |
| `EN_3V3SW` | 26 | |
| `EN_DIAG` | 27 | |
| `LED_STAT` | 13 | |
| Programming | 0, 1, 3, EN | Reserved |

Spare: GPIO 2, 12, 15, 33. Never use GPIO 6–11 (flash). **GPIO 37/38 do not exist on WROOM-32
modules** — an earlier revision wrongly listed 38 as spare. Leave GPIO 12 unused: it selects flash
voltage at boot.

**Passive-default biasing — mandatory on every one of these nets**

| Net | Bias | Floating state |
|---|---|---|
| `EN_BOOST` | pulldown to GND | Boost off |
| `EN_3V3SW` | pulldown to GND | Peripheral rail off |
| `CAN_STB` | pull-up to VIO | Transceiver in standby |
| All 14 `PWM_*` | pulldown to GND | All outputs off |
| `MUX_S0`–`S3` | pulldown to GND | Defined channel; **required on GPIO 5** (strapping pin) |

**Net naming contract** — sheets connect only through these names. Use them exactly.

```
Power:    VBAT_A  VBAT_B  VLOGIC_IN  +3V3_ALW  +3V3_SW  +24V  GND
Per-str:  +24V_FL  +24V_FR  +24V_RL  +24V_RR          (after each PTC)
RGB PWM:  PWM_FL_R PWM_FL_G PWM_FL_B PWM_FR_R PWM_FR_G PWM_FR_B
          PWM_RL_R PWM_RL_G PWM_RL_B PWM_RR_R PWM_RR_G PWM_RR_B
RGB ret:  RET_FL_R RET_FL_G RET_FL_B RET_FR_R RET_FR_G RET_FR_B
          RET_RL_R RET_RL_G RET_RL_B RET_RR_R RET_RR_G RET_RR_B
Denali:   PWM_DEN_A PWM_DEN_B  DEN_A_OUT DEN_B_OUT  ISNS_DEN_A ISNS_DEN_B
Control:  EN_BOOST EN_3V3SW EN_DIAG LED_STAT IGN_SENSE
Bus:      I2C_SDA I2C_SCL
Sense:    SENSE_FL_R SENSE_FL_G SENSE_FL_B SENSE_FR_R SENSE_FR_G SENSE_FR_B
          SENSE_RL_R SENSE_RL_G SENSE_RL_B SENSE_RR_R SENSE_RR_G SENSE_RR_B
          MUX_S0 MUX_S1 MUX_S2 MUX_S3  RGB_ISNS
CAN:      CAN_TXD CAN_RXD CAN_STB CANH CANL
Prog:     UART_TX UART_RX BOOT_N EN_MCU
```

**Commit discipline:** commit at the end of every task, and at each intermediate commit step
shown. Never leave a task's work uncommitted.

---

## File Structure

| Path | Responsibility |
|---|---|
| `hardware/README.md` | How to open the project, invoke `kicad-cli`, regenerate outputs |
| `hardware/mccan.kicad_pro` | KiCad project |
| `hardware/mccan.kicad_sch` | Root schematic — sheet instances only, no components |
| `hardware/sheets/power_input.kicad_sch` | Both feeds: fuses, P-FETs, TVS, π+CM filters, Schottky OR |
| `hardware/sheets/rails.kicad_sch` | Sync boost, low-Iq buck, 3V3 load switch |
| `hardware/sheets/mcu_can.kicad_sch` | ESP32 module, TJA1042, programming header, status LED |
| `hardware/sheets/outputs.kicad_sch` | PCA9685, 12× MOSFET + shunt, 16:1 mux, dual PROFET, PTCs, connectors |
| `hardware/mccan.kicad_pcb` | Board layout |
| `hardware/docs/part-selection.md` | Verification record: every part vs every spec criterion |
| `hardware/docs/enclosure.md` | Box, heat-spreader plate, panel layout, vent, mounting |
| `hardware/docs/harness.md` | Cable spec, connector pinouts, corner colour coding |
| `hardware/docs/bring-up.md` | Staged bring-up procedure with blank measurement tables |
| `hardware/output/` | Generated gerbers, drill, BOM, CPL (regenerable; committed for the record) |

Four schematic sheets rather than one, split by responsibility so each is reviewable on its own
and a reviewer can reject one without rejecting its neighbours.

---

## Task 1: Hardware project scaffolding

**Files:**
- Create: `hardware/README.md`
- Create: `hardware/mccan.kicad_pro`, `hardware/mccan.kicad_sch`
- Create: `hardware/sheets/` (empty sheets for the four blocks)
- Create: `hardware/.gitignore`

**Interfaces:**
- Consumes: nothing
- Produces: a KiCad project that `kicad-cli sch erc` runs against without crashing; the four
  sheet files that Tasks 3–6 populate; the net naming contract documented in `README.md`

- [ ] **Step 1: Write the acceptance criterion first**

Create `hardware/README.md` containing, before any design work:

```markdown
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

DRC (must exit 0, includes schematic parity):
  "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" pcb drc \
    --severity-error --schematic-parity --exit-code-violations \
    --refill-zones -o output/drc.rpt mccan.kicad_pcb

## Sheet responsibilities

| Sheet | Contents |
|---|---|
| power_input | Both feeds: fuses, P-FETs, TVS, pi+CM filters, Schottky OR |
| rails | Sync boost, low-Iq buck, 3V3 load switch |
| mcu_can | ESP32 module, TJA1042, programming header, status LED |
| outputs | PCA9685, 12x MOSFET + shunt, 16:1 mux, dual PROFET, PTCs, connectors |

## Net naming contract

Sheets connect ONLY through these names. See the plan's Global Constraints for the
full list and for the mandatory passive-default biasing table.
```

Copy the full net naming contract from this plan's Global Constraints into the README.

- [ ] **Step 2: Create the KiCad project and four empty hierarchical sheets**

Open KiCad, create project `hardware/mccan`, and in the root schematic place four hierarchical
sheets named exactly `power_input`, `rails`, `mcu_can`, `outputs`, with filenames under
`sheets/`. Place no components yet. The root sheet holds sheet instances only.

- [ ] **Step 3: Create `hardware/.gitignore`**

```gitignore
*-backups/
*.kicad_prl
fp-info-cache
~*
*.lck
```

Note: `output/` is deliberately NOT ignored — fabrication outputs are committed for the record.

- [ ] **Step 4: Run the ERC gate and verify it passes on an empty project**

```bash
mkdir -p hardware/output
cd hardware && "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch erc \
  --severity-error --exit-code-violations -o output/erc.rpt mccan.kicad_sch; echo "exit=$?"
```

Expected: `exit=0`. This proves the gate command itself works before there is any design to
break it. If it is nonzero on an empty project, fix the project setup now — otherwise you cannot
distinguish tool problems from design problems later.

- [ ] **Step 5: Commit**

```bash
git add hardware/
git commit -m "hw: scaffold KiCad project, four sheets, and ERC/DRC gates"
```

---

## Task 2: Part selection and go/no-go verification — GATES THE WHOLE PLAN

**Files:**
- Create: `hardware/docs/part-selection.md`

**Interfaces:**
- Consumes: spec §11 verification items; spec §2–§7 electrical requirements
- Produces: a committed decision record naming the **exact manufacturer part number** for each
  function below. Tasks 3–6 place only parts named here. The net names each part connects to are
  fixed by the Global Constraints net contract.

**Why this task exists:** the spec is built on the assumption that per-channel diagnostics are
available on the RGB side. That assumption is unverified and may be false. Find out before
drawing anything.

- [ ] **Step 1: Write the acceptance criteria BEFORE looking at any datasheet**

Create `hardware/docs/part-selection.md` with this table filled in only in the "Required" column.
Leave "Actual" and "Verdict" blank — you fill them in Step 2. Writing the criteria first is what
stops a convenient part from redefining the requirement.

```markdown
# Part Selection Verification Record

Every criterion below comes from the spec. A part may be chosen ONLY if every
row for it reads PASS. Candidate families are suggestions, not decisions.

## 1. RGB output stage (REVISED 2026-09-11) — discrete MOSFET + sense chain
Replaces the octal smart low-side switches, whose row 1.1 failed category-wide.
Three part classes to verify: the FET, the sense resistor, the analog mux.

### 1a. Logic-level N-MOSFET (12 required)
| # | Required | Actual | Verdict |
|---|---|---|---|
| 1a.1 | Vds >= 40 V (24 V rail plus transients) | | |
| 1a.2 | **Fully enhanced at Vgs = 3.3 V** — Rds(on) specified AT or BELOW 3.3 V Vgs, not only at 4.5/10 V | | |
| 1a.3 | Id >= 1 A continuous | | |
| 1a.4 | Rds(on) at 3.3 V Vgs gives <= 5 mW per channel at 0.14 A | | |
| 1a.5 | Gate charge low enough to switch cleanly at 400 Hz from a PCA9685 output (25 mA sink / 10 mA source) | | |
| 1a.6 | In stock, multi-source | | |

### 1b. Sense resistor (12 required)
| # | Required | Actual | Verdict |
|---|---|---|---|
| 1b.1 | 1 ohm, tolerance <= 1% (tolerance sets channel-to-channel reading spread) | | |
| 1b.2 | Power rating >= 50 mW with margin (dissipates 20 mW at 0.14 A) | | |
| 1b.3 | Temperature coefficient low enough that drift does not swamp open/working/short classification | | |

### 1c. 16-channel analog multiplexer (1 required)
Candidates: CD74HC4067, ADG706, MAX4617 family
| # | Required | Actual | Verdict |
|---|---|---|---|
| 1c.1 | 16 channels, single-ended, 4 binary select lines | | |
| 1c.2 | Operates from 3.3 V | | |
| 1c.3 | **On-resistance low enough not to corrupt a 140 mV reading** into the ESP32 ADC's input impedance | | |
| 1c.4 | Off-channel leakage small enough not to shift a 140 mV reading measurably | | |
| 1c.5 | Channel-to-channel on-resistance match (mismatch appears as per-channel offset) | | |
| 1c.6 | Settling time permits stepping 12 channels within a few ms sweep | | |

## 2. Dual smart high-side switch (1 required) — Denali
Candidate: Infineon BTS7008-2EPA or PROFET+2 12V family

| # | Required | Actual | Verdict |
|---|---|---|---|
| 2.1 | Continuous current per channel >= 3.3 A with margin | | |
| 2.2 | Current sense output resolves a 3.3 A load, ratio documented | | |
| 2.3 | 3.3 V logic compatible inputs (no level shifter needed) | | |
| 2.4 | PWM capable at 150 Hz | | |
| 2.5 | Integrated short-circuit, overcurrent, thermal shutdown | | |
| 2.6 | On-resistance gives <= 0.25 W for the pair at 3.3 A each | | |
| 2.7 | Standby current <= 20 uA | | |

## 3. Synchronous boost controller — 12 V to 24 V, 60 W
Candidate: TI LM5122-Q1

| # | Required | Actual | Verdict |
|---|---|---|---|
| 3.1 | Input rating 40-60 V (must exceed the 24 V TVS clamp voltage) | | |
| 3.2 | Synchronous (external FETs), efficiency >= 94% at 40 W out | | |
| 3.3 | Enable pin, 3.3 V logic compatible | | |
| 3.4 | Spread-spectrum or frequency dither available | | |
| 3.5 | Disabled-state current draw <= 10 uA, or gated externally | | |
| 3.6 | Dissipation at 40 W out <= 3 W including both FETs | | |

## 4. Low-quiescent buck — 12 V to 3.3 V, 1 A
Candidate: TI LM5164

| # | Required | Actual | Verdict |
|---|---|---|---|
| 4.1 | Quiescent current <= 30 uA (this is the dominant sleep contributor) | | |
| 4.2 | Output current >= 1 A (ESP32 WiFi TX peaks ~500 mA) | | |
| 4.3 | Input rating 40-60 V | | |
| 4.4 | Stable with no load (sleep condition) | | |

## 5. CAN transceiver
Candidate: NXP TJA1042T/3

| # | Required | Actual | Verdict |
|---|---|---|---|
| 5.1 | **GO/NO-GO:** standby mode signals bus wake-up by driving RXD LOW | | |
| 5.2 | VIO pin for 3.3 V logic (the /3 suffix) | | |
| 5.3 | Standby current <= 20 uA | | |
| 5.4 | TXD can be left pulled to VIO (recessive) with no fault latch | | |

## 6. Discretes

| # | Required | Actual | Verdict |
|---|---|---|---|
| 6.1 | P-FET: Vds >= 40 V, Rds(on) <= 10 mOhm, Vgs rated for 24 V jump | | |
| 6.2 | TVS: standoff ~24 V, clamp < 40 V, rated for the feed current | | |
| 6.3 | PTC: 0.5 A hold at 24 V, trip < 1 A, 4 required | | |
| 6.4 | Schottky OR pair: 40 V, >= 0.5 A, low leakage | | |
| 6.5 | Boost inductor: shielded, saturation current >= 1.5x peak | | |

## Sleep budget roll-up (spec 8.2: target < 200 uA, ceiling 500 uA)

| Contributor | Datasheet value | Source |
|---|---|---|
| ESP32 deep sleep | | |
| EXT0 RTC_PERIPH domain | | |
| CAN transceiver standby | | |
| Buck quiescent | | |
| Low-side switches standby | | |
| PROFET standby | | |
| P-FET gate + divider leakage | | |
| **TOTAL** | | |

## Final BOM decision

| Function | Manufacturer part number | Package | Unit price | Stock |
|---|---|---|---|---|
```

- [ ] **Step 2: Verify every row against real datasheets**

Work through each row. Record the actual figure and a PASS/FAIL verdict with the datasheet
section or page you read it from. Do not write PASS without a number beside it.

- [ ] **Step 3: Evaluate the two go/no-go rows and STOP if either fails**

Row **1.1** (open-load detection at 0.14 A) and row **5.1** (transceiver RXD wake signalling) are
go/no-go.

If **1.1 fails** on every candidate, **halt the plan and report back**. The options, in order of
preference, are:
1. Find a switch family with a lower open-load threshold
2. Add a low-value shunt plus comparator per channel (12 channels — expensive, probably not worth it)
3. Accept diagnostics on the Denali channels only, and record in the spec that RGB faults are
   not detectable — this is a **material reduction in what Approach 3 was chosen for** and needs
   the user's explicit agreement
4. Raise per-channel current by using shorter/parallel strip segments — changes the load, not the board

If **5.1 fails**, CAN wake is not achievable with that part; look at TJA1043 or TCAN1043, which
have richer low-power modes, and re-verify the sleep budget.

- [ ] **Step 4: Confirm the sleep budget roll-up is under 200 µA**

Sum the contributors. If the total exceeds the 500 µA ceiling, the design does not meet its
parking requirement — report back rather than proceeding. If it is between 200 and 500 µA, record
which contributor dominates and note it as accepted.

- [ ] **Step 5: Fill in the final BOM decision table**

One named manufacturer part number per function, with package, price and stock. Tasks 3–6 may
place only these parts.

- [ ] **Step 6: Commit**

```bash
git add hardware/docs/part-selection.md
git commit -m "hw: part selection verification record, all criteria verified against datasheets"
```

---

## Task 3: Schematic — power input sheet

**Files:**
- Modify: `hardware/sheets/power_input.kicad_sch`

**Interfaces:**
- Consumes: parts 6.1 (P-FET), 6.2 (TVS), 6.4 (Schottky) from `part-selection.md`
- Produces: hierarchical output pins `VBAT_A`, `VBAT_B`, `VLOGIC_IN`, `GND`. No other sheet may
  reference anything else from this sheet.

- [ ] **Step 1: Write the sheet's acceptance criteria as a comment block on the sheet**

Place a KiCad text box on the sheet stating what must be true when it is done:

```
ACCEPTANCE (spec 4.1-4.4):
- Two independent feeds. NO net connects VBAT_A to VBAT_B except the Schottky OR.
- Feed A: 7.5 A fuse, P-FET reverse polarity, 24 V TVS, pi + CM filter -> VBAT_A
- Feed B: 10 A fuse, P-FET reverse polarity, 24 V TVS, pi + CM filter -> VBAT_B
- Schottky OR: VBAT_A and VBAT_B -> VLOGIC_IN (logic survives either feed failing)
- All front-end parts rated >= 40 V
- Bulk capacitance on each VBAT rail
```

- [ ] **Step 2: Draw Feed A**

Panel fuse holder footprint → P-FET reverse-polarity stage (source to feed, drain to load, gate
to GND via resistor, Zener clamping Vgs) → TVS to GND → π filter (C–L–C) and common-mode choke →
bulk electrolytic + ceramic → net label `VBAT_A`.

- [ ] **Step 3: Draw Feed B identically, output `VBAT_B`**

Same topology, different fuse value (10 A) and a P-FET sized for 6.6 A rather than 3.9 A.

- [ ] **Step 4: Draw the Schottky OR**

Anode of each Schottky to `VBAT_A` and `VBAT_B` respectively; cathodes tied to `VLOGIC_IN`.
Add a ceramic to GND on `VLOGIC_IN`.

- [ ] **Step 5: Verify no accidental A↔B connection**

Run ERC, then visually trace: there must be **no** path between `VBAT_A` and `VBAT_B` other than
through the two Schottky diodes. A short here silently defeats the entire domain split and would
put both feeds on one load.

```bash
cd hardware && "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch erc \
  --severity-error --exit-code-violations -o output/erc.rpt mccan.kicad_sch; echo "exit=$?"
```

Expected: `exit=0` (unconnected hierarchical pins on the not-yet-drawn sheets may warrant
warnings, but no errors).

- [ ] **Step 6: Commit**

```bash
git add hardware/sheets/power_input.kicad_sch hardware/output/erc.rpt
git commit -m "hw(sch): dual-feed power input with domain split and Schottky logic OR"
```

---

## Task 4: Schematic — rails sheet

**Files:**
- Modify: `hardware/sheets/rails.kicad_sch`

**Interfaces:**
- Consumes: `VBAT_A`, `VLOGIC_IN`, `GND` from Task 3; parts 3 (boost), 4 (buck), 6.5 (inductor)
- Produces: `+24V`, `+3V3_ALW`, `+3V3_SW`, and input pins `EN_BOOST`, `EN_3V3SW`

- [ ] **Step 1: Write the sheet's acceptance criteria on the sheet**

```
ACCEPTANCE (spec 6, 3):
- Buck input from VLOGIC_IN (NOT VBAT_A) so logic survives either feed failing
- Buck -> +3V3_ALW, always on, >= 1 A, quiescent per part-selection row 4.1
- Load switch: +3V3_ALW -> +3V3_SW, controlled by EN_3V3SW
- EN_3V3SW pulldown to GND (floating = peripheral rail OFF)
- Sync boost input from VBAT_A -> +24V, 60 W design point, EN_BOOST
- EN_BOOST pulldown to GND (floating = boost OFF)
- Boost and buck both rated 40-60 V input
```

- [ ] **Step 2: Draw the low-Iq buck from `VLOGIC_IN` to `+3V3_ALW`**

Follow the chosen part's datasheet reference design exactly. Note the input is `VLOGIC_IN`, not
`VBAT_A` — this is what keeps the MCU alive when Feed A dies so it can report the fault.

- [ ] **Step 3: Draw the 3.3 V load switch to `+3V3_SW`**

Load switch from `+3V3_ALW` to `+3V3_SW`, enable from `EN_3V3SW`.
**Add a pulldown resistor on `EN_3V3SW`** per the passive-default table.

- [ ] **Step 4: Draw the synchronous boost from `VBAT_A` to `+24V`**

Controller per its datasheet reference design: high-side and low-side FETs, shielded inductor,
current-sense resistor, compensation network, bootstrap, soft-start, output bulk capacitance.
Enable from `EN_BOOST`, **with a pulldown resistor**.

Design the current-sense resistor for the **60 W / 2.5 A** design point, not the 40 W actual load.

- [ ] **Step 5: Add a text note recording the expected behaviour of the disabled boost**

```
NOTE: with EN_BOOST low, +24V sits near VBAT_A through the high-side FET body
diode. This is expected and benign: with all low-side switches off there is no
return path, so no current flows and the strings do not glow.
```

Recording this prevents a future reviewer "fixing" a non-bug.

- [ ] **Step 6: Run ERC and commit**

```bash
cd hardware && "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch erc \
  --severity-error --exit-code-violations -o output/erc.rpt mccan.kicad_sch; echo "exit=$?"
git add hardware/sheets/rails.kicad_sch hardware/output/erc.rpt
git commit -m "hw(sch): synchronous 24 V boost, low-Iq 3V3 buck, switched peripheral rail"
```

Expected: `exit=0`.

---

## Task 5: Schematic — MCU and CAN sheet

**Files:**
- Modify: `hardware/sheets/mcu_can.kicad_sch`

**Interfaces:**
- Consumes: `+3V3_ALW`, `GND`
- Produces: every control and bus net the outputs sheet needs — `I2C_SDA`, `I2C_SCL`,
  `MUX_S0`–`MUX_S3`, `RGB_ISNS`, `PWM_DEN_A`, `PWM_DEN_B`, `ISNS_DEN_A`, `ISNS_DEN_B`,
  `EN_BOOST`, `EN_3V3SW`, `EN_DIAG`, `LED_STAT` — plus `CANH`, `CANL` to the connector

- [ ] **Step 1: Write the sheet's acceptance criteria on the sheet**

```
ACCEPTANCE (spec 7, 8.1):
- ESP32-WROOM-32E-N8 (8 MB). NOT the 4 MB variant, NOT the -32UE (U.FL) variant.
- Module powered from +3V3_ALW (stays up in sleep)
- Pin assignment EXACTLY per the plan's Global Constraints table
- CAN_RXD on GPIO 35 (RTC-capable, EXT0 wake); IGN_SENSE on GPIO 36 (EXT1)
- ISNS_DEN_A/B on GPIO 34/39 -- ADC1 ONLY, never ADC2
- CAN_STB on GPIO 14, PULLED UP to VIO (floating = standby)
- TJA1042T/3 TXD routed through an UNPOPULATED 0 ohm link, TXD pulled to VIO
- NO 120 ohm terminator populated; unpopulated footprint present
- CAN CM choke + ESD protection on CANH/CANL
- Programming header with DTR/RTS auto-reset pair, BOOT and EN buttons
- IGN_SENSE divider footprint present but UNPOPULATED
```

- [ ] **Step 2: Place the ESP32 module and decoupling**

ESP32-WROOM-32E-N8 from the BOM. Bulk + ceramic decoupling close to the module's 3V3 pins. EN pin
with its RC reset network.

**Antenna keep-out:** place a note that no copper, no plating and no components may sit under the
module's antenna area, on any layer. This carries into Task 8.

- [ ] **Step 3: Wire every pin per the Global Constraints pin table**

Label each net with its exact contract name. Double-check GPIO 34/39 are the current-sense inputs
(ADC1) and that nothing analog landed on ADC2 pins.

- [ ] **Step 4: Add the passive-default pull resistors**

Pulldowns on `EN_BOOST`, `EN_3V3SW`. Pull-up on `CAN_STB` to the transceiver's VIO.
(The 14 `PWM_*` pulldowns belong to the outputs sheet, Task 6.)

- [ ] **Step 5: Draw the CAN transceiver with hardware-enforced listen-only**

TJA1042T/3: VIO to `+3V3_ALW`, `CAN_RXD` to GPIO 35, `CAN_STB` to GPIO 14.

For TXD: place a **0 Ω link footprint, marked DNP (do-not-populate)**, between GPIO 17 (`CAN_TXD`)
and the transceiver TXD pin, and pull the transceiver TXD pin **to VIO** through a resistor so it
rests recessive. Add a text note:

```
HARDWARE-ENFORCED LISTEN-ONLY: R__ (0 ohm) is DNP. With it unpopulated the
transceiver TXD is held recessive by R__ and the board is PHYSICALLY INCAPABLE
of transmitting on the vehicle bus. Populate R__ only for deliberate bench TX.
```

Add CANH/CANL common-mode choke and ESD protection, and an **unpopulated** 120 Ω terminator
footprint with a note that the vehicle bus is already terminated.

- [ ] **Step 6: Draw the programming header and buttons**

6-pin header: `+3V3_ALW`, `GND`, `UART_TX` (GPIO 1), `UART_RX` (GPIO 3), `EN_MCU`, `BOOT_N`
(GPIO 0). Add the standard two-transistor DTR/RTS auto-reset pair so a plain USB-UART adapter
enters download mode unaided. BOOT and EN tactile buttons. Status LED with series resistor on
`LED_STAT`.

- [ ] **Step 7: Place the unpopulated ignition-sense divider**

Resistor divider from a `VBAT_A`-side input to `IGN_SENSE` (GPIO 36), **both resistors DNP**, with
a clamp diode to 3.3 V. Note: "Fallback if the Experia CAN bus never idles (spec 8.3)."

- [ ] **Step 8: Run ERC and commit**

```bash
cd hardware && "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch erc \
  --severity-error --exit-code-violations -o output/erc.rpt mccan.kicad_sch; echo "exit=$?"
git add hardware/sheets/mcu_can.kicad_sch hardware/output/erc.rpt
git commit -m "hw(sch): ESP32-WROOM-32E-N8, TJA1042 with hardware-enforced listen-only, prog header"
```

Expected: `exit=0`.

---

## Task 6: Schematic — outputs sheet

**Files:**
- Modify: `hardware/sheets/outputs.kicad_sch`

**Interfaces:**
- Consumes: `+24V`, `+3V3_SW`, `+3V3_ALW`, `VBAT_B`, `GND`, all bus and control nets from Task 5
- Produces: the seven panel connectors. This is the last schematic sheet; after it, ERC must pass
  with zero errors **and** zero unconnected-pin warnings.

- [ ] **Step 1: Write the sheet's acceptance criteria on the sheet**

```
ACCEPTANCE (spec 5, 9.1, 9.2):
- PCA9685 on +3V3_SW, I2C, LED0-11 -> the 12 RGB switch inputs IN ChannelIndex ORDER:
  LED0,1,2 = FL R,G,B;  LED3,4,5 = FR R,G,B;
  LED6,7,8 = RL R,G,B;  LED9,10,11 = RR R,G,B.   LED12-15 UNUSED.
- 12x discrete logic-level N-MOSFET, gate direct from PCA9685, 1 ohm shunt in each source leg
- 12 SENSE_* nodes -> 16:1 analog mux (MUX_S0-S3) -> RGB_ISNS -> GPIO 32 (ADC1_CH4)
- NO SPI anywhere on this board
- Dual PROFET from VBAT_B, inputs PWM_DEN_A/B from ESP32 LEDC (NOT the PCA9685)
- PROFET current sense -> ISNS_DEN_A/B with scaling resistor to stay under 3.3 V
- 4x PTC, one per string, on the +24V feeds
- All 14 PWM_* nets have a pulldown to GND
- 4 corner connectors, keyed/colour-coded differently from each other
- Denali connector: 2 switched positives + 1 shared ground
- Output snubber footprints present but DNP
```

- [ ] **Step 2: Place the PCA9685**

Powered from `+3V3_SW` (so it is unpowered in sleep). I²C to `I2C_SDA` / `I2C_SCL` with pull-ups
on `+3V3_SW`. Tie A0–A5 address pins for a fixed address; OE tied so outputs are disabled by
default. Label LED0–LED11 outputs with the exact `PWM_*` contract names, **in `ChannelIndex`
order** — getting this order wrong produces a board whose colours and corners are scrambled
relative to firmware that is already written and tested.

- [ ] **Step 3: Place the 12 discrete MOSFETs, shunts, and the analog mux**

For each of the 12 channels: `PWM_*` → gate (with a **pulldown on every `PWM_*` net**); drain → the
corresponding `RET_*` net to the corner connector; source → a **1 Ω shunt** → `GND`. The node
between source and shunt is that channel's `SENSE_*` net.

Wire all 12 `SENSE_*` nets to the 16:1 analog mux inputs **in `ChannelIndex` order** so mux channel
0–11 matches PWM channel 0–11 — a scrambled mux order produces diagnostics that blame the wrong
corner. Mux select from `MUX_S0`–`S3` (GPIO 23/4/16/5), **each with a pulldown**; mux supply from
`+3V3_SW`; mux output → `RGB_ISNS` → GPIO 32.

Leave mux inputs 12–15 unused (tie to GND per the mux datasheet's guidance for unused inputs).

Add a note on the sheet:
```
SENSE CHAIN (spec 5.1): 1 ohm x 0.14 A = 140 mV at full channel current.
ADC1 at 0 dB attenuation (0-1.1 V range). Classification is open (~0 mV) /
working (~140 mV) / shorted (saturated) -- NOT precision current metering.
Sampling is on-demand: firmware drives one channel to 100%, steps the mux,
reads, advances. Same sweep serves as the installation self-test.
```

- [ ] **Step 4: Place the dual PROFET**

Supply from `VBAT_B`. Inputs from `PWM_DEN_A` / `PWM_DEN_B` (**GPIO 18/19** — moved off 32/33, which
GPIO 32 now needs for `RGB_ISNS`), **each with a pulldown**.
Diagnostic enable from `EN_DIAG`. Current-sense outputs through scaling resistors to `ISNS_DEN_A`
/ `ISNS_DEN_B`, sized so a 3.3 A load reads comfortably below 3.3 V at the ADC, with a clamp
diode. Outputs `DEN_A_OUT` / `DEN_B_OUT` to the Denali connector.

- [ ] **Step 5: Place the four PTCs on the 24 V string feeds**

`+24V` → PTC → `+24V_FL`, and likewise `+24V_FR`, `+24V_RL`, `+24V_RR`. Note on the sheet:
"Isolates a shorted string so one crushed cable cannot extinguish all four corners (spec 5.2)."

- [ ] **Step 6: Place all seven connectors**

| Connector | Type | Pins |
|---|---|---|
| FL | Superseal 1.0, 4-way | `+24V_FL`, `RET_FL_R`, `RET_FL_G`, `RET_FL_B` |
| FR | Superseal 1.0, 4-way | `+24V_FR`, `RET_FR_R`, `RET_FR_G`, `RET_FR_B` |
| RL | Superseal 1.0, 4-way | `+24V_RL`, `RET_RL_R`, `RET_RL_G`, `RET_RL_B` |
| RR | Superseal 1.0, 4-way | `+24V_RR`, `RET_RR_R`, `RET_RR_G`, `RET_RR_B` |
| DENALI | Superseal 1.5, 3-way | `DEN_A_OUT`, `DEN_B_OUT`, `GND` |
| CAN | Superseal 1.0, 2-way | `CANH`, `CANL` |
| PWR A / PWR B | Superseal 1.5, 2-way ×2 | Feed A +/−, Feed B +/− (on the power_input sheet) |

Annotate each corner connector with its intended **distinct colour or keying code** — the
schematic is where that decision gets recorded, since mis-mating reverses the indicators and the
firmware cannot detect it.

- [ ] **Step 7: Add DNP snubber footprints on the 12 outputs**

Series RC footprints to GND on each `RET_*` net, all DNP, in case the long corner runs need
taming during EMC work.

- [ ] **Step 8: Run the full ERC gate — this is the schematic completion gate**

```bash
cd hardware && "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch erc \
  --severity-all --exit-code-violations -o output/erc.rpt mccan.kicad_sch; echo "exit=$?"
cat output/erc.rpt
```

Expected: `exit=0` with `--severity-all`, i.e. zero errors **and** zero warnings. Every
unconnected pin must be either connected or explicitly marked with a no-connect flag. Do not
proceed to layout with outstanding warnings — an unconnected-pin warning at this stage is how a
dead net reaches fabrication.

- [ ] **Step 9: Commit**

```bash
git add hardware/sheets/outputs.kicad_sch hardware/output/erc.rpt
git commit -m "hw(sch): output stages, PCA9685 in ChannelIndex order, PTCs, all seven connectors"
```

---

## Task 7: Schematic review against the spec

**Files:**
- Create: `hardware/docs/schematic-review.md`

**Interfaces:**
- Consumes: all four completed sheets
- Produces: a signed-off review record. Task 8 must not start until every row reads PASS.

- [ ] **Step 1: Write the review checklist**

Create `hardware/docs/schematic-review.md`. Each row is a spec requirement traced to the
schematic; fill in the sheet and reference designator that satisfies it.

```markdown
# Schematic Review vs Spec

| Spec | Requirement | Sheet / refdes | Verdict |
|---|---|---|---|
| 2.2 | Feed A and Feed B are independent; only the Schottky OR links them | | |
| 4.1 | Two fuse holders, 7.5 A (A) and 10 A (B) | | |
| 4.2 | P-FET reverse polarity on each feed, Vgs clamped | | |
| 4.3 | 24 V TVS each feed; all front-end parts >= 40 V | | |
| 4.3 | pi filter + CM choke on each feed | | |
| 4.4 | Schottky OR -> VLOGIC_IN feeds the buck (NOT VBAT_A) | | |
| 5.1 | 12x discrete MOSFET, Vds >= 40 V, enhanced at 3.3 V Vgs | | |
| 5.1 | 1 ohm shunt per channel; 12 SENSE_* into 16:1 mux in ChannelIndex order | | |
| 5.1 | MUX_S0-S3 on GPIO 23/4/16/5 with pulldowns; RGB_ISNS on GPIO 32 (ADC1) | | |
| 5.1 | NO SPI nets anywhere on the board | | |
| 6 | 5 V rail present, always on, low quiescent (TJA1042 VCC) | | |
| 5.2 | 4x PTC on the per-string +24V feeds | | |
| 5.3 | Dual PROFET from VBAT_B, sense scaled for 3.3 A | | |
| 5.4 | Denali PWM from ESP32 LEDC (GPIO 32/33), NOT the PCA9685 | | |
| 5.5 | PCA9685 LED0-11 in exact ChannelIndex order | | |
| 6 | Sync boost VBAT_A -> +24V, EN_BOOST with pulldown | | |
| 6 | Low-Iq buck VLOGIC_IN -> +3V3_ALW | | |
| 3 | Load switch +3V3_ALW -> +3V3_SW, EN_3V3SW with pulldown | | |
| 7.1 | ESP32-WROOM-32E-**N8** (8 MB), onboard antenna variant | | |
| 7.2 | TXD 0 ohm link is DNP; TXD pulled recessive to VIO | | |
| 7.2 | 120 ohm terminator footprint present and UNPOPULATED | | |
| 7.2 | CAN CM choke + ESD protection | | |
| 7.3 | Every GPIO matches the pin table exactly | | |
| 7.3 | ISNS on GPIO 34/39 (ADC1); nothing analog on ADC2 | | |
| 7.3 | CAN_STB on GPIO 14, pulled up to VIO | | |
| 7.3 | All 14 PWM_* nets have pulldowns | | |
| 7.4 | Prog header + DTR/RTS auto-reset + BOOT/EN buttons | | |
| 8.3 | Ignition-sense divider present, DNP | | |
| 9.1 | Seven connectors, correct types and pinouts | | |
| 9.2 | Corner connectors assigned distinct keying/colours | | |
| 10 | DNP snubber footprints on the 12 outputs | | |
```

- [ ] **Step 2: Walk every row against the schematic and fill it in**

Record the sheet and refdes that satisfies each row. Any FAIL is fixed on the schematic now, not
noted for later.

- [ ] **Step 3: Re-run the full ERC gate after any fixes**

```bash
cd hardware && "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch erc \
  --severity-all --exit-code-violations -o output/erc.rpt mccan.kicad_sch; echo "exit=$?"
```

Expected: `exit=0`.

- [ ] **Step 4: Commit**

```bash
git add hardware/docs/schematic-review.md hardware/sheets/ hardware/output/erc.rpt
git commit -m "hw: schematic review complete, all spec requirements traced to refdes"
```

---

## Task 8: PCB layout — stackup, placement and power

**Files:**
- Modify: `hardware/mccan.kicad_pcb`

**Interfaces:**
- Consumes: the netlist from Task 7's approved schematic
- Produces: a placed board with power polygons and thermal provisions; Task 9 routes signals

- [ ] **Step 1: Write the layout constraints into the board as a text layer note**

```
LAYOUT CONSTRAINTS (spec 9.3, 9.4, 10):
- 4 layers: L1 signal, L2 GND (solid, unbroken), L3 power, L4 signal
- 2 oz outer copper
- Feed B power polygon >= 4-5 mm effective width (6.6 A, 10 C rise)
- Feed A power polygon >= 3 mm (3.9 A)
- Boost switch-node loop area MINIMISED; gate loops short and tight
- Boost FETs, inductor and both P-FETs grouped on the heat-spreader edge
- ESP32 antenna keep-out: NO copper/plating/parts any layer under the antenna
- Antenna edge faces AWAY from the aluminium plate
- Connectors on one edge, matching the panel layout in docs/enclosure.md
- High-current (Feed B/PROFET) separated from CAN and analog sense traces
```

- [ ] **Step 2: Set up the stackup and design rules**

4-layer board, 2 oz outer copper. Set net classes: a `POWER` class with wide clearance and track
width for `VBAT_A`, `VBAT_B`, `VLOGIC_IN`, `+24V`, `DEN_*_OUT`, `GND`; a `DEFAULT` class for
signals; a `CAN` class for `CANH`/`CANL` with matched width and spacing for ~120 Ω differential.

- [ ] **Step 3: Place the thermal group on the heat-spreader edge**

Boost high-side and low-side FETs, boost inductor, both P-FETs, and the PROFET all grouped along
the edge that will face the aluminium plate. These are ~3.6 W of the board's dissipation
(spec §9.4) and the plate is the only real path out of a plastic box.

Add thermal via arrays under each part's exposed pad — enough vias that the pad-to-L3 resistance
does not dominate. Note the intended gap-pad contact area on the board.

- [ ] **Step 4: Place the ESP32 module with its antenna keep-out honoured**

Module at the board edge **furthest from the aluminium plate**, antenna overhanging the board edge
with a keep-out on all four layers. Plastic enclosure walls are the RF window (spec §9.3) — an
antenna pointed into the metal plate defeats the onboard-antenna decision entirely.

- [ ] **Step 5: Place connectors to match the panel**

One edge, ordered to match the panel layout. Corner connectors grouped, power and CAN separated
from each other.

- [ ] **Step 6: Pour the power polygons and the ground plane**

Solid unbroken GND on L2 — do not route signals through it. Power polygons on L3 sized per the
constraints note. Stitch vias generously between GND regions, especially around the boost.

- [ ] **Step 7: Run DRC with schematic parity**

```bash
cd hardware && "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" pcb drc \
  --severity-error --schematic-parity --exit-code-violations --refill-zones \
  -o output/drc.rpt mccan.kicad_pcb; echo "exit=$?"
```

Expected: unrouted-net errors are acceptable at this stage (Task 9 routes them), but **schematic
parity must be clean** — any parity failure means the board and schematic disagree about a net or
a footprint, which is a silent fabrication error. Record the parity result in the report.

- [ ] **Step 8: Commit**

```bash
git add hardware/mccan.kicad_pcb hardware/output/drc.rpt
git commit -m "hw(pcb): 4-layer stackup, thermal group on plate edge, antenna keep-out, power pours"
```

---

## Task 9: PCB layout — routing and fabrication outputs

**Files:**
- Modify: `hardware/mccan.kicad_pcb`
- Create: `hardware/output/` gerbers, drill, BOM, CPL

**Interfaces:**
- Consumes: the placed board from Task 8
- Produces: a complete fabrication package

- [ ] **Step 1: Route the boost power stage first**

The switch-node loop and both gate loops are the highest-risk routing on the board. Route them
before anything else claims the space: minimal switch-node area, gate traces short and paired with
their return, current-sense traces as a differential pair routed away from the switch node.

- [ ] **Step 2: Route the remaining power nets**

`VBAT_A`, `VBAT_B`, `+24V`, `DEN_*_OUT` as polygons or wide tracks per the net class. Verify the
Feed B path width against the 6.6 A requirement.

- [ ] **Step 3: Route CAN as a differential pair**

`CANH`/`CANL` matched length, constant spacing, away from the boost and from the high-current
Denali path. Through the CM choke and ESD parts.

- [ ] **Step 4: Route the analog sense traces**

`ISNS_DEN_A` / `ISNS_DEN_B` kept short, away from PWM and the switch node, with their scaling
resistors close to the ADC pins. These carry the diagnostics the design was chosen for; coupled
noise here shows up as phantom faults.

- [ ] **Step 5: Route the remaining signals, then add test points**

Remaining buses and control nets. Then add test points on `VBAT_A`, `VBAT_B`, `VLOGIC_IN`, `+24V`,
`+3V3_ALW`, `+3V3_SW`, `+5V`, `I2C_SDA`, `I2C_SCL`, `RGB_ISNS`, `CANH`, `CANL`, `GND` (several).

- [ ] **Step 6: Run the DRC completion gate**

```bash
cd hardware && "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" pcb drc \
  --severity-all --schematic-parity --all-track-errors --exit-code-violations \
  --refill-zones -o output/drc.rpt mccan.kicad_pcb; echo "exit=$?"
cat output/drc.rpt
```

Expected: `exit=0`. Zero errors, zero warnings, zero unrouted nets, clean schematic parity. This
is the gate that says the board is fabricable.

- [ ] **Step 7: Generate the fabrication package**

```bash
cd hardware
K="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
"$K" pcb export gerbers -o output/gerbers/ mccan.kicad_pcb
"$K" pcb export drill   -o output/gerbers/ mccan.kicad_pcb
"$K" sch export bom     -o output/bom.csv  mccan.kicad_sch
"$K" pcb export pos     -o output/cpl.csv --format csv --units mm mccan.kicad_pcb
"$K" pcb export pdf     -o output/pcb.pdf  mccan.kicad_pcb
"$K" sch export pdf     -o output/sch.pdf  mccan.kicad_sch
```

- [ ] **Step 8: Verify the BOM against the part-selection record**

Open `output/bom.csv` and confirm every line's manufacturer part number appears in
`docs/part-selection.md`'s final decision table. Any part on the board that was never verified is
a gap — resolve it before fabrication.

Mark every DNP part clearly in the BOM: the TXD 0 Ω link, the 120 Ω terminator, the
ignition-sense divider, and the 12 output snubbers.

- [ ] **Step 9: Commit**

```bash
git add hardware/mccan.kicad_pcb hardware/output/
git commit -m "hw(pcb): complete routing, DRC clean with parity, fabrication package generated"
```

---

## Task 10: Enclosure, panel and harness documentation

**Files:**
- Create: `hardware/docs/enclosure.md`
- Create: `hardware/docs/harness.md`

**Interfaces:**
- Consumes: the board outline and connector positions from Task 9
- Produces: everything needed to order the box, machine the plate, and build the harness

- [ ] **Step 1: Write `hardware/docs/enclosure.md`**

Must specify, with actual values rather than descriptions:

- Chosen polycarbonate IP67 enclosure: manufacturer, part number, internal dimensions, and the
  clearance check against the board outline plus connector mating depth
- Aluminium heat-spreader plate: dimensions, thickness, the wall it replaces, gasket type and
  groove, fastener pattern and torque
- Gap-pad specification: material, thickness, compressed thickness, thermal conductivity, and the
  contact area against the Task 8 thermal group
- Panel layout drawing with cutout positions and diameters for all nine penetrations: four corner
  connectors, Denali, PWR A, PWR B, CAN, and the two fuse holders
- Pressure-equalisation vent: part number and mounting position
- Mounting: bracket design, thermal-compound interface to the plate, and the rubber isolators
  between bracket and frame — the plate must stay thermally coupled while the bracket is
  vibration-decoupled (spec §9.3)
- Conformal coating: material, and the masking list (connectors, programming header, test points,
  antenna keep-out, vent)

- [ ] **Step 2: Write `hardware/docs/harness.md`**

Must specify:

- Wire gauge per circuit, derived from the spec currents: Feed A 3.9 A, Feed B 6.6 A, Denali
  3.3 A per channel, RGB 0.14 A per channel and 0.42 A per string feed
- Connector part numbers for both halves of all seven connectors, plus terminals and seals
- **Corner colour/keying assignment table** — which colour or key code is FL, FR, RL, RR — and a
  prominent warning that mis-mating reverses the indicators and is undetectable in firmware
- Denali connector pinout showing the shared ground
- CAN tap method: where on the vehicle, and a reminder that no terminator is populated
- Both power feeds: which Experia peripheral outlets, and confirmation they are independent
  10 A circuits rather than branches of one (spec §11 verification item)
- Loom, routing and strain-relief requirements, explicitly covering the **accepted risk** that
  the runs from the outlets to the box are not fused at their source (spec §4.1)

- [ ] **Step 3: Commit**

```bash
git add hardware/docs/enclosure.md hardware/docs/harness.md
git commit -m "hw(docs): enclosure, heat-spreader plate, panel layout and harness specification"
```

---

## Task 11: Bring-up procedure

**Files:**
- Create: `hardware/docs/bring-up.md`

**Interfaces:**
- Consumes: the complete design
- Produces: an ordered procedure with blank measurement tables and explicit pass criteria, to be
  filled in when boards arrive

- [ ] **Step 1: Write the procedure with pass criteria stated before any board exists**

Create `hardware/docs/bring-up.md` following spec §11's nine stages. Every stage needs a **pass
criterion with a number**, and a blank cell for the measured value. Writing the expected value
before measuring is what stops a wrong reading being rationalised as normal.

```markdown
# Bring-Up Procedure

Work the stages IN ORDER. A failed stage stops the process -- do not proceed
to the next stage with an unexplained result.

## Stage 1: Rails only, MCU and switch ICs NOT populated
| Check | Expected | Measured | Pass |
|---|---|---|---|
| Feed A current with no load | < 5 mA | | |
| +3V3_ALW | 3.30 V +/- 3% | | |
| +24V with EN_BOOST high | 24.0 V +/- 5% | | |
| +24V with EN_BOOST floating | ~VBAT_A (body diode; see rails sheet note) | | |
| +3V3_SW with EN_3V3SW floating | 0 V (pulldown) | | |
| Reverse-polarity test: reverse Feed A | No current, no damage | | |

## Stage 2: Boost under full dummy load
| Check | Expected | Measured | Pass |
|---|---|---|---|
| 24 V into 2.5 A dummy load | 24.0 V +/- 5%, stable | | |
| Efficiency at 40 W out | >= 94% | | |
| Output ripple | < 200 mV pk-pk | | |
| Boost group temperature rise after 30 min | consistent with ~2.6 W | | |

## Stage 3: Quiescent current in simulated sleep
| Check | Expected | Measured | Pass |
|---|---|---|---|
| Total with enables floating, transceiver STB high | **< 200 uA** (ceiling 500 uA) | | |
If over budget, isolate per contributor against the part-selection roll-up table.

## Stage 4: MCU populated
| Check | Expected | Measured | Pass |
|---|---|---|---|
| Flash over the programming header with a plain USB-UART adapter | Succeeds with NO manual BOOT hold | | |
| Module identifies as 8 MB flash | 8 MB | | |

## Stage 5: Buses
| Check | Expected | Measured | Pass |
|---|---|---|---|
| PCA9685 responds at its I2C address | ACK | | |
| Mux steps through all 16 channels | RGB_ISNS follows the selected channel | | |
| Open channel vs working channel at 100% duty | ~0 mV vs ~140 mV, distinguishable | | |
| PROFET diagnostics readable | Sense voltage tracks load | | |

## Stage 6: All 14 outputs into dummy resistive loads
| Check | Expected | Measured | Pass |
|---|---|---|---|
| Each of 12 RGB channels switches independently | Correct channel, no crosstalk | | |
| Channel-to-corner mapping matches ChannelIndex | FL,FR,RL,RR in order | | |
| RGB PWM frequency | 400 Hz +/- 5% | | |
| Denali PWM frequency | 150 Hz +/- 5% | | |
| Low-duty linearity, all 12 channels | Monotonic from duty 1; colours matched | | |
| Open-load detection with one channel disconnected | Fault reported (part-selection row 1.1) | | |
| Short-to-ground detection | Fault reported, channel protected | | |

## Stage 7: CAN
| Check | Expected | Measured | Pass |
|---|---|---|---|
| Receive frames from a bench bus | Frames decoded | | |
| TXD link DNP: attempt to transmit | NOTHING appears on the bus | | |
| Standby mode entered (STB high) | Transceiver current drops | | |
| Bus activity drives RXD low in standby | Wake signal observed | | |
| Deep sleep -> EXT0 wake on bus activity | Board wakes and resumes | | |

## Stage 8: Real loads, soak test
| Check | Expected | Measured | Pass |
|---|---|---|---|
| Four real RGB strings, full white, 30 min | No flicker; thermal rise acceptable | | |
| Denali D4 pair across the full duty range | **No flicker, no audible buzz, monotonic** | | |
| Measured RGB string power vs the 40 W assumption | Record actual (spec 2.2) | | |
| Measured Denali draw vs 6.6 A | Record actual | | |
If the D4 pair misbehaves under supply PWM, fall back to full supply plus the
pods' native DataDim input (spec 5.3).

## Stage 9: Vehicle install
| Check | Expected | Measured | Pass |
|---|---|---|---|
| Both Experia outlets confirmed independent 10 A circuits | Independent | | |
| Internal temperature after a sustained ride | < 65 C at 40 C ambient | | |
| Parked quiescent drain over 7 days | Consistent with < 200 uA | | |
| Does the CAN bus actually idle when parked? | Bus goes quiet -> board sleeps | | |
| Corner mapping verified by the install self-test | All four correct | | |

## Open questions to close during bring-up (spec 14)
With live bus access, resolve: the Run bit at 0x102; the day/night bit; what
0x400 bit 16 drives; brake OR-logic; the canonical bit-numbering convention;
the duplicate Run entries; and the spot-latch decision.
```

- [ ] **Step 2: Commit**

```bash
git add hardware/docs/bring-up.md
git commit -m "hw(docs): staged bring-up procedure with pass criteria and measurement tables"
```

---

## Self-Review

**Spec coverage** — every spec section traced to a task:

| Spec section | Task |
|---|---|
| §2 Loads and power budget | 2 (verification), 3 (feeds), 10 (harness gauges) |
| §3 Architecture, three domains | 3, 4, 6 |
| §4.1 Fusing, two holders | 3, 10 |
| §4.2 P-FET reverse polarity | 3 |
| §4.3 Transient protection | 3 |
| §4.4 Dual feed, domain split, Schottky OR | 3, 7 |
| §5.1 Discrete FETs + shunt/mux/ADC sense chain | 2 (revised criteria), 6 |
| §5.2 Per-string PTC | 6 |
| §5.3 Dual PROFET | 2, 6 |
| §5.4 PWM split, 400/150 Hz | 6, 11 (Stage 6) |
| §5.5 PCA9685 ChannelIndex order | 6, 7, 11 (Stage 6) |
| §6 Rails, sync boost, low-Iq buck | 2, 4 |
| §7.1 WROOM-32E-N8 | 5, 11 (Stage 4) |
| §7.2 CAN, hardware listen-only, no terminator | 5, 11 (Stage 7) |
| §7.3 Pin allocation, passive defaults | 5, 6, 7 |
| §7.4 Programming, auto-reset | 5, 11 (Stage 4) |
| §8 Sleep and wake, budget | 2 (roll-up), 5, 11 (Stages 3, 7) |
| §9.1–9.2 Connectors, corner keying | 6, 10 |
| §9.3 Enclosure, plate, vent, mounting | 8 (thermal placement), 10 |
| §9.4 Thermal | 8, 11 (Stages 2, 9) |
| §10 Stackup, EMC | 8, 9 |
| §11 Verification and bring-up | 2, 11 |
| §12 Firmware | **Deliberately out of scope** — separate plan |
| §13 Risk register | 2 (go/no-go), 11 (Stages 8, 9) |
| §14 Open CAN questions | 11 (Stage 9) |

**Gap found and accepted:** spec §12's six firmware items have no task here. That is intentional —
the spec scopes firmware out and states each item gets its own plan. **A second plan is required
before the board is usable**, covering at minimum the three mandatory items: deep sleep + CAN
wake, the composite `IPwm` (PCA9685 0–11 + LEDC 12–13), and the 8 MB partition table.

**Placeholder scan:** no TBD/TODO. Every table in Tasks 2, 7 and 11 is deliberately blank in its
"Actual"/"Measured" columns — those are the artefacts being produced, and each has a stated
expected value beside it, which is the opposite of a placeholder.

**Consistency check:** net names are identical across Tasks 3–9 and match the Global Constraints
contract. GPIO assignments match the spec pin table including the newly added `CAN_STB` on GPIO 14.
Currents are consistent throughout: Feed A 3.9 A, Feed B 6.6 A, 0.14 A per RGB channel, 3.3 A per
Denali channel. `kicad-cli` is invoked by full path everywhere.

---

## Execution Handoff

Two execution options:

**1. Subagent-Driven (recommended)** — a fresh subagent per task, review between tasks, fast
iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution
with checkpoints.

**Caveat specific to this plan:** Tasks 1–2 and 10–11 are document and verification work that an
agent can complete end to end. **Tasks 3–9 require interactive KiCad** — schematic capture and
board layout are GUI operations that cannot be driven from the CLI. An agent can prepare the
constraint notes, net lists, design rules and review checklists, and can run every ERC/DRC gate,
but the drawing and placement itself needs a person at the keyboard. Plan for Tasks 3–9 to be
collaborative rather than autonomous.
