# Enclosure, Heat-Spreader Plate and Panel

**Status:** drafted from the spec before the board outline exists (Task 8 has not run).
Every item marked **[PROVISIONAL]** depends on the final board outline; every item marked
**[TO CONFIRM]** needs a catalogue or datasheet lookup and is stated as selection criteria rather
than a guessed part number.

**Authority:** `../../docs/superpowers/specs/2026-09-11-esp32-mccan-pcb-hardware-design.md` §9.3, §9.4

> **No part numbers have been invented in this document.** Where a specific manufacturer part is
> needed, the selection criteria are given precisely enough to make the lookup mechanical. A
> fabricated part number in a document that drives an order is worse than an admitted gap.

---

## 1. THE OPEN PROBLEM: the thermal design does not close yet

This has to be resolved before ordering an enclosure. The spec's §9.4 budget is **~4.3 W** of
internal dissipation. For natural convection (h ≈ 8 W/m²K) the required dissipating area is:

| Dissipation | Area | Rise | Internal temp at 40 °C ambient |
|---|---|---|---|
| 4.3 W (worst case) | 80 cm² | 67 K | **107 °C — fails** |
| 4.3 W | 150 cm² | 36 K | **76 °C — fails the 65 °C target** |
| 4.3 W | **215 cm²** | 25 K | **65 °C — meets target exactly** |
| 4.3 W | 300 cm² | 18 K | 58 °C — comfortable |
| 2.0 W (typical) | 80 cm² | 31 K | 71 °C |
| 2.0 W | 150 cm² | 17 K | 57 °C |

**A flat aluminium plate of plausible size cannot do this alone.** A 100 × 80 mm plate is 80 cm²,
which at worst case puts the inside at ~107 °C — above the ESP32's 85 °C maximum and destructive to
electrolytics. The spec's claim of "~65 °C at 40 °C ambient" assumed roughly 215 cm² of effective
area, which was never checked against a real plate size.

**And there is a direct conflict inside §9.3.** It specifies the plate bolts to a metal bracket so
the bracket becomes part of the heatsink, *and* that the bracket is rubber-isolated from the frame
for vibration. **Rubber is a thermal insulator** — the isolation that protects against vibration
destroys the conduction path into the frame that the thermal argument depends on. Both cannot hold
as written.

### Options, for decision before ordering

| # | Approach | Thermal | Cost |
|---|---|---|---|
| A | **Finned plate** — extruded heatsink profile as the wall | Multiplies effective area 3–5×; closes comfortably | Custom machining of a finned extrusion, deeper package |
| B | **Larger flat plate** (~215 cm², e.g. 150 × 145 mm) | Meets the 25 K target exactly, no margin | Forces a large enclosure; may not fit the intended mounting location |
| C | **Solid metal-to-metal frame mount**, drop the rubber isolators | Frame becomes a large heatsink; best thermal result | Road vibration couples directly into the board. The Experia has no engine vibration, so this is far less severe than on an ICE bike — but it is a real trade |
| D | **Split the paths** — a flexible copper/aluminium strap for heat plus rubber mounts for vibration | Keeps both properties | Extra part, extra assembly step |
| E | **Reduce dissipation** — revisit the boost's 2.6 W, the single largest contributor | Attacks the cause | More expensive switcher or a lower-loss topology |
| F | **Accept a higher rise** — worst case (full white RGB *and* both Denali maxed) is rare | Free | Relies on the worst case genuinely not occurring; the switch ICs have no thermal protection in this design since they are now discrete FETs |

**Recommendation: A + D.** A finned plate closes the thermal case with margin and removes the
dependence on frame conduction entirely, which makes D's strap unnecessary — so in practice **A
alone**, with solid metal-to-metal plate-to-bracket contact and rubber only between bracket and
frame. That keeps vibration isolation without needing the frame as a heatsink.

**This is a decision for the user, not an agent.** It changes the enclosure order.

---

## 2. Enclosure

**[TO CONFIRM]** Polycarbonate or ABS, IP67, with a machinable wall for the heat-spreader plate.

Selection criteria, in priority order:

1. **Internal dimensions** must clear the board plus connector mating depth — **[PROVISIONAL]**
   pending Task 8. Estimate the board at 100 × 80 mm; panel connectors add 25–40 mm of mating depth
   in front of the connector face, so the internal length must exceed the board length plus that
   depth plus wire bend radius.
2. **One wall large enough** for the plate chosen in §1 (80–215 cm², decision-dependent).
3. **Plastic, not metal** — the ESP32-WROOM-32E uses its onboard antenna, so the remaining walls
   must be RF-transparent (spec §9.3). This is why a diecast aluminium box was rejected.
4. **Panel area** for nine penetrations (§4).
5. IP67 with a gasketed lid, and lid screws accessible after installation.

Candidate families known to offer IP66/67 polycarbonate boxes in this size class: Hammond 1554/1555,
Fibox, Bopla, Polycase. **Exact part number and internal dimensions require a catalogue lookup** —
not guessed here.

---

## 3. Heat-spreader plate and gap pad

**Plate** — **[PROVISIONAL]**, sized by the §1 decision:
- Material: aluminium, 6082/6061 class
- Thickness: **3 mm minimum** for flatness under fastener load and for in-plane heat spreading
- Replaces one wall; sealed with a gasket in a machined groove, or a compressible gasket under a
  flange
- Fastener pattern: M3 or M4 at ≤40 mm pitch around the perimeter, so gasket compression is even.
  Torque to the gasket manufacturer's compression spec — **[TO CONFIRM]** with the gasket choice;
  do not over-torque a plastic boss.

**Gap pad** — this part of the thermal path *does* close:
- Silicone gap pad, thermal conductivity **≥2 W/mK**, thickness **1.5 mm** nominal, compressible to
  ~1.0 mm
- Contact area: the Task 8 thermal group (boost FETs, boost inductor, both P-FETs) — estimate
  **~1200 mm²** **[PROVISIONAL]**
- Computed drop across the pad: **~2.1 K** at 3.4 W through 1200 mm² of 1.5 mm / 2 W/mK material.
  Negligible — the pad is not the bottleneck. The bottleneck is the plate's external convection (§1).

---

## 4. Panel layout

**Nine penetrations.** Positions are **[PROVISIONAL]** pending Task 8, which owns the connector-edge
ordering (controller Ruling 3 — this document matches the board, not the reverse).

| # | Penetration | Notes |
|---|---|---|
| 1–4 | Corner connectors FL, FR, RL, RR | Superseal 1.0 4-way panel mount; must be **distinguishable** — see `harness.md` §3 |
| 5 | Denali | Superseal 1.5 3-way |
| 6 | PWR A | Superseal 1.5 2-way |
| 7 | PWR B | Superseal 1.5 2-way |
| 8 | CAN | Superseal 1.0 2-way, sited away from the power connectors |
| 9 | Pressure-equalisation vent | §5 |

Plus **two panel-mount blade fuse holders** (7.5 A for Feed A, 10 A for Feed B) — the user chose
panel-mounted fusing; see `harness.md` §6 for the accepted risk this carries.

**Layout rules:**
- Keep the CAN connector away from both power connectors and from the fuse holders
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
| **Thermal design (§1)** | **User decision** — the thermal case does not close with a plausible flat plate, and §9.3's rubber-isolation requirement conflicts with its own frame-conduction argument |
| Enclosure part number and internal dimensions | Task 8's board outline, then a catalogue lookup |
| Plate dimensions | Follows the §1 decision |
| Gasket and fastener torque | Follows the gasket part choice |
| Vent part number | Catalogue lookup |
| Connector cutout diameters and minimum spacing | Connector datasheets |
| Thermal group area | Task 8 placement |
