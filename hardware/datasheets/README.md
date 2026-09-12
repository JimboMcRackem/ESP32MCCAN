# Datasheets

Source documents used for the verification in `../docs/part-selection.md`. Kept so that any PASS or
FAIL verdict there can be traced back to the document it was read from.

> **The PDFs and PNGs in this folder are gitignored by default.** They are third-party copyrighted
> documents and this repository is **public** — see "Publication" below. The index itself is tracked.

## Chosen parts

| File | Part | Role | Verification |
|---|---|---|---|
| `TJA1042_CAN_transceiver.pdf` | NXP TJA1042T/3 | CAN transceiver | Rows 5.1–5.4 **PASS**. Source of the go/no-go confirmation that standby signals bus wake-up by driving RXD low (Table 4 p.5, §7.1.2). **Rev. 8 (2015), via a Farnell mirror** — nxp.com blocks automated fetch. **Rev. 11 (2023) should be diffed before ordering.** |
| `ADG706_ADG707_analog_mux.pdf` | ADI ADG706BRU/BRUZ | 16:1 analog mux for the RGB sense chain | Rows 1c.1–1c.6 **PASS**. RON 6 Ω typ / 11–12 Ω max at 3 V, leakage ≤1.5 nA, pinout and truth table confirmed. **Rev. A is a 2002 document — confirm the current analog.com revision still matches.** |
| `Littelfuse_1206L_PTC_series.pdf` | Littelfuse 1206L series | Resettable PTC, one per RGB string | Row 6.3 **PASS**, primary-sourced. |
| `PMV60ENEA_fig6_output_characteristics.png` | Nexperia PMV60ENEA | RGB low-side switching MOSFET (×12) | Row 1a.2 **PASS**. This figure *is* the evidence: the output-characteristic curve sits clearly above 0.5 A at Vgs ≤ 3.3 V. Read **qualitatively** — no precision is claimed from a graph. |
| `SMBJ24A_TVS.pdf`, `SMBJ_series_TVS.pdf` | SMBJ24A | Input transient clamp, both feeds | Row 6.2 is recorded **UNVERIFIED**. **See "Possible easy win" below — a real PDF is now present.** |

## Considered and rejected — kept as evidence

These justify the single largest design decision in the project: that the RGB output stage could not
use multichannel smart low-side switches.

| File | Part | Why it is here |
|---|---|---|
| `REJECTED_TLE8110ED_octal_low_side_switch.pdf` | Infineon TLE8110ED | **The evidence for the row 1.1 category failure.** Diagnosis code `01` is defined verbatim as "Open Load in **OFF-Mode**"; ON-mode codes cover only overload/short/overtemperature. Detection is a VDS comparator (VDSol 2.00/2.60/3.20 V, 50/90/150 mA injected pull-down) — there is **no load-current threshold at all**, so 0.14 A is unspecified rather than out of range. Also failed rows 1.6 and 1.8. |
| `REJECTED_TLE75008_octal_low_side_switch.pdf` | Infineon TLE75008 | Same category, same limitation. Confirms the failure is a property of the part class, not one vendor. |
| `REJECTED_IRLZ44N_fig1_output_characteristics.png` | Infineon IRLZ44N | Briefly selected, then **rejected by the controller**: a 55 V / 47 A **TO-220 through-hole power brick** for a 0.14 A load. Twelve would dominate the board and force through-hole assembly. Its 25 µA leakage × 12 was also what appeared to blow the sleep budget — a symptom of the wrong package, not a real problem. |
| `ALTERNATE_ADG726_ADG732_dual_mux.pdf` | ADI ADG726/ADG732 | Dual 16:1 / single 32:1. Considered, then dropped for ADG706 — the single 16:1 is the right shape. |
| `PMV30ENEA_fig6_output_characteristics.png` | Nexperia PMV30ENEA | Viable alternative to the PMV60ENEA. Useful because **PMV60ENEA is backordered at Digi-Key.** |

## Possible easy win

`SMBJ24A_TVS.pdf` is a **real 268 KB document**, yet row 6.2 in `part-selection.md` is marked
UNVERIFIED because the verifying agent reported five failed attempts to open a primary datasheet. The
file appears to have landed without being successfully read. **Opening it may close row 6.2 outright**
— it is the only remaining UNVERIFIED row on a chosen part.

## Not copied here

- **Failed downloads.** Several scratchpad files were saved with a `.pdf` extension but are ~13.9 KB
  error or block pages, not datasheets. Excluded deliberately.
- **A duplicate.** `t.pdf` was a second copy of the TLE8110ED datasheet.
- **Text extractions.** The verifying agents saved `.txt` dumps of several PDFs. Redundant where the
  PDF itself is present.
- **MC33996.** No primary datasheet was ever retrievable (NXP blocks automated fetch; distributor
  mirrors returned HTTP 410). Its rows in `part-selection.md` are labelled as product-page data.

## Publication

These are **third-party copyrighted documents** and this repository is **public**. Redistributing
vendor datasheets is common practice in hardware repositories, but some manufacturers' terms prohibit
it, so they are **gitignored by default** rather than published on your behalf.

To publish them anyway, remove the `datasheets/*.pdf` and `datasheets/*.png` lines from
`hardware/.gitignore`. To keep them private but backed up, copy the folder somewhere outside the repo.

Either way, nothing is lost locally — the files are on disk in this folder.
