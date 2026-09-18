# Datasheets still needed

Manufacturer sites block automated fetching from this project — downloading the PDF yourself and
dropping it in this directory is what has worked every time. PDFs, PNGs and text extractions here
are **gitignored**; only this file and `README.md` are tracked.

**Last reconciled against the folder contents: 2026-09-18**, after the owner supplied six files.
Full read-out of what each one settled is in `../docs/part-selection.md`, "Parts selected 2026-09-18".

---

## Blocking — nothing

**Every electrical part on the blocking list is now chosen.** L2, the last one, is the **Würth
WE-CMBNC 7448031002** (`wurth_we-cmbnc_7448031002.pdf`) — nanocrystalline, 2 mH, 10 A,
**6.3 mΩ max per winding**, **AEC-Q200 Grade 1**. With L1 = IHLP-4040DZ-01 at 1.5 µH the pair is
**18.40 mΩ against F4's 22 mΩ ceiling — a 16.4% margin**, 0.90 W, night total ~2.70 W.

> **Any substitution anywhere in the feed path must still be re-checked against the 22 mΩ sum.**
> The margin is comfortable now, not infinite: the two ferrite alternatives considered
> (Bourns PM3700-10-RC, Coilcraft CG3885-AL) are both 8.0 mΩ per winding and would take the pair
> back to 21.80 mΩ — a 0.9% margin.

> **Two items to confirm before ordering** (flagged, not assumed): whether the 6.3 mΩ is **per
> winding** — the conservative reading used above; Würth does not state it, Bourns and Coilcraft
> both do — or the total; and the **derating curve** at the 65 °C internal ambient, since the 10 A
> is specified at 20 °C.

## Blocking Task 9 — a document, not a part

| What | Why it is needed |
|---|---|
| **Espressif ESP32 Hardware Design Guidelines** | The **antenna keep-out zone**. The module datasheet marks the zone on its pin diagram but gives **no dimensions**, deferring explicitly to *Hardware Design Guidelines > Positioning a Module on a Base Board*. This is a layout constraint — board-edge placement and copper keep-out — so Task 9 cannot finalise placement without it. *(It is no longer needed for the EN reset RC: the module datasheet itself confirmed R = 10 kΩ / C = 1 µF.)* |

## Medium / low — for the BOM, not blocking

| Part | Why |
|---|---|
| **BAT54** (D8–D21, fourteen) | V_F at the clamp point and, more importantly, **reverse leakage at 3.3 V over temperature** — twelve sit across the RGB sense nodes where leakage biases the reading |
| **D1** 12 V Zener, **D3** 40 V Schottky, **C3** 220 µF, **F1** blade fuse holder | No part numbers; needed for the BOM and footprints. **C3 must be 63 V, not 50 V** — `smbj.pdf` gives the SMBJ24A an **8/20 µs clamp of 50.6 V**, which leaves a 50 V part no margin (see part-selection.md, "Correction 2") |
| **MMBT3904** (Q2, Q3) | Generic jellybean; any vendor's datasheet will do |
| **Automotive-grade IHLP** for L1 | `ihlp-4040dz-01.pdf` is the **Commercial** series — no AEC-Q200. Electrically it is the right part; for a vehicle, order the automotive variant of the same package |


---

## Recently closed — do not re-source these

| Ref | Part chosen | Closed by |
|---|---|---|
| **L1** input inductor | **Vishay IHLP-4040DZ-01**, **1.5 µH — required, not merely preferred** (5.80 mΩ max, Isat 27.5 A) | `ihlp-4040dz-01.pdf` |
| **L2** input CM choke | **Würth WE-CMBNC 7448031002** — nanocrystalline, 2 mH, 10 A, **6.3 mΩ max/winding**, **AEC-Q200 Grade 1**, through-hole. *Chosen 2026-09-19 over the Bourns PM3700-10-RC and Coilcraft CG3885-AL, both 8.0 mΩ ferrite and neither AEC-qualified* | `wurth_we-cmbnc_7448031002.pdf` |
| **L4 / L5** buck inductors | **Coilcraft XAL7070-223ME**, 22 µH, 39.69 mΩ max, Isat 6.3 A | `xal7070.pdf` |
| **L6** CAN choke | **TDK ACT45B-510-2P-TL003**, 51 µH, AEC-Q200 | `cmf_automotive_signal_act45b_en.pdf` |
| **D6 / D7** CAN ESD | **Nexperia PESD2CANFD24U-T** — one SOT23 part replaces both | `PESD2CANFD24U-T.pdf` |
| **D4** boost rectifier | **Vishay SS5PH102**, 100 V / 5 A | `ss5ph102.pdf` |
| **D2** input TVS | **SMBJ24A** — row 6.2 closed | `smbj.pdf` |
| **U7** PCA9685 | **PCA9685PW/Q900** (the AEC-Q100 variant), TSSOP28 | `PCA9685.pdf` |
| **U5** ESP32 module | **ESP32-WROOM-32E-N8** confirmed, EN reset RC verified, pin table cross-checked | `esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.pdf` |

## 3D models worth sourcing (Task 8/9, enclosure fit)

KiCad ships footprints and STEP models for nearly everything now selected — including
`RF_Module:ESP32-WROOM-32E`, `Inductor_SMD:L_Vishay_IHLP-4040`, `Package_TO_SOT_SMD:SOT-23`,
`Package_SO:TSSOP-28_4.4x9.7mm_P0.65mm` and `Package_SO:Infineon_PG-TSDSO-14-22`. These are the ones
it cannot have:

- **ESP32-WROOM-32E module** — tall, and its antenna end dictates a keep-out plus board-edge
  placement. Espressif publish a STEP model
- **TE Superseal 1.0** 4-way (J3–J6) and 2-way (J8); **TE Superseal 1.5** 3-way (J1, J7) — panel
  penetration positions and mating clearance (§9.1). TE publish STEP per part number
- **Panel-mount ATO/ATC fuse holder** (F1) — one of the nine penetrations
- **Würth WE-CMBNC 7448031002 (L2)** — **DONE.** The vendor SamacSys footprint and STEP model are
  installed as `footprints/mccan.pretty/Wurth_WE-CMBNC_7448031002.kicad_mod` and
  `3dmodels/Wurth_WE-CMBNC_7448031002.stp`. Pads verified against the datasheet: four through-hole
  pads, **7.5 × 10.7 mm pattern, ⌀1.3 mm drills**. Body **23.0 × 17.0 mm** in the board plane
  (courtyard 25.0 × 19.65), and it stands **~23–24 mm above the PCB** — **double either ferrite
  alternative, and the constraint to check against the enclosure lid (§9)**
- **TDK ACT45B** — no KiCad footprint exists for it; `L_CommonModeChoke_Coilank_ACM4532` is the right
  size class but **its land pattern must be checked against the ACT45B drawing before use**
