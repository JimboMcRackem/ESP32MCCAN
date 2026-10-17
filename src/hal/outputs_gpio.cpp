#include "hal/outputs_gpio.h"
#include <Arduino.h>

GpioOutputs::GpioOutputs(const uint8_t* pins, uint8_t count)
  : pins_(pins), count_(count) {}

bool GpioOutputs::begin() {
  if (!pins_ || count_ == 0) return false;
  for (uint8_t i = 0; i < count_; ++i) {
    pinMode(pins_[i], OUTPUT);
    digitalWrite(pins_[i], LOW);   // every lamp dark before anything else runs
  }
  return true;
}

void GpioOutputs::setOutput(uint8_t index, bool on) {
  if (index >= count_) return;
  digitalWrite(pins_[index], on ? HIGH : LOW);
}
