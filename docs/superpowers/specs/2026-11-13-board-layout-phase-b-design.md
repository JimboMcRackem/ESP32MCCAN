# Board layout, phase B: 100 × 140 mm, 8 layers, assembled by JLCPCB/PCBWay

**Date:** 2026-11-13
**Branch:** `plan4-emarked-modules`. This is a board branch: it is never merged into main, only
cherry-picked.
**Builds on:**
- The phase A schematic and the aux stage (`2026-11-13-aux-stage-design.md`). The schematic is
  complete: ERC is clean and `check_netlist.py` passes. It is the electrical authority.
- Redesign spec `2026-10-17-emarked-module-redesign-design.md`, main's copy. §4.1.1 covers
  feeds, §3.1 the harness, §4.4 the output stage. §2.2.1 has the pod measurements.

**Replaces:** the abandoned plan3 board (`mccan.kicad_pcb`, `output/gerbers/`). It is **not** a
starting point. See `hardware/README.md`, "Phase-A board status".

---

## 1. Intent

Turn the finished phase A schematic into a board that can be ordered: **5 prototypes**, fully
assembled by **JLCPCB or PCBWay**. It goes in a plastic box under the Experia's fairing, next to
the bike's main charge board.

The owner's test of success: **the boards come back and nothing is out of stock, and nothing
needs hand soldering.** The only soldering left to the owner is the harness: wires onto the
solder-tail pads.

## 2. Goals

1. **Outline of 100 × 140 mm**, the charge board's footprint, if the design fits. If it really
   cannot fit, **stop and show the owner the trade-off before growing either dimension**: a
   longer cable edge against a deeper board. The owner chooses (2026-11-13). 200 × 140 mm
   (plan3) is not acceptable.
2. **At least 8 copper layers.** This is the owner's requirement, for signal-switching headroom.
3. **Every BOM line is orderable from JLCPCB's own stock at order time.** Each line needs an
   LCSC part number with stock of at least 5 boards' worth plus attrition. **The owner places the
   order.** The deliverable therefore includes a stock-check script the owner re-runs just before
   ordering, plus a pre-chosen fallback part for every thinly stocked line (C65 has no orderable
   part chosen yet). A part without stock
   gets a stocked, footprint-compatible alternative now, and the schematic is updated through its
   generator. Basic parts are preferred over extended ones where they are equivalent, but stock
   decides, not cost.
4. **Assembly-only, no hand soldering:**
   - every component is placed by the assembler;
   - everything is SMD on **one side** (top), unless something truly cannot be;
   - the electrolytic capacitors (C3, C65, C68) are SMD V-chip types;
   - the 6-pin programming header J2 is the only through-hole part. It is either fitted by the
     assembler or left DNP with its pads kept. Choose one and record it, but the owner must
     never be left with a part to fit.
5. **All cables leave from one edge:** J1, J9, J3, J4, J5, J8, J10 and J11, all soldered
   wire-tail pads with strain-relief holes (the D5 convention). Each cable passes through a gland
   in the box wall on that edge.
6. **The WiFi works in a plastic box.** The ESP32 module (U5) sits at the board edge **opposite
   the cable edge**. Its antenna follows Espressif's keep-out: no copper on any layer under the
   antenna or around it.
7. **Lid-off service only:** J2, SW1 (BOOT) and SW2 (EN/RESET) need only be reachable with the
   lid off. Normal firmware updates go over WiFi (signed OTA already exists).
8. **Test points (owner's request, 2026-11-13).** Use bare SMD test pads: copper only, with no
   part to buy or fit, so they add nothing to the BOM or the assembly. Put them on the top side,
   reachable with the lid off, with a GND pad within probe-clip reach of each group. Label each
   one on the silkscreen with its net name.
   - **Rails:** `VBAT`, `VBAT_B`, `VLOGIC_IN`, `+3V3_ALW`, `+5V`.
   - **Grounds:** `GND`, `GND_B` and `GND_IN`, one each, so the split can be checked on the bench.
   - **Control:** `EN_5V`, `CAN_RXD`, `CANH`, `CANL`.
   - **Aux stage:** `AUX_PWM`, `YEL_L`, `YEL_R`, `POD_L_P`, `POD_R_P`.
   - **Sense:** `SNS_A`, `SNS_B`, `SNS_C`.
   - **Signal outputs:** one pad per lamp net (`FL_DRL` … `RR_BRK`), unless the wire-tail pads
     already give a clean probe point. The builder decides and records which.

   Test points are schematic symbols (`TestPoint` → a bare-pad footprint). They are added
   through the sheet generators, and `check_netlist.py` checks that each one exists on its net.
9. **Fabrication outputs:** Gerbers, drill, JLCPCB's BOM and CPL, an assembly drawing, and
   0 DRC errors against **JLCPCB's 8-layer rules**. `hardware/docs/fabrication.md` was written
   for PCBWay and is re-derived for JLCPCB.

## 3. Non-goals

- Designing the box, glands or harness. The box is chosen to fit the board afterwards. The
  harness is `hardware/docs/harness.md`.
- Any firmware change.
- Lamp-out diagnostics on the pods. There is no GPIO for it (aux stage A3).
- Re-using anything from the plan3 board file, or its placement.

## 4. Anti-goals: these make it a failure even if it passes DRC

- A part out of stock at the assembler, or one that silently becomes "consigned" or
  "hand-placed".
- A component the owner has to solder.
- WiFi that does not work inside the box because copper or metal sits by the antenna.
- A hand-edited board file that the scripts can no longer reproduce (§6).

## 5. Constraints

### 5.1 Physical

- **Box depth is about 50 mm.** The tallest parts are the V-chip electrolytics, about 10.5 mm,
  so height is not a constraint. Still record the tallest part in the outputs, so the box can be
  chosen.
- **Four mounting holes** (M3), one in each corner.
- **The cable edge is the busiest constraint.** Its pads, at the footprints `fpmap.py` already
  assigns:

  | Tail | Footprint | Row length |
  |---|---|---|
  | J1, J9 | 1.5 mm², 2 × 6 mm | 12 mm each |
  | J3 | 0.5 mm², 5 × 4.6 mm | 23 mm |
  | J4 | 0.5 mm², 4 × 4.6 mm | 18.4 mm |
  | J5 | 0.5 mm², 3 × 4.6 mm | 13.8 mm |
  | J8 | 0.5 mm², 2 × 4.6 mm | 9.2 mm |
  | J10, J11 | 1 mm², 4 × 5.4 mm | 21.6 mm each |

  That is about 132 mm of pads before any gaps, against a 140 mm edge. If they will not fit in
  one row, use **two staggered rows along that edge**. The cables must still exit through the
  one edge. The box takes about 8 glands on that wall. That is the owner's problem, but if the
  pad grouping makes it worse (for example, cables that could share a gland but are split
  apart), report it.

### 5.2 Electrical layout rules (from the schematic and spec)

- **Feed B (pods) is the high-current path.** J9 → Q13 → `VBAT_B` → U14 → `POD_x_P` → J10/J11
  pin 1, returning on `GND_B` (J10/J11 pin 2 → J9 pin 2). **Size the copper for 6.4 A
  continuous** on `VBAT_B` and `GND_B`, and **3.2 A continuous** on each `POD_x_P`. Those are
  the measured pair and per-pod currents at full beam (stage 5, 100% duty, 12 V). At lower duty
  the draw is 100 Hz pulses at about that same peak, so 6.4 A is both the peak and the worst-case
  RMS. Size C68 for that ripple. The inrush is still being measured. It sets no copper width
  (U14 trips at 77 A or more) and only confirms C68. Keep it short, wide and away from the logic area. Size
  copper by IPC-2152 for ≤ 20 K rise and use several layers if needed. C68 and C67 go close to
  U14's VS. Q13 dissipates about 0.66 W and U14 has its exposed pad on VS: give both copper for
  heat.
- **The grounds stay separate:**
  - `GND_IN` (connector side of L2) and `GND` (board side) join only through L2's return
    winding. No copper bridges them, including ground planes and capacitors (see the
    power_input sheet note).
  - `GND_B` meets `GND_IN` only at **NT1**, the star point, which is 2.0 mm wide.
  - Pod return current must not flow through the logic `GND` pour.
  - The plane strategy across 8 layers is the builder's, but it must keep these as separate
    copper regions, and the existing `check_grounds.py` and `check_zone_islands.py` style of
    check must prove it.
- **Feed A** (J1 → L2 → U10/Q10/Q11 → R100 → `VBAT`) carries ≈ 0.9 A now. R100 (33 mΩ) needs a
  Kelvin connection to U10's SNS pin.
- **U10 (LTC4380) `ON` pin:** less than 1 µA leakage. No close ground copper or guard beside
  that pad (README layout note).
- **CAN** (`CANH`/`CANL`, J8 → L6 → U6): routed as a pair, kept twisted to the pads (J8 note).
- **The `SNS_x` sense lines** are high-impedance analog going to ADC1. Keep them away from the
  pod and switching nodes.
- **Buck (U1/U2, L1/L4/L5):** a tight power loop, per its datasheet layout guidance.
- **No copper on any layer** in the antenna keep-out.

### 5.3 How the board file is produced (project rule)

Every artefact in `hardware/` is **generated** by `hardware/scripts/` and never hand-edited
(`hardware/scripts/README.md`, `hardware/docs/routing-tool.md`). Phase B keeps this rule:

- **Placement, outline, holes, zones, keep-outs, net classes and design rules** come from the
  layout scripts. Rework `gen_pcb.py`, `layout_pcb.py` and the related scripts for the plan4
  references, or replace them. Their plan3 references (U7, U8, U9, J6, J7 and so on) go.
- **Routing:** hand-specified routes for the power and critical paths. The plain signal nets
  may be autorouted. Freerouting is installed in the owner's KiCad, and `routing-tool.md` gives
  an external router path. An autorouter's result is captured as **data** the scripts re-apply,
  so a regeneration reproduces the board. Which router to use is the builder's choice.
- **Verification:** `kicad-cli pcb drc` with 0 errors and 0 unconnected items. Also netlist
  parity between the schematic and the board, plus the repo's own geometry and ground checks,
  updated for plan4.

## 6. Decided, with whose call it was

| Decision | Whose |
|---|---|
| 100 × 140 mm target outline | Owner |
| ≥ 8 layers | Owner |
| JLCPCB or PCBWay assembly, 5 prototypes | Owner |
| Board first, box chosen afterwards. Plastic box, about 50 mm deep | Owner |
| All cables leave from one edge | Owner |
| Lid-off access for J2, BOOT and RESET is acceptable | Owner |
| Out of stock, or needing hand soldering, is the failure condition | Owner |
| Antenna on the edge opposite the cables | Mine |
| Single-sided SMD assembly | Mine |
| Scripted layout, autorouting allowed for plain signals, routes kept as data | Mine (existing project rule) |
| No heat-spreader plate. Copper alone is enough at the reduced dissipation | Mine. **The builder must confirm it with a dissipation tally** (Q13 0.66 W, U14, quads, buck, R100) at the design ambient below |
| **Design ambient 85 °C inside the box** (under the fairing, next to the charger) | Mine. The owner may lower it if the bike is measured cooler |
| JLCPCB, with LCSC part numbers and JLCPCB's 8-layer rules. PCBWay is a fallback only | Mine, within the owner's "JLCPCB or PCBWay" |
| The owner places the order. The builder delivers the files and a re-runnable stock check | Mine (the obvious split) |
| If 100 × 140 mm will not fit: stop and ask before growing | Owner |

## 7. Left to the builder

- The layer stack and plane assignment, within the separation rules in §5.2.
- The exact placement, and which edge is the cable edge (a long edge is likely).
- Router choice and net ordering.
- Via sizes and trace widths within the fab's 8-layer capability and IPC-2152.
- Whether J2 is assembled or DNP (goal 4).

## 8. Still open, and does not block layout

- The yellow series resistor values (R82–R85) and the blue pad (J10.4, J11.4) wait on bench
  measurements. Values only change, so the footprints stay. Keep the blue pad.
- The aux circuit ratings and the Zumo's circuit, to be confirmed on the bike. They do not
  affect the board.
