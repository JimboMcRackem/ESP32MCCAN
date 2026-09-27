# Stackup: choosing and reasoning about layers

## Every signal layer needs a plane on at least one face

A signal layer with no ground (or return) plane adjacent to it on either side has no
controlled return path — every trace on it is an uncontrolled loop antenna, and every via
that drops onto it from a plane layer has no obvious return via nearby. The rule is cheap to
state and cheap to check while a stack is still a list of layer names: for every signal
layer, does at least one neighbouring layer carry a solid reference plane?

**A pour on the same layer as the signal traces does not satisfy this.** A zone that shares a
signal layer with tracks is still routed copper with gaps in it wherever a trace runs; it is
not a reference plane, and treating it as one is the mistake, not the rule. The plane has to
be a *different* layer.

On the worked-example board this rule is satisfied symmetrically: two ground planes (`In1.Cu`,
`In3.Cu`) sandwich the first signal layer (`In2.Cu`) from both sides, and the same pattern
(`In6.Cu`, `B.Cu` reference plane, `In5.Cu` signal) covers the other signal pair, with `F.Cu`
itself referenced by `In1.Cu` underneath (`hardware/scripts/gen_pcb.py`, the `zones()`
docstring: "In1 references F.Cu and In2; In3 references In2 and In4; In6 references In5 and
B.Cu — every signal layer has a plane on at least one face").

## Cheap symmetry, and why an odd layer count is a false economy

A symmetric stack (mirror-image copper weights and dielectric thicknesses top-to-bottom)
resists warping during lamination and reflow; an asymmetric one bows, and the thinner or
lighter side bows more. An **odd number of copper layers cannot be built symmetric** — there
is always one layer with no mirror partner — so going from an odd count to the next even one
buys the symmetry back for the same panel process and, on most fabricator's pricing, no extra
cost tier. If a design is landing on an odd layer count because that is "enough copper,"
check the next even number before committing; it is very often free.

## Inner copper weight is a stackup-wide selector, not a per-layer one

A fab typically offers one weight (1 oz, 2 oz, ...) for *all* inner layers as a single
selection, because the lamination process treats them together. That means choosing a
heavier inner weight for one signal layer's current-carrying needs silently also thickens
every inner **plane** layer's etch, and etch class and copper weight interact: heavier copper
needs a wider minimum gap to hold tolerance. A 2 oz inner layer at a 6/8 mil (~0.15/0.20 mm)
process class can land at **0.203 mm minimum etch clearance** — a hair over a 0.20 mm board
clearance rule — which means a stackup upgrade taken to serve one power layer can silently
make the *whole board* fail its own clearance floor unless the rule is widened to match. Check
the fab's etch-class-vs-copper-weight table before raising inner weight for one layer's sake;
the number that matters is what it does to the layer you weren't thinking about.

## Splitting a plane by geometry: a worked rejected approach

The instinct, when several rails need to share one plane layer without full routing, is to
give each rail its own island: compute the smallest rectangle (or a per-net bounding box)
that covers all of that net's pads, pour that net inside it, and let fill priority handle the
overlaps. It is worth writing up as a rejected approach, because on a real board with more
than a couple of rails it does not survive contact with the actual pad layout.

**The trap:** a bounding box is only an island if the net's own pads are the only thing inside
it. The moment a net's pads span a meaningful fraction of the board, its bounding box also
encloses *other nets'* pads — and a zone poured across that box either shorts to them (if
connect-pads allows it) or has to notch around every one of them to avoid it, at which point it
is not replacing routing, it is routing with extra steps and a legal-looking failure mode. On
the worked-example board, one rail's eleven pads spanned nearly 100 mm of the board's width;
its bounding box swallowed five pads belonging to the plane's *other* net outright
(`hardware/scripts/gen_pcb.py`, `zones()`: "/+24V's eleven pads span x 83.38..174.58 ... its
box is 98.4 x 20.0 mm and swallows five /VBAT pads"). A rectangular split tried first (a
straight vertical line dividing the layer) failed for the identical underlying reason: the
nets interleave across the whole board, so *no* single geometric partition — line or box —
separates them. Every ordering of pour priority just decides which net loses its copper where
the partition is wrong, not whether one is wrong.

**The resolution that held:** give the shared layer to exactly one net as a full-layer pour,
and route every other rail that would have wanted an island like an ordinary net instead. The
objection to routing them (their netclass width, e.g. 2.0 mm, "is awkward to route") turns out
to be a width problem, not a topology problem, and an external router with real net ordering
handles ordinary width just fine. Reserving a whole layer for the one net whose current
actually justifies a plane (the raw supply feed) and routing the rest is simpler to reason
about and does not require discovering, per board revision, where this revision's nets happen
to interleave.

**Carry the gate lesson forward with the plane, too.** A script that measures a plane's
current-carrying capacity by rasterising its pour and punching out via/through-hole antipads
is measuring *one net's* copper. If a second zone ever ends up sharing that same layer, the
rasteriser cannot see the neighbouring zone's polygon arithmetic — priority order, not
geometry, decides which zone wins a given pixel once two zones share a layer, and a script
that assumes it is alone will report a number for copper that is not what actually fills. The
gate's correct behaviour when that assumption breaks is to **refuse to produce a number at
all**, loudly, rather than print a plausible-looking width that nobody asked to be validated
against a lie. On the worked-example board `check_plane_width.py` does exactly this: before
measuring, it checks whether any other zone shares the plane's layer and fails outright if so
(`hardware/scripts/gen_pcb.py` line ~225, "FAIL: %s is not alone on %s"). **A gate that
degrades quietly into a wrong answer is worse than no gate at all** — no gate at least tells
you nothing was checked.

## Measuring a plane's real capacity

Do not compute a plane's current-carrying width from the drawn polygon. Rasterise the fill at
a fine pitch, punch out every via and through-hole antipad that lands in it (a real via steals
real copper, at the size it will actually be drilled, not the size a courtyard diagram
implies), then measure the narrowest cross-section that remains in both axes and grade it
against a real standard (IPC-2221 internal-layer width tables are the common one) at the
current and temperature rise the plane is actually expected to carry. On the worked-example
board this measurement runs on every build and is the *last* check in the chain specifically
because it is the one an autorouter's own via placement can make worse than the unrouted input
(`hardware/docs/routing-tool.md` §3: "every via it places punches another antipad through the
plane, so the pour is narrower after a run than on the input board").
