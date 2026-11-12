#include <Arduino.h>
#include "domain/config.h"
#include "domain/config_json.h"
#include "domain/can_state.h"
#include "domain/behavior_engine.h"
#include "domain/test_mode.h"
#include "domain/output_map.h"
#include "hal/outputs_gpio.h"
#include "hal/aux_pwm_ledc.h"
#include "hal/can_bus.h"
#include "hal/storage.h"
#include "domain/web_protocol.h"
#include "hal/web_server.h"
#include "domain/update_image.h"
#include "domain/wifi_settings.h"
#include "domain/reset_sequence.h"
#include "domain/reset_feedback.h"
#include "version.h"
#include <esp_ota_ops.h>
#include <esp_mac.h>

// Pin/bus assignments: these match the phase-A board schematic (hardware/scripts/
// gen_mcu_can.py, ESP32 pin map D2). Change them only together with that sheet.
static const int kCanRxPin = 35;            // RTC-capable, so CAN traffic can wake deep sleep
// TWAI TX idles HIGH, so it must never share a lamp pin. GPIO12 carries only its
// strap pull-down (R36): the transceiver's TXD is pulled up and not wired to the
// MCU at all (hardware listen-only), so this pin drives nothing on the board.
static const int kCanTxPin = 12;
static const uint32_t kCanBitrate = 500000;

static const int kEn5vPin   = 4;    // +5V enable: the CAN transceiver's VCC and the quads' THER
static const int kCanStbPin = 14;   // TJA1042 STB, pulled up on the board (floating = standby)
static const int kDiagEnPin = 2;    // quad switches' DIAG_EN, pulled down on the chip side
// Shared pod brightness PWM to both yellow wires (night-mode spec 6.1). It was
// status LED D5; the factory-reset feedback now shows on the indicators.
static const int kAuxPwmPin = 13;
static const int kResetBtnPin = 0;  // BOOT button: hold 10 s, release within 5 s = factory reset (LOW = pressed)

// GPIO assignment in OutputIndex order. These avoid the strapping pins
// (0, 2, 5, 12, 15), but that is hygiene, not the safety guarantee: nothing
// lights a lamp at reset because spec 3.2 mandates a hard pull-down on every
// switch input, and that covers a floating or strapping-pin GPIO either way.
// Do not read a pin choice here as doing that work.
static const uint8_t kOutputPins[] = {
  25, 26,        // FL_DRL, FL_IND
  32, 33,        // FR_DRL, FR_IND
  27, 16, 17,    // RL_DRL, RL_IND, RL_BRK
  18, 19, 21,    // RR_DRL, RR_IND, RR_BRK
  22, 23,        // AUX_L, AUX_R
};
// Catches a dropped line, which would otherwise zero-fill the tail onto GPIO 0
// and shift every later output onto the wrong wire. It does NOT check order --
// only the comments above and the on-device output walk do that. main.cpp is
// excluded from the native build, so the ESP32 build is the only thing that
// ever compiles this.
static_assert(sizeof(kOutputPins) / sizeof(kOutputPins[0]) == (size_t)OUT_COUNT,
              "kOutputPins must have one pin per OutputIndex");
static GpioOutputs g_out(kOutputPins, OUT_COUNT);
static LedcAuxPwm  g_auxPwm(kAuxPwmPin, kAuxPwmHz);

static Config      g_cfg;
static CanState    g_can;
static EngineState g_engine;
static TestMode    g_test;         // lighting override held by the web app
static EngineState g_testEngine;   // scenarios run against THIS, never g_engine
static CanBus      g_bus;

static WebServerHal g_web;
static bool         g_discovery = false;
static uint8_t      g_discoveryOwner = 0;  // the client that turned Discovery on
static std::string  g_ssid;                // "MCCAN-XXXX", from the SoftAP MAC
static bool         g_apUp = false;
static ResetSequence g_reset;

// Deferred actions, run from loop() so a reply or broadcast can flush first.
static bool         g_restartPending = false;   // an update is set to boot, or settings were erased
static uint32_t     g_restartAt = 0;
static const char*  g_restartWhy = "";
static bool         g_restartHeldLogged = false;
static bool         g_apRestartPending = false; // the Wi-Fi password changed
static uint32_t     g_apRestartAt = 0;
static std::string  g_newWifiPass;

// Rollback confirmation: the bootloader boots a fresh OTA image once as
// "pending verify" and rolls back on the next reset unless the image marks
// itself valid. Tell the Arduino core not to mark it at startup; loop() does
// it once the image has shown it runs (AP up, lighting tick running, 5 s in).
extern "C" bool verifyRollbackLater() { return true; }
static bool g_tickRan = false;
static bool g_markedValid = false;

static DeviceInfo currentDeviceInfo() {
  DeviceInfo d;
  d.version = kVersionString;
  d.build = kBuildNumber;
  d.ssid = g_ssid;
  d.defaultPassword = storage::isDefaultWifiPassword();
  return d;
}

// Move every pending TWAI frame into the state cache.
static void drainCan() {
  uint32_t id;
  uint8_t data[8];
  while (g_bus.receive(id, data)) g_can.update(id, data, millis());
}

// Drain CAN, then evaluate -> compute -> drive on the ~10 ms tick. Called
// from loop() and, during an update upload, after every upload chunk, so the
// lamps keep following the bike while the HTTP server holds the main task.
static void serviceLighting() {
  drainCan();
  const uint32_t now = millis();
  static uint32_t last = 0;
  if (now - last >= 10) {            // unsigned subtraction: wrap-safe
    last = now;
    LogicalState s = g_can.evaluate(g_cfg, now);
    OutputIntent o = resolveOutputs(s, g_test, g_cfg, now, g_engine, g_testEngine);
    // Same parked gate as the restart: feedback never touches a riding bike.
    const bool parked = g_can.stale(now) || s.kickstand;
    applyIntent(g_out, g_auxPwm, withResetFeedback(o, parked, g_reset.phase(), now));
    g_tickRan = true;
  }
}

// The update gate. It runs inside an HTTP request, after the server has
// blocked loop() to read the request: it must NEVER read the CAN cache
// without draining first, or a live bus looks stale and "parked".
static bool parkedNow() {
  drainCan();
  const uint32_t now = millis();
  return parkedForUpdate(g_can.stale(now), g_can.evaluate(g_cfg, now).kickstand);
}

static bool deadlinePassed(uint32_t now, uint32_t at) {
  return (int32_t)(now - at) >= 0;   // wrap-safe
}

// Factory-reset button, sampled every loop() pass. Nothing here blocks or
// writes a pin: serviceLighting() keeps running in every phase and shows the
// gesture on the indicators (withResetFeedback: armed blinks, erased holds). The
// erase happens only on a release inside the confirm window, so a stuck or
// wet line cancels instead, and the restart waits for parked like an update.
static void serviceResetButton(uint32_t now) {
  switch (g_reset.update(digitalRead(kResetBtnPin) == LOW, now)) {
    case ResetEvent::Armed:
      Serial.println("reset button held 10 s: release within 5 s to factory reset");
      break;
    case ResetEvent::Cancelled:
      Serial.println("reset button still held after 5 s: cancelled (stuck button?)");
      break;
    case ResetEvent::Confirmed:
      storage::eraseAll();
      Serial.println("factory reset: settings erased");
      g_restartPending = true;
      g_restartAt = now;
      g_restartWhy = "factory reset";
      break;
    case ResetEvent::None:
      break;
  }
}

// Drop any active override and tell every client. Called on explicit exit,
// owner disconnect, and cap expiry.
static void releaseTest(uint32_t now) {
  g_test = TestMode{};
  g_testEngine = EngineState{};
  g_web.broadcast(testStateMessage(g_test, g_cfg, now));
}

void setup() {
  Serial.begin(115200);

  // Pod duty 0 before any output can switch a pod on. A failed attach fails
  // dark (the yellow buffer holds low), but the pods would light only their
  // DRL LEDs, so say why.
  if (!g_auxPwm.begin())
    Serial.println("aux PWM attach failed: pods' main LEDs stay dark");
  g_out.begin();      // all twelve outputs LOW before anything else

  pinMode(kDiagEnPin, OUTPUT);
  digitalWrite(kDiagEnPin, LOW);    // switch diagnostics off until something reads them
  pinMode(kCanStbPin, OUTPUT);
  digitalWrite(kCanStbPin, LOW);    // transceiver normal mode
  pinMode(kEn5vPin, OUTPUT);
  digitalWrite(kEn5vPin, HIGH);     // transceiver VCC: without it nothing is received

  pinMode(kResetBtnPin, INPUT_PULLUP);

  // Lights must work without NVS: every storage read falls back to defaults.
  if (!storage::begin())
    Serial.println("storage unavailable -> defaults; settings will not persist");
  bool ok = false;
  g_cfg = configFromJson(storage::readConfig(), ok);  // falls back to defaults
  if (!ok) Serial.println("config missing/corrupt -> using Experia defaults");

  if (!g_bus.begin(kCanRxPin, kCanTxPin, kCanBitrate))
    Serial.println("CAN init failed");

  g_web.onMessage([](uint8_t client, const std::string& msg) {
    ProtocolAction act = handleRequest(msg);
    if (!act.error.empty()) {
      g_web.sendTo(client, errorMessage(act.error));
      return;
    }
    if (act.sendConfig) {
      g_web.sendTo(client, configMessage(g_cfg));
      g_web.sendTo(client, deviceInfoMessage(currentDeviceInfo()));
    }
    if (act.applyConfig) {
      g_cfg = act.cfgOut;                              // live apply (single-threaded)
      storage::writeConfig(configToJson(g_cfg));       // persist for next boot
      g_web.sendTo(client, configMessage(g_cfg));      // confirm with the applied config
    }
    if (act.setDiscovery) {
      g_discovery = act.discoveryOut;
      g_discoveryOwner = act.discoveryOut ? client : 0;
    }
    if (act.setWifiPassword) {
      if (!storage::writeWifiPassword(act.wifiPasswordOut)) {
        g_web.sendTo(client, errorMessage("Could not save the password. Nothing was changed."));
      } else {
        // Tell every phone first; the AP comes back with the new password in
        // 1 s (from loop()), which drops them all. The controller keeps running.
        g_web.broadcast(deviceInfoMessage(currentDeviceInfo()));
        g_newWifiPass = act.wifiPasswordOut;
        g_apRestartPending = true;
        g_apRestartAt = millis() + 1000;
      }
    }
    if (act.setTest) {
      const uint32_t now = millis();
      if (act.testOut.kind == TestKind::Off) {
        releaseTest(now);
      } else {
        // Last writer wins: a second client taking the mode is not an error.
        g_test = act.testOut;
        g_test.owner = client;
        g_test.startedMs = now;
        g_testEngine = EngineState{};
        // Broadcast, not sendTo: a second phone must not be unaware the
        // lights are held.
        g_web.broadcast(testStateMessage(g_test, g_cfg, now));
      }
    }
  });

  g_web.onDisconnect([](uint8_t client) {
    if (g_test.kind != TestKind::Off && g_test.owner == client) {
      releaseTest(millis());
    }
    // Discovery streams frames to everyone every 100 ms; do not leave it on
    // after the phone that asked for it is gone.
    if (g_discovery && g_discoveryOwner == client) {
      g_discovery = false;
    }
  });

  g_web.onUploadTick(serviceLighting);
  g_web.onUpdate(
      [] { return parkedNow(); },
      [](bool resetSettings) {
        if (resetSettings) storage::requestResetOnNextBoot();
        g_restartPending = true;
        g_restartAt = millis() + 500;   // loop() restarts once the reply has flushed
        g_restartWhy = "update installed";
      });

  uint8_t mac[6] = {0};
  esp_read_mac(mac, ESP_MAC_WIFI_SOFTAP);
  g_ssid = apSsid(mac);
  const std::string pass = storage::readWifiPassword();
  g_apUp = g_web.begin(g_ssid.c_str(), pass.c_str());
  if (!g_apUp)
    Serial.println("SoftAP start failed");
  else
    Serial.printf("AP up: SSID=%s  http://192.168.4.1/  firmware %s (build %u)\n",
                  g_ssid.c_str(), kVersionString, (unsigned)kBuildNumber);
}

void loop() {
  g_web.loop();                                   // DNS + HTTP + WS (fires onMessage inline)

  drainCan();
  uint32_t now = millis();

  if (testExpired(g_test, g_cfg, now)) releaseTest(now);

  serviceLighting();                              // drain -> evaluate -> drive, ~10 ms tick

  serviceResetButton(now);

  // Mark a fresh OTA image good once it has shown it runs. Harmless on a
  // USB-flashed image.
  if (!g_markedValid && g_apUp && g_tickRan && now >= 5000) {
    g_markedValid = true;
    esp_err_t r = esp_ota_mark_app_valid_cancel_rollback();
    Serial.printf("ota: running image marked valid (%s)\n", esp_err_to_name(r));
  }

  // New Wi-Fi password: bring the AP back with it.
  if (g_apRestartPending && deadlinePassed(now, g_apRestartAt)) {
    g_apRestartPending = false;
    g_web.restartAp(g_ssid.c_str(), g_newWifiPass.c_str());
  }

  // A verified update is set to boot, or a factory reset erased the settings.
  // Restart only while parked: CAN was drained above, so this reading is
  // current again after an upload stalled loop(). If the rider has moved off,
  // the restart waits (or happens at the next power-up). GPIO0 must also read
  // released: restarting with it held boots the ROM download mode.
  if (g_restartPending && deadlinePassed(now, g_restartAt)) {
    if (parkedNow() && digitalRead(kResetBtnPin) == HIGH) {
      Serial.printf("%s: restarting\n", g_restartWhy);
      Serial.flush();
      ESP.restart();
    } else if (!g_restartHeldLogged) {
      g_restartHeldLogged = true;
      Serial.printf("%s: restart held until parked\n", g_restartWhy);
    }
  }

  // Stream CAN frame snapshots to the browser while discovery is active.
  static uint32_t lastDisc = 0;
  // 250 ms, not 100: a full table makes each message four times larger.
  if (g_discovery && now - lastDisc >= 250) {
    lastDisc = now;
    CanFrameSnapshot fr[CanState::MAX_FRAMES];
    int n = g_can.snapshot(fr, CanState::MAX_FRAMES);
    g_web.broadcast(framesMessage(fr, n));
  }

  // Keep the app's countdown honest, and re-announce the override to any
  // client that connected after it was set.
  static uint32_t lastTest = 0;
  if (g_test.kind != TestKind::Off && now - lastTest >= 1000) {
    lastTest = now;
    g_web.broadcast(testStateMessage(g_test, g_cfg, now));
  }
}
