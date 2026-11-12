#pragma once
#include "hal/iaux_pwm.h"

// The pods' shared brightness PWM on one LEDC channel (night-mode spec 6.1).
// The pin and frequency are passed in, as GpioOutputs takes its pin table.
class LedcAuxPwm : public IAuxPwm {
public:
  LedcAuxPwm(uint8_t pin, uint32_t freqHz);
  // Attaches the pin and drives duty 0. Call before any output can switch a
  // pod on.
  bool begin();
  void setDuty(uint8_t percent) override;
private:
  uint8_t  pin_;
  uint32_t freqHz_;
};
