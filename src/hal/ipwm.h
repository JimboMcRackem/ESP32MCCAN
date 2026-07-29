#pragma once
#include <cstdint>

class IPwm {
public:
  virtual ~IPwm() = default;
  virtual void setDuty(uint8_t channel, uint8_t duty) = 0;
};
