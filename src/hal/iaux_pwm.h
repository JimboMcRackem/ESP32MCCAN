#pragma once
#include <cstdint>

// The pods' shared brightness signal (night-mode spec 6.1): one PWM duty, in
// percent, on every pod's yellow wire. Implementations clamp anything above
// 100 rather than fault.
class IAuxPwm {
public:
  virtual ~IAuxPwm() = default;
  virtual void setDuty(uint8_t percent) = 0;
};
