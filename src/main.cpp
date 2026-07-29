#include <Arduino.h>
#include "domain/config.h"
#include "domain/config_json.h"
#include "domain/can_state.h"
#include "domain/behavior_engine.h"
#include "domain/channel_map.h"
#include "hal/pwm_pca9685.h"
#include "hal/can_bus.h"
#include "hal/storage.h"
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
}

void loop() {
  // Drain all pending CAN frames into the state cache.
  uint32_t id;
  uint8_t data[8];
  while (g_bus.receive(id, data)) g_can.update(id, data);

  // Evaluate -> compute -> drive, on a ~10 ms tick.
  static uint32_t last = 0;
  uint32_t now = millis();
  if (now - last >= 10) {
    last = now;
    LogicalState s = g_can.evaluate(g_cfg);
    OutputIntent o = computeOutputs(s, g_cfg, now, g_engine);
    applyIntent(g_pwm, o);
  }
}
