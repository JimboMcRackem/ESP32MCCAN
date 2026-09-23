# The external router — KiCadRoutingTools

**Status:** set up and runnable, 2026-09-21. Nothing in the repo depends on it yet; the committed
`mccan.kicad_pcb` is still the output of `gen_pcb.py`'s own router.

**Authority for the rule this has to respect:** every artefact in `hardware/` — the four sheets,
the symbol library and `mccan.kicad_pcb` — is **generated** by the scripts in `hardware/scripts/`
and is never hand-edited. An external router writes a board file, so §4 below is the part that
keeps that rule true.

---

## 1. Why

`gen_pcb.py` carries its own grid A\* (the `AR_*` section, ~1000 lines). It is not a bad router,
and it is the only one that knows this design: the GND\_IN island, the thermal via arrays, the 142
ground drops, the true pad extents, the antenna keep-out. It lays every hand route, every fan-out
lane and the whole power stage.

Where it runs out is the signal bundle. On a full pass it routes about **85 of 139** nets, and the
54 failures are not spread evenly — **27 of them are the RGB output bundle**, and the rip-up log
shows the same nets being torn out and re-laid over and over (`RET_RR_G` was ripped at 71 and again
at 106). That is thrashing, not convergence: a global net-ordering problem that a greedy
shortest-first order cannot fix from inside.

KiCadRoutingTools is a Rust-accelerated A\* router for KiCad 9 and 10 with rip-up and reroute,
MPS crossing-aware net ordering, and a post-route cleanup reconciled against KiCad's own
connectivity model. It operates **directly on `.kicad_pcb` files**, so there is no Specctra
DSN/SES round-trip — which matters, because `kicad-cli pcb export` has no DSN exporter and a
FreeRouting round-trip would have needed the GUI.

---

## 2. What is installed, and where

| | |
|---|---|
| Tool | `C:\Users\jimba\KiCadRoutingTools` — v0.22.1, a copy of the `C:\Program Files\KiCadRoutingTools-main` install |
| Why a copy | `build_router.py` writes the compiled router into `rust_router/` inside its own tree, and `C:\Program Files` is not writable without elevation |
| Python | `C:\Users\jimba\KiCadRoutingTools\.venv` — CPython 3.14.6, with numpy 2.5.3, scipy 1.18.1, shapely 2.1.2, Pillow 12.3.0 |
| Rust router | `rust_router/grid_router.pyd`, the prebuilt `windows-x86_64` binary from release v0.22.1 (no Rust toolchain needed) |

Both locations are overridable: `KRT_HOME` for the tree, `KRT_PYTHON` for the interpreter.

To update the tool later: re-copy the tree (or `git clone` it somewhere writable), then
`cd %USERPROFILE%\KiCadRoutingTools && .venv\Scripts\python build_router.py`.

---

## 3. Running it

```
cd hardware
python scripts/route_external.py
```

That is the whole thing. It:

0. runs `check_courtyards.py` over the placement — a courtyard overlap is caught only by KiCad's
   DRC, which in this chain runs *after* the router, so it is checked here for a second instead of
   discovered twenty minutes later (see §6);
1. runs `gen_pcb.py` with **`AR_SKIP=1`** and **`PCB_OUT=output/router/unrouted.kicad_pcb`**, so the
   input board is everything this repo generates *minus* the signal copper — hand routes, thermal
   and stitching vias, ground drops and pours all present. `mccan.kicad_pcb` is not touched;
2. runs `py_router/route.py` over the signal nets only;
3. grades the result with this repo's `check_geometry.py`, then KiCadRoutingTools'
   `check_connected`, `check_drc` and `check_weird`, then this repo's `check_vias.py`,
   `check_grounds.py` and `check_plane_width.py`.

   `check_plane_width.py` runs last because it is the only one whose answer the router can
   make *worse*: every via it places punches another antipad through the VBAT plane, so the
   pour is narrower after a run than on the input board. It rasterises the pour, subtracts
   every via and through-hole antipad, cuts it in both directions and grades the worst cut
   against IPC-2221 for 7.0 A at a 10 K rise. At 1 oz that asks 11.44 mm; the board delivers
   71 mm.

Useful variants:

```
python scripts/route_external.py --preview      # route it, report what it would add, write nothing
python scripts/route_external.py --no-regen     # reuse the input board from last time
python scripts/route_external.py -- --max-ripup 6 --heuristic-weight 1.9
                                                # anything after -- is passed to route.py
```

Everything lands in `hardware/output/router/` (git-ignored): `unrouted.kicad_pcb` in,
`routed.kicad_pcb` out, plus copies of the project and DRU files — `route.py` writes DRC settings
back into the sibling `.kicad_pro`, so it is deliberately given a copy and never the real one.

### What it is and is not allowed to touch

`route_external.py` excludes, by name, every net in the **FEED**, **POWER** and **CAN** classes plus
**GND** — the same set `gen_pcb.AR_SKIP_CLASSES` skips. The list is built from
`layout_pcb.NETCLASSES` rather than typed out, so moving a net into one of those classes
automatically puts it out of the external router's reach. Those nets still exist on the input
board as copper, so the router treats them as obstacles to work around.

Further guards, all of them from the tool itself and none of them a default:

- pre-existing routed nets are **never** ripped unless `--rip-existing-nets` asks for it, and this
  wrapper does not ask;
- `--keep-input-copper` makes the input board's copper read-only through the post-route cleanup
  passes. Without it the cleanup sweeps input copper it judges dead — the first full run stripped
  7 input segments and left 5 nets ripped. The freeze step in §4 is a **diff**, so it is only
  correct while the output stays a superset of the input, and this is what keeps that true;
- `--escalation board` is the size floor. See the first bullet of §5: `--fab-tier` is *not* the
  flag that holds sizes, and its own default lets a net be retried below the board's minimums;
- `--no-bga-zones` switches off the BGA escape machinery entirely. **This board has no BGA, LGA or
  CSP part on it** — the detector is really a fine-pitch-grid detector and it fires on TSSOP and
  QFN, reading U7 (a 0.65 mm TSSOP-28) as a "14 rows x 2 columns" ball grid and then running an
  under-pad shrink rescue at 0.0762 mm track / 0.25 mm via / 0.09 mm clearance;
- `--layers` comes from `gen_pcb.SIGNAL_LAYERS` — **F.Cu, In2.Cu, In4.Cu, B.Cu** since the board
  went to six layers on 2026-09-22. **In1.Cu is the ground plane and In3.Cu is the VBAT plane;
  neither is a routing layer**, because a track on either is a slot cut through a reference.
  `route.py` would otherwise use every copper layer the board declares. It is also not quite
  watertight — back when the list was `F.Cu B.Cu`, the first run put four sub-micron stubs on
  the two plane layers despite logging both as forbidden — which is one of the things
  `check_geometry.py` exists to catch. Note that `AR_LAYERS` is still `F.Cu B.Cu`: that is
  `gen_pcb`'s own router, whose occupancy grid is two-layer by construction, and it is now the
  fallback path rather than the one that lays the signal bundle.

Geometry is read from `gen_pcb.py`'s own constants (`AR_W` 0.25 mm, `AR_CLEAR` 0.20 mm, `AR_VIA`
0.6/0.3 mm, `AR_GRID` 0.1 mm, `AR_EDGE` 0.5 mm, `AR_VIA_COST`), so the two routers are comparable
and the external one lands on the same 0.1 mm grid as the fan-out lanes it has to join.

KiCad **keep-out rule areas are honoured natively** (`extract_keepouts` in its parser), so U5's
antenna keep-out is respected without extra configuration.

---

## 4. Folding a result back in

`routed.kicad_pcb` is an artefact of a tool, not of this repo, so it **must not be committed as
`mccan.kicad_pcb`**. The rule is that the board is generated; a hand-carried router output would
break it silently the first time anyone re-ran `gen_pcb.py`.

`scripts/freeze_routes.py` closes that hole:

```
python scripts/freeze_routes.py          # after a route_external.py run
python scripts/gen_pcb.py                # now emits the frozen copper, routes nothing
```

It **diffs** the two boards — `output/router/unrouted.kicad_pcb` against
`output/router/routed.kicad_pcb` — and writes whatever the router *added* to
`scripts/routes_signal.json`, keyed by net name, in board millimetres. A diff rather than a
"copper on signal nets" filter, because the input board already carries hand routes and fan-out
lanes that sit on signal nets, and a filter would emit those twice. If the routed board is
*missing* any of the input's copper, freezing **fails loudly**: this chain is additive, and copper
going missing means one of the guards in §3 did not hold.

`gen_pcb.py` then picks that file up automatically:

| | |
|---|---|
| `routes_signal.json` present | it is emitted; the built-in router does not run |
| `AR_ROUTE=1` | run the built-in router anyway, frozen file or not |
| `AR_SKIP=1` | no signal copper at all — the router input board |
| a frozen net that the board no longer has | **hard failure**, with the fix printed |

Widths and layers come from the frozen file rather than from `AR_W` / `AR_LAYERS`, so a track the
router necked down or laid wide keeps the width it was given.

One thing the freeze does drop: **segments shorter than a tenth of the routing grid**. The first
good run left two 10 µm nubs hanging off the ends of real tracks, joining nothing to nothing —
too short for the tool's own `check_weird` to call them dangling, and too short for KiCad to draw.
`check_geometry.py` refuses to freeze a board carrying one, so left in place they would have
blocked the chain on a run that was otherwise ready. The threshold is imported from
`gen_pcb.AR_GRID` so the two files cannot drift.

`routes_signal.json` is committed. It is *data the scripts consume* — the same status as the
netlist — so the board stays fully generated and `python scripts/gen_pcb.py` reproduces it on a
machine that has never heard of KiCadRoutingTools.

---

## 5. What the runs delivered

### 5.1 The first good run -- 2026-09-21, two signal layers

58 minutes, 72 million iterations, every guard in §3 on. It is recorded here because it is the
run that set the guards, not because its copper survives: 105 unconnected items, 4248 segments
and 1190 vias, 0 DRC errors. `--keep-input-copper` was tested for real -- the router ripped
`/outputs/SENSE_FL_B` to clear a blocker and put it back, logged as *"original copper restored"*,
and `freeze_routes.py`'s additive check passed. Two numbers were not fab-ready and were fixed
before the next run: 123 router vias at 0.45/0.20 mm and 73 thermal vias at 0.50/0.25 mm, both a
0.125 mm annular ring against PCBWay's 0.15 mm minimum. `min_via_annular_width` in
`mccan.kicad_pro` was 0.1, so `--escalation board` was entitled to them; raising that floor is
what stopped it.

The diagnosis that run produced is the one that mattered: the failures were not router quality,
they were **channel count**. 38 nets could not close, concentrated in the RGB output bundle, and
the router's own hints named pre-existing copper in the way every time.

### 5.2 The six-layer run -- 2026-09-22, committed as `64182bf`

Four signal layers instead of two (F.Cu, In2.Cu, In4.Cu, B.Cu). The diagnosis held:

| | two signal layers | four signal layers |
|---|---|---|
| Single-ended nets | -- | **122 / 139** |
| Multi-point pads | -- | **293 / 299** |
| Frozen copper | 4606 seg / 817 via | **3629 seg / 568 via** |
| KiCad DRC violations | 61 | **22** |
| Unconnected items | 105 | **72** |
| Dangling vias | 53 | **10** |

Fewer segments *and* fewer vias for more connectivity, which is what a channel-starved board
looks like once it stops being starved. Of the 72 unconnected items, **51 are nets this router
was never given** -- FEED, POWER and CAN are in `AR_SKIP_CLASSES`, so VBAT, +24V, +5V,
VLOGIC_IN, VBAT_PROT, FEED_P, VBAT_F, MID, SNS, CANH and CANL are steps 2 and 3 of the routing
task and still to be laid by hand. The remaining **21 match the router's own report exactly**:
11 failed single-ended nets plus 10 multi-point pads.

### 5.3 The rip-authority run -- 2026-09-22, tried and discarded

The obvious next lever on those 21, and it does not work. route.py's failure histories named
**62 distinct blocker nets**; filtering them against copper actually present in
`unrouted.kicad_pcb` left exactly one that is this repo's -- `/rails/SW_BOOST`, the hand-routed
boost stage -- so the other **61 were passed to `--rip-existing-nets` explicitly**, which also
bypasses route.py's own self-granted `_RIP_ESCALATION_CAP = 12`.

The guards held perfectly. SW_BOOST was ripped once, logged *"original copper restored"*, and
`freeze_routes.py`'s additive check passed. KRT's own DRC came back **NO DRC VIOLATIONS**. And
the result is still worse:

| | `64182bf` | with 61 nets rippable |
|---|---|---|
| KiCad DRC violations | 22 | **15** |
| dangling vias | 10 | **3** |
| Unconnected items | **72** | 82 |
| Frozen copper | 3629 seg / 568 via | 3981 seg / 555 via |

It bought hygiene and paid in connectivity. The single worst line is `/+3V3_SW`, which was
**fully connected before the run and carries five unconnected items after it** -- a net the
router took apart to clear someone else's path and never put back. Six more output nets moved
the same way, and six moved the other way; the net movement is +10 against the number that gates
Task 9.

That is the useful finding, and it is not "the rip list was too long". A rip is only a gain if
the re-route succeeds, and on a board where 17 nets are already boxed in, granting authority over
61 more just moves which ones lose. **Do not reach for `--rip-existing-nets` as a way out of a
congested run.** The lever that worked was the stackup.

## 6. Things worth knowing before trusting a run

- **A clean exit code does not mean the sizes you asked for.** This is the one that cost a run.
  `--fab-tier standard` reads like a floor and is not: the flag that governs how far below a
  *requested* size a failing net may be retried is **`--escalation`**, whose default is `fab` —
  documented as "down to the fab tier floor, **below the board's own minimums**". The first full
  run exited 0 and handed back **2177 tracks at 0.0889 mm** against a 0.25 mm request and a 0.20 mm
  board floor, 115 vias at 0.45/0.2 against a 0.6/0.3 request, 11 zero-length segments and 4 stubs
  on the plane layers. Every descent was logged — in a warning, somewhere in 70 000 lines.

  `--escalation board` is the setting this board wants: a net may neck down to what the board
  declares and KiCad's DRC accepts, and no further. `--strict-sizes` exits 3 on any descent at all,
  which is too strict here — necking 0.25 to 0.20 mm past a fine-pitch pad is ordinary layout — so
  **`scripts/check_geometry.py`** does the grading instead. It fails on copper under the board's own
  `rules.min_*`, on a track on a plane layer and on zero-length junk, and merely *reports* legal
  necking. It runs first in the chain, and it is the gate on whether a run is freezable at all.

- **A router cannot widen a channel, and this one says so plainly.** When a net comes back with
  `Re-route FAILED: no rippable blockers found`, the thing in the way is a *pad*, not another
  net's copper, and no amount of rip-up authority will move it. That message means go and look at
  the placement. It is what the RGB driver row turned out to be: Q4..Q7 on a 3.5 mm pitch with
  2.700 mm of pads left 0.800 mm between packages, which passes one 0.20 mm track, and the two
  middle pins of each package -- boxed in by their own neighbours on both sides -- have nowhere
  else to go. Every PWM net the run left open was a pin 2 or a pin 5, and each channel closed
  exactly one of the pair facing across it. The fix was 0.8 mm of `layout_pcb.NUDGE`, not a
  router flag.

- **`boxed_in_static` means two different things, and only one of them is placement.** The
  bullet above is the first: no lane exists, so build one. The second looks identical in the
  summary and has the opposite fix. After the driver row and the resistor grid were spread the
  run went 269 -> 276 connected pairs, and eight nets stayed open with the same verdict -- but
  `show_room` on the **bare** board found **1125 legal via positions** in a 9 x 6 mm window
  around the worst of them and 0.662 mm of slack 1.5 mm from the stranded pad. The room was
  there all along. What was missing by the time those nets were attempted was a *lane to reach
  it*: the router takes nets in its own order, and the last arrivals find the one F.Cu
  thoroughfare across that corner already full.

  So the test is: run `show_room` against `output/router/unrouted.kicad_pcb`, not against the
  routed board. Room on the bare board and none on the routed one is congestion; none on either
  is geometry. Only the second wants a placement change — and a placement change aimed at the
  first actively misleads you, because it closes some nets and opens others somewhere else,
  which is exactly what the run before this did.

  The fix for congestion is to make the net go **first**. `gen_pcb` lays `ROUTES` before it
  autoroutes, so a `ROUTES` entry is simply a net that is not competing. It does not have to be
  the whole route: a stub of half a millimetre from the pad to a via is enough, because
  `In2.Cu` and `In4.Cu` carry no zones and no SMD pads and are all but empty under most of this
  board. Once a stranded pin is on an inner layer it has left the contested band entirely, and
  where it goes next is the router's problem again. Seven such stubs, none longer than 0.95 mm,
  are what the RGB row needed after the parts had been moved.

  **`scripts/find_escape.py`** finds them. Name the stranded pads and it sweeps outward from
  each for the nearest point where a through via clears every layer *and* the straight stub to
  it clears F.Cu, keeps the escapes in one invocation clear of each other, and prints the
  `ROUTES` and `ROUTE_VIAS` lines to paste:

  ```
  python scripts/find_escape.py Q4.5 Q5.5 Q6.5 Q8.5 --dir E
  ```

  `--dir` is worth giving when you know the answer: the middle pin of a two-column package can
  only leave sideways, and an unconstrained sweep just finds a nearer point that is no use.

- **A via is a square when `routes()` measures it.** `gen_pcb.routes()` compares bounding boxes,
  and a box gap is the **larger** of the two axis separations — so overlapping in x by any
  amount at all leaves the y separation standing alone as the answer. A via 0.40 mm from its
  own pad's diagonal neighbour clears it as a *disc* and fails as a *box*, by 0.025 mm, and the
  shortfall is reported on the axis you cannot fix: the cure is to push the via clear in **x**,
  the axis the message never mentions. Five candidate positions were generated against a disc
  model here and all five failed that way. If you are sweeping for via positions, call
  `gen_pcb._rect_gap` and `_seg_rect_gap` directly rather than reimplementing them —
  `show_room.py` uses discs by design, and `show_inner.py`'s docstring says so.

- **Check the courtyards before you spend twenty minutes routing.** KiCad's DRC is the only thing
  that checks courtyard overlap, and in this workflow DRC runs *after* the router — so a placement
  change can regenerate clean, pass every guard, route for twenty minutes and only then be
  rejected. U4's nudge was taken at 0.9 mm on copper arithmetic and lost exactly that way: its
  courtyard reaches 0.275 mm past its pads and C6's 0.250 mm past its own, so the real gap was
  0.700 mm and not the 0.925 mm the pads showed. **`scripts/check_courtyards.py`** is the cheap
  half of that DRC run and answers from the netlist and the placer in about a second, before any
  regenerate:

  ```
  python scripts/check_courtyards.py --near 0.35   # overlaps, plus near misses
  ```

  Run it after every edit to `PLACE` or `NUDGE`. `--near` is the one that matters when you are
  about to move something: it prints the budget you actually have.

- **`--keep-input-copper` does not stop `--rip-existing-nets`; the two compose.** The first
  reads as "the input board's copper is read-only", and what it actually does is narrower: it
  disables the late orphan sweep and the strip pass. A net named on the rip list is still
  rippable with it on. What protected `/rails/SW_BOOST` on the rip run was not the flag, it was
  that the list was filtered against `unrouted.kicad_pcb` first -- and then the router ripped it
  anyway and restored it. Filter the list; do not trust the flag to do it.

- **`--nets` exclusions say what may not be ROUTED, not what may not be RIPPED.** They keep a
  net out of the routing queue and nothing more. `route.py`'s later salvage stages build their
  own rip-eligibility list from the board, and run 6 printed `5 pre-existing net(s) eligible
  for rip-up: /+5V, /CANH, /CANL, /VLOGIC_IN, /outputs/PWM_RR_R` -- four of them nets this
  repo had just excluded by name. It then ripped `/+5V` to clear a tap route for `/+3V3_SW`,
  failed to put it back ("original corridor taken"), and the improvement gate kept the run
  because it had gained thirty nets and lost one. What shipped was a board with the entire
  hand-routed +5V distribution gone -- 21 segments and 4 vias, U2's output to U6 -- and only
  `freeze_routes.py`'s additive contract caught it, twenty minutes after the fact.

  The cure is `route.py`'s own protection map (issue #521): a `protected_nets` object in the
  sibling `.kicad_pro`, which every rip channel consults -- the pre-run `--rip-existing-nets`
  expansion, all six in-run rip ladders via `filter_rippable_blockers`, and the octolinear
  smoothing pass. `route_external.protect()` writes it from `excluded_nets()` after
  regenerating, so the two lists cannot drift. Protection lifts only for a net named EXACTLY,
  with no glob, in `--nets` or `--rip-existing-nets`; `!*/+5V` carries a `*` and `!GND` is not
  the string `GND`, so nothing this repo passes lifts it by accident. The reason string is
  free text (`hand-routed` here); only the literal `locked` is special, and that one can never
  be overridden.

- **Git Bash mangles every rip-list argument silently.** MSYS path conversion rewrites any
  argument starting with `/` into a Windows path, so `/outputs/PWM_FL_B` arrives at route.py as
  `C:/Program Files/Git/outputs/PWM_FL_B` and matches nothing -- no error, just a rip list that
  does nothing. Net names on this board all start with `/`. Export `MSYS2_ARG_CONV_EXCL='*'`
  before the run, and verify with `python -c "import sys; print(sys.argv[1:])"` rather than
  assuming. The same conversion silently redirects `kicad-cli`'s `-o /tmp/x.json` to the
  drive root, `D:\tmp`.

- **Route the planes first is *their* advice, not ours.** The tool's README recommends
  `route_planes.py` before `route.py` so plane-drop vias land on real fill. This board already
  pours its planes and places all 142 ground drops in `gen_pcb.py`, so that step is skipped
  deliberately — running it would place a second set of taps.
- **Nothing this repo writes carries a zone fill.** `gen_pcb.py` emits all six zones as outlines
  with no `filled_polygon`, and KiCad fills them on load. Two consequences, both of them regular
  false alarms rather than findings:

  `check_drc.py` needs **`--refill-zones`** when run standalone, for the same reason KiCad's own DRC
  does here — a board with outlines and no fill reports plane opens that are not real.

  `check_connected.py` has no such flag, so **every "pad <-> zone" pair it reports on a planed net
  is an artefact**. It reported `/power_input/GND_IN` open at `(41.100, 74.000) F.Cu pad <-> (42.000,
  36.000) F.Cu zone`; that pad is U10.8, and it sits well inside the GND_IN outline (x 22..62,
  y 36..119.5), as do all twelve GND_IN pads. There is simply no copper there yet for it to trace.
  The authority on plane connectivity is KiCad's own DRC with `--refill-zones`; `check_grounds.py`
  is the authority on the GND / GND_IN split.
- **The two repo guards are not optional.** GND and GND\_IN are separate nets that meet at exactly
  two places (L2 winding B, and R3). Nothing in DRC enforces that, because a pour never shorts to a
  foreign net — `check_grounds.py` is what catches it, and the wrapper runs it on the router's
  output for that reason.
- Limitations the tool states: no push-and-shove, no blind or buried vias, no per-region design
  rules. None of those bite this board.
- Both `Orthoroute` (`C:\Program Files\Orthoroute`) and this are installed. Orthoroute was not
  chosen: KiCadRoutingTools has the first-class CLI, which is what a generated-board workflow needs.
