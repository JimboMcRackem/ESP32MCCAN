# Harness Specification

**Authority:** `../../docs/superpowers/specs/2026-09-11-esp32-mccan-pcb-hardware-design.md` §2.2, §4.1, §4.4, §5.3, §7.2, §9.1, §9.2
(Revised 2026-10-18 for the phase-A board: spec `../../docs/superpowers/specs/2026-10-17-emarked-module-redesign-design.md` §3.1, §4.1.1 supersedes the figures below. Revised 2026-11-14 for the aux stage and the plan4 layout: `../../docs/superpowers/specs/2026-11-13-aux-stage-design.md`, `../../docs/superpowers/specs/2026-11-13-board-layout-phase-b-design.md`.)

**Status:** wire gauges and pinouts are derived and final. Items marked **[TO CONFIRM]** need a
catalogue lookup or a measurement on the vehicle; no part numbers have been invented.

---

## 1. Wire gauge per circuit

> **REVISED 2026-10-18 (phase-A board schematic).** The RGB strings, the Denali pair and the
> ignition wire are gone with the plan3 board. The currents below are spec §3.1 and §4.1.1; the
> 22 AWG figure is set by terminal range and mechanical robustness, not by current.

Use **automotive-grade TXL or GXL** (thin-wall, cross-linked, 125 deg C) -- not hookup wire.

| Circuit | Current | Gauge | Notes |
|---|---|---|---|
| **Feed A**, + and return (J1) | **≈ 0.87 A** worst case | **18 AWG minimum** | Ten signal channels + logic; no pod since the aux stage (aux spec A10). Behind a ≈ 2 A harness fuse |
| **Feed B**, + and return (J9) | **6.4 A** (both pods, 3.2 A each) | **1.5 mm² (≈ 16 AWG)**, the J9 pad size **[TO CONFIRM]** against the fuse | Both pods (aux spec). To the bike's 15 A aux 3 through a **10 A** harness fuse |
| Front shared return (J3 pin 5) | **160 mA** worst case | **22 AWG** | Two modules at 0.08 A each |
| Rear shared return (J4 pin 4) | **200 mA** worst case | **22 AWG** | Two modules at 0.10 A each. One return for the whole 7-core run |
| Signal wires, 4 front + 6 rear | 80 mA (20 mA on `RL_DRL`, `RR_DRL`) | **22 AWG** | One per function |
| Pod runs, J10 (L) and J11 (R) | **3.2 A** per pod (measured 2026-11-12) | **1.0 mm² 4-core** (the J10/J11 pad size) | + , return (`GND_B`), yellow PWM, blue (not connected). Pod returns do **not** share with signal returns |
| CAN H / CAN L | signal | **22 AWG twisted pair** | Twist is required, not optional -- see §5 |

**Fuse each feed at its own wire, not above it.** Feed A's ≈ 2 A fuse sits above its ≈ 0.87 A
worst case and above U10's 1.36–1.67 A limit; feed B's 10 A fuse sits above the pods' 6.4 A and
below aux 3's 15 A, so a harness fuse can act where the bike's cannot (aux spec A10). Fuse ratings
are **[TO CONFIRM]** against pod inrush (`docs/bench/2026-11-13-pod-inrush-procedure.md`).

**The shared returns are the one easy mistake.** Each carries two modules' worth (160 mA front,
200 mA rear), not one. The signal wires are sized by terminal range, so the return is not the
tight conductor here -- but do not "save" a wire by sharing the pod returns with them.

---

## 2. Connectors, cables and glands

> **CORRECTED 2026-09-19.** TE Superseal is a wire-to-wire series and has no board-side housing.
> Every circuit leaves the box as a soldered wire tail through a cable gland, and the Superseal
> joints are **wire-to-wire, out on the harness**.

| Run | Board ref | Pins | Cable | Pinout |
|---|---|---|---|---|
| Feed A | **J1** | 2 | 2 x 18 AWG | `FEED_P`, `GND_IN` |
| Feed B | **J9** | 2 | 2 x 1.5 mm² **[TO CONFIRM]** (§4) | `FEED_B_P`, `GND_B` |
| Front modules | **J3** | 5 | 5-core 22 AWG | `FL_DRL`, `FL_IND`, `FR_DRL`, `FR_IND`, `GND` |
| Rear modules, part 1 | **J4** | 4 | one 7-core 22 AWG cable, one gland | `RL_DRL`, `RL_IND`, `RL_BRK`, `GND` |
| Rear modules, part 2 | **J5** | 3 | (same 7-core cable) | `RR_DRL`, `RR_IND`, `RR_BRK` |
| CAN | **J8** | 2 | 22 AWG twisted pair | `CANH`, `CANL` |
| Pod L | **J10** | 4 | 4-core 1.0 mm² | `POD_L_P` (red), `GND_B` (black), `YEL_L` (yellow), blue: not connected |
| Pod R | **J11** | 4 | 4-core 1.0 mm² | `POD_R_P` (red), `GND_B` (black), `YEL_R` (yellow), blue: not connected |

### Pad row and glands (plan4 board, 140 × 100 mm)

Every tail is on the **bottom edge**, in one row, pin 1 on the left, strain-relief holes toward
the edge (`scripts/layout_pcb.py` `CABLE_ROW`):

```
 J1 feed A | J3 front | J4 rear 1 | J5 rear 2 | J8 CAN | J10 pod L | J9 feed B | J11 pod R
 1.5 mm²   | 0.5 mm²  | 0.5 mm²   | 0.5 mm²   | 0.5 mm²| 1.0 mm²   | 1.5 mm²   | 1.0 mm²
```

**Seven glands on that wall**, one per cable: feed A, front, rear (J4 + J5 are one 7-core cable,
placed adjacent so it splits only on the board), CAN, pod L, feed B, pod R. Feed B sits between
its two loads to keep both 3.2 A paths short. No two runs can share a gland, because each is its
own sheathed cable and a gland seals one jacket (below). The tails span about 122 mm of the
140 mm edge, roughly 17 mm per gland on average, so check the gland bodies against that.
**[TO CONFIRM]** with the glands bought.

**The rear run is one cable and one return, on two tails.** KiCad's `Connector_Wire` relief
footprints stop at 1x06, so the 7-conductor rear run lands on J4 (4 pins) and J5 (3 pins). They
are a single sheathed 7-core cable through a single gland, split only on the board; the one
return (spec §3.1) is J4 pin 4. Strip and dress it as one cable.

**Rear modules are Oxford EL360s (2026-11-07).** Their wires land as follows:

| EL360 wire | Function | Board pin |
|---|---|---|
| Black | Negative | J4 pin 4 (shared return) |
| Grey | Running light | `RL_DRL` / `RR_DRL` |
| Red | Brake | `RL_BRK` / `RR_BRK` |
| Yellow | Indicator | `RL_IND` / `RR_IND` |

The front modules are Oxford EL359s; their colours are not yet recorded. The current figures in
§1 are for the superseded eBay modules. The EL360 budget is 0.167 A per channel and 333 mA on
the rear return (spec §2.1), still inside 22 AWG.

**Gland sizes, cable ODs and the Superseal way-counts are [TO CONFIRM]** against the cables
actually bought; the old M12/M16 figures belonged to the RGB, Denali and PWR runs, which no
longer exist. Order for each run: **one cable gland** of the right clamp range, **sheathed
multi-core cable**, both mating housings, terminals in the correct wire-gauge range, wire seals,
and **cavity plugs for any unused cavity** -- an unplugged cavity is an IP67 leak.

### The cable must be sheathed, and this is not a detail

**A gland seals on a single round jacket.** Loose wires pushed through one gland do not seal --
the gland closes on the bundle's outline and leaves gaps between the conductors. Every run above
is therefore a **sheathed multi-core cable**. Automotive-grade sheathed cable is stiffer than
loose TXL, so allow bend radius at the gland.

Seal the **cut ends** of multi-core cable too (heatshrink or a sealing boot): a sheath will wick
water along the space between cores if both ends are left open.

### Board side: soldered tails with strain relief

J1, J3, J4, J5, J8, J9, J10 and J11 are **not connectors**. They are `Connector_Wire:SolderWire` *_Relief*
footprints: each conductor gets a plated hole plus a second, unplated hole to thread the wire
back through. **That second hole is the strain relief and it is not optional** -- nothing else
mechanically restrains these wires, and without it a pull on the cable lifts a pad off the board.

Hole sizes are set by the **largest conductor in each cable**: J1 and J9 use the 1.5 mm2
footprint (2.15 mm plated holes), J10/J11 the 1.0 mm2 footprint (1.75 mm), and J3-J5 and J8 the
0.5 mm2 footprint (1.15 mm) for 22 AWG. The strain-relief holes beside them are 3.5, 3.2 and
2.6 mm.

**Leave a service loop inside the box.** The board can only be lifted clear if there is enough
slack to pull it out with the glands slackened.

### There is no ignition wire

Ignition sense was deleted (spec §9.3 item 5, §6.2): CAN is off when the bike is off, so bus
activity is the wake source. J1 is 2-pin and the three-cavity PWR connector, its two topologies
and the R37/R38 population option are gone. A feed that dies with the ignition simply leaves the
board unpowered, which is correct.

**Terminal gauge range matters:** the terminals must accept 22 AWG on the signal runs and 18 AWG
on the feeds. Verify against the terminal datasheet before ordering, and crimp with the correct
die.

---

## 3. Corner identification — a safety-critical requirement

**The four modules' harness joints are electrically and mechanically identical, so they can be
mis-mated.** Swap front-left with front-right and **the indicators signal the wrong way**. The
firmware cannot detect this -- it has no way to know which physical corner a channel reaches. The
risk is also on the board now: J3 and J4/J5 carry both sides' wires, so a left and a right wire
swapped at the tail is the same fault.

Two mitigations, **both required**:

### 3a. Physical identification

| Corner | Colour band | Label |
|---|---|---|
| Front-left | **White** | `FL` |
| Front-right | **Yellow** | `FR` |
| Rear-left | **Green** | `RL` |
| Rear-right | **Blue** | `RR` |

Apply as coloured heatshrink bands on **both** ends of each module lead (board tail and module joint),
plus a printed or engraved label. If the connector series offers **mechanically keyed variants**,
use those instead — a key that physically refuses the wrong mate beats a colour a tired person
misreads in the dark. **[TO CONFIRM]** whether keyed variants exist in the chosen module-joint series.

### 3b. Installation self-test

Run the web app's installation self-test after any harness work. It lights **one corner at a time**
so the installer confirms each mapping against the physical bike. This falls out of the diagnostic
sweep at essentially no cost (spec §12) and is the only check that catches a mis-mate **before** it
matters on the road.

---

## 4. Power feeds

**Two** Experia aux circuits: feed A on a 5 A circuit (spec §4.1.1) and feed B on aux 3, a 15 A
circuit (aux spec; ratings **[TO CONFIRM]** on the bike). **Never join them anywhere in the
harness** -- feed B is the pods alone, and the whole point of the split is that a pod fault cannot
reach the controller.

| Feed | Carries | Worst case (10.5 V) | Harness fuse | Wire |
|---|---|---|---|---|
| **A** (J1) | ten signal channels + logic | **≈ 0.87 A** | **≈ 2 A** | 18 AWG min |
| **B** (J9) | both pods (aux 3, 15 A circuit) | **6.4 A** | **10 A** | 1.5 mm² **[TO CONFIRM]** |

(Aux spec 2026-11-13: both pods moved to feed B; R100 became 33 mΩ.) Each fuse sits above its
feed's worst case and below the circuit's rating, so it can act before the bike's fuse does. The fuses are **harness-side**, in the cable, not on the
board; feed A's board-side protection (LTC4380 U10 with Q10/Q11) and feed B's paralleled P-FETs Q13/Q14 and 24 V
TVS D25 handle reverse polarity and surge, not the cable. Reverse-polarity protection is per feed: it holds when that feed is reversed with the other feed disconnected, and when the whole harness is reversed. One feed reversed while the other is connected drives fault current through the shared return, via NT1 (a 2.0 mm net tie, sized to outlast the fuse), until the reversed feed's harness fuse clears. `GND_B` joins `GND_IN`, the connector side of choke L2, at NT1, so neither feed's return current bypasses L2's return winding. Fuse position along each run is
**[TO CONFIRM]**; nearest the supply end protects the most cable (§6).

U10's current limit, set by R100 (33 mOhm), is 1.36–1.67 A: above feed A's ≈ 0.87 A and below
its ≈ 2 A fuse (aux spec A10). Re-check it against the start-up current measured at bring-up.

**[TO CONFIRM] on the vehicle:** that the two available circuits are independently fused, and
whether either is switched with the ignition (spec §9.3 item 4a).

**[TO CONFIRM]** The Experia peripheral connector part number, for the mating half.

---

## 5. CAN tap

- **22 AWG twisted pair**, maintained as a twisted pair for the entire run. Untwisting near the
  connector degrades common-mode rejection on a bus that is already a long stub.
- **No terminator is populated on the board** (spec §7.2). The vehicle bus is already terminated and
  a third terminator would unbalance it. The footprint exists for standalone bench use only.
- Route **away from** the power feeds and the pod run.
- **[TO CONFIRM]** Tap point on the vehicle — identify a location giving reliable access to the
  bus pair. Prefer an existing connector over cutting into the loom.
- The board is **physically incapable of transmitting**: the transceiver's TXD is held recessive
  by a pull-up with no MCU connection (the GPIO link was deleted in phase A). Nothing in the
  harness changes that, and it should not be defeated.

---

## 6. Loom, routing and strain relief

- Abrasion-resistant convoluted loom or braided sleeving over **every** run
- Anchor within ~100 mm of each connector so vibration loads the anchor, not the crimp
- Respect each connector's minimum bend radius at the cable exit
- Keep all runs clear of the steering head, suspension travel, hot components and any pinch point
- Route the power feed **away from the CAN pair**

### Accepted risk: the cable from the outlet to the fuse is unprotected

The harness fuses (≈ 2 A feed A, 10 A feed B) protect the cable downstream of themselves. Anything
between the Experia outlet and the fuse is protected only by the bike's own circuit fuse: 5 A
for feed A's circuit, and aux 3's 15 A for feed B, so feed B's pre-fuse run must be sized for
15 A, not 10 A. **[TO CONFIRM]** both ratings on the bike. Mitigations, all of which the harness build must honour:

- Fit each fuse **as close to the supply end as practical**, and keep the run short
- Abrasion-resistant loom over the **entire** length, with no unsleeved sections
- Route clear of every chafe point, with anchors close enough that the cable cannot migrate
- Booted ring terminals or sealed connections at the supply end
- Inspect the run at every service interval

---

## 7. Open items

| Item | Needed to close |
|---|---|
| Experia peripheral connector part number | Vehicle inspection or Energica documentation |
| Whether the two aux circuits are independently fused / ignition-switched | Vehicle inspection (spec §9.3 item 4a) |
| Pod blue wire's role (J10.4 / J11.4, not connected) | Bench measurement (aux spec) |
| Harness fuse position and holder | Catalogue lookup, trial fit |
| Gland sizes, cable ODs, Superseal way-counts and housings, terminals, seals, cavity plugs | Catalogue lookup |
| Whether keyed module-joint variants exist | Catalogue lookup -- would supersede colour coding |
| CAN tap point | Vehicle inspection |
| Final run lengths | Trial fit once the enclosure is mounted |
