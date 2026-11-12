# ESP32 MCCAN — Night Mode and Dimmed Aux Pods

**Date:** 2026-11-01
**Status:** Draft for approval
**Amends:** `2026-10-17-emarked-module-redesign-design.md` §2.1, §2.2, §3, §5.2–§5.6 and §7.
Where the two disagree, this document wins.

## 1. Why this exists

The Oxford EL359 is now fitted on the front, alongside the EL360 on the rear, so the board drives
all four corners. The user wants the front lighting to change with day and night: the white
EL359 light by day, the Oxford 4K pods at low intensity by night, and the pods at full on high
beam.

## 2. Goals and non-goals

**Goals**
- Day and night front lighting as set out in §3.
- Pods dimmable across Oxford's five stages.
- Night mode taken from the Experia's CAN signal, with a flash-switch fallback.
- Indicators flash correctly when the CAN signal is a steady "on" rather than a flash.

**Non-goals**
- The spot latch. The user chose to remove it, not to preserve it in another form.
- Automatic day/night sensing. No light sensor is added.
- Board layout before the kit arrives.

**Failure, even if it technically works**
- A pod lighting at full when low was asked for, at night or after a reset.
- Night mode toggling by itself during normal riding.
- A partial indicator sweep.

## 3. Behaviour

| State | Front white (EL359) | Aux pods | Rear running light | Rear brake |
|---|---|---|---|---|
| Day | On | Off | On | With brake signal |
| Night | Off | Low, both sides | On | With brake signal |
| High beam, day or night | As day or night row | Full, both sides | On | With brake signal |
| Left or right indicator, day | Same side off | As above | Same side off | Same side off |
| Left or right indicator, night | Off | As above; same side off if `auxDarkenOnIndicate` is on (§3.1) | Same side off | Same side off |
| Hazards | As indicator, both sides | As above | Off | Off |
| Run clear | Off | Off | Off | Off (indicators and hazards still work) |

The indicating corner shows amber only. At night the front white is already off, so only the rear
has anything to drop.

The flash switch itself does not light the pods. A short flash leaves the pods unchanged.

**Level rule:** `AUX = Off if !run; Full if highBeam; Low if nightActive; otherwise Off`.

**An indicating corner shows amber only (user's choice, 2026-11-08).** The units can run every
function at once, but the indicator is clearer on its own, so same-side white, running light and
brake stay off while indicating (earlier spec §5.3).

**The pods are auxiliary lights, not DRLs (user's decision).** The DRL same-side dropout does not
apply to them.

**Compliance is unconfirmed.** Aux-light rules for this use have not been checked (§9).

### 3.1 Option: darken the indicating side

`auxDarkenOnIndicate` is a web-app setting, **off by default**. When on, a pod at Low turns off on
the indicating side for as long as that indicator request lasts, then returns to Low.

- It follows the request, never the flash phase, so the pod does not pulse with the indicator.
- Hazards do not darken either pod, because both pods would go out.
- High beam does not darken, so full aux stays full.

"Off" is the builder's reading of "darken", chosen because it works without per-pod dimming. It
is only available if the §6 branch can control each pod separately.

## 4. Night mode source

`nightActive` comes from one of two places, never both:

- **DayNight mapped to a CAN signal:** the signal decides, and the flash long press does nothing.
- **DayNight unassigned (`count == 0`):** the flash long press toggles `nightToggled`.

The user believes the Experia's mode is on CAN, but this has not been confirmed.

### 4.1 Flash long press

A long press toggles once per press when all of these hold:

- `run` is true
- DayNight is unassigned
- `flash` has been true for at least the hold time
- `highBeam` is false for the whole press

**The `highBeam` gate is essential.** `HighBeam` is bit 6 AND bit 16 and `HighBeamFlash` is bit 16,
so `s.flash` is also true on steady high beam. Without the gate, holding high beam would toggle
night mode after 800 ms. This replaces the open question in the old spot-latch note, and it must
have a regression test.

Holding on past the threshold does not toggle again. Moving from a held flash to high beam
without releasing must not toggle a second time.

`nightToggled` lives in `EngineState`, so it starts in day after every key-off (CAN off, board
asleep, reset). This is the builder's call and is a small change if the user prefers otherwise.

Whether the flash position really reads bit 16 without bit 6 must be confirmed on the Discovery
tab (§7).

### 4.2 Removing the spot latch

Delete `spotLatched`, its low-beam auto-drop and its tests. Rename `spotHoldMs` to `nightHoldMs`
with the same 800 ms default. Rename the web app's field to match. `configFromJson` must accept
the old key when the new one is absent, so a saved value survives. Bump the web protocol version.

The user chose to lose hands-off full aux on low beam.

Test mode's guard that a test session cannot leak state into the real engine must be kept and
pointed at `nightToggled`.

## 5. Indicators

`flashSource` default changes from `auto` to `generate`.

- All four corners are now on the board, so nothing has to stay in phase with the bike's flasher.
- The user reports the CAN bit shows steady "on". `auto` would hold the lamps solid for 1.2 s
  before flashing, and that is unacceptable on a steady bit.

`auto` and `follow` remain selectable. A missing or unreadable `flashSource` value now resolves to
`generate`, matching the new default. Saved configs keep their stored value, so an existing board
must be changed by hand or by the web app.

**`generate` needs one fix.** `flashIsOn` currently uses `nowMs % (2 * period)`, so the first
on-phase can start part-way through, which cuts the first sweep short. The phase must start at the
request's rising edge, and the first on-phase must be a full period.

Both sides must stay in step during hazards. When a side starts while the other is already
flashing, it joins the running phase. Use unsigned subtraction, and pick rollover test sample
points as `timing-test-sample-points` in project memory describes.

`blinkPeriodMs` must exceed the sweep time of both the EL359 and EL360, which is unmeasured. The
current 340 ms on, 340 ms off is about 1.47 Hz. Legal flash rate must stay within 1–2 Hz, so
on-time cannot exceed 500 ms with equal on and off times.

## 6. Aux output

`computeOutputs` gains an `AuxLevel { Off, Low, Full }` in `OutputIntent`, kept outside the 12-bit
word so tests still assert the whole output state. There is one level per pod, because
`AUX_L` and `AUX_R` differ only under §3.1. Otherwise they carry the same level.

### 6.1 Resolved 2026-11-12: Branch A, a 5 V PWM input per pod

The kit was measured on the bench (earlier spec §2.2.1):

- **Yellow** takes a **5 V PWM at about 100 Hz** that sets the main LEDs' brightness. Oxford's dial
  gives about 15 / 35 / 55 / 80 / 100% for stages 1–5, and 0 V with main beam off.
- **Red and black** are the supply. Power alone lights the **DRL LEDs** beside the aux light, which do not dim.
- **Blue** sits at about 0 V in every state and is open circuit to black. Its role is still open
  (§9); the board will treat it as Oxford's harness does.

So the board can make every level itself:

| `AuxLevel` | Pod supply | Yellow duty |
|---|---|---|
| Off | Off | 0% (held low) |
| Low | On | `auxLowDuty` |
| Full | On | `auxFullDuty` |

- **`auxLowStage` (1–5) becomes `auxLowDuty`, a percentage.** Default 15%, Oxford's stage 1. The
  web app's control sets the percentage directly. Oxford's stages are a reference, not a limit.
- **`auxFullDuty`**, default 100%, caps Full. It exists as a power fallback (earlier spec
  §4.1.1) and is not expected to be lowered with the pods on a 15 A circuit.
- **Each pod has its own yellow wire**, so §3.1's darkening is available as designed.
- **Oxford's dial and harness are not used.** The earlier spec's "bypass Oxford's harness" stands.
- **Both pods share the Experia's 15 A aux 3 circuit as board feed B**, each with its own switch
  (earlier spec §4.1.1; rating to be confirmed on the bike). The Experia has no 12 V battery, so
  Oxford's battery-direct feed is not possible.
- **Board hardware:** **one shared ESP32 LEDC channel** at about 100 Hz, through a 5 V buffer
  powered from the gated `+5V` rail, with one buffered output per pod's yellow wire. One channel
  is enough because every pod that is not Off carries the same level: §3.1's darkening makes a
  pod Off, which is its switch, never a different duty. The buffer must hold yellow low at reset
  and with its input open (earlier spec §3.2), and must survive yellow being shorted to 12 V in
  the harness. The U13 CH3/CH4 reservation below is no longer needed for this.
- **There is no free GPIO on the phase-A pin map** (every bonded GPIO is assigned). The PWM needs
  one. **Proposed: GPIO 13**, freed by removing status LED D5 and moving the factory-reset
  gesture's feedback onto the four indicator outputs. To be confirmed by the user.
- **The DRL LEDs are lit at Low as well as Full.** Whether that is acceptable at night is open (§9).

The rest of this section is the pre-measurement record, kept for its reasoning.

A new config value, `auxLowStage` (1–5), selects what Low means. Default is stage 1 until stages
are measured. The web app gets a control for it.

How the level reaches the pods depends on what the kit shows. **This part cannot be finalised
until the kit arrives.**

| | Branch A: pod plug has a mode input | Branch B: plain + and − only |
|---|---|---|
| Control | Board drives the mode input | Board drives Oxford's `ACC RUN` and `ACC HIGH BEAM` lines; Oxford's harness stays |
| `auxLowStage` in web app | Works, if stages can be reproduced | Removed; Oxford's dial sets the low level |
| Dial | Replaced | Kept, or Oxford's switch-delete blank if it gives the right level |
| Power feed | Two feeds as designed | Reassess: Oxford's kit is designed for a battery-direct feed |
| Earlier spec's "bypass Oxford's harness" | Stands | Reversed |
| §3.1 darkening | Available | Probably unavailable, because Oxford's lines control the pair; hide the setting if so |

A third outcome is possible: if Oxford's lines cannot produce both low and full under board
control, the requirement cannot be met as written and goes back to the user.

**PWM of the pods' 12 V supply is not an option.** Each pod has its own converter (§2.2 of the
earlier spec).

**Board provision:** U13 CH3 is reserved for `AUX_MODE` and CH4 is spare. Both are 12 V high-side
channels and may suit either branch, if the kit's signals are 12 V level and draw under the 0.5 A
limit. Confirm that two GPIOs are free before relying on this. The AUX stage's switches remain
kit-gated, and the layout stays on hold.

**Until the kit is resolved, the HAL treats `Low` as off.** A pod must never light at full because
low was requested.

## 7. Finding CAN signals

**Corrected 2026-11-01: no new screen is needed.** The web app's Discovery tab already streams live
frames and assigns a clicked bit to a function. The user watches it while flipping the Experia's
mode. It also confirms the other unverified signals.

**One gap must be fixed.** `CanState` tracks only the first 16 distinct IDs and silently ignores
the rest, for lighting as well as Discovery. On a busier bus, a mapped ID such as `0x102` or the
day/night ID may never be seen, depending on arrival order. Raise `MAX_FRAMES` and the Discovery
snapshot to 64. The CAN controller stays listen-only, and the change must not affect the lighting
loop.

## 8. Testing

Native tests, each asserting the whole output state:

- every row of §3, day and night
- level rule, including Run clear
- §3.1 darkening: off by default, follows the request not the phase, skipped on hazards and high
  beam
- CAN-mapped night mode ignores the long press
- long press toggles once per press, and not on a short flash
- steady high beam held well past the threshold does not toggle
- held flash moving to high beam does not double-toggle
- `nightToggled` not affected by test mode
- first generated on-phase is a full period, at any `nowMs`, across rollover
- hazards stay in phase, including when sides start one tick apart
- old `spotHoldMs` config key is honoured

On the bike:

- find the day/night bit, and confirm flash, high beam and indicator bits on the Discovery tab
- measure both Oxford units' sweep times and per-function currents
- measure the pods at each dial stage, including full-power inrush

## 9. Open items

1. ~~**Kit:** wires at the pod plug and between dial and pods; what the dial does at each stage;
   whether stages are reachable from the board. Decides §6.~~ **ANSWERED 2026-11-12: Branch A
   (§6.1).** Still open: blue's role (open circuit to black; see earlier spec §9.1 item 1); the
   exact PWM frequency and duty; yellow's input threshold
   (whether 3.3 V logic is enough) and its current at 5 V.
2. **Is day/night on CAN?** Decides which §4 path is used. The fallback covers either answer.
3. **Bench check of both Oxford units before making the harness.** Confirm wire functions. A
   buyer reports that the EL359's supplied diagram is wrong.
4. ~~**Fuse margin.**~~ **Superseded 2026-11-12.** The measured pods draw 3.2 A each at worst,
   so both pods move to the 15 A aux 3 circuit and feed A carries no pod (earlier spec §4.1.1).
5. **Compliance.** Whether the pods may be used as aux lights in this way, low at night alongside
   the headlight, is not established here. §3.1 gives an option if same-side darkening is wanted.
   **Added 2026-11-12:** the pods' DRL LEDs light whenever they are powered, so they are on at night
   Low. DRLs are generally expected to go out or dim when dipped beam is on. The user decides
   whether this is acceptable, or whether night Low should be dropped in favour of Off.
6. **Sweep time** against §5's flash limit.

## 10. Build order

1. **Firmware, not kit-gated:** §3–§5, §6's `AuxLevel` and §7. The HAL holds `Low` as off.
2. **After the kit:** choose the §6 branch, finish the aux stage, re-size R100, then lay out the
   board.
   **Revised 2026-11-12:** Branch A is chosen (§6.1). Next: the firmware's PWM HAL and
   `auxLowDuty` / `auxFullDuty`; the schematic's pod switches on feed B (re-rated for 6.4 A) and
   5 V PWM buffers; then re-size R100 and lay out the board.
