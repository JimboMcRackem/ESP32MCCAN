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
3. grades the result with KiCadRoutingTools' `check_connected`, `check_drc` and `check_weird`, then
   with this repo's `check_vias.py` and `check_grounds.py`.

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

Two further guards, both from the tool itself:

- pre-existing routed nets are **never** ripped unless `--rip-existing-nets` asks for it, and this
  wrapper does not ask;
- `--layers F.Cu B.Cu` keeps it off the inner layers. **In1.Cu is the ground plane and In2.Cu is the
  VBAT plane; neither is a routing layer.** This is not a default — `route.py` would otherwise use
  every copper layer the board declares.

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

`routes_signal.json` is committed. It is *data the scripts consume* — the same status as the
netlist — so the board stays fully generated and `python scripts/gen_pcb.py` reproduces it on a
machine that has never heard of KiCadRoutingTools.

---

## 5. Things worth knowing before trusting a run

- **Route the planes first is *their* advice, not ours.** The tool's README recommends
  `route_planes.py` before `route.py` so plane-drop vias land on real fill. This board already
  pours its planes and places all 142 ground drops in `gen_pcb.py`, so that step is skipped
  deliberately — running it would place a second set of taps.
- **`check_drc.py` needs `--refill-zones`** when run standalone, for the same reason KiCad's own DRC
  does here: a board shipped with zone outlines and no `filled_polygon` reports plane opens that are
  not real.
- **The two repo guards are not optional.** GND and GND\_IN are separate nets that meet at exactly
  two places (L2 winding B, and R3). Nothing in DRC enforces that, because a pour never shorts to a
  foreign net — `check_grounds.py` is what catches it, and the wrapper runs it on the router's
  output for that reason.
- Limitations the tool states: no push-and-shove, no blind or buried vias, no per-region design
  rules. None of those bite this board.
- Both `Orthoroute` (`C:\Program Files\Orthoroute`) and this are installed. Orthoroute was not
  chosen: KiCadRoutingTools has the first-class CLI, which is what a generated-board workflow needs.
