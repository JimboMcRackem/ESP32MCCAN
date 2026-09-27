# Fabrication and Assembly Notes

**Status: DRAFT — the board is not yet fabricable.** The external router's result is folded into
the board (`scripts/routes_signal.json`), and every figure below is measured against that board.
KiCad DRC currently reports **9 violations and 11 unconnected items**, at both `--severity-error`
and `--severity-all` (re-run this session with `kicad-cli pcb drc --severity-error
--schematic-parity --exit-code-violations --refill-zones`; see `../README.md` for why both
severities matter and why the exit code is not the gate). All 9 violations are `via_dangling` —
vias left on nets the router could not close. The 11 unconnected items are **9 signal nets (two of
them U9's own pins, `Net-(U9-IN0)` and `Net-(U9-IS)`) plus one `GND` pad** (U4 pad 4). **This is a
real gap, not a rounding error in a report: the board cannot go to order until those 11 close.**
Nothing else in this document depends on those hops.

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
| Board size | 200.0 × 140.0 mm rectangle, 3.0 mm corner radius |
| Layers | **8** |
| Material | FR4, Tg ≥ 150 °C |
| Finished thickness | **1.6 mm** |
| Outer copper | **1 oz (35 µm) finished** |
| Inner copper | **1 oz (35 µm) — all six inner layers** |
| Min track / clearance | **0.20 mm / 0.20 mm** (both outer and inner) |
| Min drill | **0.20 mm** (plated) |
| Max aspect ratio | **8:1** (1.6 mm ÷ 0.20 mm) |
| Min annular ring | **0.15 mm** |
| Min hole-to-hole | 0.30 mm — **see §13, this needs confirming** |
| Copper to board edge | 0.50 mm |
| Surface finish | **ENIG** |
| Solder mask | both sides; **pad-to-mask clearance 0** |
| Silkscreen | both sides (top only is populated) |
| Via treatment | tented both sides, **except every via landing inside a pad — 189 of them, plugged and capped (§7, §14 item 1)** |
| Controlled impedance | **NO — do not quote it** (§11) |
| Castellations / edge plating / V-score | none |
| Assembly | **single sided, top only** — `B.Cu` carries copper but no parts |

---

## 2. Stackup

Eight layers, built as a foil lamination: three cores and four prepregs, with `F.Cu` and `B.Cu` as
outer foil. It is symmetric about the middle core, which is what keeps the panel flat.

**Revision, 2026-09-27 — the board went from six layers to eight, and the feed plane changed
layers with it.** The six-layer stackup this section used to describe, and the split-`In3.Cu`
arrangement spec §3.2 argued for, were both superseded on this branch: the split was implemented
and then reversed (a per-net island computed as a bounding box swallows foreign pads once that
net's own pads span the board), so the plane that survives is a **solid, unbroken `/VBAT` pour on
`In4.Cu`** — not split, and not on `In3.Cu`. Read verbatim from `mccan.kicad_pcb`'s own `(stackup
...)` block:

```
    F.Mask     0.010
    F.Cu       0.035    signal
      prepreg  0.100
    In1.Cu     0.035    GND  — solid, unbroken
      core     0.200
    In2.Cu     0.035    signal — CAN stripline (§11), plane-referenced both sides
      prepreg  0.2454
    In3.Cu     0.035    GND  — solid, unbroken
      core     0.200
    In4.Cu     0.035    /VBAT — solid, unbroken, the 7 A feed plane
      prepreg  0.2454
    In5.Cu     0.035    signal
      core     0.200
    In6.Cu     0.035    GND  — solid, unbroken
      prepreg  0.100
    B.Cu       0.035    signal + GND pour + a +24V pour under D4
    B.Mask     0.010
                -----
                1.571 mm copper + dielectric (8 × 0.035 mm copper + dielectrics
                0.100/0.200/0.2454/0.200/0.2454/0.200/0.100 mm), pressed to 1.6 mm finished
```

Every signal layer sits next to a plane on at least one side: `F.Cu` by `In1.Cu` (`GND`); `In2.Cu`
by `In1.Cu` and `In3.Cu`, both `GND` — a true stripline; `In5.Cu` by `In4.Cu` (`/VBAT`) above and
`In6.Cu` (`GND`) below; `B.Cu` by `In6.Cu` (`GND`).

FR4 constants in the KiCad stackup are εr 4.5, loss tangent 0.02. **These are nominal.** The
sub-thicknesses are nominal too — the fab is free to adjust them to hit 1.6 mm, because nothing on
this board depends on a specific dielectric height (§11). The one thing that is **not** adjustable
is the *order* of the layers and the 0.1 mm prepreg either side: `F.Cu` and `B.Cu` must each sit
one thin prepreg from their reference plane.

### Why 1 oz on all eight

The earlier four-layer revision specified 1 oz outer / 2 oz inner, and the 2 oz was bought for the
`VBAT` plane. Going to six layers (and then eight) made the 2 oz impossible and then showed it had
never been needed:

- **Impossible**, because `In2.Cu` and `In5.Cu` carry *tracks* — the two signal entries of
  `gen_pcb.SIGNAL_LAYERS` among the six inner layers (`In4.Cu` is the solid `/VBAT` plane, not a
  track layer). PCBWay etch inner layers to 4/4 mil at 1 oz but 6/8 mil at 2 oz, and 8 mil is
  0.203 mm — **above** the 0.20 mm clearance every net class on this board declares. Inner copper
  weight is a single selector for all inner layers short of a custom stackup, so the signal layers
  decide it for the plane layers too — the argument gets *stronger* on this board: two inner
  signal layers out of six inner layers taking one selector, rather than two out of four.
- **Not needed**, because `scripts/check_plane_width.py` measures what the `In4.Cu` pour actually
  delivers rather than trusting the arithmetic: it rasterises the zone, punches every via and
  through-hole antipad out of it, cuts it in both directions and grades the worst cut. Re-run this
  session against the board as committed:

  ```
  /VBAT on In4.Cu, 1445 hole(s) punched through it
    narrowest vertical cut:   104.90 mm at x = 97.3
    narrowest horizontal cut: 136.70 mm at y = 144.1
  ```

  The worst cut carries **104.90 mm** of effective width against the **11.44 mm** IPC-2221 asks
  for 7.0 A at a 10 K rise, internal, 1 oz — a **9.2×** margin. (Earlier figures recorded on this
  branch for this same measurement — 71 mm/6.1× on the retired six-layer `In3.Cu`, 106.50 mm/9.3×
  before the router, 105.30 mm/9.2× and 104.90 mm/9.2× at two routing checkpoints since — are all
  superseded by this one; the router has moved the cut since every one of them.) Having a whole
  layer is what made the feed work, not the copper weight.

1 oz outer is also what holds U10's 0.15 mm land pattern (§6): the finer the etch, the less
sideways copper growth there is to close a gap that small.

---

## 3. Board outline and mechanical

**Re-measured this session against `mccan.kicad_pcb` directly** (the eight `Edge.Cuts` entities
and the `MountingHole_3.2mm_M3` footprints), replacing the 140 × 100 mm board this section
described before the re-layout:

- Rectangle **200.0 × 140.0 mm**, corners radiused **3.0 mm** (four straight `Edge.Cuts` sides plus
  four 3 mm arcs, nothing else — outline runs x 20…220, y 20…160).
- Four **M3 mounting holes, 3.2 mm NPTH**, 5.0 mm in from each corner. In board coordinates:
  **(25, 25), (215, 25), (25, 155), (215, 155)** — read off footprints H1–H4 directly, not derived
  from `MOUNT_INSET` arithmetic.
- Copper is held **0.50 mm** off the edge everywhere.
- No V-score, no tab-route, no panelisation requested. If the fab panelises for their own handling,
  the antenna keep-out below still applies to the finished piece.

### Antenna keep-out — this one is absolute, and its coordinates moved 60 mm

`U5` is an ESP32-WROOM-32E module (footprint `RF_Module:ESP32-WROOM-32E`, at board coordinates
207, 72, rotated 270°) mounted so its antenna overhangs the board's right-hand edge. Its all-layer
`keepout` zone polygon, read from `mccan.kicad_pcb` this session (search the U5 footprint for
`(keepout`), is the authority — not a constant, not a note on `Cmts.User`. **No copper, no plating,
no parts, no silkscreen and no mask on ANY layer** inside:

> **x 213.56 … 234.75, y 48.00 … 96.00** (board coordinates) — 21.19 × 48.00 mm

**This is not the same rectangle §14 item 5 used to point at.** The board moved 60 mm to the right
during the re-layout (U5 was at x=147 on the old board) and this keep-out moved with it; a reader
still working from the old x 153.56…174.75 coordinates would clear the wrong patch of board by
60 mm. **There is currently no marked region for it on `Cmts.User`** — the only antenna-related
mark there is a free-standing text note (`scripts/layout_pcb.py:419`) placed near the top edge of
the board, roughly 90 mm from this rectangle, carrying the datasheet's 18.0 × 6.19 mm antenna-element
figure rather than this keep-out's own 21.19 × 48.00 mm. **Drawing that region and moving that note
is copper-generating work (`scripts/layout_pcb.py`), which is out of scope for this documentation
pass — see §16.** Until it exists, this document and the order text in §14 are the only correct
source for where the keep-out is.

The keep-out extends past the board edge; that is intentional. The heat-spreader plate is notched
to clear it — see `enclosure.md`.

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

Net classes (`mccan.kicad_pro`'s `net_settings`, written by `scripts/gen_netclasses.py` from
`layout_pcb.NETCLASSES`) — track / clearance / via / drill, all mm, read from the project file this
session:

| Class | Track | Clearance | Via | Drill | Nets |
|---|---|---|---|---|---|
| `FEED` | 3.50 | 0.30 | 0.80 | 0.40 | `/VBAT` and the rest of the 7.0 A input chain (7 nets, incl. `/power_input/GND_IN`) |
| `POWER` | 2.00 | 0.30 | 0.80 | 0.40 | `/VLOGIC_IN`, `/+24V`, `/+5V` |
| `CAN` | 0.30 | 0.20 | 0.60 | 0.30 | `/CANH`, `/CANL` and U6's two internal CAN nets |

**There is no `Default` netclass** — every net not matched above sits on the board's own DRC
floors (the table just above: 0.20 mm track and clearance, 0.60/0.30 via/drill from KiCad's
built-in class, which just repeats those same floors). The row this table used to carry for
"Default" quoted 0.25 mm track width; the project file gives 0.20 mm, matching the floor, so that
row was simply wrong and is removed rather than corrected in place.

**`FEED` at 3.50 mm is a 20 K-rise width (8.01 A at 1 oz), not a 10 K one, and that is deliberate.**
It is a *floor* for the short hops between the input parts, which sit in one tight island by J1.
Anything running further than a few millimetres on `F.Cu` must be **poured to ≥ 4.5 mm**, and the
through-path itself belongs on the `In4.Cu` polygon (the `/VBAT` plane — §2; **not** `In3.Cu`,
which is solid `GND` on this board). A net-class minimum cannot express "and pour it", which is why
the board note says so in words.

---

## 5. Drill schedule

**Confirmed this session against `output/drill/drill-report.txt`**, KiCad's own Excellon hit
report (`kicad-cli pcb export drill --format excellon --excellon-separate-th --generate-report`,
Task 11 Step 7) — the authority this section is supposed to be re-derived from, generated for the
first time in this task. Every count below matches the report exactly: **1447 plated holes, 28
non-plated, 1475 total**, tallied by drill size in `mccan-PTH.drl` and `mccan-NPTH.drl`. (An
earlier pass this session had tallied the same counts directly from `mccan.kicad_pcb`'s `via` and
`thru_hole`/`np_thru_hole` entries before the drill files existed; the two methods agree exactly,
which is worth recording since they are independent code paths over the same board.)

**Plated (PTH + vias):**

| Drill | Pad / via dia. | Count | What |
|---|---|---|---|
| 0.20 | 0.60 | 12 | thru-hole pads inside U5's module footprint (its stitched thermal paddle) |
| **0.20** | **0.50** | **65** | vias at the board's minimum via size — the 0.15 mm annular-ring floor |
| 0.25 | 0.55 | 65 | **via-in-pad thermal arrays — see §7** |
| 0.30 | 0.60 | 968 | `CAN` and unclassified-net routed/stitching vias |
| 0.40 | 0.80 | 303 | `FEED` / `POWER` vias, ground drops, stitching |
| 1.00 | — | 6 | connector / discrete leads |
| 1.15 | — | 18 | connector / discrete leads |
| 1.30 | — | 4 | connector / discrete leads |
| 2.15 | — | 6 | heavy wire-solder pads |

**Non-plated:**

| Drill | Count | What |
|---|---|---|
| 2.60 | **18** | 0.5 mm² solder-wire relief holes (J-connectors) |
| 3.20 | 4 | M3 mounting holes H1–H4 |
| 3.50 | 6 | 1.5 mm² solder-wire relief holes |

**1401 vias in total.** `scripts/check_vias.py` reports 855 of them as frozen from the external
router (`routes_signal.json`) and 546 as graded/hand-authored ("ignoring 855 frozen from the
router" in its own output) — 855 + 546 = 1401, so that is the "came from the router" figure for
this section, in place of the six-layer board's 968-total/614-router figures, which this board has
long since exceeded.

The **0.20 mm** plated hole is the binding one, and there are **77** of them (65 vias + 12 of
U5's footprint pads) — not 47, the six-layer board's figure, and not 66/78, a routing checkpoint
between here and there. At 1.6 mm finished that is still an **8:1 aspect ratio**, the top of most
fabs' standard through-hole plating capability. The twelve from U5's footprint cannot be relieved
by rerouting. **The other 65 sit exactly at this board's 0.15 mm minimum annular ring** (0.50 mm
via / 0.20 mm drill); *why* the router placed them at the minimum rather than the 0.6/0.3 mm
default was not re-verified against the current routing this session — treat any claim about which
fanout forced them as unconfirmed. **If the fab will not hold 8:1 and a 0.15 mm ring as standard
process, say so before the order** — the 65 can be re-routed at 0.6/0.3 for the cost of some
congestion, the 12 cannot.

Total holes on the board: 1401 vias + 46 plated component pads + 28 non-plated holes = 1475.

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
| `U10` | — | **0.175 mm** (unverified this session) | **track to pad** — U10 pads 3/5 (`U10_GATE`, `VBAT_PROT`) to a 0.30 mm `SNS` track |

The first three rows are pad-to-pad gaps fixed by the manufacturer's land pattern — confirmed this
session against `mccan.kicad_dru`, which is generated from a scan of the board and carries exactly
these three (`U1`, `U2`, `U10`, each at the value above) — and they do not move when the board is
re-routed.

**The track-to-pad row is a different kind of number: it depends on where a specific routed track
sits relative to the pad, which Task 10's router run can and does change.** `mccan.kicad_dru`'s
`memberOfFootprint()` condition does cover the track as well as the pad, so DRC is silenced here
correctly — but the exact clearance figure was not re-measured against the routing this board now
carries, and this document should not state one it did not check. **0.175 mm (and the two below)
are carried forward from before Task 10's routing and are unverified against the current board;**
treat them as "still this tight or tighter" rather than as exact. The next two gaps, on the same
basis, are ~0.183 mm (U10 pad 1 to a `VCC10` track) and ~0.190 mm (U1 pad 5 to a `Net-(U1-BST)`
track). Nothing else on the board is stated to be under 0.20 mm, and that claim is equally
unverified against the current routing.

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
  not matter and a few millimetres of skew between the two tracks is ~20 ps.
  **The reasoning below changed from the six-layer board and the conclusion did not.** `CANH`/`CANL`
  are now routed almost entirely on `In2.Cu` (16 of the 20 segments on the two nets this session;
  the rest are short fanout hops onto `In5.Cu`), which sits 0.2 mm below `In1.Cu` and 0.2454 mm
  above `In3.Cu` — both solid, unbroken `GND` (§2). That makes the pair a true **stripline** with a
  reference plane on both sides, not the six-layer board's single-sided arrangement, so the return
  current has two nearby paths to run in rather than one. This was routed for **immunity**, not for
  impedance, and it still is — a stripline is, if anything, *more* tightly coupled to its return
  path than the six-layer arrangement was, not less. What the differential impedance actually lands
  at was not computed this session (a field solver, not this document, is the right tool for that
  number), and it does not need to be: what the bus sees is the 120 Ω termination at R26, and the
  track is far too short relative to the signal edge for anything between the transceiver and R26
  to be visible to it, on either stackup.
- **The ESP32 module** carries its own RF; nothing on this board routes RF.
- There is no USB, no Ethernet, and no memory bus.

The dielectric heights in §2 are therefore nominal and the fab may adjust them freely to hit
1.6 mm.

---

## 12. Copper pours

**Seven zones**, read from `mccan.kicad_pcb` directly this session (`(zone ...)` entries) — not
five, which was the six-layer board's count and is now wrong twice over (too few zones, and naming
`In3.Cu` as the feed instead of `In4.Cu`):

| Layer | Net | What |
|---|---|---|
| `In1.Cu` | `GND` | **solid and unbroken** — the reference plane for `F.Cu` and `In2.Cu` |
| `In3.Cu` | `GND` | **solid and unbroken** — the second reference plane for `In2.Cu`'s stripline (§11) |
| `In4.Cu` | `/VBAT` | the 7 A feed plane (§2) — **not `In3.Cu`** on this board |
| `In6.Cu` | `GND` | **solid and unbroken** — the reference plane for `In5.Cu` and `B.Cu` |
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
8-layer FR4, 1.6 mm finished, Tg >= 150 C.
1 oz (35 um) finished copper on ALL EIGHT layers -- inner layers must be 1 oz,
  NOT 2 oz: inner clearance is 0.20 mm and 2 oz inner etch cannot hold it.
Min track/clearance 0.20/0.20 mm outer AND inner.
Min plated drill 0.20 mm, 77 holes (aspect ratio 8:1 at 1.6 mm): 65 vias of
0.50 mm dia plus 12 thermal through-pads of 0.60 mm dia inside U5's footprint.
Min annular ring 0.15 mm, on those 65 vias of 0.50 mm dia / 0.20 mm drill.
Surface finish ENIG. Mask both sides, silkscreen both sides.

1. VIA IN PAD, PLUGGED AND CAPPED (IPC-4761 type IV or VI), planarised, BY
   RULE: every via whose centre falls inside a copper pad, wherever on the
   board it sits. That is 189 vias over 129 pads on the board as generated
   (scripts/check_vias.py recomputes this count on every build and is the
   authority for it going forward; the drill/Excellon files are the
   authority for exactly which holes they are). The default finish is
   TENTED, which is a mask skin over an open barrel and is NOT the same
   thing -- any of these left tented wicks paste down the barrel during
   reflow and starves the joint under that pad.

   The five largest concentrations are dedicated thermal arrays and want
   filling for that reason too, not only this rule: D4 pad 3, U1 pad 9, U2
   pad 9, U3 pad 17, U9 pad 15 (65 vias, 0.55 mm pad / 0.25 mm drill,
   0.80 mm pitch -- exactly the 0.55 mm-diameter subset of the 189). The
   other 124 vias sit over 124 more pads spread across the board -- wherever
   a feed via lands on a pad centre by design, or a router via changes layer
   inside a pad it fanned out to -- and are to be plugged and capped the
   same as the five.

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
   at the right-hand edge, board coordinates x 213.56-234.75, y 48.00-96.00.
   There is NO marked region for this on Cmts.User today -- only a text note
   near the top edge with the wrong dimensions -- so these coordinates, taken
   from U5's own footprint keep-out polygon, are the authority. Ask the fab
   to confirm receipt of this note in writing; do not rely on a drawing mark
   that does not yet exist (see Section 3).

6. QUESTION BEFORE BUILD: your 0.30 mm hole-to-hole minimum is quoted against
   "vias <= 0.45 mm". Every via here is 0.50 / 0.55 / 0.60 / 0.80 mm. Does
   0.30 mm still apply? If not, tell us the figure before the order runs.

7. THE BOARD IS NOT YET READY TO ORDER. 11 pads are unconnected (Status,
   top of this document) -- do not release this package until that is 0.

ASSEMBLY: single sided, top only. Stencil 0.12 mm laser cut, trapezoidal walls,
electropolished. Reduce large paddle apertures to ~70% area. Do not bridge an
exposed thermal pad to the pin 0.15-0.20 mm away.
```

---

## 15. The fabrication package

> ## DO NOT SEND THIS PACKAGE TO A FABRICATOR
>
> This package was generated from a board that is not electrically complete, so that the export
> step itself could be exercised and checked — not because the board is ready to order. **The
> board has 11 unconnected pads, of which 9 are signal nets serving the lighting outputs this
> board exists to drive** (`/outputs/MUXIN_FL_R`, `/outputs/MUXIN_RR_G`, `/outputs/PWM_FL_B`,
> `/outputs/PWM_FR_B`, `/outputs/PWM_RL_G`, `/outputs/PWM_RR_B` — two open items on one net, a
> U7/Q9/R51 chain — `/outputs/PWM_RR_R`, and U9's own pins `Net-(U9-IN0)`/`Net-(U9-IS)`); the
> remaining one is a `GND` pad (U4 pin 4). Generated from board md5 `6c4f884ff624c5b9d3bc484f7bb2613e`,
> commit `1b788e04e45d8d7814d92c011c13595499ecc8a4` (the last commit to touch `mccan.kicad_pcb`).
> **This package will be regenerated once those 11 nets close** and DRC reports zero unconnected
> items and zero violations at both severities. `output/gerbers/NOT-FOR-FABRICATION.txt` carries
> this same warning inside the gerber directory itself, so it travels with the files if they are
> copied out of this repo.

**Generated 2026-09-27, Task 11 Step 7**, from the board at md5 `6c4f884ff624c5b9d3bc484f7bb2613e`
(commit `1b788e04e`), with `kicad-cli 10.0.2`:

| File | Source | Generated |
|---|---|---|
| Gerbers, 8 copper + mask + silk + paste + `Edge.Cuts` (X2, `--check-zones`) | `kicad-cli pcb export gerbers` | `output/gerbers/*.g*` — see note below on filenames |
| Gerber job file (`.gbrjob`) — carries the stackup and disambiguates the layer names below | emitted with the Gerbers | `output/gerbers/mccan-job.gbrjob` |
| `output/gerbers/NOT-FOR-FABRICATION.txt` | written by hand this session, not by `kicad-cli` | — |
| Drill files (Excellon, plated/non-plated separated, hit report) | `kicad-cli pcb export drill` | `output/drill/mccan-PTH.drl`, `mccan-NPTH.drl`, `mccan-*-drl_map.pdf`, `drill-report.txt` (§5's authority) |
| BOM (CSV) | `kicad-cli sch export bom` | `output/mccan-bom.csv` — **not yet reconciled against `part-selection.md` this session; see §16** |
| CPL / pick-and-place (CSV, top and bottom) | `kicad-cli pcb export pos` | `output/mccan-cpl.csv` |
| Schematic PDF | `kicad-cli sch export pdf` | `output/mccan-schematic.pdf` |
| Assembly drawing (PDF, `F.Fab`/`B.Fab`/`F.Silkscreen`/`Edge.Cuts`, multipage, DNP crossed out) | `kicad-cli pcb export pdf` | `output/mccan-assembly.pdf` |
| This file | `docs/fabrication.md` | — |

**A real defect was found and worked around while generating the gerbers, and it is worth a
fabricator's attention regardless of the 11 open nets.** The board's layer table gives three
different physical layers (`In1.Cu`, `In3.Cu`, `In6.Cu`) the same user-facing name, `GND`, and a
fourth (`In4.Cu`) the name `PWR`. Plotting with the exact invocation this section used to
recommend — `kicad-cli pcb export gerbers --board-plot-params --check-zones` — uses the board's
own stored plot setting `usegerberextensions no`, which names every copper gerber `mccan-<name>.gbr`
with no per-layer disambiguation. **The three `GND` layers all write to the same filename in that
mode, and each plot overwrites the last: the resulting directory silently contains only one
ground layer's copper, duplicated by name onto two others.** Confirmed this session by running
that exact command into a scratch directory and comparing: the `.gbrjob` file correctly claims
three separate files for `In1.Cu`/`In3.Cu`/`In6.Cu` (L2, L4, L7), but only one `mccan-GND.gbr`
exists on disk, holding `In6.Cu`'s copper. **That is not this package** — the actual export
above used `kicad-cli pcb export gerbers --check-zones -l F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,In5.Cu,In6.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts`
(explicit layer list, `--board-plot-params` omitted), which falls back to `kicad-cli`'s default
numbered Protel-style extensions and produces three genuinely distinct files —
`mccan-GND.g1`/`.g3`/`.g6` — confirmed by MD5 (three different hashes) and by content (each
declares its own `%TF.FileFunction,Copper,L2/L4/L7,Inr%`). **The files are still named ambiguously
by basename** (`GND.g1`, `GND.g3`, `GND.g6`, `PWR.g4`); a fab or a human skimming the directory by
filename alone cannot tell them apart, and must read `mccan-job.gbrjob`'s `FilesAttributes` list
to map each file to its physical layer. This is a real gap in the board's own generated layer
naming (`scripts/gen_pcb.py`, which sets each plane's user-facing name and the stored
`pcbplotparams`) and is flagged in §16 as a script fix for someone with scope to touch
`hardware/scripts/` — this task's hard constraints forbid editing it.

**Confirming Ruling B — the four plane layers are not blank.** The board stores 36 zones and
zero `filled_polygon` entries (`grep -c filled_polygon mccan.kicad_pcb` → 0), so KiCad fills them
only on load/plot; plotting without `--check-zones` would have exported the `GND` and `/VBAT`
planes as empty copper. `--check-zones` was used for every plot above, and the resulting files
are non-trivially sized — an empty plane would be a few hundred bytes, not this:

| Layer | Net | File | Size |
|---|---|---|---|
| `In1.Cu` | `GND` | `mccan-GND.g1` | **926,530 bytes** |
| `In3.Cu` | `GND` | `mccan-GND.g3` | **926,530 bytes** |
| `In4.Cu` | `/VBAT` | `mccan-PWR.g4` | **1,368,647 bytes** |
| `In6.Cu` | `GND` | `mccan-GND.g6` | **926,530 bytes** |

(`In1.Cu` and `In3.Cu` and `In6.Cu` landing on the identical byte count is coincidence, not a
duplicate-content bug — confirmed above by MD5, all three differ.) The gerber set carries all
**eight** copper layers (`F.Cu`, `In1.Cu`–`In6.Cu`, `B.Cu` — verified against `mccan-job.gbrjob`'s
`FilesAttributes` list, L1 through L8), not six, which would have been the tell that the board
never regenerated.

`mccan.kicad_pcb` was confirmed unchanged by the plot (`--check-zones` refills zones in memory
while plotting, but does not write the result back to the board file): md5
`6c4f884ff624c5b9d3bc484f7bb2613e` before and after every export command in this section, and
`git diff --stat mccan.kicad_pcb` empty throughout.

The whole board is generated — `python scripts/gen_pcb.py` writes `mccan.kicad_pcb` from
`scripts/layout_pcb.py`. Nothing is hand-edited, so the fab package must always be re-exported from
a freshly generated board rather than from a working copy — and, per the warning above, re-exported
using an explicit `--layers` list rather than `--board-plot-params` until the layer-naming defect
is fixed at the source.

---

## 16. Open items

- **[BLOCKING]** The board is not yet fabricable. 11 pads are unconnected (Status, top of this
  document): 9 signal nets (two of them U9's own pins) plus one `GND` pad. Verified this session
  via `kicad-cli pcb drc` at both severities — 9 `via_dangling` violations, 11 unconnected items,
  0 footprint errors. Do not release an order until this is 0.
- **[BLOCKING]** A fabrication package now exists (§15, generated 2026-09-27) but is explicitly
  marked **NOT FOR FABRICATION** — it was generated to exercise and check the export step, not
  because the board above is ready. Do not send it to a fab. It must be regenerated once the item
  above closes.
- **[TO FIX, in `hardware/scripts/`, out of this task's scope]** Plotting gerbers with
  `--board-plot-params` (as this document used to recommend in §15) silently loses two of the
  three `GND` plane layers, because `In1.Cu`, `In3.Cu` and `In6.Cu` all carry the board's
  user-facing layer name `GND` and the board's stored `usegerberextensions no` setting gives
  every copper gerber the same `.gbr` extension with no disambiguation — three plots to the same
  filename, two of them overwritten. §15 documents the workaround (explicit `--layers`, letting
  `kicad-cli` fall back to numbered Protel extensions) and confirms by MD5 that the resulting
  files are genuinely distinct, but the files are still only distinguishable by reading
  `mccan-job.gbrjob`, not by filename. The real fix is in `hardware/scripts/gen_pcb.py`, which
  sets each plane's user-facing name and the stored `pcbplotparams` — give `In1.Cu`, `In3.Cu` and
  `In6.Cu` distinct names (or turn `usegerberextensions` on) so `--board-plot-params` alone
  produces an unambiguous set. This task's hard constraints forbid editing
  `hardware/scripts/`, so it is reported here rather than fixed.
- **[OPEN]** The BOM (`output/mccan-bom.csv`, generated 2026-09-27) has not been reconciled
  against `part-selection.md` this session — §15's table flags this. Do it before ordering
  parts from it.
- **[TO CONFIRM]** Hole-to-hole minimum at 0.50–0.80 mm via diameters (§13).
- **[TO CONFIRM]** Antenna-to-plate vertical clearance. In-plane clearance is 17.3 mm (per
  `enclosure.md`, not re-verified against the new board geometry this session); the plate sits
  ~1.6 mm below `B.Cu`. See `enclosure.md`.
- **[TO CONFIRM]** 8:1 aspect ratio and 0.15 mm annular ring as standard process, on 77 holes
  (§5). If either is an upcharge, 65 of the 77 can be re-routed away; the other 12 are inside U5's
  footprint and cannot be.
- **[OPEN]** The antenna keep-out (§3, §14 item 5) has no marked region on `Cmts.User` yet — only
  a stray text note with the wrong dimensions near the top edge. Drawing the correct dashed
  rectangle is copper-generating work in `scripts/layout_pcb.py`, out of scope for this
  documentation pass. Until it exists, this document is the fab's only correct source for the
  keep-out's coordinates.
- **[OPEN]** §6's three track-to-pad gaps (0.175 / 0.183 / 0.190 mm) were not re-measured against
  Task 10's routing this session and are carried forward as unverified, not as fact.
- **[OPEN]** Gap-pad part not selected. It must be an insulator rated for +24 V (§10) and is
  specified in `enclosure.md`, not here.
- **[OPEN]** Panelisation: no requirement stated. For a prototype quantity, single pieces.
