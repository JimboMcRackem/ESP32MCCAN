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

## Limitation: the DRC reports are stale

`v1-4layer/drc.rpt` and `v2-6layer/drc.rpt` are byte-identical. Both were last
written at commit `7c4bf0d`, before the four-to-six-layer transition, so neither
report describes the board it is archived with. In particular, the v2-6layer
board has no DRC report of its own — the one sitting beside it is a leftover
from the four-layer board. Treat both as absent rather than as evidence about
either board's DRC status.
