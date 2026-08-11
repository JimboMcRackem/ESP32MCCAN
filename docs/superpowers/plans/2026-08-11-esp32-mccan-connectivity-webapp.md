# ESP32 MCCAN — Connectivity & Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Connectivity Layer — a SoftAP-hosted web app that lets a phone read, edit, and save the lighting config live and run CAN discovery — on top of the completed core firmware (Plan 1).

**Architecture:** A pure, host-testable **protocol module** translates WebSocket JSON requests into typed actions and builds outbound messages, reusing the Plan-1 `configToJson`/`configFromJson` round-trip verbatim. A thin ESP32 **HAL** (`WebServerHal`) runs a SoftAP + captive-portal DNS + HTTP file server (LittleFS) + a **synchronous** WebSocket server whose event callback fires inline on the main task — so config edits mutate the single `Config` with no cross-thread concurrency. `main.cpp` wires them: apply+persist config live, and stream CAN frame snapshots to the browser during discovery. The single-page web app (HTML/CSS/JS in `data/`) is served from LittleFS.

**Tech Stack:** Arduino-ESP32, `WebServer` + `DNSServer` + `LittleFS` (bundled with the framework), `links2004/WebSockets` (`WebSocketsServer`), ArduinoJson 7 (already a dependency), PlatformIO. Native host tests via Unity.

## Global Constraints

- **Board / framework:** classic ESP32 (`board = esp32dev`), `framework = arduino`, `-std=gnu++17` (copy from existing `platformio.ini`).
- **Two build envs:** `esp32` (target) and `native` (host Unity tests). `native` excludes Arduino code via `build_src_filter = +<*> -<main.cpp> -<hal/>` — **all WiFi/HTTP/WS/DNS code lives under `src/hal/` so it never enters the native build.**
- **Pure domain code only in `src/domain/`** — no hardware/Arduino includes there. `web_protocol` (domain) may include `<ArduinoJson.h>` (host-portable, already used by `config_json`).
- **Reuse, do not duplicate, the config serialization:** the protocol wraps `configToJson`/`configFromJson` (from `src/domain/config_json.h`) — never re-implement config↔JSON.
- **Unity 2.6.1 gotcha:** every native test translation unit MUST define `void setUp(void){}` and `void tearDown(void){}` (even empty) or linking fails.
- **Per-suite test dirs:** each Unity suite is its own `test/test_<name>/test_<name>.cpp` with its own `main()` (PlatformIO compiles all `.cpp` in one test dir into one binary).
- **Native tests:** `python -m platformio test -e native` (PlatformIO not on PATH — invoke via `python -m platformio`). Filter one suite with `-f test_<name>`.
- **ESP32 build:** `py -3.13 -m platformio run -e esp32` (default `python` is 3.14 which the espressif32 platform rejects; 3.13 is installed via the `py -3.13` launcher).
- **Canonical LSB-first bit convention** (Plan 1): bit index `b` → byte `b / 8`, bit `b % 8` counted from the LSB. The web app displays bits in this same convention.
- **Config is not secret** but the SPA is the only intended client; keep the WS protocol minimal and validate every inbound config through `configFromJson` (which already falls back to defaults on garbage).

---

## File Structure

**New files:**
- `src/domain/web_protocol.h` / `.cpp` — pure request→action translation + outbound message builders. Host-testable.
- `src/hal/web_server.h` / `.cpp` — `WebServerHal`: SoftAP + DNS captive portal + HTTP static (LittleFS) + synchronous WebSocket. ESP32-only, excluded from native.
- `data/index.html`, `data/style.css`, `data/app.js` — the single-page config app, uploaded to LittleFS.
- Test dirs: `test/test_can_snapshot/test_can_snapshot.cpp`, `test/test_web_protocol/test_web_protocol.cpp`.

**Modified files:**
- `src/domain/can_state.h` / `.cpp` — add `CanFrameSnapshot` + `CanState::snapshot()` (discovery data source).
- `src/main.cpp` — instantiate `WebServerHal`, wire the message handler (apply+persist config, toggle discovery), service the server each loop, broadcast frame snapshots while discovering.
- `platformio.ini` — add `links2004/WebSockets` to `[env:esp32]` `lib_deps`; add `board_build.filesystem = littlefs`.

**Data flow:**
```
browser ──ws JSON──> WebServerHal (hal, port 81) ──onMessage(client,text)──> main.cpp
   ▲                                                     │
   │                              handleRequest(text) ── web_protocol (domain, pure)
   │                                                     │  ProtocolAction
   │                          apply: g_cfg = act.cfgOut; storage::writeConfig(...)
   │                          discovery: g_discovery = act.discoveryOut
   └──ws JSON (config / frames / ok / error)── configMessage / framesMessage / ...
```

---

## Task 1: CAN frame snapshot (discovery data source)

Discovery mode streams every seen CAN frame to the browser so the rider can watch which bit flips. `CanState` already caches up to 16 frames; expose a read-only snapshot of them. Pure, host-testable.

**Files:**
- Modify: `src/domain/can_state.h`
- Modify: `src/domain/can_state.cpp`
- Test: `test/test_can_snapshot/test_can_snapshot.cpp`

**Interfaces:**
- Consumes: existing `CanState::update(uint32_t id, const uint8_t data[8])`, private `frames_[16]` with `{ uint32_t id; uint8_t data[8]; bool seen; }`.
- Produces:
  - `struct CanFrameSnapshot { uint32_t id; uint8_t data[8]; };`
  - `int CanState::snapshot(CanFrameSnapshot* out, int maxOut) const;` — copies each currently-seen frame into `out` (up to `maxOut`), returns the number written. Order is unspecified but stable per call.

- [ ] **Step 1: Write the failing test**

Create `test/test_can_snapshot/test_can_snapshot.cpp`:

```cpp
#include <unity.h>
#include "domain/can_state.h"

void setUp(void) {}
void tearDown(void) {}

static void frame(uint8_t b0, uint8_t b1, uint8_t data[8]) {
  for (int i = 0; i < 8; ++i) data[i] = 0;
  data[0] = b0; data[1] = b1;
}

void test_empty_snapshot_is_zero(void) {
  CanState s;
  CanFrameSnapshot out[16];
  TEST_ASSERT_EQUAL_INT(0, s.snapshot(out, 16));
}

void test_snapshot_returns_seen_frames(void) {
  CanState s;
  uint8_t d[8];
  frame(0xAA, 0x01, d); s.update(0x102, d);
  frame(0xBB, 0x02, d); s.update(0x400, d);

  CanFrameSnapshot out[16];
  int n = s.snapshot(out, 16);
  TEST_ASSERT_EQUAL_INT(2, n);

  // Find 0x102 in the result and check its bytes.
  bool found = false;
  for (int i = 0; i < n; ++i) {
    if (out[i].id == 0x102) {
      found = true;
      TEST_ASSERT_EQUAL_UINT8(0xAA, out[i].data[0]);
      TEST_ASSERT_EQUAL_UINT8(0x01, out[i].data[1]);
    }
  }
  TEST_ASSERT_TRUE(found);
}

void test_snapshot_respects_maxOut(void) {
  CanState s;
  uint8_t d[8] = {0};
  s.update(0x100, d);
  s.update(0x200, d);
  s.update(0x300, d);
  CanFrameSnapshot out[2];
  TEST_ASSERT_EQUAL_INT(2, s.snapshot(out, 2));   // clamped to maxOut
}

void test_update_refreshes_existing_frame(void) {
  CanState s;
  uint8_t d[8] = {0};
  d[0] = 0x11; s.update(0x102, d);
  d[0] = 0x22; s.update(0x102, d);                // same id updated
  CanFrameSnapshot out[16];
  int n = s.snapshot(out, 16);
  TEST_ASSERT_EQUAL_INT(1, n);
  TEST_ASSERT_EQUAL_UINT8(0x22, out[0].data[0]);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_empty_snapshot_is_zero);
  RUN_TEST(test_snapshot_returns_seen_frames);
  RUN_TEST(test_snapshot_respects_maxOut);
  RUN_TEST(test_update_refreshes_existing_frame);
  return UNITY_END();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m platformio test -e native -f test_can_snapshot`
Expected: FAIL — `CanFrameSnapshot` / `snapshot` not declared (compile error).

- [ ] **Step 3: Add the declaration**

In `src/domain/can_state.h`, add above the `class CanState` declaration:

```cpp
struct CanFrameSnapshot { uint32_t id; uint8_t data[8]; };
```

And inside the `public:` section of `CanState`, after `evaluate(...)`:

```cpp
  int snapshot(CanFrameSnapshot* out, int maxOut) const;
```

- [ ] **Step 4: Implement**

In `src/domain/can_state.cpp`, add:

```cpp
int CanState::snapshot(CanFrameSnapshot* out, int maxOut) const {
  int n = 0;
  for (int i = 0; i < MAX_FRAMES && n < maxOut; ++i) {
    if (!frames_[i].seen) continue;
    out[n].id = frames_[i].id;
    for (int b = 0; b < 8; ++b) out[n].data[b] = frames_[i].data[b];
    ++n;
  }
  return n;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m platformio test -e native -f test_can_snapshot`
Expected: PASS (4 tests).

- [ ] **Step 6: Run the full native suite (no regressions)**

Run: `python -m platformio test -e native`
Expected: all suites PASS (previous 40 + 4 new = 44).

- [ ] **Step 7: Commit**

```bash
git add src/domain/can_state.h src/domain/can_state.cpp test/test_can_snapshot/
git commit -m "feat: expose CanState frame snapshot for discovery mode

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Web protocol module (pure, host-testable)

Translate inbound WebSocket JSON into a typed `ProtocolAction`, and build the outbound JSON messages. Reuses `configToJson`/`configFromJson` — never re-serializes config by hand.

**Protocol (all messages are JSON objects with a `"type"` field):**

Inbound (browser → firmware):
- `{"type":"get_config"}` → firmware replies with the current config.
- `{"type":"set_config","config":{ ...full config doc... }}` → validate + apply + persist; reply with the applied config. `config` uses the exact shape produced by `configToJson` (`maps`, `blinkPeriodMs`, `spotHoldMs`, `colors`, `denali`).
- `{"type":"discovery","enable":true|false}` → toggle CAN frame streaming.

Outbound (firmware → browser):
- `{"type":"config","config":{ ... }}` — current/applied config (body = `configToJson`).
- `{"type":"frames","frames":[{"id":258,"data":[..8 bytes..]}, ...]}` — discovery snapshot.
- `{"type":"error","message":"..."}` — malformed request or unknown type.

**Files:**
- Create: `src/domain/web_protocol.h`
- Create: `src/domain/web_protocol.cpp`
- Test: `test/test_web_protocol/test_web_protocol.cpp`

**Interfaces:**
- Consumes: `configToJson(const Config&)`, `configFromJson(const std::string&, bool&)` from `domain/config_json.h`; `CanFrameSnapshot` from `domain/can_state.h`.
- Produces:
  ```cpp
  struct ProtocolAction {
    bool        sendConfig    = false;  // reply with current config
    bool        applyConfig   = false;  // cfgOut is valid; caller applies + persists
    bool        setDiscovery  = false;  // discoveryOut holds the requested state
    bool        discoveryOut  = false;
    Config      cfgOut;                 // valid only when applyConfig == true
    std::string error;                  // non-empty => malformed; caller sends errorMessage
  };
  ProtocolAction handleRequest(const std::string& json);
  std::string configMessage(const Config& c);                                   // {"type":"config", "config":{...}}
  std::string framesMessage(const CanFrameSnapshot* frames, int count);         // {"type":"frames", "frames":[...]}
  std::string errorMessage(const std::string& msg);                             // {"type":"error", "message":...}
  ```

- [ ] **Step 1: Write the failing test**

Create `test/test_web_protocol/test_web_protocol.cpp`:

```cpp
#include <unity.h>
#include "domain/web_protocol.h"
#include "domain/config_json.h"
#include "domain/config.h"
#include "domain/can_state.h"
#include <ArduinoJson.h>

void setUp(void) {}
void tearDown(void) {}

void test_get_config_requests_send(void) {
  ProtocolAction a = handleRequest("{\"type\":\"get_config\"}");
  TEST_ASSERT_TRUE(a.sendConfig);
  TEST_ASSERT_FALSE(a.applyConfig);
  TEST_ASSERT_TRUE(a.error.empty());
}

void test_set_config_applies_and_parses(void) {
  // Build a valid config doc and wrap it in a set_config envelope.
  Config c = defaultConfig();
  c.blinkPeriodMs = 500;
  std::string body = configToJson(c);
  std::string req = std::string("{\"type\":\"set_config\",\"config\":") + body + "}";

  ProtocolAction a = handleRequest(req);
  TEST_ASSERT_TRUE(a.applyConfig);
  TEST_ASSERT_TRUE(a.error.empty());
  TEST_ASSERT_EQUAL_UINT32(500, a.cfgOut.blinkPeriodMs);
}

void test_set_config_missing_body_is_error(void) {
  ProtocolAction a = handleRequest("{\"type\":\"set_config\"}");
  TEST_ASSERT_FALSE(a.applyConfig);
  TEST_ASSERT_FALSE(a.error.empty());
}

void test_malformed_json_is_error(void) {
  ProtocolAction a = handleRequest("not json");
  TEST_ASSERT_FALSE(a.error.empty());
}

void test_unknown_type_is_error(void) {
  ProtocolAction a = handleRequest("{\"type\":\"bogus\"}");
  TEST_ASSERT_FALSE(a.error.empty());
}

void test_discovery_enable_and_disable(void) {
  ProtocolAction on = handleRequest("{\"type\":\"discovery\",\"enable\":true}");
  TEST_ASSERT_TRUE(on.setDiscovery);
  TEST_ASSERT_TRUE(on.discoveryOut);

  ProtocolAction off = handleRequest("{\"type\":\"discovery\",\"enable\":false}");
  TEST_ASSERT_TRUE(off.setDiscovery);
  TEST_ASSERT_FALSE(off.discoveryOut);
}

void test_config_message_round_trips(void) {
  Config c = defaultConfig();
  c.spotHoldMs = 1234;
  std::string msg = configMessage(c);

  // Envelope has type=config; nested config re-parses to the same value.
  JsonDocument doc;
  TEST_ASSERT_TRUE(deserializeJson(doc, msg) == DeserializationError::Ok);
  TEST_ASSERT_EQUAL_STRING("config", doc["type"].as<const char*>());

  std::string inner;
  serializeJson(doc["config"], inner);
  bool ok = false;
  Config back = configFromJson(inner, ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_EQUAL_UINT32(1234, back.spotHoldMs);
}

void test_frames_message_serializes_ids_and_bytes(void) {
  CanFrameSnapshot fr[2];
  fr[0].id = 0x102; for (int i = 0; i < 8; ++i) fr[0].data[i] = 0; fr[0].data[0] = 0xAB;
  fr[1].id = 0x400; for (int i = 0; i < 8; ++i) fr[1].data[i] = 0; fr[1].data[7] = 0x0F;

  std::string msg = framesMessage(fr, 2);
  JsonDocument doc;
  TEST_ASSERT_TRUE(deserializeJson(doc, msg) == DeserializationError::Ok);
  TEST_ASSERT_EQUAL_STRING("frames", doc["type"].as<const char*>());
  JsonArray arr = doc["frames"].as<JsonArray>();
  TEST_ASSERT_EQUAL_INT(2, arr.size());
  TEST_ASSERT_EQUAL_UINT32(0x102, arr[0]["id"].as<uint32_t>());
  TEST_ASSERT_EQUAL_UINT8(0xAB, arr[0]["data"][0].as<uint8_t>());
  TEST_ASSERT_EQUAL_UINT8(0x0F, arr[1]["data"][7].as<uint8_t>());
}

void test_error_message_shape(void) {
  std::string msg = errorMessage("boom");
  JsonDocument doc;
  TEST_ASSERT_TRUE(deserializeJson(doc, msg) == DeserializationError::Ok);
  TEST_ASSERT_EQUAL_STRING("error", doc["type"].as<const char*>());
  TEST_ASSERT_EQUAL_STRING("boom", doc["message"].as<const char*>());
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_get_config_requests_send);
  RUN_TEST(test_set_config_applies_and_parses);
  RUN_TEST(test_set_config_missing_body_is_error);
  RUN_TEST(test_malformed_json_is_error);
  RUN_TEST(test_unknown_type_is_error);
  RUN_TEST(test_discovery_enable_and_disable);
  RUN_TEST(test_config_message_round_trips);
  RUN_TEST(test_frames_message_serializes_ids_and_bytes);
  RUN_TEST(test_error_message_shape);
  return UNITY_END();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m platformio test -e native -f test_web_protocol`
Expected: FAIL — `web_protocol.h` not found (compile error).

- [ ] **Step 3: Write the header**

Create `src/domain/web_protocol.h`:

```cpp
#pragma once
#include "domain/config.h"
#include "domain/can_state.h"
#include <string>

struct ProtocolAction {
  bool        sendConfig   = false;
  bool        applyConfig  = false;
  bool        setDiscovery = false;
  bool        discoveryOut = false;
  Config      cfgOut;
  std::string error;
};

// Parse one inbound WebSocket text message into an action. Never throws.
ProtocolAction handleRequest(const std::string& json);

// Outbound message builders.
std::string configMessage(const Config& c);
std::string framesMessage(const CanFrameSnapshot* frames, int count);
std::string errorMessage(const std::string& msg);
```

- [ ] **Step 4: Implement**

Create `src/domain/web_protocol.cpp`:

```cpp
#include "domain/web_protocol.h"
#include "domain/config_json.h"
#include <ArduinoJson.h>

ProtocolAction handleRequest(const std::string& json) {
  ProtocolAction act;
  JsonDocument doc;
  if (deserializeJson(doc, json) != DeserializationError::Ok) {
    act.error = "malformed json";
    return act;
  }

  const char* type = doc["type"] | "";
  std::string t = type;

  if (t == "get_config") {
    act.sendConfig = true;
    return act;
  }

  if (t == "set_config") {
    JsonObjectConst cfg = doc["config"];
    if (cfg.isNull()) {
      act.error = "set_config missing config";
      return act;
    }
    std::string inner;
    serializeJson(cfg, inner);
    bool ok = false;
    Config c = configFromJson(inner, ok);
    if (!ok) {
      act.error = "invalid config";
      return act;
    }
    act.applyConfig = true;
    act.cfgOut = c;
    return act;
  }

  if (t == "discovery") {
    act.setDiscovery = true;
    act.discoveryOut = doc["enable"] | false;
    return act;
  }

  act.error = "unknown type";
  return act;
}

std::string configMessage(const Config& c) {
  JsonDocument doc;
  doc["type"] = "config";
  doc["config"] = serialized(configToJson(c));  // insert pre-formatted JSON verbatim
  std::string out;
  serializeJson(doc, out);
  return out;
}

std::string framesMessage(const CanFrameSnapshot* frames, int count) {
  JsonDocument doc;
  doc["type"] = "frames";
  JsonArray arr = doc["frames"].to<JsonArray>();
  for (int i = 0; i < count; ++i) {
    JsonObject f = arr.add<JsonObject>();
    f["id"] = frames[i].id;
    JsonArray d = f["data"].to<JsonArray>();
    for (int b = 0; b < 8; ++b) d.add(frames[i].data[b]);
  }
  std::string out;
  serializeJson(doc, out);
  return out;
}

std::string errorMessage(const std::string& msg) {
  JsonDocument doc;
  doc["type"] = "error";
  doc["message"] = msg;
  std::string out;
  serializeJson(doc, out);
  return out;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m platformio test -e native -f test_web_protocol`
Expected: PASS (9 tests).

- [ ] **Step 6: Full native suite**

Run: `python -m platformio test -e native`
Expected: all PASS (44 + 9 = 53).

- [ ] **Step 7: Commit**

```bash
git add src/domain/web_protocol.h src/domain/web_protocol.cpp test/test_web_protocol/
git commit -m "feat: add pure web protocol module (config get/set, discovery, frames)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Web server HAL (SoftAP + captive portal + HTTP + WebSocket)

The ESP32-only glue: bring up a SoftAP, redirect captive-portal probes to the app, serve the SPA from LittleFS over HTTP, and run a **synchronous** WebSocket server. Verified by compiling the `esp32` env (this code is excluded from the native build).

**Files:**
- Create: `src/hal/web_server.h`
- Create: `src/hal/web_server.cpp`
- Modify: `platformio.ini`

**Interfaces:**
- Consumes: LittleFS (already mounted by `storage::begin()` before `WebServerHal::begin()` runs — see Task 4).
- Produces:
  ```cpp
  class WebServerHal {
  public:
    using MessageCb = std::function<void(uint8_t clientId, const std::string& text)>;
    bool begin(const char* ssid, const char* password);  // SoftAP + DNS + HTTP + WS(81)
    void loop();                                          // service DNS/HTTP/WS — call every iteration
    void onMessage(MessageCb cb);
    void sendTo(uint8_t clientId, const std::string& text);
    void broadcast(const std::string& text);
  };
  ```
  The WS event callback (fired inside `loop()` on the main task) invokes the registered `MessageCb` synchronously — callers may mutate shared state without locking.

- [ ] **Step 1: Add the WebSockets dependency and LittleFS filesystem to platformio.ini**

In `platformio.ini`, under `[env:esp32]`, add to `lib_deps` and add the filesystem line:

```ini
[env:esp32]
platform = espressif32
board = esp32dev
framework = arduino
build_flags = -std=gnu++17
build_unflags = -std=gnu++11
board_build.filesystem = littlefs
lib_deps =
    bblanchon/ArduinoJson@^7.0.0
    adafruit/Adafruit PWM Servo Driver Library@^3.0.0
    adafruit/Adafruit BusIO@^1.14
    links2004/WebSockets@^2.4.1
monitor_speed = 115200
```

Leave `[env:native]` untouched.

- [ ] **Step 2: Write the header**

Create `src/hal/web_server.h`:

```cpp
#pragma once
#include <string>
#include <functional>
#include <cstdint>

// SoftAP + captive-portal DNS + HTTP static file server (LittleFS) + synchronous
// WebSocket server. The WS event callback runs inline on the main task during loop().
class WebServerHal {
public:
  using MessageCb = std::function<void(uint8_t clientId, const std::string& text)>;

  bool begin(const char* ssid, const char* password);
  void loop();                                  // call every main-loop iteration
  void onMessage(MessageCb cb);
  void sendTo(uint8_t clientId, const std::string& text);
  void broadcast(const std::string& text);
};
```

- [ ] **Step 3: Implement**

Create `src/hal/web_server.cpp`. `WebServer` (HTTP, port 80), `DNSServer` (port 53, wildcard → AP IP for the captive portal), and `WebSocketsServer` (port 81) are held as file-scope statics so the C-style WS callback can reach them:

```cpp
#include "hal/web_server.h"
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <WebSocketsServer.h>
#include <LittleFS.h>

static WebServer         s_http(80);
static DNSServer         s_dns;
static WebSocketsServer  s_ws(81);
static IPAddress         s_apIP(192, 168, 4, 1);
static WebServerHal::MessageCb s_cb;

static void onWsEvent(uint8_t num, WStype_t type, uint8_t* payload, size_t length) {
  if (type == WStype_TEXT && s_cb) {
    s_cb(num, std::string(reinterpret_cast<char*>(payload), length));
  }
}

bool WebServerHal::begin(const char* ssid, const char* password) {
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(s_apIP, s_apIP, IPAddress(255, 255, 255, 0));
  bool ap = WiFi.softAP(ssid, password);

  // Captive portal: resolve every hostname to us.
  s_dns.start(53, "*", s_apIP);

  // Serve the SPA from LittleFS. serveStatic infers content types from extensions.
  s_http.serveStatic("/", LittleFS, "/index.html");
  s_http.serveStatic("/index.html", LittleFS, "/index.html");
  s_http.serveStatic("/app.js", LittleFS, "/app.js");
  s_http.serveStatic("/style.css", LittleFS, "/style.css");
  // Any other path (OS captive-portal probes) → redirect to the app root.
  s_http.onNotFound([]() {
    s_http.sendHeader("Location", "http://192.168.4.1/", true);
    s_http.send(302, "text/plain", "");
  });
  s_http.begin();

  s_ws.begin();
  s_ws.onEvent(onWsEvent);
  return ap;
}

void WebServerHal::loop() {
  s_dns.processNextRequest();
  s_http.handleClient();
  s_ws.loop();
}

void WebServerHal::onMessage(MessageCb cb) { s_cb = cb; }

void WebServerHal::sendTo(uint8_t clientId, const std::string& text) {
  s_ws.sendTXT(clientId, text.c_str(), text.length());
}

void WebServerHal::broadcast(const std::string& text) {
  s_ws.broadcastTXT(text.c_str(), text.length());
}
```

- [ ] **Step 4: Verify the esp32 env compiles**

Run: `py -3.13 -m platformio run -e esp32`
Expected: SUCCESS — the WebSockets library resolves and links; `main.cpp` still uses the old wiring (this task only adds an unused HAL class, which compiles). Note the RAM/Flash figures.

- [ ] **Step 5: Verify native tests still pass (HAL excluded)**

Run: `python -m platformio test -e native`
Expected: all PASS (53) — `build_src_filter` keeps `src/hal/` out of the native build, so the new HAL is not compiled there.

- [ ] **Step 6: Commit**

```bash
git add src/hal/web_server.h src/hal/web_server.cpp platformio.ini
git commit -m "feat: add WebServerHal (SoftAP, captive portal, HTTP, WebSocket)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Boot wiring — live config apply + persist + discovery streaming

Wire `WebServerHal` into `main.cpp`: start the AP after LittleFS is up, handle inbound messages through `web_protocol`, apply+persist config live, and broadcast CAN frame snapshots while discovery is on. Lighting keeps running — the server is serviced every loop iteration; the 10 ms lighting tick is unchanged.

**Files:**
- Modify: `src/main.cpp`

**Interfaces:**
- Consumes: `WebServerHal` (Task 3); `handleRequest`, `configMessage`, `framesMessage`, `errorMessage` (Task 2); `CanState::snapshot` + `CanFrameSnapshot` (Task 1); existing `configToJson`, `storage::writeConfig`, `g_cfg`, `g_can`.
- Produces: no new public interface (top-level firmware wiring).

- [ ] **Step 1: Add includes and globals**

In `src/main.cpp`, add to the includes:

```cpp
#include "domain/web_protocol.h"
#include "hal/web_server.h"
```

After the existing `static CanBus g_bus;` line, add:

```cpp
static WebServerHal g_web;
static bool         g_discovery = false;

static const char* kApSsid = "MCCAN-Setup";
static const char* kApPass = "mccan1234";     // WPA2 requires >= 8 chars
```

- [ ] **Step 2: Wire the message handler and start the AP in setup()**

At the end of `setup()` (after CAN init), add:

```cpp
  g_web.onMessage([](uint8_t client, const std::string& msg) {
    ProtocolAction act = handleRequest(msg);
    if (!act.error.empty()) {
      g_web.sendTo(client, errorMessage(act.error));
      return;
    }
    if (act.sendConfig) {
      g_web.sendTo(client, configMessage(g_cfg));
    }
    if (act.applyConfig) {
      g_cfg = act.cfgOut;                              // live apply (single-threaded)
      storage::writeConfig(configToJson(g_cfg));       // persist for next boot
      g_web.sendTo(client, configMessage(g_cfg));      // confirm with the applied config
    }
    if (act.setDiscovery) {
      g_discovery = act.discoveryOut;
    }
  });

  if (!g_web.begin(kApSsid, kApPass))
    Serial.println("SoftAP start failed");
  else
    Serial.printf("AP up: SSID=%s  http://192.168.4.1/\n", kApSsid);
```

- [ ] **Step 3: Service the server and stream discovery frames in loop()**

Replace the body of `loop()` so the server is serviced every iteration and frames stream on a 100 ms throttle while discovering:

```cpp
void loop() {
  g_web.loop();                                   // DNS + HTTP + WS (fires onMessage inline)

  // Drain all pending CAN frames into the state cache.
  uint32_t id;
  uint8_t data[8];
  while (g_bus.receive(id, data)) g_can.update(id, data);

  uint32_t now = millis();

  // Evaluate -> compute -> drive, on a ~10 ms tick.
  static uint32_t last = 0;
  if (now - last >= 10) {
    last = now;
    LogicalState s = g_can.evaluate(g_cfg);
    OutputIntent o = computeOutputs(s, g_cfg, now, g_engine);
    applyIntent(g_pwm, o);
  }

  // Stream CAN frame snapshots to the browser while discovery is active.
  static uint32_t lastDisc = 0;
  if (g_discovery && now - lastDisc >= 100) {
    lastDisc = now;
    CanFrameSnapshot fr[16];
    int n = g_can.snapshot(fr, 16);
    g_web.broadcast(framesMessage(fr, n));
  }
}
```

- [ ] **Step 4: Verify the esp32 env compiles and links**

Run: `py -3.13 -m platformio run -e esp32`
Expected: SUCCESS. Note the RAM/Flash figures (WiFi + WebServer + WebSockets raise both vs. Plan 1's 7.1% / 29.4%).

- [ ] **Step 5: Verify native tests still pass**

Run: `python -m platformio test -e native`
Expected: all PASS (53) — `main.cpp` is excluded from the native build.

- [ ] **Step 6: Commit**

```bash
git add src/main.cpp
git commit -m "feat: wire WebServerHal for live config apply, persist, and discovery

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Web app (single-page config UI served from LittleFS)

The phone-facing app: connects over WebSocket, loads the config, edits tunables / appearance / mappings, runs discovery to assign bits, and exports/imports config JSON for backup. Plain HTML/CSS/JS (no build step), uploaded to LittleFS via `pio run -t uploadfs`. Automated gate = JS syntax check with `node --check`; full behavior is an on-hardware smoke test (SoftAP + browser).

**Files:**
- Create: `data/index.html`
- Create: `data/style.css`
- Create: `data/app.js`

**Interfaces:**
- Consumes: the WS protocol from Task 2 — sends `get_config` / `set_config` / `discovery`; receives `config` / `frames` / `error`. Config object shape = `configToJson` output (`maps`, `blinkPeriodMs`, `spotHoldMs`, `colors`, `denali`). Function keys in `maps`: `run, leftInd, rightInd, frontBrake, rearBrake, lowBeam, highBeam, highBeamFlash, dayNight, kickStand` (from `config_json.cpp`). `combine`: `0=Single, 1=And, 2=Or`.

- [ ] **Step 1: Write index.html**

Create `data/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MCCAN Lighting Config</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <h1>MCCAN Lighting</h1>
    <span id="status" class="status off">disconnected</span>
  </header>

  <nav>
    <button data-tab="tunables" class="active">Tunables</button>
    <button data-tab="appearance">Appearance</button>
    <button data-tab="mapping">Mapping</button>
    <button data-tab="discovery">Discovery</button>
    <button data-tab="backup">Backup</button>
  </nav>

  <main>
    <section id="tab-tunables" class="tab active">
      <label>Blink period (ms)
        <input type="number" id="blinkPeriodMs" min="50" max="2000" step="10">
      </label>
      <label>Spot hold threshold (ms)
        <input type="number" id="spotHoldMs" min="100" max="5000" step="50">
      </label>
      <div id="denali"></div>
    </section>

    <section id="tab-appearance" class="tab">
      <div id="colors"></div>
    </section>

    <section id="tab-mapping" class="tab">
      <div id="maps"></div>
    </section>

    <section id="tab-discovery" class="tab">
      <p>Toggle a control on the bike and watch which bit flips.</p>
      <label><input type="checkbox" id="discToggle"> Stream CAN frames</label>
      <label>Assign clicked bit to:
        <select id="discFunc"></select>
      </label>
      <div id="frames"></div>
    </section>

    <section id="tab-backup" class="tab">
      <button id="exportBtn">Export config JSON</button>
      <label class="filebtn">Import config JSON
        <input type="file" id="importInput" accept="application/json,.json">
      </label>
    </section>
  </main>

  <footer>
    <button id="saveBtn">Save &amp; apply</button>
    <button id="reloadBtn">Reload from device</button>
  </footer>

  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write style.css**

Create `data/style.css`:

```css
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, sans-serif; color: #eee; background: #181a1f; }
header { display: flex; align-items: center; gap: .75rem; padding: .75rem 1rem; background: #23262d; }
h1 { font-size: 1.1rem; margin: 0; flex: 1; }
.status { font-size: .8rem; padding: .2rem .5rem; border-radius: .4rem; }
.status.on { background: #1f6f3f; }
.status.off { background: #7a2b2b; }
nav { display: flex; overflow-x: auto; background: #23262d; border-top: 1px solid #333; }
nav button { flex: 1 0 auto; padding: .7rem .6rem; background: none; color: #bbb; border: none; border-bottom: 3px solid transparent; font-size: .85rem; }
nav button.active { color: #fff; border-bottom-color: #4b8bff; }
main { padding: 1rem; }
.tab { display: none; }
.tab.active { display: block; }
label { display: block; margin: .6rem 0; font-size: .9rem; }
input[type=number], select { width: 100%; padding: .5rem; margin-top: .25rem; background: #12141a; color: #eee; border: 1px solid #333; border-radius: .4rem; }
.row { display: flex; align-items: center; gap: .5rem; margin: .4rem 0; }
.row > span { flex: 1; }
footer { position: sticky; bottom: 0; display: flex; gap: .5rem; padding: .75rem 1rem; background: #23262d; border-top: 1px solid #333; }
footer button, .filebtn { flex: 1; padding: .7rem; border: none; border-radius: .4rem; background: #4b8bff; color: #fff; font-size: .9rem; text-align: center; }
#reloadBtn { background: #444; }
.frame { font-family: ui-monospace, monospace; font-size: .8rem; margin: .3rem 0; padding: .3rem; background: #12141a; border-radius: .4rem; }
.frame .id { color: #4b8bff; margin-right: .5rem; }
.bit { display: inline-block; width: 1.1rem; text-align: center; cursor: pointer; border-radius: .2rem; }
.bit.set { background: #1f6f3f; color: #fff; }
.mapfn { border: 1px solid #333; border-radius: .4rem; padding: .5rem; margin: .5rem 0; }
.mapfn h3 { margin: 0 0 .3rem; font-size: .9rem; }
.filebtn input { display: none; }
small { color: #888; }
```

- [ ] **Step 3: Write app.js**

Create `data/app.js`:

```js
"use strict";

// Function keys must match config_json.cpp kFuncNames order/spelling.
const FUNCS = ["run","leftInd","rightInd","frontBrake","rearBrake",
               "lowBeam","highBeam","highBeamFlash","dayNight","kickStand"];
const COLORS = ["drlWhiteDay","drlWhiteNight","drlDimRedDay","drlDimRedNight",
                "indicatorOrange","brakeRed"];
const DENALI = ["day","low","high","spot"];
const COMBINE = { 0: "Single", 1: "And", 2: "Or" };

let cfg = null;         // last config from device
let ws = null;

function setStatus(connected) {
  const el = document.getElementById("status");
  el.textContent = connected ? "connected" : "disconnected";
  el.className = "status " + (connected ? "on" : "off");
}

function connect() {
  ws = new WebSocket("ws://" + location.hostname + ":81/");
  ws.onopen = () => { setStatus(true); send({ type: "get_config" }); };
  ws.onclose = () => { setStatus(false); setTimeout(connect, 1500); };
  ws.onmessage = (ev) => onMessage(JSON.parse(ev.data));
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

function onMessage(msg) {
  if (msg.type === "config") { cfg = msg.config; render(); }
  else if (msg.type === "frames") { renderFrames(msg.frames); }
  else if (msg.type === "error") { alert("Device error: " + msg.message); }
}

// ---- rendering ----
function render() {
  document.getElementById("blinkPeriodMs").value = cfg.blinkPeriodMs;
  document.getElementById("spotHoldMs").value = cfg.spotHoldMs;
  renderDenali();
  renderColors();
  renderMaps();
  renderDiscFuncOptions();
}

function renderDenali() {
  const host = document.getElementById("denali");
  host.innerHTML = "<h3>Denali levels (0-255)</h3>";
  DENALI.forEach((k) => {
    const lab = document.createElement("label");
    lab.textContent = "Denali " + k;
    const inp = document.createElement("input");
    inp.type = "number"; inp.min = 0; inp.max = 255; inp.value = cfg.denali[k];
    inp.oninput = () => { cfg.denali[k] = clamp(inp.value, 0, 255); };
    lab.appendChild(inp); host.appendChild(lab);
  });
}

function renderColors() {
  const host = document.getElementById("colors");
  host.innerHTML = "";
  COLORS.forEach((k) => {
    const row = document.createElement("div");
    row.className = "row";
    const name = document.createElement("span"); name.textContent = k;
    const picker = document.createElement("input");
    picker.type = "color"; picker.value = rgbToHex(cfg.colors[k]);
    picker.oninput = () => { cfg.colors[k] = hexToRgb(picker.value); };
    row.appendChild(name); row.appendChild(picker); host.appendChild(row);
  });
}

function renderMaps() {
  const host = document.getElementById("maps");
  host.innerHTML = "";
  FUNCS.forEach((fn) => {
    const m = cfg.maps[fn] || { combine: 0, bits: [] };
    cfg.maps[fn] = m;
    const box = document.createElement("div");
    box.className = "mapfn";
    const h = document.createElement("h3"); h.textContent = fn; box.appendChild(h);

    const sel = document.createElement("select");
    Object.entries(COMBINE).forEach(([v, t]) => {
      const o = document.createElement("option"); o.value = v; o.textContent = t;
      if (Number(v) === m.combine) o.selected = true; sel.appendChild(o);
    });
    sel.onchange = () => { m.combine = Number(sel.value); };
    box.appendChild(sel);

    (m.bits || []).forEach((b, i) => {
      const row = document.createElement("div"); row.className = "row";
      const label = document.createElement("span");
      label.textContent = "0x" + b.id.toString(16) + " bit " + b.bit;
      const del = document.createElement("button");
      del.textContent = "remove";
      del.onclick = () => { m.bits.splice(i, 1); renderMaps(); };
      row.appendChild(label); row.appendChild(del); box.appendChild(row);
    });
    host.appendChild(box);
  });
}

function renderDiscFuncOptions() {
  const sel = document.getElementById("discFunc");
  const prev = sel.value;
  sel.innerHTML = "";
  FUNCS.forEach((fn) => {
    const o = document.createElement("option"); o.value = fn; o.textContent = fn;
    sel.appendChild(o);
  });
  if (prev) sel.value = prev;
}

function renderFrames(frames) {
  const host = document.getElementById("frames");
  host.innerHTML = "";
  frames.sort((a, b) => a.id - b.id).forEach((f) => {
    const div = document.createElement("div"); div.className = "frame";
    const id = document.createElement("span");
    id.className = "id"; id.textContent = "0x" + f.id.toString(16);
    div.appendChild(id);
    // 64 bits, LSB-first within each byte (canonical convention).
    for (let bit = 0; bit < 64; bit++) {
      const byte = f.data[bit >> 3];
      const on = (byte >> (bit & 7)) & 1;
      const cell = document.createElement("span");
      cell.className = "bit" + (on ? " set" : "");
      cell.textContent = on ? "1" : "0";
      cell.title = "bit " + bit;
      cell.onclick = () => assignBit(f.id, bit);
      div.appendChild(cell);
    }
    host.appendChild(div);
  });
}

function assignBit(id, bit) {
  if (!cfg) return;
  const fn = document.getElementById("discFunc").value;
  const m = cfg.maps[fn] || (cfg.maps[fn] = { combine: 0, bits: [] });
  if (!m.bits.some((b) => b.id === id && b.bit === bit)) m.bits.push({ id, bit });
  alert("Added 0x" + id.toString(16) + " bit " + bit + " to " + fn +
        " (Save & apply to persist)");
}

// ---- outbound ----
function collect() {
  cfg.blinkPeriodMs = clamp(document.getElementById("blinkPeriodMs").value, 50, 5000);
  cfg.spotHoldMs = clamp(document.getElementById("spotHoldMs").value, 100, 10000);
  return cfg;
}

function save() { send({ type: "set_config", config: collect() }); }

function exportConfig() {
  const blob = new Blob([JSON.stringify(collect(), null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "mccan-config.json"; a.click();
  URL.revokeObjectURL(a.href);
}

function importConfig(file) {
  const r = new FileReader();
  r.onload = () => {
    try { cfg = JSON.parse(r.result); render(); save(); }
    catch (e) { alert("Invalid JSON file"); }
  };
  r.readAsText(file);
}

// ---- helpers ----
function clamp(v, lo, hi) { v = Number(v) | 0; return v < lo ? lo : v > hi ? hi : v; }
function rgbToHex(a) {
  const h = (n) => ("0" + (n & 255).toString(16)).slice(-2);
  return "#" + h(a[0]) + h(a[1]) + h(a[2]);
}
function hexToRgb(s) {
  return [parseInt(s.slice(1, 3), 16), parseInt(s.slice(3, 5), 16), parseInt(s.slice(5, 7), 16)];
}

// ---- wiring ----
document.querySelectorAll("nav button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll("nav button").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    document.getElementById("tab-" + b.dataset.tab).classList.add("active");
  };
});
document.getElementById("saveBtn").onclick = save;
document.getElementById("reloadBtn").onclick = () => send({ type: "get_config" });
document.getElementById("exportBtn").onclick = exportConfig;
document.getElementById("importInput").onchange = (e) => {
  if (e.target.files[0]) importConfig(e.target.files[0]);
};
document.getElementById("discToggle").onchange = (e) => {
  send({ type: "discovery", enable: e.target.checked });
};

connect();
```

- [ ] **Step 4: Validate the JavaScript syntax**

Run: `node --check data/app.js`
Expected: no output, exit 0 (valid syntax). If `node` is unavailable, review the file manually for balanced braces and matching identifiers instead.

- [ ] **Step 5: Confirm the LittleFS image builds (assets are packable)**

Run: `py -3.13 -m platformio run -e esp32 -t buildfs`
Expected: SUCCESS — a LittleFS image is produced from `data/`. (Flashing it, `-t uploadfs`, and the browser smoke test are on-hardware steps — see Deferred, below.)

- [ ] **Step 6: Commit**

```bash
git add data/index.html data/style.css data/app.js
git commit -m "feat: add single-page config web app (tunables, appearance, mapping, discovery, backup)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Deferred to on-hardware bench (needs a physical ESP32 + phone)

These cannot run in this environment and are explicitly out of scope for the automated task gates:
- `py -3.13 -m platformio run -e esp32 -t uploadfs` to flash the LittleFS image (the `data/` app).
- Join the `MCCAN-Setup` AP from a phone, confirm the captive portal opens the app, load/edit/save config, and confirm the lights keep running during a config session.
- Discovery: toggle a control on the bike, confirm the flipped bit is visible in the frame table and assignable.
- Confirm live-apply changes lighting immediately and survives a reboot (persisted to `/config.json`).

> **Note:** `uploadfs` rewrites the whole LittleFS partition, erasing a runtime-written `/config.json`. After an `uploadfs`, the firmware falls back to the baked-in Experia defaults on next boot (expected).

---

## Self-Review Notes (spec §6 coverage)

- **SoftAP + captive portal** → Task 3 (`WiFi.softAP`, `DNSServer` wildcard, `onNotFound` 302).
- **HTTP serves SPA from LittleFS** → Task 3 (`serveStatic`) + Task 5 (`data/`).
- **WebSocket live config read/apply/save** → Task 2 (`get_config`/`set_config`) + Task 4 (apply + `storage::writeConfig`).
- **Discovery streams decoded frames** → Task 1 (`snapshot`) + Task 2 (`framesMessage`) + Task 4 (throttled broadcast) + Task 5 (frame table + bit assign).
- **Web app screens (Mapping/Tunables/Appearance/Backup/Status)** → Task 5 (tabs; Status = connection indicator + live discovery view).
- **Lighting keeps running while AP up** → Task 4 (server serviced every iteration; 10 ms lighting tick preserved; single-threaded config apply).
- **Config export/import JSON** → Task 5 (Backup tab).
```
