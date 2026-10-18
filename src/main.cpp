#include <Arduino.h>
#include "domain/config.h"
#include "domain/config_json.h"
#include "domain/can_state.h"
#include "domain/behavior_engine.h"
#include "domain/test_mode.h"
#include "domain/output_map.h"
#include "hal/outputs_gpio.h"
#include "hal/can_bus.h"
#include "hal/storage.h"
#include "domain/web_protocol.h"
#include "hal/web_server.h"

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
static const int kLedStatPin = 13;  // status LED D5; nothing signals on it yet, so it is held off

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

static Config      g_cfg;
static CanState    g_can;
static EngineState g_engine;
static TestMode    g_test;         // lighting override held by the web app
static EngineState g_testEngine;   // scenarios run against THIS, never g_engine
static CanBus      g_bus;

static WebServerHal g_web;
static bool         g_discovery = false;

static const char* kApSsid = "MCCAN-Setup";
static const char* kApPass = "mccan1234";     // WPA2 requires >= 8 chars

// Drop any active override and tell every client. Called on explicit exit,
// owner disconnect, and cap expiry.
static void releaseTest(uint32_t now) {
  g_test = TestMode{};
  g_testEngine = EngineState{};
  g_web.broadcast(testStateMessage(g_test, g_cfg, now));
}

void setup() {
  Serial.begin(115200);

  g_out.begin();   // all twelve outputs LOW before anything else

  pinMode(kDiagEnPin, OUTPUT);
  digitalWrite(kDiagEnPin, LOW);    // switch diagnostics off until something reads them
  pinMode(kCanStbPin, OUTPUT);
  digitalWrite(kCanStbPin, LOW);    // transceiver normal mode
  pinMode(kEn5vPin, OUTPUT);
  digitalWrite(kEn5vPin, HIGH);     // transceiver VCC: without it nothing is received
  pinMode(kLedStatPin, OUTPUT);
  digitalWrite(kLedStatPin, LOW);

  storage::begin();
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
    }
    if (act.applyConfig) {
      g_cfg = act.cfgOut;                              // live apply (single-threaded)
      storage::writeConfig(configToJson(g_cfg));       // persist for next boot
      g_web.sendTo(client, configMessage(g_cfg));      // confirm with the applied config
    }
    if (act.setDiscovery) {
      g_discovery = act.discoveryOut;
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
  });

  if (!g_web.begin(kApSsid, kApPass))
    Serial.println("SoftAP start failed");
  else
    Serial.printf("AP up: SSID=%s  http://192.168.4.1/\n", kApSsid);
}

void loop() {
  g_web.loop();                                   // DNS + HTTP + WS (fires onMessage inline)

  // Drain all pending CAN frames into the state cache.
  uint32_t id;
  uint8_t data[8];
  while (g_bus.receive(id, data)) g_can.update(id, data, millis());

  uint32_t now = millis();

  if (testExpired(g_test, g_cfg, now)) releaseTest(now);

  // Evaluate -> compute -> drive, on a ~10 ms tick.
  static uint32_t last = 0;
  if (now - last >= 10) {
    last = now;
    LogicalState s = g_can.evaluate(g_cfg, now);
    OutputIntent o = resolveOutputs(s, g_test, g_cfg, now, g_engine, g_testEngine);
    applyIntent(g_out, o);
  }

  // Stream CAN frame snapshots to the browser while discovery is active.
  static uint32_t lastDisc = 0;
  if (g_discovery && now - lastDisc >= 100) {
    lastDisc = now;
    CanFrameSnapshot fr[16];
    int n = g_can.snapshot(fr, 16);
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
