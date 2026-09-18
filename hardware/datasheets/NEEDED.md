# Datasheets still needed

Manufacturer sites block automated fetching from this project — downloading the PDF yourself and
dropping it in this directory is what has worked every time. PDFs here are **gitignored**; only
this file and `README.md` are tracked.

Raised by the Task 7 schematic review (2026-09-18). Full context in
`../docs/schematic-review.md`.

## Blocking Task 8 — no part number, and nothing local to work from

**Checked against the folder contents on 2026-09-18 before listing.** Three items that an earlier
draft of this list called blocking are **already covered by datasheets in this directory** — see
"Already covered" below. What genuinely remains:

| Ref | What | What it must satisfy | Candidates to look at |
|---|---|---|---|
| **L2** | **Input common-mode choke** | Carries the **full 7.0 A**. **DCR ≤ 7 mΩ per winding** (review F4). Automotive rated. This is the hardest of the three — a 7 A CM choke is a physically large part and may drive the board outline | Würth WE-CMBNC, TDK ACM series |
| **L6** | CAN common-mode choke | Value is a placeholder "51 µH". Needs a CAN-rated part with a real footprint and current rating | TDK ACT45B-101-2P, Würth 744232101, Murata DLW43SH101XK2 |
| **D6 / D7** | CAN bus ESD / TVS | Placeholder "24 V bidir". **A single dual-line CAN protector is preferable to two discretes** | NXP PESD2CAN, Nexperia PESD1CAN, ON NUP2105L |

### Already covered — do not re-source these

| Ref | Covered by | Candidate found |
|---|---|---|
| **L4 / L5** (buck inductors, 22 µH) | `xal7070.pdf` | **Coilcraft XAL7070-223ME** — 22 µH, DCR **34.51 mΩ typ / 39.69 max**, Isat **6.3 A**, AEC-Q200, shielded. The requirement is Isat ≥ 1.5 A, so this is comfortable |
| **L1** (input π-filter inductor) | `Panasonic_Inductor Hi Performance (ETQP_M__Y__ Series)  020626.pdf` | **Panasonic PCC-M1050M series** carries low-value parts at **3.8–5.9 mΩ** with Isat ~18–21 A in a 10.0 × 10.7 × 5.4 mm body — well inside the **≤ 8 mΩ** budget, and at the ~2.2–2.5 µH the review recommends over 10 µH. `xal7070.pdf` also has a 2.2 µH part (11.2 mΩ, Isat 19.6 A) but that **misses the 8 mΩ budget** |

> **Both candidates above are identified, not selected.** `pdftotext -layout` staggers the column
> blocks in both documents, so the part-number ↔ value alignment must be confirmed before ordering.
> Task 8 should pin them properly.

> **Why L1 and L2 matter most.** They sit in the main feed and carry the whole load. At plausible
> DCRs they would dissipate **1.0–2.0 W against a night total of ~1.8 W** — a doubling that takes
> the ≥ 150 cm² plate from a 16 K rise to ~30 K and misses the 65 °C internal target. The **22 mΩ
> ceiling for L1 plus both L2 windings** cannot be closed until **L2** is chosen.

## High priority — fitted parts with no datasheet held

| Part | Why it is needed |
|---|---|
| **NXP PCA9685** (U7) | **Not held locally at all**, despite being a fitted part. Needed to confirm EXTCLK handling when unused (currently tied to GND), A0–A5 address strapping, `~OE` behaviour and output ratings |
| **Espressif ESP32 Hardware Design Guidelines** | The EN reset RC (**R22 10 kΩ / C37 1 µF**) is recorded as **UNVERIFIED**. Espressif specify this network; it should not be guessed |
| **ESP32-WROOM-32E-N8 module datasheet** | Module footprint, the **antenna keep-out zone** (a layout constraint, not just a part fact), and a final pin-table cross-check |

## Medium / low

| Part | Why |
|---|---|
| **BAT54** (D8–D21, fourteen) | V_F at the clamp point and, more importantly, **reverse leakage at 3.3 V over temperature** — twelve sit across the RGB sense nodes where leakage biases the reading |
| **D1** 12 V Zener, **D3** 40 V Schottky, **C3** 220 µF, **F1** blade fuse holder | No part numbers; needed for the BOM and footprints. **C3 must be 63 V, not 50 V** — `smbj.pdf` gives the SMBJ24A an **8/20 µs clamp of 50.6 V**, which leaves a 50 V part no margin (see part-selection.md, Correction 2). The boost rectifier D4 is already covered by `ss5ph102.pdf` (Vishay SS5PH102, 100 V / 5 A) |
| **MMBT3904** (Q2, Q3) | Generic jellybean; any vendor's datasheet will do |

## 3D models worth sourcing (Task 8/9, enclosure fit)

KiCad ships STEP models for every standard passive, SOIC, WQFN, TSSOP and SOT package used here,
including `Package_SO:Infineon_PG-TSDSO-14-22`. These are the ones it cannot have:

- **ESP32-WROOM-32E module** — tall, and its antenna end dictates a keep-out plus board-edge
  placement. Espressif publish a STEP model
- **TE Superseal 1.0** 4-way (J3–J6) and 2-way (J8); **TE Superseal 1.5** 3-way (J1, J7) — panel
  penetration positions and mating clearance (§9.1). TE publish STEP per part number
- **Panel-mount ATO/ATC fuse holder** (F1) — one of the nine penetrations
- **L1, L2, L4, L5, L6** once chosen — **L2 in particular**, since a 7 A common-mode choke may be
  large enough to drive the board outline
