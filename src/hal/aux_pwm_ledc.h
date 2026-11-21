#pragma once
#include "hal/iaux_pwm.h"

// The pods' brightness PWM, one LEDC channel per pod (night-mode spec 6.1).
// The pins and frequency are passed in, as GpioOutputs takes its pin table.
//
// The two sides start separately. The right pin is GPIO 12, the MTDI strap
// and TWAI's nominal TX: it must not be driven before CanBus::begin() has
// handed it back, so beginRight() is called after that, and until it succeeds
// every right duty is dropped and the pin stays as CanBus left it.
class LedcAuxPwm : public IAuxPwm {
public:
  LedcAuxPwm(uint8_t pinL, uint8_t pinR, uint32_t freqHz);
  // Attaches the left pin and drives duty 0. Call before any output can
  // switch a pod on.
  bool begin();
  // Attaches the right pin and drives duty 0. Call after the CAN bus starts.
  bool beginRight();
  void setDuty(uint8_t left, uint8_t right) override;
  void park() override;
private:
  uint8_t  pinL_, pinR_;
  uint32_t freqHz_;
  bool     leftUp_ = false;
  bool     rightUp_ = false;
};
