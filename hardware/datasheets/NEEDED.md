# Datasheets still needed

Manufacturer sites block automated fetching from this project — downloading the PDF yourself and
dropping it in this directory is what has worked every time. PDFs, PNGs and text extractions here
are **gitignored**; only this file and `README.md` are tracked.

**Last reconciled against the folder contents: 2026-09-19**, after the owner supplied six files.
Full read-out of what each one settled is in `../docs/part-selection.md`, "Parts selected 2026-09-18".

---

## Blocking — TWO, both created by the 2026-09-19 move to an eFuse

> **This heading read "Blocking — nothing" until 2026-09-19.** That was true when written; the
> owner's decision to make F1 board-mounted and resettable (spec §4.1) reopened the list, and the
> route chosen for it (LTC4380 + back-to-back N-FETs, see `../docs/part-selection.md`) needs a
> pass FET that is not yet selected.

### 1. TWO 60 V N-channel MOSFETs — the one thing blocking route C

**What to type into a parametric search** (Digi-Key: *Discrete Semiconductor Products → Transistors
→ FETs, MOSFETs → Single FETs*; Mouser and LCSC have the same fields):

| Field | Value |
|---|---|
| FET Type | **N-Channel** |
| Drain–Source Voltage (V<sub>DSS</sub>) | **60 V** (accept 60–80 V; 60 V is the sweet spot) |
| **R<sub>DS(on)</sub> (Max) @ V<sub>GS</sub>** | **≤ 5 mΩ @ 10 V** — *this is the filter that matters* |
| V<sub>GS</sub> (Max) | **±20 V** |
| Current – Continuous Drain (I<sub>D</sub>) @ 25 °C | ≥ 25 A (see the warning below — this number is near-meaningless, it is just a proxy for die size) |
| Package | **PowerPAK SO-8 / SO-8FL / DFN 5×6**, or TO-263/D²PAK |
| Automotive | **AEC-Q101 qualified** |

**Search terms that work better than raw parametrics:** `"linear mode MOSFET"`, `"hot swap MOSFET"`,
`"enhanced SOA MOSFET"`, `"SOA optimized"`. Vendors who make parts for *this* job say so, and it is
the fastest way to filter out the ones that will fail the check below. Manufacturers to look at:
**Infineon (OptiMOS, including their Linear FET line), onsemi, Vishay (Siliconix), Nexperia,
Toshiba, Diodes Inc.**

#### The one check that actually decides it — and parametric search cannot do it for you

**A 60 V part at ≤ 5 mΩ is a commodity; dozens exist. The binding constraint is the linear-mode
SOA**, because the trench technology that gets R<sub>DS(on)</sub> low is exactly the technology
that makes linear-mode SOA *bad* (thermal-instability / "Spirito" effect). So:

1. Filter on voltage and resistance.
2. **Open the datasheet and find the figure titled "Forward Biased Safe Operating Area" (FBSOA)** —
   or "Safe Operating Area" with V<sub>DS</sub> on the x-axis and I<sub>D</sub> on the y.
3. **Read the 10 ms line at V<sub>DS</sub> = 12 V. It must allow ≥ 7 A** (that is the ≈ 83 W clamp
   condition: the LTC4380 holds the FET linear at ~27 V out while the input is higher).
4. **Reject any part whose SOA figure shows only pulsed lines** (100 µs / 1 ms and shorter) or that
   has no SOA figure at all. `NVMFD5877NL-D.PDF` **Figure 11 is exactly the right format** — dc,
   10 ms, 1 ms, 100 µs, 10 µs, with R<sub>DS(on)</sub>, thermal and package limits marked. Use it
   as the reference for what a usable figure looks like.

*If a candidate gives 7 A at 12 V for only ~1 ms, it is not automatically out — C<sub>TMR</sub> is
programmable and the ride-through can be shortened — but it must still outlast normal turn-on
inrush, so shorter is not free.*

#### Three specs that will mislead you

| Spec | Why it misleads |
|---|---|
| **I<sub>D</sub> continuous at T<sub>C</sub> = 25 °C** | A package-limited fiction. The NVMFD5877NL claims 17 A that way and **5–6 A** on the θ<sub>JA</sub>-referenced line — below our 7.0 A load. Always read the **θ<sub>JA</sub>** row, or P<sub>D</sub> at T<sub>A</sub> = 100 °C. |
| **R<sub>DS(on)</sub> "typ" at 25 °C** | It rises **~1.4–1.6× by 125 °C**. That is why the spec says **5 mΩ cold** when the real ceiling is 7.5 mΩ hot. Check the normalised-R vs temperature curve. |
| **"Logic level"** | **Not required, and filtering on it costs you options.** The LTC4380 drives GATE **10–14 V** above OUT (ΔV<sub>GATE</sub> 10 V min / 11.5 typ / 14 max), so read the **V<sub>GS</sub> = 10 V** column. The part only needs to *survive* 14 V, hence V<sub>GS</sub> ≥ 20 V. |

#### Why two, and why the resistance target is what it is

They go **back-to-back** (sources common, drains outward) so the body diodes oppose and the pair
blocks reverse polarity — that is how one element does reverse protection *and* overcurrent, and
why Q1 is deleted. **Two R<sub>DS(on)</sub> in series**, so the pair's budget is 15 mΩ hot against
§9.4's 65 °C target, i.e. **7.5 mΩ each hot ≈ 5 mΩ at 25 °C.** Thermal dissipation per FET is
trivial (~0.12 W at 2.5 mΩ) — **the package size is driven by the die area needed for the
resistance, not by cooling.**

> **A shortcut worth knowing.** The SOA requirement exists only because the LTC4380 clamps
> overvoltage by holding the FET linear. **The Experia's 12 V rail is DC-DC fed** — spec §6 notes
> there is no crank dip on an EV, and a DC-DC fed rail has no alternator load dump either. **If
> that is confirmed on the vehicle, the clamp never operates, and the FET can be chosen on
> R<sub>DS(on)</sub> alone.** Confirming it would make this search much easier.

### 2. An eFuse/controller decision is contingent on the above

`LTC4380.pdf` and `lm5069.pdf` are held and assessed; **LTC4380 is the chosen route**, indicated
orderable **`LTC4380HMS-2#TRPBF`** (auto-retry, MSOP-10, H-grade −40…125 °C). **No footprint
download is needed** — stock `Package_SO:MSOP-10_3x3mm_P0.5mm` is verified correct. Nothing further
is required here *except* the FET above.

---

## Previously blocking — now closed

**Every electrical part on the earlier blocking list is chosen.** L2, the last one, is the **Würth
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
| **Espressif ESP32 Hardware Design Guidelines** | **PARTLY RESOLVED 2026-09-19 — still wanted, no longer blocking placement.** The datasheet's *pin diagram* gives no dimensions, but **Figure 12 (Recommended PCB Land Pattern) does**: the **Antenna Area is 18.0 mm wide × 6.19 mm deep** from the module end face, module outline 25.5 × 18.0 × 3.1 mm. That is enough to lay out the keep-out and place the module. What the datasheet still will not give is the clearance required **around** the antenna — extra margin, ground-plane setback, whether board-edge overhang is mandatory or merely preferred — which Figure 3 Note A defers to *Hardware Design Guidelines > Positioning a Module on a Base Board*. **Overhanging the board edge is the conservative reading and costs nothing here**, so Task 8 proceeds; obtain the document before the Task 9 fabrication gate. *(Not needed for the EN reset RC: the module datasheet confirmed R = 10 kΩ / C = 1 µF.)* |

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
