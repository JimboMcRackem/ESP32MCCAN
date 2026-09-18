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
| 1a.6 | In stock, multi-source | **RE-CHECKED 2026-09-12 (live Digi-Key fetch this pass):** Digi-Key PMV60ENEAR: **0 in stock, "3,000 expected in stock on 18-Jan-2027," manufacturer standard lead time 30 weeks.** Pricing $0.54 (qty 1) down to $0.102 (qty 9,000, tape & reel). TTI (distributor search result, not independently opened): ~9,000 units, $0.074-$0.094, ~10-week lead time — a viable near-term channel if it holds up under a direct check. **Second-source part number established this pass (PMV30ENEA, see the screening-table entry below): also out of stock** — Digi-Key PMV30ENEAR shows a 30-week backorder (per the existing screening-table finding), and Mouser's PMV30ENEAR listing offers only "notify me when in stock" (WebSearch, 2026-09-12), i.e. no current stock there either. Both Nexperia part numbers are backordered at both major US distributors checked — this looks like a shared wafer/fab constraint across the sibling parts, not a PMV60ENEA-specific problem. No true second-manufacturer equivalent (a different vendor's part) was searched for or found; "multi-source" here means two Nexperia part numbers, not two vendors. | **UNVERIFIED, sourcing position clarified but not resolved.** PMV60ENEA itself will not restock at Digi-Key until 18-Jan-2027 at the earliest. The electrically-qualified second source (PMV30ENEA) does not relieve this — it is backordered too, everywhere checked this pass. The only concrete near-term lead is the TTI ~9,000-unit figure for PMV60ENEA, which is distributor-search-sourced and has never been independently opened. **A human must, in this order:** (1) directly check TTI's own site/quote desk for PMV60ENEA to confirm or refute the ~9,000-unit figure firsthand; (2) check LCSC and Arrow for both PMV60ENEA and PMV30ENEA, since neither was searched this pass; (3) if no distributor stock materializes, plan the build around the 30-week Nexperia lead time (order now against the Jan-2027 date) rather than assuming a workaround exists. |
| 1a.7 | **NEW (Ruling 15) — small SMD only**: SOT-23/SOT-323/SOT-523 class, footprint <= ~8 mm^2. TO-220/DPAK/D2PAK and other power packages excluded. | Section 12 "Package outline" Fig. 18: "SOT23 (TO-236AB)" — body dimensions D = 2.8-3.0 mm, E = 1.2-1.4 mm (Table under Fig. 18). Footprint area ~= 2.9 mm x 1.3 mm ~= **3.8 mm^2** body (occupied land-pattern area including leads is larger but still well inside the ~8 mm^2 ceiling, per Fig. 19's reflow footprint drawing: overall occupied area 3.3 mm x 3.0 mm ~= 9.9 mm^2 pad footprint minus lead spread — the body itself is the relevant "device size" figure here). | **PASS** — a standard SOT-23, exactly the package class named as acceptable, an order of magnitude below the TO-220 that triggered this criterion's creation. |
| 1a.8 | **NEW (Ruling 15) — off-state leakage Idss <= 2 uA per device at 24 V, 25 degC.** | Table 7 "Characteristics": "IDSS drain leakage current — VDS = 40 V; VGS = 0 V; Tj = 25 degC — Max 1 uA." No 24 V-specific row exists, but this figure is measured at a **higher** reverse bias (40 V) than our 24 V operating point; MOSFET off-state (reverse-biased junction) leakage increases monotonically with VDS, so the true leakage at 24 V is bounded above by this 40 V figure — i.e. actual leakage at 24 V is <= 1 uA, not merely "close to" 1 uA. | **PASS** — 1 uA max (a valid upper bound for the lower 24 V operating point) is half the 2 uA ceiling. This is a physically-justified bound from the same datasheet's own higher-voltage figure, not an estimate from a different part. |

### Candidate screening for 1a

| Candidate | Outcome | Evidence |
|---|---|---|
| **Nexperia PMV60ENEA** | **Selected — passes every ELECTRICAL row; row 1a.6 (stock) is UNVERIFIED** | Full datasheet verified (Product data sheet, 9 May 2019) — see table above. SOT23, 40 V, small SMD, low leakage; the only real open item is 1a.6 stock (Digi-Key backorder). |
| **Nexperia PMV30ENEA** | Passes the electrical rows; **does NOT relieve row 1a.6 — also backordered** — **formally re-verified as a second source 2026-09-12, see criteria table below** | Product data sheet, 14 Aug 2026, verified in full (already fetched in the prior pass). VGS(th) max is also 2.5 V (no longer disqualifying, per Ruling 15). Same SOT23 package (1a.7 PASS). Table 7 IDSS: "VDS = 40 V; VGS = 0 V; Tj = 25 degC — Max 1 uA" — identical to PMV60ENEA, same 1a.8 PASS reasoning. Higher current rating (4.8 A vs 3 A) than PMV60ENEA, which is irrelevant headroom at 0.14 A. Digi-Key stock re-checked 2026-09-12: also 0 units, 30-week backorder — the same 1a.6 concern applies, if anything slightly worse lead time than PMV60ENEA. |
| **Infineon IRLZ44NPbF (rejected this round)** | **FAILS 1a.7** | The candidate selected in the previous pass under the withdrawn Vgs(th)-max criterion. TO-220AB through-hole, ~90 mm^2+ body footprint — an order of magnitude over the 8 mm^2 SMD ceiling and explicitly the package class Ruling 15 excludes by name. Electrically it still passes every other row (1a.1-1a.6, 1a.8 would need its own 24 V-vs-55V leakage bound reworked), but 1a.7 alone disqualifies it now that the package constraint is explicit. |
| **Vishay SQS400EN** | Not re-checked | Previously found to share the same "no RDSon below 4.5 V" gap under an earlier, now-withdrawn criterion; not re-evaluated against the current 1a.2 wording since PMV60ENEA/PMV30ENEA already pass cleanly. |
| **ROHM RSF015N06FRA** | Not re-checked | Screened out previously (RDSon ~3x higher than the Nexperia parts); not re-evaluated once PMV60ENEA passed cleanly. |

#### Second-source qualification: PMV30ENEA against Item-3's own criteria (2026-09-12)

This pass was asked to establish PMV30ENEA as a formally verified second source
against a specific criteria list (Vds >= 40 V, Id >= 1 A, Id >= 0.5 A at Vgs
<= 3.3 V read from the curve, Idss <= 2 uA at 24 V, SOT-23-class package). The
one criterion this pass could **independently, freshly verify from a file on
disk** is the curve; the other four are carried over from the prior pass's
"Product data sheet, 14 Aug 2026" full-datasheet read (that PDF is not present
in this repo's `hardware/datasheets/` folder, only the Fig. 6 curve image is —
two attempts this pass to re-fetch the same Mouser-hosted copy of that datasheet,
`mouser.com/datasheet/2/916/PMV30ENEA-1588523.pdf`, both failed with a
connection reset, so they are reported as carried-over, not re-confirmed).

| # | Required | Actual | Verdict |
|---|---|---|---|
| Vds | >= 40 V | Carried over from the prior pass's datasheet read: VDS = 40 V (matches the PMV60ENEA sibling's rating in the same family). Not re-opened this pass. | **PASS (carried over, not independently re-verified this pass)** |
| Id | >= 1 A continuous | Carried over: ID = 4.8 A (VGS = 10 V), higher than PMV60ENEA's 3 A. Not re-opened this pass. | **PASS (carried over, not independently re-verified this pass)** |
| Id @ Vgs <= 3.3 V | >= 0.5 A | **Independently re-verified this pass** by viewing `hardware/datasheets/PMV30ENEA_fig6_output_characteristics.png` directly (image, not text-extracted). The plot shows ID vs VDS (0-5 V) at Tj = 25 degC for VGS = 2.4, 2.6, 2.8, 3.0, 4.5, and 10 V. The VGS = 3.0 V curve rises steeply and is already several amps by VDS ~= 1 V, comfortably clearing 0.5 A almost immediately. The VGS = 2.4 V curve (the weakest plotted curve below the 3.3 V target, and the more conservative bound) rises in a gentle, nearly-linear arc reaching roughly 1.5-2 A by VDS = 5 V — reading it qualitatively (no pixel measurement), it crosses the 0.5 A line at a modest VDS, well inside the plotted range, not near the axis limit. Since 3.3 V sits between the plotted 3.0 V and next-lower 2.8 V curves (both stronger than the 2.4 V curve just described), conduction at 3.3 V is bracketed on both sides by curves that clear 0.5 A with room to spare. | **PASS** — qualitative read of the actual on-disk curve, consistent with (and now independently confirming) the same conclusion the prior pass reported. |
| Idss | <= 2 uA at 24 V | Carried over: Table 7, "IDSS — VDS = 40 V; VGS = 0 V; Tj = 25 degC — Max 1 uA," identical wording to PMV60ENEA's own table, bounding the lower 24 V case the same way (leakage rises monotonically with VDS, so 1 uA at 40 V bounds the 24 V case above). Not re-opened this pass. | **PASS (carried over, not independently re-verified this pass)** |
| Package | SOT-23-class, <= ~8 mm^2 | Carried over: same SOT23 (TO-236AB) package as PMV60ENEA, confirmed via product description and part-number family (both "PMV_ENEA" Nexperia small-signal SOT23 parts). Not re-opened this pass. | **PASS (carried over, not independently re-verified this pass)** |

**Net: PMV30ENEA qualifies as a second source.** The one new criterion this task
added (the curve) is now independently confirmed from the actual file on disk,
not just repeated from an earlier claim. The other four criteria rest on the
prior pass's report of a full datasheet read that this pass could not
re-open (two fetch attempts both failed) — a human who wants all five criteria
independently re-verified in the same sitting should re-attempt
`mouser.com/datasheet/2/916/PMV30ENEA-1588523.pdf` (or Nexperia's own product
page) once more. **Second-sourcing does not currently solve the stock problem**
— see row 1a.6: PMV30ENEA is backordered at both Digi-Key and Mouser, same as
PMV60ENEA.

### 1b. Sense resistor (12 required)
Candidate: **Yageo RC2512FK-071RL** (2512 case, 1.0 ohm, F = 1% tolerance),
verified against Yageo "RC_L series" General Purpose Chip Resistors datasheet,
Product specification, 14-Nov-2025, V.14.

| # | Required | Actual | Verdict |
|---|---|---|---|
| 1b.1 | **10 ohm** (REVISED 2026-09-13 from 1 ohm), tolerance <= 1% — tolerance sets the channel-to-channel spread in readings | | |
| 1b.2 | Power rating >= 100 mW. **REVISED: the >= 1 W / 2512 requirement is WITHDRAWN.** At the real 26.7 mA the shunt dissipates 7 mW normally; even a shorted channel, limited by the boost to ~0.5 A, gives 2.5 W only until the PTC opens. An 0805 or 1206 at 1% suffices | | |
| 1b.3 | Temperature coefficient low enough that drift does not swamp open/working/short classification at the 133-267 mV signal level | | |

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
| 1c.3 | **On-resistance low enough not to corrupt a 133-267 mV reading** into the ESP32 ADC's input impedance | Same p.3 table: RON 6 Ohm typ / 11-12 Ohm max at VDD = 3 V. This is worse than the 5 V figure (2.5 Ohm typ) — CMOS RON rises as VDD falls, as expected — but still two orders of magnitude better than CD74HC4067's uncharacterised-but-likely-70-270-Ohm figure. Combined with the ~100 nF ADC-input buffer capacitor (Task 6, this file's header ruling), which supplies the SAR sample-and-hold charge locally, an 11-12 Ohm source resistance is not a meaningful error source. | **PASS** — real 3 V RON figure from the primary datasheet, comfortably addressed by the buffer-cap design fix. |
| 1c.4 | Off-channel leakage small enough not to shift a 140 mV reading measurably | p.3, "LEAKAGE CURRENTS VDD = 3.3 V": "Drain OFF Leakage ID(OFF) — ADG706: +/-0.4 nA typ / +/-1.5 nA max"; "Source OFF Leakage IS(OFF) — +/-0.01 nA typ / +/-0.3 nA max." Nanoamp-level, at 3.3 V specifically (the table's own leakage sub-heading states "VDD = 3.3 V"). | **PASS** — 15 deselected channels at up to 1.5 nA max each sum to ~22.5 nA worst case, utterly negligible against a 140 mV signal. Read directly at 3.3 V from the primary datasheet, not a same-family proxy. |
| 1c.5 | Channel-to-channel on-resistance match (mismatch appears as per-channel offset) | p.3: "ON Resistance Match Between Channels (delta-RON) — 0.4 Ohm typ / 1.2 Ohm max — VS = 0 V to VDD, IDS = 10 mA" at VDD = 3 V. | **PASS** — a 0.4-1.2 Ohm match is negligible against the 1 Ohm sense resistor's signal; read directly from the 3 V table. |
| 1c.6 | Settling time. **The binding constraint is the I15 10 kOhm series resistor with the 10 nF ADC buffer cap (tau = 100 us, >= 500 us per step), NOT the mux transition** | p.3: "tTRANSITION — 45 ns typ / 75 ns max — RL = 300 Ohm, CL = 35 pF" at VDD = 3 V. | **PASS** — sub-100 ns switching is negligible against a multi-millisecond, 12-channel sweep. |

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

**Design fix carried forward (Task 6):** a ~10 nF buffer capacitor at the
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

> **The datasheet is now held locally** at `hardware/datasheets/infineon_bts7008_2epa_datasheet_en.pdf`
> (added 2026-09-15). The pinout, the sense-resistor sizing and the thermal data that these rows
> could not reach are worked out in **"PROFET — pinout, sense chain and control lines"** below.
> Row 2.2 is unchanged; **row 2.6's conditional is now quantified** there.

| # | Required | Actual | Verdict |
|---|---|---|---|
| 2.1 | Continuous current per channel >= 3.3 A with margin | Table 13 "Electrical Characteristics: Power Stages - 8 mOhm", p.28: "Nominal Load Current per Channel (all Channels Active) — IL(NOM) — Typ. 7.5 A — TA = 85 degC, TJ <= 150 degC" (P_7.5.1.8). | **PASS** — 7.5 A nominal (both channels active simultaneously) vs 3.3 A required, >2x margin. |
| 2.2 | Current sense output resolves a 3.3 A load, ratio documented | Table 22 "Electrical Characteristics: Diagnosis - 8 mOhm", p.53: current-sense ratio kILIS is tabulated at multiple load points bracketing 3.3 A — "Current Sense Ratio at IL = IL14 (2.8 A): -5.8%/+5.8%, Typ. 5400" (P_9.7.1.18); "Current Sense Ratio at IL = IL16 (5.5 A): -4.0%/+4.0%, Typ. 5450" (P_9.7.1.20). At 3.3 A, IS output current = IL/kILIS ~= 3.3 A / 5400 ~= 0.61 mA. | **PASS** — the ratio is explicitly documented at points bracketing 3.3 A (2.8 A and 5.5 A) with tolerance <=6%, giving a clean, resolvable IS current for an external sense resistor/ADC. |
| 2.3 | 3.3 V logic compatible inputs (no level shifter needed) | Section 5.1 "Input Pins (INn)", p.13, verbatim: "The input circuitry is compatible with 3.3V and 5V microcontroller." Table 7 "Electrical Characteristics: Logic Pins - General", p.14: "Digital Input Voltage Threshold — VDI(TH) — Min 0.8 V, Typ 1.3 V, Max 2 V" (P_5.4.0.1). A 3.3 V GPIO driving high sits 1.3 V above the 2 V max threshold (guaranteed HIGH detection); 0 V is below the 0.8 V min threshold, so a grounded input is a guaranteed LOW. | **PASS** — explicit datasheet statement plus a threshold table that a 3.3 V logic swing clears with margin on both ends; no level shifter needed. |
| 2.4 | PWM capable at 150 Hz | Table 12 "Electrical Characteristics: Power Stages - PROFET", p.26: "Switch-ON Time — tON — Max 110 us" (P_7.4.1.3); "Switch-OFF Time — tOFF — Max 100 us" (P_7.4.1.4), both at VS = 13.5 V. | **PASS** — worst-case combined switching transition (210 us) is 3.1% of a 150 Hz period (6.667 ms); leaves >96% of the period free for duty-cycle range, comfortably supporting PWM dimming at 150 Hz. |
| 2.5 | Integrated short-circuit, overcurrent, thermal shutdown | Datasheet Overview, p.2, "Protection Features": "Absolute and dynamic temperature limitation with controlled restart"; "Overcurrent protection (tripping) with Intelligent Restart Control"; "Undervoltage shutdown"; and "Diagnostic Features": "Short circuit to ground and battery." | **PASS** — all three required protections plus undervoltage shutdown are named, integrated features. |
| 2.6 | On-resistance gives <= 0.25 W for the pair at 3.3 A each | Table 13, p.27-28: "ON-State Resistance at TJ = 25 degC — RDS(ON)_25 — Typ. 9 mOhm" (P_7.5.1.1, not subject to production test); "ON-State Resistance at TJ = 150 degC — RDS(ON)_150 — Max. 16 mOhm" (P_7.5.1.2). Pair dissipation at 3.3 A each: at 25 degC typ, P = 2 x 3.3^2 x 0.009 = 0.196 W; at 150 degC max, P = 2 x 3.3^2 x 0.016 = 0.349 W. | **PASS at 25 degC typical** (0.196 W < 0.25 W) **but FAILS at the 150 degC worst-case max rating** (0.349 W > 0.25 W). This is a real thermal-margin question, not a datasheet gap: whether the device actually reaches 150 degC junction under this design's duty cycle and PCB copper/thermal relief is a Task 3 layout question. Flag for the schematic/layout pass: verify junction temperature stays low enough (via thermal simulation or bench measurement) that RDS(on) stays closer to the 25 degC figure, or accept reduced margin at temperature extremes. |
| 2.7 | Standby current <= 20 uA | Table 1 "Product Summary", p.2: "Maximum current in Sleep mode (TJ <= 85 degC) — IVS(SLEEP)_85 — 0.6 uA." Section 6.1.3 "Sleep mode", p.16: entered when all digital inputs (INn, DEN, DSEL) are low; outputs OFF, current consumption minimum. | **PASS** — 0.6 uA max vs 20 uA required, >30x margin. (Note: Stand-by mode, entered with DEN high and inputs low, has higher consumption per Section 6.1.4 because diagnosis stays active — this is not the mode used for the sleep-budget rollup, which assumes full Sleep mode.) |

## 3. Boost converter — 12 V to 24 V, ~8 W
**SELECTED 2026-09-13: TI LM51571-Q1** (was LM5122-Q1). Verified from the primary datasheet,
`hardware/datasheets/lm51571-q1.pdf`, held locally — the first part on this project verified without
fetching anything.

**Why it replaced the LM5122-Q1.** The RGB load fell from 40 W to ~8 W (spec §2.2), which made a
controller-plus-external-FETs topology the wrong shape. Every criterion improved:

| | LM5122-Q1 | **LM51571-Q1** |
|---|---|---|
| Switch | 2 external FETs + gate loops | **Integrated 50 V / 4.33 A** |
| Input rating | needed checking against the ~39 V TVS clamp | **2.9–45 V op, 50 V abs, transient protection to 50 V** |
| Shutdown IQ | 9 µA typ / **17 µA max** | **≤ 2.6 µA** |
| Spread spectrum | **none** — row 3.4 had to be *relaxed* to accept an external SYNC | **Dual random, built in** |
| Qualification | -Q1 | **AEC-Q100 grade 1**, −40 to +125 °C |
| Package | controller + 2 FETs + inductor | **WQFN-16, 3 × 3 mm** + 1 Schottky |

It is **non-synchronous**, so it needs one external Schottky rectifier — at 320 mA out that costs
~64 mW, against two FETs and their gate drive.

**Switch margin:** 4.33 A against a ~0.8 A peak inductor current — **5.4×**.. Verified against **TI LM5122-Q1 datasheet SNVSAW9,
June 2017** (fetched 2026-09-12; extracted with PyMuPDF — same "the harness's
text conversion garbles it, the PDF itself is fine" situation as section 2).

| # | Required | Actual | Verdict |
|---|---|---|---|
| 3.1 | Input rating 40-60 V (must exceed the 24 V TVS clamp voltage) | **PASS** — datasheet p.1: "2.9-V to 45-V input operating range", "48-V maximum output (50-V abs max)", "Input transient protection up to 50 V". Clears the SMBJ24A's ~39 V clamp with margin. **This criterion is what eliminated the obvious alternatives** (TPS55340 is 32 V max, TPS61170 18 V). | **PASS** |
| ~~3.1-old~~ | *(superseded row retained below)* | Section 6.3 "Recommended Operating Conditions", p.6: "Input supply voltage — VIN — Min 4.5 V, Max 65 V." Section 6.1 "Absolute Maximum Ratings", p.5: "VIN, CSP, CSN — Max 75 V." Feature list p.1: "Maximum Input Voltage: 65 V." | **PASS** — 65 V recommended max and 75 V absolute max both clear the 40-60 V band with margin; 4.5 V min is far below the requirement so no conflict there either. |
| 3.2 | Synchronous (external FETs). **Efficiency: 92% is the figure the thermal budget uses (spec 9.4); >= 94% is the datasheet target and is UNVERIFIED** | **Synchronous/external FETs confirmed:** feature list p.1: "Robust 3-A Integrated Gate Drivers," "Adaptive Dead-Time Control"; pin functions p.4: "HO — High-side N-channel MOSFET gate drive output," "LO — Low-side N-channel MOSFET gate drive output" (both external FETs, true synchronous rectification, peak-current-mode control). Section 8.2 "Typical Application" worked design example, p.35, uses almost exactly this design's voltage points: VOUT = 24 V, VIN(TYP) = 12 V, VIN range 9-20 V (though at 108 W, not 60 W). **Efficiency percentage: not found.** A full-text search of all 50 pages for the word "Efficiency" returned zero hits — the "Typical Characteristics" efficiency curves in this datasheet are image-only plots with no OCR-able axis/label text extracted by PyMuPDF, and no numeric efficiency percentage appears anywhere in the document's text layer. | **PASS** for "synchronous, external FETs" (directly confirmed from pin functions and features). **UNVERIFIED** for the >= 94% efficiency figure — needs a human to open the datasheet's Typical Characteristics section visually (or run the TI WEBENCH Power Designer tool linked in Section 8.2.2.1 with this design's exact 12 V-in/24 V-out/60 W point) to read the actual efficiency curve; not stated here as a number because none could be extracted. |
| 3.3 | Enable pin, 3.3 V logic compatible | The device has **no dedicated EN pin** (confirmed against the full pin list, Section 4 "Pin Functions" p.4: SYNCOUT, OPT, CSN, CSP, VIN, UVLO, SS, SYNCIN/RT, AGND, FB, COMP, SLOPE, RES, PGND, MODE, LO, VCC, SW, HO, BST, EP — no "EN"). The **UVLO pin** serves this role: p.4, "If the UVLO pin is below 0.4 V, the regulator is in shutdown mode with all functions disabled. If the UVLO pin voltage is greater than 0.4 V and below 1.2 V, the regulator is in standby mode... If the UVLO pin voltage is above 1.2 V, the start-up sequence begins." | **PASS, with an implementation note** — a 0 V / 3.3 V logic swing cleanly straddles both thresholds (0 V is below the 0.4 V shutdown threshold; 3.3 V is above the 1.2 V start-up threshold), so no level shifter is needed. However, UVLO's primary job is analog line-undervoltage sensing via an external resistor divider from VIN (worked example, Section 8.2.2.3, p.35: RUV2 = 49.9 kOhm, RUV1 = 8.06 kOhm for an 8.7 V start-up threshold) — to add MCU enable/disable on top of that divider, the standard technique is a small transistor across the lower divider resistor gated by the 3.3 V GPIO.  |
| 3.4 | Spread spectrum | **PASS, and the earlier RELAXATION IS WITHDRAWN.** Datasheet p.1, EMI mitigation: "Selectable dual random spread spectrum". The criterion had been relaxed to accept an external SYNC input or a documented EMC plan solely because the LM5122-Q1 lacked the feature; the LM51571-Q1 meets the original requirement properly rather than having it negotiated down. | **PASS** |
| 3.5 | Disabled-state current draw <= 10 uA | **PASS** — datasheet p.1: "Low shutdown current (IQ <= 2.6 uA)". No external gating needed, and the false P-FET-disconnect justification that the old row relied on is moot. *(Old row retained below.)* | Section 6.5 "Electrical Characteristics", p.6: "ISHUTDOWN — VIN shutdown current — VUVLO = 0 V — Typ 9 uA, Max 17 uA." Feature list p.1 also states "Low Shutdown Quiescent Current: 9 uA" (the typical figure). | **PASS on typical (9 uA), FAILS on guaranteed max (17 uA)** against the bare 10 uA threshold. **CORRECTED 2026-09-12 (project review C3).** The previous text claimed the "or gated externally" clause was met because "Section 6.1's P-FET series disconnect switch sits upstream ... and can cut it off from the battery entirely during deep sleep". **That was false.** The spec 4.2 P-FET is a **passive, self-biased reverse-polarity device** - gate resistor and Zener clamp, no enable input, no control net, no GPIO in any pin table. **Nothing disconnects the boost input from the battery in sleep.** The 17 uA max is a real, unavoidable contributor and is now **budgeted explicitly in the roll-up below**. |
| 3.6 | ~~Dissipation at 40 W out <= 3 W including both FETs~~ **VOID — THERE ARE NO EXTERNAL FETs.** The LM51571-Q1 integrates the switch, so the entire FET selection is deleted from the BOM. Remaining external power part: **one Schottky rectifier** — see row 3.7. | Not determinable from this datasheet alone — HO/LO drive **external** N-channel MOSFETs (row 3.2), so total FET dissipation (conduction loss I^2 x RDS(on) plus switching loss at the chosen fSW) depends entirely on which external FETs Task 3/4 selects and what switching frequency is programmed via RT (the worked example in Section 8.2.2.2, p.35, uses 250 kHz for a 108 W/24 V design, chosen as "a reasonable compromise between small size and high-efficiency"). | **UNVERIFIED at the controller level** — this is a system-level calculation that depends on FET selection, not a fixed parameter of the LM5122-Q1. Task 3/4 must pick specific boost-stage FETs, compute conduction + switching loss for both at the 60 W/24 V operating point, and check the sum against the 3 W ceiling. |

> **CRITICAL CORRECTION 2026-09-12 (project review C3): the datasheet's worked divider values must NOT be used as-is.** RUV2 + RUV1 = 49.9 k + 8.06 k = **57.96 kOhm across 12 V = ~207 uA drawn continuously**, rising to ~240 uA while the enable transistor shunts RUV1. **That divider alone exceeds the entire 200 uA sleep target**, before any other contributor. **Requirement: scale to >= 1 MOhm total** at the same ratio for the 8.7 V threshold (~14 uA at 12 V, one fifteenth the current). The ratio sets the threshold; the absolute values set the quiescent draw, and the datasheet's example optimises for neither.


### ~~Boost power stage — external-FET requirements~~ SUPERSEDED 2026-09-13

> **These requirements are VOID.** They were derived for the LM5122-Q1's external FETs; the
> LM51571-Q1 integrates the switch, so no external FETs exist. **The inductor arithmetic below still
> stands and is still the authority for the inductor choice** — peak current, duty cycle and RMS are
> properties of the topology, not of the controller. Retained for that, and as the record of why the
> FET search was abandoned.

#### Original block (external-FET era)

### Boost power stage — requirements derived from this design (2026-09-13)

Previously the FETs were unselected and the inductor's peak current was a **scaled estimate** taken
from the LM5122 datasheet's own 108 W worked example. Both are now computed from this design's
parameters (Vin 12 V, Vout 24 V, 60 W design point, 92% assumed efficiency):

| Quantity | Design point (60 W) | Actual load (40 W) |
|---|---|---|
| Duty cycle `D = 1 - Vin/Vout` | 0.50 | 0.50 |
| Output current | 2.50 A | 1.67 A |
| Input / inductor average current | 5.43 A | 3.62 A |
| **Inductor peak** (30% ripple) | **6.25 A** | 4.17 A |
| RMS current per FET (`Iin x sqrt(D)`) | 3.84 A | 2.56 A |

**This supersedes the 7.5 A scaled estimate.** The real peak is **6.25 A**, so the candidate
Coilcraft XAL7070-682ME (Isat 12.8 A, row 6.5) has **2.0x margin**, not the 1.7x previously claimed
against the borrowed figure. Row 6.5's UNVERIFIED note about the scaled estimate is closed by this.

**Conduction loss versus Rds(on)**, at the 3.84 A RMS design point:

| Rds(on) | Per FET | Both FETs |
|---|---|---|
| 10 mOhm | 0.15 W | 0.30 W |
| **20 mOhm** | **0.30 W** | **0.59 W** |
| 30 mOhm | 0.44 W | 0.89 W |
| 40 mOhm | 0.59 W | 1.18 W |

**Requirements for both positions (high-side rectifier and low-side switch):**

| | Value | Why |
|---|---|---|
| Vds | **>= 40 V** | 24 V rail plus switch-node ringing; matches the front end's >=40 V rule |
| Id continuous | **>= 10 A** | Against a 6.25 A peak — margin for ringing and transient |
| Rds(on) | **<= 20 mOhm at Vgs = 7.5 V** | The LM5122's VCC-derived gate drive is ~7.5 V, **not** 4.5 V or 10 V. A part specified only at 10 V is not verified for this drive |
| Qg | **<= 20 nC** | Bounds switching loss and the gate-drive current the controller must supply |
| Package | **Thermal pad** (SO-8 / PowerPAK / DFN) | These sit in the thermal group gap-padded to the finned plate (spec 9.3) |
| Quantity | **2, and use the SAME part number for both** | Simplifies the BOM and halves the sourcing risk — this project has already been bitten twice by availability |

**Budget check:** 0.59 W conduction for the pair, plus roughly 0.5-1 W switching, plus ~0.3 W
inductor DCR, comes to about **1.4-1.9 W** — inside row 3.6's <= 3 W.

**Note the tension with the thermal budget, deliberately left conservative.** Spec 9.4 budgets
**3.5 W** for the boost (40 W out at 92%). This component-level buildup suggests the real figure at
40 W is nearer **1.5-2 W**, i.e. 95-96% efficiency, which is what a well-designed synchronous boost
should achieve. The thermal design is **not** being relaxed on the strength of an estimate — bring-up
Stage 2 measures it, and until then the pessimistic figure governs the plate sizing. If the
measurement confirms 94%+, the enclosure gains real margin.

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


### The enable arrangement — and why the UVLO divider is gone

The LM51571-Q1 has a **single combined `EN_UVLO_SYNC` pin** (pin 6): enable, programmable line
undervoltage lockout and sync all share it. The LM5122-Q1 had a separate UVLO pin, and the previous
design put a resistor divider on it — which was the second of the two ≥ 1 MΩ networks the whole sleep
budget was made conditional on.

**Decision: drive `EN_UVLO_SYNC` directly from `EN_BOOST` (GPIO 25), with no divider.**

- 3.3 V logic comfortably clears the enable threshold; 0 V shuts the part down
- The mandatory **pulldown on `EN_BOOST` still gives "floating = boost off"**, satisfying the
  passive-default rule
- **It removes ~14 µA of continuous divider current from the sleep budget** — the divider drew that
  whether the part was enabled or not, because it sat across the battery rail
- **It removes one of the two ≥ 1 MΩ conditions** the budget's PASS depended on. Only the P-FET gate
  network remains conditional

**What is given up:** programmable line UVLO. The part keeps its own internal undervoltage lockout,
so it simply will not run below its minimum; what is lost is the ability to choose a custom
threshold. Acceptable here — the Experia's 12 V rail is DC-DC fed and well behaved, there is no
crank-dip to ride out on an EV, and the board sleeps when the bus goes idle anyway.

### 3.7 Boost rectifier (NEW — required by the non-synchronous topology)

| # | Required | Actual | Verdict |
|---|---|---|---|
| 3.7.1 | Schottky, Vr >= 40 V (24 V rail plus ringing, consistent with the front end) | | |
| 3.7.2 | If >= 1 A average (against ~320 mA actual, ~0.8 A peak) | | |
| 3.7.3 | Low Vf at 320 mA — target <= 0.5 V, giving <= ~80 mW | | |
| 3.7.4 | Fast recovery suitable for switching up to 2.2 MHz | | |
| 3.7.5 | In stock, multi-source | | |

## 4b. 5 V regulator — mandatory, **enable-gated off in sleep**
Feeds the TJA1042's VCC (4.5-5.5 V). **Gated off in deep sleep** (spec 6): the
transceiver's low-power receiver runs on VIO alone and detects bus activity with
VIO as its only supply, so VCC is not needed for wake. Its quiescent draw does
NOT count against the sleep budget. No candidate was pre-chosen by the brief; proposed here:
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
| 4b.1 | Quiescent current <= 30 uA. **Does NOT count in sleep** - the rail is gated off (spec 6) - but matters if gating is ever dropped | Datasheet Section 5.5 "Electrical Characteristics": "IQ-SLEEP1 VIN sleep current — VEN = 2.5 V, VFB = 1.5 V — 10.5 / 25 uA" (typ/max). Feature list: "10.5uA no-load input quiescent current". Section 6.3.1/6.4.3 "Sleep Mode": at light load the converter enters diode-emulation, then "an ultra-low IQ sleep mode... The input quiescent current (IQ) required by the LM5164 decreases to 10.5uA in sleep mode." | **PASS** — 10.5 uA typ / 25 uA max, both under the 30 uA criterion, and the datasheet explicitly engineers this behavior for light/no-load standby (the exact condition here). |
| 4b.2 | Output 5.0 V +/- 5%, >= 100 mA (transceiver active draw) | Section 5.3 "Recommended Operating Conditions": "ILOAD Load current — 1 / 1.25 A" (nom/max) — far above the 100 mA needed. Output voltage is set externally: Section 6.3.3, "RFB2 = 1.2V / (VOUT - 1.2V) x RFB1", using the internal "VREF FB regulation voltage — 1.181 / 1.2 / 1.218 V" (min/typ/max, Section 5.5) reference. No dedicated fixed-5V SKU exists for this part — output accuracy at 5.0V depends on the external divider's resistor tolerance plus the +/-1.5% VREF spread. | **PASS** — 1 A/1.25 A output vs 100 mA required; +/-5% output accuracy is achievable with the +/-1.5% VREF tolerance plus standard 1% feedback resistors (well inside budget), though this is a design/BOM detail for the schematic stage, not this part's spec. |
| 4b.3 | Input rating 40-60 V (survives the 24 V TVS clamp) | Section 5.3 "Recommended Operating Conditions": "VIN Input voltage — 6 / 100 V" (min/max). | **PASS** — 6-100 V comfortably covers the 40-60 V requirement with large margin on both ends. |
| 4b.4 | **Clean start-up when EN_3V3SW asserts** - the rail is gated, not always on | Section 6.1 "Overview" / 6.4.3 "Sleep Mode": diode-emulation mode (DEM) plus an ultra-low-IQ sleep state are built in specifically to prevent instability and battery drain at light/no load. Section 7.2.3 "Application Curves", Fig. 7-6 "No-Load Start-up with VIN" is an actual bench scope capture at IOUT = 0 A showing clean, monotonic start-up (no oscillation). | **PASS** — the device is explicitly tested and characterized at 0 A load (a more demanding condition than the ~20 uA transceiver standby draw), with no instability shown. |
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
| 6.1 | P-FET (**single feed: one device now carries the WHOLE load — 7.8 A night / 3.9 A day → 1.22 W / 0.30 W at the 20 mOhm ceiling**): Vds >= 40 V, **Rds(on) <= 20 mOhm** (relaxed, fix round 1 Finding 3), Vgs rated **with the Zener gate clamp in circuit** (spec 4.2) — the gate never sees the full rail | Candidate: **Vishay Siliconix SQJ415EP** (Automotive P-Channel 40 V, PowerPAK SO-8L), datasheet S22-0224-Rev. B, 07-Mar-2022, already fetched and read in full in the prior pass. "ABSOLUTE MAXIMUM RATINGS": VDS = -40 V; VGS = +/-20 V. "SPECIFICATIONS" table: RDS(on) at VGS = -10 V, ID = -10 A — Typ. 11.5 mOhm, Max. 14.0 mOhm (the realistic operating point for a gate-resistor-to-ground + Zener-clamp self-bias network per spec 4.2, which drives the gate close to full rail swing, clamped, not to a weak partial-drive voltage); at VGS = -4.5 V — Typ. 16.3 mOhm, Max. 20.0 mOhm (a weaker-drive fallback, still within the relaxed ceiling at typ, right at it at max). Thermal: "TO-220 Full-Pak"-style PowerPAK SO-8L, Ptot(max) = 45 W (Tc = 25 degC), RthJA = 70 degC/W (PCB mount), RthJC = 3.3 degC/W (from Absolute Maximum Ratings / Thermal Resistance tables already extracted). **SINGLE FEED (decided 2026-09-12): one device now carries the whole load — 7.8 A at night, 3.9 A in daytime. At 7.8 A: 7.8^2 x 0.0140 = 0.85 W max at the realistic -10 V drive, or 7.8^2 x 0.0200 = 1.22 W at the 20 mOhm ceiling. Night total dissipation is only ~2.9 W against daytime ~4.5 W, so this does not govern the thermal design (spec 9.4).** Figures below are from the superseded dual-feed arrangement, retained because they are the datasheet arithmetic: **dissipation at both feeds, using the realistic VGS = -10 V column:** Feed A (3.9 A): P = I^2 x R = 3.9^2 x 0.0115 = **0.175 W typ** / 3.9^2 x 0.0140 = **0.213 W max**. Feed B (6.6 A): P = 6.6^2 x 0.0115 = **0.501 W typ** / 6.6^2 x 0.0140 = **0.610 W max**. Temperature rise at Feed B's worst case, using RthJA = 70 degC/W: 0.610 W x 70 degC/W ~= **43 degC rise above ambient** — well inside the 175 degC Tj max even at a hot ambient. | **PASS** on both sub-criteria under the revised criteria: (a) RDS(on) 11.5/14.0 mOhm (realistic drive) is under the relaxed 20 mOhm ceiling with margin (the weaker VGS = -4.5 V max of 20.0 mOhm sits exactly at the ceiling, not below it — the design should ensure the gate drive reaches close to -10 V, not just -4.5 V, to keep real margin); (b) with the Zener clamp from spec 4.2 in circuit, the gate never sees the full 24 V+ rail excursion, so the native +/-20 V VGS rating is adequate — no added component beyond what the design already includes. **Dissipation under the SINGLE feed (corrected 2026-09-12):** 0.30 W in daytime (3.9 A) and **1.22 W at night (7.8 A) at the 20 mOhm ceiling**, or 0.85 W at the realistic -10 V drive. At 1.22 W into the cited RthJA of 70 degC/W the rise is **~85 degC, not the ~43 degC stated for the superseded dual-feed case** - so the margin is real but half what was previously claimed. This is acceptable because the device is gap-padded to the finned plate rather than relying on RthJA (spec 9.3/9.4), and night's total board dissipation is only ~2.9 W against daytime's ~4.5 W. **Task 3/4 must confirm the gate drive reaches close to -10 V** to keep the better figure. |
| 6.2 | TVS: standoff ~24 V, clamping voltage < 40 V, rated for the feed current (clamps a single 12 V feed carrying 7.8 A at night, upstream of switchers rated 40-60 V input, must not conduct during a 24 V double-battery jump) | **RE-OPENED 2026-09-12 — both files this repo's `hardware/datasheets/` folder holds under a "TVS" name were actually read this pass, and neither is a real SMBJ24A electrical datasheet, despite the filenames:** (1) `SMBJ24A_TVS.pdf` (261.8 KB) is a **Diodes Incorporated Product Change Notice, PCN-2524 Rev 1, dated 4 Oct 2021** — a wafer-fab-diameter change announcement. It lists "SMBJ24A-13-F" in its Table 2 of affected part numbers (confirming that part number is a real, currently-manufactured Diodes Inc. product, still active as of the PCN's Jan-2022 implementation date), but the document contains **zero electrical characteristics** — no VWM, VC, IPP, or PPP anywhere in its 4 pages; it explicitly states "No change in datasheet parameters" and links out to `diodes.com/catalog/` for the actual datasheet, which is not this file. (2) `SMBJ_series_TVS.pdf` (112.8 KB) is a **Powerex POW-R-BLOK CD42__40B/CD47__40B datasheet** — a dual SCR/diode phase-control module rated 40 A / up to 1800 V, an entirely unrelated part family (not a TVS diode, not from a TVS manufacturer, not even the right voltage/current class). Both files were opened and read page-by-page (not just filename-matched) to reach this conclusion. **Fresh attempts this pass to reach a genuine primary datasheet, all unsuccessful:** Mouser-hosted SMBJ-series PDF (`mouser.com/datasheet/2/447/SMBJ_1-1955012.pdf`) — timeout; Bourns direct (`bourns.com/docs/product-datasheets/smbj.pdf`) — HTTP 403; ST direct (`st.com/resource/en/datasheet/cd00001366.pdf`) — timeout; Littelfuse's own asset link surfaced via Digi-Key's product page (`littelfuse.com/assetdocs/...`) — HTTP 403. This adds 4 new failures to the 5 already recorded from prior sessions, all against the same class of block/timeout. One IC-Components.com distributor parametric page *was* successfully opened (not a manufacturer datasheet, but a live pull, not a search-summary): "SMBJ24A-13-F / Diodes Incorporated / TVS DIODE 24V 38.9V SMB," and DigiKey's own product page for the Littelfuse SMBJ24A (live fetch) reports the same figures. Both corroborate, but neither is the primary source the rule requires: Voltage-Reverse-Standoff (Typ) 24 V, Voltage-Breakdown (Min) 26.7 V, Voltage-Clamping (Max) @ Ipp 38.9 V, Current-Peak-Pulse (10/1000us) 15.4-15.5 A, Power-Peak-Pulse 600 W. | **PASS — CLOSED 2026-09-18 from a primary source. See "Correction 2 — row 6.2 is closed" at the end of this file.** The narrative that follows is retained as the record of nine failed fetches, and is now historical.<!-- These numbers are now corroborated by more independent distributor-side reads than before (Littelfuse via a live Digi-Key page, ON Semi-branded stock via IC-Components, plus the pre-existing Bourns/Vishay/ST/Diodes-Inc corroboration), and they cleanly satisfy the stated criteria on their face (24 V standoff matches "~24 V"; 38.9 V clamp is comfortably under 40 V and under the 40-60 V input rating of the downstream switchers in row 3.1/4.3/4b.3; 15.4-15.5 A pulse rating covers the 7.8 A night feed with large margin; a device with VBR(min) 26.7 V will not conduct at a 24 V nominal double-battery jump, which sits below its breakdown floor). But **every attempt at a genuine manufacturer PDF — 9 across two sessions now — has failed (403 or timeout), and the two files placed in this repo under a "TVS" name are not TVS datasheets at all.** A human must obtain a real Littelfuse/Bourns/Vishay/ST/Diodes-Inc SMBJ-series PDF by a channel an automated fetch cannot use (a logged-in browser download, distributor account, or emailed copy) and confirm VWM/VC/PPP directly before this row can be marked PASS. If that confirms the figures above, the row passes cleanly on the arithmetic already shown; the gap is evidentiary, not numerical. -->|
| 6.3 | PTC: hold >= the per-string load at 65 degC, Vmax >= 24 V, trip below the boost limit, 4 required | Littelfuse **1206L050/24**, datasheet Rev. 03/22/17, p.1 electrical characteristics: Ihold 0.50 A, Itrip 1.00 A, Vmax 24 Vdc. p.2 derating table: 0.33 A at 60 degC, 0.29 A at 70 degC, so **0.31 A at 65 degC** by interpolation within the datasheet's own table. | **PASS (REVERSED 2026-09-13).** This row was a hard, family-wide FAIL while the per-string load was believed to be 0.42 A. The real load is **0.08 A** (16 W/m x 12 cm), so 0.31 A at 65 degC gives a **3.9x margin**. The part that could not be found in any 24 V-rated 1206L variant is no longer needed - the original candidate passes comfortably. |
| 6.4 | Schottky OR pair: 40 V, >= 0.5 A, low leakage. **NOTE 2026-09-12: single feed adopted, so only ONE diode is populated (or a 0 Ohm link VBAT -> VLOGIC_IN); the pair remains as footprints for the DNP second feed.** | Candidate: **Nexperia PMEG4010ER** (40 V, 1 A low-VF Schottky, SOD123W), Product data sheet, 1 January 2023, fetched and read in full. Table 1 "Quick reference data": "VR reverse voltage — Tj = 25 degC — Max 40 V"; "IF(AV) average forward current — Max 1 A"; "IR reverse current — VR = 40 V, Tj = 25 degC — Typ 10 uA, Max 50 uA"; "VF forward voltage — IF = 1 A, Tj = 25 degC — Typ 430 mV, Max 490 mV." | **PASS** — 40 V rating meets the requirement exactly (matches the design's 40 V front-end tolerance target); 1 A rating exceeds the 0.5 A floor 2x; 50 uA max reverse leakage at full 40 V reverse bias is low for a 1 A Schottky, consistent with "low leakage." Two of these in an OR configuration (Feed A / Feed B onto the logic rail) satisfy the pair requirement. |
| 6.5 | Boost inductor: shielded, saturation current >= 1.5x peak | Candidate: **Coilcraft XAL7070-682ME** (6.8 uH shielded composite-core power inductor), Document 856-2, Revised 02/25/26, fetched and read in full. Parametric table: "XAL7070-682ME — Inductance 6.8 uH — DCR typ 17.84 mOhm / max 19.62 mOhm — SRF typ 20 MHz — Isat 12.8 A — Irms(20 degC rise) 6.8 A / Irms(40 degC rise) 9.2 A." Family description: "Shielded Power Inductors — XAL7070," "magnetically shielded" composite core, AEC-Q200 qualified. Peak inductor current for this design was estimated by scaling the LM5122-Q1 datasheet's own worked 108 W design example (Section 8.2.2.4, p.36 of that datasheet, which computes a 13.5 A peak input/inductor current for a 12 V-in/24 V-out/108 W boost) linearly by power ratio: 13.5 A x (60 W / 108 W) ~= 7.5 A estimated peak for this design's 60 W point (same voltage points, same topology, proportional scaling — not a fabricated figure, but also not a from-scratch calculation for this exact design; Task 3/4 must re-run the LM5122 design equations with the real 60 W parameters to confirm). | **PASS on the datasheet-verified Isat figure against the scaled peak-current estimate** — Isat = 12.8 A vs an estimated ~7.5 A peak gives a ratio of ~1.7x, above the 1.5x requirement, and the part is explicitly marketed and constructed as magnetically shielded. **CLOSED 2026-09-13:** the peak current is now derived from this design's own equations (see the boost power-stage block above) and is **6.25 A**, not the 7.5 A scaled estimate — giving this part **2.0x** Isat margin rather than 1.7x. |



### Switched 3.3 V rail — DML3017LDC smart load switch (ADOPTED 2026-09-13)

Replaces the discrete P-FET + N-FET inverter + gate pull-up. Verified from
`hardware/datasheets/DML3017LDC.pdf`.

| # | Required | Actual | Verdict |
|---|---|---|---|
| LS.1 | **EN active-high**, so the mandatory `EN_3V3SW` pulldown means "floating = rail OFF" | Pin description: *"EN — **Active-high** digital input used to turn on the MOSFET, pin has an **internal pulldown resistor to GND**"* | **PASS**, and better than required — the internal pulldown holds the safe state even if the external resistor is omitted or lifts |
| LS.2 | Shutdown current negligible against the 85–100 µA sleep budget | `ISTBY` VCC Shutdown Supply Current, VVCC = 3 V, VEN = 0 V: **0.1 µA typ / 1 µA max** | **PASS** — 1% of the budget at worst |
| LS.3 | Controller supply covers 3.3 V | `VVCC` 3.0 V to 5.5 V | **PASS** |
| LS.4 | Switched path covers 3.3 V | `VVIN` 0.5 V to 20 V | **PASS** |
| LS.5 | Logic threshold compatible with a 3.3 V GPIO | `VENH` 2.0 V min | **PASS**, 1.3 V margin |
| LS.6 | Enabled-state current acceptable | `IDYN` 150 µA typ / 250 µA max | **PASS** — applies only while the rail is enabled, i.e. while the board is awake and drawing milliamps |

**Why this replaced the discrete arrangement — it removes a polarity trap, not just parts.**
A bare P-channel high-side switch inverts the logic: its source sits at `+3V3_ALW`, so a GPIO **low**
turns it **on**. With the mandatory pulldown on `EN_3V3SW`, floating would therefore have meant
**rail ON** — the exact opposite of the passive-default rule that the whole biasing table exists to
enforce. The discrete design needed an N-FET inverter stage purely to correct that. This part is
natively active-high, so the trap does not exist.

| | Discrete (3 parts) | **DML3017LDC (1 part)** |
|---|---|---|
| Polarity | needs an inverter, or floating = **ON** | **active-high natively** |
| Safe default | external pulldown only | **internal pulldown as well** |
| Sleep current | FET leakage, never budgeted | **≤ 1 µA** |
| Inrush | uncontrolled | **soft-start limited** |
| Protection | none | **short-circuit, thermal, VCC UVLO** |
| Diagnostics | none | **power-good output** |

**Wiring notes for the rails sheet** — corrected 2026-09-14 against the pin-description table
and the typical application circuit on p.2–3 of `DML3017LDC.pdf`. Two of the notes below were
wrong when first written from the feature list alone:

- **`VIN` is pins 1 AND 13, and the datasheet requires them tied together.** `VCC` (pin 3) is a
  separate controller supply. All three tie to `+3V3_ALW` here.
- **`EN` ← `EN_3V3SW`**, the same enable that gates the 5 V rail. The external pulldown lives on
  R19 next to the LM5164, so one resistor covers the whole net.
- **`BLEED` (pin 7) is mandatory, not optional, and the 100 Ω is EXTERNAL.**
  ~~"Use the BLEED pin (on-chip 100 Ω)"~~ — there is no internal bleed resistor. The pin
  description reads *"must be tied to VOUT either directly or through a resistor ≤ 1 kΩ"*, and the
  application circuit shows `RBLEED` at 10–100 Ω. Implemented as **R21, 100 Ω** from pin 7 to
  `+3V3_SW`. The discharge-at-sleep benefit is real; the part count was not.
- **`SR` (pin 5) needs `CSR`** — it sets the output slew rate (Table 1). Implemented as C32, 1 nF,
  the datasheet's typical value.
- **`PG` (pin 6) is tied to GND, not left floating.** ~~"needs an external pull-up if used"~~ is
  true as far as it goes, but the pin description also says *"tie to GND if not used"*, and unused
  is the case here — no GPIO is allocated to it. A pull-up was considered and **rejected on the
  sleep budget**: `PG` sits low whenever the switch is off, so a 100 kΩ pull-up to 3.3 V would burn
  **33 µA continuously**, a third of the entire 85–100 µA budget.
- The symbol carries **`PG` as `passive` rather than `open_collector`** so that ERC does not read
  the deliberate tie-off as an output driving into a power net.

## Final part selections — 2026-09-13

All verified from **primary datasheets held locally** in `hardware/datasheets/`. This is the first
round on this project where every figure came from a document on disk rather than a blocked fetch.

| Function | Part | Key verified figures | Datasheet |
|---|---|---|---|
| Boost converter | **TI LM51571-Q1** | Non-synchronous, integrated **50 V / 4.33 A** switch (5.4x the 1.22 A peak); 2.9–45 V in, **50 V abs**, transient to 50 V; **shutdown IQ ≤ 2.6 µA**; dual random spread spectrum; AEC-Q100 grade 1; WQFN-16 3×3 | `lm51571-q1.pdf` |
| Boost inductor | **Coilcraft XAL4030-682ME** | **6.8 µH**, **Isat 3.6 A**, Irms 3.0 A, DCR 74.1 mΩ max, SRF 29 MHz, shielded, **AEC-Q200**, 4.0×4.0×3.0 mm | `xal4000.pdf` |
| Boost rectifier | **Vishay SS5PH102** | **VRRM 100 V**, IF(AV) **5 A**, VF 0.70 V at 5 A, TJ 175 °C, SMPC (TO-277A) | `ss5ph102.pdf` |
| Buck, 3.3 V and 5 V rails | **TI LM5164** | **6–100 V** in, **1 A** out, **1.2 V reference**, IQ-SLEEP 10.5 µA typ / 25 µA max, up to 1 MHz | `lm5164.pdf` |
| Input TVS | **Littelfuse SMBJ24A** | Standoff **24 V**, VBR 26.7–29.5 V, **clamping 38.9 V at 15.5 A**, 600 W | `smbj.pdf` |
| Reverse-polarity P-FET | **Vishay SQJ461EP** | **−60 V**, ID −30 A, **Rds(on) 16 mΩ at VGS −10 V** (21 mΩ at −4.5 V), VGS ±20 V, AEC-Q101, 175 °C, PowerPAK SO-8L | `sqj461ep.pdf` |
| RGB switching FET (×6 dual = 12 ch) | **Nexperia NX5020UNBKS** | **50 V dual N-channel**, ID 300 mA, **Rds(on) specified AT VGS = 2.5 V: 1.6 Ω typ / 3 Ω max** (also 1.8 V and 1.5 V), very low threshold, SOT363 (SC-88) | `NX5020UNBKS.pdf` |
| CAN transceiver | **NXP TJA1042T/3** | **Rev. 11, 16 Jan 2023** — bus wake-up via RXD LOW re-confirmed on current silicon | `TJA1042.pdf` |
| Analog mux | **ADI ADG706** | **Rev. B** (supersedes the 2002 Rev. A previously used) | `ADG706_707.pdf` |
| PTC (×4) | **Littelfuse 1206L050/24** | Ihold 0.50 A at 23 °C, **0.31 A at 65 °C**, Itrip 1.00 A, Vmax 24 V — **3.9× margin** on the 0.08 A load | `Littelfuse_1206L_PTC_series.pdf` |
| Switched 3.3 V load switch | **Diodes DML3017LDC** | **EN active-high with internal pulldown**; `ISTBY` **0.1 µA typ / 1 µA max**; VCC 3.0–5.5 V; VIN 0.5–20 V; VENH 2.0 V min; soft-start, short-circuit, thermal, UVLO, power-good | `DML3017LDC.pdf` |
| Denali high-side | **Infineon BTS7008-2EPA** | One multiplexed IS output + DSEL; conditional PASS on thermals at 150 °C | (prior round) |

### Two selections that fixed specific defects

**SQJ461EP replaces SQJ415EP — the clamp-margin problem.** With the TVS clamp now *measured* at
**38.9 V**, the 415EP's 40 V rating left **1.1 V (2.8%)** of margin on the part that sees every
transient the vehicle produces. The 461EP's **60 V** gives **21.1 V (54%)**. Same PowerPAK SO-8L
footprint and the same SQJ family, so nothing in the layout changes. Dissipation barely moves:
7.0² × 0.016 = **0.78 W** at the night load, against 0.61 W.

**NX5020UNBKS — specified at the gate voltage actually used.** Every earlier candidate quoted
Rds(on) only at 4.5 V or 10 V, while the PCA9685 drives gates at **3.3 V** — the recurring trap on
this project. This part is characterised at **2.5 V, 1.8 V and 1.5 V**, so it is verified rather than
extrapolated. Its 1.6 Ω looks high for a MOSFET but is irrelevant here: at 26.7 mA it drops **43 mV**
and dissipates **1.1 mW**, and against the strip's ~889 Ω per channel it shifts the loop by 0.2%.
**The sense reading stays at 267 mV whether the FET sits at its typical or maximum Rds**, so
part-to-part spread cannot disturb the open/working/shorted classification. Being dual, 12 channels
need only **6 packages**.

### Feedback dividers, now computable (LM5164 reference = 1.2 V)

| Rail | R_top | R_bot | Total | Current | V_out |
|---|---|---|---|---|---|
| 3.3 V | **350 kΩ** | **200 kΩ** | 550 kΩ | 6.0 µA | 3.30 V |
| 5 V | **633 kΩ** | **200 kΩ** | 833 kΩ | 6.0 µA | 5.00 V |

Both clear the ≥ 500 kΩ sleep-budget requirement. Use E96 values (348 k / 200 k and 634 k / 200 k).

### Still to decide, and one caveat

- **DML3017LDC smart load switch** (`DML3017LDC.pdf`) — a single-part alternative to the discrete
  P-FET + N-FET inverter + pull-up on the switched 3.3 V rail, adding soft-start inrush limiting,
  fault protection and power-good. Input range 0.5–20 V covers the rail. **Confirm its EN polarity is
  active-high** (so the mandatory pulldown still means "floating = off") **and its quiescent current**
  before adopting — that rail's controller stays powered in sleep.
- **SQJ461EP stock** — the datasheet is Rev. E, **28-Nov-2011**. Normal for a mature part, but two
  parts on this project have already proved unbuyable after being written into the design.
- **SQJ461EP gate drive** — 16 mΩ is the **−10 V** column; the **−4.5 V** column is 21 mΩ, slightly
  above the ≤ 20 mΩ ceiling. The self-biased Zener-clamped network should pull the gate close to the
  full rail, but confirm that at schematic review rather than assuming it.

### Parts checked and rejected

| Part | Why not |
|---|---|
| XCL105 | 0.65–6.0 V in, 1.8–5.5 V out — wrong voltage class entirely for 12→24 V |
| 5.0SMDJ-FB | 5 kW low-clamping TVS, but the series starts at **58 V standoff** — far too high to protect a 24 V rail |
| NX3020NAKW-Q | 30 V **N**-channel; below the 38.9 V clamp, and the open slot needed P-channel |
| DMHT3006LFJ | 30 V N-channel **H-bridge** — motor-drive part, wrong topology and below the clamp |
| XP202A0003MR-G | −30 V P-channel — below the clamp, so unusable for reverse polarity. Viable for the 3.3 V load switch if the discrete arrangement is kept |
| XAL7070-682ME | Correct 6.8 µH but **Isat 12.8 A in 7×7×3 mm** — sized for the abandoned 60 W design |

## Rails sheet verification — 2026-09-14

The rails draft was checked against the primary datasheets rather than accepted as drafted.
Topology was sound; four defects were found and fixed. Values below are from
`lm5164.pdf` (SNVSAU4D, Feb 2026), `lm51571-q1.pdf` (SNVSBK8B, Aug 2023) and
`DML3017LDC.pdf` (DS46371 Rev. 1-2).

### Confirmed correct — things that looked wrong and were not

| Item | Doubt | Datasheet says | Verdict |
|---|---|---|---|
| `R15` 5.1 Ω in series with `C26` 1 µF on the LM51571 `VCC` | A series resistor in front of a bypass cap looks like a mistake — `VCC` needs a low-impedance bypass | Pin table: *"Connect a **5-Ω resistor in series with a 1-µF** ceramic bypass capacitor from this pin to PGND"* | **Exactly as specified** |
| `R11` = 37.4 kΩ on `MODE` | Arbitrary-looking value | 37.4 kΩ is the one value that enables **both** dual random spread spectrum (§9.3.5) **and** hiccup-mode overload protection (§9.3.11). 100 kΩ gives spread spectrum only; 62.0 kΩ gives hiccup only | **Deliberate and optimal** |
| `R10` = 9.09 kΩ on `RT` | — | fSW = **2200 kHz** typ. Clears the AM broadcast band (530–1710 kHz) entirely, fundamental and harmonics | **Correct for automotive EMI** |
| `R12`/`R13` = 115 k / 4.99 k | — | VREF = **1.000 V** ±1%. Vout = 1.0 × (1 + 115/4.99) = **24.05 V** | **Correct** |
| LM5164 `EN/UVLO` tied straight to `VLOGIC_IN` (~11.5 V) | A logic-level enable at 11.5 V would be a classic overstress | Abs max **EN to GND: −0.3 to 100 V**; recommended VEN/UVLO to 100 V | **Correct**, it is a precision high-voltage enable |
| `R16` = 0 Ω feeding `BIAS` from VBAT | BIAS is usually tied to the output | Pin table: *"Supply voltage input to the VCC regulator"*, operates to 45 V | **Correct**; the 0 Ω link keeps the option to re-source BIAS later |

### Defect 1 — the constant-on-time loop had no ripple to work with (FIXED)

**This was the one that would have cost a respin.** The LM5164 is a **constant-on-time** regulator:
after the on-time expires the high-side FET stays off until FB falls to the 1.2 V reference. §6.2:

> *"To maintain stability, the feedback comparator requires a minimal ripple voltage that is in
> phase with the inductor current during the off-time … **The minimum recommended ripple voltage
> is 20 mV.**"*

The draft used an all-ceramic output stage (2 × 22 µF, ESR ≈ 2 mΩ) with a 100 pF feedforward cap —
TI's **Type 2** scheme, which assumes an `RESR` in series with the output capacitor. Without it:

| | 3.3 V rail | 5 V rail |
|---|---|---|
| Inductor ripple ΔIL | 0.266 A | 0.28 A |
| Output ripple (ESR + capacitive) | ~3.2 mV | ~3.4 mV |
| **Ripple delivered to FB** | **~3.1 mV** | **~3.3 mV** |
| **Required** | **20 mV** | **20 mV** |
| Shortfall | **6.5×** | **6×** |

Too little ripple at FB in a COT converter does not fail cleanly — it shows up as jitter, audible
subharmonic behaviour, or erratic pulse bunching that a bench test at one operating point can miss.

**Fix: the datasheet's Type-3 ripple injection network (§7.2.2.6)**, chosen over adding series ESR
because this board runs an ADC sense chain off these rails and Type 3 generates the ramp *without*
raising output ripple. `RA` from SW, `CA` to VOUT, `CB` couples the ramp into FB:

```
CA    >= 10 / (fSW x (RFB1 || RFB2))
RA.CA >= tON(nom) x (VIN(nom) - VOUT) / 20 mV
CB    =  t(settling) / (3 x RFB1)
```

| Rail | RFB1‖RFB2 | fSW | CA min | **CA** | tON | **RA** | **CB** |
|---|---|---|---|---|---|---|---|
| 3.3 V | 127 kΩ | 402 kHz | 196 pF | **2.2 nF** (C28) | 714 ns | **133 kΩ** (R17) | **68 pF** (C9) |
| 5 V | 152 kΩ | 396 kHz | 166 pF | **2.2 nF** (C29) | 1010 ns | **174 kΩ** (R18) | **39 pF** (C15) |

Checked against the datasheet's second criterion — **≥ 12 mV at minimum VIN**: the 3.3 V rail holds
12.6 mV down to VIN = 6 V (the LM5164's own floor), the 5 V rail holds 12.4 mV at VIN = 8 V and is
in dropout below that anyway. Both pass. C9 and C15 were re-used as `CB`, so the part count is
unchanged at the 3.3 V rail and +1 R +1 C per rail overall.

### Defect 2 — both enables were missing their mandatory pulldowns (FIXED)

`EN_3V3SW` and `EN_BOOST` reached their pins with **nothing else on the net**. The plan's
passive-default biasing table makes a pulldown mandatory on both, and the LM51571 datasheet
independently states the UVLO/EN pin *"must not be left floating"*. Added **R19** and **R20**,
100 kΩ to GND. This is the same class of defect as the `EN_DIAG` omission caught in round 3 —
invisible on a schematic, a board rework if it ships.

### Defect 3 — the switched 3.3 V rail did not exist (FIXED)

The load-switch block was dropped when the sheet was restructured around the boost. Added as
**block 4**: `+3V3_ALW` → **U4 DML3017LDC** → `+3V3_SW`, with C30/C31 (1 µF each on VIN and VCC),
C32 (1 nF on SR), R21 (100 Ω, BLEED to VOUT) and C33/C34 on the output. `PG` tied to GND.

### Defect 4 — symbol pin types were generating false ERC violations (FIXED)

The LM51571 symbol typed **`SW` (pins 12–14) as `power_in`**, so ERC demanded an external driver
for the converter's own switch node. Retyped per Table 7-1: `VCC` → `power_out` (it is the internal
LDO's output), `SW`/`RT`/`COMP`/`SS`/`MODE`/`EP` → `passive`, `PGOOD` → `open_collector`,
`NC` → `no_connect`. `BIAS` is typed `passive` rather than `power_in` because R16 sits between it
and VBAT, leaving it on an isolated net as far as ERC can see.

### ERC status

**26 violations → 6.** All six remaining are `pin_not_connected` on root sheet pins
(`EN_3V3SW`, `EN_BOOST`, `+3V3_ALW`, `+3V3_SW`, `+5V`, `+24V`) whose counterparts live on the
`mcu_can` and `outputs` sheets, which are not drawn yet. They clear in Tasks 5 and 6.

`PWR_FLAG` symbols were added on `VBAT`, `VLOGIC_IN`, `GND` and each generated rail: every supply
on this board originates at a connector whose pins are passive, so without them ERC cannot see
what drives the power inputs.

### Netlist verification (independent, not taken from the drafting agent)

Confirmed from `hardware/output/netlist.net`:

- `VBAT` and `VLOGIC_IN` now span **both** sheets — the parent sheet pins were missing, so the
  two halves of each rail were separate nets until the root was wired.
- `EN_3V3SW` = `R19.1 U2.3 U4.2` — one enable gates both the 5 V rail and the switched 3.3 V rail,
  as the net contract requires.
- Type-3 injection nodes are correct on both rails: `RA`–`CA`–`CB` meeting at one node, with
  `RA` on SW, `CA` on VOUT and `CB` on FB.
- `+3V3_SW` = `C33.1 C34.1 R21.1` + all five `VOUT` pins.

### Still open

- **No footprints are assigned anywhere in this project yet** — every `Footprint` field on both
  sheets is empty. That is Task 8's job, but note one trap for it: the DML3017LDC's
  **V-DFN3030-12 pin-1 orientation is ambiguous between the two figures** in DS46371. The package
  outline puts the pin-1 ID at top-left; the suggested pad layout labels pad 1 at bottom-left.
  Resolve from the package-outline drawing before committing the footprint, do not infer it.
- The bucks run at **~400 kHz**, below the AM band, but their 2nd and 3rd harmonics (800 kHz,
  1.2 MHz) land inside it. The LM5164 tops out at 1 MHz so 2.2 MHz is not available; ~400 kHz with
  the fundamental below the band is the best this part can do. Flagged for the EMI pre-scan.

## mcu_can sheet — Task 5, 2026-09-14

ESP32-WROOM-32E-N8, TJA1042T/3 with hardware-enforced listen-only, programming header with
auto-reset, status LED, ignition-sense divider. Generated by `hardware/scripts/gen_mcu_can.py`.

### Pin assignment verified against the contract, pin by pin

Checked from the exported netlist, not from the drawing. Every net lands on the GPIO the plan's
Global Constraints table specifies:

| Net | Contract | Symbol pin | Net name in netlist |
|---|---|---|---|
| `CAN_RXD` | 35 | U5.7 `IO35` | ✓ |
| `IGN_SENSE` | 36 | U5.4 `SENSOR_VP` | ✓ — GPIO 36 is named SENSOR_VP on the module |
| `CAN_TXD` | 17 | U5.28 `IO17` | ✓ |
| `CAN_STB` | 14 | U5.13 `IO14` | ✓ |
| `I2C_SDA` / `I2C_SCL` | 21 / 22 | U5.33 / U5.36 | ✓ |
| `PWM_DEN_A` / `PWM_DEN_B` | 18 / 19 | U5.30 / U5.31 | ✓ |
| `RGB_ISNS` | 32 | U5.8 `IO32` | ✓ ADC1_CH4 |
| `MUX_S0`–`S3` | 23 / 4 / 16 / 5 | U5.37 / U5.26 / U5.27 / U5.29 | ✓ |
| `ISNS_DEN` | 34 | U5.6 `IO34` | ✓ ADC1 only |
| `DEN_DSEL` | 33 | U5.9 `IO33` | ✓ |
| `EN_BOOST` / `EN_3V3SW` / `EN_DIAG` | 25 / 26 / 27 | U5.10 / U5.11 / U5.12 | ✓ |
| `LED_STAT` | 13 | U5.16 `IO13` | ✓ |
| `BOOT_N` / `UART_TX` / `UART_RX` | 0 / 1 / 3 | U5.25 / U5.35 / U5.34 | ✓ |

**GPIO 39 (`SENSOR_VN`), GPIO 2 and GPIO 15 are left as no-connects** — the contract's spares.
The module's own NC pins (17–22, 32) are typed `no_connect` in the symbol, so they need no flags.

### Listen-only is structural, not a setting

The netlist proves the intent rather than merely describing it:

```
/mcu_can/CAN_TXD   R23.1  U5.28[IO17]          <- GPIO 17 goes only to the DNP link
Net-(U6-TXD)       R23.2  R24.2  U6.1[TXD]     <- transceiver TXD sees only R23 and the pull-up
```

R23 is the **only** conductive path from GPIO 17 to the transceiver, and it is DNP. R24 (10 kΩ to
VIO) holds TXD recessive. A board built to the BOM is physically incapable of asserting a dominant
bit on the vehicle bus, whatever the firmware does. R24 costs nothing in sleep: TXD rests high, so
no current flows through it.

### The two-supply split is what makes CAN wake work

| Pin | Rail | Why |
|---|---|---|
| `VIO` (5) | `+3V3_ALW` — always on | Keeps the receiver and the RXD output alive in sleep, so bus traffic still pulls RXD low. That is the EXT0 wake event on GPIO 35 |
| `VCC` (3) | `+5V` — gated off in sleep | Powers the transmit side and the bus drivers, which are dead weight while parked |

Tying both to one rail loses either the wake path or the sleep budget. Confirmed in the netlist:
`U6.5` on `+3V3_ALW`, `U6.3` on `+5V`.

`R25` (10 kΩ, STB to VIO) means floating = standby = receive-only, and it too is free in sleep:
STB rests high, so no current flows. It costs 330 µA only while the ESP32 actively drives STB low,
which is only while awake.

### Auto-reset — verified cross-coupled, not merely present

```
/mcu_can/DTR   J2.5  Q2.2[E]  R29.1        Net-(Q2-B)  Q2.1[B]  R28.2   Q2.3[C] -> EN_MCU
/mcu_can/RTS   J2.6  Q3.2[E]  R28.1        Net-(Q3-B)  Q3.1[B]  R29.2   Q3.3[C] -> BOOT_N
```

Each transistor's **emitter sits on the other control line**, so the pair only acts when DTR and
RTS differ. Both high or both low is run mode — which is what stops a plain serial monitor, which
asserts one line when it opens, from dropping the board into the bootloader. esptool drives
DTR=0/RTS=1 to assert reset, then DTR=1/RTS=0 to hold IO0 low while EN releases.

### Additions beyond the plan — flagged, not smuggled in

Three things here are not in the plan's Task 5. Each is cheap and defensible, but say so if you
would rather the plan be followed exactly:

1. **R36, 10 kΩ pulldown on GPIO 12.** GPIO 12 (MTDI) selects the flash voltage at boot: sampled
   high it selects 1.8 V, which will not run the module's 3.3 V flash. Most WROOM-32E parts ship
   with the eFuse burned so the strap is ignored, but that is not guaranteed across date codes.
   The plan says only "leave GPIO 12 unused", and an unused strapping pin is exactly the floating
   input the project's own biasing rule exists to forbid.
2. **`IGN_IN` is a new net name.** The plan says the divider is fed from "a VBAT-side input" but
   names no net. `IGN_IN` is the ignition-switched 12 V sense wire; it needs a connector pin on the
   outputs sheet. Rename or drop it if the contract should stay closed.
3. **`MUX_S0`–`S3`, `DEN_DSEL` and `EN_DIAG` pulldowns are on THIS sheet, not on `outputs`.**
   Their consumers live on `outputs`, but `MUX_S3` is GPIO 5 — a **strapping pin sampled at reset**
   — so its pulldown is a boot requirement and has to be near the module to be effective regardless
   of what happens downstream. The rest follow for consistency, gathered in one visible block
   rather than scattered through the fan-out.

### Deviation from the plan, deliberate

Task 5 Step 4 asks for the `EN_BOOST` and `EN_3V3SW` pulldowns here. **They are already fitted as
R19 and R20 on the rails sheet**, next to the converters they gate — which is where they do the
most good, since the enable then stays defined even if the inter-sheet net is open. One resistor
per net; a second in parallel would only halve the value.

### Component values

| Ref | Value | Basis |
|---|---|---|
| C35 / C36 | 10 µF / 100 nF | Module bulk + HF decoupling at VDD |
| R22 / C37 | 10 kΩ / 1 µF | EN power-on reset delay, ~10 ms. **UNVERIFIED** — no Espressif hardware-design guide held locally; confirm before ordering |
| R23 | 0 Ω **DNP** | Listen-only link |
| R24 / R25 | 10 kΩ | TXD and STB pull-ups to VIO |
| R26 | 120 Ω **DNP** | The vehicle bus is already terminated at both ends |
| R27 / D5 | 1 kΩ / green | ~1.2 mA at 3.3 V with a ~2.1 V Vf |
| R28 / R29 | 10 kΩ | Auto-reset base resistors |
| R30–R36 | 10 kΩ | Passive defaults; zero current in sleep |
| R37 / R38 | 90.9 kΩ / 33 kΩ **both DNP** | Ignition divider |
| R39 | 100 kΩ **POPULATED** | The mandatory pulldown on GPIO 36 |
| L6 | 51 µH CM choke | **PART NOT SELECTED** — placeholder value |
| D6 / D7 | 24 V bidirectional TVS | **PART NOT SELECTED** — placeholder |

If the ignition divider is ever populated: 90.9 kΩ over (33 kΩ ∥ 100 kΩ = 24.8 kΩ) gives **2.57 V
at 12.0 V in** and **2.96 V at 13.8 V**, both above the 2.48 V input-high threshold, with D8
clamping anything above the rail. Draw is 104 µA but only while the ignition line is live, so it
does not touch the parked budget.

### ERC status

**25 violations, every one of them the `outputs` sheet not existing yet**: 10 dangling root labels
(`MUX_S0`–`S3`, `DEN_DSEL`, `EN_DIAG`, `CANH`, `CANL`, `+3V3_SW`, `+24V`), 14 single-pin labels
(`RGB_ISNS`, `ISNS_DEN`, `IGN_IN`, `I2C_SDA`, `I2C_SCL`, `PWM_DEN_A`, `PWM_DEN_B` at both ends),
and `ISNS_DEN` reported as an undriven input because the PROFET sense output is on `outputs`.
All clear in Task 6.

Two mechanical classes were found and fixed during this task, both silent killers worth knowing:

- **161 `endpoint_off_grid` errors.** Coordinates must be exact multiples of **1.27 mm**. A pin
  that misses its wire by 0.6 mm looks connected on screen and is not. The generators now assert
  on every coordinate, so this cannot come back.
- **14 `unconnected_wire_endpoint` warnings** from putting local labels in the *middle* of a stub
  instead of at its end. The net still forms, so the netlist looks right, but the wire end dangles.

### J1 to 3-way, and C40 — added 2026-09-14/15

`J1` is now `Conn_01x03_Pin`, cavity 1 carrying `IGN_IN` (spec §8.1a topology B). The third cavity
went **above** the existing two, not below: `GND_IN` drops vertically from pin 2 at x = 31.75 all
the way to y = 101.6, so a pin placed below would have landed on that wire and shorted `IGN_IN` to
ground. Placing it above left **every existing wire, junction and net on this verified sheet
untouched** — the netlist confirms `FEED_P` and `GND_IN` keep exactly their previous membership,
and `GND_IN` is still separate from `GND` so the common-mode choke split is intact.

The pins renumber as a consequence: **1 = `IGN_IN`, 2 = +12 V, 3 = GND**. Cavity 1 is an end
cavity, so it is the easy one to plug on the Experia build.

**C40, 100 nF on `IGN_SENSE` — an addition, flag it if unwanted.** `IGN_IN` is an unshielded 12 V
wire entering a sealed enclosure onto a high-impedance node. C40 forms an RC with R37:
R_thev = 90.9 kΩ ∥ 24.8 kΩ = **19.5 kΩ**, so τ ≈ **2 ms**. Ignition state changes over seconds, so
this costs nothing in wake latency.

**`power_input`'s generator: RESOLVED 2026-09-15.** It had drifted out of step with the
committed sheet, which had been saved from the KiCad GUI. Diagnosed rather than rewritten: the
entire 258-line delta was cosmetic — `(show_name no)` x110, `(do_not_autoplace no)` x110,
`(body_style 1)` x22, `(in_pos_files yes)` x22, less a `sheet_instances`/`embedded_fonts` block
a child sheet does not carry — plus two orderings the GUI imposes (top-level elements grouped by
type, each group sorted by UUID). **110 + 110 + 22 + 22 − 6 = 258, exactly.**

All twelve `lib_symbols` blocks were already byte-identical, and the symbol, wire, junction,
label and text-box counts already matched, so nothing about the circuit was ever in question.

Repaired, the generator reproduces the pre-J1 committed sheet **byte for byte** — which is what
proves it faithful — and it now also carries the J1 3-way change, so it produces the current
design. Verified three ways: byte-identical against the committed sheet, **all 84 nets identical**
before and after, and ERC unchanged at 23 violations.

The fix generalises. `kicanon.py` now canonicalises **every** generator's output, so opening a
sheet in KiCad and saving it no longer breaks the generator relationship for any sheet — which is
how this one drifted in the first place. All five generators are idempotent.

### Still open

- **The root sheet is now generated, not patched.** `gen_root.py` rewrites `mccan.kicad_sch` from a
  declaration of boxes and pins. The four sheet UUIDs are pinned in that file: every symbol instance
  inside a child sheet carries the parent path, so changing one orphans every reference designator
  on that sheet.
- Root sheet pins are joined by **root-level labels on stubs**, not by wires drawn between the
  boxes. With ~40 inter-sheet nets, drawn wires are an unreadable rat's nest; labels join by name
  at the same scope.
- **The CAN choke and the two ESD diodes are placeholders.** Download datasheets for a CAN-rated
  common-mode choke and a bidirectional CAN ESD array before the BOM is frozen.

## outputs sheet — Task 6, 2026-09-15

PCA9685, 12 RGB switching channels with sense shunts, the 16:1 mux and its sense-path
protection, the dual PROFET, four PTCs and the six panel connectors. **164 symbols.**
Generated by `hardware/scripts/gen_outputs.py`.

### The schematic gate is met

```
kicad-cli sch erc --severity-all --exit-code-violations -o output/erc.rpt mccan.kicad_sch
exit=0     ERC messages: 0   Errors 0   Warnings 0
```

Zero errors **and** zero warnings across all five sheets, which is what the plan's Task 6
Step 8 demands before layout. Every unconnected pin is either connected or carries an
explicit no-connect flag.

### ChannelIndex order verified from the netlist, not from the drawing

This is the one thing on this sheet that silently ruins a working firmware build, so it was
read back pin by pin:

| PCA9685 | net | FET | mux input |
|---|---|---|---|
| LED0 | `PWM_FL_R` | Q4 unit A | S1 |
| LED1 | `PWM_FL_G` | Q4 unit B | S2 |
| LED2 | `PWM_FL_B` | Q5 unit A | S3 |
| LED3 | `PWM_FR_R` | Q5 unit B | S4 |
| LED4–7 | `PWM_FR_G/B`, `PWM_RL_R/G` | Q6, Q7 | S5–S8 |
| LED8 | `PWM_RL_B` | Q8 unit A | S9 |
| LED9–11 | `PWM_RR_R/G/B` | Q8 unit B, Q9 A/B | S10–S12 |

PWM channel *n*, FET *n* and mux address *n* all line up. LED12–15 and mux S13–S16 are
unused — the LEDs no-connect flagged, the mux inputs tied to GND per the datasheet.

Per-channel chain confirmed on both ends of the range:

```
/outputs/SENSE_FL_R   Q4.1[S1]  R52.1(shunt)  R64.1(10k series)
/outputs/MUXIN_FL_R   D9.2[clamp A]  R64.2  U8.19[S1]
/outputs/RET_RR_B     J6.4  Q9.3[D2]  R99.1(DNP snubber)
```

### A cross-domain dependency worth naming

**The shunt package rating is conditional on a firmware behaviour.** Normal dissipation in a
10 Ω shunt is 26.7 mA² × 10 = **7 mW**, so an 0805 or 1206 is ample. A *shorted* channel is
different: the boost current-limits at roughly 0.5 A, putting about **2.5 W** into one shunt —
ten times a 1206's rating. It survives only because the diagnostic sweep is brief and because
firmware **latches a shorted channel off** once it classifies one.

That is written on the sheet, here, and it belongs in the firmware spec (§12) when that is
written. **If firmware does not latch off, the shunts must move to 2512 1 W.**

### Two deviations from the plan, both deliberate

**1. `~OE` is pulled LOW (R78), not high.** The plan says "OE tied so outputs are disabled by
default". Taken literally that means pulling `~OE` HIGH — but no GPIO is allocated to release
it, so the board would be **permanently dark**. "Disabled by default" is already delivered
twice over without this pin: the PCA9685 sits on `+3V3_SW` so it is unpowered in sleep, and it
powers up with MODE1 SLEEP set and every LEDn register cleared. R78 holds `~OE` low so the part
is usable; the safe state comes from the rail and the power-on defaults.

**2. The plan's Step 3 figures are stale.** It still says 1 Ω, 0.14 A and 140 mV, and asks for
2512 ≥ 1 W shunts. Those predate the RGB load being corrected downward ~4× (spec §2.2). Rows
1b.1–1b.3 of this document carry the current values — **10 Ω, 26.7 mA, 267 mV** — and explicitly
withdrew the 2512 requirement. The sheet is built to the current values.

### Sense-path protection — what actually does the work

Each sense node reaches its mux input through **10 kΩ** (R64–R75) with a Schottky clamp to
`+3V3_SW` (D9–D20). The **series resistor** is what bounds a fault: at 24 V on a sense node it
admits **2 mA**, far inside the ADG706's input rating. The clamps are redundancy, and a quad
array may replace the twelve discretes at layout to save area.

**C44, 10 nF at the mux output**, supplies the ADC's sample-and-hold charge locally, which is
what makes 10 kΩ series resistors harmless. τ = 100 µs, so **firmware must wait ≥ 500 µs after
each mux step** before reading. 100 nF would stretch that to 1 ms.

### New symbols built for this sheet

| Symbol | Source | Status |
|---|---|---|
| `ADG706` | `ADG706_707.pdf`, pin configuration p.8 | **Verified** — all 28 pins |
| `NX5020UNBKS` | `NX5020UNBKS.pdf`, Table 2 | **Verified** — 1 S1, 2 G1, 3 D2, 4 S2, 5 G2, 6 D1. Built as a **2-unit** symbol so each channel draws as one FET and six packages cover twelve channels |
| `BTS7008_2EPA` | `infineon_bts7008_2epa_datasheet_en.pdf`, Rev. 1.21, Table 2 p.6 | **Verified 2026-09-15** — all 14 pins plus the exposed pad. See "PROFET resolved" below |

### ~~BLOCKER for Task 8 — the PROFET~~ **RESOLVED 2026-09-15**

The Infineon datasheet arrived (`hardware/datasheets/infineon_bts7008_2epa_datasheet_en.pdf`,
**Rev. 1.21, 2024-07-29**) and the whole block was rebuilt against it. See
**"PROFET — pinout, sense chain and control lines"** below for the full record. In summary:

- **U9's pin numbers were all wrong** and are now verified against Table 2. Six pins that did
  not exist in the placeholder symbol do exist in the part.
- **`R81` is sized: 2.2 kΩ.** The `TBD-see-note` value is gone.
- **The footprint is identified** — `Package_SO:Infineon_PG-TSDSO-14-22`, which ships with
  KiCad — so Task 8 does not have to draw one.

### Corner connectors — a safety item, recorded in the schematic

All four are identical Superseal 1.0 4-way parts and **can be mis-mated**; swapping front for
rear reverses the indicators and firmware cannot detect it (spec §9.2). Each connector's Value
field carries a distinct keying/colour code — **FL key A / black, FR key B / grey, RL key C /
brown, RR key D / natural** — because the schematic is where that decision has to be recorded.
Carry these into the harness build and the install instructions.

### Netlist integrity after the whole schematic is complete

**158 nets.** Spot-checked across every sheet boundary: `+24V` reaches all four PTCs and each
PTC feeds exactly one corner; `+3V3_SW` carries the load switch, both ICs and all twelve clamp
cathodes; `CANH`/`CANL` join the choke on `mcu_can` to the connector here; `VBAT` spans
`power_input`, `rails` and the PROFET; and `GND_IN` is **still separate from `GND`**, so the
common-mode choke split survives intact. All six generators remain idempotent.

## PROFET — pinout, sense chain and control lines — 2026-09-15

Verified against **Infineon BTS7008-2EPA Data Sheet Rev. 1.21, 2024-07-29**, held locally at
`hardware/datasheets/infineon_bts7008_2epa_datasheet_en.pdf`. This closes the Task 8 blocker.

### The placeholder pinout was wrong in every position

Table 2 "Pin Definition" (p.6), cross-checked against Figure 4 "Pin Configuration" (p.5):

| Pin | Symbol | Was (placeholder) |
|---|---|---|
| **EP (pad 15)** | **VS** — battery supply, *the only supply connection* | invented pin 8, a normal side pin |
| 1 | GND | was IN0 |
| 2 | IN0 | was IN1 |
| 3 | DEN | was DEN — right name, wrong number |
| 4 | IS | was DSEL |
| 5 | DSEL | was OUT0 |
| 6 | IN1 | was OUT1 |
| 7, 11 | n.c., internally not bonded | did not exist |
| 8–10 | OUT1 | did not exist |
| 12–14 | OUT0 | did not exist |

Two things the placeholder could not have guessed:

**VS is the exposed pad.** There is no side pin for battery. A layout that treats the pad as a
thermal-only feature would leave the part unpowered.

**Each output is three pins, and Table 2 note 1 is mandatory** — "All output pins of the channel
must be connected together on the PCB. ... PCB traces have to be designed to withstand the maximum
current which can flow." All six are modelled and tied on the sheet, so Task 9 cannot route one
pin per channel and call it done: **3.3 A has to be carried on all three.**

### Footprint — already in KiCad, and it fixes the pad number

`Package_SO:Infineon_PG-TSDSO-14-22` ships with KiCad 10. Its **pad 15** is the 2.65 × 4 mm thermal
pad at the origin, which is why VS is numbered 15 in the symbol rather than "EP". PG-TSDSO-14-22 is
the former name of the same package — the datasheet's own revision history records the rename
("Page 1: updated (Package PG-TSDSO-14-22 → PG-TSDSO-14)").

### R81 = 2.2 kΩ — how the sense chain was sized

`kILIS` = **5400** at IL14 = 2.8 A (±5.8%) and **5450** at IL16 = 5.5 A (±4.0%), Table 22 p.53.
The Denali draws **3.3 A per channel** (spec §2.2), so the IS pin sources 3.3 / 5400 = **611 µA**.

| | Value | Consequence |
|---|---|---|
| **R81** (RSENSE) | **2.2 kΩ** | 611 µA × 2.2 k = **1.34 V** at 3.3 A — mid-scale for ADC1 at 11 dB (usable ≈ 0.15–2.45 V) |
| ADC full scale | 2.45 V | = **6.0 A**: above the working point, below the 7.5 A nominal rating, so a real overcurrent still reads *on scale* instead of pinning |
| ADC floor | 0.15 V | = **368 mA**. Open load is IL(OL) ≈ 21 mA (Table 22), so an open channel reads a hard zero — unambiguous |

**R82 (RIS_PROT, 4.7 kΩ) and R83 (RADC, 4.7 kΩ) are not optional, and their absence was a real
defect in the Task 6 sheet.** Under a fault the IS pin *saturates*: Table 20 p.50 gives
IIS(SAT) = 4.1–15 mA and a saturation voltage VS − VIS of only **0.5 V typ / 1 V max**. The sense
node therefore sits within a volt of battery — **about 12.5 V** — and the earlier chain wired that
node to GPIO 34 through nothing but a Schottky clamp. R83 is what keeps it off the pin; D21 then
clamps the remainder to `+3V3_ALW` at under 2 mA.

C47 (220 pF) with R83 gives the ≥1 µs time constant the datasheet's Table 24 asks for. **C48
(10 nF) at the ADC end** supplies the SAR sample-and-hold charge locally — that is what makes a
4.7 kΩ series resistor harmless. τ = 47 µs, so **firmware must settle ≥ 250 µs after selecting a
channel with DSEL** before reading. (Compare the RGB chain's 500 µs at C44 — same principle,
different constant.)

### Control lines — and a divider that would have failed at temperature

R79, R80, R84 and R85 are the datasheet's **RIN / RDEN / RDSEL, 4.7 kΩ** (Table 24 p.54). They
protect the MCU during overvoltage and reverse polarity, and — the part that matters on a vehicle
— they are what allows the outputs to switch **OFF on loss of ground**.

The pulldowns are deliberately on the **MCU side** of those resistors. In series the two would form
a divider: 3.3 V × 10 k / 14.7 k = **2.24 V** at the input pin, against a guaranteed-high threshold
of **2.0 V max** (Table 7 p.14). A 240 mV margin across tolerance and −40…150 °C is not a margin.
On the MCU side the pin is driven through 4.7 kΩ into a microamp input, so the drop is negligible.

Only `PWM_DEN_A` / `PWM_DEN_B` needed a pulldown adding (R86, R87). `EN_DIAG` and `DEN_DSEL`
already have R35 and R34 in **mcu_can's passive-defaults block**, and that block exists precisely
so these live in one place — duplicating them here would have defeated it. All four must be low
for the PROFET to reach **Sleep mode (0.6 µA)** rather than Stand-by, and GPIO 18/19 float in reset.

### Deliberately not fitted

No **RPD** (47 kΩ output pulldown), **ROL** or **T1**. Those exist only for *OFF-state* open-load
diagnosis, which §5.3 does not ask for — ON-state sense through IS covers what this design needs.
RPD would also draw ~290 µA per channel whenever the output is on.

### Row 2.6's conditional PASS — now quantified, still conditional

Thermal data was not available when row 2.6 was written. Table 6 p.11 gives **RthJC = 0.8 K/W typ
/ 1.4 max** (junction to exposed pad) and **RthJA = 30.9 K/W** on a JEDEC 2s2p board; Figure 10
p.12 plots RthJA against cooling area for a 1s0p board, running roughly from the low forties to
about 110 K/W — read that curve visually before relying on a number from it.

At the budgeted 0.35 W for the pair, that is an **11–38 K rise**, so TJ at 85 °C ambient lands
somewhere around **96–123 °C — never the 150 °C at which the 16 mΩ maximum is specified.** The
0.349 W worst case in row 2.6 is therefore not a reachable operating point, and the realistic
figure is ~0.30–0.32 W. **Row 2.6 stays a conditional PASS** — the condition is now numeric rather
than open-ended, and §9.4's 0.35 W budget is conservative against it. Confirm at layout, once the
copper area under the pad is known.

### Component changes on the outputs sheet

| Ref | Was | Now |
|---|---|---|
| R79, R80 | 10 kΩ pulldowns | **4.7 kΩ series** (RIN) |
| R81 | `TBD-see-note` | **2.2 kΩ** (RSENSE) |
| R82, R83 | *(did not exist)* | **4.7 kΩ** RIS_PROT, RADC |
| R84, R85 | *(did not exist)* | **4.7 kΩ series** (RDEN, RDSEL) |
| R86, R87 | *(did not exist)* | **10 kΩ pulldowns**, MCU side |
| C47, C48 | *(did not exist)* | **220 pF** CSENSE, **10 nF** ADC hold |
| C44–C48 | were C45–C49 | shifted down one to **close a pre-existing C44 gap** in the BOM |
| R88–R99, C49–C60 | were R82–R93, C48–C59 | DNP snubbers, shifted to make room |

**Designators are now gapless**: R1–R99, C1–C60, D1–D21, Q1–Q9, U1–U9, J1–J8, F1–F5, L1–L6,
SW1–SW2, with no holes in any series.

### Verification after the rebuild

```
kicad-cli sch erc --severity-all --exit-code-violations
exit=0     0 errors   0 warnings
```

**166 nets** (was 158; the eight new ones are the series resistors' local nets, the sense node,
and the two n.c. pins). Read back from the netlist:

```
/VBAT                  ... U9.15[VS]                       <- the exposed pad
/outputs/DEN_A_OUT     J7.1  U9.12  U9.13  U9.14           <- all three OUT0 pins
/outputs/DEN_B_OUT     J7.2  U9.8   U9.9   U9.10           <- all three OUT1 pins
Net-(U9-IS)            R82.1  U9.4
Net-(C47-Pad1)         C47.1  R81.1  R82.2  R83.1          <- the sense node
/ISNS_DEN              C48.1  D21.2  R83.2  U5.6[IO34]
/PWM_DEN_A             R79.1  R86.1  U5.30[IO18]           <- pulldown on the MCU side
/DEN_DSEL              R34.1  R85.1  U5.9[IO33]            <- R34 from mcu_can, not duplicated
unconnected-(U9-n.c.-Pad7), -Pad11                         <- no-connect flagged
```

ChannelIndex order re-checked and unchanged: LED0 → `PWM_FL_R` → Q4 unit A … LED11 →
`PWM_RR_B` → Q9 unit B.

## Sleep budget roll-up (spec 8.2: target < 200 uA, ceiling 500 uA)

| Contributor | Datasheet value | Source |
|---|---|---|
| ESP32 deep sleep + EXT0 RTC_PERIPH domain | **10 uA** | Espressif "ESP32 Series Datasheet" v5.3, Table 4-2 "Power Consumption by Power Modes", row "Deep-sleep — RTC timer + RTC memory — 10 uA" (fetched 2026-09-12). The datasheet does not break "RTC_PERIPH domain for EXT0 wake" out as a separate incremental line from this baseline — RTC memory + RTC timer retention is part of the same RTC power domain that EXT0/RTC_GPIO wake depends on, so the two rollup rows are combined into this single verified figure rather than inventing a split that isn't in the source. (For contrast, the datasheet's next tier up, "Deep-sleep — ULP coprocessor powered up — 150 uA", is not needed for EXT0 alone and was not used here.) A human should still check the ESP32 Technical Reference Manual's more granular power-domain table if a tighter figure specific to "RTC_PERIPH with GPIO wake, ULP off" is wanted. |
| CAN transceiver standby | **19 uA max** | This file, row 5.3 — NXP TJA1042T/3, Table 7 p.10: ICC (Standby) max 5 uA + IIO (Standby) max 14 uA = 19 uA max, condition VTXD = VIO (firmware must hold TXD/STB high through sleep). |
| Buck quiescent - **3.3 V rail only** | **10.5 uA typ / 25 uA max** | This file, rows 4.1 and 4b.1 — TI LM5164 (SNVSAU4D), IQ-SLEEP1 10.5 uA typ / 25 uA max **per instance**; **only ONE instance counts in sleep**: the 5 V rail is **enable-gated off** (spec 6, project review I10 - the TJA1042's low-power receiver runs on VIO alone and detects bus activity with VIO as its only supply, so VCC is not needed for wake). An earlier revision counted two always-on instances. |
| **Boost shutdown (LM51571-Q1)** | **<= 2.6 uA** | This file, row 3.5 - datasheet p.1 "Low shutdown current (IQ <= 2.6 uA)". **Was 9/17 uA with the LM5122-Q1**; the part swap saves ~14 uA. |
| ~~Boost UVLO divider~~ **REMOVED** | **0 uA** | **Deleted 2026-09-13:** `EN_UVLO_SYNC` is now driven directly from the GPIO with no divider (see above), so this contributor no longer exists. |
| PROFET standby | **0.6 uA max** | This file, row 2.7 — Infineon BTS7008-2EPA, Table 1 p.2: IVS(SLEEP)_85 max 0.6 uA (one device required). |
| Low-side switches standby (12x PMV60ENEA leakage) | **<= 12 uA max (updated, fix round 1)** | This file, row 1a.8 — Nexperia PMV60ENEA Table 7: "IDSS drain leakage current — VDS = 40 V; VGS = 0 V; Tj = 25 degC — Max 1 uA." Bounded above by this 40 V figure for our lower 24 V operating point (leakage increases monotonically with reverse bias, so 24 V leakage <= the 40 V figure). 12 channels x 1 uA max = **12 uA max**. This replaces the previous IRLZ44N-based ~300 uA pessimistic bound now that the MOSFET recommendation has reverted to the SOT-23 PMV60ENEA (fix round 1, Finding 1/2) — the sleep-budget blowout was a direct symptom of the wrong package/part, not an inherent property of this design. |
| P-FET gate + divider leakage | **UNVERIFIED — depends on a resistor value not yet chosen** | This file, row 6.1 — Vishay SQJ415EP gate leakage (IGSS) itself is negligible (max +/-100 nA per the datasheet), but the P-FET's gate resistor + Zener clamp network (spec 4.2) has a divider value that is a Task 3/4 schematic decision, not yet made. A divider sized for >= 1 MOhm total resistance would add <= 24 uA at 24 V; this is a design target to carry into Task 3/4, not a verified figure. |
| **SUPERSEDED - known contributors, old basis** | ~~62.6 uA typ / 92.6 uA max~~ | Sum of ESP32+EXT0 (10) + CAN (19) + buck x2 (21 typ / 50 max) + PROFET (0.6) + RGB-FET leakage (12 max, itself a valid upper bound) = 62.6 uA typ / 92.6 uA max. |
| **3.3 V buck feedback divider (>= 500 kOhm)** | **~6.6 uA** | The LM5164's quoted IQ does NOT include the external FB divider; at a conventional 275 kOhm it would be ~12 uA. The 5 V rail's divider does not count - that rail is gated off in sleep. |
| **REVISED TOTAL 2026-09-13** | **~85 uA typ / ~100 uA max** | ESP32+EXT0 (10) + CAN (19) + buck x1 (10.5 typ / 25 max) + PROFET (0.6) + RGB-FET leakage (12) + P-FET gate network (24) + **boost shutdown (2.6)** + **buck FB divider (6.6)**. Down from 99-122 uA: the LM51571-Q1 saves ~14 uA on shutdown current and dropping the UVLO divider saves another ~14 uA. |

**Verdict, REVISED 2026-09-12 after the project review.** The earlier claim of
"63-117 uA ... confirmed PASS" was **wrong**: it omitted the boost controller
entirely, excused that omission with a false statement about the P-FET, and never
accounted for the UVLO divider, whose datasheet-example values alone draw
~207 uA. A board built to the old text would have drawn **~250-350 uA parked** -
under the 500 uA hard ceiling, so it would have passed as "working" while running
at 2-3x the predicted drain, and Stage 3 bring-up would have been chased as a
mystery.

**Revised total: ~99 uA typ / ~122 uA max.** That does meet the 200 uA target,
but only **conditionally**, and both conditions are schematic decisions that must
be honoured in Task 3/4 rather than assumed:

1. ~~The boost UVLO divider must be >= 1 MOhm~~ **CONDITION REMOVED 2026-09-13** - there is no
   divider; `EN_UVLO_SYNC` is driven straight from the GPIO.
2. **The P-FET gate/Zener network must be >= 1 MOhm** (row 6.1) - still a design
   target, not a chosen value. **This is now the only remaining condition.**
3. The 3.3 V buck's feedback divider must be **>= 500 kOhm** (new, see the roll-up).

Gating the 5 V rail (I10) recovered a further 10-25 uA and is what gives the
revised figure its margin.

---

*Superseded text from fix round 1, retained for traceability:* with the MOSFET reverted to the SOT-23
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
| RGB channel low-side FET (x12) | Nexperia **PMV60ENEA**, primary. **PMV30ENEA verified as a second-source part number this pass (electrically qualified, see 1a candidate screening) — but it does NOT relieve the stock shortage below.** | SOT23 (TO-236AB), both part numbers | $0.54 (qty 1) / $0.102 (qty 9,000) — Digi-Key, live fetch 2026-09-12, PMV60ENEAR | **Digi-Key PMV60ENEAR: 0, "3,000 expected 18-Jan-2027," 30-week mfr lead time (live fetch 2026-09-12). PMV30ENEAR: also 0 at Digi-Key (30-wk backorder) and Mouser (notify-me only) — same shortage, not an alternate. TTI ~9,000 units for PMV60ENEA (search-summary sourced, still not independently confirmed).** UNVERIFIED, see row 1a.6 — human must check TTI/LCSC/Arrow directly before assuming stock exists |
| RGB channel sense resistor (x12) — **VALUE CHANGED 1 ohm -> 10 ohm (2026-09-13)** | **10 ohm, 1%, 0805 or 1206** — the 2512/1 W part is no longer needed | 0805/1206 | ~$0.10 | **TO SELECT** — a 1% 10 ohm thin-film is a commodity; the previous 1 ohm RC2512FK-071RL is superseded |
| 16-channel analog mux | Analog Devices **ADG706BRUZ** | 28-TSSOP | $9.73 (qty 1) / $5.85 (qty 1000) (Digi-Key, live page fetch 2026-09-12) | 5,789 (Digi-Key, live page fetch); Active, 21-week manufacturer lead time |
| Dual smart high-side switch (Denali) — **conditional PASS: row 2.6 passes at 25 degC typ but FAILS at the 150 degC max (0.349 W > 0.25 W). Acceptable given spec 2.4 (Denali off in daytime), but the condition must be carried.** | Infineon **BTS7008-2EPA** (order as BTS70082EPAXUMA1) | PG-TSDSO-14 | $2.30 (qty 1) / $1.17 (qty 3000) | 6,947 (Digi-Key, live page fetch) |
| Synchronous boost controller | TI **LM5122QMHX/NOPB** | 20-HTSSOP | $6.21 (qty 1) / $3.62 (qty 1000) | 594 (Digi-Key, live page fetch) |
| Low-quiescent buck, 3.3 V rail | TI **LM5164DDAT** | 8-PowerSOIC (HSOIC-PowerPAD) | $5.37 (qty 1) / $3.43 (qty 100) | 7,056 (Digi-Key, live page fetch); 16-week lead time noted on the page |
| 5 V regulator (transceiver rail) | TI **LM5164DDAT** (same part, second instance, different feedback divider) | 8-PowerSOIC | (same as above) | (same as above) |
| CAN transceiver | NXP **TJA1042T/3** (order as TJA1042T/3,118) | SO8 | $1.67 (qty 1) / $0.864 (qty 1000) (search-summary sourced) | 966 (search-summary sourced) — part selection itself verified in Section 5, out of this pass's scope |
| P-FET (front-end protection) | Vishay Siliconix **SQJ415EP-T1_GE3** | PowerPAK SO-8L | $1.63 (qty 1) / $0.43 (bulk) (Digi-Key, live page fetch 2026-09-12) | 19,148 (Digi-Key, live page fetch); Active, 26-week manufacturer lead time |
| TVS (front-end clamp) | **SMBJ24A** — **row 6.2 CLOSED 2026-09-18, verified from `smbj.pdf`** (see Correction 2) | DO-214AA (SMB) | $0.50 (qty 1, distributor-sourced) | 32,003 (distributor-sourced) — see row 6.2: **the two files this repo ships as "TVS" datasheets are not SMBJ24A electrical datasheets** (one is an unrelated Diodes Inc. wafer-fab PCN, the other an unrelated Powerex SCR/diode module datasheet) and a primary manufacturer PDF has now failed to open on **9 separate attempts** across two sessions (Bourns and Littelfuse both 403, Mouser and ST both timeout, plus 5 earlier failures). Distributor-corroborated figures (24 V standoff / 26.7 V min breakdown / 38.9 V clamp @ 15.4-15.5 A / 600 W) are consistent everywhere they're checked and would PASS the criteria on their face — a human must obtain a genuine PDF by a non-automated channel (browser download) and confirm before ordering |
| PTC (x4, one per RGB string) | Littelfuse **1206L050/24WR** | 1206 (3216 metric) | $1.88 (qty 1) / $0.841 (qty 1000) | 24,602 (Digi-Key). **Row 6.3 now PASSES** — the real 0.08 A load against 0.31 A hold at 65 degC is a 3.9x margin; the family-wide FAIL applied only to the superseded 0.42 A load |
| Schottky OR pair - **populate ONE only** (single feed); the second is a DNP footprint (x2 positions) | Nexperia **PMEG4010ER,115** | SOD123W | ~$0.42 (qty 1, search-summary sourced) | not confirmed this session |
| Boost inductor | Coilcraft **XAL7070-682ME** (order as XAL7070-682MEC) | 7x7x3 mm shielded molded | not confirmed this session | not confirmed this session (a distinct but related part number, XAL7030-682MEC, was seen in search results — verify the exact 7070 vs 7030 case size before ordering) |
| **Boost converter** | TI **LM51571-Q1** (LM51571QRTERQ1) | WQFN-16, 3x3 mm | — | **SELECTED 2026-09-13**, verified from the local datasheet. Integrated 50 V / 4.33 A switch, shutdown IQ <= 2.6 uA, dual random spread spectrum, AEC-Q100 grade 1. Symbol + footprint in the project libraries |
| **Boost rectifier** (non-synchronous topology) | **TO SELECT** — Schottky, Vr >= 40 V, If >= 1 A, Vf <= 0.5 V at 320 mA | SMA/SMB class | — | See row 3.7 |
| ~~Boost external FETs (x2)~~ | **NOT REQUIRED** — the LM51571-Q1 integrates the switch (row 3.6 void) | — | — | — |

**P-FET — resolved, fix round 1 Finding 3.** With Row 6.1's RDS(on) ceiling
relaxed to <= 20 mOhm and the VGS rating judged with the spec-4.2 Zener gate
clamp in circuit (so the gate never sees the full rail), Vishay SQJ415EP
passes cleanly — see row 6.1 for the full readout. Under the **single feed** it
dissipates 0.30 W in daytime (3.9 A) and **1.22 W at night (7.8 A)** at the
20 mOhm ceiling, well inside the part 45 W package rating, though the junction
rise is ~85 degC at RthJA rather than the ~43 degC quoted for the superseded
dual-feed case — acceptable because the device is gap-padded to the finned plate.

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


---

## Correction 2 — row 6.2 is closed, and the 8/20 µs clamp is not 38.9 V

**2026-09-18.** Row 6.2 sat **UNVERIFIED** across two sessions and **nine failed fetch attempts**,
with a note that "a human must obtain a genuine PDF by a non-automated channel." **They already had.**
`hardware/datasheets/smbj.pdf` is a **genuine Bourns SMBJ Transient Voltage Suppressor Diode Series
datasheet** (600 W, standoff 5–495 V, SMB/DO-214AA). It was sitting in the folder, unindexed in
`datasheets/README.md` and uncited by row 6.2, while the row said it did not exist.

*Lesson, and it is the same shape as the earlier SMBJ correction: **list the directory before
concluding a document is unobtainable.** The first correction was believing a file was a datasheet
without reading it. This one is believing a datasheet was absent without looking.*

### What it says

Reading it is not straightforward — `pdftotext -layout` **staggers the table's three column blocks
against each other**, so the numbers that land on a given part's row belong to other parts. The
alignment was pinned from the document itself rather than assumed: the V<sub>RWM</sub> column steps
through the standard series (5.0, 6.0, 6.5, … 24, 26, 28, …), and **V<sub>C</sub>/V<sub>BR(max)</sub>
holds at ≈ 1.31 across every row** only under a +2-line offset for the clamping block. Four rows were
checked independently under that offset.

> **SMBJ24A** — V<sub>RWM</sub> **24.0 V**, V<sub>BR</sub> **26.7–29.5 V** @ 1.0 mA,
> I<sub>R</sub> 1.0 µA, **V<sub>C</sub> 38.9 V @ I<sub>PP</sub> 15.5 A (10/1000 µs)**,
> **V<sub>C</sub> 50.6 V @ I<sub>PP</sub> 77.5 A (8/20 µs)**.

The 10/1000 µs figures match the distributor corroboration exactly. **Row 6.2 PASSES**: 24 V standoff,
38.9 V clamp under the 40 V criterion, 15.5 A against a 7.8 A feed, and V<sub>BR(min)</sub> 26.7 V is
above a 24 V double-battery jump so it will not conduct.

### The new fact — and it was never in any distributor summary

**The 8/20 µs clamping voltage is 50.6 V, not 38.9 V.** Every corroborating source quoted only the
10/1000 µs column. The criterion "clamping voltage < 40 V" is therefore **true for 10/1000 µs at
rated I<sub>PP</sub> and false for 8/20 µs at rated I<sub>PP</sub>.**

**This is a flag, not a failure.** 50.6 V is the clamp at the *full* 77.5 A 8/20 pulse; a transient
reaching this board passes a 10 A fuse and the π filter first, so the realistic pulse current — and
therefore the realistic clamp — is far lower. But three consequences should be checked before the
BOM freezes, and none of them were visible while only the 38.9 V figure was known:

1. **C3, the 220 µF electrolytic on `VBAT`, should be 63 V, not 50 V.** The schematic review (O1)
   called for "≥ 50 V" against a 38.9 V clamp. Against a 50.6 V worst case a 50 V part has **no
   margin at all**. **63 V is the correct call**, and it is the same footprint decision either way.
2. **The boost's 50 V transient limit is no longer clear of the clamp.** Row 3.1 passes the
   LM51571-Q1 on "input transient protection up to 50 V" against a "~39 V clamp". Worst-case 8/20 is
   **50.6 V** — at or just past that limit. Re-examine at the EMI/transient pre-scan (spec §10).
3. **Q1's headroom is better than the review credited, and the retired part was worse.** Against
   50.6 V the **SQJ461EP (60 V) keeps 9.4 V**, not the 21.1 V computed from 38.9 V — still a pass.
   The **SQJ415EP (40 V) would have been destroyed outright**, not merely run at 2.8% margin. Finding
   **F1** was more load-bearing than it looked when it was written.

**Unaffected:** the RGB MOSFETs' 40 V V<sub>DS</sub> (row 1a.1). They sit on the **+24 V boost
output**, not on `VBAT`, so they do not see the TVS clamp. Row 1a.1's conditional wording — "the TVS
clamp voltage (row 6.2) must settle below 40 V for this to hold" — **states a dependency that does
not exist** and should be read as referring to the boost's own output, not the input clamp.
