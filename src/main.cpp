#include <Arduino.h>
#include "domain/config.h"
#include "domain/config_json.h"
#include "domain/can_state.h"
#include "domain/behavior_engine.h"
#include "domain/channel_map.h"
#include "hal/pwm_pca9685.h"
#include "hal/can_bus.h"
#include "hal/storage.h"
#include "domain/web_protocol.h"
#include "hal/web_server.h"
#include <Wire.h>

// Pin/bus assignments — provisional, finalized against the PCB (PCB plan).
// PWM outputs live on the PCA9685 (channels 0-13), reached over I2C — no per-channel GPIO.
static const int kI2cSda = 21;              // I2C to the PCA9685
static const int kI2cScl = 22;
static const uint8_t kPca9685Addr = 0x40;   // default PCA9685 address
static const uint32_t kPwmFreqHz = 1000;    // LED PWM frequency
static const int kCanRxPin = 16;            // CAN transceiver GPIOs (moved off the I2C pins)
static const int kCanTxPin = 17;
static const uint32_t kCanBitrate = 500000;

static Config      g_cfg;
static CanState    g_can;
static EngineState g_engine;
static Pca9685Pwm  g_pwm(kPca9685Addr);
static CanBus      g_bus;

static WebServerHal g_web;
static bool         g_discovery = false;

static const char* kApSsid = "MCCAN-Setup";
static const char* kApPass = "mccan1234";     // WPA2 requires >= 8 chars

void setup() {
  Serial.begin(115200);

  storage::begin();
  bool ok = false;
  g_cfg = configFromJson(storage::readConfig(), ok);  // falls back to defaults
  if (!ok) Serial.println("config missing/corrupt -> using Experia defaults");

  Wire.begin(kI2cSda, kI2cScl);
  if (!g_pwm.begin(kPwmFreqHz)) Serial.println("PCA9685 init failed");
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
