# Oxford 4K pod: inrush and pulse-current measurement

**Why:** this sizes the pod high-side switches on the aux stage (feed B, aux 3).
Steady draw is already known: 3.2 A per pod at stage 5 and 12 V. What we don't
know is how high the current spikes when the switch closes, and how high the
100 Hz pulses peak. Both of these set the switch rating and its current limit.

**Kit:** FNIRSI 2C53T, bench supply, one pod with its Oxford dial, and:

| Part | Value | Notes |
|---|---|---|
| Current shunt | **0.1 Ω, 5 W or more**, low-inductance (metal-element or wirewound) | 0.1 Ω turns 1 A into 100 mV. At 3.2 A steady it dissipates about 1 W. |
| Switch | Toggle switch or 12 V automotive relay, **rated 10 A or more** | Use this to apply power. Don't use the supply's own output button (see step 2). |
| Reservoir capacitor (recommended) | 2200–4700 µF, 25 V or more, electrolytic | Fit it across the supply terminals so that a fast spike isn't limited by the bench supply. On the bike, the DC-DC converter is much stiffer than a bench supply. |
| Leads | Short and thick (1.5 mm² or more) | Long, thin leads add resistance and inductance, and the measured spike comes out lower than the real one. |

Test **one pod at a time**. The board switches each pod separately.

---

## 1. Wiring (low-side shunt)

```
 Supply +  ──┬──[ switch ]──────────── pod RED
             │                          │
           [C] reservoir               pod
             │                          │
 Supply −  ──┴──────[ 0.1 Ω shunt ]──── pod BLACK
             │                    │
       scope GND (both)      CH1 tip  (current: V ÷ 0.1 = A)

 CH2 tip on pod RED (pod voltage), ground also at Supply −
 Yellow wire → Oxford dial as normal.  Blue left open.
```

- Connect **both probe grounds to Supply −**, on the supply side of the shunt.
  The 2C53T's channels share a common ground, so a ground clip anywhere else
  would short out the shunt or the supply.
- CH1 measures the voltage across the shunt. Current = voltage × 10 (for
  example, 0.32 V means 3.2 A).
- The pod sees about 0.3 V less than the supply because of the shunt. Set the
  supply to **12.3 V** so the pod gets about 12 V.

## 2. Supply settings

- Voltage: **12.3 V**.
- Current limit: **set it to the supply's maximum**. If the supply goes into
  current limit (CC) during the spike, write that down, because it means the
  real peak is higher.
- Turn the supply output on first, then use the **switch** to apply power to
  the pod. A bench supply's own output button ramps the voltage up slowly,
  which hides the spike.

## 3. Scope settings

| Setting | CH1 (current) | CH2 (pod voltage) |
|---|---|---|
| Probe | 1X (set 1X on the probe and in the menu) | 10X |
| Coupling | DC | DC |
| Volts/div | 500 mV (= 5 A/div) to start | 5 V |

- **Trigger:** source CH2, rising edge, level **6 V**. CH2 jumps from 0 V to
  12 V the instant the switch closes, which makes a clean trigger point. Set
  the trigger position near the left so you can see a little of the time
  before the switch closes.
- **Mode:** single-shot. The scope captures once and holds the trace. Set it
  up the same way as the earlier single captures.
- **Timebase:** start at **1 ms/div**. Then repeat at **100 µs/div** to see
  the spike's shape, and at **10 ms/div** to see how long it takes to settle.
- If the CH1 peak goes off the top of the screen, increase CH1 to
  1 V/div (10 A/div).

## 4. Captures

Repeat each capture **3 times**. Between captures, leave the pod off for about
10 s so its internal capacitors discharge. A 3rd or 4th quick repeat can read
lower than the first.

| # | Dial before switching | What it tells us |
|---|---|---|
| A | **Main off** (DRL only) | The spike when the board turns the switch on with the pod dark |
| B | **Stage 5** | The worst case. The firmware sets the yellow duty *before* switching on the pod, so the pod can power up with main beam already requested. |
| C | **Stage 1** | Low-beam night mode (about 15 % duty) |
| D | Pod already powered, dial **off → stage 5** | The spike when main beam starts on a pod that is already powered (switch on, no new switch-on spike) |

For capture D, trigger on **CH1** instead: rising edge, level 0.5 V. Use
"normal" or single mode, not auto.

## 5. Pulse current (no switching)

With the pod powered and running steadily, set the trigger to **CH1 rising,
auto mode**. Use a timebase of **2 ms/div**, so one 10 ms PWM period spans
5 divisions.

- **Stage 5:** record the peak and minimum current.
- **Stage 1:** record the peak current. At 15 % duty the pulses may still
  reach nearly the full current, and that peak is what the switch sees.

## 6. What to record

| Capture | Peak (V on CH1 → A) | Time from peak until current is within 10 % of steady | Pod voltage dip (CH2 min) | Supply went into CC? |
|---|---|---|---|---|
| A1 / A2 / A3 | | | | |
| B1 / B2 / B3 | | | | |
| C1 / C2 / C3 | | | | |
| D1 / D2 / D3 | | | | |

| Pulse | Peak A | Minimum A | Steady average on the supply meter |
|---|---|---|---|
| Stage 5 | | | |
| Stage 1 | | | |

Screenshots of one B capture at 100 µs/div and at 10 ms/div are the most
useful. Save them in `hardware/Oscilliscope/` the same way as before.

## 7. Safety

- The shunt gets warm, about 1 W at stage 5. Keep each run short and keep it
  off anything that melts.
- Don't look into the pod at stage 5 on the bench. Point it at a wall.
- Never connect a probe ground to pod BLACK or pod RED. Both grounds go to
  Supply − only.
- If the supply cuts out or the switch arcs badly, stop and note it. That is a
  result in its own right.

## 8. How the result is used

- **Peak current** sets the switch's current-limit threshold, which must sit
  above the inrush peak so the switch doesn't trip on every power-up.
- **Time to settle** sets how long the switch must tolerate that peak, which
  is checked against the switch's thermal (SOA) data.
- **Pulse peak** sets the bulk capacitor on feed B and the copper width in
  the phase B layout.
- If the inrush is very large (more than about 20 A), the aux stage gets a
  soft-start instead. Firmware can't help here because the pod's own input
  capacitors cause the spike.
