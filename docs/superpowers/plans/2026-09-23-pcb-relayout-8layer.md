# PCB Re-layout: 200 × 140 mm, 8 Layers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the congested 140 × 100 mm 6-layer board with a 200 × 140 mm 8-layer board whose placement leaves enough room that the external router does the bulk of the work and every reference designator is readable.

**Architecture:** The board stays fully generated from `hardware/scripts/` — nothing is hand-edited in `mccan.kicad_pcb`. Placement keeps the region/flow model in `layout_pcb.py` and gains part-free routing channels plus enforced per-region fill budgets. The stackup goes to eight layers with three GND planes, one split power plane, and four routing layers. Hand routing is confined to the feed chain, the CAN pair and the boost switch node; KiCadRoutingTools takes the other ~121 signal nets, and `freeze_routes.py` folds its output back into the generator.

**Tech Stack:** Python 3 (no test framework — the gates *are* the tests), KiCad 10 CLI, KiCadRoutingTools v0.22.1 at `C:/Users/jimba/KiCadRoutingTools`.

**Spec:** `docs/superpowers/specs/2026-09-23-pcb-relayout-8layer-design.md`

---

## Global Constraints

Every task's requirements implicitly include these. Values are copied verbatim from the spec.

- **Outline 200 × 140 mm.** `X0, Y0 = 20.0, 20.0` and `X1, Y1 = 220.0, 160.0`. Four M3 holes 5 mm in from each corner, 3.2 mm drill on a 6.0 mm pad, 3 mm corner radius.
- **8 layers, 1 oz (35 µm) on all eight, 1.6 mm finished**, foil lamination, symmetric.
  `F.Cu` sig / `In1.Cu` GND / `In2.Cu` sig / `In3.Cu` GND / `In4.Cu` POWER split / `In5.Cu` sig / `In6.Cu` GND / `B.Cu` sig.
- **Minimum track and clearance 0.20 mm.** Minimum via **0.50 mm diameter / 0.25 mm drill with a 0.15 mm annular ring**. Through-hole vias only — no blind or buried.
- **Netclasses:** `FEED` 3.5 mm / 0.3 mm; `POWER` 2.0 mm / 0.3 mm; `CAN` 0.3 mm; `Default` 0.2 mm.
- **The feed is 7.0 A continuous, 7.8 A transient.** It is poured, never tracked. Any outer-layer run of more than a few millimetres is poured to **≥ 4.5 mm**. IPC-2221 wants **11.44 mm** of effective internal width at 1 oz for a 10 °C rise.
- **`GND_IN` and `GND` meet at exactly two places** — L2 winding B, and R3. Nothing in DRC enforces this; `check_grounds.py` does.
- **The board is generated, never hand-edited.** Every change goes into `hardware/scripts/`.
- **The schematic, netlist, BOM, part selection and firmware do not change.** No component is added, removed or substituted; no net changes name or connectivity.
- **Channel width 6.0 mm**, part-free, router-only.
- KiCad CLI is at `/c/Program Files/KiCad/10.0/bin/kicad-cli.exe`.

### Net names, exactly

`routes()` resolves a `ROUTES`/`ROUTE_VIAS` net name by exact match first, then by **last
path component** -- so `SW_BOOST` finds `/rails/SW_BOOST`. It **errors on an ambiguous or
missing name rather than guessing**, so a wrong name is loud. But a name that resolves to the
*wrong net of a similar pair* is silent, and this board has several such pairs. Use these:

| What you are routing | Write this | Which is | Parts on it |
|---|---|---|---|
| Feed, connector to eFuse | `FEED_P` | `/power_input/FEED_P` | J1 Q10 Q12 R104 R105 |
| eFuse mid-node | `MID` | `/power_input/MID` | Q10 Q11 R101 |
| eFuse sense | `SNS` | `/power_input/SNS` | Q11 R100 U10 |
| Feed, eFuse out | `VBAT_PROT` | `/power_input/VBAT_PROT` | C65 D2 L2 R100 R2 U10 |
| Feed, filter mid | `VBAT_F` | `/power_input/VBAT_F` | C1 L1 L2 R2 |
| The main rail | `VBAT` | `/VBAT` | C2 C3 C4 C12 C13 C18 C19 C45 C46 D3 L1 L3 R16 U2 U9 |
| Input-side ground | `GND_IN` | `/power_input/GND_IN` | C62-C65 D2 D21 D23 J1 L2 R3 U10 |
| CAN, connector side | `CANH` / `CANL` | `/CANH`, `/CANL` | **J8** D6 R26 L6 |
| CAN, transceiver side | `Net-(U6-CANH)` / `Net-(U6-CANL)` | *(write in full)* | L6 U6 |
| Boost switch node | `SW_BOOST` | `/rails/SW_BOOST` | D4 L3 U3 |
| Boost feedback | `FB_24V` | `/rails/FB_24V` | C61 R12 R13 U3 |
| Boost compensation | `Net-(U3-COMP)` | *(write in full)* | C24 R14 U3 |
| Boost soft-start | `Net-(U3-SS)` | *(write in full)* | C25 U3 |
| Boost output | `+24V` | `/+24V` | the rail, not the PROFET outputs |

**Two traps in that table.**

`CANH` is **not one net, it is two** -- `/CANH` from J8 through the ESD diode and the split
termination to the choke, and `Net-(U6-CANH)` from the choke to the transceiver. Route only
`/CANH` and half the pair is left unrouted, and DRC's unconnected count is the only thing
that will tell you.

`+24V` is the boost **rail**. The four PROFET outputs are `/outputs/+24V_FL`, `_FR`, `_RL`
and `_RR` -- separate nets that look like the same one. `rail_island("/+24V", ...)` in Task 5
correctly ignores them, and so would a short name, since their last components differ.
Written down because the netlist suggests otherwise at a glance.

**The connectors.** `J1` is power in. `J8` is CAN. `J7` is the Denali outputs. `J3`-`J6` are
the RGB outputs. **`J2` is the six-pin programming header and is _not_ an enclosure
penetration** (`enclosure.md` section 4) -- it is reached with the lid off, so it does not
belong in the board-edge gland row and its position is free. Board-edge order, left to right,
is **J1, J7, J8, J3, J4, J5, J6**.

### The commands you will run constantly

```bash
cd hardware

# regenerate the board without running any router (placement work)
AR_SKIP=1 python scripts/gen_pcb.py

# regenerate the board as it will ship (frozen router copper folded in)
python scripts/gen_pcb.py

# the gate suite
python scripts/check_courtyards.py
python scripts/check_density.py            # created in Task 3
python scripts/check_geometry.py
python scripts/check_vias.py
python scripts/check_grounds.py
MSYS_NO_PATHCONV=1 python scripts/check_plane_width.py mccan.kicad_pcb /VBAT

# DRC (must exit 0; unconnected nets are reported separately from errors)
"/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" pcb drc \
  --severity-error --schematic-parity --exit-code-violations \
  --refill-zones -o output/drc.rpt mccan.kicad_pcb
```

**`MSYS_NO_PATHCONV=1` on the plane-width gate is not decoration.** `/VBAT` is a net name,
but Git Bash cannot tell a net name from a POSIX path and rewrites any bare argument
starting with `/` into a Windows path before Python ever sees it. Without the prefix the
gate is handed `C:/Program Files/Git/VBAT` and fails with `no zone pours
C:/Program Files/Git/VBAT` -- which reads exactly like the VBAT plane having been lost,
and is not. It has already cost this project one false alarm during Task 8. With the
prefix the same board passes with 9.5x margin. The trap is the shell, not the board, and
it applies to every `/`-prefixed net name passed on a command line, not just this gate.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `hardware/archive/README.md` | what each retired board was, why, which tag holds its source | 1 |
| `hardware/archive/v1-4layer/`, `v2-6layer/` | snapshots of the two retired boards | 1 |
| `hardware/scripts/layout_pcb.py` | **the placement source of truth** — outline, regions, channels, budgets, hand placements, hand routes | 2, 3, 4, 7, 8, 9 |
| `hardware/scripts/check_density.py` | **new** — per-region courtyard fill against declared budgets | 3 |
| `hardware/scripts/gen_pcb.py` | board emission — layers, stackup, zones, silk, routing | 5, 6 |
| `hardware/scripts/gen_netclasses.py` | design rules into `mccan.kicad_pro` | 5 |
| `hardware/scripts/routes_signal.json` | frozen router copper | 2, 10 |
| `hardware/docs/*.md`, spec §9.1/§9.3/§10 | documentation amendments | 11 |
| `~/.claude/skills/pcb-layout-routing/` | the extracted method | 12 |

---

## Task 1: Archive the two retired boards

**Files:**
- Create: `hardware/archive/README.md`, `hardware/archive/v1-4layer/`, `hardware/archive/v2-6layer/`
- Commit: the entire current working tree, unchanged, before anything else happens

**Interfaces:**
- Consumes: nothing
- Produces: tags `board/v1-4layer` and `board/v2-6layer`; `hardware/archive/` as the place retired boards live

**Why first:** the working tree currently holds ~52,000 lines of uncommitted board work. Every later task destroys some of it. Nothing may be torn down until it is recoverable.

- [ ] **Step 1: Commit the in-flight work exactly as it stands**

Do not tidy it, do not regenerate it, do not run the gates on it. It is being committed to be preserved, not to be endorsed.

```bash
cd /d/projects/ESP32MCCAN
git add -A hardware/
git status --short        # confirm nothing outside hardware/ was picked up
git commit -m "hw(pcb): the six-layer board as it stood, before the re-layout

Committed unreviewed and unregenerated, purely so the 200x140 re-layout has
something to tag. This is the tip of the six-layer work: the four-layer routing
pass, the plane-width measurement, the hand-routed CAN pair and U3 escapes, and
the untracked helper scripts (check_courtyards, find_escape, show_room) and
PCBWay production package that were never committed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 2: Tag both retired boards**

`771f4cc` is the last commit before `da4efea` took the board from four layers to six, so it is the four-layer board's final state.

```bash
git tag -a board/v1-4layer 771f4cc -m "The 4-layer board: 140x100 mm, 1 oz outer / 2 oz inner.
Retired 2026-09-22 when two routing layers proved not to close the board -- the
external router settled at ~100 of 139 signal nets, failing one pad at a time
across forty nets."

git tag -a board/v2-6layer HEAD -m "The 6-layer board: 140x100 mm, 1 oz throughout.
Reached 0 DRC errors and 122 of 139 signal nets. Retired 2026-09-23: 12 reference
designators had no silkscreen at all, the input block sat at 76 % courtyard fill,
and hand-routing was doing work the router should have done. All density."

git tag -l 'board/*'
```

Expected output: `board/v1-4layer` and `board/v2-6layer`.

- [ ] **Step 3: Snapshot both boards into `hardware/archive/`**

```bash
cd /d/projects/ESP32MCCAN/hardware
mkdir -p archive/v1-4layer archive/v2-6layer

git show board/v1-4layer:hardware/mccan.kicad_pcb > archive/v1-4layer/mccan.kicad_pcb
git show board/v2-6layer:hardware/mccan.kicad_pcb > archive/v2-6layer/mccan.kicad_pcb

# DRC reports, if they were committed at those points
git show board/v1-4layer:hardware/output/drc.rpt > archive/v1-4layer/drc.rpt 2>/dev/null \
  || echo "no committed drc.rpt at board/v1-4layer -- note it in the README"
git show board/v2-6layer:hardware/output/drc.rpt > archive/v2-6layer/drc.rpt 2>/dev/null \
  || echo "no committed drc.rpt at board/v2-6layer -- note it in the README"

# the untracked production package now lives with the board that produced it
git mv pcbway_production archive/v2-6layer/pcbway_production

ls -R archive/
```

- [ ] **Step 4: Write `hardware/archive/README.md`**

```markdown
# Retired boards

Each board here was superseded, not abandoned. The directory holds the board file
itself so it can be opened without checking anything out; the **tag** holds the
`scripts/` state that produced it, which is the part that actually matters, because
nothing in this repo is hand-edited and a board file on its own cannot be regenerated.

| Board | Tag | Outline | Stackup | Retired |
|---|---|---|---|---|
| `v1-4layer` | `board/v1-4layer` | 140 × 100 mm | 4 layer, 1 oz outer / 2 oz inner | 2026-09-22 |
| `v2-6layer` | `board/v2-6layer` | 140 × 100 mm | 6 layer, 1 oz throughout | 2026-09-23 |

## v1-4layer

F.Cu signal / In1.Cu GND / In2.Cu VBAT / B.Cu bare for the gap pad.

**Why it was retired:** two routing layers did not close the board. The external
router settled at about 100 of 139 signal nets, and the failures were not clustered
— one pad here and one pad there across forty nets, which is what running out of
layer looks like rather than what a bad net order looks like.

## v2-6layer

F.Cu signal / In1.Cu GND / In2.Cu signal / In3.Cu VBAT / In4.Cu signal / B.Cu signal.

Reached **0 DRC errors, 0 schematic-parity issues, 122 of 139 signal nets routed**.
It is a working board and it is not a good one.

**Why it was retired:** density, expressed three ways.

1. **It cannot be read.** D10, D12, D13, D15, D16, D18, F4, L6, Q3, Q5, Q6 and Q8
   have no reference designator on the silkscreen — `silk_refs()` demoted them to
   F.Fab because there was nowhere legible to put them. Four more were shrunk.
2. **The signal side is congested.** The input block sat at **76 %** courtyard fill and
   the wire-exit field at 63 % -- and the outputs block, the one the comments in
   `layout_pcb.py` worried about, was by then the fourth worst at 37 %.
3. **Hand routing was doing the router's job.** Four commits went into nets carrying
   no electrical requirement, because the router had no room to work in.

It also carried a stackup defect: `B.Cu` is a signal layer whose only neighbour is
another signal layer, so bottom-side traces had no adjacent reference plane.

**Superseded by** `docs/superpowers/specs/2026-09-23-pcb-relayout-8layer-design.md`.

## Recovering one

```bash
git checkout board/v2-6layer -- hardware/scripts hardware/mccan.kicad_pro
cd hardware && python scripts/gen_pcb.py
```
```

If either `git show ... drc.rpt` failed in Step 3, add a line to that board's section saying the DRC report was not committed at the tag and can be regenerated from it.

- [ ] **Step 5: Commit**

```bash
cd /d/projects/ESP32MCCAN
git add hardware/archive
git commit -m "hw(pcb): archive the four- and six-layer boards

A tag holds the scripts that produced a board, which is the part that matters
since nothing here is hand-edited. The directory holds the board file itself, so
reading a retired board does not mean checking out a retired tree.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: Tear down the old copper

**Files:**
- Modify: `hardware/scripts/layout_pcb.py` — `ROUTES` (from line 604), `ROUTE_VIAS` (from line 1329), `FROZEN_DROP` (line 1438)
- Delete: `hardware/scripts/routes_signal.json`

**Interfaces:**
- Consumes: Task 1's tags
- Produces: a board that generates with placement, pours and vias but **no signal copper**

**Why:** every entry in `ROUTES` and `ROUTE_VIAS` names absolute board coordinates, and `routes_signal.json` names absolute coordinates *and* layer names. Task 3 moves every part and Task 5 renames `In4.Cu` from a signal layer to a power plane. All of it is invalid. Leaving it in place produces copper in mid-air on layers that no longer route.

- [ ] **Step 1: Empty `ROUTES`, leaving the reasoning pointer**

Replace the whole `ROUTES = [ ... ]` list (line 604 to just before `ROUTE_VIAS`) with:

```python
# Hand routes: (net, layer, width_mm, [(x, y), ...]).
#
# EMPTIED 2026-09-23 for the 200 x 140 re-layout.  Every entry named absolute board
# coordinates against a placement that no longer exists, so none of it could survive the
# move -- this is not a decision to hand-route less, it is the old copper being invalid.
#
# The six-layer board's routes are at tag `board/v2-6layer`, and they are worth reading
# before writing the new ones: the reasoning in their comments (why SW is 0.75 mm across
# two adjacent QFN pins, why the track stops at y 30.55 to clear U3's paddle, why the
# return half of the commutation loop is deliberately not routed) is about the circuit,
# not about the coordinates, and carries over unchanged.
#
# Refilled by Tasks 7-9: the feed chain, the CAN pair, the boost switch node.  Everything
# else on this board is the external router's -- see docs/routing-tool.md.
ROUTES = []
```

- [ ] **Step 2: Empty `ROUTE_VIAS` and `FROZEN_DROP`**

```python
# Hand vias: (net, x, y, diameter_mm, drill_mm).  Emptied with ROUTES -- see above.
ROUTE_VIAS = []
```

Read `FROZEN_DROP` at line 1438 first. It names specific frozen-route segments to drop; with `routes_signal.json` gone it has nothing to act on. Set it to an empty tuple and comment it the same way.

- [ ] **Step 3: Delete the frozen router copper**

```bash
cd /d/projects/ESP32MCCAN/hardware
git rm scripts/routes_signal.json
```

- [ ] **Step 4: Regenerate and confirm the board is placement-only**

```bash
AR_SKIP=1 python scripts/gen_pcb.py
```

Expected: it writes `mccan.kicad_pcb`, prints `autorouter: skipped (AR_SKIP) -- signal nets left unrouted`, and prints no `ERROR:` lines. The silk line will still report demotions — that is Task 6's problem, not this one.

- [ ] **Step 5: Confirm the gates still pass on a bare board**

```bash
python scripts/check_courtyards.py
python scripts/check_geometry.py
python scripts/check_grounds.py
```

Expected: all three pass. `check_geometry.py` in particular must be clean — with no routed copper there is nothing for it to object to, and if it complains here the complaint is about the pours or the vias and needs understanding before going further.

- [ ] **Step 6: Commit**

```bash
# routes_signal.json is NOT listed here: Step 3's `git rm` already staged its
# deletion, and `git add` validates every pathspec before staging any of them,
# so naming a path that no longer exists makes the whole command stage nothing.
git add scripts/layout_pcb.py mccan.kicad_pcb
git commit -m "hw(pcb): tear out the old copper, which the re-layout invalidates

Every hand route named absolute coordinates against a placement that is about to
change, and routes_signal.json named coordinates AND In4.Cu, which is about to stop
being a signal layer. None of it could have survived the move. The reasoning in the
old route comments is about the circuit rather than the coordinates and carries over;
it is at tag board/v2-6layer.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: `check_density.py`, validated against the old board

**Files:**
- Create: `hardware/scripts/check_density.py`

**Interfaces:**
- Consumes: `layout_pcb.REGIONS`, and `gen_pcb.extent()` / `gen_pcb.read_netlist()` / `gen_pcb.place()`
- Produces: `python scripts/check_density.py` — prints per-region fill, exits 1 if any region exceeds its declared budget. `layout_pcb.BUDGET` is a `dict[str, float]` of region name → maximum fill fraction; a region absent from it is unconstrained.

**Why this comes before the outline change:** the tool has to be run on the board it describes before anything moves, or a surprising number afterwards cannot be attributed. It also settles a question the comments cannot: `layout_pcb.py` records **59 %** for the outputs block, but that figure describes the *original* `102..131` region, which was widened to `95..131` in the same commit that wrote it. Nobody has measured the board since. Do not expect 59 %.

The measured truth, which Step 2 will reproduce:

| region | mm2 | fill |
|---|---|---|
| input | 1131 | **75.8 %** |
| wire | 3240 | 62.9 % |
| mcu | 575 | 53.7 % |
| outputs | 2556 | 37.3 % |
| efuse | 1560 | 36.7 % |
| rails | 1276 | 32.8 % |
| boost | 725 | 27.8 % |
| profet | 348 | 0.0 % |

**The congested region is `input`, not `outputs`** -- the left column holds L2 (a large
through-hole choke), D2, L1, D3, R2/R3 and C1-C5 in 1131 mm2. This is why Task 4 widens the
left column rather than simply scaling every region by the same factor.

- [ ] **Step 1: Write the check, in report-only mode first**

Create `hardware/scripts/check_density.py`:

```python
# -*- coding: utf-8 -*-
"""How full each placement region is, against the budget it declares.

Why this exists
---------------
A comment in layout_pcb.py records the outputs block at 59 % courtyard fill.  It was
written by hand, after the fact, about a region that was widened in the same commit --
so it was true of something for about a minute.  Measured, the block is at 37 %, and the
congested one is `input` at 76 %.  That is the whole argument for a gate: the number was
not wrong when it was written, it just stopped being about anything.  Density is the root cause behind most of
that board's problems (silk with nowhere to go, a router that could not find a
channel, hand-routing doing the router's job), so it is worth a gate rather than a
comment.

Fill is courtyard area over region area.  It is a blunt measure -- it does not know
that a tall part needs more room than a flat one, or that an escape needs room on one
particular side -- but the failure it catches is blunt too, and a blunt measure that
runs on every build beats a precise one that runs once.

    python scripts/check_density.py [--report]

--report prints the table and always exits 0, which is what you want while you are
still choosing the budgets.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gen_pcb as G          # noqa: E402
import layout_pcb as L       # noqa: E402


def main():
    report = "--report" in sys.argv

    comps, nets, padnet = G.read_netlist()
    comps = [c for c in comps if c["fp"] and G.load_fp(c["fp"]) is not None]
    pos, unplaced, _grid = G.place(comps)

    # Courtyard area per region.  A part counts against the region its courtyard CENTRE
    # falls in, so a part that straddles a boundary is charged to one region rather than
    # to neither.  Parts outside every region (the wire field's hand placements sit in
    # 'wire', but U5 hangs off the board edge) are charged to nothing and listed.
    area = dict((r, 0.0) for r in L.REGIONS)
    homeless = []
    for c in comps:
        if c["ref"] not in pos:
            continue
        x, y, rot = pos[c["ref"]]
        x0, y0, x1, y1 = G.box(c["fp"], x, y, rot)
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        a = (x1 - x0) * (y1 - y0)
        for r, (rx0, ry0, rx1, ry1) in L.REGIONS.items():
            if rx0 <= cx <= rx1 and ry0 <= cy <= ry1:
                area[r] += a
                break
        else:
            homeless.append(c["ref"])

    budget = getattr(L, "BUDGET", {})
    bad = []
    print("%-10s %9s %9s %7s %7s" % ("region", "region", "parts", "fill", "budget"))
    for r in sorted(L.REGIONS):
        rx0, ry0, rx1, ry1 = L.REGIONS[r]
        ra = (rx1 - rx0) * (ry1 - ry0)
        fill = area[r] / ra if ra else 0.0
        lim = budget.get(r)
        flag = ""
        if lim is not None and fill > lim:
            flag = "  OVER"
            bad.append((r, fill, lim))
        print("%-10s %8.0f %9.0f %6.1f%% %6s%s"
              % (r, ra, area[r], fill * 100.0,
                 ("%.0f%%" % (lim * 100.0)) if lim is not None else "-", flag))

    if homeless:
        print("outside every region: %s" % ", ".join(sorted(homeless)))
    if unplaced:
        print("UNPLACED: %s" % ", ".join(sorted(unplaced)))

    if report:
        return 0
    for r, fill, lim in bad:
        print("FAIL: region '%s' is %.1f%% full against a %.0f%% budget"
              % (r, fill * 100.0, lim * 100.0))
    if unplaced:
        print("FAIL: %d part(s) would not fit" % len(unplaced))
    return 1 if (bad or unplaced) else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it against the current 140 × 100 board**

```bash
cd /d/projects/ESP32MCCAN/hardware
python scripts/check_density.py --report
```

Expected: exit 0, `U5` listed as outside every region (it hangs off the board edge, which is
deliberate), and a table matching the one above to within a percent or so — `input` worst at
about **76 %**, `outputs` at about **37 %**.

If it is far off, stop and find out why before going further. The two likely causes are that
`G.box()` and `G.extent()` measure different things, or that parts are being charged to the
wrong region by the centre test. Fix the tool, not the number.

Record the whole table in the commit message — it is the "before" measurement, and Task 4's
"after" is only meaningful against it.

- [ ] **Step 3: Confirm it fails when it should**

Temporarily add to `layout_pcb.py`:

```python
BUDGET = {"input": 0.45}
```

0.45 is the budget `input` will really carry in Task 4, so this is not a throwaway value —
it is the real constraint, applied to a board that cannot yet meet it.

```bash
python scripts/check_density.py; echo "exit=$?"
```

Expected: `FAIL: region 'input' is 75.8% full against a 45% budget` and `exit=1`.

Leave `BUDGET` in place with that one entry. **Task 3 therefore ends with a failing gate, and
that is deliberate** — it is the red half of red/green, and Task 4 is what turns it green. Say
so in the commit message so nobody "fixes" it by raising the budget.

- [ ] **Step 4: Correct the spec, which repeats the stale figure**

The spec was written and approved before anyone measured, so it inherited the 59 % from the
same comment. Four places name it — §1 item 2, the table row "Outputs block fill | 59 % |
~25 %", §4's "the target that matters is outputs at ~25 %, down from 59 %", and §12's risk
row. All four say the congested region is `outputs`; measured, it is `input`.

Fix them to the measured table, and add a short note under §1 item 2 saying where the 59 %
came from and why it was not wrong when written. The re-layout's *justification* does not
change — the board is congested and unreadable either way — but which region gets the space
does, and that is a decision the spec should record correctly.

```bash
cd /d/projects/ESP32MCCAN
grep -n "59 %\|59%" docs/superpowers/specs/2026-09-23-pcb-relayout-8layer-design.md
```

Expected after editing: no hits.

- [ ] **Step 5: Commit**

```bash
cd /d/projects/ESP32MCCAN/hardware
git add scripts/check_density.py scripts/layout_pcb.py ../docs/superpowers/specs/2026-09-23-pcb-relayout-8layer-design.md
git commit -m "hw(pcb): measure region fill, and fail the build when it is too high

The 59 % recorded for the outputs block was written by hand about a region that was
widened in the same commit. Measured, that block is at 37 % and the congested one is
input at 76 % -- so the number was not wrong when written, it just stopped being about
anything. Density is the root cause behind the six-layer board's silk, routing and
hand-routing problems, and it needs a measurement rather than a comment.

Run before anything is re-proportioned, so the 'after' has an 'before' to mean
something against.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: The 200 × 140 outline, regions, channels and budgets

**Files:**
- Modify: `hardware/scripts/layout_pcb.py` — `X1`/`Y1` (line 60), `REGIONS` (line 79), `PLACE` (line 150), `NUDGE` (line 340), `GND_IN_ISLAND` (line 502), `D4_24V_ISLAND` (line 575), `TIM_PADS` (line 577), `NOTES` (line 391)
- Modify: `hardware/scripts/gen_pcb.py` — `place()` at line 696, to honour channels

**Interfaces:**
- Consumes: `check_density.py` from Task 3
- Produces: `layout_pcb.CHANNELS` — a `list[tuple[float,float,float,float]]` of `(x0, y0, x1, y1)` rectangles no part may enter; `layout_pcb.BUDGET` fully populated

**This is the largest task in the plan and the one the whole exercise exists for.** Expect to iterate Steps 4–7 several times.

- [ ] **Step 1: Change the outline**

In `layout_pcb.py`, at the `board outline` block near line 60:

```python
# ------------------------------------------------------------------ board outline
# 200 x 140 mm (2026-09-23).  Was 140 x 100.
#
# The area doubles, and that is the whole point: the six-layer board reached 0 DRC errors
# at 76 % courtyard fill in the input block, with 12 designators demoted off the
# silkscreen for want of anywhere to print them.  Every one of that board's complaints was
# density.  See docs/superpowers/specs/2026-09-23-pcb-relayout-8layer-design.md.
#
# It also clears a defect logged in docs/enclosure.md section 2 item 5: seven cable glands
# need about 143 mm of wall and would not fit a 140 mm one.  200 mm fits them comfortably.
#
# Thermally it is free -- better than free.  The heat-spreader plate is the base and tracks
# the board footprint, so it goes from ~137 cm2 (61 C at 40 C ambient, against a 65 C
# target) to ~280 cm2, against the 150 cm2 enclosure.md section 1 asks for.  Measured from
# Edge.Cuts: four straight sides and four 3 mm corner arcs, 200 x 140 mm less 0.08 cm2 of
# corner = 279.92 cm2, with NO antenna notch on this board -- the 140 x 100 outline's 3.1 cm2
# notch is not carried over, which is why this is 280 and not 277.  The plate stops
# being a design driver, which is why the thermal group no longer gets to veto placement.
X0, Y0 = 20.0, 20.0
X1, Y1 = 220.0, 160.0
```

`EDGE_R`, `MOUNT_INSET`, `MOUNT_DRILL` and `MOUNT_PAD` are unchanged. `mount_holes()` in `gen_pcb.py` derives from `X0/Y0/X1/Y1`, so the holes follow automatically.

- [ ] **Step 2: Write the new regions and channels**

Replace `REGIONS` with the block below, and add `CHANNELS` and `BUDGET` after it.

```python
# ------------------------------------------------------------------ regions and channels
# (x0, y0, x1, y1) in board coordinates.  Parts not named in PLACE are auto-flowed into
# their block's region on a courtyard-sized grid, largest first.
#
# The 200 x 140 map, laid out as four columns over a full-width wire-exit field, with a
# 6 mm CHANNEL between every pair of neighbours:
#
#     x:  23          70 76        117 123        181 187   217
#         +------------+ +---------+ +---------+ +-------+   y 23
#         |   input    | |  boost  | |         | |  mcu  |
#         |            | |         | |         | +-------+   y 60
#         +------------+ +---------+ |         |             y 70
#         ~~~~~~~~~~~~~~~~~~~~~~~~~~ | outputs |             y 70..76 channel
#         +------------+ +---------+ |         |             y 76
#         |   efuse    | |  rails  | |         |
#         |            | | profet  | |         |
#         +------------+ +---------+ +---------+             y 119
#         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~   y 119..125 channel
#         | wire-exit field, full width                  |   y 125
#         +----------------------------------------------+   y 156
#
# The left band still runs the 7 A feed in ONE direction only -- J1 at the bottom, up
# through the eFuse, up through L2 and the pi filter, out of the top of "input".  Nothing
# doubles back.
#
# THE LEFT COLUMN IS THE WIDE ONE, and that is the correction this map exists to make.  The
# comments on the old board worried about the outputs block, but measured, outputs was at
# 37 % and `input` was at **75.8 %** -- the worst region on the board by a wide margin.  It
# holds L2 (a large through-hole choke), D2, L1, D3, R2/R3 and C1-C5 in 1131 mm2.  Scaling
# every region by the same factor would have left it the worst region still, so the left
# column gets 47 x 47 mm against outputs' 58 x 96, and input lands at 38.8 %.
#
# Outputs was never the problem, so it is not given the lion's share: 5568 mm2 takes its
# ~105 auto-flowed parts to 17 %, which is as much room as its escapes can use.
REGIONS = {
    "input":   (23.0,   23.0,  70.0,  70.0),
    "efuse":   (23.0,   76.0,  70.0, 119.0),
    "boost":   (76.0,   23.0, 117.0,  70.0),
    "rails":   (76.0,   76.0, 117.0, 119.0),
    "profet":  (76.0,  104.0, 117.0, 119.0),   # nested inside rails; U9 is hand-placed
    "outputs": (123.0,  23.0, 181.0, 119.0),
    "mcu":     (187.0,  23.0, 217.0,  60.0),   # U5's antenna points off the x = 217 edge
    "wire":    (23.0,  125.0, 217.0, 156.0),
}

# Part-free lanes.  The packer may not enter one; the router may, and that is the entire
# point -- on the old board the space between regions was whatever the packer happened not
# to fill, which is not a routing budget anyone can reason about.
#
# At 0.20 mm track on a 0.40 mm pitch a 6 mm channel carries about 15 tracks per layer,
# 60 across the four signal layers.  3456 mm2 in total, about 12 % of the board.
CHANNELS = [
    (70.0,   23.0,  76.0, 119.0),    # input/efuse  |  boost/rails
    (117.0,  23.0, 123.0, 119.0),    # boost/rails  |  outputs
    (181.0,  23.0, 187.0, 119.0),    # outputs      |  mcu
    (23.0,   70.0, 117.0,  76.0),    # input/boost  |  efuse/rails
    (23.0,  119.0, 217.0, 125.0),    # everything   |  the wire-exit field
]

# Maximum courtyard fill per region, enforced by scripts/check_density.py.  A region absent
# here is unconstrained -- "wire" is, because every part in it is hand-placed against the
# gland row and a budget would only restate the placement.
#
# These are NOT set to whatever the first passing run produced: a budget that exactly matches
# reality fails the moment anyone adds a part.  Each is the measured figure with headroom.
#
#             measured  budget
#   input       38.8 %    45 %   <- the tight one, and the reason the left column got wider
#   efuse       28.3 %    35 %
#   boost       10.5 %    30 %
#   rails       23.7 %    30 %
#   outputs     17.1 %    25 %
#   mcu         27.8 %    35 %
BUDGET = {
    "input":   0.45,
    "efuse":   0.35,
    "boost":   0.30,
    "rails":   0.30,
    "outputs": 0.25,
    "mcu":     0.35,
}
```

- [ ] **Step 3: Teach the packer about channels**

In `gen_pcb.py`'s `place()` (line 696), immediately after the mounting-hole loop that seeds `hand` and marks the grid, add:

```python
    # Channels are part-free by construction: marking them on the grid is all it takes,
    # because the grid is what steers the auto-flow.  They are NOT added to `hand`, because
    # `hand` is the hand-placement overlap check and a channel is not a part -- a hand
    # placement that lands in a channel is a deliberate act and is caught by the explicit
    # test below instead, which names the channel.
    for i, (cx0, cy0, cx1, cy1) in enumerate(L.CHANNELS):
        grid.mark(cx0, cy0, cx1, cy1)
```

Then, inside the `for ref, (x, y, rot) in L.PLACE.items():` loop, after the existing off-board check, add:

```python
        for i, (cx0, cy0, cx1, cy1) in enumerate(L.CHANNELS):
            if bx0 < cx1 and cx0 < bx1 and by0 < cy1 and cy0 < by1:
                print("  ERROR: hand placement %s sits in channel %d (%.1f..%.1f x %.1f..%.1f)"
                      % (ref, i, cx0, cx1, cy0, cy1))
```

- [ ] **Step 4: Rescale the hand placements**

Every coordinate in `PLACE`, `NUDGE`, `GND_IN_ISLAND`, `D4_24V_ISLAND` and `TIM_PADS` was chosen against the old outline. They must all move.

Work region by region, not part by part. For each region, take its parts' old positions relative to the *old* region origin and re-lay them relative to the new one. The relationships that were chosen deliberately must survive:

- **The wire-exit row.** The gland penetrations run **J1, J7, J8, J3, J4, J5, J6** left to
  right (`enclosure.md` section 4), spanning ~123 mm on the old board. **J2 is not in that
  row** -- it is the programming header, reached with the lid off, and may go anywhere
  convenient; the old board parked it at the far right of the row and that is still fine. The
  row now has 194 mm to work with instead of 123 mm, so restore the 2.0 mm gaps used
  elsewhere on the board rather than the 1.2 mm the old row was squeezed to. These footprints
  put their **origin on pad 1, not on the centroid** -- the comment above `PLACE` explains
  this and it is still true.

- **The boost.** U3, L3, D4 and C61 keep their relative geometry exactly. D4 at 0.75 mm of track width across U3's pins 13 and 14 is a placement decision, and Task 9 depends on it.
- **The eFuse island.** U10, Q10, Q11, R100, C65, D2, R3 stay together; R100 keeps its `KEEPCLEAR` halo of 4.0 mm.
- **U5.** Still rotated so the antenna points off the `X1 = 220.0` edge; still in `OFFBOARD_OK`.
- **The thermal group** — L2, U9, L1, U3, L3 — stays on the plate edge, but per the spec it no longer gets to displace anything. L2 is still placed first as the largest single thermal term (0.78 W), the tallest part (~24 mm) and the only through-hole part on an SMD board.

- [ ] **Step 5: Regenerate**

```bash
cd /d/projects/ESP32MCCAN/hardware
AR_SKIP=1 python scripts/gen_pcb.py
```

Expected: no `ERROR:` lines, no `UNPLACED`, and few or no `NOTE: ... spilled out of` lines. A spill means a region is too small for its own parts — fix the region, not the spill.

- [ ] **Step 6: Run the density gate**

```bash
python scripts/check_density.py
```

Expected: exit 0 and every region inside its budget — `input` about **38.8 %** (against the
75.8 % it started at), `efuse` 28.3 %, `boost` 10.5 %, `rails` 23.7 %, `outputs` 17.1 %,
`mcu` 27.8 %. `wire` is unconstrained but should land near 34 %, down from 62.9 %.

If a region is over, the fix is to move the boundary, not to raise the budget. Raising a budget is only correct when the budget itself was wrong, and you should say so in the commit message when you do it.

- [ ] **Step 7: Run the placement gates**

```bash
python scripts/check_courtyards.py
python scripts/check_grounds.py
python scripts/check_geometry.py
```

Expected: all pass. `check_grounds.py` is the one to watch — `GND_IN_ISLAND` moved in Step 4, and it must still contain every `GND_IN` pad and no `GND` pad.

- [ ] **Step 8: Update the board's own notes text**

In `layout_pcb.py`'s `NOTES` (line 391), change the outline and the layer description to 200 × 140 mm and 8 layers. The stackup detail lands in Task 5; here just stop the text saying 140 × 100.

- [ ] **Step 9: Commit**

```bash
git add scripts/layout_pcb.py scripts/gen_pcb.py mccan.kicad_pcb
git commit -m "hw(pcb): 200 x 140 mm, with routing channels and enforced fill budgets

Doubling the area halves the fill on its own, but it does not change the packer --
it just gives it more room to pack the same way. So the region model gains two
things it never had: 6 mm part-free channels between neighbours, which is a routing
budget that can be reasoned about rather than whatever gaps the packer left, and a
declared fill budget per region that check_density.py fails the build over.

input, the worst region on the old board, goes 75.8 % -> 38.8 %; outputs 37.3 % -> 17.1 %;
the wire-exit field 62.9 % -> 33.9 %. The comment claiming outputs was at 59 % described a
region that had been widened in the same commit, which is why this task moves the left
column rather than the right.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: The 8-layer stackup

**Files:**
- Modify: `hardware/scripts/gen_pcb.py` — `LAYERS` (line 1030), `SIGNAL_LAYERS`/`PLANE_LAYERS` (lines 1067–1068), `STACKUP` (line 1113), `zones()` (line 1230), the `title_block` comment in `main()`
- Modify: `hardware/scripts/layout_pcb.py` — `NOTES`

**Interfaces:**
- Consumes: Task 4's placement
- Produces: `gen_pcb.SIGNAL_LAYERS = ("F.Cu", "In2.Cu", "In5.Cu", "B.Cu")`, `gen_pcb.PLANE_LAYERS = ("In1.Cu", "In3.Cu", "In4.Cu", "In6.Cu")`, and `gen_pcb.rail_island(net, comps, pos, padnet, halo=3.0) -> list[tuple[float, float]]`

`route_external.py` already passes `G.SIGNAL_LAYERS` to the router and `check_geometry.py` already grades against `PLANE_LAYERS`, so both follow automatically. Do not edit either.

- [ ] **Step 1: Replace `LAYERS`**

KiCad's fixed numbering is `F.Cu = 0`, `B.Cu = 2`, and `In1..In30 = 4, 6, 8, …`.

```python
LAYERS = """	(layers
		(0 "F.Cu" signal)
		(4 "In1.Cu" power "GND")
		(6 "In2.Cu" signal)
		(8 "In3.Cu" power "GND")
		(10 "In4.Cu" power "PWR")
		(12 "In5.Cu" signal)
		(14 "In6.Cu" power "GND")
		(2 "B.Cu" signal)
		(9 "F.Adhes" user "F.Adhesive")
		(11 "B.Adhes" user "B.Adhesive")
		(13 "F.Paste" user)
		(15 "B.Paste" user)
		(5 "F.SilkS" user "F.Silkscreen")
		(7 "B.SilkS" user "B.Silkscreen")
		(1 "F.Mask" user)
		(3 "B.Mask" user)
		(17 "Dwgs.User" user "User.Drawings")
		(19 "Cmts.User" user "User.Comments")
		(21 "Eco1.User" user "User.Eco1")
		(23 "Eco2.User" user "User.Eco2")
		(25 "Edge.Cuts" user)
		(27 "Margin" user)
		(31 "F.CrtYd" user "F.Courtyard")
		(29 "B.CrtYd" user "B.Courtyard")
		(35 "F.Fab" user)
		(33 "B.Fab" user)
	)"""
```

- [ ] **Step 2: Replace `SIGNAL_LAYERS`, `PLANE_LAYERS` and the stackup comment**

```python
SIGNAL_LAYERS = ("F.Cu", "In2.Cu", "In5.Cu", "B.Cu")
PLANE_LAYERS = ("In1.Cu", "In3.Cu", "In4.Cu", "In6.Cu")

# 8-layer, 1.6 mm, 1 oz throughout (2026-09-23).  Was six.
#
#   F.Cu   signal -- component escapes, short runs
#   In1.Cu GND, solid
#   In2.Cu signal -- the CAN pair lives here
#   In3.Cu GND, solid
#   In4.Cu POWER, split: VBAT | +24V | +5V | VLOGIC_IN
#   In5.Cu signal -- bulk routing
#   In6.Cu GND, solid
#   B.Cu   signal -- short runs, plate side
#
# Four routing layers, three ground planes, one power layer.
#
# WHAT THIS FIXES THAT SIX DID NOT.  The six-layer stack was
# F sig / GND / sig / VBAT / sig / B sig, in which B.Cu is a signal layer whose only
# neighbour is another signal layer.  Bottom-side traces had no adjacent reference plane and
# so no defined return path -- the B.Cu GND pour is on the SAME layer as those traces, which
# is not the same thing as a plane beneath them.  Here every signal layer has a solid GND
# plane on at least one face, and In2.Cu has one on both.
#
# WHY CAN GOES ON In2.Cu.  Between two solid planes it is a buried stripline, so "CAN
# segregated from the high-current and boost nets" is satisfied by construction rather than
# by a keep-away rule that nothing enforces -- the pair is physically enclosed in copper.  It
# is also off the two layers where the feed pours and the switch node live.
#
# WHY In4.Cu IS SPLIT, AND THE RISK.  VLOGIC_IN, +24V and +5V were POWER-class 2.0 mm
# tracks; as zones they cost no routing effort at all and carry far more than the 0.5 A the
# largest of them (the boost output) needs.  The cost is that VBAT no longer owns a whole
# layer.  check_plane_width.py measured the old VBAT pour's worst cut at 71 mm against the
# 11.44 mm IPC-2221 asks for 7.0 A at a 10 K rise on 1 oz internal copper -- a 6.1x margin --
# and sharing the layer three ways eats into that.  The margin is large but it is no longer
# free, so the check stops being a formality and becomes the thing that decides whether the
# split was affordable.  It runs on every build and it fails the board.
#
# Return paths under the split are sound: In5.Cu is the only signal layer adjacent to In4.Cu
# and it has solid In6.Cu GND on its other face.
#
# AR_LAYERS, further down, is a SUBSET of SIGNAL_LAYERS and deliberately so.  gen_pcb's own
# router carries a two-layer occupancy grid, so widening it is a rewrite of the grid rather
# than a change to a constant.  It is the fallback now that routes_signal.json exists, so it
# keeps the two layers it understands and the external router gets all four.
#
# DIELECTRICS.  Foil lamination: three cores (In1/In2, In3/In4, In5/In6) bonded by four
# prepregs, with F.Cu and B.Cu as foil outside.  Symmetric about the middle prepreg, which is
# what keeps the panel flat.  Copper 8 x 0.035 = 0.28; dielectric 1.2908; total 1.5708 mm,
# exactly as the six-layer stack summed to.  Sub-thicknesses are nominal -- the fab adjusts
# them to hit 1.6 mm.
#
#   F.Cu  --0.100 prepreg-- In1 --0.200 core-- In2 --0.2454 prepreg-- In3
#         --0.200 core-- In4 --0.2454 prepreg-- In5 --0.200 core-- In6
#         --0.100 prepreg-- B.Cu
#
# The 0.1 mm outer prepregs put F.Cu and B.Cu tight against their GND planes, which is what
# makes an outer-layer escape's return path short.
```

- [ ] **Step 3: Replace `STACKUP`'s layer list**

Keep everything from `(copper_finish "ENIG")` onward exactly as it is. Replace only the copper/dielectric sequence:

```
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "prepreg") (thickness 0.1) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In1.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 2" (type "core") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In2.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 3" (type "prepreg") (thickness 0.2454) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In3.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 4" (type "core") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In4.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 5" (type "prepreg") (thickness 0.2454) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In5.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 6" (type "core") (thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "In6.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 7" (type "prepreg") (thickness 0.1) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.035))
```

- [ ] **Step 4: Add `rail_island()` and rewrite `zones()`**

The three logic rails get islands on `In4.Cu`, and those islands are **computed from where their pads actually are**, not hand-drawn. Hand-drawn power splits are what went wrong on the six-layer board — the old `In3.Cu` comment records a vertical split at `x = 105` that put seven of eleven `+24V` pads on the wrong side of it.

Add above `zones()`:

```python
def rail_island(net, comps, pos, padnet, halo=3.0):
    """A rectangle on In4.Cu covering every pad of `net`, plus a halo.

    Computed rather than drawn.  The six-layer board's power plane was split down a
    hand-chosen vertical line, and the line was wrong in both directions -- seven of the
    eleven +24V pads were on the far side of it.  The two nets interleave across the whole
    board, so no straight line separates them and no cleverer line would have.  A bounding
    box around the pads that actually exist cannot be wrong that way: if the parts move, so
    does the island.
    """
    xs, ys = [], []
    for pd in pads_board(comps, pos, padnet):
        # pads_board's `net` field is a CODE, not a name -- comparing it against the net
        # name string can never match, and the island comes out empty, which silently
        # leaves VBAT filling all of In4.Cu unsplit.  Resolve through NETNAME.
        if NETNAME.get(pd[2]) != net:
            continue
        cx, cy, w, h = pd[3], pd[4], pd[5], pd[6]
        xs += [cx - w / 2.0, cx + w / 2.0]
        ys += [cy - h / 2.0, cy + h / 2.0]
    if not xs:
        print("  WARN: rail_island found no pads on %s" % net)
        return []
    x0, y0 = min(xs) - halo, min(ys) - halo
    x1, y1 = max(xs) + halo, max(ys) + halo
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
```

Then change `zones()`'s body. Its signature gains the placement it needs:

```python
def zones(netidx, comps, pos, padnet):
```

and its pour list becomes:

```python
    full = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    # Three solid ground planes.  In1 references F.Cu and In2; In3 references In2 and In4;
    # In6 references In5 and B.Cu.  Every signal layer is covered.
    out.append(zone("GND", ["In1.Cu"], full, "GND_IN1"))
    out.append(zone("GND", ["In3.Cu"], full, "GND_IN3"))
    out.append(zone("GND", ["In6.Cu"], full, "GND_IN6"))
    out.append(zone("GND", ["B.Cu"], full, "GND_BOT"))

    # In4.Cu, the power layer.  VBAT is the whole layer at priority 0; the three logic rails
    # are islands at priority 1, so KiCad fills THEM first and VBAT keeps clear around them.
    # That is why no partition has to be drawn: the carve-out is the fill rule, not geometry.
    out.append(zone("/VBAT", ["In4.Cu"], full, "VBAT_IN4", prio=0))
    for net, tag in (("/+24V", "24V_IN4"), ("/+5V", "5V_IN4"),
                     ("/VLOGIC_IN", "VLOGIC_IN4")):
        pts = rail_island(net, comps, pos, padnet)
        if pts:
            out.append(zone(net, ["In4.Cu"], pts, tag, prio=1))

    # D4's tab still needs somewhere for its thermal array to land on the bottom side.
    out.append(zone("/+24V", ["B.Cu"], L.D4_24V_ISLAND, "24V_D4", prio=2))
```

Keep the `GND_IN` F.Cu island exactly as it is — it is unchanged and `check_grounds.py` depends on it.

Update the call site — `gen_pcb.py:3419`, `out += zones(netidx)` — to
`out += zones(netidx, comps, pos, padnet)`. It is the only call.

`rail_island()` calls `pads_board()`, which is defined *below* `zones()` at line 1483. That
is fine: the name resolves when `zones()` actually runs, from `main()`, by which point the
whole module is loaded.

- [ ] **Step 5: Update the title block**

In `main()`, change comment 2 to:

```python
'\t\t(comment 2 "Board 200 x 140 mm, 8 layer, 1 oz copper on all layers")\n'
```

- [ ] **Step 6: Regenerate and check the layer count**

```bash
cd /d/projects/ESP32MCCAN/hardware
AR_SKIP=1 python scripts/gen_pcb.py
grep -c '(type "copper")' mccan.kicad_pcb
```

Expected: `8`.

- [ ] **Step 7: Measure the feed — this is the step that decides whether the split was affordable**

```bash
MSYS_NO_PATHCONV=1 python scripts/check_plane_width.py mccan.kicad_pcb /VBAT
```

Expected: PASS, with a worst cut comfortably above **11.44 mm**.

The old board measured 71 mm on a whole layer at 140 × 100. The new board is larger but `In4.Cu` now shares with three rails. If this comes back under 11.44 mm, do not widen the tolerance — the options in order of preference are: shrink the rail islands' halo from 3.0 mm; move a rail's consumers closer together so its island is smaller; or give `VBAT` its own layer again and put the rails back on `POWER`-class tracks. Say which you chose and why in the commit message.

- [ ] **Step 8: Run the full gate suite and DRC**

```bash
python scripts/check_geometry.py
python scripts/check_vias.py
python scripts/check_grounds.py
python scripts/check_courtyards.py
python scripts/check_density.py

"/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" pcb drc \
  --severity-error --schematic-parity --exit-code-violations \
  --refill-zones -o output/drc.rpt mccan.kicad_pcb
```

Expected: gates pass; DRC reports **0 errors and 0 schematic-parity issues**, with a large unconnected count (every signal net is unrouted at this point — that is Tasks 7–10).

- [ ] **Step 9: Commit**

```bash
git add scripts/gen_pcb.py scripts/layout_pcb.py mccan.kicad_pcb output/drc.rpt
git commit -m "hw(pcb): eight layers -- three ground planes and a split power layer

Fixes a defect the six-layer stack carried: B.Cu was a signal layer whose only
neighbour was another signal layer, so bottom-side traces had no adjacent reference
plane. A GND pour on the same layer is not a plane beneath them. Now every signal
layer has a solid GND plane on at least one face and In2.Cu has one on both, which
is where the CAN pair goes -- segregation by construction rather than by a rule
nothing enforces.

In4.Cu is split so the logic rails stop being 2.0 mm tracks. The islands are
computed from where their pads are, not drawn: the old board's hand-chosen vertical
split put seven of eleven +24V pads on the wrong side of the line. VBAT fills the
layer at priority 0 and the rails carve out of it at priority 1.

VBAT worst cut measured at <FILL IN> mm against the 11.44 mm IPC-2221 asks.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

Replace `<FILL IN>` with Step 7's actual figure before committing.

---

## Task 6: Silk demotion becomes a build failure

**Files:**
- Modify: `hardware/scripts/gen_pcb.py` — `silk_refs()` at line 402

**Interfaces:**
- Consumes: Task 4's placement
- Produces: `silk_refs()` raises `SystemExit` rather than demoting or shrinking

- [ ] **Step 1: Check where you actually stand first**

```bash
cd /d/projects/ESP32MCCAN/hardware
AR_SKIP=1 python scripts/gen_pcb.py 2>&1 | grep "silk references"
```

Record the line. On the old board it read `27 left alone, 22 moved, 4 shrunk, 12 demoted to F.Fab`. With twice the area it should already be `0 shrunk, 0 demoted` — if it is, Step 2 is a safety net rather than a repair, which is the good outcome. If it is not, Step 2 turns the remaining ones into a failure you then fix by moving parts.

- [ ] **Step 2: Remove both fallbacks**

In `silk_refs()`, delete the shrink block (the `if put is None:` that calls `_font_set`) and the demote block (the `if put is None:` that rewrites `lay[1]` to `F.Fab`). Replace both with a single collection, and end the function by failing:

```python
        if put is None:
            gone.append(ref)
            continue
        obstacles.append((ref,) + box_at(put[0], put[1]))
```

Delete the `small`/`shrunk` variables and their uses, then replace the closing `print`/`if gone:` with:

```python
    print("silk references: %d left alone, %d moved" % (kept, moved))
    if gone:
        raise SystemExit(
            "FAIL: %d reference designator(s) have nowhere legible to print:\n"
            "  %s\n"
            "This is a PLACEMENT failure, not a silkscreen one.  The old board answered it\n"
            "by shrinking the text and then demoting it to F.Fab, which left twelve parts\n"
            "unidentifiable on the bare board -- the opposite of what silkscreen is for.\n"
            "Give the part more room in scripts/layout_pcb.py, or nudge its neighbours."
            % (len(gone), ", ".join(gone)))
```

Update the docstring: the paragraph describing the shrink-then-demote ladder is now wrong. Say instead that each survivor is tried where the library put it and then at the four sides of its own body at increasing distance, and that failing to place one fails the build.

`SILK_REF_MIN_H` and `SILK_REF_MIN_T` become unused — delete them and their comments if nothing else references them. Check with `grep -n "SILK_REF_MIN" scripts/*.py` first.

- [ ] **Step 3: Regenerate**

```bash
AR_SKIP=1 python scripts/gen_pcb.py 2>&1 | grep "silk references"
```

Expected: `silk references: N left alone, M moved`, and the generator completes.

If it raises instead, it has named the parts. Move them or their neighbours in `layout_pcb.py` and repeat — that is the loop working as designed.

- [ ] **Step 4: Confirm DRC agrees there are no silk violations**

```bash
"/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" pcb drc \
  --severity-error --schematic-parity --exit-code-violations \
  --refill-zones -o output/drc.rpt mccan.kicad_pcb
grep -ci "silk" output/drc.rpt
```

Expected: `0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/gen_pcb.py mccan.kicad_pcb output/drc.rpt
git commit -m "hw(pcb): a designator with nowhere to go fails the build

silk_refs() used to try the library position, then four sides, then shrink to the
board minimum, then demote to F.Fab. That ladder turns a placement failure into a
board that cannot be read on the bench, silently -- twelve parts on the six-layer
board had no reference designator at all.

Both fallbacks are gone. If a designator cannot be printed legibly at full size next
to its own part, that is the placer's problem and the build stops. With twice the
area there is no honest reason for either.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 7: Hand-route the feed chain

**Files:**
- Modify: `hardware/scripts/layout_pcb.py` — `ROUTES`, `ROUTE_VIAS`

**Interfaces:**
- Consumes: Task 5's stackup
- Produces: `VBAT`, `VBAT_PROT`, `VBAT_F`, `FEED_P`, `MID`, `SNS`, `GND_IN` fully connected (all short names, all resolving uniquely -- see the Global Constraints table)

**The requirement:** 7.0 A continuous, 7.8 A transient of seconds. **Poured, never tracked.** The `FEED` netclass's 3.5 mm is a 20 °C-rise floor for hops of a few millimetres only; any real run is poured to **≥ 4.5 mm**. The bulk of the current is on the `In4.Cu` `VBAT` zone — what carries the feed is having a layer, not having thick copper.

- [ ] **Step 1: Find the room**

```bash
cd /d/projects/ESP32MCCAN/hardware
python scripts/show_room.py VBAT 23 23 70 125 --track F.Cu 4.5
python scripts/show_room.py FEED_P 23 60 70 125 --track F.Cu 4.5
```

`show_room.py` sweeps a grid and prints where a track of that width on that layer is legal against every obstacle at the clearance the rules actually apply. A corridor you can see is a corridor you can route. Use `find_escape.py` when a specific pad has no obvious way out.

- [ ] **Step 2: Write the routes**

`ROUTES` entries are `(net, layer, width_mm, [(x, y), ...])`; `ROUTE_VIAS` entries are `(net, x, y, diameter_mm, drill_mm)`.

The feed runs in one direction through the left band — J1 at the bottom of the wire field, up through the eFuse, up through L2 and the π filter, out of the top of `input`. Nothing doubles back. Each segment gets a comment saying *why* it is where it is and what it clears — the old routes at `board/v2-6layer` are the model for the level of detail expected.

Drop onto `In4.Cu` with `FEED` class vias (0.8 mm / 0.4 mm) wherever a run is longer than a few millimetres, rather than hauling it across the board on F.Cu. Use several vias in parallel where the full 7.0 A passes through — a 0.8/0.4 via is good for roughly 1–2 A, so a full-current transition wants at least four to six.

- [ ] **Step 3: Regenerate and check the geometry**

```bash
AR_SKIP=1 python scripts/gen_pcb.py
python scripts/check_geometry.py
python scripts/check_vias.py
```

`gen_pcb.py` runs `check_track_crossings()` internally after the ground drops are placed — watch its output for hand routes crossing something they should not.

- [ ] **Step 4: Confirm the feed nets are connected and the plane still carries it**

```bash
MSYS_NO_PATHCONV=1 python scripts/check_plane_width.py mccan.kicad_pcb /VBAT
"/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" pcb drc \
  --severity-error --schematic-parity --exit-code-violations \
  --refill-zones -o output/drc.rpt mccan.kicad_pcb
grep -n -A3 "\[unconnected_items\]" output/drc.rpt | grep -iE "VBAT|FEED_P|MID|SNS|GND_IN"
```

Expected: `check_plane_width.py` still passes; the grep returns nothing.

- [ ] **Step 5: Confirm the ground split survived**

```bash
python scripts/check_grounds.py
```

Expected: pass — `GND_IN` and `GND` meeting at exactly two places, L2 winding B and R3. This is the check that exists because a pour never shorts to a foreign net, so DRC will never tell you.

- [ ] **Step 6: Commit**

```bash
git add scripts/layout_pcb.py mccan.kicad_pcb output/drc.rpt
git commit -m "hw(pcb): the 7 A feed, poured through the left band

One direction only -- J1 up through the eFuse, up through L2 and the pi filter, out
of the top of input. Nothing doubles back. Poured rather than tracked: the FEED
class's 3.5 mm is a 20 K-rise floor for hops of a few mm, and every real run here is
>= 4.5 mm or is on the In4.Cu plane.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 8: Hand-route the CAN pair on In2.Cu

**Files:**
- Modify: `hardware/scripts/layout_pcb.py` — `ROUTES`, `ROUTE_VIAS`

**Interfaces:**
- Consumes: Task 7's copper
- Produces: all **four** CAN nets fully connected on `In2.Cu`, matched and evenly spaced -- `/CANH`, `/CANL`, `Net-(U6-CANH)`, `Net-(U6-CANL)`

**The requirement:** matched length, constant spacing, `CAN` netclass 0.3 mm, on `In2.Cu` between the `In1.Cu` and `In3.Cu` ground planes.

**The pair is four nets, not two.** The choke L6 breaks each side in half, and each half is its own net:

| Segment | CANH | CANL |
|---|---|---|
| J8 -> D6 (ESD) -> L6, with R26 a stub off it | `/CANH` | `/CANL` |
| L6 -> U6 (transceiver) | `Net-(U6-CANH)` | `Net-(U6-CANL)` |

Route all four. Routing only the first row leaves the transceiver unconnected, and nothing but DRC's unconnected count will say so.

**R26 is not a link in that chain.** `gen_mcu_can.py:341-350` wires it as a DNP
120R bus terminator shunted straight across the `CANH` and `CANL` labels --
`vpart("R26", "Device:R", "120R", ..., dnp=True)` between `lab("CANH", ...)` and
`lab("CANL", ...)` -- while `w(L6["4"], D6["1"])` and `w(L6["3"], D6["2"])` wire D6
directly to L6. So the continuous copper each net needs is D6<->L6, and R26's pads
are branch stubs off it. Earlier drafts of this task called the run a
`D6 -> R26 -> L6` chain; that was wrong, and routing it as a literal chain does not
close on one layer, because D6's and L6's pad pairs are oriented north/south while
R26's are west/east.

All four pads on each long net are **one net** (`/CANH` is J8.1 + D6.1 + R26.1 +
L6.4), so which of them the long haul from J8 lands on is a free choice: same-net
copper has no clearance rule against itself.

**On segregation.** The board-edge distance between the CAN connector and the power connector is **not** what separates them here -- J8 sits third in the gland row, 36.55 mm from J1 (measured, gland row: J1 30.85, J7 49.35, J8 67.40) (`enclosure.md` section 4 fixes that order and it is not a free variable). What separates them is the layer: the pair runs as a buried stripline on `In2.Cu`, enclosed by the `In1.Cu` and `In3.Cu` ground planes, while the feed pours on `In4.Cu` and `F.Cu` and the switch node is on `F.Cu`. There is a ground plane between the pair and every aggressor on this board.

**Measured pad geometry** (taken by the controller from `mccan.kicad_pcb` at `76a3984`, the last commit that touched the board --
use these, do not re-derive, and do not move any footprint):

| Net | Pads, absolute mm |
|---|---|
| `/CANH` | J8.1 (67.400, 130.590) - D6.1 (197.093, 31.350) - R26.1 (206.755, 43.330) - L6.4 (193.575, 31.300) |
| `/CANL` | J8.2 (72.000, 130.590) - D6.2 (197.093, 33.250) - R26.2 (208.405, 43.330) - L6.3 (193.575, 33.800) |
| `Net-(U6-CANH)` | L6.1 (189.025, 31.300) - U6.7 (213.275, 31.665) |
| `Net-(U6-CANL)` | L6.2 (189.025, 33.800) - U6.6 (213.275, 32.935) |

Board outline is x 20..220, y 20..160.

Two things follow that the rest of this brief does not say, and both are rulings -- implement
them, do not re-open them:

1. **The haul is long: about 163 mm from J8 to D6** (dx 130, dy 99), because J8 is in the gland
   row along the bottom edge and the transceiver cluster is in the top-right corner. That is
   the board being 200 x 140 mm rather than anything being wrong. Take it diagonally on
   `In2.Cu` if the corridor allows; `show_room.py` will show you what is already there.

2. **The cluster's physical order is not its electrical order.** West to east the parts sit
   L6 (189-194), D6 (197), R26 (207-208), U6 (213), while the copper runs D6 -> L6 -> U6.
   So the pair doubles back west and then east again inside about 24 mm, and the two pairs run
   alongside each other over that stretch. `Ruling: route it as placed. The doubling back costs
   roughly 50 mm on a 160 mm run, and CAN at this data rate over a run this short does not care;
   moving L6 would re-open a placement that Task 6 closed and re-flow its neighbours through
   the courtyard gutter, invalidating the silk and courtyard gates for no electrical gain.`
   The two pairs running side by side is not a coupling problem -- they are the same signal
   either side of the choke.

**Spacing is constant along the haul, not at the pads.** J8's own pitch is 4.6 mm, D6's is
1.9 mm and L6's is 2.5 mm, so the pair necks at each breakout by construction. Pick one
centre-to-centre gap, hold it for the length of the run, and let the last millimetre or two at
each end fan to the pad pitch.

**`In2.Cu` is completely empty** -- no segments and no zone, on the board at `76a3984`. The
whole layer is yours. Its only obstacles are the 509 via barrels that pass through it, and the
straight line from J8 to D6 is 160.9 mm with just **15 vias within 5 mm of that centreline**, so
the corridor is open. (Current copper lives on F.Cu 178 segments, In5.Cu 18, B.Cu 4; the pours
are on F.Cu, In1, In3, In4, In6 and B.Cu.)

- [ ] **Step 1: Route the pair**

The copper runs J8 -> D6 -> L6 -> U6, with the net changing name at L6, and R26's two
pads hanging off it as stubs. Drop to `In2.Cu` as soon as each leaves its pad — the whole point of this task is that the pair spends its length as a buried stripline, not on an outer layer.

Keep the two tracks at a constant centre-to-centre gap for their whole length, and turn them together: where one bends, the other bends at the same place. Match their lengths. Both are ordinary care rather than anything this board makes hard, because at 200 × 140 mm the pair has room to be routed deliberately.

- [ ] **Step 2: Regenerate and verify the pair is where you think it is**

```bash
cd /d/projects/ESP32MCCAN/hardware
AR_SKIP=1 python scripts/gen_pcb.py
python scripts/check_geometry.py
python - <<'EOF'
import io, re
t = io.open('mccan.kicad_pcb', encoding='utf-8').read()
# Segments name their net by CODE, not by name -- the names appear only in the
# (net N "name") declarations near the top, so the codes have to be looked up first.
code = dict((m.group(2), m.group(1))
            for m in re.finditer(r'\(net (\d+) "([^"]*)"\)', t))
for n in ('/CANH', '/CANL', 'Net-(U6-CANH)', 'Net-(U6-CANL)'):
    c = code.get(n)
    segs = re.findall(r'\(segment\s+\(start[^)]*\)\s+\(end[^)]*\)\s+\(width [\d.]+\)\s+'
                      r'\(layer "([^"]+)"\)[^(]*\(net %s\)' % c, t) if c else []
    print('%-16s code %-4s %2d segments  layers %s'
          % (n, c, len(segs), sorted(set(segs)) or '-'))
EOF
```

Expected: four non-zero counts, and `In2.Cu` throughout apart from the short escape at each
pad. For comparison, the same script on the six-layer board printed 11 segments each for
`/CANH` and `/CANL` across `F.Cu` and `In2.Cu`, and 4 each for the `Net-(U6-...)` halves on
`F.Cu` alone -- the transceiver side never reached the buried layer at all. `check_geometry.py` will fail if any track landed on a plane layer, which is the mistake to watch for here — `In3.Cu` is one keystroke away from `In2.Cu`.

- [ ] **Step 3: Measure the two lengths**

Sum the segment lengths for each net from your own `ROUTES` entries. Record both figures and their difference in the commit message.

There is no length-matching requirement to hit for CAN at this data rate over a run this short; the figure is recorded so that if anyone later changes the routing they can see what it used to be.

- [ ] **Step 4: DRC**

```bash
"/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" pcb drc \
  --severity-error --schematic-parity --exit-code-violations \
  --refill-zones -o output/drc.rpt mccan.kicad_pcb
grep -n -A3 "\[unconnected_items\]" output/drc.rpt | grep -iE "CANH|CANL"   # all four nets

python scripts/check_zone_islands.py   # parses the report DRC just wrote; must run after it
```

Expected: the grep returns nothing, and the zone-island gate exits 0 with
`OK: no zone is unconnected to itself`. Task 7 pinched a ground pour into two
disconnected islands with a hand route and DRC still reported 0 violations; this task
lays hand copper past the same pours, so the gate runs here too.

- [ ] **Step 5: Commit**

```bash
git add scripts/layout_pcb.py mccan.kicad_pcb output/drc.rpt
git commit -m "hw(pcb): CAN as a buried stripline on In2.Cu

Between the In1.Cu and In3.Cu ground planes, so segregation from the feed and the
switch node is structural -- the pair is physically enclosed in copper -- rather than
a keep-away rule nothing enforces. There is a ground plane between the
pair and every aggressor on the board, which matters more than connector spacing: J8 is
third in the gland row and 36.55 mm from J1, and that order is fixed by the enclosure.

Four nets, not two -- the choke splits each side, and Net-(U6-CANH/L) is the half that
reaches the transceiver.

CANH <A> mm, CANL <B> mm, delta <C> mm.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

Replace `<A>`, `<B>`, `<C>` with Step 3's figures.

---

## Task 9: Hand-route the boost switch node

**Files:**
- Modify: `hardware/scripts/layout_pcb.py` — `ROUTES`, `ROUTE_VIAS`

**Interfaces:**
- Consumes: Task 8's copper
- Produces: `SW_BOOST`, `+24V` at the boost, `PGND`, `Net-(U3-COMP)`, `FB_24V` and `Net-(U3-SS)` routed

**Net names** (from the Global Constraints table, repeated because getting one wrong here is
silent): the switch node is `SW_BOOST` (`/rails/SW_BOOST`, on D4 L3 U3); feedback is
**`FB_24V`**, not `FB` (`/rails/FB_24V`, on C61 R12 R13 U3); compensation and soft-start are
unnamed nets and must be written out in full as **`Net-(U3-COMP)`** (C24 R14 U3) and
**`Net-(U3-SS)`** (C25 U3).

**The requirement.** The LM51571-Q1 integrates its switch, so there are no gate loops and this is the only fast edge on the board. The boost is **non-synchronous**, so **D4** carries the commutation current and is inside the loop.

- **Minimise the loop** C20/C21/C22 → D4 → U3's `SW` pins → U3's internal FET → GND.
- **Do not route the return half.** `In1.Cu` is solid GND one 0.1 mm prepreg below `F.Cu`, so the return current mirrors the outbound path directly beneath it. That is a smaller loop than any trace could be, and adding a return trace makes it worse.
- **`Net-(U3-COMP)` is the highest-impedance node in the converter** — the error amplifier's output. Keep it and its network short and away from `SW`. A 35 mm compensation trace running beside the switch node is how a boost oscillates.
- **Take the `FB_24V` tap from the far end of the output capacitor**, not from the switch-node end.

**Measured geometry** (taken by the controller from `mccan.kicad_pcb` at `f1fcd93` --
use these, do not re-derive, and do not move any footprint). All pads are F.Cu SMD;
`x a..b` is the pad's actual extent, not its centre:

| Pad | Net | x | y |
|---|---|---|---|
| U3.12 | `SW_BOOST` | 87.037..87.875 | 31.125..31.375 |
| U3.13 | `SW_BOOST` | 86.625..86.875 | 30.125..30.962 |
| U3.14 | `SW_BOOST` | 86.125..86.375 | 30.125..30.962 |
| U3.15 | NC | 85.625..85.875 | 30.125..30.962 |
| U3.11 | MODE | 87.037..87.875 | 31.625..31.875 |
| U3.17 | GND paddle | 85.162..86.838 | 31.163..32.837 |
| U3.8 | `Net-(U3-COMP)` | 86.625..86.875 | 33.037..33.875 |
| U3.9 | `FB_24V` | 87.037..87.875 | 32.625..32.875 |
| U3.10 | `Net-(U3-SS)` | 87.037..87.875 | 32.125..32.375 |
| D4.2 (anode) | `SW_BOOST` | 85.560..86.960 | 27.730..29.000 |
| D4.1 | `+24V` | 87.640..89.040 | 27.730..29.000 |
| D4.3 (tab) | `+24V` | 84.900..89.700 | 22.200..26.920 |
| L3.2 | `SW_BOOST` | 91.325..92.305 | 26.900..30.300 |
| C20.1 / C21.1 / C22.1 | `+24V` | 82.800..83.950 | 22.700..24.500 / 25.100..26.900 / 27.500..29.300 |
| C24.1 | `Net-(U3-COMP)` | 88.100..89.000 | 34.550..35.500 |
| R14.1 | `Net-(U3-COMP)` | 86.425..87.225 | 34.925..35.875 |
| C25.1 | `Net-(U3-SS)` | 88.075..88.975 | 38.525..39.475 |
| R12.2 / C61.2 / R13.1 | `FB_24V` | 89.775..90.675 | 31.725..32.675 / 33.525..34.475 / 35.325..36.275 |
| R12.1 / C61.1 | `+24V` | 91.325..92.225 | 31.725..32.675 / 33.525..34.475 |

Four numbers fall out of that table, and they are the same relationships the six-layer
board reasoned to — the block was re-placed, not redesigned:

- **The SW column is 0.75 mm centred at x 86.5**, spanning 86.125..86.875: exactly the
  outer edges of pins 13 and 14 together, clearing pin 15 (NC, right edge 85.875) by
  **0.25 mm**. D4.2 spans x 85.560..86.960, so the same column runs straight up into it
  **with no bend** — that is what D4's placement is for.
- **It must stop at y 30.55 or above.** U3's GND paddle starts at y 31.163 and a 0.75 mm
  track's end cap reaches 0.375 mm past its endpoint, so the endpoint may not exceed
  y 30.588 at 0.20 mm clearance. At 30.55 the copper ends at 30.925, clearing the paddle
  by 0.238 mm while still covering pins 13/14 over 0.80 of their 0.837 mm length.
- **L3 joins along y 29.70 at 0.75 mm**, spanning 29.325..30.075, which clears D4.1
  (a foreign net, `+24V`, bottom edge y 29.000) by **0.325 mm** and stays above U3's
  top-edge pads (y 30.125).
- **Pin 12 gets a 0.30 mm tie, not a share of the current.** Centred on its own y 31.250
  the copper reaches 31.400 and clears pin 11 (MODE, top edge 31.625) by **0.225 mm**.
  0.34 mm is in fact the widest that still clears it, at 0.205 mm; 0.30 mm is the
  prescription anyway, because it carries 0.025 mm of margin against the 0.20 mm floor
  where 0.34 carries 0.005 mm, and 0.35 mm misses by a floating-point last bit
  (31.625 - 31.425 computes as 0.19999999999999929, just under the floor).

**What is already in that window**, and this is the part Task 8 learned the hard way —
`gen_pcb.py` checks hand copper against pads *and vias*, and refuses to write the board
when anything is short:

- **`/+24V` already has a `B.Cu` pour**, and D4.3's tab carries a **5 x 5 grid of 25
  thermal vias** at 0.55/0.25 covering x 85.325..89.275, y 22.625..26.495. So `+24V`
  leaves the boost downward, not along `F.Cu`. C20/C21/C22's `+24V` pads have **no vias**
  — the `F.Cu` column and rung this task lays are their only connection to anything.
- U3.17's paddle carries four GND thermal vias at (85.588 / 86.412, 31.587 / 32.413).
- **A GND via at (86.250, 34.225)**, 0.60/0.30, fed by a 0.25 mm segment from U3.7. Its
  right edge is x 86.525. A `COMP` track leaving pin 8 straight down the pin's own centre
  (x 86.750, 0.25 mm wide, left edge 86.625) clears it by **0.10 mm and fails**. R14.1
  spans x 86.425..87.225, so entering nearer x 87.0 clears by 0.35 mm.
- Other GND drops already placed nearby: (85.250, 29.775), (83.775, 31.250),
  (86.775, 36.375), (87.725, 36.575), (85.175, 39.825), (90.075, 39.825),
  (91.825, 36.625), plus GND stitching at (91.000, 23.000), (94.000, 23.000),
  (92.359, 22.000) and a 3 mm perimeter grid from y 35 down.
- `/VBAT` risers already exist at (94.185, 28.600) and (81.175, 32.400), both 0.80/0.40.

`Ruling: the FB_24V tap reads through the +24V pour, not along F.Cu.` D4.3's 25 vias put
`+24V` on `B.Cu` immediately, and R12.1/C61.1 sit 8 mm east of the output caps with U3 in
between; an `F.Cu` haul from C20.1 round to R12.1 would be long, would run beside `SW`,
and would carry no current worth the copper. Drop R12.1/C61.1 to the pour instead. The
"far end of the output capacitor" requirement survives it: the sense point is downstream
of the caps either way, which is what the rule is protecting. Cost if wrong: the divider
sees the pour's IR drop rather than the cap's terminal, worth single-digit millivolts on
a 24 V rail.

- [ ] **Step 1: Re-read how the old board did it**

```bash
cd /d/projects/ESP32MCCAN
git show board/v2-6layer:hardware/scripts/layout_pcb.py | sed -n '604,660p'
```

The coordinates are dead; the reasoning is not. Note specifically: `SW` carried at 0.75 mm across U3's pins 13 and 14 together, because you cannot bring 0.75 mm into a single pin of a 0.5 mm-pitch QFN but you can bring it into two adjacent pins of the same net; the track stopping short of U3's exposed paddle by an explicit margin; and pin 12 getting a 0.3 mm tie rather than a share of the current because its neighbour is `MODE`.

- [ ] **Step 2: Route it**

Work outward from the loop: `SW` first, then `+24V` from the output caps to D4's cathode tab, then `PGND`, then the `VBAT` feed into the boost (up out of the `In4.Cu` plane rather than along the board), then `Net-(U3-COMP)`, `FB_24V` and `Net-(U3-SS)`.

Comment every segment with what it clears and by how much. This is the part of the board where a 0.1 mm mistake is a bench problem rather than a DRC problem.

- [ ] **Step 3: Regenerate and check**

```bash
cd /d/projects/ESP32MCCAN/hardware
AR_SKIP=1 python scripts/gen_pcb.py
python scripts/check_geometry.py
python scripts/check_vias.py
```

Watch `check_track_crossings()`'s output in the generator log.

- [ ] **Step 4: Measure the loop**

Compute the enclosed area of the C20/C21/C22 → D4 → U3 `SW` → paddle loop from your own coordinates, and record it in the commit message. There is no threshold to hit; the number exists so that a later change can be compared against it rather than argued about.

- [ ] **Step 5: Full gate suite and DRC**

```bash
python scripts/check_courtyards.py
python scripts/check_density.py
python scripts/check_geometry.py
python scripts/check_vias.py
python scripts/check_grounds.py
MSYS_NO_PATHCONV=1 python scripts/check_plane_width.py mccan.kicad_pcb /VBAT

"/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" pcb drc \
  --severity-error --schematic-parity --exit-code-violations \
  --refill-zones -o output/drc.rpt mccan.kicad_pcb

python scripts/check_zone_islands.py   # parses the report DRC just wrote; must run after it
```

Expected: all gates pass, DRC 0 errors, 0 parity issues. Unconnected is still large — the router has not run.

- [ ] **Step 6: Commit**

```bash
git add scripts/layout_pcb.py mccan.kicad_pcb output/drc.rpt
git commit -m "hw(pcb): the boost switch node, by hand and tight

The LM51571 integrates its switch, so there are no gate loops and this is the only
fast edge on the board; the boost is non-synchronous, so D4 is inside the
commutation loop. Loop area is a geometric property no router optimises for -- it
will hand back an electrically correct switch node that rings, and the failure shows
up on the bench rather than in any gate. Hence by hand.

The return half is deliberately not routed: In1.Cu is solid GND one 0.1 mm prepreg
below F.Cu, so the return mirrors the outbound path beneath it, which is smaller than
any trace. COMP and FB_24V are kept off SW; FB_24V taps the far end of the output cap.

Loop area <FILL IN> mm2.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 10: Run the external router and freeze its copper

**Files:**
- Create: `hardware/scripts/routes_signal.json` (regenerated, not written by hand)
- Modify: `hardware/mccan.kicad_pcb`

**Interfaces:**
- Consumes: Tasks 7–9's hand routes
- Produces: a board with all or nearly all of ~139 signal nets routed

**The traps, restated because they have cost this project real time:**

- `--fab-tier standard` is **not** the size floor. `--escalation` is, and its default is `fab`, documented as "down to the fab tier floor, below the board's own minimums". A run once returned **2177 tracks at 0.0889 mm** against a 0.25 mm request and exited 0 with every one of the tool's own graders content. Always `--escalation board`.
- The BGA machinery is a **fine-pitch-grid detector** and fires on TSSOP and QFN. It read a TSSOP-28 as a 14 × 2 ball grid and ran an under-pad shrink rescue at 0.0762 mm. Always `--no-bga-zones`.
- `--strict-sizes` is deliberately **not** used: it exits 3 on any descent, including the 0.25 → 0.20 mm necking that is ordinary layout.
- **Never let the tool grade itself.** `check_geometry.py` runs first and decides whether the copper is admitted.

- [ ] **Step 1: Emit the unrouted board for the router**

```bash
cd /d/projects/ESP32MCCAN/hardware
AR_SKIP=1 PCB_OUT=output/router/unrouted.kicad_pcb python scripts/gen_pcb.py
```

This board carries everything decided by hand — the pours, the thermal and stitching vias, the ground drops, and Tasks 7–9's routes — and is missing only the part being handed over.

- [ ] **Step 2: Route**

```bash
python scripts/route_external.py
```

It passes `--fab-tier standard --escalation board --no-bga-zones --keep-input-copper --json-out` and `--layers` from `gen_pcb.SIGNAL_LAYERS`, which Task 5 set to the four signal layers. No change is needed to this script.

Expect a long run. Record how many nets it closed.

- [ ] **Step 3: Grade the output before admitting it**

```bash
python scripts/check_geometry.py output/router/routed.kicad_pcb
```

It fails on copper under the board's own `rules.min_*`, on a track on a plane layer, and on zero-length junk; it only *reports* legal necking.

If it fails, the copper does not go in. Fix the invocation or the board and re-run — do not relax the check.

- [ ] **Step 4: Freeze**

```bash
python scripts/freeze_routes.py
```

It diffs `routed.kicad_pcb` against `unrouted.kicad_pcb` and writes what the router **added** to `scripts/routes_signal.json`. It is a diff, not a net filter — the input board carries hand routes sitting on signal nets, and a filter would emit them twice. It also drops segments under a tenth of the routing grid, which is how the 10 µm nubs that block a freeze get removed.

- [ ] **Step 5: Regenerate the real board and run everything**

```bash
python scripts/gen_pcb.py

python scripts/check_courtyards.py
python scripts/check_density.py
python scripts/check_geometry.py
python scripts/check_vias.py
python scripts/check_grounds.py
MSYS_NO_PATHCONV=1 python scripts/check_plane_width.py mccan.kicad_pcb /VBAT

"/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" pcb drc \
  --severity-error --schematic-parity --exit-code-violations \
  --refill-zones -o output/drc.rpt mccan.kicad_pcb

python scripts/check_zone_islands.py   # parses the report DRC just wrote; must run after it
```

Expected: every gate passes, DRC 0 errors and 0 parity issues, and **unconnected dramatically
lower than the 72 the six-layer board finished at** (`hardware/docs/routing-tool.md` s5.2).
Do not use 105 as the bar -- that is the earlier TWO-signal-layer column of the same table,
and the six-layer board already beat it. Note also that 51 of those 72 are nets the router is
never given (FEED, POWER and CAN are in `AR_SKIP_CLASSES`), so the router-attributable figure
to beat is 21, and the rest close by hand in Step 6.

- [ ] **Step 6: Close whatever is left, by hand**

If nets remain unconnected, add them to `ROUTES` the way Tasks 7–9 did, using `show_room.py` and `find_escape.py` to find the corridor. Re-run Step 5 after each batch.

If the shortfall is large rather than a handful, the router's hints name the nets blocking it — and those are usually nets it committed earlier in the same run. `--rip-existing-nets` on that named list is the lever, and it has never been tried. `hardware/docs/routing-tool.md` records why an earlier rip-up experiment was not the lever, which is worth reading before assuming it is.

- [ ] **Step 7: Commit**

```bash
git add scripts/routes_signal.json scripts/layout_pcb.py mccan.kicad_pcb output/drc.rpt
git commit -m "hw(pcb): the router's copper, on four layers with room to use them

<N> of 139 signal nets, against 122 on the six-layer board. Graded by
check_geometry.py before a single segment was admitted -- the tool will go below the
sizes you give it and exit 0, so its own graders being content means nothing.

DRC: 0 errors, 0 schematic parity, <M> unconnected.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 11: Fabrication outputs and documentation

**Files:**
- Modify: `docs/superpowers/specs/2026-09-11-esp32-mccan-pcb-hardware-design.md` §9.1, §9.3, §10
- Modify: `hardware/docs/enclosure.md`, `hardware/docs/routing-tool.md`, `hardware/docs/fabrication.md`
- Modify: `docs/superpowers/plans/2026-09-11-esp32-mccan-pcb-hardware.md` Tasks 8 and 9
- Create: `hardware/output/` gerbers, drill, BOM, CPL

**Interfaces:**
- Consumes: Task 10's routed board
- Produces: a fabrication package, and documentation that matches the board

**About the line numbers in this brief.** Every `file.md:N` citation into a document was
resolved against the file and lands on the text it claims — I checked them one by one. Every
citation into `hardware/scripts/gen_pcb.py` or `hardware/scripts/layout_pcb.py` is
**approximate**, because Task 10 Step 6 was still adding `ROUTES` entries and `ROUTE_VIAS` to
those two files when this brief was written, and inserting lines moves everything below them.
Fourteen of the citations here are into those two files. When one does not land on what this
brief says it says, the line moved — `grep` for the quoted text, which is stable, and do not
conclude the brief is describing something that is not there. Do not "fix" a citation by
editing the source to match it.

- [ ] **Step 1: Amend spec §10**

Replace the stackup paragraph and table with the 8-layer arrangement, keeping the existing revision-note style — the section already carries its own history and the new note should say what changed and why, not overwrite the old reasoning. State: 8 layers, 1 oz throughout, the layer roles, that every signal layer is plane-referenced, and that CAN is a stripline on `In2.Cu`.

**The plan's next clause — "that `In4.Cu` is split with `check_plane_width.py` as the gate" —
is false in both halves, and this brief supersedes it.** Task 5 implemented the split and then
reversed it: the per-net islands were bounding boxes, and on a board where a net's pads span the
width, a bounding box encloses foreign pads rather than isolating a net. `In4.Cu` is a **solid
`/VBAT` plane**. And `check_plane_width.py` is not the gate spec §3.2 named, because a check that
rasterises a zone outline and subtracts via barrels cannot see a neighbouring zone on the same
layer — it now refuses to measure a layer the plane shares rather than printing a number it
cannot stand behind. Write the section to match the board: solid `/VBAT` on `In4.Cu`, with a
revision note recording that §3.2's split was tried and abandoned and why. **Do not transcribe a figure for this — measure it.** The worst cut moves every time a via is
punched through the plane, so every number written down for it has a shelf life: the ledger's
is a Task 5 figure taken before the router placed a via, `49b482b` measured 105.30 mm at
x = 106.0 over 1426 holes, and `26969e1` measures **104.90 mm at x = 97.3, 9.2× the 1 oz
IPC-2221 requirement** over 1449 holes. All three were right when taken. Run the checker on
the board you are documenting and quote what it prints:

```bash
python scripts/check_plane_width.py
```

**Mind the argument order.** `sys.argv[1]` is the **board path** and `sys.argv[2]` is the net,
which defaults to `/VBAT`. So `check_plane_width.py /VBAT` reads `/VBAT` as a filename and prints
`FAIL: /VBAT is missing` — a message that reads like a missing plane and is nothing of the kind.
The bare form above is correct; to name the net explicitly it is
`python scripts/check_plane_width.py mccan.kicad_pcb /VBAT`.

**The same correction is needed in three places in this plan's own spec**,
`docs/superpowers/specs/2026-09-23-pcb-relayout-8layer-design.md`, and none of them is in any
other step's scope. Do them in this commit:

- **§3.2 "Why the power layer is split, and the risk that creates"** (lines 108-124) is the
  section that argued for the split. It quotes "**71 mm**" worst cut and a "**6.1×** margin",
  and closes "This is accepted because the gate already exists … No arithmetic argument is
  being relied on." Every load-bearing sentence in it is now superseded. Rewrite it the way
  Step 1 rewrites the old spec's §10 — as a section that records the split was tried, why it
  could not work (a per-net bounding box is not an island once that net's pads span the board),
  and what the board does instead. Keep the section number and keep its reasoning visible; a
  rejected approach with its reason is worth more than a deleted one. Its last paragraph, on
  return paths under `In5.Cu`, is **still correct** and survives unchanged.
- **§7's gates table** has a `check_plane_width.py` row reading "the feed's effective poured
  width … **Load-bearing now** — see §3.2". It is not load-bearing in that sense any more.
  While you are in that table: it does not list **`check_zone_islands.py`**, which was added
  later on this branch and catches a zone that filled as two disconnected islands — legal
  copper on the right net, invisible to every other check here. Add a row for it.
- **§12's risk table**, first row: "The split power plane starves the `VBAT` feed |
  `check_plane_width.py` measures it and fails the build (§3.2). Current margin is 6.1×".
  Both the risk and the figure are stale.

Use the same measured figure in all of them, and take it from one re-run of the checker rather
than copying it between sections — four copies of a number is four chances for three of them to
rot.

**And the figure itself is restated in nine more places, five of them in source comments.**
`71 mm` / `6.1×` was measured on the six-layer board's `In3.Cu`. Run

```bash
grep -rnE "6\.1 ?[x×]|71 ?mm" --include=*.md --include=*.py docs hardware
```

and work every hit. They fall into three groups:

- **Correct them** — these describe the board as it is now:
  `hardware/docs/fabrication.md:92-93`, `hardware/docs/routing-tool.md:75`,
  `hardware/scripts/gen_netclasses.py:38` and `:103`, `hardware/scripts/gen_pcb.py:1085-1086`,
  `hardware/scripts/layout_pcb.py:439`. The five in `.py` files are **comments asserting a
  measurement the artifact no longer produces** — the exact defect class this branch has caught
  twenty-four of, and the reason this step exists. Scripts must regenerate byte-identical after
  a comment-only edit.
- **Leave them** — `docs/superpowers/plans/2026-09-11-esp32-mccan-pcb-hardware.md:186` and
  `:1100` are a historical plan describing the board that was built. Step 6 marks its Tasks 8
  and 9 superseded; do not rewrite its body.
- **Already covered** — `docs/superpowers/specs/2026-09-11-...-design.md:1502` and `:1509` are
  inside the §10 block this step rewrites.

`fabrication.md:89` and `:92` also still name **`In3.Cu`** as the feed pour. On this board it is
**`In4.Cu`**. Fix the layer name with the figure; a right number against a wrong layer is not a
correction.

**Re-measure after the router, not before.** `routing-tool.md:70-73` makes the point itself:
`check_plane_width.py` is the one gate whose answer the router can make *worse*, because every
via it places punches another antipad through the plane. Task 10 has run by the time you read
this, so the ledger's Task 5 figure is an input-board figure. The two differ: 106.50 mm and 9.3×
before the router, **105.30 mm and 9.2× after it**. Both pass with room to spare, but only the
second is a measurement of the board being fabricated. Run the checker yourself and use what it
prints.

**The feed plane also changed layers, and that is a separate sweep.** On the six-layer board
`In3.Cu` was the `VBAT` feed. On this board **`In3.Cu` is solid GND and the feed is `In4.Cu`**.
So every sentence naming `In3.Cu` has to be read twice: as GND it is correct and stays, as the
feed or the power plane it is wrong. Run

```bash
grep -rn "In3.Cu" --include=*.md --include=*.py docs hardware
```

and split the hits. **Wrong — `In3.Cu` used as the feed or power plane:**
`hardware/docs/fabrication.md:63`, `:89`, `:153`, `:350`; `hardware/docs/routing-tool.md:113`
("In1.Cu is the ground plane and In3.Cu is the VBAT plane"); `hardware/scripts/gen_netclasses.py:37`;
`hardware/scripts/gen_pcb.py:930` and `:1373`; `hardware/scripts/layout_pcb.py:438` and `:450`.
**Right — `In3.Cu` as GND, leave alone:** the stackup and zone code in `gen_pcb.py`
(`:1014`, `:1050`, `:1057`, `:1120`, `:1234`, `:1302`), `check_geometry.py:28`,
`route_external.py:35`, `layout_pcb.py:369`.

This matters more than a figure does. A comment that names the wrong layer for the 7 A feed is
the kind a future reader acts on.

- [ ] **Step 2: Amend spec §9.1 and §9.3**

§9.1: the panel now has a 200 mm wall, which resolves the seven-gland problem. §9.3: the enclosure needs a box for 200 × 140 mm plus the service loop, and the part number is still unchosen.

Four things about these two sections that the step above does not say:

**Compute the gland row, do not assert it.** §9.1's ASCII panel sketch draws the seven glands in
**two rows**, which is what a 140 mm wall forced. The seven are five M12 and two M16 (rows 1-4 are
M12, Denali and Power are M16, CAN is M12; the eighth penetration is the vent and takes no gland).
Add up the hex across-flats plus the spacing you are assuming, show the arithmetic in the revision
note, and only then say the row fits in one line on 200 mm. A claim that something now fits is
exactly the kind of number this branch keeps finding wrong.

**§9.1 carries the stale outline itself**, at lines 1288-1289, inside its own
"REVISED 2026-09-20" block: "the plate is therefore the **base**, 140 x 100 mm, with the
**antenna corner notched out**". This is the only place in the whole spec that says it —
`grep -n "140 . 100\|notch"` over the spec returns just those two lines — and it must be
corrected in step with `enclosure.md` (see Step 3, which explains why the notch goes and what
survives). The *base rather than the wall* half of that revision still stands; only the outline
and the notch change.

**§9.1 and `enclosure.md` disagree about the plate-area requirement**, and you are editing both.
§9.1 says an edge wall "would also have to be ~100 mm deep to reach the required **140 cm²**";
`enclosure.md`'s open-items table says "the **≥ 150 cm²** requirement". This predates the
re-layout and is not yours to have caused, but do not propagate it: pick the one the thermal
model actually uses, say which and why, and make both documents agree — or, if you cannot
establish which is right, record it as an open item in both rather than quietly choosing.

**§9.3 names a box size class that may no longer hold.** It says "Hammond 1554/1555, Fibox,
Bopla class". Those were chosen around a 140 × 100 mm board. Check whether the named families
reach 200 × 140 mm plus the service loop at all; if they do not, say so rather than leaving a
part-number hint that sends someone down a dead end. The part number itself stays unchosen —
that is still an open item, not something to invent here.

- [ ] **Step 3: Amend `hardware/docs/enclosure.md`**

Its opening line still says "the board outline is now known — 140 × 100 mm". Update §1, §2 (the gland row now fits; the box size class has moved), §6 (mounting) and the open-items table.

**The board outline has no notch. The plate still does. These are two different things, and an
earlier draft of this step confused them — read this paragraph before you delete anything.**

`Edge.Cuts` is four straight sides plus four 3 mm corner arcs and nothing else (lines 40431-40438
of `mccan.kicad_pcb`), so the **board** is 200 × 140 mm less 0.08 cm² of corner = **279.92 cm²**,
un-notched. But U5's footprint still carries its all-layer antenna keep-out, and on this board it
lands at **x 213.56 … 234.75, y 48 … 96**. The outline stops at x = 220, so **6.44 × 48 mm of that
keep-out is still over the board** — 309.1 mm², or **3.09 cm²**. A plate coextensive with the
outline *would* reach under the antenna. The notch survives.

What actually changed is the notch's **position**, not its existence or its size. The old notch
removed x 153.56–160.00, y 48.00–96.00; the new one removes **x 213.56–220.00, y 48.00–96.00** —
the same 6.44 × 48 mm rectangle, shifted 60 mm right, which is exactly how far the right edge
moved. So the numbers to write are:

| | Old | New |
|---|---|---|
| Board area | 140 cm² | **279.92 cm²** |
| Notch | x 153.56–160.00, y 48–96 (3.1 cm²) | **x 213.56–220.00, y 48–96 (3.09 cm²)** |
| Plate after notching | ~137 cm² | **~276.8 cm²** |

Re-derive all three rather than copying them: the keep-out polygon is in U5's footprint block in
`mccan.kicad_pcb` (search for the `keepout` token), and the outline is the eight `Edge.Cuts`
entities.

**~272 cm² is close but is not measured.** It appears in the 2026-09-23 spec's comparison table
and again in `layout_pcb.py`'s plate comment. The measured figure is 276.8 cm². Correct both to
the measured value and say it was measured; do not leave an estimate standing beside a board you
can compute from. (An earlier draft of this step called ~272 an arithmetic slip and told you to
write 280. Both halves of that were wrong: 280 is the board, not the plate, and ~272 was an
estimate of the right quantity.)

So the twenty lines carrying "notch" or "~137 cm²" — find them with
`grep -in "notch\|137 cm\|~137" hardware/docs/enclosure.md`; they sit in §1 (74, 76, 79, 84, 87,
100, 104, 106, 119, 123, 125-126, 141), §5 (175-176), §6 (239, 241) and the tables at 372, 375
and 376 — are **mostly re-numbering, not deletion**.

**The `-i` is load-bearing: without it the grep returns eighteen, not twenty.** Line 119 begins
"Notch inner corners" and line 126 "Notching only the antenna corner", both capitalised, and a
case-sensitive grep drops both. Line 119 is the one this paragraph goes on to single out for
recomputation, so running the command without `-i` hides precisely the line you were sent to
find. Work the list one line at a time and decide
per line. Line 119 ("Notch inner corners (153.56, 48) and (153.56, 96) | 21.2 mm") is an antenna
clearance distance and has to be **recomputed** against the new corners, not just re-coordinated.
Line 125-126's "why notching beats cutting the plate back" argument still holds and keeps its
shape, but its arithmetic was done on the old plate and needs redoing. The one line that is
simply false now is the footprint row at 74, and the 241 and 372 restatements of it.

**What survives the edit:** the whole plate-notch decision, with new coordinates. The heading at
line 84, "Which face the plate is — DECIDED 2026-09-20", is a decision record and **both** halves
of it still stand — the plate is the base, and it is notched. Amend the coordinates, date the
amendment, and leave the decision. Espressif's 15 mm in-plane antenna clearance still binds the
enclosure, and the vertical-clearance open item at line 376 stays open, reworded for the new
geometry. Do not delete a decision to make a document tidy.

**The plate's argument has, however, genuinely weakened, and that is the real change to record.**
At ~137 cm² the old plate missed `enclosure.md` §1's ≥ 150 cm² and the thermal group got a veto
over placement because of it. At ~276.8 cm² the requirement is met most of twice over. The
2026-09-23 spec §2 says so explicitly ("the plate stops being a design driver") and §4.3 records
the consequence. That — not the notch — is what changed about the plate.

**Four comments in `hardware/scripts/layout_pcb.py` need attention in the same commit**, and only
three of them are wrong.

The first is the module's own docstring. **Lines 7-16 still argue for a 140 x 100 mm board**, in
the present tense and as a decision: "140 x 100 mm, decided here and not guessed", then the
courtyard sum, then "**140 x 100 = 140 cm2.**" The block that supersedes it is forty lines further
down at `:58` ("200 x 140 mm (2026-09-23). Was 140 x 100.") and is correct and complete. Nothing
at the top says it has been superseded, so a reader who starts at the top of the file -- which is
what a docstring is for -- reads the wrong board size stated as a finding. Do not delete the old
argument; its courtyard arithmetic is the reasoning the new size was chosen against. Mark it:
say at its head that it records the **original** sizing and that the board is now 200 x 140, and
point at the outline block. The same applies to the line inside it about the >= 150 cm2 plate,
which Step 2 resolves against spec 9.1's 140 cm2.

**Line 35 says the antenna keep-out is "on all six layers".** It is eight. This is the six-layer
fact surviving in a fifth place; correct it in passing.

Then the two you were already going to look at, one of which is fine. Lines 25-26 say the heat-spreader is the base "with the **antenna corner
notched out**" and that this supersedes spec §9.1 — that is still **true** and stays. Line 70's
plate comment says the plate goes "to ~272 cm2, against the 150 cm2 enclosure.md section 1 asks
for" — the area is the estimate to replace with the measured 276.8 cm², and the 150 cm² there
disagrees with spec §9.1's "required 140 cm²" (see Step 2, which resolves that). Also check the
dead constants: `ANT_W, ANT_D = 18.0, 6.19` just below are defined and never read anywhere in
`hardware/scripts/` — the real keep-out comes from U5's footprint through `fp_keepouts()`. Either
say in the comment that they document the datasheet figure, or remove them; a constant that looks
load-bearing and is not is the same defect class in a different costume.

**And one in `hardware/scripts/gen_pcb.py`.** `SILK_REF_KEEP`'s docstring at `:290-301` says
"That is what **233 parts on 140 x 100 mm** costs". The board is 200 x 140 with **234** parts --
that is `gen_pcb.py`'s own "parts 234", the netlist component count, which is the same thing
the old "233" counted. The board carries **238** footprints and 238 reference designators; the
extra four are H1-H4, the mounting holes, which the generator adds rather than the netlist. `:388` carries the companion figure ("already took this from 398
to 68"). Both are measurements taken on the old board, sitting inside a rationale for a policy
that is still in force -- so correct the numbers and say which board they were measured on;
do not delete the paragraph or restate the policy.

While you are in that docstring: `:443`'s comment is **correct and stays**. "The ladder used to
stop at 1.4 mm, which was enough only because anything it could not place got shrunk and then
demoted. With those gone..." -- the shrink-and-demote *fallback* really was removed on this
branch and silk really is a hard gate now (`raise SystemExit` at `:470`). The blanket
by-prefix demotion at `:418` and `:508` is a different mechanism and is still there. Two
mechanisms, one of them gone and one of them live, and the comments about each are right.

**Do not widen `SILK_REF_KEEP`.** 177 of the 238 designators are hidden on `F.Fab` -- every R
and C, and both switches -- and whether that policy still earns its keep on a board of twice
the area is a real open question that I am holding for the user, because it goes to why they
asked for the re-layout. It is not yours, it changes the board, and it would break the
byte-identical check below. Leave the tuple exactly as it is.

Change comments only — the board must regenerate byte-identical, and `python scripts/gen_pcb.py`
plus `git diff --stat mccan.kicad_pcb` is how you prove it did.

**One exception to "comments only", and it is the most consequential thing in this task.**
§14 item 5 of `fabrication.md` tells the fab: "ANTENNA KEEP-OUT: no copper, plating, mask,
silkscreen or parts on ANY layer in the marked region at the right-hand edge (**see Cmts.User**)."
There is no such marked region. I checked the artifact:

- The only antenna marking on `Cmts.User` is a free-standing text note, `layout_pcb.py:419`,
  placed at **(121, 16)** — the top edge of the board, about 90 mm from the region it names.
- **No rectangle marks the keep-out anywhere.** The board's only two `Cmts.User` rectangles are
  the TIM gap pads at (76,23)-(110,82) and (81,104)-(95,116), emitted by `tim_areas()` from
  `TIM_PADS`.
- The note's own dimensions, "**18.0 x 6.19 mm** from the module end face", are the dead
  `ANT_W, ANT_D` constants from the paragraph above. The keep-out the board actually enforces is
  U5's footprint `keepout` polygon at **x 213.56 … 234.75, y 48.00 … 96.00** — 21.19 x 48.00 mm.
  The note contradicts the thing it describes.

So between §3's coordinates being 60 mm out and this, **the fab has no correct way to learn where
the keep-out is** — from the document, from the order text, or from the board. This is the one
defect on the branch that reaches the physical part.

Fix it in this commit:

1. Draw the region. Follow `tim_areas()` in `gen_pcb.py:1215` exactly — a dashed `gr_rect` plus a
   label on `Cmts.User` — and take the rectangle from U5's footprint keep-out polygon rather
   than from a constant, so it cannot drift from what the board enforces.
2. Move the note beside the region it names, and correct its dimensions to the keep-out's own.
   If you keep the 18.0 x 6.19 datasheet figure, label it as the *antenna element* inside the
   larger keep-out, which is what it is — do not leave two rectangles stated as one.
3. Then check §14 item 5 and §3 against what you drew. "Right-hand edge" is correct; make the
   rest correct too.

This one change makes `mccan.kicad_pcb` differ, which is the point. Everything else in this step
is still comments-only: after `python scripts/gen_pcb.py`, `git diff mccan.kicad_pcb` must show
the new rectangle and the moved note **and nothing else**. Read the diff, do not just count it.

**Two more places carry the ~272 cm² estimate or the notch, and they pull in opposite directions.**

`docs/superpowers/specs/2026-09-23-pcb-relayout-8layer-design.md` — this plan's own spec — puts
"**~272 cm²**" in its §2 comparison table and repeats the plate argument at lines 61 and 68.
Line 68 ("the plate is still the **base**, still notched at the antenna corner") is **correct**
and is the sentence that caught the error in the earlier draft of this step; leave it. The
~272 cm² in the table is the estimate: correct it to the measured 276.8 cm² in the same commit.
Editing the spec is in scope here because the spec is the authority every later reader argues
from, and an estimate left standing in the authority is how a wrong number propagates — but say
in the commit message that you changed it and why.

`hardware/docs/fabrication.md:119` says "heat-spreader plate is notched to clear it — see
`enclosure.md`". That is **still true** and needs no edit. It is listed here so you do not
"fix" it on a sweep for the word "notch".

**`enclosure.md`'s resolved-items table (around lines 372-378) has stale rows that have nothing
to do with the notch**, so the notch grep does not find them. Read the whole table and fix:

- **"~~Layer count~~ RESOLVED 2026-09-22 | 6 layers, 1 oz on all six"** — this board is
  **8 layers**. The row's reasoning about odd stacks laminating from an even one still holds
  and is worth keeping; the count and the date do not.
- **"~~2 oz outer copper vs the land patterns~~ RESOLVED 2026-09-20 | 1 oz outer / 2 oz inner
  … the In2.Cu feed polygon gained copper"** — wrong twice. This board is **1 oz on all
  eight**, and the feed polygon is **In4.Cu**.
- **"~~Board outline~~ RESOLVED 2026-09-20 | 140 × 100 mm, M3 at 5 mm from each corner"** —
  the outline is **200 × 140 mm**; check the M3 inset against `layout_pcb.py`'s `MOUNT_INSET`
  rather than assuming it carried over.
- **"~~Thermal group area~~ RESOLVED 2026-09-20 | 1358 mm² in two patches"** — re-measure or
  mark it as needing re-measurement; §4.3 of the 2026-09-23 spec relaxed the thermal group.

These are **resolved-item records**, so amend them with a dated supersession the way Step 1
handles §3.2 — the decision and its reasoning are the value; only the figures are wrong.

**Grep for the coordinates as well as for the words.** The notch grep above keys on "notch" and
"137", and `enclosure.md` carries the old keep-out rectangle in six further lines that contain
neither. Run

```bash
grep -n "153.56\|174.75\|160.00\|136.9" hardware/docs/enclosure.md
```

**Work the grep's output, not this list.** When I ran it, it returned lines **101, 108, 115,
119, 176, 192, 242 and 349** — the "14.75 mm beyond the board's own 160 mm edge" sentence, the
notch-area arithmetic, the antenna-proper rectangle at x 168.56–174.75, the 21.2 mm notch-corner
clearance, item 3's restatement of the notch rectangle in the box-selection list, the §5
statement of the absolute keep-out, the §6 restatement, and the conformal-coating row. Eight
lines, and the enumeration is here to tell you what each one *is*, not to bound the work: if
your run returns a line this list does not name, the line is in scope and this brief is out of
date. Each needs the same 60 mm shift, except line 115's antenna-proper rectangle and line 119's
21.2 mm clearance, which need **recomputing** rather than shifting, because they are distances
between the notch corners and the antenna rather than the rectangle itself.

**One more file to look at, with a question rather than an instruction.**
`hardware/scripts/gen_pcb.py:1249` and `:1313` explain why the per-net `/VBAT` island failed,
using "eleven pads span x 83.38..174.58, so its box is 98.4 x 20.0 mm and swallows five /VBAT
pads". Those are old-board coordinates. The *argument* is the one Step 1 preserves and is still
correct; the *numbers* in it may describe a board that no longer exists. Check them against the
current pad positions. If they are stale, either re-derive them or rewrite the sentence so it
makes the argument without asserting a measurement — do not leave old coordinates standing as
though they were measured on this board.

- [ ] **Step 4: Amend `hardware/docs/routing-tool.md`**

Four signal layers rather than two, the new `SIGNAL_LAYERS`, and what the router achieved on the roomier board against its 122 of 139 on the old one.

**§5 is a dated log of runs, not a status page.** It holds §5.1 (two signal layers), §5.2 (the
six-layer run, committed as `64182bf`) and §5.3 (the rip-authority run, tried and discarded).
Add a **§5.4 for the eight-layer run** with its date and commit, and leave 5.1–5.3 alone — 5.2
is the baseline the new figures are compared against, and 5.3 records a thing that was tried
and did not work, which is worth more than a tidy document. The figure to beat from §5.2 is
**72 unconnected items**, of which 51 are nets the router never sees (`AR_SKIP_CLASSES`
covers FEED, POWER and CAN), so **21** is the router-attributable number.

Note that §5.2's own line reads "Four signal layers instead of two (F.Cu, In2.Cu, **In4.Cu**,
B.Cu)". That was true of the six-layer board. On this board `In4.Cu` is the solid `/VBAT`
power plane and the fourth signal layer is `In5.Cu`. Do **not** correct §5.2 — it is accurate
about the run it describes. State the current set in §3 and §5.4, where it belongs.

§3 and its "What it is and is not allowed to touch" subsection describe *current* behaviour
rather than history, so those are updated in place: the layer list the run is given, and the
net classes it is not allowed to touch.

**One more line, in §6 and not §3 or §5, so neither grep above finds it.** "Nothing this repo
writes carries a zone fill" (around `:373`) says `gen_pcb.py` "emits **all six zones** as
outlines with no `filled_polygon`". The sentence is right about the fill and wrong about the
count: the board has **seven** zones -- GND on `In1.Cu`, `In3.Cu`, `In6.Cu` and `B.Cu`,
`/VBAT` on `In4.Cu`, `/+24V` on `B.Cu`, and `/power_input/GND_IN` on `F.Cu`. Correct the count
and leave the rest of the bullet, including both `--refill-zones` consequences, alone.

This is the same figure `fabrication.md` §12 gets wrong in the other direction (it tables
five), and Step 5 fixes that one. After this task the two documents must agree with the board
and with each other -- seven zones, that list. If you change one and not the other you have
replaced one wrong number with two that disagree, which is worse.

- [ ] **Step 5: Amend `hardware/docs/fabrication.md`**

8 layers, 200 × 140 mm, 1 oz throughout, ENIG. Carry forward the three PCBWay items that still apply: **via-in-pad plugging must be specified on the order**, not implied by the gerbers; U10's 0.15 mm pad gap is under their 8 mil IC mask figure so expect no mask dam there; and their "vias ≤ 0.45 mm" hole-to-hole wording wants a DFM question. Add one new item: confirm PCBWay's standard 8-layer 1.6 mm stackup and whether 1 oz on all eight is standard or a surcharge.

**This is not a headline-facts edit.** `fabrication.md` is 450 hand-maintained lines across
sixteen sections, and several of them are *derived from the board* — they were computed against a
six-layer, 140 × 100 board whose routing no longer exists. This is the one document that goes to a
vendor, so a stale number here is an order placed on a wrong board. These sections must be
re-derived, not reworded:

- **§5 Drill schedule** — every figure in it. The per-size counts, "**968 vias in total, of which
  614 came from the router**", "the 0.20 mm plated hole … there are **47** of them", and the
  8:1-aspect-ratio argument built on those 47, are all functions of the router run that Task 10
  has just replaced. Re-derive from the **generated Excellon files** in `hardware/output/` — they
  are what the fab actually receives, and they carry PTH and NPTH separately. That means doing
  this section **after Step 7**, not before; do the prose parts of Step 5 now and come back.
  Delete the trailing line "Via totals will grow by a handful as the last hops are hand-routed" —
  the hand routes are done.
- **§6 Land-pattern exceptions** — the measured gaps (U10's 0.175 mm track-to-pad, and the
  "next three gaps" at 0.183 / 0.190 mm) are routing-dependent. Re-measure or, if you cannot,
  say in the document that they are unverified against the current routing rather than leaving
  them stated as fact.
- **§4 design rules**, **§12 copper pours** and **§14 order notes** restate numbers from §2, §5 and
  §6. Update them from the re-derived values; §14 is pasted verbatim into a vendor order, so a
  number that survives there survives into the build.
  **§12 needs more than a number pass.** It opens "Five zones" and tables five. The board has
  **seven**, and I have taken them from the artifact so you do not have to
  (`mccan.kicad_pcb:91161` onward):

  | Layer | Net |
  |---|---|
  | `In1.Cu` | `GND` |
  | `In3.Cu` | `GND` |
  | `In4.Cu` | `/VBAT` |
  | `In6.Cu` | `GND` |
  | `B.Cu` | `GND` |
  | `B.Cu` | `/+24V` |
  | `F.Cu` | `/power_input/GND_IN` |

  So the count is wrong, the feed is on the wrong layer (`In3.Cu` in the table, `In4.Cu` on the
  board — the swap again), and two ground planes are missing entirely. `In1.Cu`'s "the reference
  plane for `F.Cu` and `In2.Cu`" is still correct and stays. The `GND_IN`/`GND` separation
  paragraph below the table is a circuit requirement, unchanged by any of this — leave it.
- **§11 Impedance** currently argues "do NOT order controlled impedance" from a six-layer board
  with CAN on an outer layer. The conclusion may well still hold, but its reasoning does not:
  CAN is now a stripline on `In2.Cu` between two ground planes. Rewrite the reasoning for the
  present stackup and restate the conclusion you reach, whichever way it goes.

If any figure cannot be re-derived within the task, write it down as an open item in §16 with the
reason. An honest gap is fine; a confident stale number is not.

**§7 "Via in pad — the five paddles" is correct and stays.** I counted it on the routed board so
you do not have to re-derive a section that does not need it: 65 vias at 0.55 mm pad / 0.25 mm
drill, split `/+24V` 25 (D4's 5 × 5), `GND` 28 (U1 and U2 at 3 × 4, U3 at 2 × 2) and `/VBAT` 12
(U9's 3 × 4) — exactly the table §7 prints, and exactly the 65 vias §14 item 1 orders plugged
and capped. Paddle arrays come from the footprints, not from the routing, so they did not move
when the board did. Leave the section alone.

That is the line to draw when re-deriving: **routing-dependent figures moved, footprint-derived
figures did not.** For contrast, two §14 figures that did move, because they count vias the
router placed — "Min plated drill 0.20 mm, **47** holes" and "Min annular ring 0.15 mm, on **35**
vias of 0.50 mm dia". The board carried 55 vias at 0.50/0.20 when I counted, and hand routing
may have changed it again since. Both come from §5, which is why §5 and everything restating it
wait until after Step 7 and are taken from the generated Excellon files.

**Those two counts are not the same count, and 47 was never a via count.** I took the drill
inventory off the board at `50486be`: 1382 vias, 55 at 0.50/0.20, 65 at 0.55/0.25, 957 at
0.60/0.30, 305 at 0.80/0.40 — and **twelve further plated 0.20 mm holes that are not vias**.
They are U5's thermal pad: the `ESP32-WROOM-32E` footprint models its paddle stitching as
twelve `thru_hole` pads numbered 39, size 0.6 mm, drill 0.2 mm. So the smallest-drill *hole*
count is vias-plus-those-twelve. The old pair reconciles exactly — 35 + 12 = 47 — which is how
you can tell the two figures were always coupled. On the board as it stands the pair is
**55 vias and 67 holes**. If you re-derive "min plated drill, N holes" from the via list alone
you will write 55 and be twelve holes short, and the fab will be quoted the wrong drill count.
Take it from the Excellon file after Step 7, which contains both.

**The 0.15 mm annular-ring *value* did not move — only its count.** Three of the four via sizes
give exactly 0.15 mm of ring (0.50/0.20, 0.55/0.25, 0.60/0.30); the 0.80/0.40 gives 0.20 mm, and
U5's 0.6/0.2 paddle pads give 0.20 mm. So 0.15 mm is still the minimum. Do not "correct" it.

**Three §14 items are verified correct and are not yours to touch.** A list of things to change
reads as permission to change anything nearby, so I checked these against the artifact:

- **item 1** (via-in-pad, 65 vias at 0.55 mm pad / 0.25 mm drill, five paddles) — matches the
  board exactly, and matches §7 above. Footprint-derived.
- **item 4**'s closing sentence, "Layer ORDER and the 0.1 mm prepreg either side of the outer
  layers must be kept" — the eight-layer stackup does put 0.1 mm prepreg either side of the
  outers, so this survives the layer-count change even though the sentence sits in a section
  whose opening lines do not. Item 4's subject — no controlled impedance ordered — is also
  still true: nothing on this branch ordered any.
- **item 6**'s via-diameter list, "0.50 / 0.55 / 0.60 / 0.80 mm" — those are exactly the four
  diameters on the board and no others. The hole-to-hole DFM question around it stands.

Items 2 (U10's missing mask dam) and 3 (tight land patterns) are footprint-derived like §7 and
did not move either; carry them forward as they are.

**§3 "Board outline and mechanical" is stale in every line, including the one marked absolute.**
It says "Rectangle **140.0 × 100.0 mm**", gives mounting holes at (25, 25), (155, 25), (25, 115),
(155, 115) with "the outline runs x 20…160, y 20…120", and then states the antenna keep-out as
"**x 153.56 … 174.75, y 48.00 … 96.00** — this one is absolute". Every one of those is the old
board. Take all of them from the artifact:

- outline and corner radius from the eight `Edge.Cuts` entities (x 20…220, y 20…160, 3 mm arcs);
- mounting-hole centres from the board, not from `MOUNT_INSET` arithmetic;
- the keep-out rectangle from U5's footprint `keepout` zone polygon — it is
  **x 213.56 … 234.75, y 48.00 … 96.00** on this board (see Step 3).

The keep-out is the serious one: §14 item 5 tells the fab "no copper, plating, mask, silkscreen or
parts on ANY layer in the marked region at the right-hand edge", and §3 is where the region's
coordinates come from. "Right-hand edge" is still true; the numbers are 60 mm out.

**§1 "The one-screen summary" restates the headline facts** — layer count, size, copper weight,
finish. Check it against the values you land on; a summary that disagrees with the document under
it is worse than no summary. Four of its rows are stale and two that look stale are not — I
checked the generated `(stackup …)` block at `gen_pcb.py:1110` so you do not have to:

- **stale:** "Board size 140.0 × 100.0 mm"; "Layers **6**"; "Inner copper … **all four inner
  layers**" (there are six now); and, in §2, every row below `In2.Cu`.
- **correct, leave alone:** "Finished thickness **1.6 mm**" and "Max aspect ratio **8:1**". The
  eight-layer stackup still sums to 1.59 mm — 8 × 0.035 copper, dielectrics
  0.1/0.2/0.2454/0.2/0.2454/0.2/0.1, two 0.01 masks — so 1.6 mm and 1.6 ÷ 0.20 = 8:1 both
  survive the layer-count change. Adding layers did not thicken the board; the dielectrics got
  thinner. Do not "correct" these to match the new layer count.

**§2 is a six-layer stackup end to end, and §14 orders one.** §2 opens "Six layers, built as a
foil lamination: two cores bonded by three prepregs" and its table lists `In3.Cu 0.035 VBAT — the
7 A feed plane`; §14's order text says "**6-layer FR4, 1.6 mm finished**" and "**1 oz (35 um)
finished copper on ALL SIX layers**". §14 is the block that gets pasted into the PCBWay order, so
this is the one stale number on the branch that spends money: it would order a six-layer board
for an eight-layer design. Rebuild §2's stackup table from `gen_pcb.py`'s `(stackup ...)` block
rather than editing the old one row by row, and rewrite §14's opening lines from it. Line 82's
"Going to six layers made the 2 oz impossible" is a **historical** sentence about how the copper
weight was decided and reads correctly in past tense — check it rather than replacing it.

Two more lines in that subsection are not historical and are wrong in the present tense:

- **`:79`, the heading "Why 1 oz on all six"** — it is eight now, and the heading is the label on
  an argument that still holds.
- **`:85`, "`In2.Cu` and `In4.Cu` now carry *tracks*"** — present tense, wrong layers. The signal
  layers are `In2.Cu` and `In5.Cu`; `In4.Cu` is the solid `/VBAT` plane. The argument itself gets
  **stronger** on this board rather than weaker: two inner signal layers became two inner signal
  layers out of six inner layers, all of which take one inner-copper selector, so the 6/8 mil
  etch limit at 2 oz still decides the plane's copper weight. Fix the layer names and keep the
  reasoning.

This is the In3/In4 swap again, inside a section you are already editing for the layer count —
exactly the place a partial edit leaves a wrong layer name behind.

- [ ] **Step 6: Mark the old plan's Tasks 8 and 9 as superseded**

Add a line at the head of each pointing at this plan and its spec. Do not delete them — they record how the board got here.

- [ ] **Step 7: Generate the fabrication outputs**

**The plan named the wrong script here and it has been corrected.** `scripts/gen_outputs.py`
generates `outputs.kicad_sch` — the *outputs schematic sheet*, the PROFET/PCA9685 page. It is a
sibling of `gen_rails.py` and `gen_mcu_can.py`, it contains no reference to gerbers, drills or
`kicad-cli`, and it imports `uuid`, so running it would regenerate a schematic with fresh UUIDs
and dirty the tree for no reason. **Do not run it.** Nothing in this repo generates a fabrication
package; `hardware/output/` today holds only DRC/ERC reports, logs and netlists. You are creating
that package for the first time, with `kicad-cli` directly:

```bash
cd /d/projects/ESP32MCCAN/hardware
KC="/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"
mkdir -p output/gerbers output/drill

# Gerbers, using the plot settings gen_pcb.py already writes into the board
"$KC" pcb export gerbers --board-plot-params --check-zones -o output/gerbers/ mccan.kicad_pcb

# Drill, PTH and NPTH separate, with the hit report section 5 needs
"$KC" pcb export drill --format excellon --excellon-separate-th       --generate-map --generate-report --report-path output/drill/drill-report.txt       -o output/drill/ mccan.kicad_pcb

# Placement (CPL) and BOM
"$KC" pcb export pos --format csv --units mm --side both -o output/mccan-cpl.csv mccan.kicad_pcb
"$KC" sch export bom -o output/mccan-bom.csv mccan.kicad_sch

ls -la output/ output/gerbers/ output/drill/
```

Confirm the gerber set contains **eight copper layers** — `F.Cu`, `In1.Cu` through `In6.Cu`,
`B.Cu`. A gerber set with six is the tell that the board file did not regenerate.

`output/drill/drill-report.txt` is the authority for §5 of `fabrication.md`: it is KiCad's own
count of every hit at every size, PTH and NPTH separately. Re-derive that section from it rather
than from the board file or by hand.

**§15 of `fabrication.md` lists two outputs these commands do not produce**, and says of the whole
package "Not yet generated — Task 9 step 7", which is now wrong twice: it is this task, and it is
generated. Add both exports rather than trimming the list — a schematic PDF and an assembly
drawing are what an assembler actually reads. Both invocations are checked against
`kicad-cli 10.0 --help`:

```bash
"$KC" sch export pdf -o output/mccan-schematic.pdf mccan.kicad_sch
"$KC" pcb export pdf --mode-multipage --include-border-title \
      --crossout-DNP-footprints-on-fab-layers \
      -l F.Fab,B.Fab,F.Silkscreen,Edge.Cuts -o output/ mccan.kicad_pcb
```

Then update §15 itself: replace "Not yet generated" with what was generated, when, and from which
commit, and check every row of its table against what is actually in `output/`. A manifest that
does not match the directory beside it is the same defect as a stale figure.

Note that `--check-zones` refills the zones as it plots. Afterwards, confirm the board file on
disk has not changed (`git diff --stat mccan.kicad_pcb` is empty); if it has, the committed board
and the plotted gerbers disagree, and that is the thing to resolve before shipping either.

- [ ] **Step 8: Commit**

```bash
git add -A docs hardware/docs hardware/output hardware/scripts/layout_pcb.py
git commit -m "hw(docs): the documents catch up with a 200 x 140 mm, 8-layer board

Spec 9.1, 9.3 and 10; enclosure.md, routing-tool.md and fabrication.md; and the old
plan's Tasks 8 and 9 marked superseded rather than deleted, since they record how
the board got here. layout_pcb.py's heat-spreader comment no longer claims a notch
the outline does not have. Plus the fabrication package, generated for the first
time -- gerbers, drill with its hit report, CPL and BOM.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 12: Extract the `pcb-layout-routing` skill

**Files:**
- Create: `~/.claude/skills/pcb-layout-routing/SKILL.md` and `references/{placement,stackup,routing,router-traps,gates}.md`

**Interfaces:**
- Consumes: everything learned in Tasks 1–11
- Produces: a user-level skill, reusable on any KiCad board

**The test of every sentence in this skill:** would it still be true on a different board? MCCAN's regions, nets and part numbers stay in `hardware/docs/`. The method goes here.

- [ ] **Step 1: Write `SKILL.md`**

```markdown
---
name: pcb-layout-routing
description: Use when laying out, placing or routing a printed circuit board in KiCad - especially when the board is generated from scripts rather than drawn by hand, when an autorouter is involved, or when a board is congested, hard to read, or failing DRC in ways that keep coming back.
---

# PCB layout and routing

## The workflow

1. **Generate, never hand-edit.** The board file is an output. Every change goes into the
   scripts that produce it. A hand edit in pcbnew is lost on the next run, and worse, it is
   lost silently.
2. **Place, and measure the placement.** Courtyard fill per region, checked by a script.
   Density is the root cause behind most routing failure, most silkscreen failure, and most
   "the autorouter is bad" complaints.
3. **Hand-route what carries an electrical requirement**, before the router runs: current
   paths that must be poured, differential pairs, switching loops, Kelvin taps.
4. **Let the router do the rest**, then **grade its output against the board's own rules**
   before admitting a single segment.
5. **Gate everything**, on every build. A gate that runs sometimes is a comment.

## Start here

- Congested board, unroutable nets, silk with nowhere to go → `references/placement.md`
- Choosing or changing a layer stack → `references/stackup.md`
- Deciding what to route by hand → `references/routing.md`
- Using an autorouter → `references/router-traps.md`
- What to check and why DRC is not enough → `references/gates.md`

## The five things most worth knowing

- **A pour never shorts to a foreign net**, so DRC will never catch a ground-split error.
  If two nets must meet at exactly N places, a script has to count them.
- **An autorouter will go below the sizes you give it and exit 0.** Grade its output
  yourself, against the board's own minimums.
- **Loop area and Kelvin taps are placement problems**, not routing problems. There is no
  good route for a 35 mm compensation trace.
- **Measure, do not derive.** A plane's current capacity, a region's fill, a pair's length:
  compute them from the board. Arithmetic in a comment was true once.
- **Silkscreen that cannot be printed is a placement failure.** Shrinking it or moving it to
  the fab layer hides the failure and leaves a board nobody can work on.
```

- [ ] **Step 2: Write `references/placement.md`**

Regions and auto-flow; why largest-first packing beats reference order; part-free channels between regions and how to size one (0.20 mm track on 0.40 mm pitch ≈ 15 tracks per layer in 6 mm); fill budgets and what a realistic target is (under ~40 % routable, ~75 % not); why a budget should have headroom rather than match the current measurement -- note that this board's own budgets run 25 % to 45 %, so do not write that they are all under 40 %; silk as a hard gate; and the specific observation that every silk violation on a dense board is a designator landing on a neighbour's outline or on a pad, never two real silk graphics — which makes it a text-placement problem, decidable before anything is routed.

Then the lesson that cost the most here. The silk placer searched four candidate positions per part — the midpoints of its four sides — and behind that sat a ladder of fallbacks: shrink the text, then demote it to the fab layer. The candidate search was simply broken for any part hemmed in on all four sides, and the ladder hid that perfectly: every part it could not place was quietly degraded, and the gate went green, so nobody ever had to notice. **Removing a fallback is how you find out what it was covering for.** Generalise it: a fallback that fires silently converts a defect into a cosmetic loss, and a cosmetic loss nobody is shown is a defect that never gets fixed. Make the fallback announce itself, or take it out until the thing behind it works.

- [ ] **Step 3: Write `references/stackup.md`**

Every signal layer needs a plane on at least one face — and a pour on the *same* layer is not that. Cheap symmetry rules. Why an odd layer count costs the same as the next even one and warps more. How inner-copper weight is one selector for all inner layers, so a signal layer's etch class decides the plane's weight too — and the trap that follows: 2 oz inner etch at 6/8 mil is 0.203 mm, above a 0.20 mm clearance rule, so thick inner copper can silently make a board unbuildable. Split power planes — and write this one up as a **worked rejected approach**, because that is what it was on this board. The instinct is to compute islands from pad positions and let fill priority carve rather than drawing a partition. The trap is that a per-net bounding box is not an island once that net's pads span the board: the box encloses foreign pads, and the "split" shorts what it was meant to separate. The plane went solid instead. Carry the gate lesson with it: a check that rasterises a zone outline and subtracts via barrels cannot see a neighbouring zone on the same layer, so when the plane stops being alone on its layer that check must **refuse to measure** rather than print a number it cannot stand behind. A gate that degrades quietly into a wrong answer is worse than no gate. Measuring a plane's real current capacity by rasterising the pour and punching the antipads out.

- [ ] **Step 4: Write `references/routing.md`**

What earns a hand route: poured current paths, differential pairs, switching loops, high-impedance nodes, Kelvin taps. What does not. Pour, do not track, for current. Why the return half of a switching loop should not be routed when there is a plane beneath it. Bringing wide copper into fine-pitch packages across two adjacent pins of the same net. Taking a feedback tap from the far end of a capacitor. Putting a differential pair on a buried layer so segregation is structural rather than a rule.

- [ ] **Step 5: Write `references/router-traps.md`**

The KiCadRoutingTools specifics — `--escalation board` rather than trusting `--fab-tier`, `--no-bga-zones` because the BGA machinery is really a fine-pitch-grid detector that fires on TSSOP and QFN, `--keep-input-copper`, why `--strict-sizes` is unusable, and the general rule underneath all of them: a tool's own graders passing tells you nothing about whether it honoured your rules. Do not reconstruct these rationales from memory: `hardware/docs/routing-tool.md` is the written authority for them, and the comments in `hardware/scripts/route_external.py` beside each flag say why that flag is passed. Generalise from those; do not restate MCCAN's own numbers.

- [ ] **Step 6: Write `references/gates.md`**

Each gate, what it catches, and specifically what it catches that DRC does not: ground-split counting, copper below the board's own minimums, tracks on plane layers, zero-length segments, courtyard overlap before a twenty-minute routing run rather than after, plane current capacity, region density, and a zone that filled as two disconnected islands - that last one because a pinched pour is legal copper on the right net and shipped through every other check in this repo. Two traps about the gates themselves belong here too: a DRC run that counts unconnected pads in its exit status returns non-zero on a board with zero violations, so the gate is the violation count in the report body and never `$?`; and a gate that parses that report has to run after it, not beside it. And the framing that makes them worth writing: a gate exists because someone lost hours to the thing it checks.

One more belongs in `gates.md` because it is the failure the gates here could not catch at all:
**the stale-fact sweep, and why grepping for words is half of it.** When a measurement or a
decision is superseded, it has to be chased through every document and comment that restates it.
Grepping for the words that name it -- "notch", "split plane", "six layers" -- finds the prose.
It does not find the copies that travel as bare numbers, because "x 153.56 … 174.75" says
nothing greppable about what that rectangle is. So a sweep needs two passes: one for the words,
one for the numbers themselves. On this board the second pass is what found the fabrication
document telling the vendor an antenna keep-out 60 mm from where it is, and an order block still
specifying a six-layer stackup for an eight-layer design.

Carry the rule with it: **a ruling recorded is not a ruling delivered.** The moment a decision
reverses a documented claim, grep for every restatement of that claim -- then, not in the task
that happens to own one of the sections. A single reversal here had to be chased into a spec
three times, two other specs, four hand-maintained documents and five source comments, and it
was found each time by asking "which other file quotes the number I just corrected", never by
looking somewhere new.

And the sharpest version of it, which cost this branch three more defects after everything
above was already written: **sweep the source of truth too, and start at the top of the file.**
Every sweep here pointed outward from the one module that decides the layout, at the documents
that quote it. That module's own docstring had carried the superseded board size, in the present
tense and as a decision, since the day it was superseded -- and no sweep looked there, because
it was the thing the sweeps were checking *against*. The file you trust is the file you stop
reading, and the summary at the top of a file is the part nobody re-reads after they write it.

One more, about the citations themselves rather than what they point at: **a line number is a
claim with a shelf life.** Everything above is about text that went stale where it sat. This one
goes stale without being touched. A brief written for a later task cited fourteen places in two
source files that a concurrent task was still inserting lines into; every citation was correct
when written and wrong by the time it was read, offset by however many lines landed above it.
The failure mode is worse than a dangling reference, because the reader finds *something* at the
line and has to decide who is wrong — and the cheap resolutions are both bad: skip the finding
as already fixed, or edit the source until the citation comes true. When you cite into a file
someone else is editing, cite the quoted text, which is stable, and offer the number as a hint.

Its sibling, and the sharper of the two: **when a handoff document prescribes a command and then
says what the command returns, run it.** A drifted citation announces itself — the reader finds
the wrong text at the line and knows something is off. A command that under-returns is silent.
It hands back a shorter list that looks complete, and nothing distinguishes "the brief listed
extras" from "my command missed some". Both happened here in one sentence: a grep prescribed
without `-i`, a prose count taken from that grep, and an enumeration beside it taken by eye —
two lines apart in the list, and the line the paragraph then singled out for special handling
was one of the two the command dropped. Prose and command have to come from the same run, or
they disagree the moment either is edited.

Its corollary is worth its own line: **a stale number inside a live rationale is not a dead
comment.** The instinct on finding one is to delete the paragraph. Usually the policy it argues
for is still in force and still correctly described, and only the measurement moved -- so the
repair is to correct the figure and say which artifact it was measured on, not to remove the
reasoning. Deleting it costs the next reader the answer to "why is this like this", which is
the only thing a comment is for.

And its sibling, which the number sweep cannot find: **check that an instruction has a
referent.** A sweep asks whether a figure is current. It does not ask whether the sentence around
the figure still points at something. On this board the order text told the fab "no copper in the
marked region at the right-hand edge (see Cmts.User)" — every word of it current, and nothing
marked on that layer to see. The test is to read a document as the person who will act on it and
ask what they would do next, not to read it as a list of values to verify.

Two rules about writing them, both learned the hard way on this board. **A gate that admits or rejects copper should not be written by the agent whose copper it judges** — not because anyone cheats, but because the author's idea of what could go wrong is exactly the blind spot the gate is supposed to cover. And **ablation over argument**: when a change fixes something, do not reason about which part of it did the work — take each part back out and watch. A fix credited to the wrong cause teaches the wrong lesson and leaves the real one live. That happened here, in the very task whose subject was that unverified fallbacks hide defects.

- [ ] **Step 7: Verify the skill loads**

```bash
ls -R ~/.claude/skills/pcb-layout-routing/
head -5 ~/.claude/skills/pcb-layout-routing/SKILL.md
```

Confirm the frontmatter has `name` and `description` and that `name` matches the directory.

- [ ] **Step 8: Note it in the project**

The skill is user-level and outside the repo, so nothing commits. Add one line to `hardware/scripts/README.md` saying the method behind these scripts is written up in the `pcb-layout-routing` skill, so a future reader in this repo knows it exists.

```bash
cd /d/projects/ESP32MCCAN
git add hardware/scripts/README.md
git commit -m "hw(docs): point at the pcb-layout-routing skill

The method behind these scripts now lives in a user-level skill, since the expensive
lessons in it are tool lessons rather than MCCAN lessons.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Self-review notes

**A correction the review turned up.** The spec, and the first draft of this plan, both said
the outputs block was the congested one at 59 % fill. Running the Task 3 script against the
current board shows outputs at 37 % and **`input` at 75.8 %** — the 59 % in `layout_pcb.py`
described the *original* `102..131` outputs region, which was widened in the same commit that
recorded it. The re-layout is still right; which column gets the extra width is not what the
spec said. Task 3 Step 4 corrects the spec; Task 4's region map now widens the left column.

**A second correction.** The first draft said the CAN connector was J2 and that its distance
from J1 provided the separation. `enclosure.md` §4 is explicit that **J8** is CAN and that J2
is the programming header and not an enclosure penetration at all. J8 sits third in the gland
row, ~35 mm from J1, so the separation argument had to be rebuilt on the stackup rather than
on distance — which is what §3.1 of the spec actually claims. The CAN path is also **four
nets**, not two, because the choke L6 splits each side.

**Spec coverage.** §2 outline → Task 4. §3 stackup → Task 5. §3.1 CAN on In2.Cu → Tasks 5 and 8. §3.2 split plane and its gate → Task 5 Steps 4 and 7. §4 placement, channels, budgets → Tasks 3 and 4. §4.3 thermal group relaxes → Task 4 Step 4. §5 silk → Task 6. §6.1 hand routes → Tasks 7, 8, 9. §6.2 router → Task 10. §7 gates → Task 3 creates the new one; every other task runs the suite. §8 archive → Task 1. §9 skill → Task 12. §10 what is not changing → the Global Constraints. §11 open items → Task 11 Steps 2, 3 and 5 record them; the CAN impedance question is answered by Task 8 Step 3 recording the lengths and the spec's explicit "uncontrolled is defensible, but decide it".

**Known soft spots, called out rather than hidden.**

- **Task 4 Step 4** cannot give exact coordinates for every hand-placed part, because they depend on decisions made while doing it. It gives the constraints each group must preserve and names them. This is the task to expect iteration in.
- **Tasks 7–9** likewise give the electrical requirement, the tools that find the room, and the verification, but not the coordinates. Routing coordinates cannot be written before the placement they sit on exists.
- **Task 5 Step 7** has a real chance of failing, and three named fallbacks in preference order if it does.
