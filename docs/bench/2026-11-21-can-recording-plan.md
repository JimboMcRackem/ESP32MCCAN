# Experia CAN recording: speed, lean and day/night

**Why:** the firmware is waiting on four facts that only the bike can give:

1. **Speed.** Which message carries road speed, and where in it.
2. **km/h or mph.** Which unit that speed is in. The dash can show both.
3. **Lean.** Which message carries lean (roll) angle, and which way is positive.
4. **Day/night.** Which bit says the bike is in night mode.

Your log goes to Claude, who decodes it into Mapping tab settings.

**How the log gets decoded:** a signal is found by matching a change in the data
against the moment you made that change. So the rules are:

- do **one thing at a time**
- hold each state **still for 10 s**
- write down **when** you did it

**Kit:**
- the MrDIY CAN tool (GVRET firmware) on the bike's CAN bus
- a laptop with SavvyCAN
- a phone stopwatch
- this sheet and a pen
- for the lean test: a helper, and the bike **off** the paddock stand
- for the speed test: a rear paddock stand

---

## Markers

Steps are separated by a marker the decoder can find by itself: **the left
indicator on for 3 flashes, then off**. The bike sends the indicators in
message 0x102, which is already known, so each marker shows up clearly in the
log.

Make a marker at the start of every step below. Then leave the bike untouched
for 5 s before you begin the step.

---

## 0. Setup

1. Ignition **off**. Connect the tool to the bike's CAN bus and the laptop.
2. In SavvyCAN, open Connection → New Device Connection → Serial, pick the
   tool's COM port, and set speed 1000000. Set the CAN bitrate to 500 kbps.
   Tick **Listen Only** if SavvyCAN offers it.
3. Check the dash display mode and units. Write down how the bike switches
   between day and night: a menu setting, automatic (a light sensor), or
   with the headlight.
4. Clear the log. Start the phone stopwatch and SavvyCAN capture **together**.

## 1. Ignition (bonus: the "Run" signal)

| Time | Action |
|---|---|
| | Ignition **on**. Wait 15 s. |
| | Ignition **off**. Wait 10 s. |
| | Ignition **on** and leave it on. Wait 15 s. Do not ride. |

## 2. Day/night

Use whichever way the bike switches modes (from step 0.3).

| Time | Action |
|---|---|
| | Marker |
| | Switch to **night**. Hold 10 s. |
| | Switch to **day**. Hold 10 s. |
| | **Night** again. Hold 10 s. |
| | **Day** again. Hold 10 s. |

If the switching is automatic, cover the dash's light sensor (a cloth or your
hand) to get night, then uncover it for day. Note how long the dash took to
change.

If you can't make it change at all, write down **"no manual day/night"**. That
answer is useful too.

## 3. Lean (bike off the stand, helper holding it, ignition on)

Sit on the bike, or have the helper hold it from the side. Hold each lean for
10 s. You can estimate the angles roughly, but be honest with them, and use a
phone level app on the tank if you have one.

| Time | Action | Angle (est.) |
|---|---|---|
| | Marker (bike upright) | 0° |
| | Upright, still | 0° |
| | Lean **left** gently, hold | ___° |
| | Upright | 0° |
| | Lean **right** gently, hold | ___° |
| | Upright | 0° |
| | Lean **left** a bit further, hold | ___° |
| | Upright | 0° |
| | Lean **right** a bit further, hold | ___° |
| | Upright | 0° |

Also record about 10 s of the bike resting on its **side stand**, noting the
time. That gives the side-stand angle the speed gate has to ignore.

## 4. Speed and units (rear paddock stand, ignition on)

**Safety:** keep clear of the spinning wheel and chain, and use the lowest
power ride mode.

If the dash reads **0** with the rear wheel spinning, the speed comes from the
front wheel. In that case skip this step and do step 5.

| Time | Action | Dash reads |
|---|---|---|
| | Marker (wheel still) | 0 |
| | Wheel still, 10 s | 0 |
| | Hold a steady speed, 10 s | ___ km/h |
| | Hold a faster steady speed, 10 s | ___ km/h |
| | Back off to stop, wheel still 10 s | 0 |
| | **Switch the dash units to mph** in the menu | |
| | Marker | |
| | Hold a steady speed, 10 s | ___ mph |
| | Hold a faster steady speed, 10 s | ___ mph |
| | Stop, wheel still 10 s | 0 |
| | Switch the dash back to your normal units | |

Changing the dash units halfway shows whether the CAN number changes with the
display or always stays in one unit.

## 5. Only if the rear-stand test showed 0: short ride

Use a **separate** recording, with the laptop safe in a backpack and nothing
to touch while riding.

1. Start the capture, then make a marker.
2. On a quiet road, hold each of these dash speeds steadily for about 10 s:
   30, 50 and 70 (in whatever unit the dash is showing).
3. Note roughly when each one happened.
4. Stop safely, then stop the capture.

A few gentle bends during the ride also give real lean data, but you don't have
to make them.

## 6. Save

1. Stop the capture.
2. File → Save Log File, in **CSV** format (SavvyCAN's default is fine).
3. Name it `experia-speed-lean-daynight-YYYY-MM-DD.csv`.
4. Send the CSV along with a photo or copy of this sheet with the times and
   readings filled in.

---

## What comes back

You get Mapping tab settings for each of these:

| Item | What you'll get |
|---|---|
| Speed | Signal: ID, start bit, length, byte order, signed, scale, offset. The scale converts mph to km/h if needed. |
| Lean | Signal settings as for speed, with the sign set so that leaning right reads positive. |
| Day/night | A bit (ID and bit number) for the Day/night function |
| Run | Bonus: a bit, if one turns up |

Once mapped, check the Mapping tab's live values against the dash and against
a real lean before turning either feature on.
