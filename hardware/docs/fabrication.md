# Fabrication and Assembly Notes (plan4, JLCPCB)

**Status: ready to quote.** `scripts/gen_fab.py` writes the package from `mccan.kicad_pcb` into
`hardware/output/jlcpcb/`, and `gen_fab.py --check` passes. KiCad DRC reports **0 violations,
0 unconnected, 0 parity issues**. It was run at **all severities**, with zones refilled and
schematic parity on (`output/jlcpcb/drc.rpt`).

**The owner places the order.** Nothing in this repo uploads anything. Do the three checks in §8
before paying.

This document replaces the plan3 version (PCBWay, 200 × 140 mm), which is in git history. Its
board is in `hardware/archive/`.

**Authority:** goal 9 of `docs/superpowers/specs/2026-11-13-board-layout-phase-b-design.md`.
Numbers are taken from `scripts/layout_pcb.py` (`RULES`, `JLC_FLOOR`) and `scripts/gen_pcb.py`, read
on 2026-11-14.

---

## 1. Order form

| Field | Value |
|---|---|
| Base material | FR-4, TG155 or better (motorcycle; the spec's thermal tally uses an 85 °C ambient) |
| Layers | **8** |
| Dimensions | **140 × 100 mm**, 3 mm corner radius (Edge.Cuts) |
| Quantity | 5 |
| Thickness | **1.6 mm** |
| Outer copper | **1 oz** |
| Inner copper | **1 oz.** Not JLCPCB's 0.5 oz default: the feed-B pours on In3/In5 carry 6.4 A |
| Impedance control | **No.** CAN at 500 kbit/s does not need it, and no trace carries RF |
| Surface finish | **ENIG.** U10 has a 0.15 mm pad gap (§4), and HASL's uneven deposit is a poor fit for it |
| Via covering | **Epoxy filled & capped** (via-in-pad, §3) |
| Min via hole / diameter | 0.2 mm / 0.5 mm |
| Solder mask | green, both sides |
| Silkscreen | white; the top carries all the print |
| Castellations / edge plating / gold fingers | none |

**Assembly:** PCBA, **top side only**, Standard PCBA. Only Standard places the ESP32 module and the
THT parts on an 8-layer board. Upload `bom.csv` and `cpl.csv`. There are two THT parts: J2 (1×6
programming header) and L2 (Würth 7448031002 common-mode choke). Either have JLCPCB hand-solder
them, or untick them and fit them yourself.

---

## 2. Stackup and design rules

The board is eight layers, 1.6 mm thick, with 1 oz copper on every layer. The board file's
dielectric thicknesses are nominal; JLCPCB's standard 8-layer press is fine.

| Layer | Use |
|---|---|
| F.Cu | parts, signals, FEED_B_P / VBAT_B pours at the pod switches |
| In1.Cu | **GND** plane, with GND_IN and GND_B islands |
| In2.Cu | signals (CAN pair, DIAG bus) |
| In3.Cu | power: VBAT and VBAT_B pours |
| In4.Cu | **GND** plane (islands as In1) |
| In5.Cu | signals, FEED_B_P pour |
| In6.Cu | **GND** plane (islands as In1) |
| B.Cu | signals, GND_B and FEED_B_P pours; no parts |

GND, GND_IN and GND_B are separate nets. They meet only at L2/R3 (GND to GND_IN) and at NT1, the
star tie (GND_B to GND_IN). `scripts/check_grounds.py` enforces this.

The board's rules all sit at or above JLCPCB's 8-layer capability. `check_frame.py` asserts this
against `JLC_FLOOR`.

| Rule | Board | JLCPCB floor |
|---|---|---|
| Track / clearance | 0.15 / 0.15 mm (Default netclass 0.20; FEED / FEED_B 0.30) | 0.09 / 0.09 |
| Vias (count) | 0.6/0.3 (610), 0.8/0.4 (53), 0.55/0.25 thermal (83), 0.5/0.2 (3) | 0.25/0.15 |
| Annular ring | ≥ 0.15 mm | 0.15 |
| Hole to hole | ≥ 0.45 mm | 0.45 |
| Hole to copper | ≥ 0.25 mm | 0.2 |
| Copper to edge | ≥ 0.5 mm | 0.2 |
| Silk text | ≥ 1.0 mm high, 0.15 mm stroke | 1.0 / 0.15 |

Plated drills run from 0.20 to 2.15 mm. Non-plated drills are 2.6, 3.2 and 3.5 mm; the 3.2 mm
holes are the M3 mounting holes. Drill files are Excellon in mm, with PTH and NPTH in separate
files.

---

## 3. Via in pad: 83 vias in eight paddles

`gen_pcb.thermal_vias()` fills these exposed pads with 0.55/0.25 mm vias on a 0.8 mm pitch:

| Pad | Array | Net |
|---|---|---|
| Q13.5, Q14.5 (SQJ461EP drain) | 4 × 4 each | FEED_B_P |
| U1.9, U2.9 (LM5164 EP) | 3 × 4 each | GND |
| U11.29, U12.29, U13.29 (TPS4HC120A EP) | 1 × 5 each | GND |
| U14.15 (BTS7008-2EPA EP) | 3 × 4 | VBAT_B |

An open barrel in a paddle wicks solder out of the joint. Order **epoxy filled and copper capped**
(IPC-4761 type VII). That option fills every via on the board, and the rest need nothing more.

---

## 4. Land-pattern exceptions

On these parts, the vendor land pattern puts pads of different nets closer together than the
board clearance allows. `mccan.kicad_dru` excepts each part down to 0.12 mm. The file is generated
by `gen_netclasses.py` from a scan of the board.

| Ref | Part | Pad-to-pad gap |
|---|---|---|
| U1, U2 | LM5164DDA (SOIC-8 EP) | 0.200 mm |
| U10 | LTC4380 (MSOP-10, 0.5 mm pitch) | **0.150 mm** |
| U11, U12, U13 | TPS4HC120A (HTSSOP-28 EP) | 0.200 mm |
| U14 | BTS7008-2EPA (TSDSO-14 EP) | 0.200 mm |

Every gap is above JLCPCB's 0.09 mm minimum space. Pad-to-mask clearance is 0, so each mask dam is
as wide as its pad gap. U10's 0.15 mm dam is the thinnest on the board. If JLCPCB's DFM says it
cannot hold that dam, let them gang U10's mask opening; the stencil defines the joints.

The three GND planes also neck to 0.12 mm between via antipads, at four places per plane. The
scoped DRU rule "GND plane neck" allows this. The surrounding plane carries the current, not the
neck.

---

## 5. The package (`hardware/output/jlcpcb/`)

| File | Contents |
|---|---|
| `gerbers.zip` | 8 copper, 2 mask, 2 paste and 2 silk layers, Edge.Cuts, PTH and NPTH Excellon, job file. **Upload this.** |
| `bom.csv` | `Comment,Designator,Footprint,LCSC`: 64 lines covering 153 placed parts |
| `cpl.csv` | `Designator,Mid X,Mid Y,Layer,Rotation`: KiCad's placement plus `ROT_FIX`; J2 and L2 at their pad centre (KiCad's origin for them is pin 1) |
| `assembly.pdf` | F.Fab (every designator and value) plus the outline, for hand assembly and inspection |
| `rotation-review.txt` | every part whose orientation matters, with its rotation and where the offset came from (§8) |
| `stock.txt` | `check_stock.py --boards 5` against JLCPCB's own parts stock, at generation time |
| `drc.rpt` | the DRC run the package was cut from |
| `render-top.png`, `render-bottom.png` | 3D views from `kicad-cli pcb render` |

Some parts are deliberately left out of the BOM and CPL because they are copper only:

- the 30 test pads, TP1–TP30;
- the solder-wire tails J1, J3–J5 and J8–J11;
- NT1, the net tie;
- the four mounting holes.

The DNP parts (R2, R3, R26) are also excluded. Each test pad's net name is printed beside it on
F.Silkscreen.

To regenerate after any board change, run:

```
python scripts/gen_fab.py && python scripts/gen_fab.py --check && python scripts/check_stock.py
```

---

## 6. Stock

As of 2026-11-14 (`stock.txt`), JLCPCB stocks every line for 5 boards with attrition, except
**U10, LTC4380HMS-2 (C688451)**. That part is marked GLOBAL: JLCPCB holds 3 and the order needs 7.
The owner approved global sourcing for it; the part is still machine-placed, but lead time grows.
**L2, Würth 7448031002 (C1519839), is the next tightest: 11 in stock against 10 needed.** One
more sale and it goes SHORT, and `check_stock.py` exits 1. If it does, either wait for stock or
order L2 through global sourcing as for U10. Stock moves, so re-run `check_stock.py` on the day
of the order.

---

## 7. Mechanical

- The outline is 140 × 100 mm with 3 mm corners. The four M3 mounting holes (3.2 mm, non-plated)
  are 5 mm in from each corner.
- **The tallest part is L2, the Würth 7448031002 common-mode choke: 24.0 mm max** above the board
  (datasheet; THT, on a 3 mm standoff). C3 and C68, the 10 × 10.5 mm electrolytics, come next at
  about 10.5 mm. Size the enclosure to L2.
- U5's antenna overhangs the top edge at the centre. Its keep-out (no copper on any layer, no
  parts) is in the Gerbers. Keep metal 15 mm clear of it in the enclosure.
- The cable edge is the bottom, where the wire tails J1–J11 sit in one row. The bottom face carries
  no parts.

---

## 8. Three checks before paying

1. **Rotations: check every row.** `rotation-review.txt` lists 39 parts whose orientation
   matters. **None of their offsets has been checked against JLCPCB.**
   - 13 are `recalled`: the electrolytics, SOT-23, SOIC-8 and MSOP-10 offsets, as remembered from
     the community rotation tables, not re-fetched. Likely right, not known right. A wrong one
     turns U10 or an electrolytic 180° on every board.
   - 26 are `unverified`: their packages are in no table (every diode; Q10/Q11, TOLL; Q13/Q14,
     PowerPAK SO-8L; U5; U11–U14), plus SW1/SW2, L2, L6 and J2.
   - SW1/SW2, L2 and L6 have no polarity mark, but turned 90° they short or cross-connect: the
     switches read as always pressed, and the chokes cross CANH/CANL or the two windings. Check
     them against their pads.
   - J2 and L2 are placed at their pad centre, not KiCad's pin-1 origin. Check they sit on their
     holes.

   In JLCPCB's placement preview, compare each part's pin-1, cathode or + mark with the board
   silk, and correct any that are wrong there. Then write the correct offset into `ROT_FIX` in
   `scripts/gen_fab.py` and label it `"confirmed"` (widening `check()`'s allowed set), so the
   next order comes out right.
2. **Stock.** Re-run `check_stock.py`.
3. **DFM.** Read JLCPCB's DFM report for the U10 mask dam (§4) and the via-in-pad option (§3).

---

## 9. Order notes (paste)

```
8-layer, 1.6 mm, 1 oz outer and 1 oz inner, ENIG, TG155+.
Via-in-pad: 83 vias in 8 exposed pads (Q13, Q14, U1, U2, U11-U14) - epoxy filled and capped.
No impedance control.
U10 (MSOP-10) pad gap is 0.15 mm with mask clearance 0; gang its mask opening if the dam
cannot be held.
Assembly top side only. THT: J2, L2.
```
