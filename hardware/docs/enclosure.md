# Enclosure, Heat-Spreader Plate and Panel

**Status:** drafted from the spec before the board outline exists (Task 8 has not run).
**Thermal design decided 2026-09-12** — see §1.
Every item marked **[PROVISIONAL]** depends on the final board outline; every item marked
**[TO CONFIRM]** needs a catalogue or datasheet lookup and is stated as selection criteria rather
than a guessed part number.

**Authority:** `../../docs/superpowers/specs/2026-09-11-esp32-mccan-pcb-hardware-design.md` §9.3, §9.4

> **No part numbers have been invented in this document.** Where a specific manufacturer part is
> needed, the selection criteria are given precisely enough to make the lookup mechanical. A
> fabricated part number in a document that drives an order is worse than an admitted gap.

---

## 1. Thermal design — REVISED 2026-09-13: fins no longer required

**Decision: FLAT plate ≥ 150 cm², metal-to-metal plate-to-bracket, rubber isolators at the frame only.**

> **This supersedes the finned-plate decision of 2026-09-12.** Fins were required when the budget
> stood at 4.5 W and needed ≥ 300 cm² of effective area. The RGB load then turned out to be ~4×
> smaller than assumed (spec §2.2), total dissipation fell to **~1.9 W**, and a flat plate of
> **150 cm²** now gives 56 °C at 40 °C ambient. Fins remain a harmless option — they would buy a
> further ~10 K — but nothing depends on them, and the "fins must be vertical" installation
> constraint falls away with them.

### Why a flat plate was not an option

At the steady-state worst case, natural convection (h ≈ 8 W/m²K) needs:

**Updated 2026-09-12** for the real operating modes (spec §2.4 — the owner confirmed the loads never
all coincide: daytime has the Denali lights off, night has the front DRLs off). Steady-state worst
case is **daytime, ~4.5 W**; night is **~2.9 W**. The old "full white plus both Denali" figure of 5.7 W
occurs only during a flash-to-pass in daylight, for seconds, and is absorbed by thermal mass.

| Effective area | Night 1.9 W (governs) | Internal at 40 °C | Daytime 1.2 W | Verdict |
|---|---|---|---|---|
| 80 cm² (flat 100 × 80 mm plate) | 30 K | 70 °C | 19 K | Marginal |
| **100 cm²** | 24 K | **64 °C** | 15 K | Meets the 65 °C target |
| **150 cm² — requirement** | **16 K** | **56 °C** | 10 K | Comfortable |
| 200 cm² | 12 K | 52 °C | 7 K | Ample |

A flat plate sized to fit this enclosure delivers roughly **a quarter** of what is needed. Fins
multiply effective area 3–5× for the same footprint, which closes the case.

### The contradiction that is now resolved

Spec §9.3 previously made the bracket **part of the heatsink** *and* **rubber-isolated from the
frame**. Rubber is a thermal insulator, so the vibration isolation destroyed the conduction path the
thermal argument depended on. Both could not hold.

**Because the finned plate now carries the whole thermal load by itself, the frame is no longer needed
as a heatsink — so the vibration isolation survives intact.** The conflict dissolves rather than
being traded away.

### Specification

| | Value |
|---|---|
| Plate type | **Flat aluminium plate** forming one wall (a finned extrusion is optional, not required) |
| Footprint | ≥ 80 cm² (≈ 100 × 80 mm) **[PROVISIONAL** — confirm against Task 8's board outline**]** |
| **Effective area — requirement** | **≥ 150 cm²** → ~56 °C at 40 °C ambient |
| Effective area — minimum acceptable | ≥ 100 cm² → ~64 °C, meets the target with no margin |
| Base thickness | ≥ 3 mm, for flatness under fastener load and in-plane spreading |
| **Fin orientation** | **VERTICAL in the installed attitude** — see below |
| Material | Aluminium, 6063 extrusion (typical for finned profiles) or 6082/6061 if machined |

Expressed as an area requirement rather than a named profile, so any extrusion meeting it qualifies.
**[TO CONFIRM]** the specific profile and its published surface area.

### Fin orientation is a requirement, not a preference

The fins must run **vertically** once installed, so convection forms a chimney between them. Mounted
with fins horizontal they trap air and much of the added area stops contributing — the installation
would quietly lose the margin this decision bought. Record the intended mounting attitude alongside
the bracket drawing.

### Mounting interfaces

- **Plate → bracket: metal-to-metal**, thermal compound at the interface. The bracket contributes
  spreading area as *bonus margin*, not as something the design depends on.
- **Bracket → frame: rubber isolators.** Vibration decoupling preserved; nothing thermal is lost.

### Gap pad — not the bottleneck

~**2.9 K** across 1000 mm² of 1.5 mm, 2 W/mK material at **3.8 W** (the daytime thermal group: 3.50 W
boost + 0.30 W P-FET). The constraint was always the plate's external convection, never the pad.

### Note on worst case

The governing case is **daytime, ~4.5 W** — all four corners at full white with the Denali lights off
(spec §2.4). Night is lower at ~2.9 W despite drawing more current, because the boost carries the
whole RGB load in daytime and that loss dominates. The **~6.7 W** that a full-white-plus-both-Denali combination
implies occurs only during a flash-to-pass in daylight, for seconds, and is absorbed by thermal mass.

The design sizes for the daytime steady state deliberately, because the RGB stage is discrete MOSFETs
with no thermal protection of their own — unlike the smart switches originally specified, which would
have shut themselves down.

---

## 2. Enclosure

**[TO CONFIRM]** Polycarbonate or ABS, IP67, with a machinable wall for the heat-spreader plate.

Selection criteria, in priority order:

1. **Internal dimensions** must clear the board plus connector mating depth — **[PROVISIONAL]**
   pending Task 8. Estimate the board at 100 × 80 mm; panel connectors add 25–40 mm of mating depth
   in front of the connector face, so the internal length must exceed the board length plus that
   depth plus wire bend radius.
2. **One wall large enough** for the finned plate's **footprint** (≥ 80 cm², ≈ 100 × 80 mm — §1).
   Note this is the footprint, not the ≥300 cm² *effective* area, which the fins provide outside
   the box. The wall opening is sized by footprint alone.
3. **The finned wall and the antenna wall must be different walls** — ideally opposite. The plate is
   metal and will shadow the ESP32's onboard antenna if they share a face (Task 8 places the
   antenna edge away from the plate).
4. **Plastic elsewhere, not metal** — the ESP32-WROOM-32E uses its onboard antenna, so the remaining walls
   must be RF-transparent (spec §9.3). This is why a diecast aluminium box was rejected.
5. **Panel area** for **nine** penetrations (§4). **[TO CONFIRM]** the wall dimension this implies:
   seven Superseal 1.0/1.5 cutouts plus one blade-fuse holder plus the vent plus gasket lands need
   roughly **130 × 55 mm** of wall in two rows — which is larger than the 100 × 80 mm board estimate and is
   therefore the real size driver for the enclosure, not the board.
   **Also confirm jointly satisfiable:** spec §9.1 puts the plate on the wall *opposite the panel*,
   §2.3 here wants it *opposite the antenna*, and §4 forbids penetrations in the antenna wall. Three
   constraints on a six-face box — nobody has yet checked they can all hold at once.
6. IP67 with a gasketed lid, and lid screws accessible after installation.

Candidate families known to offer IP66/67 polycarbonate boxes in this size class: Hammond 1554/1555,
Fibox, Bopla, Polycase. **Exact part number and internal dimensions require a catalogue lookup** —
not guessed here.

---

## 3. Heat-spreader plate and gap pad

**Plate** — finned extrusion per §1 (decided). Dimensions **[PROVISIONAL]** pending Task 8:
- Material: aluminium — 6063 extrusion for a finned profile
- Base thickness: **3 mm minimum** for flatness under fastener load and in-plane heat spreading
- **Fins vertical in the installed attitude** (§1)
- Replaces one wall; sealed with a gasket in a machined groove, or a compressible gasket under a
  flange
- Fastener pattern: M3 or M4 at ≤40 mm pitch around the perimeter, so gasket compression is even.
  Torque to the gasket manufacturer's compression spec — **[TO CONFIRM]** with the gasket choice;
  do not over-torque a plastic boss.

**Gap pad** — this part of the thermal path *does* close:
- Silicone gap pad, thermal conductivity **≥2 W/mK**, thickness **1.5 mm** nominal, compressible to
  ~1.0 mm
- Contact area: the Task 8 thermal group (boost FETs, boost inductor, **the single P-FET**) — estimate
  **~1000 mm²** **[PROVISIONAL]**
- Computed drop across the pad: **~2.9 K** at 3.8 W (daytime) through 1000 mm² of 1.5 mm / 2 W/mK material.
  Negligible — the pad is not the bottleneck. The bottleneck is the plate's external convection (§1).

---

## 4. Panel layout

**Nine penetrations** (single feed, decided 2026-09-12 — dropping the second feed removed its
connector and its fuse holder, taking the count from eleven to nine). Positions are **[PROVISIONAL]**
pending Task 8, which owns the connector-edge ordering (controller Ruling 3 — this document matches the
board, not the reverse).

| # | Penetration | Notes |
|---|---|---|
| 1–4 | Corner connectors FL, FR, RL, RR | Superseal 1.0 4-way panel mount; must be **distinguishable** — see `harness.md` §3 |
| 5 | Denali | Superseal 1.5 3-way |
| 6 | **PWR** (single feed) | Superseal 1.5 2-way |
| 7 | CAN | Superseal 1.0 2-way, sited away from the power connector |
| 8 | Pressure-equalisation vent | §5 |
| 9 | **Blade fuse holder, 10 A** | Sealed screw-cap, IP67 when closed |

The **10 A fuse holder** is penetration 9 above. The owner chose panel-mounted fusing; see
`harness.md` §6 for the accepted risk this carries. **No second feed connector or fuse holder** — the
second feed exists only as unpopulated board footprints, so restoring it later needs one drilled hole
rather than a PCB respin.

**Layout rules:**
- Keep the CAN connector away from the power connector and the fuse holder
- Group the four corner connectors, ordered to match the board's connector edge
- Maintain the gasket land and minimum wall between adjacent cutouts per the connector datasheets
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
- Orientation: connectors and vent **downward or sideways**, never upward

---

## 7. Conformal coating

**[TO CONFIRM]** Acrylic or silicone conformal coating. Acrylic is easier to rework; silicone
tolerates temperature better and is kinder over thermal cycles.

**Mask before coating — every one of these:**

| Must be masked | Why |
|---|---|
| All panel connector contacts | Coating is an insulator; a coated contact is an open circuit |
| Programming header (3V3, GND, TXD0, RXD0, EN, IO0) | Needed for flashing |
| All test points | Needed for bring-up (`bring-up.md`) |
| **ESP32 antenna keep-out** | Coating over the antenna detunes it — the same reason potting was rejected |
| Pressure-equalisation vent | Coating would seal the membrane and defeat it |
| Gap-pad contact area on the thermal group | Coating adds thermal resistance exactly where it hurts |

Note the last two: both are cases where coating would silently destroy a feature designed in
elsewhere.

---

## 8. Open items carried

| Item | Needed to close |
|---|---|
| ~~Thermal design~~ **RESOLVED 2026-09-12** | Finned plate, metal-to-metal plate-to-bracket, rubber at the frame. Remaining: pick a profile meeting **≥300 cm²** (target ≥350 cm²) |
| Enclosure part number and internal dimensions | Task 8's board outline, then a catalogue lookup |
| Finned profile part number and its published surface area | Catalogue lookup against the **≥300 cm²** requirement |
| Gasket and fastener torque | Follows the gasket part choice |
| Vent part number | Catalogue lookup |
| Connector cutout diameters and minimum spacing | Connector datasheets |
| Thermal group area | Task 8 placement |
