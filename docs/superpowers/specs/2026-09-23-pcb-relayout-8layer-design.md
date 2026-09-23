# ESP32 MCCAN — PCB Re-layout: 200 × 140 mm, 8 Layers

**Date:** 2026-09-23
**Status:** design, approved for planning
**Branch:** `plan3-pcb-hardware`
**Supersedes:** the board produced by Plan 3 Tasks 8–9 up to commit `4989e8a`. It does
**not** supersede `2026-09-11-esp32-mccan-pcb-hardware-design.md` — that document remains
the electrical specification. This one replaces its §9.1, §9.3 and §10 and nothing else.

---

## 1. Why this exists

The 6-layer, 140 × 100 mm board reached 0 DRC errors and 122 of 139 signal nets routed,
and it is still not a board worth fabricating. Three complaints, all of them the same
complaint:

1. **It cannot be read.** `silk_refs()` in `gen_pcb.py` demoted 12 reference designators to
   F.Fab and shrank 4 more to the board's own minimum text size, because there was nowhere
   legible to put them. D10, D12, D13, D15, D16, D18, F4, L6, Q3, Q5, Q6 and Q8 have no
   reference on the silkscreen at all.
2. **The signal side is congested.** `layout_pcb.py`'s own comment records the outputs block
   at **59 % courtyard fill** and calls that "about twice what a two-layer escape can be
   routed through". Adding layers twice — 4 → 6 — treated the symptom.
3. **Routing is hand-work where it should not be.** Four commits of hand-routing
   (`2c74003`, `d2b44b7`, `4989e8a`) went into nets that carry no special requirement,
   because the router had no room to work in.

All three are density. The fix is room, and the decision taken here is to stop economising
on it.

The area is also the answer to an open defect logged elsewhere: `hardware/docs/enclosure.md`
§2 item 5 records that seven cable glands need **≈ 143 mm** of wall and "will not fit a
140 mm wall". No enclosure part number has ever been chosen, so the board was never
constrained by a box — the box follows the board.

---

## 2. Outline

**200 × 140 mm.** Four M3 mounting holes, 5 mm in from each corner, 3.2 mm drill on a
6.0 mm pad. Corners radiused 3 mm, drawn as four arcs, as today.

| | Old | New |
|---|---|---|
| Outline | 140 × 100 mm | **200 × 140 mm** |
| Area | 140 cm² | **280 cm²** (+100 %) |
| Footprints | 238 | 238 (unchanged) |
| Outputs block fill | 59 % | **~25 %** |
| Panel wall for 7 glands | 140 mm (needs 143) | **200 mm** |
| Heat-spreader plate | ~137 cm² → 61 °C | **~272 cm²** |

**The plate stops being a design driver.** `enclosure.md` §1 requires ≥ 150 cm² and the old
board delivered ~137 cm² after the antenna notch, which is why so much of the current
placement bends around the plate edge. At ~272 cm² the requirement is met roughly twice
over. The consequence is recorded in §4.3: the thermal group keeps its plate-edge placement
but loses its veto over everything else.

The antenna keep-out is unchanged in size — 18.0 × 6.19 mm from the module's end face, per
ESP32-WROOM-32E datasheet v1.8 Figure 12 — and U5 still points it off the board edge. The
plate is still the **base**, still notched at the antenna corner.

---

## 3. Stackup

**8 layers, 1 oz (35 µm) on all eight, 1.6 mm finished, foil lamination, symmetric.**

| # | Layer | Role |
|---|---|---|
| 1 | `F.Cu` | signal — component escapes, short runs |
| 2 | `In1.Cu` | **GND**, solid |
| 3 | `In2.Cu` | signal — **the CAN pair lives here** |
| 4 | `In3.Cu` | **GND**, solid |
| 5 | `In4.Cu` | **POWER**, split: `VBAT` \| `+24V` \| `+5V` \| `VLOGIC_IN` |
| 6 | `In5.Cu` | signal — bulk routing |
| 7 | `In6.Cu` | **GND**, solid |
| 8 | `B.Cu` | signal — short runs, plate side |

Four routing layers, three ground planes, one power layer.

**This fixes a defect in the 6-layer stack.** That stack was
`F sig / GND / sig / VBAT / sig / B sig`, in which `B.Cu` is a signal layer whose only
neighbour is another signal layer — bottom-side traces had no reference plane and no
defined return path. Here **every signal layer has a solid GND plane on at least one face**,
and `In2.Cu` has one on both.

`B.Cu` carries copper, so the two gap-pad contact patches on `Cmts.User` (1358 mm² total)
become keep-outs on `B.Cu`: the pad meets bare solder mask there, not routed copper.

### 3.1 Why CAN goes on In2.Cu

`In2.Cu` is a buried stripline between two solid ground planes. Putting `CANH`/`CANL` there
satisfies "CAN segregated from the high-current and boost nets" by construction rather than
by a keep-away rule that nothing enforces — the pair is physically enclosed in copper. It
also removes the pair from the two layers where the feed pours and the switch node live.

The pair stays matched-length with constant spacing. See §11 for the impedance question the
move opens.

### 3.2 Why the power layer is split, and the risk that creates

`VLOGIC_IN`, `+24V` and `+5V` are today the `POWER` netclass at 2.0 mm, routed as tracks.
A 2.0 mm track is awkward to route, and there is no reason for it when a layer is available:
as zones on `In4.Cu` they cost no routing effort at all and carry more current than they
need. The largest of these loads is the boost output at 0.5 A.

**The risk is that `VBAT` no longer owns a whole layer.** `hardware/scripts/check_plane_width.py`
measures the VBAT pour's worst cut at **71 mm** against the **11.44 mm** IPC-2221 requires
for 7.0 A at a 10 °C rise on 1 oz internal copper — a 6.1× margin. Sharing `In4.Cu` three
ways consumes some of that margin, and the margin is large but it is no longer free.

**This is accepted because the gate already exists.** `check_plane_width.py` rasterises the
zone, punches every via and through-hole antipad out of it, and cuts it in both directions.
It is part of the build and it fails the board. If the split starves the feed, the build
says so before anyone orders copper. No arithmetic argument is being relied on.

Return paths under the split are sound: `In5.Cu` is the only signal layer adjacent to
`In4.Cu`, and it has solid `In6.Cu` GND on its other face.

### 3.3 Carried over unchanged

- **Via floor 0.50 mm / 0.25 mm with a 0.15 mm annular ring.** PCBWay's stated minimum,
  given for vias-in-pad specifically, which is the case that applies here.
- **Through-hole vias only.** `route.py` appends unrequested copper layers as forbidden
  obstacles and only ever emits through-hole vias, so no blind or buried via can appear.
- **0.20 mm minimum track and clearance.** 1 oz territory. Inner-layer etch at 1 oz is
  4/4 mil at PCBWay, comfortably inside it — this was the reason the 6-layer revision had to
  drop inner copper to 1 oz, and it applies identically here.
- **Aspect ratio 6.4:1** (1.6 mm ÷ 0.25 mm) against PCBWay's ≤ 8:1.
- **Netclasses:** `FEED` 3.5 mm / 0.3 mm, `POWER` 2.0 mm / 0.3 mm, `CAN` 0.3 mm,
  `Default` 0.2 mm. `POWER` becomes a fallback rather than the normal case now that those
  rails pour on `In4.Cu`.
- **No outer-layer track carries the feed.** Anything running more than a few millimetres
  on an outer layer is poured to ≥ 4.5 mm.
- **`GND_IN` and `GND` meet at exactly two places** — L2 winding B, and R3.

---

## 4. Placement

The region/flow model in `layout_pcb.py` is kept. Its 1446 lines encode reasoning that is
expensive to re-derive and correct as it stands — why the boost's COMP network must sit at
the controller rather than 35 mm away, why D2 and R3 belong in the GND_IN column and not in
the input filter their sheet puts them on, why the wire-exit row is pitched to fit between
the lower mounting holes. Regions are re-proportioned to the new outline; three mechanisms
are added.

### 4.1 Channels

**6 mm part-free lanes between regions**, declared as placement keep-outs that the flow
packer may not enter and the router may.

At 0.20 mm track on a 0.40 mm pitch a 6 mm channel carries about **15 tracks per layer, 60
across the four signal layers**. That is a routing budget that can be reasoned about, as
against the current arrangement where inter-region space is whatever the packer happened not
to fill.

### 4.2 Fill budgets

Each region declares a maximum courtyard fill fraction. A new
`hardware/scripts/check_density.py` computes actual fill per region and **fails the build**
above the declared figure.

This turns the lesson already written in `layout_pcb.py`'s comments into something
enforced. The target that matters is outputs at ~25 %, down from 59 %.

### 4.3 The thermal group relaxes

The current rule is absolute: "**L2 is placed first and everything else gives way to it**".
That rule exists because the old plate delivered ~137 cm² against a 150 cm² requirement, so
plate-edge real estate was scarce.

At ~272 cm² it is not scarce. **L2 keeps its plate-edge placement** — it is still the
largest single thermal term at 0.78 W, still the tallest part at ~24 mm, still through-hole
on an otherwise-SMD board — as do U9, L1, U3 and L3. What it loses is the veto. The thermal
group is placed early; it no longer distorts the blocks around it.

R100 stays out of the thermal group, in the eFuse island with U10, with its own copper and
its Kelvin tap, and no thermal vias. Unchanged, and for the unchanged reason: the copper
around it is part of the measurement.

---

## 5. Silk and readability

`silk_refs()` currently runs a ladder: try the library position, then N/S/E/W of the part's
own body at increasing distance, then shrink to the board's minimum text height, then
**demote to F.Fab**. The ladder converts a placement failure into a board that cannot be
read on the bench, silently.

**Both fallbacks are removed. Demotion and shrinking become build failures.**

If a reference designator cannot be placed legibly, at full size, adjacent to its own part,
that is the placer's problem and the build stops. With twice the area and declared fill
budgets there is no honest reason for either fallback to fire.

The search itself — library position, then the four compass directions at increasing
distance — is kept. It is the *give up* branches that go.

---

## 6. Routing

The division of labour is explicit: geometry that carries an electrical requirement is laid
by hand before the router runs; everything else is the router's, constrained only by
netclass widths and the channel keep-outs.

### 6.1 By hand, first (~18 nets)

**The feed chain** — `VBAT`, `VBAT_PROT`, `VBAT_F`, `FEED_P`, `MID`, `SNS`, `GND_IN`.
Poured, never tracked; ≥ 4.5 mm on any outer-layer run of more than a few millimetres; the
bulk of it on the `In4.Cu` `VBAT` zone. The requirement is 7.0 A continuous with a 7.8 A
flash-to-pass transient of seconds.

**The CAN pair** — `CANH`/`CANL` on `In2.Cu`, matched length, constant spacing, GND above
and below.

**The boost** — `SW` → D4 → C61 → `PGND` at minimum loop area. The LM51571-Q1 integrates
its switch, so there are no gate loops and this is the only fast edge on the board; the
boost is non-synchronous, so D4 carries the commutation current and belongs in the loop.
`COMP`, `FB` and `SS` are routed away from the switch node — `COMP` is the error
amplifier's output and the highest-impedance node in the converter. The `FB` tap is taken
from the far end of the output capacitor, not the switch-node end.

Loop area is a geometric property no autorouter optimises for. A router will return an
electrically correct switch node that rings, and the failure appears on the bench, not in
any gate. That is why these are hand routes despite carrying no unusual width.

### 6.2 The router, second (~121 nets)

`hardware/scripts/route_external.py` drives KiCadRoutingTools over the four signal layers
with `--fab-tier standard --escalation board --no-bga-zones --keep-input-copper --json-out`.
`--strict-sizes` is deliberately not used: it exits 3 on any descent, including the
0.25 → 0.20 mm necking that is ordinary layout.

`freeze_routes.py` diffs the routed board against the unrouted input and writes what the
router **added** to `scripts/routes_signal.json`, which `gen_pcb.py` then emits in place of
running its own router. A diff, not a net filter — the input board carries hand routes
sitting on signal nets, and a filter would emit them twice.

`gen_pcb.py`'s own grid A* router stays as the fallback it has become. Its occupancy grid is
two-layer, so `AR_LAYERS` remains `F.Cu`/`B.Cu` and it is not expected to be used.

The board remains fully generated from `hardware/scripts/`. Nothing is hand-edited in
`mccan.kicad_pcb`.

---

## 7. Gates

Every gate runs on every build. A failure is a build failure, not a warning.

| Gate | Catches |
|---|---|
| KiCad DRC | clearance, unconnected, schematic parity |
| `check_geometry.py` | copper below the board's own minimums; tracks on a plane layer; zero-length segments. Grades the router's output **before** the copper is admitted |
| `check_vias.py` | via placement against a baseline, so the router's deliberate via-in-pad is not graded as gen_pcb's |
| `check_grounds.py` | `GND_IN` and `GND` meet at **exactly two** places — L2 winding B, and R3. DRC cannot catch this, because a pour never shorts to a foreign net |
| `check_plane_width.py` | the feed's effective poured width, antipads punched out, cut both ways. **Load-bearing now** — see §3.2 |
| `check_courtyards.py` | courtyard overlap |
| `check_density.py` | **new** — per-region courtyard fill against declared budgets (§4.2) |
| silk assertion | **new** — any reference designator shrunk or demoted to F.Fab (§5) |

---

## 8. Archive

The two superseded boards are preserved two ways, because a git tag records the source that
produced a board and an archive directory records the board itself, and reading the second
should not require checking out the first.

**Tags:**

- `board/v1-4layer` → `771f4cc` (the last 4-layer commit; `da4efea` is the six-layer change)
- `board/v2-6layer` → the tip of the current in-flight work, committed first so nothing is lost

**Directory** — `hardware/archive/`:

```
hardware/archive/
  README.md              what each board was, why it was retired, which tag holds its source
  v1-4layer/             mccan.kicad_pcb, drc.rpt, gate output
  v2-6layer/             mccan.kicad_pcb, drc.rpt, gate output
  v2-6layer/pcbway_production/   the production package, currently untracked
```

The uncommitted working tree — `mccan.kicad_pcb`, `routes_signal.json`, `layout_pcb.py`
(+278 lines), `check_courtyards.py`, `find_escape.py`, `show_room.py`,
`pcbway_production/` — is committed onto `plan3-pcb-hardware` before anything is archived
or torn down.

---

## 9. The skill

`~/.claude/skills/pcb-layout-routing/` — **user-level, and about the method rather than this
board**. The lessons worth keeping are tool lessons that will recur on any KiCad board;
MCCAN's own specifics stay in `hardware/docs/` where they already live.

```
~/.claude/skills/pcb-layout-routing/
  SKILL.md              when to use it; the generate → place → hand-route → route → gate workflow
  references/
    placement.md        regions, flow, channels, fill budgets, silk as a hard gate
    stackup.md          layer allocation, plane references, split-plane risk and how to measure it
    routing.md          what is hand-routed and why; loop area; Kelvin taps; pour-don't-track
    router-traps.md     the KiCadRoutingTools failure modes
    gates.md            the check suite, and what each one catches that DRC cannot
```

The contents that justify it existing:

- **`--fab-tier` is not the size floor; `--escalation` is**, and its default is `fab`, which
  means "below the board's own minimums". A run that returned 2177 tracks at 0.0889 mm
  against a 0.25 mm request exited 0 with every one of the tool's own graders content.
- **The BGA machinery is a fine-pitch-grid detector** and fires on TSSOP and QFN. It read a
  TSSOP-28 as a 14 × 2 ball grid and ran an under-pad shrink rescue at 0.0762 mm.
  `--no-bga-zones`.
- **Never let a routing tool grade itself.** Grade its output against the board's own rules
  before admitting the copper.
- **A pour never shorts to a foreign net**, so DRC cannot catch a ground-split error. If two
  nets must meet at exactly N places, a script has to count them.
- **Boards are generated, never hand-edited**, and the netlist is read by hand — ERC alone
  misses whole classes of error.
- **Loop area and Kelvin taps are placement problems**, not routing problems. There is no
  good route for a 35 mm COMP trace.
- **Density is the root cause behind most routing failure.** Measure courtyard fill before
  blaming the router or adding layers.

---

## 10. What is not changing

The schematic, the netlist, the BOM, part selection and the firmware. This design covers
outline, stackup, placement, silk and routing only. No component is added, removed or
substituted, and no net changes name or connectivity.

Documents amended, not replaced: spec §9.1 (panel), §9.3 (enclosure), §10 (PCB and EMC);
`hardware/docs/enclosure.md`; `hardware/docs/routing-tool.md`; `hardware/docs/fabrication.md`;
and Plan 3 Tasks 8 and 9.

---

## 11. Open items this creates

- **Enclosure part number.** Never chosen, and now needs a box for 200 × 140 mm plus the
  internal cable service loop and a ~24 mm tallest part. Hammond 1554/1555, Fibox, Bopla and
  Polycase were the candidate families; the size class has moved.
- **Mounting a box that size on the bike.** A 200 × 140 mm footprint is large for the
  application and wants a physical sanity check before the enclosure is ordered.
- **PCBWay's standard 8-layer 1.6 mm stackup** needs confirming — layer spacings, and
  whether 1 oz on all eight is a standard option or a surcharge.
- **CAN pair geometry.** The 0.3 mm / matched-pair figure was derived for an outer layer.
  As a stripline between two planes the geometry changes. Either re-derive it for the
  actual dielectric spacing, or record an explicit decision that the pair is uncontrolled —
  which is defensible for a short on-board run at CAN data rates, but should be a decision
  rather than an omission.

### Carried forward from the existing board, unresolved

These predate this design and are unaffected by it, but should not be lost in the move:

- Antenna-to-plate **vertical** clearance is unconfirmed (in-plane is 17.3 mm against
  Espressif's 15 mm); `enclosure.md` §8.
- Orderables not picked: Q12 (NPN), D21 (22 V Zener), D22/D23 (1N4148 class),
  C65 (22 µF 63 V), and L4/L5/L6 have no part numbers.
- The Infineon HSOF-8 variant for Q10/Q11 (-1 vs -2 vs -3) and its pad 1/2/3 → G/S/D.
- U10 is `Package_SO:MSOP-10_3x3mm_P0.5mm` with no exposed pad; confirm that is the right
  LTC4380 package.
- Whether D2 (SMBJ24A) should move from `VBAT_PROT` to `FEED_P` — deferred, NO for this pass.
- Spec §6 wrongly credits the boost pass-through to "the high-side FET's body diode"; the
  boost is non-synchronous, so it is D4.
- `harness.md` §6 still describes a panel fuse holder that no longer exists.
- Fab notes: via-in-pad plugging must be **specified on the order**, not implied by gerbers;
  U10's 0.15 mm pad gap is under PCBWay's 8 mil IC mask figure, so expect no mask dam there;
  their "vias ≤ 0.45 mm" hole-to-hole wording wants one DFM question.

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| The split power plane starves the `VBAT` feed | `check_plane_width.py` measures it and fails the build (§3.2). Current margin is 6.1× |
| 8 layers at 280 cm² costs materially more than 6 at 140 cm² | Accepted deliberately. The board is a one-off, and two respins of a cramped board cost more |
| A 200 × 140 mm enclosure is awkward to mount | Flagged as an open item (§11) before any enclosure is ordered |
| Removing silk's fallbacks makes the build unbuildable if placement is tight | That is the intent. The failure is loud and early, and the area exists to satisfy it |
| Channels consume area that placement then wants back | Budgets (§4.2) make the trade visible; outputs at ~25 % has substantial headroom |
| The router still falls short of 100 % | It has four layers and ~25 % fill rather than two and 59 %. Residual shortfall is hand-finished, as it was before, but from a much shorter list |
