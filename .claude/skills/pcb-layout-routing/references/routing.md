# Routing: what to lay by hand, and what to leave to a router

## What earns a hand route

A general-purpose autorouter optimises for "every net connects, within the sizes it is told."
That is exactly the wrong objective for a short list of nets whose *geometry itself* is the
electrical requirement, not just a means to connectivity:

- **Poured current paths.** A rail that has to carry real current is a plane or a wide pour,
  not a track, and its width is set by a current/temperature-rise calculation, not by whatever
  a router's default net class says. See `stackup.md` for the corollary — sometimes the right
  hand-authored answer is "give it a whole layer," not "give it a wide track."
- **Differential pairs.** Length-matching and consistent spacing are constraints an
  autorouter can be told about, but a pair that has to stay coupled through vias and layer
  changes is easiest to get right by hand or by placing it where it never has to compete for
  room in the first place (see the buried-layer point below).
- **Switching loops.** The loop area of a switching converter's hot loop is often the single
  biggest lever on its radiated noise. That area is fixed by where the parts sit and how the
  loop closes, not by which router laid the last 2 mm of it.
- **High-impedance nodes.** A feedback or sense node with real input impedance picks up
  whatever is capacitively or inductively coupled onto its trace. Keep it short, keep it away
  from noisy neighbours, and do not let a router's shortest-path heuristic route it alongside
  a switching node just because that happened to be the free channel.
- **Kelvin taps.** A four-wire sense connection is only a Kelvin connection if the sense tap
  comes off the *right physical point* on the part it measures — a via near a pin is not the
  same node as the pin's own copper once real current is flowing. This is a placement decision
  disguised as a routing one; see below.

Everything else — the bulk of ordinary signal nets, once placement has given them real
channels to travel through — is exactly what a rip-up-and-reroute autorouter with proper net
ordering is good at, and hand-routing it is usually just doing the router's job slower.

## Pour, do not track, for current

If a net's job is to deliver current rather than a signal, the question "what width track"
is usually the wrong question. A pour sized to the net's own footprint, checked against a
real current/width standard (see `stackup.md`'s plane-measurement section), removes the need
to compute a track width from a chart and then hope the router respects it. Where a full pour
is not available (the net has to share a layer with routed signals), the fallback is a wide
track laid by hand at the start of the routing pass, before any router touches the board.

## Don't route the return half of a loop that already has a plane under it

If a signal layer sits directly against a reference plane, the return current for every trace
on that layer already has a low-impedance path directly beneath it — that is the point of the
plane. Explicitly routing a "return trace" alongside a signal trace on the same layer, when a
plane is already doing that job one layer away, adds a second, higher-impedance return path in
parallel with the plane and can do more harm than good by giving return current somewhere
worse to flow. Route the signal; trust the plane; only add an explicit return conductor where
there genuinely is no reference plane to rely on.

## Bringing wide copper into fine-pitch packages

A wide feed track narrowing down to meet a fine-pitch package pad is often unavoidable, but do
it deliberately: neck the width down close to the pad rather than routing the full width in,
and if two adjacent pins carry the same net, bring the wide copper to *both* of them rather
than routing one pin wide and tying the other to it with a thin jumper. The thin jumper is the
one that fails a current check later and is easy to miss because the net "is connected."

## Taking a feedback tap from the far end of a component, not the near end

For a compensation or feedback tap off a passive (a sense resistor, a filter capacitor), take
the tap from the terminal that is electrically downstream of the thing being measured, not
whichever terminal happens to be closer to the tap's destination on the board. A tap taken
from the "convenient" end measures the wrong node — it includes whatever drop happens across
the component and the copper before it — and the error is invisible until the board is
characterized, not before.

## Put a differential pair on a layer nothing else uses, if you can afford to

A differential pair's segregation from other signals is a *rule* if it shares a layer with
everything else (keep-out distance, routing-order priority, hoping the router respects both).
It is a *structural fact* if the pair gets a layer to itself, or a layer with nothing else
routed near it. Structural beats enforced: a buried layer that carries only the pair (plus
whatever plane references it) cannot have another net routed across it by mistake, because
there is no mechanism by which that could happen. Spend a layer on this when the stack allows
it; it removes an entire category of review from every future change.

## Kelvin taps and loop area are placement problems wearing a routing costume

The single most generalisable point in this file: by the time you are asking "how do I route
this trace to keep loop area small" or "how do I route this Kelvin tap correctly," the
question has usually already been lost. There is no good route for a 35 mm compensation trace
— the fix was never available at the routing stage, because the parts were placed too far
apart to route it short in the first place. If a net has an electrical requirement on its
*geometry* (loop area, tap point, coupling), that requirement has to be satisfied by where the
parts sit, checked before routing starts, not discovered as a routing complaint afterward.
