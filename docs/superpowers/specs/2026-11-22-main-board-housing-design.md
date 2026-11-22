# Main board housing: design

**Date:** 2026-11-22. **Status:** approved by the owner, 2026-11-22. The overall size (about
200 × 148 × 45 mm including the ears, with glands sticking out about 25 mm) is **not yet confirmed
against the space under the fairing**. Keep the ears and flange as parameters so they can shrink
after a trial fit.
**Inputs (read, not changed):** `hardware/mccan.kicad_pcb`, `hardware/docs/enclosure.md`,
`harness.md`, `fabrication.md`, `bring-up.md`, the programmer board spec (2026-11-14).

## 1. Intent

A housing for the plan4 main board (140 × 100 mm), mounted under the Experia's fairing next to the
charge board. The owner's hard requirement: **it is screwed shut.** The first parts are 3D printed in
ASA. The geometry is to be **injection moulded** later, so it is designed to be mouldable now rather
than redesigned then.

It replaces the open box-selection items in `enclosure.md` §4 (an off-the-shelf box) with a custom
housing. The rest of `enclosure.md` still holds: the antenna clearance (§2), the vent (§5), the
coating masks (§7) and the thermal basis (§9, an 85 °C internal design ambient).

## 2. Goals, non-goals, anti-goals

**Goals**
- Holds the board on its four M3 holes and survives vibration on the bike.
- **IP67 by design**: a gasketed lid joint, seven sealed cable glands and a membrane vent.
- Screwed shut: lid screws go into threaded metal (heat-set inserts), never self-tapped into plastic.
- WiFi works: no metal in the antenna zone (§4.2).
- With the lid off, J2, SW1, SW2 and all 30 test pads are reachable on the bike or the bench.
- A parametric model whose dimensions trace back to the board file, plus exports to print now and
  to quote for moulding later.

**Non-goals**
- No J2 access port. The lid comes off for the first flash and for recovery; OTA does the rest.
- No heat sinking. Copper alone carries the board's ~1.4–1.6 W (`enclosure.md` §9).
- No changes to the board, the schematic or `hardware/scripts/`.
- No bike bracket design. The housing carries the ears; the bracket follows a trial fit.

**Anti-goals (failure even if it "works")**
- A screw, insert, sleeve or bracket inside the antenna zone: WiFi and OTA degrade on the road.
- A seal that relies on the print being perfect: a print that only reaches IP65 is acceptable for
  testing, but the geometry itself must be capable of IP67 once moulded.
- A layout that needs undercuts or slides to mould.

## 3. Decisions (the owner's, 2026-11-22)

| Topic | Decision |
|---|---|
| How it is made | **ASA 3D print** for the prototypes; **injection moulded** in production |
| Sealing | **IP67 design, gasketed** lid joint and a breather vent |
| Mounting | **Four ears with rubber grommets** (metal sleeves, M5 bolts) |
| Cable entry | **Seven glands in two staggered rows** on the cable wall, one per sheathed cable (`harness.md` §2) |
| J2 | **Open the lid** to program; no access port |
| CAD | **Autodesk Fusion** (through the Fusion MCP) |

## 4. Constraints taken from the board

All figures are read from `mccan.kicad_pcb` by a script (§6.1); none are retyped by hand. The board
file is in KiCad coordinates, with the board's top-left corner at (20, 20). The housing uses
**board coordinates**: the top-left corner is (0, 0), x runs right and y runs toward the cable edge.

### 4.1 Board
- Outline: 140 × 100 × 1.6 mm, 1 mm corner radius. The top side carries every part; the bottom has
  none.
- Holes H1–H4: Ø3.2 mm at (5, 5), (135, 5), (5, 95), (135, 95). Keep a Ø6 mm circle clear for the
  standoff face.
- Underside: THT leads and soldered wire tails protrude, so the standoffs must be **at least 5 mm**.
- The tallest part is **L2**, 24.0 mm above the board (a Würth 7448031002, body 23 × 17 mm at x
  7.25–30.25, y 32.15–49.15). Next come C3 and C68 (10.5 mm), then the IHLP inductor L1.
- Cable tails, along the bottom (cable) edge, pin 1 on the left: J1, J3, J4, J5, J8, J10, J9 and J11.
  The pads lie roughly at y 79–86, and their strain-relief holes sit toward the edge.
- J2 is a 1×6 vertical header at (121.87, 11.37), pins running in +y. It mates from above with the
  programmer's jumper cable. SW1 and SW2 are beside it, and the test pads cluster in the board's
  middle.

### 4.2 Antenna zone (no metal)
- U5 sits on the top edge. The copper keep-out on the board is x 70.75–119.25, y 0–6.44.
- **No metal within 15 mm** of that span, in plane and above and below it. The zone is
  x 55.75–134.25 and y from −15 to +21.44, through the full height of the housing. ASA, the
  gasket and nylon are all fine there.
- Steel screws, brass inserts, ear sleeves, metal glands and the bracket all stay outside it.
- **H2 at (135, 5) is not clear.** Its centre is 15.75 mm from the end of the span, so a brass insert
  (r 2.3) or a screw head (r 2.75) reaches about 13 mm. Ruling made during the build: H2 is fixed
  with a **nylon M3 screw into a captive nylon nut** in its boss. That is a nut, not self-tapping,
  and has no metal. H1, H3 and H4 use brass inserts.

## 5. Approaches considered

| Approach | Trade-off | Outcome |
|---|---|---|
| Off-the-shelf IP67 PC box, drilled | Proven seal and lid inserts, but too big for the board and not tailored for moulding | Not chosen |
| **Custom ASA print → moulding** | Fits the board closely, mounts and glands where wanted; prints seal to roughly IP65 until moulded | **Chosen** |
| Machined or off-the-shelf aluminium | Blocks WiFi (antenna zone) | Ruled out |
| CadQuery script (with STEP, STL and PDF drawing) | Regenerates from the board file in git; adds a 200 MB package | Not chosen |
| **Fusion through MCP** | The owner can edit by hand; moulders accept the files | **Chosen** |
| OpenSCAD | No STEP export | Ruled out |

## 6. Design

### 6.1 Traceability: board → model
- `hardware/enclosure/extract_board.py` (plain Python, run outside Fusion) reads `mccan.kicad_pcb`
  and writes `hardware/enclosure/board.json`. That file holds the outline, the holes, every
  footprint's courtyard rectangle and height, the cable-tail pads, J2/SW1/SW2 and the antenna zone.
  Heights come from the KiCad 3D models where they resolve; otherwise they come from an explicit
  table in the script, citing the datasheet (L2 24.0 mm from `enclosure.md`).
- `hardware/enclosure/build_housing.py` is a **Fusion API script**, run through the MCP. It reads
  `board.json` and a parameter table at its top, then builds the housing in a new Fusion document as
  **user parameters** plus features, so the owner can edit the parameters by hand in Fusion.
- If the board ever changes, re-run both scripts. The model regenerates; nothing is retyped.

### 6.2 Architecture
- A **base** (a deep tray) holds the board, glands, vent and ears. A **lid** (a shallow cap) carries
  the gasket face. The split line is at the base's top rim, and every gland sits wholly in the base.
- Material: ASA. The **nominal wall is 2.5 mm** everywhere (uniform for moulding; strong when
  printed). Internal corners have ≥ 1 mm radii.
- **Draft: 1°** on every vertical face, opening away from the parting line. Bosses and ribs are
  drafted too, and there are no undercuts. The gland seats are flat spot faces, perpendicular to the
  gland axis.

### 6.3 Inside space (my proposals, all parameters)
| Parameter | Value | Why |
|---|---|---|
| Board to side and top walls | 3 mm | Lifting the board out; tolerance |
| Board edge to cable wall | 22 mm | Gland locknuts inside, and the bend from gland to pad (`harness.md` service loop) |
| Standoff height | 8 mm | ≥ 5 mm needed; room for the leads and wire loops underneath |
| L2 top to lid underside | ≥ 4 mm | 3 mm minimum plus print tolerance |
| Interior footprint | ≈ 146 × 125 mm | Follows from the above |
| Interior height | ≈ 38 mm (floor to lid underside) | 8 + 1.6 + 24 + 4 |

### 6.4 Board fixing
- Four standoff bosses rise from the floor at H1–H4. The **top face is Ø6 mm** (the board's clear
  circle), and the boss widens below. Each holds an **M3 brass heat-set insert**, and an M3 × 6
  stainless pan-head screw goes in with a washer under its head. The H2 boss is checked against the
  antenna zone (§4.2).

### 6.5 Lid joint and seal
- The base rim carries an outward **flange**. A **face-seal groove** runs inside the screw line, so
  the screw holes are **outside** the seal and are not leak paths.
- **Gasket:** a **Ø2.0 mm silicone O-ring cord**, joined into a loop. The groove is about 1.5 mm deep
  × 2.7 mm wide (about 25 % compression, at most about 85 % fill; final values from the cord
  datasheet). The lid face is flat over the groove and a small skirt locates it. For the moulded
  part, the same groove takes a moulded silicone gasket or a formed-in-place foam bead.
- **Screws:** M3 stainless into **M3 brass heat-set inserts** in the base flange, at a pitch of
  **≤ 60 mm** wherever the antenna zone allows. **Along the antenna wall, no screw falls inside
  x 55.75–134.25.** That edge spans about 90 mm, from the last screw left of the zone to the
  top-right corner screw, so it is stiffened with a lid rim and ribs instead. This is the one
  seal-risk spot; the dunk test (§7) checks it.
- **Moulding later:** the inserts go in after moulding (heat or ultrasonic), in the same holes.

### 6.6 Cable glands
- **Seven nylon IP68 glands**, threaded into through-holes and held by locknuts inside, are placed
  over their tails from left to right: feed A, front, rear, CAN, pod L, feed B, pod R.
- **Sizes (provisional):** M16 × 1.5 for feed B, pod L and pod R (cables around 7–9 mm OD); M12 × 1.5
  for feed A, front, rear and CAN. **[TO CONFIRM]** against the cables bought. Sizes and positions
  are parameters.
- **Two staggered rows**, alternating, so neighbouring hexes and locknuts clear each other, with
  spanner room outside and nut room inside. The upper row also clears the flange above it. If the
  rows do not fit, **the interior height grows**. The glands never move to another wall without the
  owner's say.
- Holes are flat-seated in the drafted wall (§6.2).

### 6.7 Vent
- A **M12 membrane vent** (screw-in, plastic, IP67/68, Gore-type) on a **side wall near the cable
  end, low down**, so it points sideways when the box hangs with its glands down. It must never point
  up. Its part number is **[TO CONFIRM]**; the hole is a parameter.

### 6.8 Mounting ears
- **Four ears**, two on each short side wall (the left and right walls), flush with the base's back
  face. Each has a hole for a **rubber grommet** with a metal sleeve, and takes an M5 bolt to a
  bracket. The ear thickness matches the grommet's panel groove. Hole and thickness are
  **[TO CONFIRM]** against the grommet bought.
- The housing then mounts with its **floor against the bracket**. Mounted with the cable wall down,
  the glands and vent face down or sideways, as `enclosure.md` §6 requires.
- The ears near the antenna end sit outside the antenna zone. **The bracket must also stay outside
  the zone**; the README says so.

### 6.9 Printing notes (prototype)
- ASA, 0.2 mm layers, at least 5 perimeters (the whole 2.5 mm wall solid), at least 6 top and bottom
  layers. Base printed opening up and lid printed face down, so the gasket faces are smooth.
- Expect about IP65 as printed. Vapour smoothing or a sealing coat closes the porosity if a printed
  part has to reach IP67.

## 7. Verification ("done")
1. **Interference:** the board STEP, exported by `kicad-cli` (read-only) and placed on the
   standoffs, shows zero interference with the base and lid in Fusion. Parts whose KiCad 3D model
   is missing are stood in by envelope blocks (courtyard × height from `board.json`), with L2 as the
   Würth STEP or a 23 × 17 × 24 mm block.
2. **Clearance rules** (scripted, from `board.json`):
   - lid to the tallest part ≥ 3 mm;
   - standoff top faces within Ø6 mm, and the boss clear of every courtyard by ≥ 0.5 mm;
   - no screw, insert, sleeve or other metal body inside the antenna zone;
   - gland locknuts clear of each other, of the floor and flange, and of the board edge;
   - J2, SW1/SW2 and all TP pads unobstructed from above with the lid off;
   - the board lifts out vertically.
3. **Exports**, in `hardware/enclosure/`:
   - `.f3d` (the Fusion archive);
   - STEP for the base, the lid and the assembly;
   - STL for the base and the lid;
   - a dimensioned **SVG drawing** (it prints to PDF). The Fusion API cannot create drawing
     sheets, so the drawing is generated from `board.json` and the parameters by a small stdlib
     script; no new packages. A Fusion drawing can be made by hand for a moulder.
4. **`hardware/enclosure/README.md`**: the decisions, the bill of materials (screws, inserts,
   gasket cord, glands, vent, grommets; anything not yet looked up marked **[TO CONFIRM]**,
   following `enclosure.md`'s no-invented-part-numbers rule), the print settings, and the
   check-on-the-bike items: a dunk test and a WiFi RSSI check with the lid on.

## 8. Left to the builder
- Exact groove and flange dimensions, rib layout, screw count (within ≤ 60 mm pitch and the antenna
  rule), and the gland row heights: all within the rules above, and all as Fusion parameters.
- Model fidelity: plain cylinders for the glands and vent in the check model (thread OD, hex AF and
  locknut), not vendor CAD.

## 8a. Changed during the build (2026-11-22, after review)
- §6.5: the antenna edge is no longer left unscrewed. The lid screw that falls in the antenna zone
  (x 97) is a **nylon M3 × 12 into a captive nylon nut**, so the pitch is ≤ 54 mm all round.
- §6.6: glands get **5 mm of spanner room** (hex to hex, floor and drafted wall). That raises the
  interior from 38.6 to 44.6 mm.
- §6.7: the vent sits at y 70, z 20.1. Its inside nut must clear the board edge and parts, and it
  sits between the ear gussets.
- §6.8: each ear has two triangular gussets, and its root is 2 mm into the wall.
- §4.1: L2 keeps its datasheet height of 24.0 mm as a floor, even if its 3D model resolves, because
  the STEP reads 11.6 mm.

## 9. Reported to the Coordinator (no action taken here)
- 16 parts' 3D models do not resolve in `kicad-cli` on this PC: L2 (its model path is
  `7448031002.stp`, but the file is `hardware/3dmodels/Wurth_WE-CMBNC_7448031002.stp`), the
  J wire-tail footprints, Q13/Q14, SW1/SW2, U1/U2 and U14. This only affects 3D exports, not the
  fabrication files, and is a cosmetic fix for the Main Board session.
- No board change is needed for the housing.
