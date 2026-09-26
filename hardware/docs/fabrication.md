# Fabrication and Assembly Notes

**Status: DRAFT — the routing is frozen but not finished.** The external router's result is folded
into the board (`scripts/routes_signal.json`), and every figure below is measured against that
board. KiCad DRC currently reports **20 violations and 25 unconnected items**, none of them a
clearance or short: the violations are 12 dangling vias and 1 dangling track left on nets the
router could not close, plus 7 pour necks. About twenty single hops remain to be hand-routed.
Nothing in this document depends on those hops except the via counts in §5, which will grow by a
few. Re-measure §5 before an order goes out.

**Authority:** `../../docs/superpowers/specs/2026-09-11-esp32-mccan-pcb-hardware-design.md` §9.3,
§9.4, §10 (Task 9). The board itself carries a condensed version of this document on `Cmts.User`
(`scripts/layout_pcb.py`, `NOTES`) — that text and this file must agree; the board is what the fab
actually reads.

> **Nothing here is a default.** A board house quotes its standard process and builds what the
> Gerbers say. Four things on this board are *not* standard process and will be built wrong unless
> they are asked for in words: the via-in-pad plugging (§7), the U10 mask opening (§8), the stencil
> (§10), and the confirmation that hole-to-hole 0.3 mm applies at these via sizes (§13). They are
> collected in §14 as the text to paste into the order.

---

## 1. The one-screen summary

| Field | Value |
|---|---|
| Board size | 140.0 × 100.0 mm rectangle, 3.0 mm corner radius |
| Layers | **6** |
| Material | FR4, Tg ≥ 150 °C |
| Finished thickness | **1.6 mm** |
| Outer copper | **1 oz (35 µm) finished** |
| Inner copper | **1 oz (35 µm) — all four inner layers** |
| Min track / clearance | **0.20 mm / 0.20 mm** (both outer and inner) |
| Min drill | **0.20 mm** (plated) |
| Max aspect ratio | **8:1** (1.6 mm ÷ 0.20 mm) |
| Min annular ring | **0.15 mm** |
| Min hole-to-hole | 0.30 mm — **see §13, this needs confirming** |
| Copper to board edge | 0.50 mm |
| Surface finish | **ENIG** |
| Solder mask | both sides; **pad-to-mask clearance 0** |
| Silkscreen | both sides (top only is populated) |
| Via treatment | tented both sides, **except the five paddles in §7, which must be plugged and capped** |
| Controlled impedance | **NO — do not quote it** (§11) |
| Castellations / edge plating / V-score | none |
| Assembly | **single sided, top only** — `B.Cu` carries copper but no parts |

---

## 2. Stackup

Six layers, built as a foil lamination: two cores bonded by three prepregs, with `F.Cu` and `B.Cu`
as outer foil. It is symmetric about the middle prepreg, which is what keeps the panel flat.

```
    F.Mask     0.010
    F.Cu       0.035    signal
      prepreg  0.100
    In1.Cu     0.035    GND  — solid, unbroken
      core     0.200
    In2.Cu     0.035    signal
      prepreg  0.761
    In3.Cu     0.035    VBAT — the 7 A feed plane
      core     0.200
    In4.Cu     0.035    signal
      prepreg  0.100
    B.Cu       0.035    signal + GND pour + a +24V pour under D4
    B.Mask     0.010
                -----
                1.571 mm copper + dielectric, pressed to 1.6 mm finished
```

FR4 constants in the KiCad stackup are εr 4.5, loss tangent 0.02. **These are nominal.** The
sub-thicknesses are nominal too — the fab is free to adjust them to hit 1.6 mm, because nothing on
this board depends on a specific dielectric height (§11). The one thing that is **not** adjustable
is the *order* of the layers and the 0.1 mm prepreg either side: `F.Cu` and `B.Cu` must each sit
one thin prepreg from their reference plane.

### Why 1 oz on all six

The earlier four-layer revision specified 1 oz outer / 2 oz inner, and the 2 oz was bought for the
`VBAT` plane. Going to six layers made the 2 oz impossible and then showed it had never been
needed:

- **Impossible**, because `In2.Cu` and `In4.Cu` now carry *tracks*. PCBWay etch inner layers to
  4/4 mil at 1 oz but 6/8 mil at 2 oz, and 8 mil is 0.203 mm — **above** the 0.20 mm clearance
  every net class on this board declares. Inner copper weight is a single selector for all inner
  layers short of a custom stackup, so the signal layers decide it for the plane as well.
- **Not needed**, because `scripts/check_plane_width.py` measures what the `In3.Cu` pour actually
  delivers rather than trusting the arithmetic: it rasterises the zone, punches every via and
  through-hole antipad out of it, cuts it in both directions and grades the worst cut. The worst
  cut carries **71 mm** of effective width against the **11.44 mm** IPC-2221 asks for 7.0 A at a
  10 K rise, internal, 1 oz. That is 6.1×. Having a whole layer is what made the feed work, not the
  copper weight.

1 oz outer is also what holds U10's 0.15 mm land pattern (§6): the finer the etch, the less
sideways copper growth there is to close a gap that small.

---

## 3. Board outline and mechanical

- Rectangle **140.0 × 100.0 mm**, corners radiused **3.0 mm** (four arcs, `Edge.Cuts`).
- Four **M3 mounting holes, 3.2 mm NPTH**, 5.0 mm in from each corner. In board coordinates:
  (25, 25), (155, 25), (25, 115), (155, 115) — the outline runs x 20…160, y 20…120.
- Copper is held **0.50 mm** off the edge everywhere.
- No V-score, no tab-route, no panelisation requested. If the fab panelises for their own handling,
  the antenna keep-out below still applies to the finished piece.

### Antenna keep-out — this one is absolute

`U5` is an ESP32-WROOM-32 module mounted so its antenna overhangs the board edge. **No copper, no
plating, no parts, no silkscreen and no mask on ANY layer** inside:

> **x 153.56 … 174.75, y 48.00 … 96.00** (board coordinates)

which is 18.0 × 6.19 mm of module antenna plus margin, measured from the module end face
(datasheet v1.8 Fig. 12). The region extends past the board edge; that is intentional. The
heat-spreader plate is notched to clear it — see `enclosure.md`.

---

## 4. Design rules the board is actually built to

These are the values in `mccan.kicad_pro` and they are what DRC enforces. They are *floors*; most
of the board is looser.

| Rule | Value |
|---|---|
| Minimum clearance | 0.20 mm |
| Minimum track width | 0.20 mm |
| Minimum connection width | 0.20 mm |
| Minimum via diameter | 0.50 mm |
| Minimum via annular ring | 0.15 mm |
| Minimum through-hole diameter | 0.20 mm |
| Minimum hole clearance (hole to copper) | 0.25 mm |
| Minimum hole-to-hole | 0.30 mm |
| Copper to board edge | 0.50 mm |
| Solder-mask to copper clearance | 0.00 mm |

Net classes (`scripts/layout_pcb.py`, `NETCLASSES`) — track / clearance / via / drill, all mm:

| Class | Track | Clearance | Via | Drill | Nets |
|---|---|---|---|---|---|
| `FEED` | 3.50 | 0.30 | 0.80 | 0.40 | the 7.0 A input chain |
| `POWER` | 2.00 | 0.30 | 0.80 | 0.40 | `VLOGIC_IN`, `+24V`, `+5V` |
| `CAN` | 0.30 | 0.20 | 0.60 | 0.30 | `CANH`, `CANL` |
| Default | 0.25 | 0.20 | 0.60 | 0.30 | everything else |

**`FEED` at 3.50 mm is a 20 K-rise width (8.01 A at 1 oz), not a 10 K one, and that is deliberate.**
It is a *floor* for the short hops between the input parts, which sit in one tight island by J1.
Anything running further than a few millimetres on `F.Cu` must be **poured to ≥ 4.5 mm**, and the
through-path itself belongs on the `In3.Cu` polygon. A net-class minimum cannot express "and pour
it", which is why the board note says so in words.

---

## 5. Drill schedule

**Plated (PTH + vias):**

| Drill | Pad / via dia. | Count | What |
|---|---|---|---|
| 0.20 | 0.60 | 12 | thermal vias inside U5's module land pattern (part of the footprint) |
| **0.20** | **0.50** | **35** | router under-pad rescue vias in U7/U8's fine-pitch fanout — **at the 0.15 mm annular-ring floor** |
| 0.25 | 0.55 | 65 | **via-in-pad thermal arrays — see §7** |
| 0.30 | 0.60 | 732 | `CAN`, Default-class and routed signal vias |
| 0.40 | 0.80 | 136 | `FEED` / `POWER` vias, ground drops, stitching |
| 1.00 | — | 6 | connector / discrete leads |
| 1.15 | — | 18 | connector / discrete leads |
| 1.30 | — | 4 | connector / discrete leads |
| 2.15 | — | 6 | heavy wire-solder pads |

**Non-plated:**

| Drill | Count | What |
|---|---|---|
| 2.60 | 20 | 0.5 mm² solder-wire relief holes (J-connectors) |
| 3.20 | 4 | M3 mounting holes H1–H4 |
| 3.50 | 6 | 1.5 mm² solder-wire relief holes |

**968 vias in total**, of which 614 came from the router.

The **0.20 mm** plated hole is the binding one, and there are **47** of them. At 1.6 mm finished
that is an **8:1 aspect ratio**, which is the top of most fabs' standard through-hole plating
capability. Twelve come from U5's footprint and cannot be relieved by rerouting; the other 35 are
0.50 / 0.20 mm vias the router shrank to escape U7 and U8's 0.65 mm-pitch land patterns, and they
sit exactly on this board's 0.15 mm minimum annular ring. **If the fab will not hold 8:1 and a
0.15 mm ring as standard process, say so before the order** — the 35 can be re-routed at 0.6 / 0.3
for the cost of some congestion, the 12 cannot.

Via totals will grow by a handful as the last hops are hand-routed.

---

## 6. Land-pattern exceptions — DRC is suppressed here, so the fab must be told

Three footprints have pad-to-pad gaps under this board's 0.20 mm global minimum. A clearance
constraint governs what the *layout* may do; it has no business policing the gap between a part's
own pads, which is fixed by the manufacturer's recommended footprint and is identical on every
board that uses the part. `mccan.kicad_dru` therefore suppresses the check for these three refs —
generated by `scripts/gen_netclasses.py` from a scan of the board, so it cannot drift out of step
with the schematic.

**Suppressing the check is correct, but it is not free: it moves the requirement out of DRC and
into this document.**

| Ref | Part | Needs | What |
|---|---|---|---|
| `U1` | VSON/QFN | **0.200 mm** | exposed thermal pad to neighbouring signal pad |
| `U2` | VSON/QFN | **0.200 mm** | exposed thermal pad to neighbouring signal pad |
| `U10` | LTC4380, MSOP-10 | **0.150 mm** | pad to pad, lead pitch 0.5 mm |
| `U10` | — | **0.175 mm** | **track to pad** — U10 pads 3/5 (`U10_GATE`, `VBAT_PROT`) to a 0.30 mm `SNS` track |

That last row is the tightest feature on the board and is not covered by the `.kicad_dru`
exception at all in spirit — `memberOfFootprint()` names the pad, so KiCad does accept the track as
well, but the *fab* was never told. **The board is no easier to build than its tightest entry:
0.15 mm etch and 0.175 mm track-to-pad registration inside U10's land pattern.**

The next three gaps are 0.183 mm (U10 pad 1 to a `VCC10` track), 0.190 mm (U1 pad 5 to a
`Net-(U1-BST)` track) and 0.200 mm. Nothing else on the board is under 0.20 mm.

The assembler has the matching problem: they need a stencil and reflow profile that will not bridge
an exposed thermal pad to the pin 0.15–0.20 mm away. §10.

---

## 7. Via in pad — the five paddles

Five pads are filled with via arrays to get heat off the part and onto a plane. All of them use
**0.55 mm pad / 0.25 mm drill** on a **0.80 mm** pitch, inset 0.15 mm inside the pad edge:

| Pad | Pad size | Array | Net |
|---|---|---|---|
| `D4.3` | 4.80 × 4.72 | 5 × 5 | `/+24V` |
| `U1.9` | 2.62 × 3.51 | 3 × 4 | `GND` |
| `U2.9` | 2.62 × 3.51 | 3 × 4 | `GND` |
| `U3.17` | 1.68 × 1.68 | 2 × 2 | `GND` |
| `U9.15` | 2.65 × 4.00 | 3 × 4 | `/VBAT` |

**65 vias in total.** The sizing criterion is thermal, not a count copied from an app note: one
0.25 mm-drill via through 1.6 mm with a 25 µm barrel is roughly 60 K/W, so a 3 × 4 array is about
5 K/W — well under the 8–15 K/W the gap pad to the enclosure contributes, which is the point at
which the array stops being the bottleneck.

> ### Order requirement: **PLUGGED AND CAPPED (IPC-4761 type IV or VI)**
>
> The board's global via setting is `tenting front back`, and **tenting is not plugging**. A tent is
> a mask skin over an open barrel, and inside a solderable paddle it does nothing: the barrel is
> inside the pad's own mask opening, so the top is open regardless. An open barrel in a paddle wicks
> paste out of the joint during reflow and voids the thermal path the vias exist for.
>
> These five paddles must be **resin plugged and copper capped**, planarised flat, on both sides.
> This is an explicit, chargeable process step. It will not happen by default.

Everything else on the board is ordinary tented via and needs no special treatment.

---

## 8. Solder mask and silkscreen

- **`pad_to_mask_clearance` is 0** and `solder_mask_to_copper_clearance` is 0 — the mask opening is
  exactly the pad. The consequence is that the **mask dam between adjacent pads equals the pad-to-pad
  gap**, so it is 0.20 mm at U1/U2 and **0.15 mm at U10**.
- `allow_soldermask_bridges_in_footprints` is **no**, so KiCad has not ganged anything automatically.

> ### Order requirement: **NO MASK DAM AT U10**
>
> A 0.15 mm dam does not survive the mask process at any normal fab. What comes back is a
> half-formed sliver, which is worse than no dam at all — it lifts, traps flux and can float into a
> joint. **Run one mask opening across all of U10's leads** and let the paste stencil define the
> joints. Say this explicitly; do not leave the fab to discover it.

- Silkscreen is present on both sides; only the top is populated. Minimum text height 0.8 mm,
  minimum stroke 0.08 mm — both comfortably above standard capability.
- Silk is **not** subtracted from mask (`subtractmaskfromsilk no`). Any silk that lands on a pad
  should be trimmed by the fab in the usual way.
- DNP parts are crossed out on the fab layer (`crossoutdnponfab yes`) and are **not** to be fitted.
  See §15.

---

## 9. Surface finish — ENIG

**ENIG**, and it is specified in the stackup itself (`copper_finish "ENIG"`), not left to the
quote form. The reason is §6: HASL leaves a domed, uneven deposit whose height variation is a
sizeable fraction of a 0.15 mm gap, and the levelling air-knife does not reach reliably between
0.5 mm-pitch MSOP leads. ENIG is flat, which is what a 0.15 mm land pattern and a 0.12 mm stencil
need to co-planarise against.

It also suits the application: this board lives on a motorcycle, and ENIG's corrosion resistance
over a long unsealed service life is worth the cost difference on a board this size.

---

## 10. Assembly

**Single sided — every component is on `F.Cu`.** `B.Cu` carries copper (a `GND` pour, a `/+24V`
pour under D4, and signal routing) but no parts, deliberately: the bottom face is what couples to
the heat-spreader plate.

> ### Order requirement: **STENCIL 0.12 mm, laser cut, trapezoidal walls**
>
> - 0.12 mm foil, laser cut, electropolished, **trapezoidal (tapered) apertures**.
> - **Reduce the large paddle apertures to ≈ 70 % area** — the five paddles in §7 plus any other
>   exposed pad over ~4 mm². A 100 % aperture on a paddle floats the part and tombstones its
>   neighbours.
> - U1, U2 and U10 are at 0.200 / 0.150 mm pad-to-pad **by written exception**
>   (`mccan.kicad_dru`), not by accident. The profile must not bridge a thermal pad to the pin
>   0.15–0.20 mm away.

The heat path: `B.Cu` contacts a gap pad over the two dashed patches marked on `Cmts.User`
(≈ 1360 mm² total). **Do not tent the stitching vias inside those patches any differently from the
rest of the bottom side** — the bottom is bare on purpose.

**`B.Cu` under D4 is `+24V`, not ground.** The gap pad is the only thing between that copper and the
plate, so it must be an insulator rated for the rail — not a conductive or metal-loaded filler.

---

## 11. Impedance — do NOT order controlled impedance

Nothing on this board is a transmission line, and quoting controlled impedance would add cost and a
coupon for no benefit.

- **CAN** is the only net that leaves the box on a long unshielded harness. At 500 kbit/s the
  110 mm from the transceiver to J8 is about 0.7 ns of flight against a ~50 ns edge. Stub lengths do
  not matter and a few millimetres of skew between the two tracks is ~20 ps. The pair is routed on
  `In2.Cu`, 0.2 mm under the solid `In1.Cu` ground plane with no splits anywhere it crosses, so the
  return current runs directly beneath each track for the whole run — it is routed for **immunity**,
  not for impedance. At 0.2 mm from the plane the pair is plane-referenced rather than edge coupled,
  so differential impedance lands near 70 Ω, not 120 Ω. Widening the gap does not change that (the
  plane dominates) and at this bit rate it does not need to: what the bus sees is the 120 Ω
  termination at R26, and the track is far too short to be visible to it.
- **The ESP32 module** carries its own RF; nothing on this board routes RF.
- There is no USB, no Ethernet, and no memory bus.

The dielectric heights in §2 are therefore nominal and the fab may adjust them freely to hit
1.6 mm.

---

## 12. Copper pours

Five zones:

| Layer | Net | What |
|---|---|---|
| `In1.Cu` | `GND` | **solid and unbroken** — the reference plane for `F.Cu` and `In2.Cu` |
| `In3.Cu` | `/VBAT` | the 7 A feed plane (§2) |
| `B.Cu` | `GND` | bottom pour |
| `B.Cu` | `/+24V` | under D4 only — **see the gap-pad warning in §10** |
| `F.Cu` | `/power_input/GND_IN` | the input-side ground island |

`GND_IN` and `GND` are **separate nets** and meet at exactly two places: L2 winding B, and R3. The
plane must not bridge them anywhere else; `scripts/check_grounds.py` verifies this and it is a
real circuit requirement, not a style preference.

---

## 13. The open question to put to the fab before ordering

> **Hole-to-hole minimum at these via sizes.** This board is built to a 0.30 mm hole-to-hole
> minimum, and 0.30 mm is the figure PCBWay quote — but they write it against *"vias ≤ 0.45 mm"*.
> Every via here is 0.50, 0.55, 0.60 or 0.80 mm. It is **not clear** whether the 0.30 mm rule this
> board is built to applies at these diameters or whether a wider one does. Ask before ordering. If
> a wider minimum applies, the stitching and ground-drop fields are where it will bite, and they are
> regenerated by script — it is a fixable problem, but only if it is found before the order.

---

## 14. Text to paste into the order notes

```
6-layer FR4, 1.6 mm finished, Tg >= 150 C.
1 oz (35 um) finished copper on ALL SIX layers -- inner layers must be 1 oz,
  NOT 2 oz: inner clearance is 0.20 mm and 2 oz inner etch cannot hold it.
Min track/clearance 0.20/0.20 mm outer AND inner.
Min plated drill 0.20 mm, 47 holes (aspect ratio 8:1 at 1.6 mm).
Min annular ring 0.15 mm, on 35 vias of 0.50 mm dia / 0.20 mm drill.
Surface finish ENIG. Mask both sides, silkscreen both sides.

1. VIA IN PAD, PLUGGED AND CAPPED (IPC-4761 type IV or VI), planarised, BY
   RULE: every via whose centre falls inside a copper pad, wherever on the
   board it sits. That is 194 vias over 132 pads on the board as generated
   (scripts/check_vias.py recomputes this count on every build and is the
   authority for it going forward; the drill/Excellon files are the
   authority for exactly which holes they are). The default finish is
   TENTED, which is a mask skin over an open barrel and is NOT the same
   thing -- any of these left tented wicks paste down the barrel during
   reflow and starves the joint under that pad.

   The five largest concentrations are dedicated thermal arrays and want
   filling for that reason too, not only this rule: D4 pad 3, U1 pad 9, U2
   pad 9, U3 pad 17, U9 pad 15 (65 vias, 0.55 mm pad / 0.25 mm drill,
   0.80 mm pitch). The other 129 vias sit over 127 more pads spread across
   the board -- wherever a feed via lands on a pad centre by design, or a
   router via changes layer inside a pad it fanned out to -- and are to be
   plugged and capped the same as the five.

2. NO SOLDER MASK DAM AT U10. Its leads leave a 0.15 mm gap and a dam that thin
   does not survive the mask process. Run one opening across the leads and let
   the paste stencil define the joints.

3. TIGHT LAND PATTERNS BY DESIGN, NOT BY ERROR. U1 and U2 are 0.200 mm
   pad-to-pad, U10 is 0.150 mm pad-to-pad and 0.175 mm track-to-pad. These are
   vendor land patterns and are covered by a written DRC exception in the
   project. Do not "correct" them.

4. NO CONTROLLED IMPEDANCE required. Dielectric sub-thicknesses are nominal;
   adjust freely to hit 1.6 mm. Layer ORDER and the 0.1 mm prepreg either side
   of the outer layers must be kept.

5. ANTENNA KEEP-OUT: no copper, plating, mask, silkscreen or parts on ANY layer
   in the marked region at the right-hand edge (see Cmts.User).

6. QUESTION BEFORE BUILD: your 0.30 mm hole-to-hole minimum is quoted against
   "vias <= 0.45 mm". Every via here is 0.50 / 0.55 / 0.60 / 0.80 mm. Does
   0.30 mm still apply? If not, tell us the figure before the order runs.

ASSEMBLY: single sided, top only. Stencil 0.12 mm laser cut, trapezoidal walls,
electropolished. Reduce large paddle apertures to ~70% area. Do not bridge an
exposed thermal pad to the pin 0.15-0.20 mm away.
```

---

## 15. The fabrication package

Not yet generated — Task 9 step 7. It will contain:

| File | Source |
|---|---|
| Gerbers (X2, all copper + mask + silk + paste + `Edge.Cuts`) | `kicad-cli pcb export gerbers` |
| Drill files (Excellon, plated and non-plated separated) | `kicad-cli pcb export drill` |
| Gerber job file (`.gbrjob`) — carries the stackup | emitted with the Gerbers (`creategerberjobfile yes`) |
| BOM (CSV) | `kicad-cli sch export bom`, reconciled against `part-selection.md` |
| CPL / pick-and-place (CSV, top only) | `kicad-cli pcb export pos` |
| Schematic PDF | `kicad-cli sch export pdf` |
| Assembly drawings (PDF, `F.Fab` + this document) | `kicad-cli pcb export pdf` |
| This file | `docs/fabrication.md` |

Plot parameters are already set in the board (`pcbplotparams`): Gerber X2 with advanced attributes,
job file on, output to `output/gerbers/`, DNP parts crossed out on the fab layer.

The whole board is generated — `python scripts/gen_pcb.py` writes `mccan.kicad_pcb` from
`scripts/layout_pcb.py`. Nothing is hand-edited, so the fab package must always be re-exported from
a freshly generated board rather than from a working copy.

---

## 16. Open items

- **[TO CONFIRM]** Hole-to-hole minimum at 0.50–0.80 mm via diameters (§13). Blocking for the order.
- **[TO CONFIRM]** Antenna-to-plate vertical clearance. In-plane clearance is 17.3 mm; the plate
  sits ~1.6 mm below `B.Cu`. See `enclosure.md`.
- **[TO CONFIRM]** 8:1 aspect ratio and 0.15 mm annular ring as standard process, on 47 holes
  (§5). If either is an upcharge, 35 of the 47 can be re-routed away.
- **[OPEN]** Via counts in §5 will grow by a handful as the last ~20 hops are hand-routed.
- **[OPEN]** Gap-pad part not selected. It must be an insulator rated for +24 V (§10) and is
  specified in `enclosure.md`, not here.
- **[OPEN]** Panelisation: no requirement stated. For a prototype quantity, single pieces.
