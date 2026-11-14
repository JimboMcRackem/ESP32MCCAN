# Placement: regions, budgets, channels, silk

Placement decides almost everything that happens later. On a generated board it is also the
one stage cheap enough to measure on every single build — there is no autorouter run, no DRC
pass, just a courtyard box and a rectangle. Spend the cheap check here; it is what a
routing failure, a silk failure and "the autorouter must be bad" all turn out to trace back to.

## Regions and auto-flow

Divide the board into named rectangular regions (one per functional block is a reasonable
default), give each part a home region, and let an auto-flow packer place whatever was not
pinned by hand. Two placement policies worth naming explicitly:

- **Largest-first packing beats reference-designator order.** A packer that places C1, C2,
  C3... in schematic order leaves odd-shaped gaps that only another small part happens to
  fit, and it is luck whether the next part in line is small. Sorting the unplaced queue by
  footprint area, largest first, packs the big constraints while the most room still exists
  and lets small parts fill in around them.
- **Part-free channels between regions are not wasted space — they are where escapes live.**
  A stranded pad needs somewhere to route a fan-out stub to a via; if every square millimetre
  between two regions is full of components, that stub has nowhere to go. Size a channel from
  the geometry it has to carry: a 0.20 mm track on a 0.40 mm pitch fits roughly 15 tracks per
  layer across a 6 mm channel. If a region needs N escapes side by side, that arithmetic tells
  you the channel width before you place a single part, not after the router fails.

## Fill budgets

Track courtyard-area-over-region-area per region, on every build, against a declared budget
per region — not one global number, because different regions carry different escape demand.
A budget only works as an early warning if it has headroom over where the region actually
sits: pushing a budget down to match today's measurement removes the warning it exists to
give the next change.

What "reasonable" looks like is board-specific, but the shape is not: a region a router still
has to work in wants a real margin (**under ~40% is a workable rule of thumb for a routable
region**); a region that is a static, at-rest can tolerate more (**~75% for a region nothing
routes through**). Do not copy a single global percentage from a rule of thumb into every
region's budget — measure the region, decide what margin it needs, and write that number down
as the budget, not as a fact about the current board. On the worked-example board these
budgets run from 25% (an output-driver region with heavy fan-out) to 45% (a mostly-static
input region) — a spread, not a constant — while the actual measured fill on the same board
runs 0% to 38.8% across all of them (`python scripts/check_density.py --report`, current
run). Both the spread and the gap between budget and measurement are the point: a single
"everything under 40%" rule would have been true of this board by coincidence, not by design,
and a docstring in the script that computed it had already drifted — it recorded one region
at 76% from an earlier placement round, a fact about a board that no longer existed by the
time a later task ran the same script and got 38.8%. **A number in a comment is a claim with a
shelf life; regenerate it, don't copy it.**

## Silk as a hard gate

At any real component density, every silkscreen placement failure resolves to the same root
cause: a reference designator lands on a neighbour's outline or on a pad. It is never two
pieces of real silk graphics (outlines, pin-1 marks, polarity dots) overlapping each other.
That means it is a **text-placement problem**, decidable from geometry alone, before a single
net is routed — which makes it worth gating on every build rather than eyeballing at the end.

The mechanics that generalise:
- Cut the keep-list of designators that actually stay on silk to what a person needs to find
  by eye on a finished board — connectors, fuses, test points, semiconductors worth probing.
  Move everything else's reference to the fabrication/assembly layer, where the value field
  can carry the same information for anyone reading the assembly drawing instead of the bare
  board. This alone removes most of the conflicts before any text is moved.
- For what remains, try the position the footprint library gave it first, then walk outward
  from the part's own body at increasing distance until a candidate box clears every other
  designator's silk graphics *and* every pad on the board (including the part's own — that is
  the same pair of rules the CAD tool's own silk checker applies).
- A designator that fits nowhere in that search is a **hard failure of the build**, not a
  warning. Placement made the promise that everything would fit; silk is where that promise
  gets checked.

## The lesson that cost the most

A silk placer can be built to try only a handful of candidate positions — say, the midpoints
of a part's four sides — and back it with a ladder of fallbacks: shrink the text if nothing
fits, then demote it to the fabrication layer if even shrunk text does not fit. This looks
like defensive engineering. It is a trap.

The candidate search above is simply broken for any part boxed in on all four sides by close
neighbours — a common case at real density — and the fallback ladder hides that perfectly:
every designator the search could not place gets quietly shrunk and then demoted, the gate
stays green, and nobody ever has to notice that the search itself doesn't work. On the
worked-example board, one part's control-loop group was placed deliberately tight — four
passives sitting within 1.4 mm of an edge on purpose, because the loop area they set matters
electrically — and its own designator needed to walk out to 2.95 mm before anything cleared.
A four-candidate search with a 1.4 mm ceiling and a silent fallback would have shrunk and
demoted that one designator forever, and the board would have shipped with a part nobody
could identify by eye, exactly the failure silk exists to prevent.

**Removing a fallback is how you find out what it was covering for.** The fix here was not a
smarter fallback — it was a longer, honest search (`gen_pcb.py`'s `silk_refs()` walks
outward at increasing push distances rather than trying four fixed points and giving up) and
a hard failure with no shrink-and-hide option when even that search comes up empty. Generalise
the shape of the mistake, not the fix: a fallback that fires silently converts a real defect
into a cosmetic loss, and a cosmetic loss nobody is shown is a defect that never gets fixed.
Either make the fallback announce itself loudly enough that someone has to act on it, or take
the fallback out until the thing behind it actually works.

## Worked example

`hardware/scripts/gen_pcb.py`'s `silk_refs()` is the concrete version of everything above:
`SILK_REF_KEEP` is the keep-list (connectors, fuses, test points, MOSFETs/diodes/inductors —
everything else moves to the fabrication layer); the candidate search tries the library
position first, then walks a ladder of push distances outward on all four sides; a designator
that clears nothing raises a build failure naming every part that has nowhere to go, with the
placement fix spelled out rather than a silent shrink. On the current board this keep-list
took warning count from 398 designators down to 68 candidates, and the search then places 54
of those where the library already had them and moves the remaining 7 (measured this session,
`python scripts/gen_pcb.py` with `PCB_OUT` redirected to a scratch path — see
`hardware/docs/routing-tool.md` for why the real board is never regenerated as a side effect
of checking something). `hardware/scripts/check_density.py` is the region-fill gate described
above, and its own docstring is the citation for the stale-76% story.
