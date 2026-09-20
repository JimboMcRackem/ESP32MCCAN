# Enclosure, Heat-Spreader Plate and Panel

**Status:** **the board outline is now known — 140 × 100 mm, four M3 holes 5 mm in from the corners
(Task 8, 2026-09-20).** Every figure below that was previously estimated against a guessed
"100 × 80 mm" board has been re-stated against the real outline, and the thermal budget has been
brought into line with the plan's current numbers.
**Thermal design decided 2026-09-12, revised 2026-09-13 (flat plate), figures corrected 2026-09-20 — see §1.**
Every item marked **[PROVISIONAL]** depends on something not yet decided; every item marked
**[TO CONFIRM]** needs a catalogue or datasheet lookup and is stated as selection criteria rather
than a guessed part number.

**Authority:** `../../docs/superpowers/specs/2026-09-11-esp32-mccan-pcb-hardware-design.md` §9.3, §9.4

> **No part numbers have been invented in this document.** Where a specific manufacturer part is
> needed, the selection criteria are given precisely enough to make the lookup mechanical. A
> fabricated part number in a document that drives an order is worse than an admitted gap.

---

## 1. Thermal design — flat plate, ≥ 150 cm²

**Decision: FLAT plate ≥ 150 cm², metal-to-metal plate-to-bracket, rubber isolators at the frame only.**

> **This supersedes the finned-plate decision of 2026-09-12.** Fins were required when the budget
> stood at 4.5 W and needed ≥ 300 cm² of effective area. The RGB load then turned out to be ~4×
> smaller than assumed (spec §2.2), and §4.2's rewrite replaced the 0.78 W P-FET with a back-to-back
> pair at 0.12 W plus a 0.27 W sense resistor. Fins remain a harmless option — they would buy a
> further ~10 K — but nothing depends on them, and the "fins must be vertical" installation
> constraint falls away with them.

### How much plate area is needed

At the steady-state worst case, natural convection (h ≈ 8 W/m²K) needs:

**Load figures, current as of 2026-09-20.** The operating modes never coincide (spec §2.4 — the owner
confirmed the loads never all occur together: daytime has the Denali lights off, night has the front
DRLs off). **Night governs at ~2.31 W**; daytime is ~1.4 W plus the inductors. The
full-white-plus-both-Denali combination occurs only during a flash-to-pass in daylight, for seconds,
and is absorbed by thermal mass.

| Effective area | Night 2.31 W (governs) | Internal at 40 °C | Daytime ~1.4 W | Verdict |
|---|---|---|---|---|
| 80 cm² (a 100 × 80 mm plate) | 36 K | 76 °C | 22 K | Fails the 65 °C target |
| 100 cm² | 29 K | 69 °C | 18 K | Still short |
| **140 cm² (the board's own 140 × 100 footprint)** | 21 K | **61 °C** | 13 K | Meets the target |
| **150 cm² — requirement** | **19 K** | **59 °C** | 12 K | Comfortable |
| 200 cm² | 14 K | 54 °C | 9 K | Ample |

**This table is what moved the plate.** The old 80 cm² footprint was sized against a board assumed to
be 100 × 80 mm; at 2.31 W it no longer clears the target. The real board is 140 × 100 mm, so a plate
covering the board's own footprint does — see "Which wall the plate is" below.

> **Correction, 2026-09-20.** Earlier revisions of this section quoted "daytime, ~4.5 W governs;
> night ~2.9 W", and a table headed "Night 1.9 W / Daytime 1.2 W" that contradicted the prose two
> lines above it. Both are wrong and both are replaced here. The plan's own amendment table records
> the same correction.

### The contradiction that is now resolved

Spec §9.3 previously made the bracket **part of the heatsink** *and* **rubber-isolated from the
frame**. Rubber is a thermal insulator, so the vibration isolation destroyed the conduction path the
thermal argument depended on. Both could not hold.

**Because the plate now carries the whole thermal load by itself, the frame is no longer needed as a
heatsink — so the vibration isolation survives intact.** The conflict dissolves rather than being
traded away.

### Specification

| | Value |
|---|---|
| Plate type | **Flat aluminium plate** forming one wall (a finned extrusion is optional, not required) |
| Footprint | **≥ 140 cm², i.e. the board's own 140 × 100 mm** — see the open decision below |
| **Effective area — requirement** | **≥ 150 cm²** → ~59 °C at 40 °C ambient |
| Effective area — minimum acceptable | ≥ 140 cm² → ~61 °C, meets the target with little margin |
| Base thickness | ≥ 3 mm, for flatness under fastener load and in-plane spreading |
| Fin orientation, *if* fins are fitted | **VERTICAL in the installed attitude** — see below |
| Material | Aluminium, 6063 extrusion (typical for finned profiles) or 6082/6061 if machined |

Expressed as an area requirement rather than a named profile, so any extrusion meeting it qualifies.
**[TO CONFIRM]** the specific profile and its published surface area.

### Which wall the plate is — OPEN, and it needs a decision

**This is a live conflict, surfaced by Task 8's placement and not yet resolved.** Three things now
point at different walls:

1. **Spec §9.1 puts the plate on the wall *opposite the panel*** — an edge wall, 140 mm or 100 mm
   long and only as tall as the box is deep.
2. **The gap pad contacts B.Cu** (§3, and the board's own fab note). Assembly is single sided
   precisely so the bottom is bare copper. A gap pad only works between two roughly parallel faces,
   so the plate it presses against has to be **parallel to the board** — the base or the lid, not an
   edge wall.
3. **An edge wall cannot be 140 cm².** The board is 1.6 mm thick with a ~24 mm tallest part (L2); an
   edge wall large enough to host the plate would need the box to be roughly 100 mm deep, three
   times the height the board actually needs.

**Recommendation: the plate becomes the BASE** — the face the board lies over — sized to the board's
own 140 × 100 mm footprint, ~140 cm². That meets the 65 °C target on its own, reaches the 150 cm²
requirement once the bracket's contribution is counted, makes the gap-pad geometry in §3 mean
something, and leaves the panel wall and the antenna wall both free.

**The antenna does not block a base plate, but it does constrain its extent.** U5 sits on the
right-hand board edge with its antenna end overhanging: the keep-out runs to **x = 174.75 mm in board
coordinates, 14.75 mm beyond the board's own 160 mm edge** (this overhang is Espressif's preferred
arrangement — see §2 item 5a). The gap-pad patches stop at **x = 98 mm**, so a base plate cut back to
x ≈ 105 mm sits **more than 55 mm** from the antenna, far outside the 15 mm Espressif asks for. But a
plate cut back that far is 85 × 100 mm ≈ **85 cm²**, which is below even the minimum acceptable area.

**What needs deciding — the trade is antenna margin against plate area:**
- **(a)** full 140 × 100 mm base plate, accepting metal under the antenna end, **or**
- **(b)** full plate with only the antenna corner notched out (keeps most of the area, costs a
  machining step), **or**
- **(c)** plate cut back to ~105 mm and the shortfall made up by fins or by counting the bracket.

**(b) is the recommendation** — it is the only one that keeps both the area and the 15 mm clearance.

**Spec §9.1 has to be amended either way**: it currently says the plate is the wall opposite the
panel, and that is not compatible with a gap pad on B.Cu.

### Fin orientation, if fins are fitted

Fins are optional (§1). If they are fitted they must run **vertically** once installed, so convection
forms a chimney between them. Mounted with fins horizontal they trap air and much of the added area
stops contributing. Record the intended mounting attitude alongside the bracket drawing.

### Mounting interfaces

- **Plate → bracket: metal-to-metal**, thermal compound at the interface. The bracket contributes
  spreading area as *bonus margin*, not as something the design depends on.
- **Bracket → frame: rubber isolators.** Vibration decoupling preserved; nothing thermal is lost.

### Gap pad — not the bottleneck

**~0.75 K** across the **1358 mm²** the board actually presents (§3, measured from Task 8's
placement) of 1.5 mm, 2 W/mK material, at the **~1.35 W** that reaches it through the thermal vias.
The constraint was always the plate's external convection, never the pad.

**Note what the pad does *not* carry.** Only parts with an exposed paddle full of thermal vias couple
into it: U9 (PROFET), U3 (boost controller), U1 and U2 (the buck regulators) and D4's tab. **L2, the
single largest heat source at 0.78 W, is a through-hole common-mode choke with no paddle** — its heat
leaves through its own pins into the board copper and then into the air, not through the gap pad. So
the pad sees ~1.35 W while the plate must still be sized for the full ~2.31 W.

---

## 2. Enclosure

**[TO CONFIRM]** Polycarbonate or ABS, IP67, with a machinable wall for the heat-spreader plate.

Selection criteria, in priority order:

1. **Internal dimensions** must clear the board plus the internal cable service loop. The board is
   **140 × 100 mm** (Task 8), tallest part ~24 mm (L2, the Würth common-mode choke). **The 25–40 mm
   of connector mating depth is gone** (glands, §5 below), and is replaced by a smaller but real
   allowance: enough slack on seven soldered tails to lift the board clear with the glands
   slackened, since nothing unplugs any more.
2. **One face large enough for the plate's footprint** — **140 × 100 mm**, i.e. the board's own
   outline. Per §1 this is expected to be the **base**, not an edge wall; confirm when the open
   decision in §1 closes.
3. **The plate face and the antenna must not shadow each other.** With a base plate this is a
   clearance question rather than a choice of walls: see §1's three options. The antenna overhangs
   the board's right-hand edge and needs 15 mm clear in every direction (item 5a).
4. **Plastic elsewhere, not metal** — the ESP32-WROOM-32E uses its onboard antenna, so the remaining
   walls must be RF-transparent (spec §9.3). This is why a diecast aluminium box was rejected.
5a. **ANTENNA CLEARANCE — 15 mm in all directions. ADDED 2026-09-19, and it may be the
   binding constraint on this enclosure.** Espressif's *ESP32 Hardware Design Guidelines → PCB
   Layout Design* states: **"A clearance of at least 15 mm is recommended in all directions"**
   around the PCB antenna inside the end-product housing.

   The module is 18 mm wide and its antenna area is **18.0 × 6.19 mm** (module datasheet Figure
   12). Fifteen millimetres clear on every side makes a keep-clear volume roughly **48 mm across
   and 15 mm deep** that must contain **no PCB, no metal, no cable, no gland body and no plate**.

   **Task 8 has now placed it.** U5 is at (147, 72) rotated 270°, and the board-level keep-out —
   copper, board material and plate alike — is **x 153.56 to 174.75 mm, y 48.00 to 96.00 mm**, i.e.
   **21.2 × 48.0 mm, overhanging the board's 160 mm edge by 14.75 mm**. Espressif **explicitly
   forbids** the alternative: *"the module should not be placed in the center of the board with
   clearance created by hollowing out on all four sides."* Board-edge overhang is their preferred
   arrangement and is what the board does.

   **Still to check against the chosen box:** that 15 mm of air, not plastic wall thickness, sits
   beyond that rectangle on the +x side and above/below it.

5. **Panel area** for **eight** penetrations (§4). **REVISED 2026-09-19**, count corrected
   2026-09-20 — two changes, both of which shrink this:
   - The seven "Superseal panel cutouts" **never existed**: Superseal is a wire-to-wire series
     with no panel-mount housing. Those seven become **cable glands** — 5 × M12 and 2 × M16.
   - The blade-fuse holder is gone; F1 is now a **board-mounted eFuse** (spec §4.1).

   Gland field, allowing spanner access: **4 × M12 corners in one row ≈ 96 mm**, then
   **M12 CAN + M16 Denali + M16 PWR ≈ 78 mm** in a second, plus the vent — roughly
   **100 × 70 mm** of wall.

   **The glands must stack in two rows; the board's connectors do not.** The board puts all seven
   pigtails in a single row spanning ~123 mm of one edge, but a seven-gland row is
   **≈ 143 mm** (5 × M12 + 2 × M16 with spanner access) and will not fit a 140 mm wall. This is
   harmless — these are solder-wire pigtails, not panel connectors, so the tails simply fan out
   inside the box on their way to two rows of glands. It is recorded because the panel drawing and
   the board's connector edge are *not* a one-to-one map, and someone will otherwise assume they are.

   **The bigger gain is not area, it is that there is no mating envelope.** A panel connector
   needs 25–40 mm of clear space in front of its face for the plug and its cable bend; a gland
   needs only the cable's bend radius. That envelope was what made the old estimate the binding
   constraint on enclosure length.

   **Also confirm jointly satisfiable:** spec §9.1 puts the plate on the wall *opposite the
   panel*, item 3 here wants it clear of the antenna, and §4 forbids penetrations in the antenna
   wall. Three constraints on a six-face box. **§1's base-plate recommendation is what makes them
   satisfiable** — it takes the plate off the wall set entirely, leaving the panel and the antenna
   on opposite edge walls with four faces spare. That is not yet ratified; §1 carries the decision.
6. IP67 with a gasketed lid, and lid screws accessible after installation.

Candidate families known to offer IP66/67 polycarbonate boxes in this size class: Hammond 1554/1555,
Fibox, Bopla, Polycase. **Exact part number and internal dimensions require a catalogue lookup** —
not guessed here.

---

## 3. Heat-spreader plate and gap pad

**Plate** — flat plate per §1 (a finned extrusion is optional). Dimensions follow Task 8's outline:
- Material: aluminium — 6082/6061 if machined, 6063 extrusion for a finned profile
- Base thickness: **3 mm minimum** for flatness under fastener load and in-plane heat spreading
- **Footprint 140 × 100 mm**, expected to be the **base**; see the open decision in §1
- Fins, if fitted, vertical in the installed attitude (§1)
- Replaces one face; sealed with a gasket in a machined groove, or a compressible gasket under a
  flange
- Fastener pattern: M3 or M4 at ≤40 mm pitch around the perimeter, so gasket compression is even.
  Torque to the gasket manufacturer's compression spec — **[TO CONFIRM]** with the gasket choice;
  do not over-torque a plastic boss.

**Gap pad** — this part of the thermal path *does* close:
- Silicone gap pad, thermal conductivity **≥2 W/mK**, thickness **1.5 mm** nominal, compressible to
  ~1.0 mm
- **Contact area: two patches, 1358 mm² total**, measured from Task 8's placement and drawn on the
  board's `Cmts.User` layer as dashed rectangles labelled with their sizes:

  | Patch | Board coordinates | Size | Area | What it covers |
  |---|---|---|---|---|
  | **TIM-A** | x 64–98, y 23–58 | 34 × 35 mm | 1190 mm² | D4's tab, U3's paddle, U1 and U2's paddles, L3 alongside |
  | **TIM-B** | x 69–83, y 82–94 | 14 × 12 mm | 168 mm² | U9, the PROFET |

  Two patches rather than one because the thermal group's bounding box is 73 × 67.5 mm ≈ 4900 mm² —
  mostly empty board. The patches are sized to where the thermal vias actually are.
- **The pad contacts B.Cu.** Assembly is single sided and the bottom is left bare on purpose. The
  stitching vias inside the patches are tented no differently from the rest of the bottom side.
- Computed drop across the pad: **~0.75 K** at ~1.35 W through 1358 mm² of 1.5 mm / 2 W/mK material.
  Negligible — the pad is not the bottleneck. The bottleneck is the plate's external convection (§1).

> **Corrected 2026-09-20.** This section previously read "the Task 8 thermal group (boost FETs, boost
> inductor, the single P-FET) — estimate ~1000 mm²". There are **no boost FETs** (U3 is an integrated
> switcher) and **no P-FET** (§4.2's rewrite replaced it with a back-to-back pair). The area is now
> measured, not estimated.

---

## 4. Panel layout

**Eight penetrations.** Corrected 2026-09-20 from "nine": the ninth was a blade fuse holder, and F1
is now a board-mounted eFuse (spec §4.1). Positions follow Task 8, which owns the connector-edge
ordering (controller Ruling 3 — this document matches the board, not the reverse).

| # | Penetration | Board ref | Notes |
|---|---|---|---|
| 1 | **PWR** (single feed) | J1 | Superseal 1.5 **3-way** — IGN_IN, FEED_P, GND_IN. Gland **M16** |
| 2 | Denali | J7 | Superseal 1.5 3-way. Gland **M16** |
| 3 | CAN | J8 | Superseal 1.0 2-way, sited away from the power connector. Gland **M12** |
| 4–7 | Corner connectors FL, FR, RL, RR | J3, J4, J5, J6 | Superseal 1.0 4-way; must be **distinguishable** — see `harness.md` §3. Glands **M12** |
| 8 | Pressure-equalisation vent | — | §5 |

**Board-edge order, left to right (Task 8):** **J1 (PWR), J7 (Denali), J8 (CAN), J3, J4, J5, J6**,
spanning ~123 mm. **J2 is not a penetration** — it is the 6-pin programming header, reached with the
lid off, and it sits at the right-hand end of the same edge.

> **Corrected 2026-09-20.** PWR was listed as "Superseal 1.5 **2-way**"; the netlist has three
> conductors on J1 (IGN_IN, FEED_P, GND_IN), so it is **3-way**. The blade fuse holder row is
> deleted. **There is no panel-mounted fuse** — the accepted-risk note in `harness.md` §6 about
> owner-chosen panel fusing no longer applies to this build and should be re-read in that light.

**No second feed connector.** The second feed exists only as unpopulated board footprints, so
restoring it later needs one drilled hole rather than a PCB respin.

**Layout rules:**
- Keep the CAN gland away from the power gland
- Group the four corner glands, ordered to match the board's connector edge where the two rows allow
  (see §2 item 5 — seven glands do not fit one 140 mm row)
- Maintain the gasket land and minimum wall between adjacent cutouts per the gland datasheets
  **[TO CONFIRM]**
- **No penetration in the wall facing the ESP32 antenna**, and no metal there

---

## 5. Pressure-equalisation vent

**[TO CONFIRM]** A breathable membrane vent (Gore-type or equivalent), panel-mounted.

**Why it is not optional:** a sealed enclosure that heats and cools pumps air past its seals, and
eventually draws moisture *through* them. The vent equalises pressure while blocking liquid water,
and is what makes an IP67 rating hold over years rather than months.

Mount on a **sheltered face, pointing downward or sideways** — never upward where standing water
collects on the membrane.

---

## 6. Mounting

- Plate to bracket: **solid metal-to-metal** contact with thermal compound or a thermal pad, so the
  bracket contributes to heat spreading
- Bracket to frame: **rubber isolators** for vibration — see §1, this is the interface where the
  thermal/vibration conflict lives
- Bracket material: steel or aluminium, stiff enough not to resonate; no large unsupported spans
- Orientation: glands and vent **downward or sideways**, never upward
- Board to enclosure: **four M3 holes, 5 mm in from each corner** of the 140 × 100 mm outline
  (Task 8)

---

## 7. Conformal coating

**[TO CONFIRM]** Acrylic or silicone conformal coating. Acrylic is easier to rework; silicone
tolerates temperature better and is kinder over thermal cycles.

**Mask before coating — every one of these:**

| Must be masked | Why |
|---|---|
| All connector solder pads and tails | Coating is an insulator; a coated joint is an open circuit |
| Programming header J2 (3V3, GND, TXD0, RXD0, EN, IO0) | Needed for flashing |
| All test points | Needed for bring-up (`bring-up.md`) |
| **ESP32 antenna keep-out** (x 153.56–174.75, y 48.00–96.00) | Coating over the antenna detunes it — the same reason potting was rejected |
| Pressure-equalisation vent | Coating would seal the membrane and defeat it |
| **Gap-pad contact patches on B.Cu** — TIM-A and TIM-B (§3) | Coating adds thermal resistance exactly where it hurts |

Note the last two: both are cases where coating would silently destroy a feature designed in
elsewhere. Both are drawn on the board's `Cmts.User` layer so the coating house can see them.

---

## 8. Open items carried

| Item | Needed to close |
|---|---|
| ~~Thermal design~~ **RESOLVED 2026-09-12/13** | Flat plate, metal-to-metal plate-to-bracket, rubber at the frame. Remaining: pick a plate or profile meeting **≥ 150 cm²** |
| **Which face the plate is — OPEN** | §1. The gap pad contacts B.Cu, so the plate must be parallel to the board; spec §9.1 says the wall opposite the panel. **Needs a decision, and a spec amendment either way.** |
| ~~Board outline~~ **RESOLVED 2026-09-20** | 140 × 100 mm, M3 at 5 mm from each corner (Task 8) |
| ~~Thermal group area~~ **RESOLVED 2026-09-20** | 1358 mm² in two patches — §3 |
| Enclosure part number and internal dimensions | Catalogue lookup against 140 × 100 mm + ~24 mm tallest part + the antenna's 15 mm halo |
| Plate part number, or drawing if machined | Catalogue lookup against the **≥ 150 cm²** requirement, once §1's face decision closes |
| Gasket and fastener torque | Follows the gasket part choice |
| Vent part number | Catalogue lookup |
| Gland cutout diameters and minimum spacing | Gland datasheets (5 × M12, 2 × M16) |
| `harness.md` §6 | Still describes an owner-chosen panel fuse holder that no longer exists — §4 |
