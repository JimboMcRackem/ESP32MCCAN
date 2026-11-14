#include "hal/aux_pwm_ledc.h"
#include "domain/aux_pwm.h"
#include <Arduino.h>

static const uint8_t kBits = 10;

LedcAuxPwm::LedcAuxPwm(uint8_t pin, uint32_t freqHz) : pin_(pin), freqHz_(freqHz) {}

bool LedcAuxPwm::begin() {
  if (!ledcAttach(pin_, freqHz_, kBits)) return false;
  ledcWrite(pin_, 0);   // pods' main LEDs dark before anything else runs
  return true;
}

void LedcAuxPwm::setDuty(uint8_t percent) {
  ledcWrite(pin_, ledcDutyFor(percent, kBits));
}
