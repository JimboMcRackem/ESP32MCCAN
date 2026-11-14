# Board Layout Phase B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate an orderable 100 × 140 mm, 8-layer, JLCPCB-assembled `mccan.kicad_pcb` for the
phase A + aux stage schematic. It must have test points, a stock-checked BOM, 0 DRC errors and
complete fabrication outputs.

**Architecture:** The board stays **generated**. `gen_pcb.py`'s generic machinery is kept: it
reads the netlist, loads footprints, places parts on an occupancy grid, and writes zones,
outlines and holes. `layout_pcb.py` is rewritten from scratch as the plan4 placement and rules
data. Plan3's hand routes are replaced by plan4 power routes. Signal nets are routed headlessly
by KiCadRoutingTools (`route_external.py`), and `freeze_routes.py` captures the result into
`routes_signal.json`. Every gate is a script with an exit code.

**Tech Stack:** Python 3.14 (`python`), KiCad 10.0.2 `kicad-cli` at
`C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`, and KiCadRoutingTools v0.22.1 at
`C:\Users\jimba\KiCadRoutingTools` (its own `.venv`). The LCSC/JLCPCB part data is fetched over
HTTPS.

**Spec:** `docs/superpowers/specs/2026-11-13-board-layout-phase-b-design.md`. The electrical
authority is the schematic, plus `docs/superpowers/specs/2026-11-13-aux-stage-design.md`.

**Worktree / branch:** `D:\Projects\ESP32MCCAN-pcb`, `plan4-emarked-modules`. This is a board
branch: never merge it into main. All paths below are relative to that worktree.

## Global Constraints

- The board outline is **100 × 140 mm**. If placement cannot fit, **STOP and ask the owner**
  which dimension grows (cable edge or depth). Never grow it silently. 200 × 140 is never
  acceptable.
- **8 copper layers** (`F.Cu`, `In1`–`In6.Cu`, `B.Cu`). Use JLCPCB's 8-layer capability and
  stackup, fetched and recorded in Task 3. Do not use PCBWay rules.
- **Components on the top side only.** Every component is placed by the assembler. J2 is the only
  through-hole part: list it in the BOM as assembled (THT) if JLCPCB stocks a 1×6 2.54 mm header,
  otherwise DNP with its pads kept. Record which.
- **Every BOM line has an LCSC part number with stock ≥ 5 × qty-per-board + 10% (minimum 10).**
  A failing line gets a stocked, footprint-compatible alternative, changed through the schematic
  generators. The owner places the order.
- **All wire tails (J1, J3, J4, J5, J8, J9, J10, J11) sit on one edge, the cable edge.** Two
  staggered rows are allowed.
- **U5's antenna sits on the edge opposite the cable edge.** No copper on any layer inside
  Espressif's antenna keep-out (WROOM-32E datasheet, PCB-layout section).
- **Ground separation:**
  - `GND_IN` ↔ `GND` only through L2.
  - `GND_B` ↔ `GND_IN` only through NT1.
  - No pour, via or capacitor bridges them.
- **Copper sizing:** IPC-2152 at ≤ 20 K rise:
  - 6.4 A continuous on `FEED_B_P`, `VBAT_B` and `GND_B`;
  - 3.2 A on each of `POD_L_P` and `POD_R_P`;
  - 1 A on feed A (`FEED_P` … `VBAT`).
- **Design ambient is 85 °C.**
- **Generated, never hand-edited:** `python scripts/gen_pcb.py` must reproduce
  `mccan.kicad_pcb` byte for byte from the netlist, `layout_pcb.py` and `routes_signal.json`.
- **Commits** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Push only when
  the owner asks.

## Review Focus

1. **Part orientation in the JLCPCB CPL.** Electrolytics (C3, C65, C68), diodes, SOT-23 and
   ESP32 parts must land the right way round. Task 8 checks the rotation table against the
   footprint origin for every polarised part.
2. **Ground split broken by an inner-layer pour or a stitching via.** Task 5's
   `check_grounds.py` must fail on a deliberate bridge (mutation step).
3. **Antenna keep-out violated on an inner layer.** Copper the top-layer view would not show.
   Task 4's `check_antenna.py` checks all 8 layers.
4. **High-current paths necked by vias or antipads.** Task 6's `check_plane_width.py` grades the
   narrowest cut on each feed-B net after routing, not before.
5. **Stock gone between the check and the order.** Task 2's `check_stock.py` is re-runnable,
   exits non-zero on any short line, and names that line's fallback.

---

### Task 1: Test points in the schematic

**Files:**
- Modify: `hardware/scripts/gen_outputs.py`, `gen_power_input.py` (or `layout_power_input.py`),
  `gen_mcu_can.py`, `gen_rails.py`; the sheet each net lives on gets its pads.
- Modify: `hardware/scripts/fpmap.py`, `hardware/scripts/check_netlist.py`

**Interfaces:**
- Produces: refs `TP1`… with symbol `Connector:TestPoint`, footprint
  `TestPoint:TestPoint_Pad_D1.5mm`, `in_bom` false (bare copper). Net list `TESTPOINTS` in
  `check_netlist.py`.

- [ ] **Step 1: Write the failing check.** Add group `testpoints` to `check_netlist.GROUPS`, with
  `chk_testpoints(nl)`. For each net in
  `TESTPOINTS = ["VBAT","VBAT_B","VLOGIC_IN","+3V3_ALW","+5V","GND","GND_B","GND_IN","EN_5V","CAN_RXD","CANH","CANL","AUX_PWM","YEL_L","YEL_R","POD_L_P","POD_R_P","SNS_A","SNS_B","SNS_C","FL_DRL","FL_IND","FR_DRL","FR_IND","RL_DRL","RL_IND","RL_BRK","RR_DRL","RR_IND","RR_BRK"]`,
  assert that exactly one part with ref `TP\d+` is on it, and that its footprint ends in
  `TestPoint_Pad_D1.5mm`. Ruling recorded in the spec: lamp nets get pads too, because the
  wire-tail pads are covered once the harness is soldered.
- [ ] **Step 2: Export the netlist and run the check.** Use the commands in Task 1 Step 4.
  Expected: `FAIL testpoints (30)`.
- [ ] **Step 3: Add the test points.** Each `TP` goes on the sheet that owns its net, with a
  wire stub and a local or hierarchical label, following each generator's existing conventions
  (on grid, label at the wire end). Add the footprint mapping for `TP\d+` in `fpmap.py` and
  make `in_bom()` return False for `TP*`.
- [ ] **Step 4: Verify.** Run, from `hardware/`:
  ```
  python scripts/symlib.py; for g in gen_power_input gen_rails gen_mcu_can gen_outputs gen_root; do python scripts/$g.py; done
  "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch export netlist --format kicadsexpr -o output/netlist.net mccan.kicad_sch
  "/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch erc --severity-all -o output/erc.rpt mccan.kicad_sch
  python scripts/check_netlist.py; python scripts/verify_fpmap.py
  ```
  Expected: `Found 0 violations`, every group `PASS` (8 groups), `FAILURES : 0`. A second run of
  the generators changes no file (compare with md5sum).
- [ ] **Step 5: Commit.** `hw(sch): test points on rails, grounds, CAN, aux, sense and lamp nets`

### Task 2: LCSC part numbers, stock check, fallbacks

**Files:**
- Create: `hardware/scripts/lcsc.py`: the BOM-line → LCSC mapping, plus fallbacks.
- Create: `hardware/scripts/check_stock.py`
- Modify: the schematic generators for any part that is swapped. Modify
  `hardware/docs/part-selection.md` (new section "JLCPCB BOM, 2026-11").

**Interfaces:**
- Produces: `lcsc.LCSC: dict[str, dict]`, keyed by BOM line key `"<value>|<footprint>"`, holding
  `{"lcsc": "C1234", "mpn": str, "fallback": "C5678" | None, "note": str}`. Also
  `lcsc.bom_lines(netlist_path) -> list[tuple[key, list[ref]]]`, which groups non-DNP,
  `in_bom()` parts by value + footprint. Task 8 consumes both.
- Produces: `check_stock.py [--boards N]`, default N = 5. It prints one line per BOM line,
  `OK|SHORT|MISSING <key> <lcsc> stock=<n> need=<n> fallback=<c>`, and exits 1 on any
  `SHORT`/`MISSING`.

- [ ] **Step 1: Write the failing check.** `check_stock.py --offline` asserts only that every
  `bom_lines()` key has an `LCSC` entry. Run it. Expected: exit 1, listing every line as
  `MISSING`.
- [ ] **Step 2: Fill `lcsc.py`.** For each line, pick a JLCPCB/LCSC part matching the value, the
  footprint, and any voltage, power or tolerance the schematic notes pin. These include:
  - 100 V for the 0805s on `VBAT` and `VBAT_B`;
  - 63 V V-chips C3, C65 and C68, choosing C65's orderable part now;
  - R100 33 mΩ 1% 2512, ≥ 1 W;
  - R84/R85 1206;
  - U15 **74AHCT2G126DC** (not the "DP");
  - the automotive parts already selected in `part-selection.md`.

  Prefer JLCPCB Basic, then Extended. Set a fallback for any line with stock < 200.
- [ ] **Step 3: Live stock check.** `check_stock.py` fetches stock per C-number from LCSC. Use
  `https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=<C>`, or JLCPCB's parts search if
  that endpoint is gone. Record the endpoint used in the script's docstring. Run it. Expected:
  exit 0. Every `SHORT` line gets its part swapped in the generator, `fpmap.py` if the footprint
  changes, and `lcsc.py`, and Task 1 Step 4's verification re-runs green.
- [ ] **Step 4: Commit.** `hw(bom): LCSC part numbers, stock check with fallbacks`

### Task 3: Board frame: outline, stackup, rules, net classes

**Files:**
- Rewrite: `hardware/scripts/layout_pcb.py`, keeping the module names `gen_pcb.py` reads
  (`EDGE_R`, `MOUNT_*`, `REGIONS`, `PLACE`, `KEEPCLEAR`, `NETCLASSES`, `NOTES`, `ROUTES`,
  `ROUTE_VIAS`). Drop every plan3 ref and table: `CHANNELS`, `BUDGET`, `TIM_PADS`,
  `GND_IN_ISLAND` as written, and `FROZEN_DROP`. Remove the matching `gen_pcb.py` code paths
  (RGB-era `routes()` content, `tim_areas`, `gnd_drops` if unused) rather than leaving them
  dormant.
- Modify: `hardware/scripts/gen_pcb.py` (board size, layer stack), `gen_netclasses.py`,
  `hardware/mccan.kicad_dru`
- Delete: `hardware/scripts/routes_signal.json` (plan3 copper)
- Create: `hardware/scripts/check_frame.py`

**Interfaces:**
- Produces: `layout_pcb.BOARD_W = 140.0`, `BOARD_H = 100.0`, and
  `CABLE_EDGE = "bottom" | "top" | "left" | "right"` (the builder chooses; a 140 mm edge is
  expected). `ANTENNA_EDGE` is the opposite edge. `STACKUP`: a list of the 8 copper layers with
  roles.

- [ ] **Step 1: Write `check_frame.py`.** It parses `mccan.kicad_pcb` and asserts:
  - the Edge.Cuts bounding box is 140.0 × 100.0 mm (±0.01);
  - there are exactly 8 copper layers;
  - there are 4 mounting holes of 3.2 mm drill, 5 mm in from each corner;
  - the DRU minima are ≥ the JLCPCB 8-layer capability recorded in the `layout_pcb.py`
    docstring.

  Run it against the current file. Expected: FAIL (200 × 140).
- [ ] **Step 2: Fetch JLCPCB's 8-layer capability** and its default 8-layer 1.6 mm impedance
  stackup. Record the trace/space, via drill/annular ring and copper weights in the
  `layout_pcb.py` docstring, with the source URL and date. Set the layer roles in `STACKUP`. A
  sensible default:

  | Layer | Role |
  |---|---|
  | F.Cu | parts and signal |
  | In1 | `GND` plane |
  | In2 | signal |
  | In3 | power (`VBAT` / `VBAT_B` / `+3V3_ALW` / `+5V` areas) |
  | In4 | `GND` |
  | In5 | signal |
  | In6 | `GND` |
  | B.Cu | signal and pours |

  The `GND_IN` and `GND_B` regions are cut out of every `GND` layer under their footprints.
- [ ] **Step 3: Implement.** `gen_pcb.py` with the placement and route tables empty, so the
  board is frame only.
- [ ] **Step 4: Verify.** Run, from `hardware/`:
  `python scripts/gen_pcb.py && python scripts/check_frame.py && python scripts/gen_pcb.py && git diff --stat mccan.kicad_pcb`.
  Expected: PASS, and the second generation is byte-identical.
- [ ] **Step 5: Commit.** `hw(pcb): plan4 frame - 140x100, 8 layers, JLCPCB rules`

### Task 4: Placement

**Files:**
- Modify: `hardware/scripts/layout_pcb.py` (`REGIONS`, `PLACE`, `KEEPCLEAR`)
- Create: `hardware/scripts/check_placement.py`, `hardware/scripts/check_antenna.py`
- Reuse: `check_courtyards.py`, `check_density.py`

**Interfaces:**
- Consumes: `CABLE_EDGE`, `ANTENNA_EDGE`, `BOARD_W/H` (Task 3)

- [ ] **Step 1: Write the checks.**
  - `check_placement.py` asserts:
    - every netlist footprint is placed inside the outline;
    - every part is on F.Cu (bottom-side parts fail);
    - J1, J3, J4, J5, J8, J9, J10 and J11 all lie within 15 mm of `CABLE_EDGE`;
    - every `TP*` is on F.Cu, with no part courtyard overlapping the pad plus 1 mm;
    - each TP group has a `GND`, `GND_B` or `GND_IN` TP within 25 mm;
    - C67 and C68 are within 10 mm of U14 pad 15;
    - R100 is within 8 mm of U10 pin 4.
  - `check_antenna.py` asserts:
    - U5's antenna end faces `ANTENNA_EDGE` and is at the board edge (module overhang or
      flush, per Espressif);
    - **no copper on any of the 8 layers**, pads, zones or tracks, falls inside the keep-out
      rectangle taken from the WROOM-32E datasheet's layout guideline.

  Run both. Expected: FAIL (nothing placed).
- [ ] **Step 2: Place.** Regions:
  - the cable strip along `CABLE_EDGE`, all tails, in two staggered rows if needed, grouped so
    each harness cable is one gland;
  - feed B (J9, Q13, D24, D25, C66, C67, C68, U14, C69, C70) beside its tails;
  - feed A (J1, L2, U10, Q10, Q11, R100 … C65, the TVS);
  - rails (U1/U2 bucks and their inductors);
  - outputs (U11–U13 near J3/J4/J5);
  - aux buffer (U15, R81–R87, D26/D27 near J10/J11);
  - MCU + CAN (U5 at `ANTENNA_EDGE`, U6/L6/D6 near J8);
  - service (J2, SW1, SW2 reachable from the top).

  If `check_courtyards.py` or the region budgets cannot be met at 140 × 100, **STOP**. Report
  the shortfall (mm² needed vs available, and which region) and ask the owner which dimension
  grows.
- [ ] **Step 3: Verify.** Run, from `hardware/`:
  `python scripts/gen_pcb.py && python scripts/check_courtyards.py && python scripts/check_placement.py && python scripts/check_antenna.py && python scripts/check_frame.py`.
  Expected: all PASS. Render the top view with
  `kicad-cli pcb render --side top -o output/place_top.png mccan.kicad_pcb` and read it.
- [ ] **Step 4: Commit.** `hw(pcb): plan4 placement - cable edge, antenna edge, regions`

### Task 5: Zones and ground separation

**Files:**
- Modify: `hardware/scripts/layout_pcb.py` (zone table), `gen_pcb.py` `zones()`
- Modify: `hardware/scripts/check_grounds.py`, `check_zone_islands.py` (for plan4 nets)

- [ ] **Step 1: Update the checks.**
  - `check_grounds.py` asserts that:
    - no zone, track or via connects `GND` to `GND_IN` except through L2's pads;
    - `GND_B` meets `GND_IN` only at NT1;
    - every `GND_B` copper region is reachable from J9.2 without crossing `GND`;
    - the pod returns (J10.2, J11.2) and C67–C70 sit on `GND_B` copper only.
  - `check_zone_islands.py` asserts there is no orphan zone island on any net.

  Run both. Expected: FAIL (no zones).
- [ ] **Step 2: Implement the zones** per `STACKUP`:
  - `GND` planes on In1, In4 and In6, cut back around the `GND_IN` and `GND_B` regions on every
    layer;
  - a `GND_IN` island under J1/J9/L2-connector side/D2;
  - a `GND_B` region from J9.2 to J10/J11/U14's capacitors;
  - `VBAT_B` and `VBAT` power areas on In3;
  - stitching vias per net region.
- [ ] **Step 3: Mutation check.** Temporarily extend the In1 `GND` zone over the `GND_IN`
  island, and confirm `check_grounds.py` FAILS naming the bridge. Revert, then confirm the
  regenerated board is byte-identical to the pre-mutation output.
- [ ] **Step 4: Verify.** Run `python scripts/gen_pcb.py && python scripts/check_grounds.py && python scripts/check_zone_islands.py && python scripts/check_antenna.py`.
  Expected: PASS.
- [ ] **Step 5: Commit.** `hw(pcb): planes and the three-ground split`

### Task 6: Power and critical routes

**Files:**
- Modify: `hardware/scripts/layout_pcb.py` (`ROUTES`, `ROUTE_VIAS`), `check_plane_width.py`
- Create: `hardware/scripts/check_power_paths.py`

**Interfaces:**
- Produces: hand routes on these nets, which the autorouter must not touch:
  `FEED_P, MID, SNS, VBAT_PROT, VBAT_F, VBAT, FEED_B_P, VBAT_B, POD_L_P, POD_R_P, GND_B` (where
  not poured), the buck switch nodes, and `CANH/CANL`.

- [ ] **Step 1: Write the checks.**
  - `check_power_paths.py` computes, for each listed net, the narrowest copper cross-section
    along the path from source pad to load pad, summed across parallel layers. It asserts
    IPC-2152 capacity at ≤ 20 K rise for:
    - 6.4 A on `FEED_B_P`/`VBAT_B`/`GND_B`;
    - 3.2 A on `POD_x_P`;
    - 1 A on feed A.
  - It asserts that R100 has two Kelvin traces to U10.4 and `VBAT_PROT`, separate from the
    current path.
  - It asserts that `CANH`/`CANL` are routed as a pair with length mismatch ≤ 2 mm.
  - It asserts that U10's `ON` pad has no copper of another net within 0.5 mm, on its own
    layer or the next one, because its leakage must stay < 1 µA (README layout note).
  - Update `check_plane_width.py` to plan4 nets and currents.

  Run. Expected: FAIL.
- [ ] **Step 2: Route by hand** in `ROUTES` (or pour, where a zone is better). Use multiple
  layers with via arrays for feed B. Lay out the buck power loops (input cap, switch, inductor,
  output cap) to each buck datasheet's layout example, and cite the figure in a `layout_pcb.py`
  comment. Put Q13's and U14's thermal copper on the pads' nets with
  thermal via arrays.
- [ ] **Step 3: Dissipation tally.** Add a section to `hardware/docs/enclosure.md`, re-derived
  for plan4. Cover Q13 (6.4² × 16 mΩ), U14 (2 × 3.2² × R_DS(on) at 150 °C), U11–U13, the
  bucks, R100, D-clamps, and the board total. Estimate each hot part's junction temperature at
  85 °C ambient from its datasheet θJA, scaled to the copper it gets. **If any part exceeds its
  rating, or Tj > 125 °C, STOP and report** (the no-plate decision is reversed only by the owner).
- [ ] **Step 4: Verify.** Run `python scripts/gen_pcb.py && python scripts/check_power_paths.py && python scripts/check_plane_width.py && python scripts/check_grounds.py`.
  Expected: PASS.
- [ ] **Step 5: Commit.** `hw(pcb): power paths, Kelvin sense, CAN pair, dissipation tally`

### Task 7: Signal routing (headless) and freeze

**Files:**
- Modify: `hardware/scripts/route_external.py` (plan4 net list and checks),
  `freeze_routes.py` if the output format needs it
- Create: `hardware/scripts/routes_signal.json` (generated by `freeze_routes.py`)
- Modify: `hardware/docs/routing-tool.md` (plan4 section)

- [ ] **Step 1: Point `route_external.py` at plan4.** Give it the signal nets: every net not in
  Task 6's list, and not a pour. Exclude the antenna keep-out from routing (a keep-out zone on
  all layers). Constrain `SNS_A/B/C` to inner layers between `GND` planes, and keep them out of
  the feed-B and buck regions (a router keep-out per region).
- [ ] **Step 2: Route.** Run `python scripts/route_external.py`. Expected: every signal net
  connected, and the router's own checks green. If nets fail, adjust placement (Task 4 tables)
  or layer assignment and re-run. Do not hand-edit the routed board.
- [ ] **Step 3: Freeze and regenerate.** Run `python scripts/freeze_routes.py && python scripts/gen_pcb.py`.
  Then run `kicad-cli pcb drc --severity-all --schematic-parity --exit-code-violations -o output/drc.rpt mccan.kicad_pcb`.
  Expected: exit 0, 0 errors, 0 unconnected items, 0 parity issues.
- [ ] **Step 4: Run every check again.** Run `check_frame`, `check_placement`, `check_antenna`,
  `check_courtyards`, `check_grounds`, `check_zone_islands`, `check_power_paths`,
  `check_plane_width` and `check_vias`. Expected: all PASS. Then run `gen_pcb.py` twice more:
  the board must be byte-identical.
- [ ] **Step 5: Commit.** `hw(pcb): signal routing frozen; DRC clean`

### Task 8: Silkscreen, fabrication outputs, JLCPCB BOM/CPL

**Files:**
- Modify: `hardware/scripts/gen_pcb.py` `silk_refs()` (plan4 refs, TP net labels)
- Create: `hardware/scripts/gen_fab.py`
- Rewrite: `hardware/docs/fabrication.md` (JLCPCB, plan4)

**Interfaces:**
- Consumes: `lcsc.LCSC`, `lcsc.bom_lines()` (Task 2)
- Produces: in `hardware/output/jlcpcb/`:
  - `gerbers.zip`, including drill;
  - `bom.csv`, with columns `Comment,Designator,Footprint,LCSC`;
  - `cpl.csv`, with columns `Designator,Mid X,Mid Y,Layer,Rotation`;
  - `assembly.pdf`.

- [ ] **Step 1: Write the checks in `gen_fab.py --check`.** It asserts:
  - every placed non-DNP `in_bom` part appears once in `bom.csv` with a C-number;
  - no TP, wire tail or mounting hole is in the BOM or CPL;
  - every CPL row's rotation applies the `ROT_FIX` table (JLCPCB's per-package rotation
    offsets, for example SOT-23, SOIC and electrolytics), and every polarised part (C3, C65,
    C68, all D*, Q*, U*) has an explicit `ROT_FIX` entry or a recorded "0 verified".

  Every silkscreen reference and TP label must be on F.Silkscreen, not on a pad, and not
  clipped by the outline. Run it. Expected: FAIL (no outputs).
- [ ] **Step 2: Implement `gen_fab.py`.** It drives `kicad-cli pcb export gerbers/drill/pos/pdf`
  and writes the JLCPCB-format BOM and CPL. Then run `check_stock.py` and include its report in
  `output/jlcpcb/stock.txt`.
- [ ] **Step 3: Verify.** Run `python scripts/gen_fab.py && python scripts/gen_fab.py --check && python scripts/check_stock.py`.
  Expected: PASS, exit 0. Render top and bottom 3D views (`kicad-cli pcb render`) and read
  them: parts the right way round, TP labels legible, antenna clear. Record the tallest part's
  height in `fabrication.md`.
- [ ] **Step 4: Commit.** `hw(fab): JLCPCB gerbers, BOM, CPL, assembly drawing`

### Task 9: Docs and hand-over

**Files:**
- Modify: `hardware/README.md` ("Phase-A board status" → phase B status; verification gates for
  the plan4 board; remove the "abandoned plan3 board" warnings that no longer apply),
  `hardware/docs/harness.md` (pad rows and gland grouping), `docs/bench/` unchanged.

- [ ] **Step 1: Update the docs.** Cover:
  - the outline and why it fits;
  - the stackup;
  - the gate commands, in run order;
  - how to re-run the stock check before ordering;
  - the J2 decision;
  - the gland count and grouping;
  - the open items (R82–R85 values and the blue pad, which wait on bench measurements and change
    values only).
- [ ] **Step 2: Final full run.** Run, from `hardware/`:
  - every schematic generator, then the netlist export, ERC and `check_netlist`;
  - `gen_pcb.py`, then every `check_*.py`;
  - DRC with schematic parity;
  - `gen_fab.py --check` and `check_stock.py`.

  Expected: all green. Record the output summary in the README.
- [ ] **Step 3: Commit.** `docs: phase B board status and ordering checklist`
