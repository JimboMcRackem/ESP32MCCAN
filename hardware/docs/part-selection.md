# Part Selection Verification Record

Every criterion below comes from the spec. A part may be chosen ONLY if every
row for it reads PASS. Candidate families are suggestions, not decisions.

## 1. RGB output stage (REVISED 2026-09-11) — discrete MOSFET + sense chain
Replaces the octal smart low-side switches, whose row 1.1 failed category-wide
(the full superseded verification record is preserved in the Appendix at the end
of this file — it is the evidence for why the design changed). Three part classes
are verified here: the FET, the sense resistor, the analog mux. 1 ohm x 0.14 A =
140 mV at full channel current, read at 0 dB ADC attenuation (0-1.1 V range).
Classification is open (~0 mV) / working (~140 mV) / shorted (saturated) — this is
**not** precision current metering.

### 1a. Logic-level N-MOSFET (12 required) — REVISED 2026-09-12 against Rulings 11/12

**Revised candidate: Infineon IRLZ44NPbF** (55 V N-channel HEXFET, TO-220AB,
standard non-isolated package). Verified in full against the **Infineon
IRLIZ44NPbF datasheet** (isolated TO-220 Full-Pak variant, doc ref ifx1,
edition 2016-04-19/2017-04-27) — its Electrical Characteristics table and
Fig. 1/2 output-characteristic curves are the die's native data (only the
avalanche-energy and a couple of switching-time rows carry footnote 6,
"Uses IRLZ44N data and test conditions"; VGSth, RDS(on) and Qg are the
part's own measured values, not borrowed). The standard non-isolated
IRLZ44NPbF (recommended for the BOM — no isolation is needed here, and it
is the cheaper, far more common TO-220AB SKU) shares the same die and
electrical spec per that note; a human should still pull the standalone
IRLZ44N/IRLZ44NPbF datasheet once to confirm the table is identical
before board order (low risk given the explicit linkage).

Nexperia PMV60ENEA (the prior candidate) and its sibling PMV30ENEA were
re-checked against the revised criterion and both **fail** on VGS(th) max
alone — see screening table below.

| # | Required | Actual | Verdict |
|---|---|---|---|
| 1a.1 | Vds >= 40 V (24 V rail plus transients) | IRLIZ44NPbF Electrical Characteristics table, p.2: "V(BR)DSS Drain-to-Source Breakdown Voltage — 55 V min — VGS = 0 V, ID = 250 uA." Datasheet header/quick-ref box: VDSS = 55 V. | **PASS** — 55 V vs 40 V required, 15 V of real margin (unlike the prior PMV60ENEA candidate's exact 40 V with zero margin). |
| 1a.2 | **REVISED**: Vgs(th) max <= 2.0 V, AND the output-characteristic curve shows Id >= 0.5 A at Vgs = 3.3 V with Vds <= 0.5 V | **(a) VGS(th):** Electrical Characteristics table p.2: "VGS(th) Gate Threshold Voltage — Min 1.0 V, Max 2.0 V — VDS = VGS, ID = 250 uA." Exactly meets the 2.0 V ceiling. **(b) Output curve:** Fig. 1 "Typical Output Characteristics" (20 us pulse width, TJ = 25 degC), p.3, plots ID vs VDS for VGS = 2.5, 3.0, 4.0, 6.0, 8.0, 10, 12, 15 V — no VGS = 3.3 V curve is printed, but the 3.0 V and 4.0 V curves bracket it. The figure was rendered from the datasheet PDF at high resolution (PyMuPDF, 14x scale) and calibrated pixel-for-pixel against its own gridlines (log-log axes; gridlines at ID = 1/10/100/1000 A and VDS = 0.1/1/10/100 V, spaced ~429-431 px/decade both axes) and the two curves were traced by nearest-neighbour continuity from VDS ~1.3 V down to VDS = 0.5 V. Result at VDS = 0.5 V: the VGS = 3.0 V curve reads ID = 13.0 A; the VGS = 4.0 V curve reads ID = 20.4 A. Since ID increases monotonically with VGS at fixed VDS, the true VGS = 3.3 V curve lies between these two, i.e. ID is approximately 13-20 A at VDS = 0.5 V. | **PASS** — VGS(th) max = 2.0 V meets the ceiling exactly; the traced output-characteristic curve gives ~13-20 A at Vgs=3.3V/Vds<=0.5V, vastly exceeding the 0.5 A floor (26-40x margin). This is a real reading off Fig. 1 of this part's own datasheet, not an estimate from a similar part. |
| 1a.3 | Id >= 1 A continuous | Electrical Characteristics table p.2 (Full-Pak, thermally derated by the isolation layer): "ID @ TC = 25 degC, VGS = 10 V — 30 A"; "ID @ TC = 100 degC — 22 A." (The non-isolated standard IRLZ44NPbF is rated 47 A per its Digi-Key listing, higher still.) | **PASS** — 22-30 A vs 1 A required, >20x margin even at the derated Full-Pak figure. |
| 1a.4 | Total series resistance (FET + the 1 ohm shunt) keeps per-channel loss <= 50 mW at 0.14 A | Using the conservative (worst-case-low) VGS = 3.0 V curve read in row 1a.2 at VDS = 0.5 V, ID = 13.0 A: this implies RDS(on) at VGS = 3.0 V is AT MOST 0.5 V / 13.0 A = 38.5 mOhm at that operating point (an upper bound — the real VGS = 3.3 V curve draws more current at the same VDS, so its RDS(on) is lower still). Applying a generous high-temperature derate from Fig. 4 "Normalized On-Resistance vs. Temperature" (~2.2x at Tj = 175 degC vs 25 degC, read for the VGS = 10 V/ID = 41 A curve, applied here as a conservative multiplier) gives a worst-case RDS(on) ~85 mOhm. Total series R = 1 Ohm (shunt) + 0.085 Ohm (FET) = 1.085 Ohm. Power at 0.14 A: P = I^2 x R = 0.0196 x 1.085 = 21.3 mW. | **PASS** — 21.3 mW vs the 50 mW ceiling, >2x margin, using a deliberately pessimistic (upper-bound) RDS(on) derived from the datasheet's own graphs rather than an assumed "typical" number. |
| 1a.5 | Gate charge low enough to switch cleanly at 400 Hz from a PCA9685 output (25 mA sink / 10 mA source) | Electrical Characteristics table p.2: "Qg Total Gate Charge — Max 48 nC — ID = 25 A" (this is referenced to charging fully to VGS = 10 V per Fig. 6's gate-charge test, so it is a conservative/larger upper bound for only charging to 3.3 V). At the PCA9685's 10 mA source current: charge time = 48 nC / 10 mA = 4.8 microseconds. | **PASS** — 4.8 us vs a 2.5 ms period at 400 Hz is 0.19% of the period; large margin. |
| 1a.6 | In stock, multi-source | Digi-Key product page for IRLZ44NPBF (fetched 2026-09-12, live page load): **31,603 units in stock**, unit pricing $1.80 (qty 1) down to $0.6023 (qty 500), package "TO-220-3", lifecycle status **Active**. Manufacturer is Infineon (formerly International Rectifier) — a single legal manufacturer for this exact part number; multi-source (a second vendor's pin-identical part) was not independently confirmed. | **PASS** for stock/price/lifecycle at the named distributor; **UNVERIFIED** for true multi-source (single-manufacturer part number). A human should check Mouser/Arrow for the same PN and decide whether a second-source logic-level TO-220 MOSFET is wanted as a backup line item. |

### Candidate screening for 1a

| Candidate | Outcome | Evidence |
|---|---|---|
| **Infineon IRLZ44NPbF / IRLIZ44NPbF** | Selected — passes every row above | Full datasheet verified (IRLIZ44NPbF, doc ifx1) — see table above. Package is TO-220AB (through-hole), notably larger than the SOT23 originally targeted; flagged as a layout consideration for Task 3 (12 through-hole FETs vs 12 SOT23s), not a criterion failure — no row in this section constrains package/footprint. |
| **Nexperia PMV60ENEA** | **FAILS revised 1a.2** | Datasheet Table 7 "Characteristics": "VGSth gate-source threshold voltage — ID = 250 uA; VDS = VGS; Tj = 25 degC — Min 1, Typ 1.6, **Max 2.5 V**." 2.5 V exceeds the new 2.0 V ceiling, so this candidate fails outright regardless of the output-characteristic curve reading (Fig. 6 of that datasheet plots VGS = 2.4/3.0/3.5/4.5/10 V curves, which would otherwise likely pass the current half of 1a.2 by inspection, but the VGS(th) max already disqualifies it). |
| **Nexperia PMV30ENEA** | **FAILS revised 1a.2** (same gap) | Datasheet (Product data sheet, 14 Aug 2026) Table 7: "VGSth — Min 1, Typ 1.6, **Max 2.5 V**" — identical threshold spec to PMV60ENEA (same technology family, different current/RDSon rating). Fig. 6 output-characteristics there plots VGS = 2.4/2.6/2.8/3.0/4.5/10 V and shows strong current at low VDS even at VGS = 3.0 V (curve reaches ~13 A by VDS = 1 V), so the *curve* half of the criterion looks easy to meet on this part too — but VGS(th) max = 2.5 V still exceeds the 2.0 V ceiling, so it fails on that basis alone. |
| **Vishay SQS400EN** | Not re-checked | Previously found to share the same "no RDSon below 4.5 V" gap under the old criterion; not re-evaluated against the new VGS(th)-max criterion within the effort cap once IRLZ44N passed cleanly. |
| **ROHM RSF015N06FRA** | Not re-checked | Screened out previously (RDSon ~3x higher than the Nexperia parts, "4 V-drive" spec still above 3.3 V); not re-evaluated once IRLZ44N passed cleanly. |

Two Infineon parts share this data: **IRLZ44NPbF** (standard TO-220AB,
non-isolated — the BOM pick) and **IRLIZ44NPbF** (isolated TO-220 Full-Pak —
the part actually datasheet-verified above; use only if electrical isolation
from a heatsink/chassis is required, which this design does not need).

### 1b. Sense resistor (12 required)
Candidate: **Yageo RC2512FK-071RL** (2512 case, 1.0 ohm, F = 1% tolerance),
verified against Yageo "RC_L series" General Purpose Chip Resistors datasheet,
Product specification, 14-Nov-2025, V.14.

| # | Required | Actual | Verdict |
|---|---|---|---|
| 1b.1 | 1 ohm, tolerance <= 1% (tolerance sets channel-to-channel reading spread) | Datasheet Table 3 ("Electrical characteristics", RC2512 row, 1 W option): "1% (E24/E96) 1 Ohm <= R <= 10 MOhm" is an explicit tolerance/range bracket that includes 1.0 Ohm at F = 1.0% tolerance (part-number tolerance code table, Section 2). Confirmed as an orderable Yageo global part number (RC2512FK-071RL) via distributor listing. | **PASS** — 1.0 Ohm at F = 1% tolerance is a directly supported, orderable configuration. |
| 1b.2 | Power rating >= 50 mW with margin (dissipates 20 mW at 0.14 A) | Datasheet "Functional description", "Power rating": "RC2512 = 1 W, 2 W" (rated power at 70 degC). Table 3, RC2512 row confirms 1 W and 2 W options both cover 1 Ohm at 1% tolerance. | **PASS** — 1 W (1000 mW) minimum option vs 50 mW required; actual dissipation of 0.14^2 x 1 = 19.6 mW is under 2% of the 1 W rating, >50x thermal margin. |
| 1b.3 | Temperature coefficient low enough that drift does not swamp open/working/short classification | Table 3, RC2512 row: "Temperature Coefficient — 1 Ohm <= R <= 10 Ohm: +/-200 ppm/degC". Over a 100 degC swing from a 25 degC reference (e.g. to 125 degC), drift = 200 ppm/degC x 100 degC = 20,000 ppm = 2% of nominal resistance, i.e. the 1 Ohm sense resistor could read 0.98-1.02 Ohm. At 0.14 A that shifts the 140 mV nominal reading by about +/-2.8 mV. | **PASS** — a +/-2.8 mV (2%) shift is negligible against the coarse three-bin classification (open ~0 mV / working ~140 mV / shorted saturated), which needs to separate states by tens to hundreds of mV, not a few mV. |

### 1c. 16-channel analog multiplexer (1 required) — REVISED 2026-09-12, hard 3.3 V requirement

**CD74HC4067 is excluded per the task's hard requirement** (HC-family
on-resistance is uncharacterised below 4.5 V — see the prior pass's findings,
retained below for the record). **ADG706 was re-checked directly against the
new requirement and itself FAILS it** — its own datasheet's specifications
table is written only for VDD = 5 V, with no 3 V/3.3 V column at all (this
is a genuine gap in the part's own datasheet, not a search-summary error —
confirmed twice below). Two other Analog Devices low-voltage muxes were then
checked: **ADG708** (8-channel, genuinely 3 V-tabulated, but wrong channel
count) and **ADG726** (16-channel, 4 address lines — the right shape — with
strong structural evidence of a dedicated 3 V table, but exact numbers could
not be pulled from any reachable mirror inside the effort cap). **ADG726 is
the recommended part**, with the numeric RON/leakage table at 3 V left as an
open item for a human to close directly from Analog Devices.

| # | Required | Actual | Verdict |
|---|---|---|---|
| 1c.1 | 16 channels, single-ended, 4 binary select lines | ADG726 product description (Analog Devices product page, and consistently repeated across independent distributor listings — Mouser, Digi-Key, alldatasheet — fetched 2026-09-12): "monolithic CMOS 16-channel analog multiplexer that switches one of 16 inputs... determined by 4-bit binary address lines," parallel address inputs (vs. the serial-interface ADG725/ADG731 siblings). The datasheet's own table of contents (confirmed via a direct fetch of the Rev. C, 2/2021 document, radiolocman mirror) lists pin/function sections consistent with this. Exact pinout/truth table was not read from the primary PDF within the effort cap (see below). | **PASS, with a caveat** — channel count and 4-address-line structure are corroborated by multiple independent sources describing the same physical part, but the primary-source pinout table itself was not opened. A human should confirm the pinout (A0-A3, EN, 16x S pins, D) directly from the ADI datasheet before layout. |
| 1c.2 | **Specified** (not merely tolerant) for 3.3 V operation, with on-resistance tabulated at 3.3 V | ADG726/ADG732 datasheet (Analog Devices, Rev. C, 2/2021) table of contents, read directly (radiolocman mirror, fetched 2026-09-12): lists **three separate "Specifications" sections** — "+5 V Single Supply" (p.3), "**+3 V Single Supply**" (p.5), and "+/-2.5 V Dual Supply" (p.7). This confirms the part carries a dedicated, distinctly-titled 3 V specifications table in its own datasheet structure — the same pattern independently confirmed for its sibling ADG708/ADG709 (see below), which really does tabulate RON at VDD = 3 V +/- 10% with real numbers (8 Ohm typ / 11-12 Ohm max). The actual ADG726 +3 V table's numeric contents (page 5) could not be extracted: direct PDF fetches from Mouser (2 attempts) and alldatasheet.com (1 attempt, HTTP 403) failed, a curl download from a third mirror (dzsc.com) returned a corrupted/truncated file (0 readable pages), and the radiolocman preview served only the cover/TOC/revision-history pages, not the specifications body. | **PASS on structure, UNVERIFIED on numbers** — the datasheet demonstrably has a dedicated +3 V table (confirmed from its own table of contents), satisfying "specified for 3.3 V" in principle, but the actual RON figure printed in that table was not obtained. A human must open https://www.analog.com/media/en/technical-documentation/data-sheets/ADG726_732.pdf directly (analog.com blocked automated fetches all session) and read the +3 V Single Supply RON row before this can be called a full PASS. |
| 1c.3 | **On-resistance low enough not to corrupt a 140 mV reading** into the ESP32 ADC's input impedance | Not directly available for ADG726 (see 1c.2). As a same-family proxy (same "enhanced submicron" low-voltage CMOS process, same design house, same generation): **ADG708/ADG709** datasheet (Analog Devices, Rev. 0, 2000), fetched and read directly page-by-page: "SPECIFICATIONS (VDD = 3 V +/-10%...)" p.3: "On-Resistance (RON) — 8 Ohm typ / 11-12 Ohm max — VS = 0 V to VDD, IDS = 10 mA." The design also adds a ~100 nF buffer capacitor at the ADC input (Task 6) specifically so source resistance in the tens-of-ohms range does not corrupt the sampled value, per the ruling in this file's header. | **UNVERIFIED for ADG726 itself** (no number pulled — see 1c.2); if ADG726's +3 V RON is in the same 4-12 Ohm neighborhood as its sibling ADG708 (plausible given the shared "4 Ohm typ" figure quoted in ADG726/732's own title, per search result, but not read from the primary table), it is two orders of magnitude better than CD74HC4067's uncharacterised-but-likely-70-270-Ohm figure, and combined with the ADC buffer cap this would comfortably pass. A human must confirm the actual ADG726 number. |
| 1c.4 | Off-channel leakage small enough not to shift a 140 mV reading measurably | ADG708/ADG709 datasheet p.3, VDD = 3 V +/-10% table: "Source OFF Leakage IS(OFF) — +/-0.01 nA typ / +/-0.3 nA max (B version) — VS = 3 V/1 V, VD = 1 V/3 V"; "Drain OFF Leakage ID(OFF) — +/-0.01 nA typ / +/-0.75 nA max." These are nanoamp-level, roughly 1000x smaller than CD74HC4067's microamp-level OFF-leakage (uncharacterised at 3.3 V but ~8 uA max at 6 V). ADG726's own leakage table (page 5 area) was not read. | **UNVERIFIED for ADG726 itself**, but if it shares the same process family's nA-level leakage (plausible, not confirmed), 15 deselected channels would sum to tens of nA at most — utterly negligible against a 140 mV signal. A human must pull ADG726's actual +3 V leakage row. |
| 1c.5 | Channel-to-channel on-resistance match (mismatch appears as per-channel offset) | ADG708/ADG709 datasheet p.3, VDD = 3 V table: "On-Resistance Match Between Channels (Delta-RON) — 0.4 Ohm typ / 1.2 Ohm max." | **UNVERIFIED for ADG726 itself** (same-family proxy only); a sub-1.2-Ohm match would be negligible against the 1 Ohm sense resistor's signal, but this must be confirmed from ADG726's own table, not assumed from a sibling part. |
| 1c.6 | Settling time permits stepping 12 channels within a few ms sweep | ADG708/ADG709 datasheet p.3, VDD = 3 V table: "tTRANSITION — 18 ns typ / 30 ns max — RL = 300 Ohm, CL = 35 pF." | **PASS as a same-family proxy** — even at 10x this figure, sub-microsecond switching is negligible against a multi-millisecond, 12-channel sweep; ADG726's own dynamic-characteristics table (not reached) should still be confirmed, but this row is unlikely to be the blocking one. |

**Why ADG706 (the brief's suggested target) fails, confirmed twice:** (1) A
direct fetch of the ADG706/ADG707 datasheet via a radiolocman text mirror
(fetched 2026-09-12) returned the full "SPECIFICATIONS" table content, which
carries exactly **one** supply-voltage header: "VDD = 5 V +/-10%, VSS = 0 V,
GND = 0 V" — RON 2.5 Ohm typ / 4.5-5 Ohm max, RON match 0.3/0.8 Ohm typ/max,
RFLAT(on) 0.5/1.2 Ohm typ/max, leakage +/-0.01 nA typ / up to +/-1.5 nA max —
all at that one 5 V condition. No 3 V or 3.3 V row exists anywhere in that
table. (2) A second attempt to fetch analog.com's own product page for a
"fully specified at 3 V" claim seen in an AI search summary failed
(connection reset); the search-summary claim is **not corroborated** by the
actual specifications table text obtained directly from the datasheet, so it
is treated as unverified marketing paraphrase, not evidence, per this task's
rule against trusting search summaries over primary sources. ADG706 is
therefore recorded as **FAIL on 1c.2** on the strength of its own datasheet
table, despite superficially matching the brief's "ADG706-class" description.

**CD74HC4067 — excluded by the hard requirement, retained for the record**
(from the prior pass): its Electrical Characteristics table specifies RON
**only at VCC = 4.5 V and 6 V** (70 Ohm typ / 160-270 Ohm max at 4.5 V) and
OFF-leakage only at 6 V (8 uA max) — no 3.3 V row exists, which is precisely
the "uncharacterised at 3.3 V" gap this revision was written to close. Not
re-verified further in this pass since it is now explicitly out of scope.

**Design fix carried forward (Task 6):** a ~100 nF buffer capacitor at the
ESP32 ADC input, to supply the SAR sample-and-hold charge locally so mux
on-resistance (whatever it turns out to be) matters far less. Fallback if
140 mV proves noisy at bring-up: a 2.2 Ohm shunt (308 mV) or an op-amp gain
stage (both already noted in the ruling at the top of this section).

## 2. Dual smart high-side switch (1 required) — Denali
Candidate: Infineon BTS7008-2EPA (PROFET+2 12V family, "8 mOhm" variant).
Verified against **Infineon BTS7008-2EPA Data Sheet Rev. 1.21, 2024-07-29**
(fetched 2026-09-12; extracted with PyMuPDF after the harness's own PDF-to-text
conversion garbled the file — the underlying PDF is a normal text-layer
document, not corrupted).

| # | Required | Actual | Verdict |
|---|---|---|---|
| 2.1 | Continuous current per channel >= 3.3 A with margin | Table 13 "Electrical Characteristics: Power Stages - 8 mOhm", p.28: "Nominal Load Current per Channel (all Channels Active) — IL(NOM) — Typ. 7.5 A — TA = 85 degC, TJ <= 150 degC" (P_7.5.1.8). | **PASS** — 7.5 A nominal (both channels active simultaneously) vs 3.3 A required, >2x margin. |
| 2.2 | Current sense output resolves a 3.3 A load, ratio documented | Table 22 "Electrical Characteristics: Diagnosis - 8 mOhm", p.53: current-sense ratio kILIS is tabulated at multiple load points bracketing 3.3 A — "Current Sense Ratio at IL = IL14 (2.8 A): -5.8%/+5.8%, Typ. 5400" (P_9.7.1.18); "Current Sense Ratio at IL = IL16 (5.5 A): -4.0%/+4.0%, Typ. 5450" (P_9.7.1.20). At 3.3 A, IS output current = IL/kILIS ~= 3.3 A / 5400 ~= 0.61 mA. | **PASS** — the ratio is explicitly documented at points bracketing 3.3 A (2.8 A and 5.5 A) with tolerance <=6%, giving a clean, resolvable IS current for an external sense resistor/ADC. |
| 2.3 | 3.3 V logic compatible inputs (no level shifter needed) | Section 5.1 "Input Pins (INn)", p.13, verbatim: "The input circuitry is compatible with 3.3V and 5V microcontroller." Table 7 "Electrical Characteristics: Logic Pins - General", p.14: "Digital Input Voltage Threshold — VDI(TH) — Min 0.8 V, Typ 1.3 V, Max 2 V" (P_5.4.0.1). A 3.3 V GPIO driving high sits 1.3 V above the 2 V max threshold (guaranteed HIGH detection); GND sits 0.8 V below the 0.8 V min threshold isn't quite true — 0 V is below the 0.8V min threshold itself (guaranteed LOW). | **PASS** — explicit datasheet statement plus a threshold table that a 3.3 V logic swing clears with margin on both ends; no level shifter needed. |
| 2.4 | PWM capable at 150 Hz | Table 12 "Electrical Characteristics: Power Stages - PROFET", p.26: "Switch-ON Time — tON — Max 110 us" (P_7.4.1.3); "Switch-OFF Time — tOFF — Max 100 us" (P_7.4.1.4), both at VS = 13.5 V. | **PASS** — worst-case combined switching transition (210 us) is 3.1% of a 150 Hz period (6.667 ms); leaves >96% of the period free for duty-cycle range, comfortably supporting PWM dimming at 150 Hz. |
| 2.5 | Integrated short-circuit, overcurrent, thermal shutdown | Datasheet Overview, p.2, "Protection Features": "Absolute and dynamic temperature limitation with controlled restart"; "Overcurrent protection (tripping) with Intelligent Restart Control"; "Undervoltage shutdown"; and "Diagnostic Features": "Short circuit to ground and battery." | **PASS** — all three required protections plus undervoltage shutdown are named, integrated features. |
| 2.6 | On-resistance gives <= 0.25 W for the pair at 3.3 A each | Table 13, p.27-28: "ON-State Resistance at TJ = 25 degC — RDS(ON)_25 — Typ. 9 mOhm" (P_7.5.1.1, not subject to production test); "ON-State Resistance at TJ = 150 degC — RDS(ON)_150 — Max. 16 mOhm" (P_7.5.1.2). Pair dissipation at 3.3 A each: at 25 degC typ, P = 2 x 3.3^2 x 0.009 = 0.196 W; at 150 degC max, P = 2 x 3.3^2 x 0.016 = 0.349 W. | **PASS at 25 degC typical** (0.196 W < 0.25 W) **but FAILS at the 150 degC worst-case max rating** (0.349 W > 0.25 W). This is a real thermal-margin question, not a datasheet gap: whether the device actually reaches 150 degC junction under this design's duty cycle and PCB copper/thermal relief is a Task 3 layout question. Flag for the schematic/layout pass: verify junction temperature stays low enough (via thermal simulation or bench measurement) that RDS(on) stays closer to the 25 degC figure, or accept reduced margin at temperature extremes. |
| 2.7 | Standby current <= 20 uA | Table 1 "Product Summary", p.2: "Maximum current in Sleep mode (TJ <= 85 degC) — IVS(SLEEP)_85 — 0.6 uA." Section 6.1.3 "Sleep mode", p.16: entered when all digital inputs (INn, DEN, DSEL) are low; outputs OFF, current consumption minimum. | **PASS** — 0.6 uA max vs 20 uA required, >30x margin. (Note: Stand-by mode, entered with DEN high and inputs low, has higher consumption per Section 6.1.4 because diagnosis stays active — this is not the mode used for the sleep-budget rollup, which assumes full Sleep mode.) |

## 3. Synchronous boost controller — 12 V to 24 V, 60 W
Candidate: TI LM5122-Q1. Verified against **TI LM5122-Q1 datasheet SNVSAW9,
June 2017** (fetched 2026-09-12; extracted with PyMuPDF — same "the harness's
text conversion garbles it, the PDF itself is fine" situation as section 2).

| # | Required | Actual | Verdict |
|---|---|---|---|
| 3.1 | Input rating 40-60 V (must exceed the 24 V TVS clamp voltage) | Section 6.3 "Recommended Operating Conditions", p.6: "Input supply voltage — VIN — Min 4.5 V, Max 65 V." Section 6.1 "Absolute Maximum Ratings", p.5: "VIN, CSP, CSN — Max 75 V." Feature list p.1: "Maximum Input Voltage: 65 V." | **PASS** — 65 V recommended max and 75 V absolute max both clear the 40-60 V band with margin; 4.5 V min is far below the requirement so no conflict there either. |
| 3.2 | Synchronous (external FETs), efficiency >= 94% at 40 W out | **Synchronous/external FETs confirmed:** feature list p.1: "Robust 3-A Integrated Gate Drivers," "Adaptive Dead-Time Control"; pin functions p.4: "HO — High-side N-channel MOSFET gate drive output," "LO — Low-side N-channel MOSFET gate drive output" (both external FETs, true synchronous rectification, peak-current-mode control). Section 8.2 "Typical Application" worked design example, p.35, uses almost exactly this design's voltage points: VOUT = 24 V, VIN(TYP) = 12 V, VIN range 9-20 V (though at 108 W, not 60 W). **Efficiency percentage: not found.** A full-text search of all 50 pages for the word "Efficiency" returned zero hits — the "Typical Characteristics" efficiency curves in this datasheet are image-only plots with no OCR-able axis/label text extracted by PyMuPDF, and no numeric efficiency percentage appears anywhere in the document's text layer. | **PASS** for "synchronous, external FETs" (directly confirmed from pin functions and features). **UNVERIFIED** for the >= 94% efficiency figure — needs a human to open the datasheet's Typical Characteristics section visually (or run the TI WEBENCH Power Designer tool linked in Section 8.2.2.1 with this design's exact 12 V-in/24 V-out/60 W point) to read the actual efficiency curve; not stated here as a number because none could be extracted. |
| 3.3 | Enable pin, 3.3 V logic compatible | The device has **no dedicated EN pin** (confirmed against the full pin list, Section 4 "Pin Functions" p.4: SYNCOUT, OPT, CSN, CSP, VIN, UVLO, SS, SYNCIN/RT, AGND, FB, COMP, SLOPE, RES, PGND, MODE, LO, VCC, SW, HO, BST, EP — no "EN"). The **UVLO pin** serves this role: p.4, "If the UVLO pin is below 0.4 V, the regulator is in shutdown mode with all functions disabled. If the UVLO pin voltage is greater than 0.4 V and below 1.2 V, the regulator is in standby mode... If the UVLO pin voltage is above 1.2 V, the start-up sequence begins." | **PASS, with an implementation note** — a 0 V / 3.3 V logic swing cleanly straddles both thresholds (0 V is below the 0.4 V shutdown threshold; 3.3 V is above the 1.2 V start-up threshold), so no level shifter is needed. However, UVLO's primary job is analog line-undervoltage sensing via an external resistor divider from VIN (worked example, Section 8.2.2.3, p.35: RUV2 = 49.9 kOhm, RUV1 = 8.06 kOhm for an 8.7 V start-up threshold) — to add MCU enable/disable on top of that divider, the standard technique is a small transistor across the lower divider resistor gated by the 3.3 V GPIO, not a bare pin-to-GPIO wire. This is a normal design detail for Task 3/4, not a missing capability. |
| 3.4 | Spread-spectrum or frequency dither available | Feature list, p.1, lists every switching-related feature explicitly ("Free-Run and Synchronizable Switching to 1 MHz," "Peak-Current-Mode Control," programmable slope compensation, skip-cycle mode) with **no mention of spread-spectrum or frequency dither**. A full-text search of all 50 pages for "dither" and "spread spectrum" found no matching feature description anywhere in the document. The part does support external clock synchronization (SYNCIN pin, Section on Oscillator, p.7/21) up to 1 MHz, which could in principle accept an externally-dithered clock source. | **FAIL** — the LM5122-Q1 itself does not implement spread-spectrum or dither as a built-in feature. If EMI dithering is a hard requirement, either add an external dithered clock into SYNCIN (extra complexity, not evaluated here) or select a different controller family that natively supports it. |
| 3.5 | Disabled-state current draw <= 10 uA, or gated externally | Section 6.5 "Electrical Characteristics", p.6: "ISHUTDOWN — VIN shutdown current — VUVLO = 0 V — Typ 9 uA, Max 17 uA." Feature list p.1 also states "Low Shutdown Quiescent Current: 9 uA" (the typical figure). | **PASS on typical (9 uA), FAILS on guaranteed max (17 uA)** against the bare 10 uA threshold. The criterion's alternate clause ("or gated externally") is met by this design's own architecture: Section 6.1's P-FET series disconnect switch (row 6.1) sits upstream of this whole boost stage and can cut it off from the battery entirely during deep sleep, making the IC's own shutdown-current spec moot for the sleep budget as long as that P-FET is used as intended. |
| 3.6 | Dissipation at 40 W out <= 3 W including both FETs | Not determinable from this datasheet alone — HO/LO drive **external** N-channel MOSFETs (row 3.2), so total FET dissipation (conduction loss I^2 x RDS(on) plus switching loss at the chosen fSW) depends entirely on which external FETs Task 3/4 selects and what switching frequency is programmed via RT (the worked example in Section 8.2.2.2, p.35, uses 250 kHz for a 108 W/24 V design, chosen as "a reasonable compromise between small size and high-efficiency"). | **UNVERIFIED at the controller level** — this is a system-level calculation that depends on FET selection, not a fixed parameter of the LM5122-Q1. Task 3/4 must pick specific boost-stage FETs, compute conduction + switching loss for both at the 60 W/24 V operating point, and check the sum against the 3 W ceiling. |

## 4. Low-quiescent buck — 12 V to 3.3 V, 1 A
Candidate: TI LM5164

| # | Required | Actual | Verdict |
|---|---|---|---|
| 4.1 | Quiescent current <= 30 uA (this is the dominant sleep contributor) | | |
| 4.2 | Output current >= 1 A (ESP32 WiFi TX peaks ~500 mA) | | |
| 4.3 | Input rating 40-60 V | | |
| 4.4 | Stable with no load (sleep condition) | | |

## 4b. 5 V regulator (ADDED 2026-09-11) — mandatory, always on
Feeds the TJA1042's VCC (4.5-5.5 V). Must stay powered in deep sleep so the
transceiver can monitor the bus, so its own quiescent draw lands directly in
the sleep budget. No candidate was pre-chosen by the brief; proposed here:
**TI LM5164** (100 V input, 1 A synchronous buck, ultra-low IQ, datasheet
SNVSAU4D, revised February 2026), configured for a 5.0 V output via its
external feedback divider. This is the same IC family already candidate for
Section 4's 3.3 V rail — using it again for 5 V adds one more IC of a part
already qualified for this design's input range, rather than introducing a new
part number.

**Trade-off (buck vs. LDO):** a buck was chosen over an LDO specifically for
its verified ultra-low quiescent current (10.5 uA typ, row 4b.1), which lands
far under the 30 uA target and is the dominant lever on the whole-board sleep
budget. An LDO dropping 12-24 V down to 5 V at light load would be thermally
trivial (its dissipation problem only matters at active current, row 4b.5),
but low-IQ LDOs rated for a 40-60 V input are a narrower, more expensive part
class than low-IQ 100 V bucks, and none was located and verified in this
session. The accepted cost of the buck choice is switching-converter EMI
mitigation (layout care), which the LM5164 datasheet documents compliance for
(see row 4b.5).

| # | Required | Actual | Verdict |
|---|---|---|---|
| 4b.1 | Quiescent current <= 30 uA (counts against the <200 uA sleep budget) | Datasheet Section 5.5 "Electrical Characteristics": "IQ-SLEEP1 VIN sleep current — VEN = 2.5 V, VFB = 1.5 V — 10.5 / 25 uA" (typ/max). Feature list: "10.5uA no-load input quiescent current". Section 6.3.1/6.4.3 "Sleep Mode": at light load the converter enters diode-emulation, then "an ultra-low IQ sleep mode... The input quiescent current (IQ) required by the LM5164 decreases to 10.5uA in sleep mode." | **PASS** — 10.5 uA typ / 25 uA max, both under the 30 uA criterion, and the datasheet explicitly engineers this behavior for light/no-load standby (the exact condition here). |
| 4b.2 | Output 5.0 V +/- 5%, >= 100 mA (transceiver active draw) | Section 5.3 "Recommended Operating Conditions": "ILOAD Load current — 1 / 1.25 A" (nom/max) — far above the 100 mA needed. Output voltage is set externally: Section 6.3.3, "RFB2 = 1.2V / (VOUT - 1.2V) x RFB1", using the internal "VREF FB regulation voltage — 1.181 / 1.2 / 1.218 V" (min/typ/max, Section 5.5) reference. No dedicated fixed-5V SKU exists for this part — output accuracy at 5.0V depends on the external divider's resistor tolerance plus the +/-1.5% VREF spread. | **PASS** — 1 A/1.25 A output vs 100 mA required; +/-5% output accuracy is achievable with the +/-1.5% VREF tolerance plus standard 1% feedback resistors (well inside budget), though this is a design/BOM detail for the schematic stage, not this part's spec. |
| 4b.3 | Input rating 40-60 V (survives the 24 V TVS clamp) | Section 5.3 "Recommended Operating Conditions": "VIN Input voltage — 6 / 100 V" (min/max). | **PASS** — 6-100 V comfortably covers the 40-60 V requirement with large margin on both ends. |
| 4b.4 | Stable at the ~20 uA load the transceiver presents in standby | Section 6.1 "Overview" / 6.4.3 "Sleep Mode": diode-emulation mode (DEM) plus an ultra-low-IQ sleep state are built in specifically to prevent instability and battery drain at light/no load. Section 7.2.3 "Application Curves", Fig. 7-6 "No-Load Start-up with VIN" is an actual bench scope capture at IOUT = 0 A showing clean, monotonic start-up (no oscillation). | **PASS** — the device is explicitly tested and characterized at 0 A load (a more demanding condition than the ~20 uA transceiver standby draw), with no instability shown. |
| 4b.5 | If an LDO: dissipation at (12 V - 5 V) x active current is acceptable; if a buck: EMI acceptable | LM5164 chosen as a **buck**. Feature list: "Optimized for ultra-low EMI requirements — Meets CISPR 25 class 5 standard". Section 7.2.3, Figures 7-16/7-17: actual "CISPR 25 Class 5 Conducted Emissions Plot" bench measurements (150 kHz-30 MHz and 30-108 MHz) at VIN = 48 V, Load = 1 A, with an RC snubber (Rsnub = 1 Ohm, Csnub = 680 pF) — both plots are datasheet-published evidence of compliance testing, not merely a claim. | **PASS** — CISPR 25 Class 5 is TI's stated, bench-verified EMI compliance level for this part; acceptable for this design subject to following the datasheet's layout guidance (Section 7.4). |

## 5. CAN transceiver
Candidate: NXP TJA1042T/3

Verified against **NXP TJA1042 Product data sheet Rev. 8, 15 January 2015**
(TJA1042T/3/1J, TJA1042T/1J, TJA1042TK/3/1J). nxp.com/docs blocks automated
fetch; the identical document was obtained from the Farnell mirror
(farnell.com/datasheets/1923816.pdf). Rev. 11 (16 January 2023) exists on
nxp.com and was not read — a human should diff the four parameters below
against Rev. 11 before the board order.

| # | Required | Actual | Verdict |
|---|---|---|---|
| 5.1 | **GO/NO-GO:** standby mode signals bus wake-up by driving RXD LOW | **Yes.** Table 4 "Operating modes" p.5: Standby = pin STB HIGH, pin **RXD LOW = "wake-up request detected"**, RXD HIGH = "no wake-up request detected". §7.1.2 Standby mode p.5, verbatim: "only a low-power differential receiver monitors the bus lines for activity. The wake-up filter on the output of the low-power receiver does not latch bus dominant states, but ensures that only bus dominant and bus recessive states that persist longer than tfltr(wake)bus are reflected on pin RXD. … The low-power receiver is supplied by VIO, and is capable of detecting CAN bus activity even if VIO is the only supply voltage available. **When pin RXD goes LOW to signal a wake-up request**, a transition to Normal mode will not be triggered until STB is forced LOW." Timing, Table 8 p.12: tfltr(wake)bus (versions with VIO pin, Standby mode) **0.5 / 1.5 / 5 us**; td(stb-norm) standby-to-normal delay 7 / 25 / 47 us. | **PASS** — RXD is actively driven LOW on a filtered bus-dominant while in Standby, which is exactly the edge/level an ESP32 EXT0 wake needs, and it works on VIO alone (VCC may be off). **Two constraints to design to:** (a) §7.2.2 p.5 bus dominant time-out — "If the dominant state on the bus persists for longer than **tto(dom)bus**, the RXD pin is reset to HIGH", tto(dom)bus = 0.3 / 2 / 5 ms (Table 8 p.12), so the LOW is guaranteed for at least 0.3 ms but is **not latched** indefinitely; (b) RXD is not open-drain — IOL 2 / 5 / 12 mA, IOH −8 / −3 / −1 mA (Table 7 p.10) — so it must wake the ESP32 on level/edge, not be wire-ORed. |
| 5.2 | VIO pin for 3.3 V logic (the /3 suffix) | §7.3 p.8: "Pin 5 is either a SPLIT output pin or a VIO supply pin"; §7.3.2 p.8: "Pin VIO on the TJA1042T/3 and TJA1042TK/3 should be connected to the microcontroller supply voltage. This sets the signal levels of pins TXD, RXD and STB to the I/O levels of the microcontroller." §2 p.1: "VIO input on TJA1042T/3 and TJA1042TK/3 allows for direct interfacing with **3 V to 5 V** microcontrollers." Table 7 p.10: "VIO supply voltage on pin VIO **2.8 … 5.5 V**"; "Vuvd(VIO) undervoltage detection voltage on pin VIO 1.3 / 2.0 / **2.7 V**". Logic thresholds referenced to VIO: VIH 0.7xVIO min, VIL 0.3xVIO max (pins STB and TXD, Table 7 p.10). | **PASS** — 3.3 V sits inside the 2.8-5.5 V VIO window with 0.6 V above the 2.7 V max undervoltage-detect level; no level shifter needed on TXD/RXD/STB. |
| 5.3 | Standby current <= 20 uA | Table 7 p.10, Standby mode: "ICC supply current — Standby mode — **TJA1042T/3 or TJA1042TK/3: max 5 uA**" (the TJA1042T row, which "includes IIO", is typ 10 / max 15 uA). "IIO supply current on pin VIO — Standby mode; VTXD = VIO: **5 / – / 14 uA**" (column extraction reads min 5, typ –, max 14; the max of 14 uA is unambiguous). For the /3 part the two rails are separate, so worst-case standby = **5 + 14 = 19 uA max** over Tvj = −40 to +150 C. §7.2.3 p.5 condition: "Pins TXD and STB have internal pull-ups to VIO … **both pins should be held HIGH in Standby mode to minimize standby current**" — the datasheet's standby figures are specified at VTXD = VIO, so firmware must leave TXD and STB high through deep sleep. | **PASS, but with no margin** — 19 uA max vs the 20 uA criterion (95% of it). Against the whole-board target of <200 uA this is ~10% of budget. Note the figure is split across two rails: 5 uA from the 5 V VCC and 14 uA from the 3.3 V VIO. |
| 5.4 | TXD can be left pulled to VIO (recessive) with no fault latch | §7.2.3 p.5: "Pins TXD and STB have **internal pull-ups to VIO** to ensure a safe, defined state in case one or both of these pins are left floating." §7.2.1 p.5, TXD dominant time-out: "A 'TXD dominant time-out' timer is **started when pin TXD is set LOW** … The TXD dominant time-out timer is **reset when pin TXD is set to HIGH**." TXD HIGH is the recessive state, so the time-out never starts. Table 7 p.10: IIH at VTXD = VIO is −1 / – / +5 uA (vs IIL typ −150 / max −30 uA at VTXD = 0 V), i.e. holding TXD high also costs essentially nothing. There is no latched-fault or error-flag pin on this device at all (no ERR_N / EN pins — pin list §6 p.4 is TXD, GND, VCC, RXD, VIO or SPLIT, CANL, CANH, STB). | **PASS** — TXD at VIO is the intended idle state, it starts no timer and latches no fault, and it is also the condition under which the standby current of row 5.3 is specified. |

### Additional finding (not a listed criterion)

TJA1042 requires **VCC = 4.5 … 5.5 V** (Table 7 p.10), with Vuvd(VCC) 3.5 / – / 4.5 V
and §7.2.4 p.5: "Should VCC drop below the VCC undervoltage detection level,
Vuvd(VCC), the transceiver will switch to Standby mode." The design context lists
only a 3.3 V logic rail, so the board needs a 5 V rail (or a 5 V-capable CAN
transceiver) for the transceiver's VCC. Section 4 owns the rail decision; flagged
here because it is discovered by this section's datasheet read.

## 6. Discretes

| # | Required | Actual | Verdict |
|---|---|---|---|
| 6.1 | P-FET: Vds >= 40 V, Rds(on) <= 10 mOhm, Vgs rated for 24 V jump | | |
| 6.2 | TVS: standoff ~24 V, clamp < 40 V, rated for the feed current | | |
| 6.3 | PTC: 0.5 A hold at 24 V, trip < 1 A, 4 required | | |
| 6.4 | Schottky OR pair: 40 V, >= 0.5 A, low leakage | | |
| 6.5 | Boost inductor: shielded, saturation current >= 1.5x peak | | |

## Sleep budget roll-up (spec 8.2: target < 200 uA, ceiling 500 uA)

| Contributor | Datasheet value | Source |
|---|---|---|
| ESP32 deep sleep | | |
| EXT0 RTC_PERIPH domain | | |
| CAN transceiver standby | | |
| Buck quiescent | | |
| Low-side switches standby | | |
| PROFET standby | | |
| P-FET gate + divider leakage | | |
| **TOTAL** | | |

## Final BOM decision

| Function | Manufacturer part number | Package | Unit price | Stock |
|---|---|---|---|---|

## Appendix: superseded Section 1 — octal smart low-side switches (FAILED)

Preserved as the evidence record for why the RGB output stage was redesigned
(see Section 1 above). Row 1.1 (open-load detection at 0.14 A, ON-state) failed
for every candidate checked, which is the reason the design moved to discrete
MOSFETs + shunt + mux.

## 1. Octal smart low-side switch (2 required) — RGB channels
Candidates: ST VNI8200XP, Infineon TLE8110ED / TLE8108EM, NXP MC33996

Rows below are evaluated against **Infineon TLE8110ED** (Data Sheet Rev. 1.0,
2018-03-07 / Rev. 1.1, 2021-04-30 — same content for every parameter cited),
because it is the only candidate that provides a per-channel direct PWM input
pin (row 1.5). The other candidates were screened first — see
"Candidate screening" below the table.

| # | Required | Actual | Verdict |
|---|---|---|---|
| 1.1 | **GO/NO-GO:** open-load detection resolves a **0.14 A** load, and works in the ON state (not only OFF) | Open load is an **OFF-state-only** diagnosis. Diagnosis register field DRA/DRB, §12.3.2.1 p.64: `DRn[1]x/DRn[0]x = 01` is defined verbatim as "**Open Load in OFF-Mode**"; the ON-state code is `10` = "Over Load, Shorted Load, Over temperature **in ON-Mode**". §12.3.6 p.71 (DEVS.DCCx) confirms: "OFF-State Diagnosis (Detection of open load and short to GND) of CHx is switched OFF. **ON state diagnosis (over current and over temperature detection)** is still active." Mechanism is a VDS comparator, not a load-current comparator: Table 8 §8.2 p.29 — "Open load detection threshold voltage **VDSol 2.00 / 2.60 / 3.20 V**" (P_8.2.1) and "Output pull-down diagnosis current per channel **IDpd 50 / 90 / 150 mA** at VDS = 13.5 V" (P_8.2.2). No load-current detection threshold is specified anywhere in the datasheet, so "resolves a 0.14 A load" is **not a specified parameter** for this part. | **FAIL** — ON-state open-load detection does not exist; the 0.14 A resolution figure is unspecified (VDS-threshold method, OFF state only). See the go/no-go note below the table. |
| 1.2 | Output voltage rating >= 40 V | Abs Max Table 2 p.11: "Continuous Drain Source Voltage **VDSn −0.3 … 45 V**". Table 7 §7.3 p.21: "Output Clamping Voltage, Channel 1 to 10 **VDScl 45 / 55 / 60 V**" (P_7.3.10). Abs-max short-circuit entry p.11: "maximum Voltage for short circuit VDSn 24 V, one event on one channel". | **PASS** — 45 V continuous rating, 45 V min clamp, vs 40 V required (24 V rail + transient headroom). |
| 1.3 | Continuous current per channel >= 0.3 A | §7.1 p.19: "Channel 1 to 4 … nominal current requirement of **1.5 A**", "Channel 5 to 6 … nominal current requirement of **1.7 A**", "Channel 7 to 10 … nominal current requirement of **0.75 A**". RDSon specified at IDnom = 1.5 A / 1.7 A / 0.75 A respectively (Table 7 p.21). | **PASS** — lowest channel group is 0.75 A, vs 0.3 A required (5.4x margin over the 0.14 A load). |
| 1.4 | >= 6 channels per package (2 packages cover 12) | **10 channels** per package. Datasheet title: "Smart Multichannel Low Side Switch with Parallel Control and SPI Interface"; §2 p.6: "The TLE8110ED is equipped with 10 parallel input pins that are routed to each output channel." Pin list §3.2 pp.7-8 shows P_IN1…P_IN10 and OUT1…OUT10. Package PG-DSO-36. | **PASS** — 2 packages give 20 channels for the 12 needed, and allow the 12 to be placed on the low-RDSon groups (see 1.9). |
| 1.5 | Parallel/direct PWM input mode exists, usable at 400 Hz | Feature list p.1: "**Direct Parallel PWM Control of all Channels**". §2 p.6: 10 parallel input pins routed to each output channel (PWM does **not** go over SPI). Table 7 p.21 Timing: "Output Switching Frequency **fOUTx max 20 kHz**" (P_7.3.11); turn-on tdON 5/10 us (P_7.3.12), turn-off tdOFF 5/10 us (P_7.3.13). | **PASS** — 400 Hz is 1/50 of the 20 kHz max; 10 us edges are 0.4% of the 2.5 ms period. Caveat (not a spec violation): §8.1 p.28 Application Hint — "It is recommended to avoid OFF periods of the channel shorter than td(max) (**220 us**) in order to ensure the filter time is expired and the correct diagnosis information is stored", i.e. OFF-state diagnostics need duty <= ~91% at 400 Hz. |
| 1.6 | SPI diagnostics: open load, short to battery, short to GND, overtemperature | Only **four** diagnosis codes exist in total (§8.1 p.27 table, and §12.3.2.1 p.64): `00` Short to Ground (OFF-mode), `01` Open Load (OFF-mode), `10` "**Over Load, Shorted Load, Over temperature** in ON-Mode", `11` No Fault. All four required conditions are *detected*, but short-to-battery (which on a low-side switch appears as overload) and overtemperature are **merged into the single code `10`** and cannot be told apart over SPI. Short-to-GND threshold: Table 8 p.29 "VDSsg 1.00 / 1.50 / 2.00 V" (P_8.2.5), "IDsg −150 / −100 / −50 mA" (P_8.2.6). Note also §8.1 p.27: "No priority scheme is implemented for the diagnosis detection, any new diagnosis entry will override the previous one." | **FAIL** — all four conditions are detected, but the 2-bit register cannot distinguish short-to-battery from overtemperature. If the firmware only needs "a fault on this channel, ON-state class" this is adequate; as written, the criterion is not met. |
| 1.7 | Daisy-chainable on one CS, or 2 CS available in spare GPIO | §2 p.6: "The SPI interface provides **daisy-chain capability** in order to assemble multiple devices in one SPI chain." Protocol detail §12.2.3.4 p.47 "Daisy-Chain and 2x8-bit protocol". | **PASS** — two packages daisy-chain on one CS; no second CS GPIO needed. |
| 1.8 | Standby current <= 20 uA total for both packages | Table 5 §5.2 pp.14-15, standby (EN de-asserted) rows: "Analogue Supply Current during Reset **IDDstb** (VEN < VENI) **typ 1 / max 5 uA** at Tj = 85 C; **typ 2 / max 15 uA** at Tj = 150 C" (P_5.2.10). "Digital Supply Current during Reset **ICCstb** (VRST > VRSTI) **typ 2 / max 5 uA** at Tj = 85 C; **typ 5 / max 15 uA** at Tj = 150 C" (P_5.2.3). Per package at 85 C: typ 3 uA, max 10 uA. **Two packages: typ 6 uA, max 20 uA at 85 C; max 60 uA at 150 C.** Separately, Table 7 p.21 "Output Leakage Current in standby mode **IDoff**" (P_7.3.7-9) is specified max **3 uA** (Ch 1-4), **6 uA** (Ch 5-6), **2 uA** (Ch 7-10) per channel at Tj = 85 C and 8 / 12 / 5 uA at Tj = 150 C — all at **VDS = 13.5 V**, not at the 24 V rail this design uses. | **FAIL** — typical is comfortable (6 uA) but the guaranteed worst case is exactly 20 uA at 85 C with **zero margin**, 60 uA at 150 C, before adding IDoff, which for 12 channels adds up to ~36 uA at 85 C. Worst-case total exceeds the 20 uA criterion. Datasheet note 1) on Table 5: the standby rows are "Parameter not subject to production test. Specified by design." |
| 1.9 | On-resistance, and resulting dissipation at 0.14 A x 12 channels <= 0.2 W | Table 7 §7.3 p.21: RDSon Ch 1-4 "typ **0.3 Ohm** at IDnom = 1.5 A, Tj = 25 C / typ 0.45, **max 0.6 Ohm** at Tj = 150 C" (P_7.3.1); Ch 5-6 "typ **0.25 Ohm** at 25 C / typ 0.35, **max 0.5 Ohm** at 150 C" (P_7.3.2/3); Ch 7-10 "typ **0.6 Ohm** at 25 C / typ 0.85, **max 1.2 Ohm** at 150 C". Worst-case hot dissipation at 0.14 A, 100% duty, using 6 channels per package from groups 1-6 (8x Ch1-4 + 4x Ch5-6): 8 x 0.14^2 x 0.6 + 4 x 0.14^2 x 0.5 = 94 mW + 39 mW = **133 mW**. | **PASS** — 0.133 W vs 0.2 W limit, at max RDSon and Tj = 150 C. **Conditional on channel assignment:** if the 12 channels used include group 7-10 (max 1.2 Ohm), 12 x 0.14^2 x 1.2 = **282 mW** and the criterion FAILS. Layout must place all 12 RGB channels on OUT1-OUT6 of each package. |
| 1.10 | In stock, multi-source or >= 12 month lead visibility | Single-source (Infineon only; no second-source equivalent exists for the parallel-PWM + SPI-diagnostics combination). LCSC product page C540057 (fetched 2026-09-11) shows package DSO-36 and "**Not available now**" with no stock quantity, price or lead time published. Infineon's own part page did not render lifecycle status or distributor stock to an automated fetch. Digi-Key / Mouser / Arrow stock and lead time were not obtained. | **UNVERIFIED** — needs a human to check Digi-Key, Mouser and Arrow for TLE8110EDXUMA1 stock, price and quoted lead time, and to pull Infineon's PCN/lifecycle status (Active vs NRND) from the authenticated Infineon part page. The one data point obtained (LCSC: not available) is a negative signal. |

### Go/no-go outcome for row 1.1

**Row 1.1 FAILS, and it fails for every candidate that was checked — this is not a
TLE8110ED-specific result.** Multichannel smart low-side switches in this class
implement open-load detection as an OFF-state VDS comparison against an internal
diagnostic pull-up/pull-down current source. ON-state open-load detection needs a
per-channel current sense, which none of the verified parts has. Per the task
rules no workaround is proposed here; the resolution (e.g. accepting OFF-phase
diagnostics inside the 400 Hz PWM cycle, or changing the diagnostics requirement)
is a design decision, not a part-selection one.

### Candidate screening

| Candidate | Outcome | Evidence |
|---|---|---|
| **Infineon TLE8110ED** | Best fit; fails 1.1, 1.6, 1.8 | Full datasheet verified — see table above. 10 ch, 45 V, per-channel parallel PWM inputs, SPI daisy-chain. Needs a **5 V analogue rail** (Table 5 p.15: "Analogue Supply Voltage VDD 4.5 … 5.5 V"); digital VCC may be 3.3 V ("Digital Supply Voltage VCC 3 … 5.5 V"). |
| **ST VNI8200XP** | **Not applicable** — wrong topology | ST datasheet title and product page: "Octal **high side** smart power solid state relay with serial/parallel selectable interface on chip". This is a high-side device and cannot serve as the low-side switch. (Also rated 10.5-36 V operating.) |
| **NXP MC33996** | Fails 1.1 and 1.5 | NXP product page (16-Output Switch with SPI Control) states diagnostics as "Output **ON short-to-VBAT** and **OFF short-to-ground/open** detection" — open load is OFF-state only (fails 1.1) — and PWM as "A Pulse-Width Modulation (PWM) control input may be used to pulse width modulate multiple outputs **at the same duty cycle**", i.e. one shared PWM pin, not 12 independent duty cycles (fails 1.5). Page also gives "Load supply voltage min. 0 V, max. 40 V", outputs "voltage clamped (50 V)", "Load current (IL) 0.35 A (Typ)", "current limited (0.9 A)", 16 channels. The full datasheet PDF could not be retrieved (nxp.com/docs blocks automated fetch; Digi-Key and Mouser mirrors returned HTTP 410), so its numeric open-load threshold was never read — recorded as unread, not estimated. |
| **Infineon TLE8108EM** | Not evaluated | Superseded by TLE8110ED in the same family; no datasheet was fetched, so nothing is asserted about it. |
| **Infineon TLE75008-ESD** | Checked as an alternative; fails 1.1 | Datasheet Rev. 1.10 2020-09-02 verified locally. Feature list p.1: "**Open Load detection at OFF state** using Output Status Monitor function"; §5 p.14: "Open Load at OFF state detection, a internal current source IOL can be activated via SPI"; Table §9.5 "Output diagnosis current IOL 70 / 85 / 100 uA at VDS = 3.3 V", "Open Load equivalent ROL 30 … 300 kOhm". Also a 12 V part ("SPIDER+ 12V") with only 2 direct input pins (IN0, IN1) — fails 1.5 as well. |
