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

## 5. What the first good run delivered

2026-09-21, with every guard in §3 on. 58 minutes of routing, 72 million iterations.

| | HEAD, built-in router | this run, frozen in |
|---|---|---|
| KiCad DRC errors | **1** (U4 pad 2 clearance) | **0** |
| DRC warnings | 71 (68 silk, 2 footprint, 1 other) | 58 (51 dangling via, 5 connection width, 2 dangling track) |
| Unconnected items | 179 | **105** |
| Schematic parity | — | 0 issues |
| Copper | 2613 seg / 787 via | 4248 seg / 1190 via |

The guards held, and the summary says so as data rather than as an absence of warnings:
`escalation_policy: board`, `fab_tier_escalations: 0`, and `min_delivered` exactly
`{via_diameter: 0.45, track_width: 0.2}` — the board's own floors, not a micron under. 1007
narrowings, every one of them legal. `--keep-input-copper` was tested for real: the router did rip
`/outputs/SENSE_FL_B` to clear a blocker and then put it back, logged as *"original copper
restored"*, and `freeze_routes.py`'s additive check passed on the result.

Of the 105 unconnected items, **53 are on nets this router was never given** — VBAT, +24V, +5V,
VLOGIC_IN, FEED_P, VBAT_PROT, VBAT_F, MID, SNS, CANH, CANL, GND_IN. Those are steps 2 and 3 of the
routing task and they are still to be laid by hand. The other 52 are the router's own shortfall,
38 nets it could not close — mostly one pad each, concentrated in the same RGB output bundle that
defeats the built-in router, and its own hints name the pre-existing nets in the way.

Two numbers are **not** fab-ready and are tracked separately: 123 of the router's vias came back at
0.45 / 0.20 mm, and gen_pcb's 73 thermal vias are 0.50 / 0.25 mm. Both have a **0.125 mm annular
ring**, under PCBWay's stated 0.15 mm minimum — which they state for exactly this case, *"for pads
with vias in the middle"*. The router was entitled to the first set: `min_via_annular_width` in
`mccan.kicad_pro` is **0.1**, so `--escalation board` permits it. Raising that floor to 0.15 is
what stops it, and it has to happen before the next run rather than after.

---

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
