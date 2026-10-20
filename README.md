# ESP32 MCCAN

ESP32 motorcycle lighting controller. It reads the bike's CAN bus and drives 12 on/off outputs.
You configure it from a phone over its own Wi-Fi network.

The firmware is one image. `tools/embed_web.py` embeds the web app from `data/` at build time,
so there is no separate filesystem flash.

Settings and the Wi-Fi password live in NVS (namespace `mccan`). A legacy `/config.json` is
migrated once and then deleted, but only on a unit that still has the old partition table (see
below).

## Flashing over USB

Before the first USB flash of this firmware:

1. `python -m pip install cryptography` (needed by `tools/sign_update.py`).
2. `python tools/sign_update.py keygen`, then commit `src/domain/update_pubkey.h`. Firmware built
   with the all-zero placeholder key refuses every phone update until it is flashed over USB
   again.
3. Export your settings from the app's Backup tab. This firmware uses the `min_spiffs.csv`
   partition table (bigger app slots), so the old `/config.json` is not carried over. Import the
   backup after flashing.

```
PYTHONIOENCODING=utf-8 py -3.13 -m platformio run -e esp32 -t upload
```

This is the only flash. There is no `uploadfs`. Native tests run with `python -m platformio test -e native`.

The controller's Wi-Fi network is `MCCAN-XXXX` (XXXX is the last two bytes of the SoftAP MAC
address, which differs from the base MAC printed on module labels).
The default password is `mccan1234`, and the app nags until you change it.

## Releasing an update

1. Once only, before the first USB flash: `python tools/sign_update.py keygen`. The private key goes to `~/.mccan/update_key.pem`
   and the public half to `src/domain/update_pubkey.h`, which is built into the firmware.
   **Back up the key.** If it is lost, units in the field can only be updated over USB.
2. Bump `kBuildNumber` and `kVersionString` in `src/version.h`.
3. Build: `PYTHONIOENCODING=utf-8 py -3.13 -m platformio run -e esp32`
4. Sign:
   ```
   python tools/sign_update.py sign --key ~/.mccan/update_key.pem --bin .pio/build/esp32/firmware.bin --out mccan-<version>.mcup
   ```

The `.mcup` format is documented at the top of `tools/sign_update.py`.

## Installing an update from the phone

1. Join the `MCCAN-XXXX` network and open the app.
2. Go to the Device tab and choose the `.mcup` file.
3. The controller refuses an older build, and refuses any update while the bike is not parked.
4. After the update it restarts once the bike reads parked. The new image marks itself good
   after it has run for about 5 s with the Wi-Fi network up. If it crashes or is power-cycled
   before that, the next start goes back to the previous image. An image that hangs stays until
   a power cycle, and one that runs but behaves wrongly is kept: install a fixed update.

## Recovering a forgotten password

Factory reset: hold the reset button (GPIO0, labelled BOOT on the dev board) for 10 s while the
controller is running, then **release it within 5 s**. That erases the settings, and the
controller restarts with defaults (password `mccan1234`) as soon as the bike reads parked. A short
press does nothing. If the button is still held 5 s after the 10 s mark, the reset is cancelled;
release it and start a new 10 s hold to try again. The lamps keep working throughout.

Feedback: on the MCCAN board the status LED (GPIO13) fast-blinks at the 10 s mark (release now),
goes solid once the settings are erased, and goes off if cancelled. The dev board has no LED on
GPIO13: watch the serial log instead (`reset button held 10 s: release within 5 s ...`,
`factory reset: settings erased`).

Holding the button at power-up enters the ESP32's USB flashing mode instead. That is harmless.

## Bring-up notes

- On the dev board, a serial terminal that asserts DTR without RTS can hold GPIO0 low through the
  auto-program circuit. Held, it arms the reset at 10 s and cancels it at 15 s; it never erases
  unless the line is released inside that window. Use a monitor that leaves DTR and RTS
  deasserted.
- Hold BOOT through "Connecting......" if the upload cannot connect.
