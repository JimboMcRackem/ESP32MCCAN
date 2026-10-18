# Harness Specification

**Authority:** `../../docs/superpowers/specs/2026-09-11-esp32-mccan-pcb-hardware-design.md` §2.2, §4.1, §4.4, §5.3, §7.2, §9.1, §9.2
(Revised 2026-10-18 for the phase-A board: spec `../../docs/superpowers/specs/2026-10-17-emarked-module-redesign-design.md` §3.1, §4.1.1 supersedes the figures below.)

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
| **Feed A**, + and return (J1) | **2.86 A** worst case (10.5 V sag) | **18 AWG minimum** | Pod L + ten signal channels + logic (spec §4.1.1). Behind a 4 A harness fuse |
| **Feed B**, + and return (J9) | **2.48 A** worst case (10.5 V sag) | **18 AWG minimum** | Pod R alone. Behind a 3 A harness fuse |
| Front shared return (J3 pin 5) | **160 mA** worst case | **22 AWG** | Two modules at 0.08 A each |
| Rear shared return (J4 pin 4) | **200 mA** worst case | **22 AWG** | Two modules at 0.10 A each. One return for the whole 7-core run |
| Signal wires, 4 front + 6 rear | 80 mA (20 mA on `RL_DRL`, `RR_DRL`) | **22 AWG** | One per function |
| Pod run (+12 V and return per pod) | 2.17 A nominal, 2.48 A at 10.5 V | **18 AWG minimum** | **KIT-GATED: not on the board yet.** Connector, count and routing wait on the Oxford kit (spec §9.1 items 1-2). Pod returns do **not** share with signal returns |
| CAN H / CAN L | signal | **22 AWG twisted pair** | Twist is required, not optional -- see §5 |

**Fuse each feed at its own wire, not above it.** 4 A is 140% of feed A's worst
case (2.86 A) and 3 A is 121% of feed B's (2.48 A) (spec §4.1.1) and both sit below the Experia circuit's 5 A, so a harness fuse can act where
the bike's cannot. 18 AWG carries either with a wide margin.

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
| Feed B | **J9** | 2 | 2 x 18 AWG | `FEED_B_P`, `GND_B` |
| Front modules | **J3** | 5 | 5-core 22 AWG | `FL_DRL`, `FL_IND`, `FR_DRL`, `FR_IND`, `GND` |
| Rear modules, part 1 | **J4** | 4 | one 7-core 22 AWG cable, one gland | `RL_DRL`, `RL_IND`, `RL_BRK`, `GND` |
| Rear modules, part 2 | **J5** | 3 | (same 7-core cable) | `RR_DRL`, `RR_IND`, `RR_BRK` |
| CAN | **J8** | 2 | 22 AWG twisted pair | `CANH`, `CANL` |
| Pods | -- | 4 (+1) | **KIT-GATED** | not on the board; added by the kit plan |

**The rear run is one cable and one return, on two tails.** KiCad's `Connector_Wire` relief
footprints stop at 1x06, so the 7-conductor rear run lands on J4 (4 pins) and J5 (3 pins). They
are a single sheathed 7-core cable through a single gland, split only on the board; the one
return (spec §3.1) is J4 pin 4. Strip and dress it as one cable.

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

J1, J3, J4, J5, J8 and J9 are **not connectors**. They are `Connector_Wire:SolderWire` *_Relief*
footprints: each conductor gets a plated hole plus a second, unplated hole to thread the wire
back through. **That second hole is the strain relief and it is not optional** -- nothing else
mechanically restrains these wires, and without it a pull on the cable lifts a pad off the board.

Hole sizes are set by the **largest conductor in each cable**: J1 and J9 use the 1.5 mm2
footprint (1.7 mm holes) for 18 AWG, J3-J5 the 0.5 mm2 footprint (0.9 mm holes) for 22 AWG.

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

**Two** Experia aux circuits, each 5 A (spec §4.1.1): three exist and one is already in use.
**Never join them anywhere in the harness** -- feed B is pod R alone, and the whole point of the
split is that a pod R fault cannot reach the controller.

| Feed | Carries | Worst case (10.5 V) | Harness fuse | Wire |
|---|---|---|---|---|
| **A** (J1) | pod L + ten signal channels + logic | **2.86 A** (57% of 5 A, 72% of the fuse) | **4 A** | 18 AWG min |
| **B** (J9) | pod R only | **2.48 A** (50% of 5 A) | **3 A** | 18 AWG min |

Each fuse is at least 120% of its own feed's worst case (140% on A, 121% on B) and below the circuit's 5 A, so it can act before
the bike's fuse does (spec §4.1.1). The fuses are **harness-side**, in the cable, not on the
board; feed A's board-side protection (LTC4380 U10 with Q10/Q11) and feed B's P-FET Q13 and 24 V
TVS D25 handle reverse polarity and surge, not the cable. Fuse position along each run is
**[TO CONFIRM]**; nearest the supply end protects the most cable (§6).

**Known gap:** U10's current limit, set by R100 (5.6 mOhm), is about 9 A, behind a 4 A fuse, so it
cannot act. It is re-sized once pod inrush is measured (spec §9.1 item 2a).

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

The harness fuses (4 A feed A, 3 A feed B) protect the cable downstream of themselves. Anything
between the Experia outlet and the fuse is protected only by the bike's own 5 A circuit fuse.
**[TO CONFIRM]** what that is. Mitigations, all of which the harness build must honour:

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
| Pod run: connector, conductor count, gauge confirmation | **The Oxford kit** (spec §9.1 items 1-2) |
| Harness fuse position and holder | Catalogue lookup, trial fit |
| Gland sizes, cable ODs, Superseal way-counts and housings, terminals, seals, cavity plugs | Catalogue lookup |
| Whether keyed module-joint variants exist | Catalogue lookup -- would supersede colour coding |
| CAN tap point | Vehicle inspection |
| Final run lengths | Trial fit once the enclosure is mounted |
