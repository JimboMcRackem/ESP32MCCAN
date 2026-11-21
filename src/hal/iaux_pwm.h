#pragma once
#include <cstdint>

// The pods' brightness signals (night-mode spec 6.1): one PWM duty per pod,
// in percent, on that pod's yellow wire. Implementations clamp anything above
// 100 rather than fault.
class IAuxPwm {
public:
  virtual ~IAuxPwm() = default;
  virtual void setDuty(uint8_t left, uint8_t right) = 0;
  // Stop both PWM signals and leave the pins driven low, for a planned
  // restart: the right pin is the MTDI strap and must read LOW at reset.
  virtual void park() = 0;
};
