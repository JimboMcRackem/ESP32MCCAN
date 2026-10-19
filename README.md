# ESP32 MCCAN

ESP32 motorcycle lighting controller. It reads the bike's CAN bus and drives 12 on/off outputs.
You configure it from a phone over its own Wi-Fi network.

The firmware is one image. `tools/embed_web.py` embeds the web app from `data/` at build time,
so there is no separate filesystem flash.

Settings and the Wi-Fi password live in NVS (namespace `mccan`). A legacy `/config.json` is
migrated once and then deleted.

## Flashing over USB

```
PYTHONIOENCODING=utf-8 py -3.13 -m platformio run -e esp32 -t upload
```

This is the only flash. There is no `uploadfs`. Native tests run with `python -m platformio test -e native`.

The controller's Wi-Fi network is `MCCAN-XXXX` (XXXX is the last two bytes of the MAC address).
The default password is `mccan1234`, and the app nags until you change it.

## Releasing an update

1. Once only: `python tools/sign_update.py keygen`. The private key goes to `~/.mccan/update_key.pem`
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
4. After the update it restarts. A new image that does not run cleanly for about 5 s is rolled
   back to the previous one, and so is a power cut within 5 s of first boot.

## Recovering a forgotten password

Factory reset: hold the reset button (GPIO0, labelled BOOT on the dev board) for 10 s while the
controller is running. The LED blinks, then stays solid. Release it and the controller restarts
with defaults: password `mccan1234`, and settings back to defaults. A short press does nothing.

Holding the button at power-up enters the ESP32's USB flashing mode instead. That is harmless.

## Bring-up notes

- On the dev board, a serial terminal that asserts DTR without RTS can hold GPIO0 low through the
  auto-program circuit and trigger a factory reset after 10 s. Use a monitor that leaves DTR and
  RTS deasserted, or watch for it.
- Hold BOOT through "Connecting......" if the upload cannot connect.
