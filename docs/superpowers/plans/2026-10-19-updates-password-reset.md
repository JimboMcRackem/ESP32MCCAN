# Phone Updates, Wi-Fi Password and Factory Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A rider updates firmware and web app from the phone with one signed file. Settings
survive updates unless reset is chosen. The rider sets the Wi-Fi password in the app. A 10 s
button hold restores defaults.

**Architecture:**
- **Native-testable logic lives in `src/domain/`:** update-file parsing and streaming
  verification, SHA-256, P-256 signature check, password rules, reset-hold timing, protocol
  messages.
- **ESP32-only glue lives in `src/hal/`:** NVS storage, the embedded web app, the HTTP upload
  route writing through the Arduino `Update` library, and ESP-IDF app rollback.
- **A Python tool signs releases.**
- The web app is gzipped into the firmware at build time, so the LittleFS image goes away.

**Tech Stack:**
- PlatformIO: `espressif32` (Arduino core 3.3.4) and `native` (Unity).
- ArduinoJson 7, `kmackay/micro-ecc@1.0.0`.
- Python 3 with `cryptography` for the signing tool.

**Spec:** `docs/superpowers/specs/2026-10-19-updates-password-reset-design.md` (approved).

**Branch:** `plan5-updates`, cut from `main`, in worktree `D:/Projects/ESP32MCCAN-upd`.

## Global Constraints

- **Never burn an eFuse.** No task runs `espefuse.py` or enables Secure Boot or flash
  encryption.
- **The owner's private key** lives at `~/.mccan/update_key.pem` and is never committed. Only
  the test key under `test/keys/` may be in the repo, and the firmware never embeds it.
- **Commands:**
  - Native tests: `python -m platformio test -e native`. The 95 existing cases stay green.
  - ESP32 build: `PYTHONIOENCODING=utf-8 py -3.13 -m platformio run -e esp32`.
  - Signing tool: `python tools/sign_update.py ...`, after `python -m pip install cryptography`
    if it is missing.
- **The assistant cannot reach COM ports.** Every flash and serial step is the owner's, typed
  as `! <command>`. The upload form is `! PYTHONIOENCODING=utf-8 py -3.13 -m platformio run -e
  esp32 -t upload --upload-port COM3`.
- **Flash budget:** the image must fit one 1,966,080-byte app slot (`min_spiffs.csv`, owner's
  decision 2026-10-20; was 1,310,720 B on the `esp32dev` default). Report the measured size in
  Task 8. Stop and rule if it exceeds 1,769,472 bytes (90 % of the slot).
- **`kProtocolVersion`** (`src/domain/web_protocol.h`) and **`PROTOCOL_VERSION`**
  (`data/app.js`) both become **4** in the same commit.
- **Default Wi-Fi password:** `mccan1234`. **SSID:** `MCCAN-` followed by the last two MAC
  bytes as uppercase hex.
- **Git:** stage files by name, never `git add -A`. Commits end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Update file format (`.mcup`): fixed here, used by Tasks 2, 3, 8 and 9

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | magic `MCUP` (ASCII) |
| 4 | 2 | format version, u16 LE = 1 |
| 6 | 2 | reserved, 0 |
| 8 | 4 | build number, u32 LE |
| 12 | 4 | image length, u32 LE, > 0 |
| 16 | 32 | display version, ASCII, NUL-padded, at most 31 chars, must contain a NUL |
| 48 | 16 | reserved, 0 |
| 64 | image length | `firmware.bin` exactly as PlatformIO builds it |
| 64 + len | 64 | ECDSA P-256 signature, r‖s, each 32 bytes big-endian, over SHA-256(bytes 0 .. 64+len-1) |

The build number and display version come from `src/version.h`. This is their only source;
the signing tool reads them from it.

## Review Focus

1. **Phone walks out of range mid-upload.** Expected: the running firmware is untouched, and
   the next boot is the old image. Test `test_truncated_upload_fails` (Task 3).
2. **Rider picks the raw `firmware.bin`, or any wrong file, instead of the `.mcup`.** Expected:
   refused before a byte is written to flash. Test `test_raw_firmware_bin_rejected` (Task 3).
3. **Reinstalling the same release** (a rider re-doing an update) must work; an older release
   must not. Tests `test_same_build_accepted` and `test_older_build_refused` (Task 3).
4. **Passwords at the edges:** exactly 8 and 63 chars, a trailing space, `é`, an empty field.
   Expected: 8/63 and the space accepted; `é` and empty refused, each with its reason. Test
   `test_password_boundaries` (Task 4).
5. **A bouncing or interrupted button press.** 20 ms contact bounce still counts as one hold. A
   60 ms release restarts the count. Holding again after firing does not fire twice. Tests
   `test_bounce_ignored`, `test_release_restarts_count`, `test_fires_once_per_hold` (Task 4).

---

### Task 1: Rollback spike on the dev board

Proves that an OTA image which crashes before confirming itself is rolled back by the stock
bootloader. Throwaway project; nothing from it is merged except the result line.

**Files:**
- Create: `spike/rollback/platformio.ini`, `spike/rollback/src/main.cpp`. Deleted again in
  Step 5.

- [ ] **Step 1: Write the spike firmware.**
  - Same `[env]` platform and board as the root `platformio.ini`.
  - SoftAP `MCCAN-SPIKE` with password `spike1234`.
  - `WebServer` route `POST /update` (multipart): each chunk goes to `Update.write`, then
    `Update.end(true)` and `ESP.restart()`.
  - `extern "C" bool verifyRollbackLater() { return true; }`.
  - After 5 s of `loop()`, call `esp_ota_mark_app_valid_cancel_rollback()` once and print
    `VALID`.
  - On boot, print `SPIKE build=<BUILD>` where `-DBUILD=` is a build flag.
  - When built with `-DCRASH`, call `abort()` in `setup()` before marking valid.
- [ ] **Step 2: Build three binaries, `BUILD=1`, `BUILD=2`, and `BUILD=3 CRASH`, and copy them
  to the scratchpad.**
- [ ] **Step 3: Owner flashes build 1 over USB.** Then the owner joins a laptop to
  `MCCAN-SPIKE` and runs `curl -F update=@build2.bin http://192.168.4.1/update`.
  - Expected serial: `SPIKE build=2`, then `VALID`.
  - Then upload `build3crash.bin`. Expected: one abort, then `SPIKE build=2` again, with no
    boot loop.
- [ ] **Step 4: Record the outcome in the ledger.**
  - If rollback happened, the stock bootloader is used and Task 8 relies on it.
  - If it did not, stop. The controller rules on producing a rollback-enabled bootloader (spec
    §5.3) before Task 8.
- [ ] **Step 5: Delete `spike/` and commit nothing from it.**

### Task 2: Crypto primitives and the signing tool

**Files:**
- Create: `src/domain/sha256.h`, `src/domain/sha256.cpp`, `src/domain/signature.h`,
  `src/domain/signature.cpp`
- Create: `tools/sign_update.py`, `src/version.h`, `src/domain/update_pubkey.h`
- Create: `test/keys/test_update_key.pem`, `test/test_crypto/test_crypto.cpp`,
  `test/test_update_image/vectors.h`
- Modify: `platformio.ini`: add `kmackay/micro-ecc@1.0.0` to both envs' `lib_deps`.

**Interfaces:**
- Produces:
  - `class Sha256 { public: Sha256(); void update(const uint8_t* d, size_t n); void finish(uint8_t out[32]); };`
  - `bool verifyP256(const uint8_t pub[64], const uint8_t digest[32], const uint8_t sig[64]);`
  - `src/version.h`: `constexpr uint32_t kBuildNumber = 1;` and
    `constexpr const char* kVersionString = "1.0.0";`
  - `src/domain/update_pubkey.h`: `constexpr uint8_t kUpdatePubKey[64] = {...};`, the raw X‖Y
    of the owner's public key. It holds an all-zero placeholder until Task 10, and a zero key
    must make every verify fail.
  - `vectors.h`:
    - `kTestPubKey[64]`
    - `kImage[1000]` (byte i = (i*7) & 0xFF)
    - `kMcupBuild7[]` with its length, display string `"test-7"`
    - `kMcupBuild3[]` with its length, display string `"test-3"`
- Tool CLI:
  - `sign_update.py keygen [--key PATH] [--pubkey-header PATH]`. It refuses to overwrite an
    existing key. Defaults are `~/.mccan/update_key.pem` and `src/domain/update_pubkey.h`.
  - `sign_update.py sign --key PATH --bin PATH --out PATH`. It reads build and version from
    `src/version.h`.
  - `sign_update.py testvectors`. It writes `vectors.h` using `test/keys/test_update_key.pem`,
    creating that key if absent.

- [ ] **Step 1: Write failing tests in `test/test_crypto/test_crypto.cpp`.**
  - `test_sha256_empty`: digest = `e3b0c442...b855` (FIPS 180-4).
  - `test_sha256_abc`: `ba7816bf...15ad`.
  - `test_sha256_two_block`: `"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"` →
    `248d6a61...06c1`.
  - `test_sha256_split_updates`: feeding `"abc"` as `"a"` + `"bc"` gives the same digest as in
    one call.
  - `test_verify_good_signature`: digest of `kMcupBuild7[0 .. len-65]`, verified with
    `kTestPubKey` against the last 64 bytes, is true.
  - `test_verify_flipped_bit`: same, with one image byte XOR 0x01, is false.
  - `test_verify_zero_key_fails`: an all-zero public key is false.
- [ ] **Step 2: Run `python -m platformio test -e native -f test_crypto`.** Expected: FAIL to
  compile, because the headers are missing.
- [ ] **Step 3: Implement.**
  - `Sha256`: FIPS 180-4, portable C++, no platform headers.
  - `verifyP256`: wraps
    `uECC_verify(pub, digest, 32, sig, uECC_secp256r1())`, and returns false first if the key
    is all zero.
  - `sign_update.py`: uses `cryptography`'s `ec.SECP256R1` and `utils.decode_dss_signature` to
    get raw r‖s. The header layout is exactly the table above.
  - Run `testvectors` and commit its output.
- [ ] **Step 4: Run the native tests.** Expected: 7 new cases PASS, all 95 old ones PASS.
- [ ] **Step 5: Commit** the files listed under **Files** above, as
  `feat(update): SHA-256, P-256 verify and the signing tool`.

### Task 3: Update receiver (stream, policy, verdict)

**Files:**
- Create: `src/domain/update_image.h`, `src/domain/update_image.cpp`,
  `test/test_update_image/test_update_image.cpp`

**Interfaces:**
- Consumes: `Sha256`, `verifyP256`, the `vectors.h` blobs.
- Produces:

```cpp
enum class UpdateError { None, Truncated, BadMagic, BadFormat, BadLength,
                         Downgrade, TooLarge, ExtraBytes, BadSignature, WriteFailed };
const char* updateErrorText(UpdateError e);
struct UpdateHeader { uint32_t build; uint32_t imageLen; char display[32]; };
class IUpdateSink { public: virtual ~IUpdateSink() = default;
  virtual bool begin(uint32_t imageLen) = 0;
  virtual bool write(const uint8_t* d, size_t n) = 0; };
class UpdateReceiver {
 public:
  UpdateReceiver(uint32_t runningBuild, uint32_t slotBytes,
                 const uint8_t* pubKey64, IUpdateSink& sink);
  bool feed(const uint8_t* data, size_t len);   // false once errored; never writes after an error
  UpdateError finish();                          // verdict once the upload has ended
  UpdateError error() const;
  const UpdateHeader* header() const;            // nullptr until 64 header bytes are in
};
bool parkedForUpdate(bool canStale, bool kickstandDown);   // true if either
```

`updateErrorText` texts, used verbatim:

| Error | Text |
|---|---|
| Truncated | "The upload was cut short. Nothing was changed." |
| BadMagic | "That is not an MCCAN update file (.mcup)." |
| BadFormat | "This update file needs newer firmware to install." |
| BadLength | "The update file is damaged." |
| Downgrade | "This update is older than the installed firmware." |
| TooLarge | "This update is too large for this controller." |
| ExtraBytes | "The update file is damaged." |
| BadSignature | "This update is not signed by MCCAN. Nothing was changed." |
| WriteFailed | "Writing the update failed. Nothing was changed." |
| None | "" |

The parked refusal text, used by Task 8: "Park the bike first: kickstand down or ignition off."

**Receiver behaviour:**
- **Header:** buffers 64 bytes and validates magic, then format version, then length and NUL.
- **Policy:** `build < runningBuild` → Downgrade; `imageLen > slotBytes` → TooLarge.
- **Writing:** only after the header passes does it call `sink.begin(imageLen)`. It streams
  exactly `imageLen` bytes to `sink.write` while hashing header + image, then buffers 64
  signature bytes.
- **Extra bytes:** any byte beyond the signature → ExtraBytes.
- **`finish()`:** returns Truncated if short, else BadSignature unless `verifyP256` passes,
  else None.
- **Failing sink:** a `false` from either sink call → WriteFailed.

- [ ] **Step 1: Write failing tests.** Use a `FakeSink` that records `begin` calls and
  concatenates written bytes.
  - `test_valid_file_streams_image_and_verifies`: feed `kMcupBuild7` in 37-byte chunks with
    runningBuild 5. Expected: `finish()==None`, sink saw `begin(1000)`, written == `kImage`,
    `header()->build==7`, display `"test-7"`.
  - `test_same_build_accepted`: runningBuild 7 → None.
  - `test_older_build_refused`: `kMcupBuild3` with runningBuild 7 → `error()==Downgrade`, sink
    `begin` never called.
  - `test_too_large_refused`: slotBytes 999 → TooLarge, no `begin`.
  - `test_raw_firmware_bin_rejected`: feed 64 bytes starting `0xE9` (ESP image magic) → BadMagic,
    no `begin`.
  - `test_truncated_upload_fails`: feed all but the last 10 bytes → `finish()==Truncated`.
  - `test_extra_bytes_fail`: append one byte → ExtraBytes.
  - `test_tampered_image_fails`: flip a byte at offset 64+500 → `finish()==BadSignature`.
  - `test_bad_format_version`: set bytes 4..5 to 2 → BadFormat.
  - `test_zero_length_rejected`: imageLen 0 → BadLength.
  - `test_display_without_nul_rejected`: 32 non-NUL display bytes → BadLength.
  - `test_sink_failure_reported`: `FakeSink::write` returns false → WriteFailed, and `feed`
    returns false.
  - `test_parked_rule`: (stale, kick) → (F,F) false, (T,F) true, (F,T) true, (T,T) true.
  - Tampered and edited blobs must be copied from `vectors.h`, never edited in place.
- [ ] **Step 2: Run `-f test_update_image`.** Expected: FAIL to compile.
- [ ] **Step 3: Implement `update_image.cpp` as specified above.**
- [ ] **Step 4: Run the native tests.** Expected: all PASS.
- [ ] **Step 5: Commit** as `feat(update): streaming receiver with signature and version policy`.

### Task 4: Password rules, SSID, reset hold, config source

**Files:**
- Create: `src/domain/wifi_settings.h/.cpp`, `src/domain/reset_hold.h/.cpp`,
  `test/test_device_settings/test_device_settings.cpp`

**Interfaces:**
- Produces:

```cpp
constexpr const char* kDefaultWifiPassword = "mccan1234";
enum class PasswordCheck { Ok, TooShort, TooLong, BadChar };
PasswordCheck checkWifiPassword(const std::string& p);  // 8..63 bytes, each 0x20..0x7E
const char* passwordCheckText(PasswordCheck c);
//   TooShort "Wi-Fi password must be at least 8 characters."
//   TooLong  "Wi-Fi password must be at most 63 characters."
//   BadChar  "Wi-Fi password may only use plain letters, digits, spaces and symbols."
std::string apSsid(const uint8_t mac[6]);               // "MCCAN-" + %02X mac[4] + %02X mac[5]
enum class ConfigSource { Nvs, Legacy, Defaults };
ConfigSource pickConfigSource(bool nvsHasConfig, bool legacyHasConfig);  // Nvs wins, then Legacy
class ResetHold {
 public:
  static constexpr uint32_t kHoldMs = 10000;
  static constexpr uint32_t kDebounceMs = 50;
  bool update(bool pressed, uint32_t nowMs);   // true exactly once per completed hold
};
```

**ResetHold rule:**
- A hold starts at the first pressed sample.
- A release counts only once it has lasted at least `kDebounceMs`. It then ends the hold, and
  re-arms firing.
- The hold fires when `now - start >= kHoldMs` while pressed.

- [ ] **Step 1: Write failing tests.**
  - `test_password_boundaries`:
    - 7 chars → TooShort
    - 8 → Ok
    - 63 → Ok
    - 64 → TooLong
    - `"password "` (trailing space) → Ok
    - `"pässword1"` (UTF-8) → BadChar
    - `""` → TooShort
  - `test_ssid_from_mac`: `{0x24,0x6F,0x28,0xAB,0x3F,0x2A}` → `"MCCAN-3F2A"`, and
    `{...,0x00,0x0A}` → `"MCCAN-000A"`.
  - `test_config_source`: (T,T)→Nvs, (T,F)→Nvs, (F,T)→Legacy, (F,F)→Defaults.
  - `test_short_press_does_nothing`: pressed 0..3000 ms in 10 ms samples, then released → never
    fires.
  - `test_fires_at_ten_seconds`: pressed from t=1000 → false at 10999, true at 11000.
  - `test_bounce_ignored`: pressed from 0, released for 20 ms at t=4000 → fires at 10000.
  - `test_release_restarts_count`: released for 60 ms at t=4000, pressed again from 4060 → no
    fire before 14060, fires at 14060.
  - `test_fires_once_per_hold`: held to 20000 → exactly one true. After a 100 ms release and a
    new 10 s hold → a second true.
- [ ] **Step 2: Run `-f test_device_settings`.** Expected: FAIL to compile.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the native tests.** Expected: all PASS.
- [ ] **Step 5: Commit** as `feat(device): password rules, per-unit SSID, reset-hold timing`.

### Task 5: Protocol v4 (password, device info) and the version banner

**Files:**
- Modify: `src/domain/web_protocol.h/.cpp`, `test/test_web_protocol/test_web_protocol.cpp`,
  `data/app.js:8`

**Interfaces:**
- Consumes: `checkWifiPassword`, `passwordCheckText`.
- Produces:
  - `kProtocolVersion = 4`.
  - `ProtocolAction` gains `bool setWifiPassword = false; std::string wifiPasswordOut;`.
  - `struct DeviceInfo { std::string version; uint32_t build; std::string ssid; bool defaultPassword; };`
  - `std::string deviceInfoMessage(const DeviceInfo& d);`

**Wire format:**
- Inbound `{"type":"set_wifi_password","password":"<p>"}`. If the password fails the check,
  `error` = `passwordCheckText(...)` and `setWifiPassword` stays false.
- Outbound
  `{"type":"device_info","protocolVersion":4,"version":"1.0.0","build":1,"ssid":"MCCAN-3F2A","defaultPassword":true}`.

- [ ] **Step 1: Write failing tests.**
  - `test_set_wifi_password_valid`: `"newpass99"` → `setWifiPassword`, out == `"newpass99"`,
    no error.
  - `test_set_wifi_password_short_refused`: `"short"` → error equals the TooShort text, and
    `setWifiPassword` is false.
  - `test_set_wifi_password_missing_field`: no `"password"` key → error non-empty, flag false.
  - `test_device_info_message`: parse the output with ArduinoJson and assert all six fields.
  - `test_protocol_version_is_4`.
- [ ] **Step 2: Run `-f test_web_protocol`.** Expected: the new tests FAIL.
- [ ] **Step 3: Implement it, and set `PROTOCOL_VERSION = 4` in `data/app.js`.**
  - Update the comment above `kProtocolVersion`. The app now ships inside the firmware, so the
    banner only fires for a stale cached page.
- [ ] **Step 4: Run the native tests.** Expected: all PASS.
- [ ] **Step 5: Commit** as `feat(protocol): v4 adds set_wifi_password and device_info`.

### Task 6: Settings in NVS with one-time migration and pending reset

**Files:**
- Modify: `src/hal/storage.h`, `src/hal/storage.cpp`

**Interfaces:**
- Consumes: `pickConfigSource`, `kDefaultWifiPassword`.
- Produces:

```cpp
namespace storage {
  bool begin();                                  // see order below
  std::string readConfig();                      // "" if none
  bool writeConfig(const std::string& json);
  std::string readWifiPassword();                // kDefaultWifiPassword if none stored
  bool writeWifiPassword(const std::string& p);
  bool isDefaultWifiPassword();
  void requestResetOnNextBoot();                 // sets reset_pend = 1
  void eraseAll();                               // erases the whole "mccan" namespace
}
```

**NVS layout:**
- Namespace `mccan` via `Preferences`.
- Keys:
  - `config`: blob (`putBytes`; the JSON is not limited to NVS string size)
  - `wifi_pass`: string
  - `reset_pend`: u8

**`begin()` order:**
1. Open the namespace.
2. If `reset_pend` is 1, `eraseAll()`.
3. Mount LittleFS with `LittleFS.begin(false)`. **Never format.** If mounting fails, skip
   migration.
4. If `pickConfigSource(nvsHas, legacyHas) == Legacy`, copy `/config.json` into `config`.
5. In every case where `/config.json` exists, `LittleFS.remove("/config.json")`. A later reset
   must not bring old settings back.
6. `LittleFS.end()`.

- [ ] **Step 1: Implement.**
  - There is no native test: `src/hal/` is excluded from the native build. Its decision logic
    was tested in Task 4.
- [ ] **Step 2: ESP32 build.** Expected: SUCCESS.
- [ ] **Step 3: Commit** as `feat(storage): settings move to NVS; legacy config.json migrates once`.

### Task 7: Web app embedded in the firmware

**Files:**
- Create: `tools/embed_web.py` (PlatformIO pre-script)
- Modify: `platformio.ini` (`[env:esp32]`: `extra_scripts = pre:tools/embed_web.py`),
  `.gitignore` (add `src/hal/web_assets.h`), `src/hal/web_server.cpp`

**Interfaces:**
- Produces: the generated `src/hal/web_assets.h`:

```cpp
struct WebAsset { const char* path; const char* mime; const uint8_t* gz; size_t len; };
static const WebAsset kWebAssets[] = { {"/index.html","text/html",...}, {"/app.js","application/javascript",...}, {"/style.css","text/css",...} };
```

**Requirements:**
- The script gzips every file in `data/` with `mtime=0`, so output is byte-identical
  run-to-run, and rewrites the header only when its content changes.
- `web_server.cpp` serves every asset with `Content-Encoding: gzip` via `send_P`.
- `/` and every unknown path, for the captive portal, serve `/index.html`.
- All LittleFS use and the "web filesystem not loaded" diagnostic leave `web_server.cpp`.

- [ ] **Step 1: Write the script and the serving code.**
- [ ] **Step 2: ESP32 build twice.** Expected: SUCCESS both times, and the second build does not
  rewrite `web_assets.h` (same mtime).
- [ ] **Step 3: Native tests.** Expected: all PASS.
- [ ] **Step 4: Commit** as `feat(web): the app is embedded in the firmware; no LittleFS image`.

### Task 8: OTA route, rollback confirmation, and `main.cpp` wiring

**Files:**
- Modify: `src/hal/web_server.h/.cpp`, `src/main.cpp`

**Interfaces:**
- Consumes: `UpdateReceiver`, `IUpdateSink`, `parkedForUpdate`, `updateErrorText`, `storage::*`,
  `apSsid`, `ResetHold`, `deviceInfoMessage`, `kBuildNumber`, `kVersionString`,
  `kUpdatePubKey`.
- Produces, in `WebServerHal`:
  - `bool begin(const char* ssid, const char* password);` (unchanged)
  - `void restartAp(const char* ssid, const char* password);`
  - `void onUpdate(std::function<bool()> parked, std::function<void(bool resetSettings)> committed);`

**`POST /update?reset=0|1` (multipart, field `update`):**
- **`UPLOAD_FILE_START`:** if `!parked()`, refuse. Otherwise construct the receiver with
  `kBuildNumber`, `esp_ota_get_next_update_partition(nullptr)->size` and `kUpdatePubKey`, and
  an `EspUpdateSink` (`Update.begin`/`Update.write`).
- **On end:**
  - If `finish()==None` and `Update.end(true)` succeeds, reply `200 {"ok":true}` and call
    `committed(reset)`.
  - Otherwise call `Update.abort()` and reply
    `400 {"ok":false,"error":"<text>"}`, where the text is `updateErrorText(...)` or the parked
    text.
- **Upload aborted by the client:** `Update.abort()`.

**`main.cpp`:**
- **Rollback confirmation:**
  - `extern "C" bool verifyRollbackLater() { return true; }`.
  - Call `esp_ota_mark_app_valid_cancel_rollback()` once, the first time `millis() >= 5000`
    with the AP up and `loop()` running.
  - On a USB-flashed image this call is harmless.
- **`committed(reset)`:** if reset, `storage::requestResetOnNextBoot()`. Then restart 500 ms
  later, from `loop()` and not inside the handler.
- **`parked`:** `parkedForUpdate(g_can.stale(now), g_can.evaluate(g_cfg, now).kickstand)`.
- **AP:** SSID is `apSsid(mac)`, from `esp_read_mac(mac, ESP_MAC_WIFI_SOFTAP)`. The password is
  `storage::readWifiPassword()`. Remove `kApSsid` and `kApPass`.
- **`setWifiPassword`:**
  - `storage::writeWifiPassword`, then broadcast `deviceInfoMessage`.
  - 1000 ms later, `g_web.restartAp(...)` with the new password.
  - Do **not** restart the controller.
- **`sendConfig`:** also send `deviceInfoMessage` to that client.
- **Discovery owner:** remember which client enabled Discovery; `onDisconnect` of that client
  sets `g_discovery = false`.
- **Reset button:**
  - GPIO0 `INPUT_PULLUP`, pressed = LOW, sampled every loop into `ResetHold`.
  - On fire: blink `kLedStatPin` at 10 Hz for 1 s, then `storage::eraseAll()`, then
    `ESP.restart()`.
- **Storage:** `storage::begin()` stays before `configFromJson`.

- [ ] **Step 1: Implement.**
- [ ] **Step 2: ESP32 build.** Expected: SUCCESS. Record the image size in bytes from
  `.pio/build/esp32/firmware.bin` and check it against the flash budget.
- [ ] **Step 3: Native tests.** Expected: all PASS.
- [ ] **Step 4: Commit** as `feat(update): phone OTA route, rollback confirmation, password and reset wiring`.

### Task 9: App screens — Device tab, password, update, banner

**Files:**
- Modify: `data/index.html`, `data/app.js`, `data/style.css`

**Requirements:**
- **New nav tab `Device`.** It shows:
  - version and SSID, from `device_info`
  - **Wi-Fi password**: two `type=password` fields and a Save button
  - **Update**: a file input with `accept=".mcup"`, a "Reset all settings to defaults"
    checkbox (off), an Install button and a progress bar
- **Password save:**
  - The app mirrors `checkWifiPassword`'s rules and texts before sending.
  - It refuses a mismatch with "The two passwords don't match."
  - It warns "Your phone will drop off the Wi-Fi. Rejoin <ssid> with the new password." before
    sending `set_wifi_password`.
- **Install:**
  - `XMLHttpRequest` POST to `/update?reset=0|1` with `FormData` field `update`, showing upload
    progress.
  - On `{"ok":true}`, show "Installed. The controller is restarting — rejoin <ssid>". If reset
    was ticked, add " with password mccan1234".
  - On an error, show its `error` text.
- **Banner:** while `device_info.defaultPassword` is true, a persistent warning banner reads
  "Change the default Wi-Fi password (Device tab)."
- **Note under the file input:** "If the file picker doesn't open, open http://192.168.4.1 in
  your browser instead of the sign-in pop-up." iOS's captive mini-browser may block file
  selection.

- [ ] **Step 1: Implement.**
- [ ] **Step 2: ESP32 build** (re-embeds the app). Expected: SUCCESS.
- [ ] **Step 3: Commit** as `feat(app): Device tab with password change and phone update`.

### Task 10: Owner key, first signed release, on-device acceptance, docs

**Files:**
- Modify: `src/domain/update_pubkey.h` (generated), `src/version.h`, `README.md` and/or
  `docs/` flashing notes (remove `uploadfs`, add the update and release procedure)

- [ ] **Step 1: Owner generates the release key.** Run
  `! python tools/sign_update.py keygen`.
  - This writes `~/.mccan/update_key.pem` and regenerates `src/domain/update_pubkey.h`.
  - Tell the owner to back up the key file. Losing it means fielded units can only be updated
    over USB.
  - Commit the header only.
- [ ] **Step 2: ESP32 build `1.0.0` / build 1. Owner flashes it over USB** (upload only; there
  is no `uploadfs` any more).
- [ ] **Step 3: Acceptance on the dev board.** The owner does each item; record pass or fail per
  line.
  1. The settings saved before this plan are still present: migration worked.
  2. SSID is `MCCAN-XXXX`, the default-password banner shows, and password `mccan1234` joins.
  3. Change the password. The phone drops; rejoining with the new one works and the banner is
     gone.
  4. Set `kBuildNumber = 2` and `"1.0.1"`, build, and
     `python tools/sign_update.py sign --key ~/.mccan/update_key.pem --bin .pio/build/esp32/firmware.bin --out mccan-1.0.1.mcup`.
     Install from the phone. The Device tab then shows 1.0.1, and settings and password are
     kept.
  5. Install `mccan-1.0.1.mcup` again: accepted (same build).
  6. Install a build-1 `.mcup`: refused with the Downgrade text.
  7. Install the raw `firmware.bin`: refused with the BadMagic text.
  8. Build 3, `"1.0.2-crash"`, with an `abort()` at the top of `setup()`, signed. Install
     it. The controller comes back on 1.0.1, which proves rollback through the real route.
     Then remove the `abort()`.
  9. Build 4, `"1.0.2"`. Install it with "Reset all settings" ticked: the password is back to
     `mccan1234` and the CAN mappings are back to defaults.
  10. Hold BOOT for 3 s: nothing happens. Hold it for 10 s: the controller restarts with
      defaults.
  11. Start Discovery and close the browser tab: frame streaming stops.
- [ ] **Step 4: Docs.**
  - Flashing notes lose `uploadfs`.
  - Add a "Releasing an update" section: bump `src/version.h`, build, sign, publish the
    `.mcup`.
  - Add a "Recovering a forgotten password" section: hold the reset button 10 s.
  - Spec 2026-10-17 §11's two-flash warning gets a pointer to this plan.
- [ ] **Step 5: Commit** as `docs: phone updates, release signing and password recovery`.
  - Include `src/version.h` at build 4 / `"1.0.2"`, matching what the dev board now runs.
  - The crash build is never committed.
