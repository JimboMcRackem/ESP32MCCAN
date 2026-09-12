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

### 1a. Logic-level N-MOSFET (12 required) — REVISED 2026-09-12 against Ruling 15 (fix round 1)

**Candidate reverted to Nexperia PMV60ENEA** (40 V N-channel TrenchMOS,
SOT23/TO-236AB), per Ruling 15: the `Vgs(th) max <= 2.0 V` gate used in the
previous pass was itself withdrawn as an arbitrary proxy that wrongly
rejected this SOT-23 part (Vgs(th) max 2.5 V, which at 3.3 V drive still
leaves 0.8 V of overdrive — plainly sufficient at 0.14 A) in favour of an
IRLZ44N TO-220 power brick that cannot fit 12-up on a small sealed-enclosure
board. Verified against the same **Nexperia PMV60ENEA Product data sheet,
9 May 2019** already fetched in the prior pass, re-read for the new
criteria (1a.2 revised, 1a.7 and 1a.8 added). Its sibling **PMV30ENEA**
(Product data sheet, 14 Aug 2026) was also re-checked in full and passes
identically — see the screening table below; PMV60ENEA is named as the
primary pick only because it is the smaller/lower-current part closer to
this 0.14 A load, not because PMV30ENEA fails anything.

| # | Required | Actual | Verdict |
|---|---|---|---|
| 1a.1 | Vds >= 40 V (24 V rail plus transients) | Datasheet Section 4 "Quick reference data" Table 1 / Section 8 "Limiting values" Table 5: "VDS drain-source voltage — 40 V" (Tj = 25 degC). | **PASS** — meets the 40 V threshold exactly. Zero margin beyond the 40 V figure itself; the TVS clamp voltage (row 6.2) must settle below 40 V for this to hold in practice — noted, not a defect of this row. |
| 1a.2 | **REVISED (Ruling 15)**: the datasheet establishes conduction of Id >= 0.5 A at Vgs <= 3.3 V, via an Rds(on) spec at that gate voltage or a transfer/output curve. No Vgs(th) threshold imposed. | Section 10 "Characteristics" Table 7 gives no RDS(on) row at <=3.3 V directly, so this is read from **Fig. 6 "Output characteristics"** (drain current vs VDS, TJ = 25 degC), which plots curves for VGS = 2.4, 3.0, 3.5, 4.5, and 10 V. The page was rendered to a high-resolution image (PyMuPDF) and inspected visually rather than pixel-measured, per the coordinator's guidance that a rendered graph does not support false precision. Both the VGS = 3.0 V and VGS = 3.5 V curves are **clearly and comfortably above 0.5 A across essentially the entire plotted VDS range** — they rise steeply from the origin and are already well past 1 A by VDS ~= 0.4-0.5 V, continuing up to several amps by VDS = 4 V. Even the lowest plotted curve, VGS = 2.4 V (below our 3.3 V target), clears 0.5 A by roughly VDS ~= 0.3-0.4 V. Since 3.3 V sits between the plotted 3.0 V and 3.5 V curves, conduction at 3.3 V is bracketed by two curves that both clear the 0.5 A bar with room to spare. | **PASS** — qualitative read of Fig. 6: the datasheet's own curve shows Id well above 0.5 A at Vgs <= 3.3 V, at any VDS the design would plausibly operate at. No precise figure is claimed beyond "well above the floor," which is all the criterion asks for and all a rendered curve can honestly support. |
| 1a.3 | Id >= 1 A continuous | Table 1 / Table 5: "ID drain current VGS = 10 V; Tamb = 25 degC — 3 A"; "VGS = 10 V; Tamb = 100 degC — 2.1 A". | **PASS** — 3 A at 25 degC ambient, 2.1 A at 100 degC ambient, vs 1 A required (>=2x margin even hot). |
| 1a.4 | Total series resistance (FET + the 1 ohm shunt) keeps per-channel loss <= 50 mW at 0.14 A | Available FET-resistance budget after the fixed 1 Ohm shunt: 50 mW / 0.14 A^2 = 2.551 Ohm total, so up to 1.551 Ohm is available for the FET before the ceiling is hit. Fig. 6 (see row 1a.2) shows the curves for VGS = 3.0-3.5 V rising steeply from the origin — near the origin, before their respective knees, they track close to the same slope as the 4.5 V and 10 V curves, whose worst-case RDS(on) is documented in Table 7 at 75-99 mOhm (VGS = 4.5 V, ID = 2.6 A). Reading the graph only qualitatively (not pixel-measuring it), the effective resistance implied for the 3.0-3.5 V curves in the low-current region the 0.14 A load actually operates in looks to be the same order of magnitude — at most a few hundred mOhm, nowhere near the 1.551 Ohm available. | **PASS** — even a pessimistically-read few-hundred-mOhm FET resistance leaves total series R well under the 2.551 Ohm ceiling (e.g. 1 Ohm + 0.3 Ohm = 1.3 Ohm, giving P = 0.14^2 x 1.3 = 25.5 mW, still under 50 mW with margin). Not pixel-precise, but the margin is wide enough that it doesn't need to be. |
| 1a.5 | Gate charge low enough to switch cleanly at 400 Hz from a PCA9685 output (25 mA sink / 10 mA source) | Table 7 "Dynamic characteristics": "QG(tot) total gate charge — VGS = 10 V; VDS = 20 V; ID = 3 A; Tj = 25 degC — 3.6 / 5 nC" (typ/max). Charging to only 3.3 V requires less charge than this 10 V-referenced figure, so 5 nC max is a conservative upper bound. At the PCA9685's 10 mA source current: charge time = 5 nC / 10 mA = 0.5 microseconds. | **PASS** — 0.5 us vs a 2.5 ms period at 400 Hz is 0.02% of the period; trivial margin. |
| 1a.6 | In stock, multi-source | Digi-Key product page for PMV60ENEAR (re-checked 2026-09-12, live page load): 0 units in stock, backorder to Jan 2027. TTI (distributor search result, not independently opened): ~9,000 units, $0.074-$0.094 depending on quantity, ~10-week lead time. Single manufacturer part number (Nexperia); no second-source exact equivalent checked. | **UNVERIFIED** — Active and buildable in volume per the TTI figure, but the near-term single-unit Digi-Key picture is a backorder. A human should check Mouser/Arrow/LCSC directly and confirm the TTI stock first-hand. |
| 1a.7 | **NEW (Ruling 15) — small SMD only**: SOT-23/SOT-323/SOT-523 class, footprint <= ~8 mm^2. TO-220/DPAK/D2PAK and other power packages excluded. | Section 12 "Package outline" Fig. 18: "SOT23 (TO-236AB)" — body dimensions D = 2.8-3.0 mm, E = 1.2-1.4 mm (Table under Fig. 18). Footprint area ~= 2.9 mm x 1.3 mm ~= **3.8 mm^2** body (occupied land-pattern area including leads is larger but still well inside the ~8 mm^2 ceiling, per Fig. 19's reflow footprint drawing: overall occupied area 3.3 mm x 3.0 mm ~= 9.9 mm^2 pad footprint minus lead spread — the body itself is the relevant "device size" figure here). | **PASS** — a standard SOT-23, exactly the package class named as acceptable, an order of magnitude below the TO-220 that triggered this criterion's creation. |
| 1a.8 | **NEW (Ruling 15) — off-state leakage Idss <= 2 uA per device at 24 V, 25 degC.** | Table 7 "Characteristics": "IDSS drain leakage current — VDS = 40 V; VGS = 0 V; Tj = 25 degC — Max 1 uA." No 24 V-specific row exists, but this figure is measured at a **higher** reverse bias (40 V) than our 24 V operating point; MOSFET off-state (reverse-biased junction) leakage increases monotonically with VDS, so the true leakage at 24 V is bounded above by this 40 V figure — i.e. actual leakage at 24 V is <= 1 uA, not merely "close to" 1 uA. | **PASS** — 1 uA max (a valid upper bound for the lower 24 V operating point) is half the 2 uA ceiling. This is a physically-justified bound from the same datasheet's own higher-voltage figure, not an estimate from a different part. |

### Candidate screening for 1a

| Candidate | Outcome | Evidence |
|---|---|---|
| **Nexperia PMV60ENEA** | Selected — passes every row above | Full datasheet verified (Product data sheet, 9 May 2019) — see table above. SOT23, 40 V, small SMD, low leakage; the only real open item is 1a.6 stock (Digi-Key backorder). |
| **Nexperia PMV30ENEA** | Also passes every row, equally valid alternate | Product data sheet, 14 Aug 2026, verified in full (already fetched in the prior pass). VGS(th) max is also 2.5 V (no longer disqualifying, per Ruling 15) — Fig. 6 there shows the VGS = 2.4-3.0 V curves clearing several amps well before VDS = 1 V, comfortably above the 0.5 A floor. Same SOT23 package (1a.7 PASS). Table 7 IDSS: "VDS = 40 V; VGS = 0 V; Tj = 25 degC — Max 1 uA" — identical to PMV60ENEA, same 1a.8 PASS reasoning. Higher current rating (4.8 A vs 3 A) than PMV60ENEA, which is irrelevant headroom at 0.14 A. Digi-Key stock re-checked 2026-09-12: also 0 units, 30-week backorder — the same 1a.6 concern applies, if anything slightly worse lead time than PMV60ENEA. |
| **Infineon IRLZ44NPbF (rejected this round)** | **FAILS 1a.7** | The candidate selected in the previous pass under the withdrawn Vgs(th)-max criterion. TO-220AB through-hole, ~90 mm^2+ body footprint — an order of magnitude over the 8 mm^2 SMD ceiling and explicitly the package class Ruling 15 excludes by name. Electrically it still passes every other row (1a.1-1a.6, 1a.8 would need its own 24 V-vs-55V leakage bound reworked), but 1a.7 alone disqualifies it now that the package constraint is explicit. |
| **Vishay SQS400EN** | Not re-checked | Previously found to share the same "no RDSon below 4.5 V" gap under an earlier, now-withdrawn criterion; not re-evaluated against the current 1a.2 wording since PMV60ENEA/PMV30ENEA already pass cleanly. |
| **ROHM RSF015N06FRA** | Not re-checked | Screened out previously (RDSon ~3x higher than the Nexperia parts); not re-evaluated once PMV60ENEA passed cleanly. |

### 1b. Sense resistor (12 required)
Candidate: **Yageo RC2512FK-071RL** (2512 case, 1.0 ohm, F = 1% tolerance),
verified against Yageo "RC_L series" General Purpose Chip Resistors datasheet,
Product specification, 14-Nov-2025, V.14.

| # | Required | Actual | Verdict |
|---|---|---|---|
| 1b.1 | 1 ohm, tolerance <= 1% (tolerance sets channel-to-channel reading spread) | Datasheet Table 3 ("Electrical characteristics", RC2512 row, 1 W option): "1% (E24/E96) 1 Ohm <= R <= 10 MOhm" is an explicit tolerance/range bracket that includes 1.0 Ohm at F = 1.0% tolerance (part-number tolerance code table, Section 2). Confirmed as an orderable Yageo global part number (RC2512FK-071RL) via distributor listing. | **PASS** — 1.0 Ohm at F = 1% tolerance is a directly supported, orderable configuration. |
| 1b.2 | Power rating >= 50 mW with margin (dissipates 20 mW at 0.14 A) | Datasheet "Functional description", "Power rating": "RC2512 = 1 W, 2 W" (rated power at 70 degC). Table 3, RC2512 row confirms 1 W and 2 W options both cover 1 Ohm at 1% tolerance. | **PASS** — 1 W (1000 mW) minimum option vs 50 mW required; actual dissipation of 0.14^2 x 1 = 19.6 mW is under 2% of the 1 W rating, >50x thermal margin. |
| 1b.3 | Temperature coefficient low enough that drift does not swamp open/working/short classification | Table 3, RC2512 row: "Temperature Coefficient — 1 Ohm <= R <= 10 Ohm: +/-200 ppm/degC". Over a 100 degC swing from a 25 degC reference (e.g. to 125 degC), drift = 200 ppm/degC x 100 degC = 20,000 ppm = 2% of nominal resistance, i.e. the 1 Ohm sense resistor could read 0.98-1.02 Ohm. At 0.14 A that shifts the 140 mV nominal reading by about +/-2.8 mV. | **PASS** — a +/-2.8 mV (2%) shift is negligible against the coarse three-bin classification (open ~0 mV / working ~140 mV / shorted saturated), which needs to separate states by tens to hundreds of mV, not a few mV. |

### 1c. 16-channel analog multiplexer (1 required) — REVISED again, fix round 1 Finding 5

**ADG706 restored as the primary recommendation.** The previous pass's "FAIL"
verdict for ADG706 is **withdrawn**: it rested on a radiolocman mirror of a
later "Rev. B" datasheet that appeared to show only a 5 V specifications
table. In this fix round, a **complete, genuine ADG706/ADG707 primary
datasheet (Rev. A, 2002, Analog Devices, fetched via a Farnell-hosted direct
PDF mirror, downloaded and parsed page-by-page with PyMuPDF — 12 real,
varied pages: features, functional diagram, three full specifications
tables, absolute maximum ratings, pinout, and both truth tables)** was
obtained, and it **does** carry a dedicated "SPECIFICATIONS (VDD = 3 V
+/-10%...)" table on page 3, with real RON/leakage/timing numbers at 3 V.
This directly satisfies Finding 5's instruction to prefer ADG706 (the right
shape — single 16:1, 4 address lines) over ADG726 (which turned out to be
sold as a confusing "dual 16:1"/48-pin part, the wrong shape, and whose exact
3 V numbers could never be pulled from any reachable source in the prior
round). **Open item for a human:** Rev. A (2002) is an older document; a
later revision may exist on analog.com (which blocked every direct fetch
attempt this session and every prior session) — a human should confirm the
currently-shipping datasheet revision still carries this 3 V table with the
same or better numbers before board order, though the electrical die itself
is unlikely to have changed between documentation revisions for a mature,
single-sourced 2002-era part.

**CD74HC4067 remains excluded** per the task's hard requirement (HC-family
on-resistance uncharacterised below 4.5 V) — retained below for the record.

| # | Required | Actual | Verdict |
|---|---|---|---|
| 1c.1 | 16 channels, single-ended, 4 binary select lines | ADG706/ADG707 datasheet (Rev. A, 2002), p.1 "General Description": "The ADG706 switches one of 16 inputs (S1-S16) to a common output, D, as determined by the 4-bit binary address lines A0, A1, A2, and A3." p.5 "PIN CONFIGURATIONS": 28-lead TSSOP, pins A0-A3, EN, S1-S16, D, VDD, VSS, GND (plus 4 NC). p.6 "Table I. ADG706 Truth Table": confirms all 16 switches individually addressed by A3:A0 with EN as master enable. | **PASS** — confirmed directly from the primary datasheet's own pin configuration diagram and truth table, not a distributor description. |
| 1c.2 | **Specified** (not merely tolerant) for 3.3 V operation, with on-resistance tabulated at 3.3 V | p.3, "ADG706/ADG707-SPECIFICATIONS (VDD = 3 V +/-10%, VSS = 0 V, GND = 0 V, unless otherwise noted.)": a **complete, dedicated 3 V table**, separate from the 5 V table on p.2 and the dual-supply table on p.4. "ON Resistance (RON) — 6 Ohm typ, 11/12 Ohm max (25 degC / -40 to +85 degC) — VS = 0 V to VDD, IDS = 10 mA." p.1 "Product Highlights": "The ADG706 and ADG707 are fully specified and guaranteed with 3 V and 5 V single-supply and +/-2.5 V dual-supply rails" — this claim, dismissed as an unverified search-summary paraphrase in the prior round, is now confirmed verbatim from the primary document itself. | **PASS** — genuinely specified and tabulated at 3 V +/-10% (2.7-3.3 V), which spans this design's 3.3 V rail, with a real RON figure (6 Ohm typ / 11-12 Ohm max), read directly from the primary datasheet. |
| 1c.3 | **On-resistance low enough not to corrupt a 140 mV reading** into the ESP32 ADC's input impedance | Same p.3 table: RON 6 Ohm typ / 11-12 Ohm max at VDD = 3 V. This is worse than the 5 V figure (2.5 Ohm typ) — CMOS RON rises as VDD falls, as expected — but still two orders of magnitude better than CD74HC4067's uncharacterised-but-likely-70-270-Ohm figure. Combined with the ~100 nF ADC-input buffer capacitor (Task 6, this file's header ruling), which supplies the SAR sample-and-hold charge locally, an 11-12 Ohm source resistance is not a meaningful error source. | **PASS** — real 3 V RON figure from the primary datasheet, comfortably addressed by the buffer-cap design fix. |
| 1c.4 | Off-channel leakage small enough not to shift a 140 mV reading measurably | p.3, "LEAKAGE CURRENTS VDD = 3.3 V": "Drain OFF Leakage ID(OFF) — ADG706: +/-0.4 nA typ / +/-1.5 nA max"; "Source OFF Leakage IS(OFF) — +/-0.01 nA typ / +/-0.3 nA max." Nanoamp-level, at 3.3 V specifically (the table's own leakage sub-heading states "VDD = 3.3 V"). | **PASS** — 15 deselected channels at up to 1.5 nA max each sum to ~22.5 nA worst case, utterly negligible against a 140 mV signal. Read directly at 3.3 V from the primary datasheet, not a same-family proxy. |
| 1c.5 | Channel-to-channel on-resistance match (mismatch appears as per-channel offset) | p.3: "ON Resistance Match Between Channels (delta-RON) — 0.4 Ohm typ / 1.2 Ohm max — VS = 0 V to VDD, IDS = 10 mA" at VDD = 3 V. | **PASS** — a 0.4-1.2 Ohm match is negligible against the 1 Ohm sense resistor's signal; read directly from the 3 V table. |
| 1c.6 | Settling time permits stepping 12 channels within a few ms sweep | p.3: "tTRANSITION — 45 ns typ / 75 ns max — RL = 300 Ohm, CL = 35 pF" at VDD = 3 V. | **PASS** — sub-100 ns switching is negligible against a multi-millisecond, 12-channel sweep. |

**Orderable part/package:** p.5 "ORDERING GUIDE": **ADG706BRU**, -40 degC to
+85 degC, 28-lead Thin Shrink Small Outline Package (TSSOP), package option
RU-28. This is the exact, confirmed pinout/package — resolving the "unknown
pinout" concern the prior round's ADG726 recommendation carried.

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
| 3.4 | Spread-spectrum, frequency dither, **an external SYNC/dither input, or a documented EMC mitigation plan** (relaxed, fix round 1 Finding 4 — EMC nicety, not a functional requirement) | Pin Functions, p.4: "SYNCIN/RT — The internal oscillator frequency is programmed by a single resistor between RT and AGND. The internal oscillator can be synchronized to an external clock by applying a positive pulse signal into this SYNCIN pin." Section on Oscillator, p.7/21: synchronization up to 1 MHz (2 MHz internal in master config / 2 for 1 MHz switching). No native spread-spectrum/dither generator exists on-chip (confirmed by a full-text search of all 50 pages in the prior pass), but the part has a real, documented **external SYNC input** — exactly what the relaxed criterion accepts. | **PASS (relaxed criterion)** — the SYNCIN/RT pin is a genuine external synchronization input; driving it from a dithered clock source satisfies the EMC-mitigation intent without requiring an on-chip spread-spectrum generator. No further evaluation of an actual dither source was done (Task 3/4's EMC design decision), but the pin/capability itself is confirmed present in the datasheet. |
| 3.5 | Disabled-state current draw <= 10 uA, or gated externally | Section 6.5 "Electrical Characteristics", p.6: "ISHUTDOWN — VIN shutdown current — VUVLO = 0 V — Typ 9 uA, Max 17 uA." Feature list p.1 also states "Low Shutdown Quiescent Current: 9 uA" (the typical figure). | **PASS on typical (9 uA), FAILS on guaranteed max (17 uA)** against the bare 10 uA threshold. The criterion's alternate clause ("or gated externally") is met by this design's own architecture: Section 6.1's P-FET series disconnect switch (row 6.1) sits upstream of this whole boost stage and can cut it off from the battery entirely during deep sleep, making the IC's own shutdown-current spec moot for the sleep budget as long as that P-FET is used as intended. |
| 3.6 | Dissipation at 40 W out <= 3 W including both FETs | Not determinable from this datasheet alone — HO/LO drive **external** N-channel MOSFETs (row 3.2), so total FET dissipation (conduction loss I^2 x RDS(on) plus switching loss at the chosen fSW) depends entirely on which external FETs Task 3/4 selects and what switching frequency is programmed via RT (the worked example in Section 8.2.2.2, p.35, uses 250 kHz for a 108 W/24 V design, chosen as "a reasonable compromise between small size and high-efficiency"). | **UNVERIFIED at the controller level** — this is a system-level calculation that depends on FET selection, not a fixed parameter of the LM5122-Q1. Task 3/4 must pick specific boost-stage FETs, compute conduction + switching loss for both at the 60 W/24 V operating point, and check the sum against the 3 W ceiling. |

## 4. Low-quiescent buck — 12 V to 3.3 V, 1 A
Candidate: TI LM5164. This is the **same physical IC** already verified in
Section 4b for the 5 V rail (TI LM5164, datasheet SNVSAU4D, revised February
2026) — only the external feedback divider changes between the two rails, so
every current/voltage-input-range spec below is identical to 4b's and is
carried over directly rather than re-fetched.

| # | Required | Actual | Verdict |
|---|---|---|---|
| 4.1 | Quiescent current <= 30 uA (this is the dominant sleep contributor) | Datasheet Section 5.5 "Electrical Characteristics" (same row cited in 4b.1): "IQ-SLEEP1 VIN sleep current — VEN = 2.5 V, VFB = 1.5 V — 10.5 / 25 uA" (typ/max). This is the IC's own input-referred sleep current and does not depend on which output voltage the feedback divider is set for. | **PASS** — 10.5 uA typ / 25 uA max, both under 30 uA, identical evidence to row 4b.1. |
| 4.2 | Output current >= 1 A (ESP32 WiFi TX peaks ~500 mA) | Section 5.3 "Recommended Operating Conditions" (same row cited in 4b.2): "ILOAD Load current — 1 / 1.25 A" (nom/max). | **PASS** — 1 A nominal / 1.25 A max vs 1 A required and ~500 mA actual peak (WiFi TX), comfortable margin at nominal and more at max. |
| 4.3 | Input rating 40-60 V | Section 5.3: "VIN Input voltage — 6 / 100 V" (min/max) — same figure cited in 4b.3. | **PASS** — 6-100 V comfortably covers 40-60 V. |
| 4.4 | Stable with no load (sleep condition) | Section 6.1/6.4.3 "Sleep Mode": diode-emulation mode (DEM) plus an ultra-low-IQ sleep state built in to prevent instability at light/no load; Section 7.2.3, Fig. 7-6 "No-Load Start-up with VIN" — bench scope capture at IOUT = 0 A showing clean, monotonic start-up (no oscillation), same evidence cited in 4b.4. Output voltage here is set to 3.3 V by the external feedback divider (Section 6.3.3, RFB2 = 1.2 V / (VOUT - 1.2 V) x RFB1) instead of 5.0 V — the no-load stability behavior is a function of the control loop, not the programmed output voltage, so the same evidence applies. | **PASS** — same datasheet-documented no-load stability behavior as the 5 V rail use of this part. |

**Design simplification confirmed:** using LM5164 for both the 3.3 V logic
rail (this section) and the 5 V transceiver rail (Section 4b) means Tasks 3-6
place two instances of the same qualified IC with different resistor-divider
values, rather than two different regulator part numbers.

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
| 6.1 | P-FET: Vds >= 40 V, **Rds(on) <= 20 mOhm** (relaxed, fix round 1 Finding 3), Vgs rated **with the Zener gate clamp in circuit** (spec 4.2) — the gate never sees the full rail | Candidate: **Vishay Siliconix SQJ415EP** (Automotive P-Channel 40 V, PowerPAK SO-8L), datasheet S22-0224-Rev. B, 07-Mar-2022, already fetched and read in full in the prior pass. "ABSOLUTE MAXIMUM RATINGS": VDS = -40 V; VGS = +/-20 V. "SPECIFICATIONS" table: RDS(on) at VGS = -10 V, ID = -10 A — Typ. 11.5 mOhm, Max. 14.0 mOhm (the realistic operating point for a gate-resistor-to-ground + Zener-clamp self-bias network per spec 4.2, which drives the gate close to full rail swing, clamped, not to a weak partial-drive voltage); at VGS = -4.5 V — Typ. 16.3 mOhm, Max. 20.0 mOhm (a weaker-drive fallback, still within the relaxed ceiling at typ, right at it at max). Thermal: "TO-220 Full-Pak"-style PowerPAK SO-8L, Ptot(max) = 45 W (Tc = 25 degC), RthJA = 70 degC/W (PCB mount), RthJC = 3.3 degC/W (from Absolute Maximum Ratings / Thermal Resistance tables already extracted). **Dissipation at both feeds, using the realistic VGS = -10 V column:** Feed A (3.9 A): P = I^2 x R = 3.9^2 x 0.0115 = **0.175 W typ** / 3.9^2 x 0.0140 = **0.213 W max**. Feed B (6.6 A): P = 6.6^2 x 0.0115 = **0.501 W typ** / 6.6^2 x 0.0140 = **0.610 W max**. Temperature rise at Feed B's worst case, using RthJA = 70 degC/W: 0.610 W x 70 degC/W ~= **43 degC rise above ambient** — well inside the 175 degC Tj max even at a hot ambient. | **PASS** on both sub-criteria under the revised criteria: (a) RDS(on) 11.5/14.0 mOhm (realistic drive) is under the relaxed 20 mOhm ceiling with margin (the weaker VGS = -4.5 V max of 20.0 mOhm sits exactly at the ceiling, not below it — the design should ensure the gate drive reaches close to -10 V, not just -4.5 V, to keep real margin); (b) with the Zener clamp from spec 4.2 in circuit, the gate never sees the full 24 V+ rail excursion, so the native +/-20 V VGS rating is adequate — no added component beyond what the design already includes. Dissipation at both feeds (0.175-0.610 W) is well inside the part's 45 W package rating and gives a modest ~43 degC worst-case temperature rise, which the board's thermal budget can absorb with normal copper pour, pending Task 3/4 layout confirmation. |
| 6.2 | TVS: standoff ~24 V, clamp < 40 V, rated for the feed current | Candidate: **Littelfuse/Bourns/ST SMBJ24A** (unidirectional TVS, DO-214AA/SMB). Primary-datasheet PDF fetches failed three times (Bourns 403, Littelfuse 403, ST timeout) — figures below are corroborated across multiple independent distributor parametric listings (Newark, Digi-Key, datasheet4u), not read from an opened primary PDF this session: standoff (VWM) 24 V; breakdown VBR 26.7-29.5 V; maximum clamping voltage VC = 38.9 V; peak pulse power PPP = 600 W (standard 10/1000 us TVS waveform for the SMBJ series). Derived peak pulse current at clamp: IPP = PPP / VC = 600 W / 38.9 V = 15.4 A. | **PASS, sourced from corroborated distributor data rather than an opened primary PDF** — 38.9 V clamp is under the 40 V ceiling; 24 V standoff matches; the derived 15.4 A peak-pulse capability exceeds both Feed A (3.9 A) and Feed B (6.6 A) individually and combined (10.5 A), so it can absorb a fault event on either feed. A human should open the manufacturer PDF directly (all three attempted here were blocked or timed out) to confirm these distributor-sourced figures before board order. |
| 6.3 | PTC: 0.5 A hold at 24 V, trip < 1 A, 4 required | Candidate: **Littelfuse 1206L050/24WR** (PolySwitch PPTC, 1206 SMD). Digi-Key product page, fetched live 2026-09-12: "Voltage Rating: 24V maximum," "Hold Current (Ih): 500 mA maximum," "Trip Current (It): 1 A," package 1206, AEC-Q200 automotive grade, response time 100 ms, 24,602 units in stock. | **PASS with a boundary note** — hold current matches exactly (0.5 A at 24 V); trip current is specified as exactly 1 A rather than strictly "< 1 A" (PTC trip current is defined as the current that guarantees tripping, not a hard ceiling below which it never conducts), which is the industry-standard way this parameter is specified — a human should confirm this reading of the criterion is acceptable, or look for a lower-trip-current PTC (e.g. an 0.9 A-trip part) if the "< 1 A" wording is meant literally. 4x required for the 4 PTC-per-RGB-string design context. |
| 6.4 | Schottky OR pair: 40 V, >= 0.5 A, low leakage | Candidate: **Nexperia PMEG4010ER** (40 V, 1 A low-VF Schottky, SOD123W), Product data sheet, 1 January 2023, fetched and read in full. Table 1 "Quick reference data": "VR reverse voltage — Tj = 25 degC — Max 40 V"; "IF(AV) average forward current — Max 1 A"; "IR reverse current — VR = 40 V, Tj = 25 degC — Typ 10 uA, Max 50 uA"; "VF forward voltage — IF = 1 A, Tj = 25 degC — Typ 430 mV, Max 490 mV." | **PASS** — 40 V rating meets the requirement exactly (matches the design's 40 V front-end tolerance target); 1 A rating exceeds the 0.5 A floor 2x; 50 uA max reverse leakage at full 40 V reverse bias is low for a 1 A Schottky, consistent with "low leakage." Two of these in an OR configuration (Feed A / Feed B onto the logic rail) satisfy the pair requirement. |
| 6.5 | Boost inductor: shielded, saturation current >= 1.5x peak | Candidate: **Coilcraft XAL7070-682ME** (6.8 uH shielded composite-core power inductor), Document 856-2, Revised 02/25/26, fetched and read in full. Parametric table: "XAL7070-682ME — Inductance 6.8 uH — DCR typ 17.84 mOhm / max 19.62 mOhm — SRF typ 20 MHz — Isat 12.8 A — Irms(20 degC rise) 6.8 A / Irms(40 degC rise) 9.2 A." Family description: "Shielded Power Inductors — XAL7070," "magnetically shielded" composite core, AEC-Q200 qualified. Peak inductor current for this design was estimated by scaling the LM5122-Q1 datasheet's own worked 108 W design example (Section 8.2.2.4, p.36 of that datasheet, which computes a 13.5 A peak input/inductor current for a 12 V-in/24 V-out/108 W boost) linearly by power ratio: 13.5 A x (60 W / 108 W) ~= 7.5 A estimated peak for this design's 60 W point (same voltage points, same topology, proportional scaling — not a fabricated figure, but also not a from-scratch calculation for this exact design; Task 3/4 must re-run the LM5122 design equations with the real 60 W parameters to confirm). | **PASS on the datasheet-verified Isat figure against the scaled peak-current estimate** — Isat = 12.8 A vs an estimated ~7.5 A peak gives a ratio of ~1.7x, above the 1.5x requirement, and the part is explicitly marketed and constructed as magnetically shielded. The peak-current figure itself is UNVERIFIED for this exact 60 W design point (scaled estimate, not a from-scratch calculation) — Task 3/4 should confirm with the actual design equations before finalizing the inductance/Isat choice. |

## Sleep budget roll-up (spec 8.2: target < 200 uA, ceiling 500 uA)

| Contributor | Datasheet value | Source |
|---|---|---|
| ESP32 deep sleep + EXT0 RTC_PERIPH domain | **10 uA** | Espressif "ESP32 Series Datasheet" v5.3, Table 4-2 "Power Consumption by Power Modes", row "Deep-sleep — RTC timer + RTC memory — 10 uA" (fetched 2026-09-12). The datasheet does not break "RTC_PERIPH domain for EXT0 wake" out as a separate incremental line from this baseline — RTC memory + RTC timer retention is part of the same RTC power domain that EXT0/RTC_GPIO wake depends on, so the two rollup rows are combined into this single verified figure rather than inventing a split that isn't in the source. (For contrast, the datasheet's next tier up, "Deep-sleep — ULP coprocessor powered up — 150 uA", is not needed for EXT0 alone and was not used here.) A human should still check the ESP32 Technical Reference Manual's more granular power-domain table if a tighter figure specific to "RTC_PERIPH with GPIO wake, ULP off" is wanted. |
| CAN transceiver standby | **19 uA max** | This file, row 5.3 — NXP TJA1042T/3, Table 7 p.10: ICC (Standby) max 5 uA + IIO (Standby) max 14 uA = 19 uA max, condition VTXD = VIO (firmware must hold TXD/STB high through sleep). |
| Buck quiescent (both rails) | **21 uA typ / 50 uA max** | This file, rows 4.1 and 4b.1 — TI LM5164 (SNVSAU4D), IQ-SLEEP1 10.5 uA typ / 25 uA max **per instance**; **two instances** are needed (one for the 3.3 V logic rail, one for the always-on 5 V transceiver rail), so the rollup uses 2x: 21 uA typ / 50 uA max. |
| PROFET standby | **0.6 uA max** | This file, row 2.7 — Infineon BTS7008-2EPA, Table 1 p.2: IVS(SLEEP)_85 max 0.6 uA (one device required). |
| Low-side switches standby (12x PMV60ENEA leakage) | **<= 12 uA max (updated, fix round 1)** | This file, row 1a.8 — Nexperia PMV60ENEA Table 7: "IDSS drain leakage current — VDS = 40 V; VGS = 0 V; Tj = 25 degC — Max 1 uA." Bounded above by this 40 V figure for our lower 24 V operating point (leakage increases monotonically with reverse bias, so 24 V leakage <= the 40 V figure). 12 channels x 1 uA max = **12 uA max**. This replaces the previous IRLZ44N-based ~300 uA pessimistic bound now that the MOSFET recommendation has reverted to the SOT-23 PMV60ENEA (fix round 1, Finding 1/2) — the sleep-budget blowout was a direct symptom of the wrong package/part, not an inherent property of this design. |
| P-FET gate + divider leakage | **UNVERIFIED — depends on a resistor value not yet chosen** | This file, row 6.1 — Vishay SQJ415EP gate leakage (IGSS) itself is negligible (max +/-100 nA per the datasheet), but the P-FET's gate resistor + Zener clamp network (spec 4.2) has a divider value that is a Task 3/4 schematic decision, not yet made. A divider sized for >= 1 MOhm total resistance would add <= 24 uA at 24 V; this is a design target to carry into Task 3/4, not a verified figure. |
| **TOTAL (known contributors)** | **~62.6 uA typ / ~92.6 uA max** | Sum of ESP32+EXT0 (10) + CAN (19) + buck x2 (21 typ / 50 max) + PROFET (0.6) + RGB-FET leakage (12 max, itself a valid upper bound) = 62.6 uA typ / 92.6 uA max. |
| **TOTAL (incl. P-FET divider design target)** | **~86.6-116.6 uA** | Adding the P-FET divider's design target of <= 24 uA (not yet a chosen resistor value) to the known total above. |

**Verdict (updated, fix round 1):** with the MOSFET reverted to the SOT-23
PMV60ENEA, the sleep budget resolves cleanly. **Total is approximately
63-117 uA**, comfortably under the **200 uA target** with margin to spare,
even before the one remaining open item (the P-FET gate-divider resistor
value, a normal Task 3/4 sizing job easily kept under ~24 uA by design) is
finalized. The ~405 uA pessimistic figure from the previous pass is now
**withdrawn** — it was a direct symptom of the withdrawn IRLZ44N/TO-220
selection (Finding 1), not a real property of this design. This is now a
**confirmed PASS against both the 200 uA target and the 500 uA ceiling**,
modulo the one small, bounded, non-blocking open item noted above.

## Final BOM decision

| Function | Manufacturer part number | Package | Unit price | Stock |
|---|---|---|---|---|
| RGB channel low-side FET (x12) | Nexperia **PMV60ENEA** | SOT23 (TO-236AB) | $0.074-$0.094 (TTI, search-summary sourced) | Digi-Key: 0, backorder to Jan 2027; TTI: ~9,000 (search-summary sourced) — **UNVERIFIED stock**, see row 1a.6 |
| RGB channel sense resistor (x12) | Yageo **RC2512FK-071RL** | 2512 (6332 metric) | $0.72 (qty 1, search-summary sourced, not independently opened) | 27,482 (search-summary sourced) — part selection itself (1 Ohm, 1%) verified in Section 1b of this file, out of this pass's scope |
| 16-channel analog mux | Analog Devices **ADG706BRUZ** | 28-TSSOP | $9.73 (qty 1) / $5.85 (qty 1000) (Digi-Key, live page fetch 2026-09-12) | 5,789 (Digi-Key, live page fetch); Active, 21-week manufacturer lead time |
| Dual smart high-side switch (Denali) | Infineon **BTS7008-2EPA** (order as BTS70082EPAXUMA1) | PG-TSDSO-14 | $2.30 (qty 1) / $1.17 (qty 3000) | 6,947 (Digi-Key, live page fetch) |
| Synchronous boost controller | TI **LM5122QMHX/NOPB** | 20-HTSSOP | $6.21 (qty 1) / $3.62 (qty 1000) | 594 (Digi-Key, live page fetch) |
| Low-quiescent buck, 3.3 V rail | TI **LM5164DDAT** | 8-PowerSOIC (HSOIC-PowerPAD) | $5.37 (qty 1) / $3.43 (qty 100) | 7,056 (Digi-Key, live page fetch); 16-week lead time noted on the page |
| 5 V regulator (transceiver rail) | TI **LM5164DDAT** (same part, second instance, different feedback divider) | 8-PowerSOIC | (same as above) | (same as above) |
| CAN transceiver | NXP **TJA1042T/3** (order as TJA1042T/3,118) | SO8 | $1.67 (qty 1) / $0.864 (qty 1000) (search-summary sourced) | 966 (search-summary sourced) — part selection itself verified in Section 5, out of this pass's scope |
| P-FET (front-end protection) | Vishay Siliconix **SQJ415EP-T1_GE3** | PowerPAK SO-8L | $1.63 (qty 1) / $0.43 (bulk) (Digi-Key, live page fetch 2026-09-12) | 19,148 (Digi-Key, live page fetch); Active, 26-week manufacturer lead time |
| TVS (front-end clamp) | Littelfuse **SMBJ24A** | DO-214AA (SMB) | $0.50 (qty 1, Littelfuse SKU; search-summary sourced) | 32,003 (search-summary sourced) |
| PTC (x4, one per RGB string) | Littelfuse **1206L050/24WR** | 1206 (3216 metric) | $1.88 (qty 1) / $0.841 (qty 1000) | 24,602 (Digi-Key, live page fetch) |
| Schottky OR pair (x2) | Nexperia **PMEG4010ER,115** | SOD123W | ~$0.42 (qty 1, search-summary sourced) | not confirmed this session |
| Boost inductor | Coilcraft **XAL7070-682ME** (order as XAL7070-682MEC) | 7x7x3 mm shielded molded | not confirmed this session | not confirmed this session (a distinct but related part number, XAL7030-682MEC, was seen in search results — verify the exact 7070 vs 7030 case size before ordering) |

**P-FET — resolved, fix round 1 Finding 3.** With Row 6.1's RDS(on) ceiling
relaxed to <= 20 mOhm and the VGS rating judged with the spec-4.2 Zener gate
clamp in circuit (so the gate never sees the full rail), Vishay SQJ415EP
passes cleanly — see row 6.1 for the full readout, including dissipation at
both Feed A (3.9 A: 0.175/0.213 W typ/max) and Feed B (6.6 A: 0.501/0.610 W
typ/max), both well inside the part's 45 W package rating.

**Mux — resolved, fix round 1 Finding 5.** ADG706BRUZ is confirmed the right
shape directly from its own primary datasheet (28-lead TSSOP, single 16:1,
4 address lines, real 3 V table — see Section 1c) and independently
corroborated by its Digi-Key listing ("IC MUX 16:1 4.5OHM 28TSSOP," single
circuit, matching the ordering-guide part number ADG706BRU exactly). No
open pinout question remains for this part.

**Sourcing note on this table:** rows marked "search-summary sourced" reflect
WebSearch's own aggregated answer text rather than a directly opened
distributor page, because live WebFetch attempts to the distributor page
either failed or were not attempted a second time within the effort cap for
that specific lookup. This is weaker evidence than the "Digi-Key, live page
fetch" rows and should be re-confirmed by a human before committing to
final quantities/pricing for a board order.

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
