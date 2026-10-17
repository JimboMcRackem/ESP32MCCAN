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

// Pin/bus assignments — provisional, finalized against the PCB (PCB plan).
static const int kCanRxPin = 16;            // CAN transceiver GPIOs (moved off the I2C pins)
static const int kCanTxPin = 17;
static const uint32_t kCanBitrate = 500000;

// Provisional GPIO assignment in OutputIndex order - finalized against the PCB
// in the board plan. All twelve are plain outputs; none is a strapping pin that
// would float a lamp on at reset.
static const uint8_t kOutputPins[OUT_COUNT] = {
  13, 14,        // FL_DRL, FL_IND
  25, 26,        // FR_DRL, FR_IND
  27, 32, 33,    // RL_DRL, RL_IND, RL_BRK
  18, 19, 23,    // RR_DRL, RR_IND, RR_BRK
   4,  5,        // AUX_L, AUX_R
};
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
