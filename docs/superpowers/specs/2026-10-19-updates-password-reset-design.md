# Phone updates, Wi-Fi password and factory reset — design

Status: approved by the owner, 2026-10-19.
Builds on: `2026-07-29-esp32-mccan-lighting-firmware-design.md` (firmware), plan 2
(connectivity + web app), and `2026-10-17-emarked-module-redesign-design.md` (current board).

## 1. Why

The owner wants the controller to be something **other riders** can fit and live with, not
only a one-off build. Today, three things assume a builder with a laptop:

- **Updating needs USB and two separate flashes** (firmware, then the LittleFS image). The two
  can disagree; spec 2026-10-17 §11 records the protocol-version trap that follows from it.
- **Updating the web app wipes the settings.** `/config.json` lives in the same LittleFS image
  that `uploadfs` replaces, so every app update silently drops the rider's CAN bit assignments.
- **The Wi-Fi password is hard-coded** (`mccan1234` in `main.cpp`). Anyone who knows it, or
  reads it in the source, can join and change every setting.

The owner's words:
- "I want OTA update ability."
- "The app needs to be able to add a password". That means the Wi-Fi password.
- "I don't want anyone to be able to change settings and need a reset in case."
- Updates are done from the **phone through the app**.

## 2. Goals

1. **Update from the phone, over MCCAN-Setup.** One update file carries firmware and web app
   together. A failed or interrupted update can never leave the controller unbootable.
2. **Settings survive updates by default.** Wiping them is an explicit choice, offered as a
   tick-box on the Update screen.
3. **The rider sets the Wi-Fi password in the app.** The password is the access control:
   joining MCCAN-Setup is the only way to change anything.
4. **A physical factory reset** recovers a forgotten password. It restores every setting,
   including the password, to defaults.
5. **Only the owner's builds install.** Every update file is signed, and the controller refuses
   anything else.
6. Carry-over from plan 2: Discovery switches off when the phone that started it disconnects.

## 3. Non-goals (this round)

- **The controller checking for updates itself** over the rider's home Wi-Fi. This is the
  intended next step and §9 describes it. This round must not block it, and does not build it.
- **A release pipeline** (build, sign, publish). This round adds only a local signing script.
- **Other bikes.** The owner says "not key". The only obligation is to keep CAN decoding
  table-driven, as it already is, so another bike can later become a different table.
- A native phone app.
- ESP32 hardware Secure Boot or flash encryption. Both burn eFuses irreversibly; see §6.

## 4. Anti-goals: failure even if it "works"

- An update that can leave a bike with **no working indicators or brake light** after a
  dropped connection or a bad file.
- An update that **starts while the bike is being ridden**.
- A reset that a **knock, a jet-wash or a passer-by** can trigger.
- A rider **locked out for good** after mistyping a new password.
- Settings lost **as a side effect** of anything except an explicit reset.

## 5. What gets built

### 5.1 Web app inside the firmware
- The app is about 17 KB (`data/index.html`, `app.js`, `style.css`). Gzip it at build time and
  embed it in the firmware image; serve it from flash.
- LittleFS is no longer used for the app, and (§5.2) not for settings either.
- **Effect:** one image holds both halves. The A/B fallback (§5.3) protects the app too. Firmware
  and app cannot drift apart.
- `kProtocolVersion` and `PROTOCOL_VERSION` both stay. They now always match by construction; the
  banner only matters for a browser holding an old cached page.
- The `uploadfs` step disappears from the workflow and from every doc that mentions it.
- *Builder's call:* how the embedding is produced (a PlatformIO pre-build script generating a
  header, or `board_build.embed_files`), provided `data/` stays the editable source.

### 5.2 Settings in NVS
- The config JSON, the Wi-Fi password and (§9) future home-Wi-Fi credentials move to NVS
  (`Preferences`), in one namespace.
- NVS writes are atomic per key, which closes plan 2's "config write not atomic" item.
- **Migration:** on first boot of the new firmware, if NVS holds no config and
  `/config.json` exists in LittleFS, import it once. A rider who updates keeps their bits.
- *My call:* the partition table stays the `esp32dev` default: `nvs`, `otadata`, two 1.25 MB
  app slots, and the `spiffs` data partition left in place. Changing the partition table needs a
  USB flash, and the default already has everything OTA needs. Today's image (81.5 % of one
  slot) leaves about 240 KB, enough for the signature check and the embedded app.

### 5.3 Phone update (OTA)
- The app gets an **Update** screen:
  - current version
  - "Choose update file"
  - a **"Reset all settings to defaults"** tick-box, off by default
  - **Install**
- **Transport:** the browser uploads the file with an HTTP `POST` to the controller on port 80.
  The WebSocket stays for the existing protocol.
- **Write and switch:** the controller writes the image into the inactive app slot, checks the
  signature (§5.4), and only then marks that slot to boot. It replies, then restarts.
- **Fallback:** use ESP-IDF app rollback. The new image counts as valid only after it has
  started, brought up the AP and run the lighting loop for a few seconds; otherwise the
  bootloader returns to the previous slot on the next reset. The stock precompiled Arduino
  bootloader may not have rollback enabled.
  - **The plan's first task is a spike on the dev board** that proves rollback happens, using a
    deliberately crashing test image.
  - If the stock bootloader can't do it, ship a rollback-enabled bootloader. *My call.* This
    costs nothing extra, because every existing unit needs one USB flash anyway to receive
    OTA-capable firmware (see "First install" below). How that bootloader is produced is the
    builder's call.
  - Shipping without rollback is not an option (§4).
- **First install:** units already flashed (today, only the owner's dev board) get the new
  firmware once over USB, bootloader included if needed. The partition table is unchanged, so
  the old LittleFS partition and its `/config.json` survive for the migration in §5.2. Every
  update after that goes over the phone.
- **Versions:**
  - The firmware carries a monotonic integer build number and a display string. Both go in the
    signed part of the update file.
  - The Update screen shows the running display string.
  - The controller refuses a lower build number and allows the same one to be reinstalled.
    *My call:* a signed-but-old image is still refused, so a mistake or a replayed file can't
    downgrade a bike.
- **Server:** the existing synchronous `WebServer` on port 80 plus `WebSocketsServer` on 81.
  - The upload streams to flash inside the HTTP handler in chunks.
  - Short lighting-tick stalls per chunk are acceptable *because the interlock guarantees the
    bike is parked*. No separate task is required. *My call.*
  - An interrupted or oversized upload aborts the write, leaves the running firmware as it is,
    and reports why.
- **Parked interlock:** the controller refuses to start an update unless the CAN bus is stale
  **or** `LogicalState::kickstand` (the CAN-decoded input, not a pin) reads down. It answers with
  a reason the app shows.
  - "Stale" is the existing > 500 ms rule (spec 2026-10-17 §6.2), reused, not a new timeout.
  - A bench board with no bus is therefore always open. That is intended: no bike means nothing
    is being ridden.
  - *My call,* because Run's meaning in a parked state is still open (spec 2026-10-17 §9.3.5).
    Revisit once that is confirmed on the bike.
- **Lights during the upload:** the lighting tick keeps running as far as the upload allows. The
  restart takes outputs dark for about a second, which the interlock makes acceptable.
- If the tick-box was set, the new firmware erases the settings namespace before first use, and
  the app reconnects to the default password.

### 5.4 Signed updates
- The update file is the firmware image plus an ECDSA P-256 signature over its SHA-256.
  *My call:* mbedTLS is already in the core, so this costs no new library.
- The public key is compiled into the firmware. The private key stays with the owner, outside
  the repo, and is never committed.
- A script in the repo (`tools/sign_update.py` or similar) turns a PlatformIO build into a
  signed update file.
- **Keys:**
  - The same script has a `keygen` mode. The owner runs it once, and the private key is written
    outside the repo, in the owner's home directory, never committed.
  - The public key is compiled in from a file that *is* committed.
  - Native tests use a separate **test key pair** committed under `test/`, clearly named as
    test-only, so signature verdicts are tested on fixed vectors. The firmware build never
    embeds the test key.
- *Builder's call:* the file layout, as long as the signature and the signed header (build
  number, display string, image length) can't be separated from the image they cover.
- An unsigned file, a wrong signature, or a truncated upload is refused, and the running
  firmware is untouched.
- **Limit, stated plainly:** this stops anyone pushing firmware over Wi-Fi. It does **not** stop
  someone with the board on a bench and a USB cable. That would need Secure Boot (§6).

### 5.5 Wi-Fi password
- **Settings → Wi-Fi password:** a new-password field and a confirm field.
- 8–63 characters, as WPA2 requires. Saving with a mismatch or a short password is refused in
  the app.
- On save, the controller stores the password and restarts the AP, so the phone drops and
  rejoins with the new password. The app says so before it happens.
- **Default:** `mccan1234`.
- **No extra PIN or "current password" step.** Joining the AP *is* the gate, for the password
  change and the update alike. Whoever is on the network already used the current password.
- **SSID gets a per-unit suffix** from the MAC (e.g. `MCCAN-3F2A`), so two bikes at a meet
  don't collide. *My call.*
- While the default password is in use, the app shows a persistent banner: "Change the default
  Wi-Fi password." *My call.*

### 5.6 Factory reset button
- **Trigger:** hold the button for 10 s while the controller is running. Erase the settings
  namespace and restart. A short press does nothing.
  - The hold must be continuous. Any release longer than a debounce interval restarts the count;
    the interval is the builder's call.
  - The reset erases the settings namespace only. The SSID suffix is derived from the MAC and is
    unaffected.
- **Pin:** GPIO0 (`BOOT_N`), read only after boot.
  - Holding it at **power-up** enters the ROM USB-flashing mode instead. That is harmless (the
    controller just waits) and is why the reset is a hold while running, not a hold at power-on.
- **Feedback:**
  - status LED, GPIO13 on the new board: fast blink once the 10 s is reached
  - serial log line
  - after the restart, the app's default-password banner
- **Dev board today:** the existing BOOT button works as-is, so this is testable now.
- **New board (hardware, joins the kit-gated list):** a 2-pin connector in parallel with SW1
  for the owner's IP67 inset push-button, with ESD protection and an RC filter on the line. Long
  wire to a handlebar-area switch is an ESD and noise entry into a strap pin. Hardware detail is
  decided in the board plan, not here.

### 5.7 Discovery off on disconnect (plan 2 carry-over)
- Discovery remembers the client that turned it on, and `onDisconnect` clears it for that
  client, mirroring test mode.

## 6. Constraints

- Lighting behaviour, test mode and the protocol's existing messages are unchanged. Native tests
  stay green, and the new domain logic gets native tests too: interlock decision, password
  validation, reset-hold timing, signature-check verdicts on fixed vectors, config migration.
- **No eFuse is burned by anything in this design.** Secure Boot, flash encryption and the
  flash-voltage fuse remain the owner's separate, irreversible decisions.
- Flash budget: stay inside one 1.25 MB app slot with headroom for §9's HTTPS client. Report the
  measured size.

## 7. Left to the builder

- File and module layout, protocol message names for the new screens, and the shape of the
  version string (but show it on the Update screen).
- How the upload streams to flash while keeping the lighting tick alive.
- Exact LED blink pattern.

## 8. Open, owner's to decide later

- What "parked" should mean once spec 2026-10-17 §9.3.5 (Run in a parked state) is settled.
- Whether Secure Boot is wanted for units sold to others.

## 9. Concept, not this round: the controller fetches its own updates

- The rider adds their home Wi-Fi in the app once.
- When the bike is switched on in range (typically the garage), the controller joins it as a
  station alongside the AP and checks a release feed over HTTPS.
- It downloads a newer signed file into the spare slot in the background.
- The app then says "Update available (vX): install?", and the status LED can show a distinct
  pattern.
- Installing still needs the rider's tap and the parked interlock.
- This round prepares for it in three ways: the NVS namespace has room for credentials, the
  update file is self-contained and signed, and the install path is the same one the manual
  upload uses.
