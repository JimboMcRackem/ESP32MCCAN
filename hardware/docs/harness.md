# Harness Specification

**Authority:** `../../docs/superpowers/specs/2026-09-11-esp32-mccan-pcb-hardware-design.md` §2.2, §4.1, §4.4, §5.3, §7.2, §9.1, §9.2

**Status:** wire gauges and pinouts are derived and final. Items marked **[TO CONFIRM]** need a
catalogue lookup or a measurement on the vehicle; no part numbers have been invented.

---

## 1. Wire gauge per circuit

Derived from the spec currents, with automotive derating for bundled conductors in a warm
environment. Use **automotive-grade TXL or GXL** (thin-wall, cross-linked, 125 °C) — not hookup wire.

| Circuit | Current | Gauge | Notes |
|---|---|---|---|
| **Feed, +12 V and return** (single) | **7.8 A** night / 3.9 A day | **16 AWG** | ~13 A bundled ampacity. Sized for the **night** case, not daytime |
| Denali A switched +12 V | **3.3 A** | **18 AWG** | |
| Denali B switched +12 V | **3.3 A** | **18 AWG** | |
| Denali shared ground | **6.6 A** | **16 AWG** | Carries **both** channels — sized for the pair, not one |
| RGB string +24 V feed | 0.42 A | **22 AWG** | Gauge set by mechanical robustness and terminal range, not current |
| RGB colour return (×3 per corner) | 0.14 A | **22 AWG** | Same reasoning |
| CAN H / CAN L | signal | **22 AWG twisted pair** | Twist is required, not optional — see §5 |

**The Denali shared ground is the one easy mistake here.** Both channels return through it, so it
carries 6.6 A while each positive carries only 3.3 A. Sizing it like a positive would undersize it by
half.

**Voltage drop is a non-issue on the RGB runs**, and this is where the 24 V strings pay off: 0.42 A
through 3 m round-trip of 22 AWG drops ~0.07 V out of 24 V. At 12 V the same strings would draw twice
the current for the same power and drop four times the power in the wire.

---

## 2. Connectors

**[TO CONFIRM]** — housings, terminals, seals and cavity plugs all need catalogue part numbers for
both halves. Series are fixed by the spec; the specific orderable numbers are a lookup.

| Connector | Series | Ways | Pinout |
|---|---|---|---|
| FL, FR, RL, RR | TE Superseal 1.0 | 4 | `+24V_xx`, `RET_xx_R`, `RET_xx_G`, `RET_xx_B` |
| DENALI | TE Superseal 1.5 | 3 | `DEN_A_OUT`, `DEN_B_OUT`, shared `GND` |
| **PWR** | TE Superseal 1.5 | 2 | +12 V feed, return (**one connector** — spec 4.4) |
| CAN | TE Superseal 1.0 | 2 | `CANH`, `CANL` |

Order for each: panel-mount (board side) housing, mating (harness side) housing, terminals in the
correct wire-gauge range, wire seals, and **cavity plugs for any unused cavity** — an unplugged cavity
is an IP67 leak.

**Note on Denali current sense (C1):** the board uses **one** multiplexed `IS` output with a
`DEN_DSEL` select line (spec §7.3), not one sense pin per channel. Nothing changes in the harness,
but the web app reports the two channels currents **alternately** rather than simultaneously.

**Terminal gauge range matters:** Superseal 1.0 terminals must accept 22 AWG; Superseal 1.5 must
accept 16–18 AWG. Verify against the terminal datasheet before ordering, and crimp with the correct
die.

---

## 3. Corner identification — a safety-critical requirement

**The four corner connectors are electrically and mechanically identical, so they can be mis-mated.**
Swap front-left with front-right and **the indicators signal the wrong way**. The firmware cannot
detect this — it has no way to know which physical corner a channel reaches.

Two mitigations, **both required**:

### 3a. Physical identification

| Corner | Colour band | Label |
|---|---|---|
| Front-left | **White** | `FL` |
| Front-right | **Yellow** | `FR` |
| Rear-left | **Green** | `RL` |
| Rear-right | **Blue** | `RR` |

Apply as coloured heatshrink bands on **both** the panel-side and harness-side of each connector,
plus a printed or engraved label. If the connector series offers **mechanically keyed variants**,
use those instead — a key that physically refuses the wrong mate beats a colour a tired person
misreads in the dark. **[TO CONFIRM]** whether keyed variants exist in Superseal 1.0 4-way.

### 3b. Installation self-test

Run the web app's installation self-test after any harness work. It lights **one corner at a time**
so the installer confirms each mapping against the physical bike. This falls out of the diagnostic
sweep at essentially no cost (spec §12) and is the only check that catches a mis-mate **before** it
matters on the road.

---

## 4. Power feeds

**ONE** Experia peripheral outlet, rated 10 A, with a **10 A** panel-mounted fuse.

| Mode | Load | % of the 10 A feed |
|---|---|---|
| Daytime (corners white, Denali off) | **3.9 A** | 39% |
| **Night (Denali on, front DRLs off)** | **7.8 A** | **78% — the governing case** |
| Flash-to-pass in daylight, seconds | 10.5 A | 105% — harmless; blade fuses need ~135% for minutes |

This works because the loads never coincide (spec §2.4). **78% sustained is at the upper end of good
practice** for an automotive blade fuse and is the figure to watch on the first warm-night ride. If it
ever nuisance-opens, the fix needs no hardware: the Denali maximum level is a web-app tunable, and 90%
of full brings the night total to 7.2 A (72%).

**[TO CONFIRM] on the vehicle:** that the chosen outlet genuinely sustains **7.8 A** without voltage
sag or a warm connector.

**[TO CONFIRM]** The Experia peripheral connector part number, for the mating half.

**If the second feed is ever populated** (its board footprints remain — spec §4.4), do **not** parallel
the two feeds anywhere in the harness. They are domain-split by design, and the only join is a Schottky
OR on the board onto the logic rail alone. Joining them in the harness would defeat the split and let
one outlet carry both domains.

---

## 5. CAN tap

- **22 AWG twisted pair**, maintained as a twisted pair for the entire run. Untwisting near the
  connector degrades common-mode rejection on a bus that is already a long stub.
- **No terminator is populated on the board** (spec §7.2). The vehicle bus is already terminated and
  a third terminator would unbalance it. The footprint exists for standalone bench use only.
- Route **away from** the Denali conductors, the power feeds, and any switched 24 V run.
- **[TO CONFIRM]** Tap point on the vehicle — identify a location giving reliable access to the
  bus pair. Prefer an existing connector over cutting into the loom.
- The board is **physically incapable of transmitting**: the transceiver's TXD goes through a
  do-not-populate 0 Ω link with TXD held recessive. Nothing in the harness changes that, and it
  should not be defeated.

---

## 6. Loom, routing and strain relief

- Abrasion-resistant convoluted loom or braided sleeving over **every** run
- Anchor within ~100 mm of each connector so vibration loads the anchor, not the crimp
- Respect each connector's minimum bend radius at the cable exit
- Keep all runs clear of the steering head, suspension travel, hot components and any pinch point
- Route the power feed **away from the CAN pair**

### Accepted risk: the feed runs are not fused at their source

The fuses are **on the enclosure panel**, at the far end of the cable from the supply. This was the
user's explicit decision, recorded in spec §4.1. The consequence is plain:

> **The cable run from the Experia's peripheral outlet to the enclosure carries no overcurrent
> protection.** A chafe-through to the frame anywhere along that run is not interrupted by the panel
> fuse, because the fault is upstream of it.

Mitigations that partly offset it, all of which the harness build must honour:

- Keep the run **as short as practical**
- Abrasion-resistant loom over the **entire** length, with no unsleeved sections
- Route clear of every chafe point, with anchors close enough that the cable cannot migrate
- Booted ring terminals or sealed connections at the supply end
- Inspect the run at every service interval

**A battery-end inline fuse can be added later with no board change** if this risk is reconsidered.
That option stays open permanently.

---

## 7. Open items

| Item | Needed to close |
|---|---|
| **The chosen outlet sustains 7.8 A** | **Measure on the vehicle** — 78% loading is the tight spot of the single-feed design |
| Experia peripheral connector part number | Vehicle inspection or Energica documentation |
| All connector housings, terminals, seals, cavity plugs | Catalogue lookup |
| Whether keyed Superseal 1.0 4-way variants exist | Catalogue lookup — would supersede colour coding |
| CAN tap point | Vehicle inspection |
| Final run lengths | Trial fit once the enclosure is mounted |
