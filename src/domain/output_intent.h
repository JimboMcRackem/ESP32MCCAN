#pragma once
#include "domain/color.h"
#include <cstdint>

struct OutputIntent {
  Rgb frontL, frontR, rearL, rearR;
  uint8_t denali = 0;   // 0-255 duty, applied to both Denali channels
};
