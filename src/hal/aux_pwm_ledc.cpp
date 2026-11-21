#include "hal/aux_pwm_ledc.h"
#include "domain/aux_pwm.h"
#include <Arduino.h>

static const uint8_t kBits = 10;

LedcAuxPwm::LedcAuxPwm(uint8_t pinL, uint8_t pinR, uint32_t freqHz)
    : pinL_(pinL), pinR_(pinR), freqHz_(freqHz) {}

bool LedcAuxPwm::begin() {
  if (!ledcAttach(pinL_, freqHz_, kBits)) return false;
  ledcWrite(pinL_, 0);   // left pod's main LEDs dark before anything else runs
  leftUp_ = true;
  return true;
}

bool LedcAuxPwm::beginRight() {
  if (!ledcAttach(pinR_, freqHz_, kBits)) return false;
  ledcWrite(pinR_, 0);
  rightUp_ = true;
  return true;
}

void LedcAuxPwm::park() {
  // Detach from LEDC and hold both pins low. Later duties are dropped.
  if (leftUp_)  { ledcDetach(pinL_); leftUp_ = false; }
  if (rightUp_) { ledcDetach(pinR_); rightUp_ = false; }
  pinMode(pinL_, OUTPUT); digitalWrite(pinL_, LOW);
  pinMode(pinR_, OUTPUT); digitalWrite(pinR_, LOW);
}

void LedcAuxPwm::setDuty(uint8_t left, uint8_t right) {
  if (leftUp_)  ledcWrite(pinL_, ledcDutyFor(left, kBits));
  if (rightUp_) ledcWrite(pinR_, ledcDutyFor(right, kBits));
}
