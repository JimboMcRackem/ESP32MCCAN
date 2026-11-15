# MCCAN Programmer Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A generated, gate-checked, JLCPCB-ready KiCad project for a small USB-C → J2 programmer that flashes and powers the MCCAN board's 3.3 V rail from USB alone.

**Architecture:** A self-contained KiCad project in `hardware/programmer/` with its own scripts, one flat schematic sheet, a 2-layer board, and its own fab package. It reuses the main board's *shared* modules by import (`kicanon`, `check_netlist.load`, `check_stock.fetch_stock`/`need`). Main-board generators whose import has side effects (`gen_mcu_can.py` reads the root schematic at import) are not imported. Their helper pattern is copied into a small local library instead. Nothing under `hardware/` outside `hardware/programmer/` changes.

**Tech Stack:** Python 3.14 (stdlib only: no numpy/scipy on this machine), KiCad 10.0 (`C:/Program Files/KiCad/10.0/bin/kicad-cli.exe`, `PYTHONIOENCODING=utf-8`), JLCPCB parts API via `hardware/scripts/check_stock.py`.

**Spec:** `docs/superpowers/specs/2026-11-14-programmer-board-design.md`

## Global Constraints

- Branch `programmer-board`, worktree `D:/Projects/ESP32MCCAN-prog`. Do not push, do not merge, and do not touch main.
- Do not modify any file under `hardware/` outside `hardware/programmer/`. The MCCAN project's files and gates stay untouched (spec §6.8).
- Generate everything. Never hand-edit `.kicad_sch`, `.kicad_pcb`, `.kicad_pro` or `.kicad_dru`. Schematic coordinates go on the 1.27 mm grid. Every generated sheet goes through `kicanon.canonicalise()`.
- J2 pinout (spec §6.1), header pin → net: 1 `+3V3_ALW`, 2 `GND`, 3 `UART_TX`, 4 `UART_RX`, 5 `DTR`, 6 `RTS`.
- Cross TX and RX on the programmer: the serial chip's RXD goes to header pin 3 and its TXD to header pin 4 (spec §6.2).
- 3.3 V output must deliver at least **600 mA** continuous. The output must not fall below **3.0 V** at the MCCAN board at full load, counting the cable (spec §6.3).
- Block reverse current. Load sharing with a powered MCCAN board is accepted (spec §6.3).
- USB-C is a USB 2.0 device: CC1 and CC2 each get 5.1 kΩ to GND. No USB-PD.
- 2 layers, 1.6 mm, all parts on the top side, about 20 × 40 mm. USB-C at one end, the 6-pin header at the other.
- Silkscreen: pin 1 and the six net names at the header, plus "MCCAN PROG" and the revision.
- Every part comes from JLCPCB's own stock for **5 boards**. JLCPCB assembles every part; nothing is hand-soldered. JLCPCB's THT service is allowed for the header, as for the main board's J2.
- Gates: ERC 0; netlist check PASS; DRC 0 at all severities with `--refill-zones --severity-all --schematic-parity`; fab `--check` PASS; stock check PASS for 5 boards.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Decided here (builder's calls the spec left open)

Record each of these in `hardware/programmer/README.md` with its reason (spec §9). Refs and parts:

| Ref | Part | LCSC (verify in Task 1) | Why |
|---|---|---|---|
| J1 | HRO TYPE-C-31-M-12, `Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12`, symbol `Connector:USB_C_Receptacle_USB2.0_16P` | C165948 | JLCPCB's most-stocked USB-C 16P |
| J2 | 1×6 2.54 mm header, `Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical` | C492405 | same part as the MCCAN J2; named J2 because it carries J2's pinout |
| U1 | CH343P, `Interface_USB:CH343P`, `Package_DFN_QFN:WCH_QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm` | C2846043 | CDC-ACM on Windows 10/11; separate VIO pin; no crystal |
| U2 | USBLC6-2SC6, `Power_Protection:USBLC6-2SC6` (SOT-23-6) | C7519 (alt C2827654) | ESD on D+/D− |
| U3 | AMS1117-3.3, `Regulator_Linear:AMS1117-3.3` (SOT-223) | C6186 | 1 A with current limit and thermal shutdown. **Not** AP2112K/TLV757 in SOT-23-5: 1.7 V × 0.6 A ≈ 1 W cannot leave a SOT-23 package, but SOT-223 on a copper pour can |
| U4 | LM66100DCK, `Power_Management:LM66100DCK` (SC-70-6) | C2869734 | ideal diode with reverse blocking; ≈79 mΩ, so ≈50 mV at 0.6 A |
| U5 | SN74LVC2G125DCTR, `74xGxx:74LVC2G125`, `Package_SO:SSOP-8_2.95x2.8mm_P0.65mm` | C206035 | buffers ~DTR/~RTS. LVC's Ioff makes its outputs high-impedance when it is unpowered. Without it, an unpowered programmer on a powered MCCAN board drags EN_MCU to ≈ 2.2 V: R22 10k → Q2 CB junction → R28 10k → R6 → U1's ESD diode into a dead `+3V3_USB`. That is below the ESP32's 2.5 V VIH, so the chip may be held in reset. Both ~OE → `GND`, VCC → `+3V3_USB`, C9 100 nF |
| R1, R2 | 5.1k 0603 | C23186 | CC1, CC2 |
| R3 | 4.7k 0603 | C23162 | header pin 3 (ESP TX) → U1 RXD. Limits back-power into an unpowered U1 to ≤ 0.6 mA (spec §6.4); τ ≈ 4.7k × 10 pF ≈ 47 ns against a 1085 ns bit at 921 600 baud |
| R4 | 470R 0603 | C23179 | U1 TXD → header pin 4 (ESP RX) |
| R5, R6 | 220R 0603 | C22962 | U5 output (from U1 ~DTR) → pin 5, U5 output (from U1 ~RTS) → pin 6. Low enough that Q2 still pulls EN below the ESP32's 0.825 V VIL (emitter current ≈ 0.6 mA → ≈ 0.13 V across 220 Ω). A misplugged output sees ≤ 15 mA |
| D1, R7 | green 0603 LED + 1k | C72043, C21190 | power: lit from `+3V3_USB` (spec §6.6) |
| D2, R8 | red 0603 LED + 1k | C2286, C21190 | TX: anode network from `+3V3_USB` to U1-side TXD node (lit while U1 pulls low) |
| D3, R9 | yellow 0603 LED + 1k | C72038, C21190 | RX: anode network from `+3V3_USB` to **header-side** pin 3 node, so the ESP drives it directly and R3 stays a clean limiter. With USB unplugged its anode rail is 0 V, so the LED is reverse-biased by ≤ 3.34 V (inside a 5 V rating) and carries no current |
| C1 | 10µF 0805 | C15850 | VBUS bulk, at U3's input |
| C2, C6 | 100nF 0603 | C14663 | VBUS decoupling at J1; U1 VDD5 |
| C3 | 22µF 0805 | C45783 | U3 output (AMS1117 needs ≥ 22 µF ceramic for stability) |
| C4, C5 | 22µF 0805 | C45783 | `+3V3_OUT` bulk at J2 for the WiFi start-up peaks (spec §6.3, builder's call) |
| C7 | 100nF 0603 | C14663 | U1 VIO |
| C9 | 100nF 0603 | C14663 | U5 VCC |
| C8 | per CH343 datasheet (1 µF 0603 C15849 if it gives none) | — | U1 V3_OUT |

Nets: `VBUS`, `+3V3_USB` (U3 out: U1 VIO, LEDs, U4 VIN), `+3V3_OUT` (U4 VOUT → J2.1), `GND`, `USB_DP`, `USB_DN`, `CC1`, `CC2`, `U_RXD`, `U_TXD`, `U_DTR`, `U_RTS` (U1 → U5 inputs), `B_DTR`, `B_RTS` (U5 outputs → R5/R6), plus header-side `UART_TX`, `UART_RX`, `DTR`, `RTS`. Header-side nets are named exactly as on the MCCAN board, so a reader can trace the cable straight across.

U1 connections, by symbol pin name:

- VDD5 and VBUS → `VBUS`; VIO → `+3V3_USB`; UD+/UD− → `USB_DP`/`USB_DN`.
- V3_OUT → C8 only.
- GND and GND_EPAD → `GND`.
- ~ACT, ~DCD, ~DSR, ~CTS, ~RI: no-connect. Read the datasheet first: if it says an unused input must be tied, tie it to the stated level and record that. ~CTS in particular may gate transmission when flow control is off.

U4: ~CE → `GND` (active-low enable); ST no-connect. J1: A6/B6 → `USB_DP`, A7/B7 → `USB_DN`, SBU1/SBU2 no-connect, SHIELD → `GND`. Cable drop budget: 20 cm Dupont is ≈ 0.2 Ω round trip, so 0.1 V at 0.5 A. That gives AMS1117 3.234 V min − 0.05 V − 0.1 V ≈ 3.08 V ≥ 3.0 V.

## Review Focus

1. **Programmer on a powered MCCAN board with USB unplugged.** Back-feed may hold the ESP32 in reset or brown out U1. EN_MCU (R22 10k pull-up, C37 1 µF) can forward-bias Q2's collector-base junction, and the current then runs through R28 (10k), `RTS`, and R6 into U5. U5's Ioff is what stops that current, so it must not be bypassed. The ESP's TX also feeds R3 → U1 RXD. Expected: the ESP32 keeps running and the back-current is ≤ 1 mA per line. *Test:* `test_unpowered_backfeed_budget` in Task 2.
2. **Both boards powered.** No current may flow into U3's output, and the rail stays 3.2–3.4 V. *Test:* `test_reverse_blocking_topology` in Task 2.
3. **Cable reversed end-for-end.** Every programmer output that lands on GND or 3.3 V must be limited to ≤ 15 mA by its series resistor or by U4/U3's current limit. *Test:* `test_misplug_currents` in Task 2.
4. **ESP32 at full WiFi load.** At 0.6 A the rail at the MCCAN board must stay ≥ 3.0 V, and U3 must not cross into thermal shutdown on the bench. *Test:* `test_power_budget` in Task 2 for the numbers, and `test_regulator_heatsink_pour` in Task 3 for U3's tab copper.
5. **USB enumeration and ESD.** D+/D− must pass through U2 next to J1 as a short, matched pair with no stubs, and enumeration must use Windows' CDC driver. *Test:* `test_usb_pair_routing` in Task 3. Enumeration is bench acceptance item 1.

---

### Task 1: Parts table and stock gate

**Files:**
- Create: `hardware/programmer/scripts/parts.py`
- Create: `hardware/programmer/scripts/check_stock_prog.py`
- Test: `hardware/programmer/scripts/test_parts.py`

**Interfaces:**
- Consumes: `hardware/scripts/check_stock.py` → `fetch_stock(code) -> int | None` and `need(refs, boards) -> int`. Insert `hardware/scripts` on `sys.path`; `check_stock` imports `lcsc` and `check_netlist`, which are side-effect free.
- Produces:
  - `parts.PARTS: dict[str, dict]` keyed by ref. Each entry: `{"value", "symbol", "footprint", "lcsc", "mpn", "fallback", "note"}`, with the table above as the data.
  - `parts.bom_lines() -> list[tuple[str, list[str]]]`: `(value|footprint key, refs)` groups, refs sorted naturally.
  - `check_stock_prog.main(argv) -> int`: `--boards` (default 5) and `--offline`. Prints one line per BOM line in `check_stock.py`'s format and returns nonzero on any shortfall.

- [ ] **Step 1: Write the failing tests** in `test_parts.py`. Use the `main()` runner pattern of `hardware/scripts/test_check_plane_mincut.py` (plain asserts; no pytest needed).
  - `test_every_ref_has_symbol_footprint_lcsc`: for each entry, symbol, footprint and lcsc are non-empty, and lcsc matches `^C\d+$`.
  - `test_footprints_exist_in_kicad`: each `Lib:Name` resolves to `C:/Program Files/KiCad/10.0/share/kicad/footprints/Lib.pretty/Name.kicad_mod`.
  - `test_symbols_exist_in_kicad`: each `Lib:Name` occurs as `(symbol "Name"` in `.../symbols/Lib.kicad_sym`.
  - `test_refs_match_plan`: `set(PARTS) == {"J1","J2","U1","U2","U3","U4","U5","R1",…,"R9","D1","D2","D3","C1",…,"C9"}`.
  - `test_bom_lines_group_shared_parts`: R7, R8 and R9 share one line, as do C4, C5 and C3.
- [ ] **Step 2: Run** `python hardware/programmer/scripts/test_parts.py`. Expected: FAIL (`No module named 'parts'`).
- [ ] **Step 3: Implement `parts.py`** from the table in "Decided here".
- [ ] **Step 4: Run the tests.** Expected: `test_parts: PASS`.
- [ ] **Step 5: Implement `check_stock_prog.py`**, reusing `fetch_stock`/`need` and grading shared C-numbers on their combined need, as `check_stock.main` does. Run `python hardware/programmer/scripts/check_stock_prog.py --boards 5`. Expected: every line `OK`, exit 0.
  - If a C-number is missing or short, pick a JLCPCB-stocked substitute in the same footprint, record it in `note` with the date, and re-run.
  - If the CH343P is out, fall back per spec §6.5: CH9102F (C2858418, `Interface_USB:CH9102F`) first, CP2102N/CH340 last, with the reason.
- [ ] **Step 6: Commit**
```bash
git add hardware/programmer/scripts/parts.py hardware/programmer/scripts/check_stock_prog.py hardware/programmer/scripts/test_parts.py
git commit -m "feat(programmer): parts table and JLCPCB stock gate"
```

### Task 2: Schematic generator, ERC and the netlist gate

**Files:**
- Create: `hardware/programmer/scripts/schlib.py`. These are the sheet-building helpers, copied from `hardware/scripts/gen_mcu_can.py`'s pattern (`place`, `vpart`, `hpart`, `gnd`, `w`, `j`, `nc`, `lab`, `ongrid`, `from_library`, sheet writer). Module state lives in a `Sheet` object, not in globals.
- Create: `hardware/programmer/scripts/gen_sch.py`, which writes `hardware/programmer/prog.kicad_sch` and `prog.kicad_pro`.
- Create: `hardware/programmer/scripts/check_netlist_prog.py`
- Test: `hardware/programmer/scripts/test_netlist_prog.py`
- Output: `hardware/programmer/output/netlist.net` and `erc.rpt`

**Interfaces:**
- Consumes: `parts.PARTS`; `hardware/scripts/kicanon.canonicalise(text) -> str`; `hardware/scripts/check_netlist.load(path) -> Netlist`, which gives `pin_net`, `part_pins`, `nets`, `pinfunc` and `pins_of(ref, func_prefix)`.
- Produces:
  - `gen_sch.build() -> str`: the canonical sheet text, also written to disk.
  - `check_netlist_prog.check(nl) -> list[str]`: failures, empty on PASS. `main()` exits 1 on failure.
  - `check_netlist_prog.budget() -> dict`: the computed numbers below, so tests and the README read one source.
  - Net names: as listed under "Decided here".

- [ ] **Step 1: Write the failing tests** in `test_netlist_prog.py`. They run against the generated `output/netlist.net`. Each test also mutates a copy of the loaded `Netlist` to prove that `check()` catches the fault.
  - `test_j2_pinout`: `J2.1..6` nets are `+3V3_OUT`, `GND`, `UART_TX`, `UART_RX`, `DTR`, `RTS`.
  - `test_txrx_crossed`:
    - header pin 3 reaches U1's `RXD` pin through exactly R3 (4.7k);
    - pin 4 reaches U1's `TXD` through exactly R4 (470R);
    - pin 5 reaches a U5 output through R5 (220R), and that channel's input is on U1 `~{DTR}`;
    - pin 6 does the same through R6 (220R) to `~{RTS}`;
    - no header pin is on any U1 pin directly.
    - Mutation: swap U1's TXD/RXD nets, and `check()` reports `TX/RX`.
  - `test_cc_pulldowns`: CC1 and CC2 each have exactly one 5.1k resistor to `GND`.
  - `test_usb_pair`: J1 A6/B6 and U1 UD+ are on `USB_DP`, J1 A7/B7 and U1 UD− on `USB_DN`, and U2's I/O pins sit on both nets with U2 VBUS on `VBUS`.
  - `test_reverse_blocking_topology`:
    - U3 VI is on `VBUS` and VO on `+3V3_USB`;
    - U4 VIN is on `+3V3_USB`, VOUT on `+3V3_OUT`, and ~CE on `GND`;
    - `+3V3_OUT` members are exactly `{J2.1, U4.6, C4.*, C5.*}`, so nothing else draws from or feeds the output.
  - `test_u1_supplies`: VDD5 and VBUS are on `VBUS`, VIO on `+3V3_USB`, both GND pins on `GND`, and no U1 pin is on `+3V3_OUT`. U5 VCC is on `+3V3_USB` and both ~OE pins on `GND`.
  - `test_power_budget`:
    - `budget()["v_at_mccan_min"] >= 3.0`, computed from 3.234 V − 0.6 A × (U4 0.079 Ω + cable 0.2 Ω);
    - `budget()["u3_watts"] <= 1.1`, from (5.25 − 3.234) × 0.6.
  - `test_misplug_currents`: for each signal series resistor, 3.34 V / R ≤ 15 mA. R3, R4, R5 and R6 values come from the netlist, not constants.
  - `test_unpowered_backfeed_budget`:
    - `budget()["rxd_backfeed_ma"] <= 1.0`, computed from (3.34 − 0.5) / R3;
    - `budget()["en_hold_v"]`: the EN_MCU voltage when an unpowered programmer is attached, = 3.34 − 10k × Ioff, with Ioff = 10 µA from the SN74LVC2G125 datasheet's Ioff max (≈ 3.24 V).
    - The test asserts `en_hold_v >= 2.5` (the ESP32's VIH is 0.75 × VDD).
    - A second assertion pins the reason for U5. With U5 removed from the path, the same formula, I = (3.34 − 1.1) / (10k + 10k + R6) and EN = 3.34 − 10k × I, gives `< 2.5`. `budget()` exposes it as `en_hold_v_without_buffer`.
- [ ] **Step 2: Run** `python hardware/programmer/scripts/test_netlist_prog.py`. Expected: FAIL (no netlist yet).
- [ ] **Step 3: Implement `schlib.py` and `gen_sch.py`.**
  - One A4 sheet with title block "MCCAN programmer", rev "A", date 2026-11-14.
  - Pull symbols with `from_library` from KiCad's stock symbol libraries, plus `power:GND`.
  - Put a label at every wire end.
  - Put no-connect flags on the unused pins listed above.
  - Set each symbol's `Footprint` and `LCSC` fields from `parts.PARTS`.
  - Use deterministic uuid5 keys with the `"prog:"` namespace.
- [ ] **Step 4: Generate and export.** Run from `hardware/programmer/`:
```bash
K="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
python scripts/gen_sch.py
"$K" sch export netlist --format kicadsexpr -o output/netlist.net prog.kicad_sch
"$K" sch erc --severity-all --exit-code-violations -o output/erc.rpt prog.kicad_sch
```
  Expected: the ERC report shows `** Found 0 violations **`.
- [ ] **Step 5: Read the netlist by hand** (memory: ERC alone misses things). Check every U1, U3 and U4 pin against "Decided here", then run the tests. Expected: `test_netlist_prog: PASS` and `python scripts/check_netlist_prog.py` prints `PASS`.
- [ ] **Step 6: Commit**
```bash
git add hardware/programmer
git commit -m "feat(programmer): generated schematic, ERC 0, netlist gate with power and back-feed budgets"
```

### Task 3: Board layout, routing and DRC

**REQUIRED SKILL:** load `pcb-layout-routing` before starting this task.

**Files:**
- Create: `hardware/programmer/scripts/gen_pcb.py`, which writes `hardware/programmer/prog.kicad_pcb` and `prog.kicad_dru`.
- Create: `hardware/programmer/scripts/check_board.py`
- Test: `hardware/programmer/scripts/test_board.py`
- Output: `hardware/programmer/output/drc.rpt`

**Interfaces:**
- Consumes: `output/netlist.net`; `parts.PARTS`; KiCad's stock `.kicad_mod` files.
  - Import `load_fp` and `build_footprint` from `hardware/scripts/gen_pcb.py` only if `python -c "import gen_pcb"` from `hardware/scripts` has no side effects (writes nothing, reads no board).
  - Otherwise copy the minimal footprint-instancing code into `hardware/programmer/scripts/pcblib.py`, and record the choice as a ruling.
- Produces:
  - `gen_pcb.PLACE: dict[str, tuple[float, float, float]]` (ref → x, y, rot; mm; top side)
  - `gen_pcb.ROUTES: list[tuple[str, str, list[tuple[float, float]], float]]` (net, layer, polyline, width)
  - `check_board.check(path) -> list[str]`

Layout decisions:
- Outline is 20 × 40 mm with 1 mm corner radii.
- J1 sits at the y = 0 end with its receptacle flush with the edge, as its footprint's edge line requires.
- J2 sits at the far end along the board's short axis, pin 1 on the left seen from the top with USB away from the viewer.
- Order from the USB end: U2 next to J1, U1 with U5 beside it, then U3 with C1/C3, then U4 with C4/C5 next to J2.
- The LEDs sit along one long edge.
- Routes are hand-coded and deterministic. Do not use an autorouter.
- Power traces are ≥ 0.5 mm (`VBUS`, `+3V3_USB`, `+3V3_OUT`).
- `USB_DP`/`USB_DN` run as a pair on F.Cu, 0.3 mm wide, with no vias and no stubs, through U2's pads.
- Pour solid GND on both layers and stitch it with vias. U3's tab (pin 2, VO) gets a ≥ 60 mm² `+3V3_USB` F.Cu pour for heat.
- The DRU uses JLCPCB's standard 2-layer limits (0.127 mm track and space, 0.3 mm drill), with the same comment style as `hardware/mccan.kicad_dru`.
- Silkscreen: "MCCAN PROG rev A"; a "1" and a triangle at J2 pin 1; the six net names `3V3 GND TX RX DTR RTS` beside J2's pins, using the MCCAN board's names as seen *at the MCCAN board*; LED labels `PWR TX RX`.

- [ ] **Step 1: Write the failing tests** in `test_board.py`:
  - `test_outline_size`: the Edge.Cuts bounding box is ≤ 22 × 42 mm.
  - `test_all_top_side`: every footprint is on `F.Cu`.
  - `test_every_part_placed`: the footprint refs equal `set(parts.PARTS)`.
  - `test_j1_at_edge` and `test_j2_far_end`: the J1 origin is within 2 mm of one short edge and J2 within 5 mm of the other.
  - `test_header_silk`: F.Silkscreen text contains each of `3V3 GND TX RX DTR RTS`, plus "MCCAN PROG" and a pin-1 mark within 2 mm of J2 pin 1.
  - `test_usb_pair_routing`: `USB_DP` and `USB_DN` have no vias. Each net's track length from J1 to U1 is within 1 mm of the other's and ≤ 15 mm.
  - `test_regulator_heatsink_pour`: a `+3V3_USB` F.Cu zone ≥ 60 mm² contains U3 pad 2.
  - `test_power_track_widths`: every track on `VBUS`, `+3V3_USB` and `+3V3_OUT` is ≥ 0.5 mm.
- [ ] **Step 2: Run** `python hardware/programmer/scripts/test_board.py`. Expected: FAIL (no board).
- [ ] **Step 3: Implement `gen_pcb.py` and `check_board.py`.** `gen_pcb.py` must write a `.kicad_pro` netclass setup that matches the DRU.
- [ ] **Step 4: Generate the board and run DRC.** Run from `hardware/programmer/`:
```bash
python scripts/gen_pcb.py
"$K" pcb drc --refill-zones --severity-all --schematic-parity --exit-code-violations -o output/drc.rpt prog.kicad_pcb
```
  Expected:
  - `** Found 0 DRC violations **`
  - `** Found 0 unconnected pads **`
  - `** Found 0 Footprint errors **`
  - If DRC fails, fix the generator, never the board file.
- [ ] **Step 5: Run the tests.** Expected: `test_board: PASS`. Render both sides with `"$K" pcb render` to `output/render-top.png` and `output/render-bottom.png`, and look at them: silk legible and not on pads, pin 1 obvious.
- [ ] **Step 6: Commit**
```bash
git add hardware/programmer
git commit -m "feat(programmer): generated 2-layer board, hand routes, DRC 0 at all severities"
```

### Task 4: JLCPCB fab package

**Files:**
- Create: `hardware/programmer/scripts/gen_fab_prog.py`
- Test: `hardware/programmer/scripts/test_fab_prog.py`
- Output: `hardware/programmer/output/jlcpcb/` containing `gerbers.zip`, `bom.csv`, `cpl.csv`, `assembly.pdf`, `stock.txt`, `rotation-review.txt` and `board.sha256`

**Interfaces:**
- Consumes:
  - `parts.PARTS` and `parts.bom_lines()`;
  - `check_stock_prog.main`;
  - the board from Task 3;
  - `hardware/scripts/gen_fab.py`'s patterns: `ROT_FIX` with trust labels `"recalled"`/`"unverified"`, the pad-centre CPL for THT parts (`pad_centre`, `cpl_xy`), and the sha256 stamp over the CRLF-normalised board. Copy what is needed; `gen_fab.py` imports `layout_pcb`, which is main-board-specific.
- Produces: `gen_fab_prog.build()` and `gen_fab_prog.check() -> list[str]`. The CLI is `--check`.

- [ ] **Step 1: Write the failing tests** in `test_fab_prog.py`. Each runs `check()` against the generated package and against a deliberately broken copy in a temp directory.
  - `test_bom_covers_every_part`: each designator appears exactly once and each LCSC matches `parts.PARTS`.
  - `test_cpl_matches_board`: the CPL row count equals the footprint count, every Layer is `top`, and J1/J2 sit at their pad centres.
  - `test_rotation_review_lists_polarised`: U1–U5, D1–D3, J1 and J2 each appear in `rotation-review.txt` with a trust label in `{"recalled","unverified"}`, and the header says to check EVERY row in JLCPCB's preview.
  - `test_stamp_matches_board`: `board.sha256` equals the board's hash, and appending a byte to a copy of the board makes `check()` fail.
  - `test_gerbers_complete`: the zip holds F/B Cu, Mask, Paste and Silk, Edge.Cuts, and PTH and NPTH drill files.
- [ ] **Step 2: Run** `python hardware/programmer/scripts/test_fab_prog.py`. Expected: FAIL.
- [ ] **Step 3: Implement `gen_fab_prog.py`.**
  - `build()` runs DRC (as in Task 3), and stops if it is not 0. It then exports Gerbers and drill with `kicad-cli pcb export gerbers`/`drill` (JLCPCB settings as in `gen_fab.py`), writes `bom.csv` (`Comment,Designator,Footprint,LCSC`), `cpl.csv` (`Designator,Mid X,Mid Y,Layer,Rotation`) and `assembly.pdf` (F.Fab plus Edge.Cuts), runs the stock check into `stock.txt`, and writes the stamp last.
  - ROT_FIX entries for SOT-223, SOT-23-6, SC-70-6, SSOP-8, the WCH QFN-16, USB-C and the 1×6 header start as `"unverified"`, except where the main board's `ROT_FIX` already holds a `"recalled"` value for the same footprint family.
- [ ] **Step 4: Build and check.** Run `python scripts/gen_fab_prog.py && python scripts/gen_fab_prog.py --check && python scripts/test_fab_prog.py`. Expected: `check: PASS` and `test_fab_prog: PASS`.
- [ ] **Step 5: Commit**
```bash
git add hardware/programmer
git commit -m "feat(programmer): JLCPCB fab package with rotation review and board stamp"
```

### Task 5: README, ordering notes and the whole-project gate

**Files:**
- Create: `hardware/programmer/README.md`
- Create: `hardware/programmer/scripts/gate.sh`, which runs every gate and exits nonzero on any failure.

**Interfaces:**
- Consumes: every script above.
- Produces: `bash hardware/programmer/scripts/gate.sh`. It prints one `PASS`/`FAIL` row per gate: tests, ERC, netlist, DRC, fab check, stock.

- [ ] **Step 1: Write `gate.sh`** in `hardware/README.md`'s style (`ok=1; … || ok=0; [ $ok = 1 ]`). It runs `test_parts`, `test_netlist_prog`, `test_board` and `test_fab_prog`, regenerates the netlist and checks that ERC is 0, then runs `check_netlist_prog`, DRC, `gen_fab_prog --check` and `check_stock_prog --boards 5`. Make it fail first: point it at a missing script, run it, and expect `FAIL` and a nonzero exit. Then fix it.
- [ ] **Step 2: Write `README.md`** with:
  - what the board does (spec §1–2);
  - the regenerate-and-gate commands;
  - the "Decided here" table with reasons, plus any rulings from Tasks 1–4;
  - the power and back-feed budget numbers, quoted from `check_netlist_prog.budget()` output (paste the printed values);
  - the order notes:
    - 5 pcs, 2 layers, 1.6 mm, standard assembly, top side;
    - THT service for J2;
    - check every rotation-review row in JLCPCB's preview;
    - re-run the stock check the day the order is placed;
    - order **together with the MCCAN boards** (spec §10);
  - what to buy separately (spec §7): a 6-way F-F 2.54 mm straight-through jumper cable, 10–20 cm (buy spares), and a USB-C cable;
  - the bench acceptance checklist, copied from spec §8 as checkboxes. Add one more item from Review Focus 1: with the programmer attached, USB unplugged and the MCCAN board on its bench supply, the ESP32 keeps running (no reset, serial log continues).
  - Mention that the first flash over J2 should be a build with the real OTA key (`tools/sign_update.py keygen`).
- [ ] **Step 3: Run** `bash hardware/programmer/scripts/gate.sh`. Expected: every row `PASS`, exit 0.
- [ ] **Step 4: Confirm that main-board files are untouched.** Run `git diff --stat 917355b -- hardware ':!hardware/programmer'`. Expected: empty output.
- [ ] **Step 5: Commit**
```bash
git add hardware/programmer
git commit -m "docs(programmer): README, order notes, bench acceptance; one-command gate"
```
